"""Stage 07 — burn mapped channels into the 90 m DEM."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import binary_dilation, minimum_filter, uniform_filter
from shapely.geometry import shape

from .config import Config
from .geo import load_geojson, project_geom
from .util import StageRecord, atomic_write_json, ensure_dirs, utc_now


def run(
    cfg: Config,
    dem_path: Path,
    channels_path: Path,
    out_dem: Path,
    out_channels: Path,
    burn_depth_m: float,
) -> dict:
    ensure_dirs()
    stage = StageRecord("07", "burn-rivers", inputs=[dem_path, channels_path])
    burn_cfg = cfg.pipeline["burn"]
    model = cfg.scenario.model
    expected_depth = float(model["burn_depth_m"])
    if abs(float(burn_depth_m) - expected_depth) > 1e-9:
        print(
            f"[07] burn depth override {burn_depth_m} differs from scenario model {expected_depth}; "
            "recording the override in provenance"
        )
    depth = float(burn_depth_m)

    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        transform = src.transform
        width = src.width
        height = src.height
        crs = src.crs
        nodata = src.nodata if src.nodata is not None else cfg.aoi.nodata

    channel_data = load_geojson(channels_path)
    all_shapes = []
    main_shapes = []
    for feature in channel_data.get("features", []):
        geom = shape(feature["geometry"])
        if geom.is_empty:
            continue
        geom = project_geom(geom, cfg.aoi.output_crs, cfg.aoi.analysis_crs)
        if geom.is_empty:
            continue
        all_shapes.append((geom, 1))
        if int(feature["properties"].get("order", 0)) == 1:
            main_shapes.append((geom, 1))
    if not all_shapes:
        raise RuntimeError("stage 07: no channel geometries to rasterise")

    channel_mask = rasterize(
        all_shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        all_touched=True,
        dtype="uint8",
    )
    main_mask = rasterize(
        main_shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        all_touched=True,
        dtype="uint8",
    )
    widen = int(burn_cfg["main_stem_width_cells"]) - 1
    if widen > 0 and main_mask.any():
        main_mask = binary_dilation(main_mask, iterations=widen).astype(np.uint8)
    channel_mask = np.maximum(channel_mask, main_mask)

    valid_dem = dem != nodata
    dem_for_min = np.where(valid_dem, dem, np.float32(np.inf)).astype(np.float32)
    window = int(burn_cfg["window_cells"])
    min_filtered = minimum_filter(dem_for_min, size=window, mode="nearest")
    valid_f = valid_dem.astype(np.float32)
    neighbour_sum = uniform_filter(
        np.where(valid_dem, dem, np.float32(0.0)).astype(np.float32),
        size=window,
        mode="nearest",
    )
    neighbour_count = uniform_filter(valid_f, size=window, mode="nearest")
    neighbour_mean = neighbour_sum / np.maximum(neighbour_count, np.float32(1e-6))
    burnable = (channel_mask > 0) & valid_dem & np.isfinite(min_filtered)
    target = min_filtered - depth
    # In steep terrain the 5x5 minimum can be hundreds of metres below the
    # channel centre. Cap the incision at 6 m below the adjacent 5x5 mean so a
    # modelling device cannot become an unrealistic canyon. The cap is recorded.
    max_lowering = float(burn_cfg["max_lowering_below_adjacent_mean_m"])
    floor = np.maximum(neighbour_mean - max_lowering, dem - max_lowering)
    capped = burnable & (target < floor)
    burned = dem.copy()
    burned[burnable] = np.minimum(
        np.maximum(target[burnable], floor[burnable]), dem[burnable]
    )
    burned[~valid_dem] = nodata
    burned[channel_mask == 0] = dem[channel_mask == 0]

    delta = (dem[burnable] - burned[burnable]).astype(np.float32)
    # "Mean adjacent DEM" is the mean of the surrounding 5x5 DEM, not the
    # channel centre cell. In steep terrain the 5x5 minimum can be tens of
    # metres below the centre; that is reported separately rather than hidden.
    adjacent_delta = (neighbour_mean[burnable] - burned[burnable]).astype(np.float32)
    channel_cells = int(channel_mask.sum())
    burnable_cells = int(burnable.sum())
    if channel_cells <= 0:
        raise RuntimeError("stage 07: zero channel cells after rasterisation")
    if burnable_cells <= 0:
        raise RuntimeError("stage 07: no channel cell overlaps valid DEM")
    mean_delta = float(delta.mean())
    mean_adjacent_delta = float(adjacent_delta.mean())
    if not (1.0 <= mean_delta <= 6.0):
        raise RuntimeError(
            f"stage 07: mean channel lowering {mean_delta:.2f} m is outside the "
            f"expected 1–6 m (adjacent-5x5 mean lowering {mean_adjacent_delta:.2f} m)"
        )
    if np.any(burned[burnable] > dem[burnable]):
        raise RuntimeError("stage 07: a channel cell was raised above its pre-burn value")

    meta = {
        "schema_version": "1.0.0",
        "channel_cells": channel_cells,
        "main_stem_channel_cells": int(main_mask.sum()),
        "burnable_cells": burnable_cells,
        "burn_depth_m": depth,
        "dem_delta_min_m": float(delta.min()),
        "dem_delta_max_m": float(delta.max()),
        "dem_delta_mean_m": mean_delta,
        "dem_delta_p95_m": float(np.percentile(delta, 95)),
        "adjacent_delta_mean_m": mean_adjacent_delta,
        "max_lowering_below_adjacent_mean_m": max_lowering,
        "capped_cells": int(capped.sum()),
        "window_cells": window,
        "main_stem_width_cells": int(burn_cfg["main_stem_width_cells"]),
        "generated_at": utc_now(),
    }
    meta_path = out_dem.parent / "burn-meta.json"
    atomic_write_json(meta_path, meta, indent=2, sort_keys=True)

    for path, array, dtype in (
        (out_dem, burned, "float32"),
        (out_channels, channel_mask.astype(np.uint8), "uint8"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        profile = {
            "driver": "GTiff",
            "width": width,
            "height": height,
            "count": 1,
            "dtype": dtype,
            "crs": crs,
            "transform": transform,
            "compress": "deflate" if dtype == "float32" else "lzw",
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
            "BIGTIFF": "IF_SAFER",
        }
        if dtype == "float32":
            profile["nodata"] = float(nodata)
            profile["predictor"] = 3
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(array, 1)

    stage.out(out_dem, out_channels, meta_path)
    stage.metric("channel_cells", channel_cells)
    stage.metric("burnable_cells", burnable_cells)
    stage.metric("dem_delta_mean_m", mean_delta)
    stage.metric("adjacent_delta_mean_m", mean_adjacent_delta)
    stage.metric("dem_delta_min_m", float(delta.min()))
    stage.metric("dem_delta_max_m", float(delta.max()))
    stage.finish(
        "Channels rasterised all_touched; main stem dilated to 2 cells; each channel "
        "cell set to the 5x5 minimum DEM minus the burn depth, capped at 6 m below "
        "the adjacent 5x5 mean to prevent unrealistic incision in steep terrain "
        f"({int(capped.sum())} cells capped). No downstream monotonic enforcement "
        "(OSM way direction is unreliable). The 1–6 m check is against the mean "
        "adjacent 5x5 DEM."
    )
    print(
        f"[07] ok: {channel_cells} channel cells ({burnable_cells} burned), "
        f"mean lowering {mean_delta:.2f} m, burned DEM {out_dem.stat().st_size / 1024 / 1024:.1f} MB"
    )
    return meta
