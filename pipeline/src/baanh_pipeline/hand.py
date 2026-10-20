"""Stage 08 — exact nearest-drainage distance, nearest channel elevation, HAND."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt
from shapely.geometry import shape

from .config import Config
from .geo import load_geojson, project_geom, rasterize_geom
from .util import StageRecord, atomic_write_json, ensure_dirs, utc_now


def run(
    cfg: Config,
    dem_burned_path: Path,
    channels_path: Path,
    out_hand: Path,
    out_distance: Path,
    out_meta: Path,
    max_channel_distance_m: float,
) -> dict:
    ensure_dirs()
    stage = StageRecord("08", "compute-hand", inputs=[dem_burned_path, channels_path])
    res = float(cfg.aoi.resolution_m)
    nodata = float(cfg.aoi.nodata)
    max_distance = float(max_channel_distance_m)

    with rasterio.open(dem_burned_path) as src:
        dem = src.read(1)
        transform = src.transform
        width = src.width
        height = src.height
        crs = src.crs
        dem_nodata = float(src.nodata if src.nodata is not None else nodata)
    with rasterio.open(channels_path) as src:
        channel = src.read(1) > 0
        if (src.width, src.height) != (width, height):
            raise RuntimeError("stage 08: channel raster shape does not match DEM")
    if not channel.any():
        raise RuntimeError("stage 08: no channel cells; HAND cannot be computed")

    print(f"[08] distance transform on {width}x{height}, channels={int(channel.sum())}")
    distance, indices = distance_transform_edt(
        ~channel, sampling=(res, res), return_indices=True
    )
    iy = indices[0]
    ix = indices[1]
    nearest_z = dem[iy, ix]
    del indices, iy, ix
    distance32 = distance.astype(np.float32)
    del distance

    raw_hand = dem - nearest_z
    valid = (dem != dem_nodata) & (nearest_z != dem_nodata) & (distance32 <= max_distance)
    clamped = valid & (raw_hand < 0)
    hand = np.full((height, width), nodata, dtype=np.float32)
    hand[valid] = np.maximum(raw_hand[valid], 0.0)
    del raw_hand

    valid_cells = int(valid.sum())
    clamped_cells = int(clamped.sum())
    clamped_share = clamped_cells / valid_cells if valid_cells else 1.0
    valid_values = hand[valid]
    if valid_values.size == 0:
        raise RuntimeError("stage 08: no valid HAND cells")

    assam_mask = None
    state_path = cfg.root / "public" / "data" / "admin" / "assam-state.geojson"
    if state_path.exists():
        state = load_geojson(state_path)
        geoms = [shape(f["geometry"]) for f in state.get("features", [])]
        if geoms:
            from shapely.ops import unary_union

            state_utm = project_geom(
                unary_union(geoms), cfg.aoi.output_crs, cfg.aoi.analysis_crs
            )
            assam_mask = rasterize_geom(
                state_utm, transform, width, height, dtype="uint8"
            ).astype(bool)
    if assam_mask is None or not assam_mask.any():
        raise RuntimeError(
            "stage 08: Assam state mask unavailable; run stage 05 before compute-hand"
        )
    assam_cells = int(assam_mask.sum())
    valid_assam = int((valid & assam_mask).sum())
    valid_assam_share = valid_assam / assam_cells if assam_cells else 0.0

    warning = None
    if clamped_share > float(cfg.pipeline["validation"]["max_clamped_negative_share"]):
        warning = f"clamped negative HAND cells {clamped_share:.2%} exceed 2%"
        print(f"[08] WARNING: {warning}")
    if valid_assam_share < float(cfg.pipeline["validation"]["warn_valid_hand_share"]):
        msg = f"valid HAND covers only {valid_assam_share:.2%} of Assam-masked cells"
        print(f"[08] WARNING: {msg}")
        warning = f"{warning}; {msg}" if warning else msg
    if valid_assam_share < float(cfg.pipeline["validation"]["min_valid_hand_share"]):
        raise RuntimeError(
            f"stage 08: valid HAND covers {valid_assam_share:.2%} of Assam cells, "
            f"below the {cfg.pipeline['validation']['min_valid_hand_share']:.0%} floor"
        )

    meta = {
        "schema_version": "1.0.0",
        "valid_cells": valid_cells,
        "nodata_cells": int((~valid).sum()),
        "clamped_negative_cells": clamped_cells,
        "clamped_negative_share": clamped_share,
        "max_distance_m": float(distance32.max()),
        "max_channel_distance_m": max_distance,
        "p50_hand_m": float(np.percentile(valid_values, 50)),
        "p95_hand_m": float(np.percentile(valid_values, 95)),
        "channel_elevation_min_m": float(dem[channel & (dem != dem_nodata)].min()),
        "channel_elevation_max_m": float(dem[channel & (dem != dem_nodata)].max()),
        "assam_cells": assam_cells,
        "valid_assam_cells": valid_assam,
        "valid_assam_share": valid_assam_share,
        "warning": warning,
        "generated_at": utc_now(),
    }

    profiles = {
        out_hand: (hand, "float32", nodata),
        out_distance: (distance32, "float32", nodata),
        out_hand.parent / "nearest-channel-elevation-90m.tif": (nearest_z.astype(np.float32), "float32", nodata),
    }
    for path, (array, dtype, nd) in profiles.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=width,
            height=height,
            count=1,
            dtype=dtype,
            crs=crs,
            transform=transform,
            nodata=nd,
            compress="deflate",
            predictor=3,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            BIGTIFF="IF_SAFER",
        ) as dst:
            dst.write(array, 1)

    atomic_write_json(out_meta, meta, indent=2, sort_keys=True)
    stage.out(out_hand, out_distance, out_meta, out_hand.parent / "nearest-channel-elevation-90m.tif")
    stage.metric("valid_cells", valid_cells)
    stage.metric("clamped_negative_share", round(clamped_share, 6))
    stage.metric("valid_assam_share", round(valid_assam_share, 6))
    stage.metric("p50_hand_m", meta["p50_hand_m"])
    stage.metric("p95_hand_m", meta["p95_hand_m"])
    stage.metric("max_distance_m", meta["max_distance_m"])
    stage.finish(
        "Exact Euclidean EDT on the channel mask (8-connected metric, sampling 90 m), "
        "nearest channel elevation sampled from the burned DEM, negatives clamped, "
        f"cells beyond {max_distance:.0f} m set nodata. No smoothing."
    )
    print(
        f"[08] ok: HAND valid {valid_cells / 1e6:.1f}M cells, p50 {meta['p50_hand_m']:.2f} m, "
        f"p95 {meta['p95_hand_m']:.2f} m, Assam valid share {valid_assam_share:.1%}, "
        f"clamped {clamped_share:.2%}"
    )
    return meta
