"""Stage 09 — HAND-threshold inundation sequence, depth bands and summary."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes as raster_shapes
from rasterio.transform import Affine
from scipy.ndimage import label
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import unary_union

from .config import Config
from .geo import (
    drop_small_parts,
    feature,
    feature_collection,
    geodesic_area_km2,
    geom_to_geojson,
    load_geojson,
    polygon_parts,
    project_geom,
    row_cell_areas_km2,
    valid,
)
from .util import (
    StageRecord,
    atomic_write_json,
    ensure_dirs,
    json_bytes,
    utc_now,
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
        return None, 0.0
    parts = []
    for geom_mapping, _ in raster_shapes(
        band, mask=mask, connectivity=8, transform=step_transform
    ):
        geom = shape(geom_mapping)
        if geom.is_empty:
            continue
        parts.extend(polygon_parts(geom))
    if not parts:
        return None, 0.0
    # The connected components of one band are disjoint.  Build a MultiPolygon
    # directly instead of unioning thousands of parts per step (the union was
    # the dominant runtime and is not needed for disjoint parts).
    multi = MultiPolygon(parts)
    if not multi.is_valid:
        multi = valid(unary_union(parts))
    if multi is None or multi.is_empty:
        return None, 0.0
    wgs = project_geom(multi, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
    wgs = valid(wgs)
    if wgs is None or wgs.is_empty:
        return None, 0.0
    # Simplifying one MultiPolygon with tens of thousands of parts is very
    # expensive.  Simplify each disjoint part in WGS84 with an equivalent
    # ground tolerance (~75 m in latitude); this is the spec's latitude-safe
    # fallback and keeps the runtime bounded.
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
        return None, 0.0
    result = MultiPolygon(kept)
    if not result.is_valid:
        result = valid(unary_union(kept))
    if result is None or result.is_empty:
        return None, 0.0
    area = sum(geodesic_area_km2(part) for part in polygon_parts(result))
    if area <= 0:
        return None, 0.0
    return result, area


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
    out_stack: Path,
) -> dict:
    ensure_dirs()
    stage = StageRecord(
        "09",
        "build-inundation",
        inputs=[dem_path, hand_path, distance_path, channels_path, state_path, scenario_path],
    )
    scenario = cfg.scenario
    model = scenario.model
    res = float(cfg.aoi.resolution_m)
    nodata = float(cfg.aoi.nodata)
    edges = list(model["depth_bands_m"])
    min_component_cells = int(model.get("min_component_cells", 3))
    tolerance = float(model["simplify_tolerance_m"])
    min_band_area = float(model["min_polygon_area_km2"])
    version = cfg.pipeline["dataset_version"]

    with rasterio.open(hand_path) as src:
        hand = src.read(1)
        transform = src.transform
        width = src.width
        height = src.height
        crs = src.crs
    with rasterio.open(distance_path) as src:
        distance = src.read(1)
    with rasterio.open(channels_path) as src:
        channel = src.read(1) > 0
    if not channel.any():
        raise RuntimeError("stage 09: no channel cells")
    if hand.shape != (height, width):
        raise RuntimeError("stage 09: HAND raster shape mismatch")

    state_data = load_geojson(state_path)
    state_geoms = [shape(f["geometry"]) for f in state_data.get("features", [])]
    if not state_geoms:
        raise RuntimeError("stage 09: state outline has no geometry")
    from .geo import rasterize_geom

    state_utm = project_geom(
        unary_union(state_geoms), cfg.aoi.output_crs, cfg.aoi.analysis_crs
    )
    state_mask = rasterize_geom(
        state_utm, transform, width, height, dtype="uint8"
    ).astype(bool)
    if not state_mask.any():
        raise RuntimeError("stage 09: state mask is empty")

    districts_path = cfg.root / "pipeline" / "work" / "districts-base.geojson"
    district_ids = None
    district_names: list[str] = []
    if districts_path.exists():
        stage.inputs.append(districts_path)
        d_data = load_geojson(districts_path)
        shapes_list = []
        for index, district_feature in enumerate(d_data.get("features", []), start=1):
            district_names.append(district_feature["properties"]["district_id"])
            district_geom = project_geom(
                shape(district_feature["geometry"]), cfg.aoi.output_crs, cfg.aoi.analysis_crs
            )
            shapes_list.append((district_geom, index))
        if shapes_list:
            from rasterio.features import rasterize

            district_ids = rasterize(
                shapes_list,
                out_shape=(height, width),
                transform=transform,
                fill=0,
                all_touched=False,
                dtype="int32",
            )

    areas = row_cell_areas_km2(transform, height, width, cfg.aoi.analysis_crs)
    area_2d = np.broadcast_to(areas, (height, width))
    valid_hand = hand != nodata
    valid_assam = valid_hand & state_mask
    assam_cells = int(state_mask.sum())
    valid_assam_cells = int(valid_assam.sum())
    valid_cell_share = valid_assam_cells / assam_cells if assam_cells else 0.0
    assam_area_km2 = _row_area(areas, state_mask)
    print(
        f"[09] Assam mask {assam_cells / 1e6:.2f}M cells, {assam_area_km2:,.0f} km²; "
        f"valid HAND share {valid_cell_share:.1%}"
    )

    tmp_depth = out_stack.parent / "_stack-depth.npy"
    tmp_wet = out_stack.parent / "_stack-wet.npy"
    out_stack.parent.mkdir(parents=True, exist_ok=True)
    depth_mm = np.lib.format.open_memmap(
        tmp_depth, mode="w+", dtype=np.float32, shape=(scenario.step_count, height, width)
    )
    wet_mm = np.lib.format.open_memmap(
        tmp_wet, mode="w+", dtype=bool, shape=(scenario.step_count, height, width)
    )

    step_summaries: list[dict] = []
    frame_features: list[dict] = []
    prev_wet = np.zeros((height, width), dtype=bool)
    district_ever_wet: set[int] = set()
    peak_area = 0.0
    peak_index = 0

    for index, step in enumerate(scenario.steps):
        stage_m = float(step["stage_m"])
        step_label = str(step["label"])
        phase = str(step["phase"])
        wet_raw = valid_assam & (hand <= stage_m)
        depth_raw = np.where(wet_raw, stage_m - hand, np.float32(0.0)).astype(np.float32)
        wet, component_count, dropped = _component_filter(
            wet_raw, distance, min_component_cells, res
        )
        depth = np.where(wet, depth_raw, np.float32(0.0)).astype(np.float32)
        depth_mm[index] = depth
        wet_mm[index] = wet

        area_km2 = _row_area(areas, wet)
        new_km2 = _row_area(areas, wet & ~prev_wet)
        receded_km2 = _row_area(areas, ~wet & prev_wet)
        if wet.any():
            max_depth = float(depth.max())
            mean_depth = _row_area(areas, depth * wet) / area_km2 if area_km2 > 0 else None
        else:
            max_depth = None
            mean_depth = None

        affected = 0
        if district_ids is not None and wet.any():
            wet_ids = district_ids[wet]
            wet_weights = area_2d[wet]
            district_area = np.bincount(
                wet_ids, weights=wet_weights, minlength=len(district_names) + 1
            )
            district_area[0] = 0.0  # outside the simplified district union
            affected_ids = np.flatnonzero(district_area > 1.0)
            affected = int(len(affected_ids))
            district_ever_wet.update(int(v) for v in affected_ids)
        elif district_ids is not None:
            affected = 0

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
            "max_depth_m": round(max_depth, 4) if max_depth is not None else None,
            "mean_depth_m": round(mean_depth, 4) if mean_depth is not None else None,
            "affected_district_count": affected,
            "valid_cell_share": round(valid_cell_share, 6),
        }
        step_summaries.append(summary_step)
        if area_km2 > peak_area:
            peak_area = area_km2
            peak_index = index
        prev_wet = wet

        # Polygonise bands within the wet bounding window only.
        if wet.any():
            rows = np.flatnonzero(wet.any(axis=1))
            cols = np.flatnonzero(wet.any(axis=0))
            r0, r1 = int(rows[0]), int(rows[-1]) + 1
            c0, c1 = int(cols[0]), int(cols[-1]) + 1
            depth_window = depth[r0:r1, c0:c1]
            band = _band_index(depth_window, edges)
            window_transform = transform * Affine.translation(c0, r0)
            for band_value in range(1, 5):
                band_label, lo, hi = BAND_LABELS[band_value - 1]
                geom_wgs, band_area = _polygonise_band(
                    band, band_value, window_transform, cfg, tolerance, min_band_area
                )
                if geom_wgs is None:
                    continue
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
                    frame_features.append(feat)

        print(
            f"[09] S{index:02d} {step_label} {phase:8s} stage {stage_m:.1f} m: "
            f"{area_km2:,.0f} km² wet ({area_km2 / assam_area_km2:.1%} of Assam), "
            f"max depth {max_depth if max_depth is None else round(max_depth, 2)}, "
            f"components {component_count} dropped {dropped}"
        )

    depth_mm.flush()
    wet_mm.flush()
    np.savez(out_stack, depth=depth_mm, wet=wet_mm)
    del depth_mm, wet_mm
    tmp_depth.unlink(missing_ok=True)
    tmp_wet.unlink(missing_ok=True)

    # Validate the shape of the hydrograph before writing the public files.
    rising = [s["inundated_area_km2"] for s in step_summaries[: scenario.peak_step + 1]]
    recession = [s["inundated_area_km2"] for s in step_summaries[scenario.peak_step :]]
    tolerance_area = float(cfg.pipeline["inundation"]["monotonic_tolerance"])
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
    max_share = float(cfg.pipeline["inundation"]["max_peak_area_share_of_assam"])
    if peak_area > assam_area_km2 * max_share:
        raise RuntimeError(
            f"stage 09: peak area {peak_area:,.0f} km² exceeds {max_share:.0%} of Assam "
            f"({assam_area_km2 * max_share:,.0f} km²)"
        )

    frame_features.sort(
        key=lambda f: (
            f["properties"]["step"],
            BAND_LABELS.index(
                next(b for b in BAND_LABELS if b[0] == f["properties"]["depth_band"])
            ),
            -f["properties"]["band_area_km2"],
            json.dumps(f["geometry"])[:120],
        )
    )
    frames = feature_collection(
        "Scenario inundation depth bands", "scenario", frame_features, version
    )
    out_frames.parent.mkdir(parents=True, exist_ok=True)
    frames_payload = json_bytes(frames, indent=None)
    from .util import atomic_write_bytes

    frame_cap = int(cfg.pipeline["validation"]["file_caps_bytes"]["data/flood/flood-frames.geojson"])
    if len(frames_payload) > frame_cap:
        raise RuntimeError(
            f"stage 09: flood frames {len(frames_payload)} bytes exceed cap {frame_cap}; "
            "reduce bands only as a last resort and record the deviation"
        )
    atomic_write_bytes(out_frames, frames_payload)
    total_features = len(frame_features)
    for index, step in enumerate(scenario.steps):
        if not any(f["properties"]["step"] == index for f in frame_features):
            raise RuntimeError(f"stage 09: step {index} has no flood feature")

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
        },
    }
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_summary, summary, indent=2, sort_keys=False)

    public_scenario_path = cfg.root / "public" / "data" / "scenario.json"
    atomic_write_json(public_scenario_path, scenario.raw, indent=2, sort_keys=False)

    stage.out(out_frames, out_summary, out_stack, public_scenario_path)
    stage.metric("frames_features", total_features)
    stage.metric("frames_bytes", len(frames_payload))
    stage.metric("peak_area_km2", round(peak_area, 4))
    stage.metric("assam_area_km2", round(assam_area_km2, 4))
    stage.metric("peak_area_share_of_assam", round(peak_area / assam_area_km2, 6))
    stage.metric("valid_cell_share", round(valid_cell_share, 6))
    stage.metric("stack_bytes", out_stack.stat().st_size)
    stage.finish(
        f"Connectivity {model['connectivity']}; depth bands {edges}; bands polygonised "
        f"separately, simplified at {tolerance:.0f} m in EPSG:32646, converted to WGS84; "
        "only cells inside the dissolved Assam mask are counted."
    )
    print(
        f"[09] ok: {total_features} band features, peak {peak_area:,.0f} km² at S{peak_index:02d}, "
        f"frames {len(frames_payload) / 1024 / 1024:.2f} MB, stack {out_stack.stat().st_size / 1024 / 1024:.0f} MB"
    )
    return summary
