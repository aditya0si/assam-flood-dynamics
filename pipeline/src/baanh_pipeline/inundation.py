"""Stage 09 — AOI-v2 HAND inundation, written one step at a time.

REVIEW-02 A5: build a per-step uint8 wet mask, never a float stack of all
steps; threshold inside AOI v2 (inside Assam, DEM <= 120 m) before any
polygonisation; write one GeoJSON per step and combine those into
``flood-frames.geojson``; do not write ``inundation-stack.npz``.  Stage 10
and stage 12 read the per-step masks instead.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes as raster_shapes
from rasterio.transform import Affine
from scipy.ndimage import binary_opening, label
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import unary_union

from . import aoi_domain
from .config import Config
from .geo import (
    feature,
    feature_collection,
    geodesic_area_km2,
    load_geojson,
    polygon_parts,
    project_geom,
    row_cell_areas_km2,
    valid,
)
from .util import (
    StageRecord,
    atomic_write_bytes,
    atomic_write_json,
    ensure_dirs,
    gzip_bytes,
    json_bytes,
    path_size,
)


BAND_LABELS = [
    ("0.0-0.5", 0.0, 0.5),
    ("0.5-1.5", 0.5, 1.5),
    ("1.5-3.0", 1.5, 3.0),
    ("3.0+", 3.0, None),
]


def _band_index(depth: np.ndarray, edges: list[float | None]) -> np.ndarray:
    low = np.asarray(edges[:-1], dtype=np.float32)
    band = np.digitize(depth, low, right=True).astype(np.uint8)
    band[depth <= 0] = 0
    return band


def _row_area(areas: np.ndarray, mask: np.ndarray) -> float:
    return float(areas[:, 0].dot(mask.sum(axis=1)))


def _component_filter(wet_raw: np.ndarray, distance: np.ndarray, min_cells: int, res: float):
    labels, count = label(wet_raw, structure=np.ones((3, 3), dtype=np.int8))
    if count == 0:
        return wet_raw.copy(), 0, 0
    near = wet_raw & (distance <= res)
    component_has_channel = np.zeros(count + 1, dtype=bool)
    if near.any():
        component_has_channel[np.unique(labels[near])] = True
    sizes = np.bincount(labels.ravel(), minlength=count + 1)
    keep = component_has_channel & (sizes >= min_cells)
    keep[0] = False
    wet = keep[labels]
    dropped = int((~keep[1:]).sum())
    return wet, int(count), dropped


def _speckle_control(
    wet: np.ndarray,
    distance: np.ndarray,
    area_2d: np.ndarray,
    res: float,
    opening_cells: int,
    min_part_area_km2: float,
):
    """V-A9: 3x3 opening, then drop wet parts below the area floor.

    ``parts_before`` and ``parts_after`` are connected-component counts of the
    connectivity-filtered wet mask and of the retained mask, both recorded in
    ``flood-summary.json``.  Applied before polygonisation, never after it.
    """
    structure = np.ones((opening_cells, opening_cells), dtype=bool)
    opened = binary_opening(wet, structure=structure, border_value=0)
    _, parts_before = label(wet, structure=np.ones((3, 3), dtype=np.int8))
    labels, count = label(opened, structure=np.ones((3, 3), dtype=np.int8))
    if count == 0:
        return opened, int(parts_before), 0, 0, 0.0
    part_area = np.bincount(labels.ravel(), weights=area_2d.ravel(), minlength=count + 1)
    # V-A9 drops parts by area only.  Connectivity was already enforced on the
    # pre-opening mask; re-testing channel proximity here would delete large
    # components merely because the opening moved their edge cells.
    keep = part_area >= min_part_area_km2
    keep[0] = False
    kept = keep[labels]
    removed_area = float(area_2d[opened].sum() - area_2d[kept].sum())
    dropped = int((~keep[1:]).sum())
    return kept, int(parts_before), int(keep[1:].sum()), dropped, removed_area


def _polygonise_band(
    band: np.ndarray,
    value: int,
    step_transform: Affine,
    cfg: Config,
    tolerance_m: float,
    min_area_km2: float,
):
    mask = band == value
    if not mask.any():
        return None, 0.0, 0
    parts = []
    for geom_mapping, _ in raster_shapes(
        band, mask=mask, connectivity=8, transform=step_transform
    ):
        geom = shape(geom_mapping)
        if geom.is_empty:
            continue
        parts.extend(polygon_parts(geom))
    if not parts:
        return None, 0.0, 0
    # The connected components of one band are disjoint.  Build a MultiPolygon
    # directly instead of unioning thousands of parts per step.
    multi = MultiPolygon(parts)
    if not multi.is_valid:
        multi = valid(unary_union(parts))
    if multi is None or multi.is_empty:
        return None, 0.0, 0
    wgs = project_geom(multi, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
    wgs = valid(wgs)
    if wgs is None or wgs.is_empty:
        return None, 0.0, 0
    # Simplifying one MultiPolygon with tens of thousands of parts is very
    # expensive.  Simplify each disjoint part in WGS84 with an equivalent
    # ground tolerance (~75 m in latitude).
    tolerance_deg = tolerance_m / 111320.0
    kept = []
    for part in polygon_parts(wgs):
        if geodesic_area_km2(part) < min_area_km2:
            continue
        simplified_part = part.simplify(tolerance_deg, preserve_topology=True)
        simplified_part = valid(simplified_part)
        if simplified_part is None or simplified_part.is_empty:
            continue
        for clean_part in polygon_parts(simplified_part):
            if geodesic_area_km2(clean_part) < min_area_km2:
                continue
            if clean_part.interiors:
                holes = [
                    interior
                    for interior in clean_part.interiors
                    if geodesic_area_km2(Polygon(interior)) >= min_area_km2
                ]
                clean_part = Polygon(clean_part.exterior, holes)
            kept.append(clean_part)
    if not kept:
        return None, 0.0, 0
    result = MultiPolygon(kept)
    if not result.is_valid:
        result = valid(unary_union(kept))
    if result is None or result.is_empty:
        return None, 0.0, 0
    parts = polygon_parts(result)
    area = sum(geodesic_area_km2(part) for part in parts)
    if area <= 0:
        return None, 0.0, 0
    return result, area, len(parts)


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
            shape(district_feature["geometry"]), cfg.aoi.output_crs, cfg.aoi.analysis_crs
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
    out_frames: Path,
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
    min_component_cells = int(model.get("min_component_cells", 3))
    tolerance = float(model["simplify_tolerance_m"])
    min_band_area = float(model["min_polygon_area_km2"])
    speckle = dict(model.get("speckle_control") or {})
    if not speckle.get("applied_before_polygonisation"):
        raise RuntimeError(
            "stage 09: V-A9 requires the documented speckle control before "
            "polygonisation (model.speckle_control)"
        )
    opening_cells = int(speckle.get("opening_cells", 3))
    min_part_area = float(speckle.get("min_part_area_km2", 0.10))
    version = cfg.pipeline["dataset_version"]

    aoi = aoi_domain.load_saved(cfg)
    with rasterio.open(hand_path) as src:
        hand = src.read(1)
        transform = src.transform
        width = src.width
        height = src.height
        crs = src.crs
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
    out_frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_masks_dir.glob("step-*-wet.tif"):
        stale.unlink()
    for stale in out_frames_dir.glob("step-*.geojson"):
        stale.unlink()

    step_summaries: list[dict] = []
    prev_wet = np.zeros((height, width), dtype=bool)
    district_ever_wet: set[int] = set()
    peak_area = 0.0
    peak_index = 0
    peak_median_depth = None
    peak_max_depth = None
    peak_p95_depth = None
    peak_clamped_wet_share = None
    peak_clamped_aoi_share = None
    total_features = 0

    for index, step in enumerate(scenario.steps):
        stage_m = float(step["stage_m"])
        step_label = str(step["label"])
        phase = str(step["phase"])
        wet_raw = domain & (hand <= stage_m)
        wet_connected, component_count, dropped = _component_filter(
            wet_raw, distance, min_component_cells, res
        )
        wet, parts_before, parts_after, speckle_dropped, speckle_removed = _speckle_control(
            wet_connected,
            distance,
            area_2d,
            res,
            opening_cells,
            min_part_area,
        )
        depth = np.where(wet, stage_m - hand, np.float32(0.0)).astype(np.float32)

        mask_path = out_masks_dir / f"step-{index:02d}-wet.tif"
        aoi_domain.write_mask(mask_path, wet, transform, str(crs))

        area_km2 = _row_area(areas, wet)
        new_km2 = _row_area(areas, wet & ~prev_wet)
        receded_km2 = _row_area(areas, ~wet & prev_wet)
        if wet.any():
            values = depth[wet]
            max_depth = float(values.max())
            median_depth = float(np.median(values))
            p95_depth = float(np.percentile(values, 95))
            mean_depth = _row_area(areas, depth * wet) / area_km2 if area_km2 > 0 else None
            clamped_wet_km2 = _row_area(areas, wet & clamped_domain)
            clamped_wet_share = clamped_wet_km2 / area_km2 if area_km2 > 0 else None
        else:
            max_depth = None
            mean_depth = None
            median_depth = None
            p95_depth = None
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
            "new_inundation_km2": round(new_km2, 4),
            "receded_area_km2": round(receded_km2, 4),
            "median_depth_m": round(median_depth, 4) if median_depth is not None else None,
            "p95_depth_m": round(p95_depth, 4) if p95_depth is not None else None,
            "max_depth_m": round(max_depth, 4) if max_depth is not None else None,
            "mean_depth_m": round(mean_depth, 4) if mean_depth is not None else None,
            "clamped_wet_share": (
                round(clamped_wet_share, 6) if clamped_wet_share is not None else None
            ),
            "clamped_aoi_share": round(clamped_aoi_share, 6),
            "speckle_control": {
                "opening": f"{opening_cells}x{opening_cells}",
                "min_part_area_km2": min_part_area,
                "parts_before": parts_before,
                "parts_after": parts_after,
                "dropped_parts": speckle_dropped,
                "removed_area_km2": round(speckle_removed, 4),
            },
            "affected_district_count": affected,
            "valid_cell_share": round(valid_cell_share, 6),
            "share_of_aoi_v2": round(area_km2 / core_area, 6) if core_area else None,
            "share_of_assam": round(area_km2 / assam_area, 6) if assam_area else None,
            "share_of_flood_prone_area": (
                round(area_km2 / flood_prone_area, 6) if flood_prone_area else None
            ),
        }
        step_summaries.append(summary_step)
        if area_km2 > peak_area:
            peak_area = area_km2
            peak_index = index
            peak_median_depth = median_depth
            peak_max_depth = max_depth
            peak_p95_depth = p95_depth
            peak_clamped_wet_share = clamped_wet_share
            peak_clamped_aoi_share = clamped_aoi_share
        prev_wet = wet

        # Polygonise only the wet bounding window; every cell is already inside
        # AOI v2, so no full-state grid is ever polygonised.
        step_features: list[dict] = []
        if wet.any():
            rows = np.flatnonzero(wet.any(axis=1))
            cols = np.flatnonzero(wet.any(axis=0))
            r0, r1 = int(rows[0]), int(rows[-1]) + 1
            c0, c1 = int(cols[0]), int(cols[-1]) + 1
            depth_window = depth[r0:r1, c0:c1]
            band = _band_index(depth_window, edges)
            window_transform = transform * Affine.translation(c0, r0)
            frame_parts = 0
            for band_value in range(1, 5):
                band_label, lo, hi = BAND_LABELS[band_value - 1]
                geom_wgs, band_area, band_parts = _polygonise_band(
                    band, band_value, window_transform, cfg, tolerance, min_band_area
                )
                if geom_wgs is None:
                    continue
                frame_parts += band_parts
                props = {
                    "step": index,
                    "step_label": step_label,
                    "phase": phase,
                    "depth_band": band_label,
                    "depth_m_lo": lo,
                    "depth_m_hi": hi,
                    "band_area_km2": round(band_area, 4),
                    "step_area_km2": round(area_km2, 4),
                    "class": "scenario",
                    "model_version": scenario.model_version,
                    "label": f"Scenario inundation · {step_label} · {band_label} m",
                }
                feat = feature(geom_wgs, props, cfg.aoi.decimals)
                if feat is not None:
                    step_features.append(feat)
        step_features.sort(
            key=lambda f: (
                BAND_LABELS.index(
                    next(b for b in BAND_LABELS if b[0] == f["properties"]["depth_band"])
                ),
                -f["properties"]["band_area_km2"],
                json_bytes(f["geometry"]).decode("utf-8")[:120],
            )
        )
        if not step_features:
            raise RuntimeError(
                f"stage 09: step {index} has no flood feature after AOI v2 clipping"
            )
        step_payload = feature_collection(
            f"Scenario inundation depth bands · step {index:02d}",
            "scenario",
            step_features,
            version,
        )
        step_payload_bytes = json_bytes(step_payload, indent=None)
        summary_step["frame_polygon_parts"] = frame_parts
        summary_step["frame_raw_bytes"] = len(step_payload_bytes)
        summary_step["frame_gzip_bytes"] = gzip_bytes(step_payload_bytes)
        atomic_write_json(out_frames_dir / f"step-{index:02d}.geojson", step_payload, indent=None)
        total_features += len(step_features)

        print(
            f"[09] S{index:02d} {step_label} {phase:8s} stage {stage_m:.2f} m: "
            f"{area_km2:,.0f} km² ({area_km2 / core_area:.1%} of AOI v2, "
            f"{area_km2 / assam_area:.1%} of Assam, "
            f"{area_km2 / flood_prone_area:.1%} of flood-prone), "
            f"median {median_depth if median_depth is None else round(median_depth, 2)}, "
            f"p95 {p95_depth if p95_depth is None else round(p95_depth, 2)}, "
            f"clamped {clamped_wet_share if clamped_wet_share is None else round(clamped_wet_share, 1)}, "
            f"max {max_depth if max_depth is None else round(max_depth, 2)}, "
            f"parts {parts_before}->{parts_after}/{frame_parts}, "
            f"frame {len(step_payload_bytes) / 1024 / 1024:.2f} MB raw / "
            f"{summary_step['frame_gzip_bytes'] / 1024 / 1024:.2f} MB gzip"
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

    # V-A5 / V-A6 — measured on the same wet masks that are written out.
    peak_step_summary = step_summaries[scenario.peak_step]
    peak_stage_m = float(peak_step_summary["stage_m"])
    v_a5_failures: list[str] = []
    median_min = float(inundation_cfg["peak_median_depth_min_m"])
    median_max = float(inundation_cfg["peak_median_depth_max_m"])
    clamped_wet_max = float(inundation_cfg["peak_clamped_wet_share_max"])
    if not (median_min <= float(peak_median_depth) <= median_max):
        v_a5_failures.append(
            f"median {float(peak_median_depth):.3f} m outside {median_min:.2f}–{median_max:.2f} m"
        )
    if float(peak_p95_depth) > peak_stage_m + 1e-6:
        v_a5_failures.append(f"p95 {float(peak_p95_depth):.3f} m > peak stage {peak_stage_m:.2f} m")
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
        "totals": {
            "max_area_km2": round(peak_area, 4),
            "peak_stage_m": peak_stage_m,
            "median_depth_at_peak_m": (
                round(peak_median_depth, 4) if peak_median_depth is not None else None
            ),
            "p95_depth_at_peak_m": (
                round(peak_p95_depth, 4) if peak_p95_depth is not None else None
            ),
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

    # Combine the per-step files (A5.3).  The staging directory is removed after
    # the combined file is written; the committed load contract stays one file.
    frame_features: list[dict] = []
    for index in range(scenario.step_count):
        step_path = out_frames_dir / f"step-{index:02d}.geojson"
        if not step_path.exists():
            raise RuntimeError(f"stage 09: missing incremental frame {step_path.name}")
        frame_features.extend(load_geojson(step_path)["features"])
    frame_features.sort(
        key=lambda f: (
            f["properties"]["step"],
            BAND_LABELS.index(
                next(b for b in BAND_LABELS if b[0] == f["properties"]["depth_band"])
            ),
            -f["properties"]["band_area_km2"],
            json_bytes(f["geometry"]).decode("utf-8")[:120],
        )
    )
    frames = feature_collection(
        "Scenario inundation depth bands", "scenario", frame_features, version
    )
    out_frames.parent.mkdir(parents=True, exist_ok=True)
    frames_payload = json_bytes(frames, indent=None)
    frame_cap = int(
        cfg.pipeline["validation"]["file_caps_bytes"]["data/flood/flood-frames.geojson"]
    )
    if len(frames_payload) > frame_cap:
        raise RuntimeError(
            f"stage 09: flood frames {len(frames_payload)} bytes exceed cap {frame_cap}; "
            "reduce bands only as a last resort and record the deviation"
        )
    gzip_cap = int(
        cfg.pipeline["validation"]["gzip_caps_bytes"]["data/flood/flood-frames.geojson"]
    )
    frames_gzip = gzip_bytes(frames_payload)
    if frames_gzip > gzip_cap:
        raise RuntimeError(
            f"stage 09: flood frames gzip {frames_gzip} bytes exceed cap {gzip_cap}; "
            "record the two-class fallback instead of dropping polygons"
        )
    atomic_write_bytes(out_frames, frames_payload)
    for step_path in out_frames_dir.glob("step-*.geojson"):
        step_path.unlink()
    try:
        out_frames_dir.rmdir()
    except OSError:
        pass

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
        "totals": {
            "max_area_km2": round(peak_area, 4),
            "peak_stage_m": max(float(s["stage_m"]) for s in step_summaries),
            "scenario_days": int(scenario.raw["total_days"]),
            "districts_any_inundation": len(district_ever_wet),
            "median_depth_at_peak_m": (
                round(peak_median_depth, 4) if peak_median_depth is not None else None
            ),
            "p95_depth_at_peak_m": (
                round(peak_p95_depth, 4) if peak_p95_depth is not None else None
            ),
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
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_summary, summary, indent=2, sort_keys=False)

    public_scenario_path = cfg.root / "public" / "data" / "scenario.json"
    atomic_write_json(public_scenario_path, scenario.raw, indent=2, sort_keys=False)

    mask_bytes = path_size(out_masks_dir)
    stage.out(out_frames, out_summary, out_masks_dir, public_scenario_path)
    stage.metric("frames_features", total_features)
    stage.metric("frames_bytes", len(frames_payload))
    stage.metric("frames_gzip_bytes", frames_gzip)
    stage.metric("mask_cache_bytes", mask_bytes)
    stage.metric("peak_p95_depth_m", round(peak_p95_depth, 4))
    stage.metric("peak_clamped_wet_share", round(peak_clamped_wet_share, 6))
    stage.metric("clamped_aoi_share", round(clamped_aoi_share, 6))
    stage.metric("speckle_opening", f"{opening_cells}x{opening_cells}")
    stage.metric("speckle_min_part_area_km2", min_part_area)
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
    stage.finish(
        f"Connectivity {model['connectivity']}; depth bands {edges}; AOI v2 core "
        f"{core_area:,.1f} km²; per-step uint8 wet masks written to "
        f"{out_masks_dir.name}/; one GeoJSON per step written then combined into "
        f"{out_frames.name} and the staging files removed; no inundation-stack.npz. "
        "Bands polygonised separately, simplified at "
        f"{tolerance:.0f} m, converted to WGS84; only AOI v2 cells are counted."
    )
    print(
        f"[09] ok: {total_features} band features, peak {peak_area:,.0f} km² at "
        f"S{peak_index:02d} ({peak_area / core_area:.1%} of AOI v2, "
        f"{peak_area / flood_prone_area:.1%} of flood-prone), frames "
        f"{len(frames_payload) / 1024 / 1024:.2f} MB, masks {mask_bytes / 1024 / 1024:.1f} MB"
    )
    return summary
