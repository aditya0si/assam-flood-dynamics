"""Stage 09 — HAND inundation, area filter and half-resolution PNG frames.

REVIEW-04 C1/C2 replaces the A3 per-band GeoJSON contract with a raster frame
contract: one 5-class paletted PNG per step at half the analysis resolution,
plus ``frame-index.json``.  The wet mask receives a >=9-cell connected-component
area filter before statistics, rendering and mask output.  Morphological opening
is forbidden and is not imported anywhere in this module.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import transform_bounds
from scipy.ndimage import label
from shapely.geometry import shape

from . import aoi_domain
from .config import Config
from .geo import load_geojson, project_geom, row_cell_areas_km2
from .util import (
    StageRecord,
    atomic_write_bytes,
    atomic_write_json,
    ensure_dirs,
    path_size,
)


BAND_LABELS = [
    ("0.0-0.5", 0.0, 0.5),
    ("0.5-1.5", 0.5, 1.5),
    ("1.5-3.0", 1.5, 3.0),
    ("3.0+", 3.0, None),
]

# REVIEW-05 D2: the per-step depth distribution is an artifact, not a sentence.
DECILE_KEYS = ("p10", "p25", "p50", "p75", "p90", "p95")
DECILE_QUANTILES = (10.0, 25.0, 50.0, 75.0, 90.0, 95.0)

# id, label, RGBA, lower edge, upper edge.  Class 0 is dry and fully transparent.
CLASS_PALETTE = [
    (0, "dry", (0, 0, 0, 0), None, 0.0),
    (1, "0.0-0.5", (158, 202, 225, 235), 0.0, 0.5),
    (2, "0.5-1.5", (66, 146, 198, 235), 0.5, 1.5),
    (3, "1.5-3.0", (8, 81, 156, 240), 1.5, 3.0),
    (4, "3.0+", (3, 19, 94, 245), 3.0, None),
]


def _band_index(depth: np.ndarray, edges: list[float | None]) -> np.ndarray:
    low = np.asarray(edges[:-1], dtype=np.float32)
    band = np.digitize(depth, low, right=True).astype(np.uint8)
    band[depth <= 0] = 0
    return band


def _row_area(areas: np.ndarray, mask: np.ndarray) -> float:
    return float(areas[:, 0].dot(mask.sum(axis=1)))


def _depth_deciles(values: np.ndarray) -> dict[str, float]:
    """REVIEW-05 D2: depth percentiles over the wet cells of one step.

    The deciles are published independently.  No consumer may collapse them
    into a single number: the p10–p95 strip is the shape evidence that the
    V-A5 spread rule is designed to test.
    """
    quantiles = np.percentile(values, DECILE_QUANTILES)
    return {
        key: round(float(value), 4)
        for key, value in zip(DECILE_KEYS, quantiles)
    }


def _component_area_filter(
    wet_raw: np.ndarray,
    distance: np.ndarray,
    area_2d: np.ndarray,
    mean_cell_area: float,
    min_cells: int,
    connectivity_enabled: bool,
    max_channel_distance_m: float,
):
    """Apply the REVIEW-04 component-area filter and return an audit record.

    When connectivity is enabled it is applied first and recorded separately;
    the >=9-cell area filter is always the last wet-mask operation before
    statistics and rendering.  Morphological opening is never used.
    """
    structure = np.ones((3, 3), dtype=np.int8)
    labels_raw, raw_count = label(wet_raw, structure=structure)
    raw_area = float(area_2d[wet_raw].sum())

    if connectivity_enabled and raw_count:
        near = wet_raw & (distance <= max_channel_distance_m)
        has_channel = np.zeros(raw_count + 1, dtype=bool)
        if near.any():
            has_channel[np.unique(labels_raw[near])] = True
        has_channel[0] = False
        wet_connected = has_channel[labels_raw]
    else:
        wet_connected = wet_raw

    labels, before_count = label(wet_connected, structure=structure)
    connected_area = float(area_2d[wet_connected].sum())
    if before_count == 0:
        audit = {
            "method": "component_area_filter",
            "min_cells": int(min_cells),
            "min_area_km2": round(mean_cell_area * min_cells, 6),
            "opening": "none",
            "connectivity": bool(connectivity_enabled),
            "connectivity_max_distance_m": float(max_channel_distance_m) if connectivity_enabled else None,
            "raw_components": int(raw_count),
            "connectivity_components": int(before_count),
            "components_before": int(before_count),
            "components_after": 0,
            "dropped_components": int(before_count),
            "area_before_km2": round(connected_area, 4),
            "dropped_area_km2": round(connected_area, 4),
            "raw_area_km2": round(raw_area, 4),
        }
        return wet_connected.copy(), audit

    sizes = np.bincount(labels.ravel(), minlength=before_count + 1)
    keep = sizes >= min_cells
    keep[0] = False
    wet = keep[labels]
    after_count = int(keep[1:].sum())
    kept_area = float(area_2d[wet].sum())
    audit = {
        "method": "component_area_filter",
        "min_cells": int(min_cells),
        "min_area_km2": round(mean_cell_area * min_cells, 6),
        "opening": "none",
        "connectivity": bool(connectivity_enabled),
        "connectivity_max_distance_m": float(max_channel_distance_m) if connectivity_enabled else None,
        "raw_components": int(raw_count),
        "connectivity_components": int(before_count),
        "components_before": int(before_count),
        "components_after": after_count,
        "dropped_components": int(before_count - after_count),
        "area_before_km2": round(connected_area, 4),
        "dropped_area_km2": round(connected_area - kept_area, 4),
        "raw_area_km2": round(raw_area, 4),
    }
    return wet, audit


def _frame_bbox(transform, crs: str, width: int, height: int) -> list[float]:
    left, top = transform * (0, 0)
    right, bottom = transform * (width, height)
    west, south, east, north = transform_bounds(crs, "EPSG:4326", left, bottom, right, top)
    return [round(west, 6), round(south, 6), round(east, 6), round(north, 6)]


def _write_frame_png(band: np.ndarray, path: Path, scale: int) -> tuple[int, int, int]:
    """Downsample a class raster by ``scale`` and write an optimised P-mode PNG."""
    height = band.shape[0] - band.shape[0] % scale
    width = band.shape[1] - band.shape[1] % scale
    reduced = band[:height, :width][::scale, ::scale]
    image = Image.fromarray(reduced, mode="P")
    palette: list[int] = []
    for _, _, (red, green, blue, _), _, _ in CLASS_PALETTE:
        palette.extend([red, green, blue])
    image.putpalette(palette)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True, transparency=0)
    return int(reduced.shape[1]), int(reduced.shape[0]), int((reduced > 0).sum())


def _district_raster(cfg: Config, transform, height: int, width: int):
    districts_path = cfg.root / "pipeline" / "work" / "districts-base.geojson"
    if not districts_path.exists():
        return None, [], None
    data = load_geojson(districts_path)
    ids: list[str] = []
    shapes_list = []
    for index, district_feature in enumerate(data.get("features", []), start=1):
        ids.append(district_feature["properties"]["district_id"])
        district_geom = project_geom(
            shape(district_feature["geometry"]),
            cfg.aoi.output_crs,
            cfg.aoi.analysis_crs,
        )
        shapes_list.append((district_geom, index))
    if not shapes_list:
        return None, [], None
    from rasterio.features import rasterize

    raster = rasterize(
        shapes_list,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        all_touched=False,
        dtype="int32",
    )
    return raster, ids, districts_path


def run(
    cfg: Config,
    dem_path: Path,
    hand_path: Path,
    distance_path: Path,
    channels_path: Path,
    state_path: Path,
    scenario_path: Path,
    out_frame_index: Path,
    out_summary: Path,
    out_masks_dir: Path,
    out_frames_dir: Path,
) -> dict:
    ensure_dirs()
    stage = StageRecord(
        "09",
        "build-inundation",
        inputs=[
            dem_path,
            hand_path,
            distance_path,
            channels_path,
            state_path,
            scenario_path,
            cfg.root / "pipeline" / "work" / aoi_domain.META_JSON,
            cfg.root / "pipeline" / "work" / aoi_domain.CORE_TIF,
        ],
    )
    scenario = cfg.scenario
    model = scenario.model
    res = float(cfg.aoi.resolution_m)
    nodata = float(cfg.aoi.nodata)
    edges = list(model["depth_bands_m"])
    component_cfg = dict(model.get("component_filter") or {})
    if component_cfg.get("method") != "component_area_filter":
        raise RuntimeError(
            "stage 09: REVIEW-04 C2 requires model.component_filter.method = "
            "'component_area_filter'"
        )
    if not component_cfg.get("applied_before_statistics"):
        raise RuntimeError(
            "stage 09: the component-area filter must be applied before statistics "
            "and rendering (model.component_filter.applied_before_statistics)"
        )
    if component_cfg.get("opening") not in ("none", None, False):
        raise RuntimeError("stage 09: morphological opening is forbidden (REVIEW-04 C2)")
    min_cells = int(component_cfg.get("min_cells", 9))
    if min_cells < 9:
        raise RuntimeError(f"stage 09: component-area filter {min_cells} cells < 9")
    connectivity_cfg = dict(model.get("connectivity") or {})
    connectivity_enabled = bool(connectivity_cfg.get("enabled", False))
    connectivity_distance = float(connectivity_cfg.get("max_channel_distance_m", res))
    scale = int(model.get("frame_resolution_scale", 2))
    if scale != 2:
        raise RuntimeError(f"stage 09: frame resolution scale {scale} != 2 (half resolution)")
    version = cfg.pipeline["dataset_version"]
    frame_cap = int(
        cfg.pipeline["validation"].get("max_frame_png_bytes", 409600)
    )

    aoi = aoi_domain.load_saved(cfg)
    with rasterio.open(hand_path) as src:
        hand = src.read(1)
        transform = src.transform
        width = src.width
        height = src.height
        crs = str(src.crs)
    if hand.shape != aoi.core.shape:
        raise RuntimeError("stage 09: HAND raster shape does not match AOI v2 mask")
    with rasterio.open(distance_path) as src:
        distance = src.read(1)
    with rasterio.open(channels_path) as src:
        channel = src.read(1) > 0
    nearest_path = hand_path.parent / "nearest-channel-elevation-90m.tif"
    if not nearest_path.exists():
        raise RuntimeError(
            f"stage 09: nearest-channel-elevation raster missing at {nearest_path}; "
            "re-run stage 08"
        )
    with rasterio.open(nearest_path) as src:
        nearest_z = src.read(1)
    with rasterio.open(dem_path) as src:
        dem = src.read(1)
    if not (dem.shape == nearest_z.shape == hand.shape):
        raise RuntimeError("stage 09: DEM/nearest-channel/HAND raster shape mismatch")
    stage.inputs.append(nearest_path)
    if not channel.any():
        raise RuntimeError("stage 09: no channel cells")
    if hand.shape != (height, width):
        raise RuntimeError("stage 09: HAND raster shape mismatch")

    domain = aoi.core & (hand != nodata)
    if not domain.any():
        raise RuntimeError("stage 09: AOI v2 has no valid HAND cells")
    core_cells = aoi.core_cells
    core_area = aoi.core_area_km2
    assam_area = aoi.assam_area_km2
    flood_prone_area = float(cfg.aoi.raw["flood_prone_area_km2"])
    valid_cell_share = float(domain.sum()) / core_cells if core_cells else 0.0
    areas = row_cell_areas_km2(transform, height, width, cfg.aoi.analysis_crs)
    area_2d = np.broadcast_to(areas, (height, width))
    mean_cell_area = float(areas.mean())
    # B2/V-A6: a cell is "clamped" when the burned ground lies below its
    # nearest channel elevation, so HAND is reported as 0 and depth = stage.
    clamped_domain = domain & (dem < nearest_z)
    clamped_aoi_cells = int(clamped_domain.sum())
    valid_aoi_cells = int(domain.sum())
    clamped_aoi_share = clamped_aoi_cells / valid_aoi_cells if valid_aoi_cells else 1.0

    district_ids, district_names, districts_path = _district_raster(
        cfg, transform, height, width
    )
    if districts_path is not None:
        stage.inputs.append(districts_path)

    out_masks_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = cfg.root / "pipeline" / "work" / "flood-frames"
    staging_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_masks_dir.glob("step-*-wet.tif"):
        stale.unlink()
    for stale in staging_dir.glob("step-*.*"):
        stale.unlink()
    for stale in out_frames_dir.glob("step-*.*"):
        stale.unlink()

    step_summaries: list[dict] = []
    frame_steps: list[dict] = []
    prev_wet = np.zeros((height, width), dtype=bool)
    district_ever_wet: set[int] = set()
    peak_area = 0.0
    peak_index = 0
    peak_median_depth = None
    peak_max_depth = None
    peak_p95_depth = None
    peak_deciles = None
    peak_wet_cells = None
    peak_clamped_wet_share = None
    peak_clamped_aoi_share = None
    peak_filter_audit: dict = {}
    total_dropped_area = 0.0
    total_frame_bytes = 0
    max_frame_bytes = 0
    frame_bbox: list[float] | None = None
    frame_width = 0
    frame_height = 0

    for index, step in enumerate(scenario.steps):
        stage_m = float(step["stage_m"])
        step_label = str(step["label"])
        phase = str(step["phase"])
        wet_raw = domain & (hand <= stage_m)
        wet, filter_audit = _component_area_filter(
            wet_raw,
            distance,
            area_2d,
            mean_cell_area,
            min_cells,
            connectivity_enabled,
            connectivity_distance,
        )
        depth = np.where(wet, stage_m - hand, np.float32(0.0)).astype(np.float32)

        mask_path = out_masks_dir / f"step-{index:02d}-wet.tif"
        aoi_domain.write_mask(mask_path, wet, transform, str(crs))

        area_km2 = _row_area(areas, wet)
        wet_cells = int(wet.sum())
        new_km2 = _row_area(areas, wet & ~prev_wet)
        receded_km2 = _row_area(areas, ~wet & prev_wet)
        if wet.any():
            values = depth[wet]
            max_depth = float(values.max())
            median_depth = float(np.median(values))
            p95_depth = float(np.percentile(values, 95))
            deciles = _depth_deciles(values)
            mean_depth = _row_area(areas, depth * wet) / area_km2 if area_km2 > 0 else None
            clamped_wet_km2 = _row_area(areas, wet & clamped_domain)
            clamped_wet_share = clamped_wet_km2 / area_km2 if area_km2 > 0 else None
        else:
            max_depth = None
            mean_depth = None
            median_depth = None
            p95_depth = None
            deciles = None
            clamped_wet_share = None

        affected = 0
        if district_ids is not None and wet.any():
            wet_ids = district_ids[wet]
            wet_weights = area_2d[wet]
            district_area = np.bincount(
                wet_ids, weights=wet_weights, minlength=len(district_names) + 1
            )
            district_area[0] = 0.0
            affected_ids = np.flatnonzero(district_area > 1.0)
            affected = int(len(affected_ids))
            district_ever_wet.update(int(v) for v in affected_ids)

        # Rasterise only the wet bounding window into a full-size class grid so
        # the committed PNG keeps the analysis extent.
        band = np.zeros((height, width), dtype=np.uint8)
        if wet.any():
            rows = np.flatnonzero(wet.any(axis=1))
            cols = np.flatnonzero(wet.any(axis=0))
            r0, r1 = int(rows[0]), int(rows[-1]) + 1
            c0, c1 = int(cols[0]), int(cols[-1]) + 1
            band[r0:r1, c0:c1] = _band_index(depth[r0:r1, c0:c1], edges)

        frame_path = staging_dir / f"step-{index:02d}.png"
        frame_width, frame_height, png_wet_cells = _write_frame_png(band, frame_path, scale)
        frame_bytes = frame_path.stat().st_size
        png_area_km2 = png_wet_cells * (scale * scale) * mean_cell_area
        if frame_bbox is None:
            frame_bbox = _frame_bbox(
                transform,
                crs,
                (width // scale) * scale,
                (height // scale) * scale,
            )

        summary_step = {
            "step": index,
            "step_label": step_label,
            "day_offset": int(step["day_offset"]),
            "phase": phase,
            "rainfall_mm_day": int(step["rainfall_mm_day"]),
            "mainstem_stage_m": float(step["mainstem_stage_m"]),
            "backwater_m": float(step["backwater_m"]),
            "stage_m": stage_m,
            "above_threshold": bool(stage_m >= scenario.threshold_m),
            "inundated_area_km2": round(area_km2, 4),
            "wet_cells": wet_cells,
            "new_inundation_km2": round(new_km2, 4),
            "receded_area_km2": round(receded_km2, 4),
            "median_depth_m": round(median_depth, 4) if median_depth is not None else None,
            "p95_depth_m": round(p95_depth, 4) if p95_depth is not None else None,
            "delay_deciles": deciles,
            "max_depth_m": round(max_depth, 4) if max_depth is not None else None,
            "mean_depth_m": round(mean_depth, 4) if mean_depth is not None else None,
            "clamped_wet_share": (
                round(clamped_wet_share, 6) if clamped_wet_share is not None else None
            ),
            "clamped_aoi_share": round(clamped_aoi_share, 6),
            "component_filter": filter_audit,
            "frame_file": f"frames/step-{index:02d}.png",
            "frame_png_bytes": int(frame_bytes),
            "frame_width": int(frame_width),
            "frame_height": int(frame_height),
            "png_wet_cells": int(png_wet_cells),
            "png_area_km2": round(png_area_km2, 4),
            "affected_district_count": affected,
            "valid_cell_share": round(valid_cell_share, 6),
            "share_of_aoi_v2": round(area_km2 / core_area, 6) if core_area else None,
            "share_of_assam": round(area_km2 / assam_area, 6) if assam_area else None,
            "share_of_flood_prone_area": (
                round(area_km2 / flood_prone_area, 6) if flood_prone_area else None
            ),
        }
        step_summaries.append(summary_step)
        frame_steps.append(
            {
                "id": index,
                "label": step_label,
                "stage_m": stage_m,
                "file": f"frames/step-{index:02d}.png",
                "area_km2": round(area_km2, 4),
                "png_bytes": int(frame_bytes),
                "png_wet_cells": int(png_wet_cells),
                "png_area_km2": round(png_area_km2, 4),
            }
        )
        total_dropped_area += float(filter_audit["dropped_area_km2"])
        total_frame_bytes += int(frame_bytes)
        max_frame_bytes = max(max_frame_bytes, int(frame_bytes))
        if frame_bytes > frame_cap:
            raise RuntimeError(
                f"stage 09: step {index} PNG {frame_bytes} bytes exceeds V09 cap {frame_cap}"
            )
        if area_km2 > peak_area:
            peak_area = area_km2
            peak_index = index
            peak_median_depth = median_depth
            peak_max_depth = max_depth
            peak_p95_depth = p95_depth
            peak_deciles = deciles
            peak_wet_cells = wet_cells
            peak_clamped_wet_share = clamped_wet_share
            peak_clamped_aoi_share = clamped_aoi_share
            peak_filter_audit = dict(filter_audit)
        prev_wet = wet

        print(
            f"[09] S{index:02d} {step_label} {phase:8s} stage {stage_m:.2f} m: "
            f"{area_km2:,.0f} km² ({area_km2 / core_area:.1%} of AOI v2, "
            f"{area_km2 / assam_area:.1%} of Assam, "
            f"{area_km2 / flood_prone_area:.1%} of flood-prone), "
            f"median {median_depth if median_depth is None else round(median_depth, 2)}, "
            f"p95 {p95_depth if p95_depth is None else round(p95_depth, 2)}, "
            f"clamped {clamped_wet_share if clamped_wet_share is None else round(clamped_wet_share, 3)}, "
            f"wet {wet_cells:,} cells, "
            f"components {filter_audit['components_before']}->{filter_audit['components_after']}, "
            f"dropped {filter_audit['dropped_area_km2']:.1f} km², "
            f"PNG {frame_width}x{frame_height} {frame_bytes / 1024:.1f} KB"
        )

    # REVIEW-05 D2: print the same per-step decile table that flood-summary.json
    # publishes, so a reviewer can see the distribution shape without trusting a
    # single median.  No downstream consumer may average these columns.
    print("[09] depth deciles over wet cells (m):")
    print("[09] step  wet_cells    p10    p25    p50    p75    p90    p95")
    for step_summary in step_summaries:
        step_deciles = step_summary["delay_deciles"] or {}
        print(
            f"[09] S{step_summary['step']:02d} {step_summary['wet_cells']:>10,}  "
            + "  ".join(
                f"{step_deciles.get(key, float('nan')):5.2f}" for key in DECILE_KEYS
            )
        )

    # Hydrograph shape — exact, not a widened tolerance.
    tolerance_area = float(cfg.pipeline["inundation"]["monotonic_tolerance"])
    rising = [s["inundated_area_km2"] for s in step_summaries[: scenario.peak_step + 1]]
    recession = [s["inundated_area_km2"] for s in step_summaries[scenario.peak_step :]]
    for i in range(len(rising) - 1):
        if rising[i + 1] < rising[i] * (1.0 - tolerance_area):
            raise RuntimeError(
                f"stage 09: rising-limb area decreased at step {i}->{i + 1}: "
                f"{rising[i]:.3f} -> {rising[i + 1]:.3f} km²"
            )
    for i in range(len(recession) - 1):
        if recession[i + 1] > recession[i] * (1.0 + tolerance_area):
            raise RuntimeError(
                f"stage 09: recession area increased at peak-relative step {i}->{i + 1}: "
                f"{recession[i]:.3f} -> {recession[i + 1]:.3f} km²"
            )
    if peak_index != scenario.peak_step:
        raise RuntimeError(
            f"stage 09: peak area at step {peak_index}, expected scenario peak_step "
            f"{scenario.peak_step}"
        )
    if peak_area <= 0:
        raise RuntimeError("stage 09: peak inundation area is zero")

    inundation_cfg = cfg.pipeline["inundation"]
    peak_min = float(inundation_cfg["peak_extent_min_km2"])
    peak_max = float(inundation_cfg["peak_extent_max_km2"])
    max_flood_prone_share = float(inundation_cfg["max_peak_area_share_of_flood_prone"])
    if not (peak_min <= peak_area <= peak_max):
        raise RuntimeError(
            f"stage 09: peak extent {peak_area:,.0f} km² is outside the V-A4 "
            f"plausibility band {peak_min:,.0f}–{peak_max:,.0f} km²"
        )
    flood_prone_share = peak_area / flood_prone_area
    if flood_prone_share > max_flood_prone_share:
        raise RuntimeError(
            f"stage 09: peak extent {peak_area:,.0f} km² is {flood_prone_share:.1%} of "
            f"the {flood_prone_area:,.0f} km² flood-prone area, above "
            f"{max_flood_prone_share:.0%}"
        )

    # V-A5 v4 (REVIEW-05 D1) / V-A6 — measured on the same area-filtered wet
    # masks that are written.  The shape gate replaces the withdrawn absolute
    # 1.0–2.2 m band; every rule is binding and none is widened here.
    peak_step_summary = step_summaries[scenario.peak_step]
    peak_stage_m = float(peak_step_summary["stage_m"])
    v_a5_failures: list[str] = []
    median_min = float(inundation_cfg["peak_median_depth_min_m"])
    median_offset = float(inundation_cfg["peak_median_depth_offset_below_stage_m"])
    spread_min = float(inundation_cfg["peak_depth_spread_min_m"])
    clamped_wet_max = float(inundation_cfg["peak_clamped_wet_share_max"])
    median_max = peak_stage_m - median_offset
    if float(peak_median_depth) < median_min - 1e-9:
        v_a5_failures.append(
            f"median {float(peak_median_depth):.3f} m < {median_min:.2f} m"
        )
    if float(peak_median_depth) > median_max + 1e-9:
        v_a5_failures.append(
            f"median {float(peak_median_depth):.3f} m > peak stage {peak_stage_m:.2f} m "
            f"− {median_offset:.2f} m = {median_max:.2f} m"
        )
    if float(peak_p95_depth) > peak_stage_m + 1e-6:
        v_a5_failures.append(f"p95 {float(peak_p95_depth):.3f} m > peak stage {peak_stage_m:.2f} m")
    spread = float(peak_p95_depth) - float(peak_median_depth)
    if spread < spread_min - 1e-9:
        v_a5_failures.append(
            f"p95 − median {spread:.3f} m < {spread_min:.2f} m"
        )
    if float(peak_clamped_wet_share) > clamped_wet_max + 1e-9:
        v_a5_failures.append(
            f"clamped wet share {float(peak_clamped_wet_share):.1%} > {clamped_wet_max:.0%}"
        )
    max_clamped_aoi = float(cfg.pipeline["validation"]["max_clamped_negative_share"])
    if clamped_aoi_share > max_clamped_aoi + 1e-9:
        v_a5_failures.append(
            f"clamped AOI share {clamped_aoi_share:.2%} > {max_clamped_aoi:.1%} (V-A6)"
        )

    attempt = {
        "schema_version": "1.0.0",
        "status": "blocked" if v_a5_failures else "ok",
        "peak_step": peak_index,
        "steps": step_summaries,
        "component_filter_audit": {
            "method": "component_area_filter",
            "min_cells": min_cells,
            "opening": "none",
            "connectivity": bool(connectivity_enabled),
            "connectivity_max_distance_m": connectivity_distance if connectivity_enabled else None,
            "peak_components_before": peak_filter_audit.get("components_before"),
            "peak_components_after": peak_filter_audit.get("components_after"),
            "peak_dropped_components": peak_filter_audit.get("dropped_components"),
            "peak_dropped_area_km2": peak_filter_audit.get("dropped_area_km2"),
            "total_dropped_area_km2": round(total_dropped_area, 4),
        },
        "frame_audit": {
            "frame_count": len(frame_steps),
            "frame_width": frame_width,
            "frame_height": frame_height,
            "frame_scale": scale,
            "total_png_bytes": int(total_frame_bytes),
            "max_png_bytes": int(max_frame_bytes),
            "bbox": frame_bbox,
        },
        "totals": {
            "max_area_km2": round(peak_area, 4),
            "peak_stage_m": peak_stage_m,
            "wet_cells_at_peak": peak_wet_cells,
            "median_depth_at_peak_m": (
                round(peak_median_depth, 4) if peak_median_depth is not None else None
            ),
            "p95_depth_at_peak_m": (
                round(peak_p95_depth, 4) if peak_p95_depth is not None else None
            ),
            "delay_deciles_at_peak": peak_deciles,
            "v_a5_version": str(inundation_cfg.get("v_a5_version", "v4-shape")),
            "v_a5_rules": {
                "median_min_m": median_min,
                "median_max_m": round(median_max, 4),
                "median_max_rule": (
                    f"peak stage {peak_stage_m:.2f} m − "
                    f"{median_offset:.2f} m"
                ),
                "p95_max_m": peak_stage_m,
                "p95_minus_median_min_m": spread_min,
                "p95_minus_median_m": round(spread, 4),
                "clamped_wet_share_max": clamped_wet_max,
            },
            "clamped_wet_share_at_peak": (
                round(peak_clamped_wet_share, 6)
                if peak_clamped_wet_share is not None
                else None
            ),
            "clamped_aoi_share": round(clamped_aoi_share, 6),
            "v_a5_failures": v_a5_failures,
        },
    }
    atomic_write_json(
        cfg.root / "pipeline" / "work" / "stage09-attempt.json", attempt, indent=2
    )
    if v_a5_failures:
        raise RuntimeError(
            "stage 09: V-A5/V-A6 failed on the measured peak: " + "; ".join(v_a5_failures)
        )

    classes = [
        {
            "id": int(class_id),
            "label": label,
            "color": f"#{red:02x}{green:02x}{blue:02x}",
            "alpha": int(alpha),
            "min_m": low,
            "max_m": high,
        }
        for class_id, label, (red, green, blue, alpha), low, high in CLASS_PALETTE
    ]
    frame_index = {
        "schema_version": "1.0.0",
        "dataset_version": version,
        "scenario_id": scenario.scenario_id,
        "class": "scenario",
        "bbox": frame_bbox,
        "width": int(frame_width),
        "height": int(frame_height),
        "crs": "EPSG:4326",
        "source_crs": "EPSG:32646",
        "source_resolution_m": res,
        "frame_resolution_m": res * scale,
        "frame_scale": scale,
        "classes": classes,
        "steps": frame_steps,
    }
    summary = {
        "schema_version": "1.0.0",
        "scenario_id": scenario.scenario_id,
        "class": "scenario",
        "peak_step": scenario.peak_step,
        "series_class": {
            "rainfall": "synthetic",
            "mainstem_stage": "synthetic",
            "backwater": "synthetic",
            "inundated_area": "scenario",
        },
        "steps": step_summaries,
        "component_filter_audit": attempt["component_filter_audit"],
        "frame_contract": {
            "format": "png",
            "scale": scale,
            "frame_width": int(frame_width),
            "frame_height": int(frame_height),
            "frame_resolution_m": res * scale,
            "bbox": frame_bbox,
            "frame_count": len(frame_steps),
            "total_png_bytes": int(total_frame_bytes),
            "max_png_bytes": int(max_frame_bytes),
            "index": "frame-index.json",
        },
        "totals": {
            "max_area_km2": round(peak_area, 4),
            "peak_stage_m": max(float(s["stage_m"]) for s in step_summaries),
            "scenario_days": int(scenario.raw["total_days"]),
            "districts_any_inundation": len(district_ever_wet),
            "wet_cells_at_peak": peak_wet_cells,
            "median_depth_at_peak_m": (
                round(peak_median_depth, 4) if peak_median_depth is not None else None
            ),
            "p95_depth_at_peak_m": (
                round(peak_p95_depth, 4) if peak_p95_depth is not None else None
            ),
            "delay_deciles_at_peak": peak_deciles,
            "v_a5_version": attempt["totals"]["v_a5_version"],
            "v_a5_rules": attempt["totals"]["v_a5_rules"],
            "clamped_wet_share_at_peak": (
                round(peak_clamped_wet_share, 6)
                if peak_clamped_wet_share is not None
                else None
            ),
            "clamped_aoi_share": round(clamped_aoi_share, 6),
            "max_depth_at_peak_m": (
                round(peak_max_depth, 4) if peak_max_depth is not None else None
            ),
            "aoi_v2_area_km2": round(core_area, 4),
            "assam_area_km2": round(assam_area, 4),
            "flood_prone_area_km2": flood_prone_area,
            "peak_extent_share_of_aoi_v2": round(peak_area / core_area, 6),
            "peak_extent_share_of_assam": round(peak_area / assam_area, 6),
            "peak_extent_share_of_flood_prone_area": round(flood_prone_share, 6),
            "plausibility_band": {
                "min_km2": peak_min,
                "max_km2": peak_max,
                "max_share_of_flood_prone_area": max_flood_prone_share,
                "note": (
                    "V-A4 band chosen by the reviewer from REVIEW-02; it is not a "
                    "calibrated observation and not an event forecast."
                ),
            },
        },
    }

    # Publish only after every stage-09 gate has passed.
    out_frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_frames_dir.glob("step-*.*"):
        stale.unlink()
    for index in range(scenario.step_count):
        source = staging_dir / f"step-{index:02d}.png"
        atomic_write_bytes(out_frames_dir / source.name, source.read_bytes())
    out_frame_index.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_frame_index, frame_index, indent=2, sort_keys=False)
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_summary, summary, indent=2, sort_keys=False)

    public_scenario_path = cfg.root / "public" / "data" / "scenario.json"
    atomic_write_json(public_scenario_path, scenario.raw, indent=2, sort_keys=False)

    mask_bytes = path_size(out_masks_dir)
    stage.out(out_frame_index, out_frames_dir, out_summary, out_masks_dir, public_scenario_path)
    stage.metric("frame_count", len(frame_steps))
    stage.metric("frame_width", frame_width)
    stage.metric("frame_height", frame_height)
    stage.metric("frame_total_png_bytes", total_frame_bytes)
    stage.metric("frame_max_png_bytes", max_frame_bytes)
    stage.metric("mask_cache_bytes", mask_bytes)
    stage.metric("peak_p95_depth_m", round(peak_p95_depth, 4))
    stage.metric("peak_clamped_wet_share", round(peak_clamped_wet_share, 6))
    stage.metric("clamped_aoi_share", round(clamped_aoi_share, 6))
    stage.metric("component_filter_min_cells", min_cells)
    stage.metric("component_filter_opening", "none")
    stage.metric("peak_components_before", peak_filter_audit.get("components_before"))
    stage.metric("peak_components_after", peak_filter_audit.get("components_after"))
    stage.metric("peak_dropped_area_km2", peak_filter_audit.get("dropped_area_km2"))
    stage.metric("peak_area_km2", round(peak_area, 4))
    stage.metric("aoi_v2_area_km2", round(core_area, 4))
    stage.metric("assam_area_km2", round(assam_area, 4))
    stage.metric("flood_prone_area_km2", flood_prone_area)
    stage.metric("peak_area_share_of_aoi_v2", round(peak_area / core_area, 6))
    stage.metric("peak_area_share_of_assam", round(peak_area / assam_area, 6))
    stage.metric("peak_area_share_of_flood_prone_area", round(flood_prone_share, 6))
    stage.metric("valid_cell_share_aoi_v2", round(valid_cell_share, 6))
    stage.metric("median_depth_at_peak_m", summary["totals"]["median_depth_at_peak_m"])
    stage.metric("max_depth_at_peak_m", summary["totals"]["max_depth_at_peak_m"])
    stage.metric("wet_cells_at_peak", peak_wet_cells)
    stage.metric("v_a5_version", attempt["totals"]["v_a5_version"])
    stage.metric("v_a5_p95_minus_median_m", attempt["totals"]["v_a5_rules"]["p95_minus_median_m"])
    stage.finish(
        f"REVIEW-05 D1/D2: V-A5 v4 shape gate on the area-filtered mask (median >= "
        f"{median_min:.2f} m and <= peak stage - {median_offset:.2f} m; p95 <= peak "
        f"stage; p95 - median >= {spread_min:.2f} m; clamped wet <= "
        f"{clamped_wet_max:.0%}); REVIEW-04 C1/C2 component-area filter >= {min_cells} "
        f"cells (no opening, no morphological operation); per-step wet_cells and "
        f"delay_deciles published; half-resolution {frame_width}x{frame_height} 5-class "
        f"PNGs plus frame-index.json; no per-band GeoJSON and no polygonisation. AOI v2 "
        f"core {core_area:,.1f} km²; per-step uint8 wet masks in {out_masks_dir.name}/; "
        "no inundation-stack.npz."
    )
    print(
        f"[09] ok: peak {peak_area:,.0f} km² at S{peak_index:02d} "
        f"({peak_area / core_area:.1%} of AOI v2, "
        f"{peak_area / flood_prone_area:.1%} of flood-prone), median "
        f"{peak_median_depth:.3f} m, p95 {peak_p95_depth:.3f} m, clamp "
        f"{peak_clamped_wet_share:.1%}; components "
        f"{peak_filter_audit['components_before']}->{peak_filter_audit['components_after']}, "
        f"dropped {peak_filter_audit['dropped_area_km2']:.1f} km²; frames "
        f"{total_frame_bytes / 1024 / 1024:.2f} MB (max {max_frame_bytes / 1024:.1f} KB)"
    )
    return summary
