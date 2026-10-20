"""AOI v2 — the valley-floor analysis domain from REVIEW-02 A1.

``AOI_v2 = (inside Assam) ∩ (DEM <= 120 m)``.  The 2 km edge buffer is kept
only for raster continuity; the reported area, channel-cell share and flood
metrics use the core mask, which is the denominator the review measured
(52,358 km² at 90 m).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes as raster_shapes
from scipy.ndimage import distance_transform_edt
from shapely.geometry import shape
from shapely.ops import unary_union

from .config import Config
from .geo import (
    load_geojson,
    polygon_parts,
    project_geom,
    rasterize_geom,
    row_cell_areas_km2,
    valid,
)
from .util import atomic_write_json, utc_now

CORE_TIF = "aoi-v2-core-90m.tif"
EDGE_TIF = "aoi-v2-edge-90m.tif"
CLIP_TIF = "aoi-v2-clip-5km-90m.tif"
META_JSON = "aoi-v2.json"


@dataclass
class AoiV2:
    core: np.ndarray
    edge: np.ndarray
    clip: np.ndarray
    transform: rasterio.Affine
    width: int
    height: int
    crs: str
    core_area_km2: float
    edge_area_km2: float
    clip_area_km2: float
    assam_area_km2: float
    core_cells: int
    edge_cells: int
    clip_cells: int
    assam_cells: int
    meta: dict

    def geometry(self, which: str = "clip"):
        mask = {"core": self.core, "edge": self.edge, "clip": self.clip}[which]
        return geometry_from_mask(mask, self.transform)


def _row_area(areas: np.ndarray, mask: np.ndarray) -> float:
    return float(areas[:, 0].dot(mask.sum(axis=1)))


def geometry_from_mask(mask: np.ndarray, transform: rasterio.Affine):
    """Dissolve a boolean raster mask into one (Multi)Polygon."""
    if not mask.any():
        raise RuntimeError("AOI v2: cannot polygonise an empty mask")
    parts = [
        shape(mapping)
        for mapping, value in raster_shapes(
            mask.astype(np.uint8), mask=mask, connectivity=8, transform=transform
        )
        if value
    ]
    if not parts:
        raise RuntimeError("AOI v2: mask produced no polygon parts")
    geom = valid(unary_union(parts))
    if geom is None or geom.is_empty:
        raise RuntimeError("AOI v2: mask polygon is empty after union")
    return geom


def _state_mask(cfg: Config, state_path: Path, transform, width: int, height: int):
    state = load_geojson(state_path)
    geoms = [shape(f["geometry"]) for f in state.get("features", [])]
    if not geoms:
        raise RuntimeError("AOI v2: state outline has no geometry")
    state_utm = project_geom(unary_union(geoms), cfg.aoi.output_crs, cfg.aoi.analysis_crs)
    mask = rasterize_geom(state_utm, transform, width, height, dtype="uint8").astype(bool)
    if not mask.any():
        raise RuntimeError("AOI v2: state mask is empty")
    return mask, state_utm


def build(cfg: Config, dem_path: Path, state_path: Path) -> AoiV2:
    domain_cfg = cfg.aoi.raw["analysis_domain"]
    max_dem = float(domain_cfg["max_dem_m"])
    edge_buffer_m = float(domain_cfg["edge_buffer_km"]) * 1000.0
    clip_buffer_m = float(domain_cfg["channel_clip_buffer_km"]) * 1000.0
    res = float(cfg.aoi.resolution_m)
    nodata = float(cfg.aoi.nodata)

    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        transform = src.transform
        width = src.width
        height = src.height
        crs = str(src.crs)
        dem_nodata = float(src.nodata if src.nodata is not None else nodata)
    state_mask, _ = _state_mask(cfg, state_path, transform, width, height)
    valid_dem = dem != dem_nodata
    core = state_mask & valid_dem & (dem <= max_dem)
    if not core.any():
        raise RuntimeError(f"AOI v2: no cells inside Assam at or below {max_dem:.0f} m")

    distance = distance_transform_edt(~core, sampling=(res, res))
    edge = distance <= edge_buffer_m
    clip = distance <= clip_buffer_m
    del distance

    areas = row_cell_areas_km2(transform, height, width, cfg.aoi.analysis_crs)
    core_area = _row_area(areas, core)
    edge_area = _row_area(areas, edge)
    clip_area = _row_area(areas, clip)
    assam_area = _row_area(areas, state_mask)
    meta = {
        "schema_version": "1.0.0",
        "definition": "(inside Assam) intersect (DEM <= max_dem_m)",
        "max_dem_m": max_dem,
        "edge_buffer_km": float(domain_cfg["edge_buffer_km"]),
        "channel_clip_buffer_km": float(domain_cfg["channel_clip_buffer_km"]),
        "analysis_crs": cfg.aoi.analysis_crs,
        "resolution_m": res,
        "core_area_km2": round(core_area, 6),
        "edge_area_km2": round(edge_area, 6),
        "channel_clip_area_km2": round(clip_area, 6),
        "assam_area_km2": round(assam_area, 6),
        "assam_area_km2_reference": float(cfg.aoi.raw["assam_area_km2_reference"]),
        "flood_prone_area_km2": float(cfg.aoi.raw["flood_prone_area_km2"]),
        "core_cells": int(core.sum()),
        "edge_cells": int(edge.sum()),
        "channel_clip_cells": int(clip.sum()),
        "assam_cells": int(state_mask.sum()),
        "note": (
            "Metrics use the core mask (inside Assam, DEM <= 120 m). The 2 km edge "
            "buffer is for raster continuity only and is not counted as AOI v2 area. "
            "The channel clip mask is AOI v2 + 5 km."
        ),
        "generated_at": utc_now(),
    }
    return AoiV2(
        core=core,
        edge=edge,
        clip=clip,
        transform=transform,
        width=width,
        height=height,
        crs=crs,
        core_area_km2=core_area,
        edge_area_km2=edge_area,
        clip_area_km2=clip_area,
        assam_area_km2=assam_area,
        core_cells=int(core.sum()),
        edge_cells=int(edge.sum()),
        clip_cells=int(clip.sum()),
        assam_cells=int(state_mask.sum()),
        meta=meta,
    )


def write_mask(path: Path, mask: np.ndarray, transform, crs: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "width": mask.shape[1],
        "height": mask.shape[0],
        "count": 1,
        "dtype": "uint8",
        "crs": crs,
        "transform": transform,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "BIGTIFF": "IF_SAFER",
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(mask.astype(np.uint8), 1)


def save(cfg: Config, aoi: AoiV2) -> dict[str, Path]:
    work = cfg.root / "pipeline" / "work"
    paths = {
        "core": work / CORE_TIF,
        "edge": work / EDGE_TIF,
        "clip": work / CLIP_TIF,
        "meta": work / META_JSON,
    }
    write_mask(paths["core"], aoi.core, aoi.transform, aoi.crs)
    write_mask(paths["edge"], aoi.edge, aoi.transform, aoi.crs)
    write_mask(paths["clip"], aoi.clip, aoi.transform, aoi.crs)
    atomic_write_json(paths["meta"], aoi.meta, indent=2, sort_keys=True)
    return paths


def load_saved(cfg: Config) -> AoiV2:
    work = cfg.root / "pipeline" / "work"
    meta_path = work / META_JSON
    if not meta_path.exists():
        raise RuntimeError("AOI v2 metadata is missing; run stage 06 (build-rivers) first")
    import json

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    with rasterio.open(work / CORE_TIF) as src:
        core = src.read(1).astype(bool)
        transform = src.transform
        width = src.width
        height = src.height
        crs = str(src.crs)
    edge = core
    clip = core
    if (work / EDGE_TIF).exists():
        with rasterio.open(work / EDGE_TIF) as src:
            edge = src.read(1).astype(bool)
    if (work / CLIP_TIF).exists():
        with rasterio.open(work / CLIP_TIF) as src:
            clip = src.read(1).astype(bool)
    return AoiV2(
        core=core,
        edge=edge,
        clip=clip,
        transform=transform,
        width=width,
        height=height,
        crs=crs,
        core_area_km2=float(meta["core_area_km2"]),
        edge_area_km2=float(meta["edge_area_km2"]),
        clip_area_km2=float(meta["channel_clip_area_km2"]),
        assam_area_km2=float(meta["assam_area_km2"]),
        core_cells=int(core.sum()),
        edge_cells=int(edge.sum()),
        clip_cells=int(clip.sum()),
        assam_cells=int(meta.get("assam_cells", 0)),
        meta=meta,
    )


def polygon_parts_count(geom) -> int:
    return len(polygon_parts(geom))
