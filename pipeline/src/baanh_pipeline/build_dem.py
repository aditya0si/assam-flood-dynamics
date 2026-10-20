"""Stage 04 — mosaic Terrarium tiles, warp to 90 m EPSG:32646 and hillshade."""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.fill import fillnodata
from rasterio.transform import Affine
from rasterio.warp import reproject, transform_bounds

import mercantile

from .config import Config
from .geo import analysis_grid, grid_window_for_bounds
from .util import StageRecord, atomic_write_json, ensure_dirs, utc_now


def _decode_tile(path: Path, nodata: float, min_valid: float, max_valid: float) -> np.ndarray:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    elevation = (
        rgb[:, :, 0].astype(np.float32) * 256.0
        + rgb[:, :, 1].astype(np.float32)
        + rgb[:, :, 2].astype(np.float32) / 256.0
        - 32768.0
    )
    # Terrarium void pixels decode to implausible values (observed -5456 m in
    # this AOI). Mark them nodata rather than letting bilinear interpolation
    # smear them across neighbouring cells.
    elevation[(elevation < min_valid) | (elevation > max_valid)] = nodata
    elevation.setflags(write=False)
    return elevation


def _make_padded_reader(
    tiles_dir: Path, nodata: float, min_valid: float, max_valid: float, pad: int = 2
):
    @lru_cache(maxsize=96)
    def decoded(z: int, x: int, y: int) -> np.ndarray | None:
        path = tiles_dir / str(z) / str(x) / f"{y}.png"
        if not path.exists():
            return None
        return _decode_tile(path, nodata, min_valid, max_valid)

    def read(tile: mercantile.Tile) -> tuple[np.ndarray, Affine]:
        size = 256
        bounds = mercantile.xy_bounds(tile)
        res = (bounds.right - bounds.left) / size
        padded = np.full((size + 2 * pad, size + 2 * pad), nodata, dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                arr = decoded(tile.z, tile.x + dx, tile.y + dy)
                if arr is None:
                    continue
                # Neighbour origin in padded pixel coordinates.
                ox = pad + dx * size
                oy = pad + dy * size
                # Intersection of [0,size) of the neighbour with the padded box.
                sx0 = max(0, -ox)
                sy0 = max(0, -oy)
                sx1 = min(size, padded.shape[1] - ox)
                sy1 = min(size, padded.shape[0] - oy)
                if sx1 <= sx0 or sy1 <= sy0:
                    continue
                padded[oy + sy0 : oy + sy1, ox + sx0 : ox + sx1] = arr[sy0:sy1, sx0:sx1]
        extended = Affine(
            res,
            0.0,
            bounds.left - pad * res,
            0.0,
            -res,
            bounds.top + pad * res,
        )
        return padded, extended

    return read


def _hillshade(dem: np.ndarray, res: float, azimuth_deg: float, altitude_deg: float) -> np.ndarray:
    z = np.where(dem <= -9998.0, np.nan, dem).astype(np.float32)
    # Shallow holes left after fillnodata are interpolated only for the image.
    if np.isnan(z).any():
        from scipy.ndimage import distance_transform_edt

        invalid = np.isnan(z)
        indices = distance_transform_edt(invalid, return_distances=False, return_indices=True)
        z = z[tuple(indices)]
    dzdx = np.gradient(z, axis=1) / res
    dzdy = -np.gradient(z, axis=0) / res
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(dzdy, -dzdx)
    azimuth = math.radians(azimuth_deg)
    altitude = math.radians(altitude_deg)
    shaded = np.sin(altitude) * np.cos(slope) + np.cos(altitude) * np.sin(slope) * np.cos(
        azimuth - aspect
    )
    shaded = np.clip(shaded, 0.0, 1.0)
    return (30.0 + 225.0 * shaded).astype(np.uint8)


def run(
    cfg: Config,
    tiles_dir: Path,
    index_path: Path,
    out_dem: Path,
    out_hillshade: Path,
    hillshade_width: int,
) -> dict:
    ensure_dirs()
    stage = StageRecord("04", "build-dem", inputs=[index_path])
    dem_cfg = cfg.pipeline["dem"]
    aoi = cfg.aoi
    res = aoi.resolution_m
    nodata = aoi.nodata
    transform, width, height, bounds = analysis_grid(aoi)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    present = {(int(t["z"]), int(t["x"]), int(t["y"])) for t in index["tiles"]}
    print(f"[04] target grid {width} x {height} = {width * height / 1e6:.1f}M cells; {len(present)} tiles")

    min_valid = float(dem_cfg["decode_min_valid_m"])
    max_valid = float(dem_cfg["decode_max_valid_m"])
    dem = np.full((height, width), nodata, dtype=np.float32)
    reader = _make_padded_reader(tiles_dir, nodata, min_valid, max_valid, pad=2)
    written = 0
    for order, (z, x, y) in enumerate(sorted(present, key=lambda item: (item[2], item[1]))):
        tile = mercantile.Tile(x=x, y=y, z=z)
        source, src_transform = reader(tile)
        west, south, east, north = mercantile.bounds(tile)
        tb = transform_bounds("EPSG:4326", aoi.analysis_crs, west, south, east, north, densify_pts=21)
        row0, row1, col0, col1 = grid_window_for_bounds(transform, tb, pad_cells=1)
        row1 = min(height, row1)
        col1 = min(width, col1)
        if row1 <= row0 or col1 <= col0:
            continue
        window_transform = transform * Affine.translation(col0, row0)
        temp = np.full((row1 - row0, col1 - col0), nodata, dtype=np.float32)
        reproject(
            source=source,
            destination=temp,
            src_transform=src_transform,
            src_crs="EPSG:3857",
            dst_transform=window_transform,
            dst_crs=aoi.analysis_crs,
            resampling=Resampling.bilinear,
            src_nodata=nodata,
            dst_nodata=nodata,
            num_threads=1,
        )
        temp[(temp < min_valid) | (temp > max_valid)] = nodata
        target = dem[row0:row1, col0:col1]
        np.copyto(target, temp, where=(temp != nodata))
        written += int((temp != nodata).sum())
        if (order + 1) % 100 == 0 or order + 1 == len(present):
            print(f"[04] warped {order + 1}/{len(present)} tiles ({written / 1e6:.1f}M cells)")

    void_before = int((dem == nodata).sum())
    if void_before:
        valid_mask = (dem != nodata).astype(np.uint8)
        dem = fillnodata(
            dem,
            mask=valid_mask,
            max_search_distance=int(dem_cfg["fill_max_search_cells"]),
            smoothing_iterations=0,
        )
    void_after = int((dem == nodata).sum())
    if void_after:
        dem[dem == nodata] = nodata

    valid = dem[dem != nodata]
    if valid.size == 0:
        raise RuntimeError("stage 04: DEM is entirely nodata; tile fetch failed")
    dem_min = float(valid.min())
    dem_max = float(valid.max())
    dem_mean = float(valid.mean())
    exact_zero_share = float((valid == 0.0).mean())
    print(
        f"[04] DEM min {dem_min:.1f} m, max {dem_max:.1f} m, "
        f"void before {void_before}, after {void_after}, zero share {exact_zero_share:.2%}"
    )
    if dem_min < float(dem_cfg["elevation_min_plausible_m"]) or dem_min > float(
        dem_cfg["elevation_min_upper_m"]
    ):
        raise RuntimeError(
            f"stage 04: implausible minimum elevation {dem_min:.1f} m "
            f"(expected {dem_cfg['elevation_min_plausible_m']}..{dem_cfg['elevation_min_upper_m']})"
        )
    if dem_max < 0 or dem_max > float(dem_cfg["elevation_max_upper_m"]):
        raise RuntimeError(
            f"stage 04: implausible maximum elevation {dem_max:.1f} m "
            f"(expected 0..{dem_cfg['elevation_max_upper_m']})"
        )
    if exact_zero_share > 0.10:
        raise RuntimeError(
            f"stage 04: {exact_zero_share:.1%} of cells are exactly 0 m; possible ocean/missing tiles"
        )

    out_dem.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out_dem,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype="float32",
        crs=aoi.analysis_crs,
        transform=transform,
        nodata=nodata,
        compress="deflate",
        predictor=3,
        tiled=True,
        blockxsize=256,
        blockysize=256,
        BIGTIFF="IF_SAFER",
    ) as dst:
        dst.write(dem, 1)

    # Hillshade image, positioned in the app with the AOI Mercator corners.
    merc = transform_bounds(
        "EPSG:4326", "EPSG:3857", *aoi.bbox, densify_pts=21
    )
    merc_width = merc[2] - merc[0]
    merc_height = merc[3] - merc[1]
    image_width = int(hillshade_width)
    image_height = max(1, int(round(image_width * merc_height / merc_width)))
    shade = _hillshade(dem, res, dem_cfg["hillshade_azimuth_deg"], dem_cfg["hillshade_altitude_deg"])
    image = Image.fromarray(shade, mode="L").resize((image_width, image_height), Image.LANCZOS)
    out_hillshade.parent.mkdir(parents=True, exist_ok=True)
    tmp_image = out_hillshade.with_suffix(".tmp.webp")
    image.save(
        tmp_image,
        format="WEBP",
        quality=int(dem_cfg["hillshade_webp_quality"]),
        method=6,
    )
    tmp_image.replace(out_hillshade)

    meta = {
        "schema_version": "1.0.0",
        "crs": aoi.analysis_crs,
        "width": width,
        "height": height,
        "resolution_m": res,
        "transform": list(transform)[:6],
        "bounds": list(bounds),
        "nodata": nodata,
        "min_m": dem_min,
        "max_m": dem_max,
        "mean_m": dem_mean,
        "void_cells_before_fill": void_before,
        "void_cells_remaining": void_after,
        "exact_zero_share": exact_zero_share,
        "tile_count": len(present),
        "hillshade": {
            "path": str(out_hillshade),
            "width_px": image_width,
            "height_px": image_height,
            "bytes": out_hillshade.stat().st_size,
            "quality": int(dem_cfg["hillshade_webp_quality"]),
            "azimuth_deg": float(dem_cfg["hillshade_azimuth_deg"]),
            "altitude_deg": float(dem_cfg["hillshade_altitude_deg"]),
            "bounds_mercator": list(merc),
            "width_m_mercator": merc_width,
            "height_m_mercator": merc_height,
        },
        "generated_at": utc_now(),
    }
    meta_path = out_dem.parent / "dem-meta.json"
    atomic_write_json(meta_path, meta, indent=2, sort_keys=True)
    stage.inputs = [index_path, tiles_dir]
    stage.out(out_dem, out_hillshade, meta_path)
    stage.metric("grid", [width, height])
    stage.metric("min_m", dem_min)
    stage.metric("max_m", dem_max)
    stage.metric("void_before", void_before)
    stage.metric("void_after", void_after)
    stage.metric("hillshade_bytes", out_hillshade.stat().st_size)
    stage.source(
        cfg.sources["terrain"]["name"],
        cfg.sources["terrain"]["url_template"],
        cfg.sources["terrain"]["licence"],
    )
    stage.finish(
        "Bilinear warp z11 Web Mercator -> EPSG:32646 90 m; small voids filled with "
        f"fillnodata max_search={dem_cfg['fill_max_search_cells']}; hillshade "
        f"{dem_cfg['hillshade_azimuth_deg']}°/{dem_cfg['hillshade_altitude_deg']}°."
    )
    print(f"[04] ok: DEM {out_dem.stat().st_size / 1024 / 1024:.1f} MB, hillshade {out_hillshade.stat().st_size / 1024:.0f} KB")
    return meta
