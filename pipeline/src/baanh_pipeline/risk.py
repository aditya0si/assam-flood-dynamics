"""Stage 10 — scenario-conditional risk zones, district ranking and hotspots."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import Affine
from scipy import ndimage
from shapely.geometry import Point, shape

from .config import Config
from .geo import (
    feature,
    feature_collection,
    geodesic_area_km2,
    load_geojson,
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

CLASS_NAMES = {1: "very_high", 2: "high", 3: "moderate", 4: "low"}
CLASS_ORDER = {name: rank for rank, name in CLASS_NAMES.items()}


def _duration_weights(days: list[int]) -> np.ndarray:
    n = len(days)
    weights = np.zeros(n, dtype=np.float32)
    weights[0] = (days[1] - days[0]) / 2.0
    weights[-1] = (days[-1] - days[-2]) / 2.0
    for k in range(1, n - 1):
        weights[k] = (days[k + 1] - days[k - 1]) / 2.0
    return weights


def _classify_cells(score: np.ndarray, thresholds: dict[str, float], names: dict[int, str]) -> np.ndarray:
    out = np.zeros(score.shape, dtype=np.uint8)
    out[score >= thresholds["moderate"]] = 3
    out[score >= thresholds["high"]] = 2
    out[score >= thresholds["very_high"]] = 1
    return out


def _class_from_thresholds(score: float, thresholds: dict[str, float]) -> str:
    if score >= thresholds["very_high"]:
        return "very_high"
    if score >= thresholds["high"]:
        return "high"
    if score >= thresholds["moderate"]:
        return "moderate"
    return "low"


def _district_class(score: float, cfg: Config) -> str:
    return _class_from_thresholds(score, cfg.pipeline["risk"]["district"]["thresholds"])


def _weighted_percentile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    if values.size == 0:
        return 0.0
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights)
    if cumulative[-1] <= 0:
        return 0.0
    target = q * cumulative[-1]
    index = int(np.searchsorted(cumulative, target, side="left"))
    return float(values[min(index, values.size - 1)])


def _simplify_wgs(geom, tolerance_m: float, cfg: Config):
    proj = project_geom(geom, cfg.aoi.output_crs, cfg.aoi.analysis_crs)
    simplified = valid(proj.simplify(tolerance_m, preserve_topology=True))
    if simplified is None or simplified.is_empty:
        return None
    return project_geom(simplified, cfg.aoi.analysis_crs, cfg.aoi.output_crs)


def run(
    cfg: Config,
    masks_dir: Path,
    hand_path: Path,
    distance_path: Path,
    channels_path: Path,
    districts_path: Path,
    scenario_path: Path,
    out_zones: Path,
    out_ranking: Path,
    out_districts: Path,
    out_hotspots: Path,
) -> dict:
    ensure_dirs()
    stage = StageRecord(
        "10",
        "build-risk",
        inputs=[masks_dir, hand_path, distance_path, channels_path, districts_path, scenario_path],
    )
    scenario = cfg.scenario
    risk_cfg = cfg.pipeline["risk"]
    version = cfg.pipeline["dataset_version"]
    res = float(cfg.aoi.resolution_m)
    nodata = float(cfg.aoi.nodata)

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

    mask_paths = [masks_dir / f"step-{index:02d}-wet.tif" for index in range(scenario.step_count)]
    missing_masks = [path for path in mask_paths if not path.exists()]
    if missing_masks:
        raise RuntimeError(
            "stage 10: per-step wet masks are missing; re-run stage 09 "
            f"({', '.join(path.name for path in missing_masks[:3])})"
        )

    def read_wet(index: int) -> np.ndarray:
        with rasterio.open(mask_paths[index]) as src:
            wet = src.read(1) > 0
        if wet.shape != (height, width):
            raise RuntimeError(
                f"stage 10: wet mask {mask_paths[index].name} shape {wet.shape} "
                f"does not match HAND {(height, width)}"
            )
        return wet

    days = scenario.days
    weights = _duration_weights(days)
    if abs(float(weights.sum()) - float(scenario.raw["total_days"])) > 1e-3:
        raise RuntimeError(
            f"stage 10: duration weights sum to {weights.sum()} not {scenario.raw['total_days']}"
        )

    duration = np.zeros((height, width), dtype=np.float32)
    peak_depth = np.zeros((height, width), dtype=np.float32)
    first_wet = np.full((height, width), -1, dtype=np.int8)
    wet_any = np.zeros((height, width), dtype=bool)
    for index in range(scenario.step_count):
        stage_m = float(scenario.steps[index]["stage_m"])
        w = read_wet(index)
        d = np.where(w, stage_m - hand, np.float32(0.0)).astype(np.float32)
        duration += np.where(d > 0.1, weights[index], np.float32(0.0))
        np.maximum(peak_depth, d, out=peak_depth)
        first_wet = np.where((first_wet < 0) & w, index, first_wet).astype(np.int8)
        wet_any |= w

    valid_hand = hand != nodata
    cell_cfg = risk_cfg["cell"]
    hand_term = np.clip(hand, 0.0, float(cell_cfg["hand_reference_m"])) / float(
        cell_cfg["hand_reference_m"]
    )
    duration_term = np.clip(duration, 0.0, float(cell_cfg["duration_reference_days"])) / float(
        cell_cfg["duration_reference_days"]
    )
    cell_risk = 100.0 * (
        float(cell_cfg["hand_weight"]) * (1.0 - hand_term)
        + float(cell_cfg["duration_weight"]) * duration_term
    )
    cell_risk = np.clip(cell_risk, 0.0, 100.0)
    cell_risk = np.where(wet_any & valid_hand, cell_risk, np.float32(0.0)).astype(np.float32)
    class_raster = _classify_cells(cell_risk, cell_cfg["thresholds"], CLASS_NAMES)
    class_raster[~wet_any | ~valid_hand] = 0

    rows = np.flatnonzero(wet_any.any(axis=1))
    cols = np.flatnonzero(wet_any.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        raise RuntimeError("stage 10: no wet cells to classify")
    r0, r1 = int(rows[0]), int(rows[-1]) + 1
    c0, c1 = int(cols[0]), int(cols[-1]) + 1
    window_transform = transform * Affine.translation(c0, r0)
    class_window = class_raster[r0:r1, c0:c1]
    score_window = cell_risk[r0:r1, c0:c1]
    hand_window = hand[r0:r1, c0:c1]
    duration_window = duration[r0:r1, c0:c1]
    peak_window = peak_depth[r0:r1, c0:c1]
    wet_window = wet_any[r0:r1, c0:c1]
    areas = row_cell_areas_km2(transform, height, width, cfg.aoi.analysis_crs)
    area_window = np.broadcast_to(areas[r0:r1], (r1 - r0, c1 - c0))

    from rasterio.features import shapes as raster_shapes

    structure = np.ones((3, 3), dtype=np.int8)
    min_zone_area = float(risk_cfg["zone"]["min_area_km2"])
    zone_tolerance = float(risk_cfg["zone"]["simplify_tolerance_m"])
    wet_window = wet_any[r0:r1, c0:c1]

    def _blocks(array, bh, bw, factor, pad_h, pad_w):
        padded = np.pad(array, ((0, pad_h), (0, pad_w)), mode="constant")
        return padded.reshape(bh, factor, bw, factor)

    def build_zones(block_factor: float, tolerance_m: float):
        """Vectorise the classified wet mask on a block-majority grid.

        The 0.9 MB raw cap cannot be met by one polygon per 8-connected 90 m
        component: the peak mask has ~75k class components and 12k of them pass
        the 0.05 km² floor, which is several MB even at coarse simplification.
        Vectorising a block-majority grid preserves the class areas (a block is
        kept when at least half of its cells are wet) while reducing the
        boundary coordinate count.  Statistics are still computed from the
        90 m cells under each zone.
        """
        factor = int(block_factor)
        hh, ww = class_window.shape
        bh = (hh + factor - 1) // factor
        bw = (ww + factor - 1) // factor
        pad_h = bh * factor - hh
        pad_w = bw * factor - ww
        class_blocks = _blocks(class_window, bh, bw, factor, pad_h, pad_w)
        wet_blocks = _blocks(wet_window, bh, bw, factor, pad_h, pad_w)
        class_counts = np.stack(
            [(class_blocks == value).sum(axis=(1, 3)) for value in (1, 2, 3, 4)],
            axis=0,
        )
        coarse = (np.argmax(class_counts, axis=0) + 1).astype(np.uint8)
        coarse_wet_cells = wet_blocks.sum(axis=(1, 3))
        coarse[coarse_wet_cells < (factor * factor + 1) // 2] = 0

        def block_sum(array):
            return _blocks(array, bh, bw, factor, pad_h, pad_w).sum(axis=(1, 3))

        def block_max(array):
            return _blocks(array, bh, bw, factor, pad_h, pad_w).max(axis=(1, 3))

        block_wet_area = block_sum(area_window * wet_window)
        block_score_area = block_sum(score_window * area_window)
        block_hand_area = block_sum(hand_window * wet_window * area_window)
        block_duration_area = block_sum(duration_window * wet_window * area_window)
        block_peak_max = block_max(peak_window)
        coarse_transform = window_transform * Affine.scale(factor, factor)

        records: list[dict] = []
        temp_raster = np.zeros(coarse.shape, dtype=np.int32)
        for class_value in (1, 2, 3, 4):
            mask = coarse == class_value
            if not mask.any():
                continue
            labels, component_count = ndimage.label(mask, structure=structure)
            if component_count == 0:
                continue
            ids = np.arange(1, component_count + 1, dtype=np.int32)
            component_area = ndimage.sum(block_wet_area, labels=labels, index=ids)
            keep_ids = ids[component_area >= min_zone_area - 0.01]
            if keep_ids.size == 0:
                continue
            keep_lookup = np.zeros(component_count + 1, dtype=bool)
            keep_lookup[keep_ids] = True
            keep_mask = keep_lookup[labels]
            mapping = np.zeros(component_count + 1, dtype=np.int32)
            start = len(records)
            for label_id in keep_ids:
                temp_id = len(records) + 1
                mapping[int(label_id)] = temp_id
                records.append(
                    {"temp": temp_id, "label": int(label_id), "class": class_value}
                )
            class_zone = mapping[labels]
            temp_raster[class_zone > 0] = class_zone[class_zone > 0]
            geoms = {
                int(value): shape(geometry_mapping)
                for geometry_mapping, value in raster_shapes(
                    labels,
                    mask=keep_mask,
                    connectivity=8,
                    transform=coarse_transform,
                )
            }
            for record in records[start:]:
                record["utm"] = geoms.get(record["label"])

        if not records:
            return [], 0
        temp_max = max(record["temp"] for record in records)
        kept = []
        for record in records:
            geom = record.get("utm")
            if geom is None or geom.is_empty:
                continue
            simplified = valid(geom.simplify(tolerance_m, preserve_topology=True))
            if simplified is None or simplified.is_empty:
                continue
            wgs = valid(project_geom(simplified, cfg.aoi.analysis_crs, cfg.aoi.output_crs))
            if wgs is None or wgs.is_empty:
                continue
            area = geodesic_area_km2(wgs)
            if area < min_zone_area:
                continue
            centroid = wgs.representative_point()
            kept.append(
                {
                    "temp": record["temp"],
                    "wgs": wgs,
                    "class": record["class"],
                    "area": area,
                    "cx": float(centroid.x),
                    "cy": float(centroid.y),
                }
            )
        kept.sort(
            key=lambda r: (
                r["class"],
                round(r["cy"], 5),
                round(r["cx"], 5),
                -r["area"],
            )
        )
        if not kept:
            return [], 0
        remap = np.zeros(temp_max + 1, dtype=np.int32)
        for index, record in enumerate(kept, start=1):
            remap[record["temp"]] = index
        zone_raster = remap[temp_raster]
        ids = np.arange(1, len(kept) + 1, dtype=np.int32)
        area_sum = ndimage.sum(block_wet_area, labels=zone_raster, index=ids)
        score_sum = ndimage.sum(block_score_area, labels=zone_raster, index=ids)
        hand_sum = ndimage.sum(block_hand_area, labels=zone_raster, index=ids)
        duration_sum = ndimage.sum(block_duration_area, labels=zone_raster, index=ids)
        max_peak = ndimage.maximum(block_peak_max, labels=zone_raster, index=ids)
        features = []
        for index, record in enumerate(kept):
            if area_sum[index] <= 0:
                continue
            mean_score = float(score_sum[index] / area_sum[index])
            mean_score = min(100.0, max(0.0, mean_score))
            zone_class = _class_from_thresholds(mean_score, cell_cfg["thresholds"])
            feature_record = {
                "zone_id": f"RZ-{len(features) + 1:04d}",
                "risk_class": zone_class,
                "risk_score": round(mean_score, 3),
                "mean_hand_m": round(float(hand_sum[index] / area_sum[index]), 3),
                "mean_duration_days": round(
                    float(duration_sum[index] / area_sum[index]), 3
                ),
                "peak_depth_m": round(float(max_peak[index]), 3),
                "area_km2": round(float(record["area"]), 4),
                "class": "derived",
                "model_version": scenario.model_version,
                "label": f"Derived risk zone · {zone_class.replace('_', ' ')}",
            }
            item = feature(record["wgs"], feature_record, cfg.aoi.decimals)
            if item is not None:
                features.append(item)
        return features, int((zone_raster > 0).sum())

    cap = int(cfg.pipeline["validation"]["file_caps_bytes"]["data/risk/risk-zones.geojson"])
    chosen = None
    for block_factor in (4, 5, 6, 8, 10, 12):
        zone_features, _ = build_zones(block_factor, zone_tolerance)
        payload = json_bytes(
            feature_collection("Derived risk zones", "derived", zone_features, version),
            indent=None,
        )
        grid_m = block_factor * res
        print(
            f"[10] risk zones on {grid_m:.0f} m block-majority grid: "
            f"{len(zone_features)} features, {len(payload):,} B "
            f"(cap {cap:,} B)"
        )
        if len(payload) <= cap:
            chosen = (block_factor, zone_features, payload, grid_m)
            break
    if chosen is None:
        raise RuntimeError(
            f"stage 10: risk zones still exceed the {cap} byte cap at a "
            "1,080 m block-majority grid"
        )
    block_factor, zone_features, payload, zone_grid_m = chosen
    out_zones.parent.mkdir(parents=True, exist_ok=True)
    from .util import atomic_write_bytes

    atomic_write_bytes(out_zones, payload)

    # District raster and aggregation.
    districts_data = load_geojson(districts_path)
    district_features = districts_data.get("features", [])
    district_names = [f["properties"]["name"] for f in district_features]
    district_ids_list = [f["properties"]["district_id"] for f in district_features]
    district_area_km2 = [float(f["properties"]["area_km2"]) for f in district_features]
    district_shapes = [
        (project_geom(shape(f["geometry"]), cfg.aoi.output_crs, cfg.aoi.analysis_crs), i + 1)
        for i, f in enumerate(district_features)
    ]
    district_raster = rasterize(
        district_shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        all_touched=False,
        dtype="int32",
    )
    n_districts = len(district_features)
    area_2d = np.broadcast_to(areas, (height, width))
    district_cell_area = ndimage.sum(area_2d, labels=district_raster, index=np.arange(1, n_districts + 1))
    district_valid_area = ndimage.sum(
        area_2d * valid_hand, labels=district_raster, index=np.arange(1, n_districts + 1)
    )
    peak_flooded = np.zeros(n_districts, dtype=np.float64)
    for index in range(scenario.step_count):
        w = read_wet(index)
        if not w.any():
            continue
        d_area = np.bincount(
            district_raster[w],
            weights=area_2d[w],
            minlength=n_districts + 1,
        )[1:]
        peak_flooded = np.maximum(peak_flooded, d_area)
    ever_wet_area = np.bincount(
        district_raster[wet_any], weights=area_2d[wet_any], minlength=n_districts + 1
    )[1:]
    duration_sum = np.bincount(
        district_raster[wet_any],
        weights=(duration * area_2d)[wet_any],
        minlength=n_districts + 1,
    )[1:]
    mean_duration = np.divide(
        duration_sum, ever_wet_area, out=np.zeros(n_districts), where=ever_wet_area > 0
    )
    peak_stage = float(scenario.steps[scenario.peak_step]["stage_m"])
    peak_step_wet = read_wet(scenario.peak_step)
    peak_step_depth = np.where(
        peak_step_wet, peak_stage - hand, np.float32(0.0)
    ).astype(np.float32)
    p90_depth = np.zeros(n_districts, dtype=np.float64)
    for index in range(n_districts):
        mask = (district_raster == index + 1) & peak_step_wet
        if not mask.any():
            continue
        values = peak_step_depth[mask].astype(np.float64)
        weights_cells = area_2d[mask].astype(np.float64)
        p90_depth[index] = _weighted_percentile(values, weights_cells, 0.90)

    district_cfg = risk_cfg["district"]
    scores = np.full(n_districts, np.nan)
    classes = [None] * n_districts
    drivers: list[list[str]] = [[] for _ in range(n_districts)]
    area_share_arr = np.zeros(n_districts)
    for index in range(n_districts):
        if district_cell_area[index] <= 0 or peak_flooded[index] <= 0 or ever_wet_area[index] <= 0:
            continue
        area_share = min(peak_flooded[index] / district_area_km2[index], 1.0)
        area_share_arr[index] = area_share
        a_term = min(area_share / float(district_cfg["area_share_saturation"]), 1.0)
        d_term = min(mean_duration[index] / float(district_cfg["duration_saturation_days"]), 1.0)
        h_term = min(p90_depth[index] / float(district_cfg["depth_reference_m"]), 1.0)
        score = 100.0 * (
            float(district_cfg["weights"]["area_share"]) * a_term
            + float(district_cfg["weights"]["duration"]) * d_term
            + float(district_cfg["weights"]["depth"]) * h_term
        )
        scores[index] = min(100.0, max(0.0, score))
        classes[index] = _class_from_thresholds(scores[index], district_cfg["thresholds"])
        contributions = [
            ("area", float(district_cfg["weights"]["area_share"]) * a_term),
            ("duration", float(district_cfg["weights"]["duration"]) * d_term),
            ("depth", float(district_cfg["weights"]["depth"]) * h_term),
        ]
        contributions.sort(key=lambda item: (-item[1], ["area", "duration", "depth"].index(item[0])))
        drivers[index] = [name for name, value in contributions[:2] if value > 0]

    ranked = [
        index
        for index in range(n_districts)
        if np.isfinite(scores[index]) and scores[index] is not None and peak_flooded[index] > 0
    ]
    ranked.sort(key=lambda index: (-scores[index], district_names[index]))
    ranks = {index: rank + 1 for rank, index in enumerate(ranked)}

    districts_out = []
    for index in range(n_districts):
        has_score = np.isfinite(scores[index])
        risk_score = round(float(scores[index]), 3) if has_score else None
        risk_class = classes[index] if has_score else None
        rank = ranks.get(index)
        valid_share = (
            float(district_valid_area[index] / district_cell_area[index])
            if district_cell_area[index] > 0
            else 0.0
        )
        districts_out.append(
            {
                "district_id": district_ids_list[index],
                "name": district_names[index],
                "area_km2": district_area_km2[index],
                "peak_flooded_area_km2": round(float(peak_flooded[index]), 4),
                "area_share": round(float(area_share_arr[index]), 6),
                "mean_duration_days": round(float(mean_duration[index]), 4),
                "p90_peak_depth_m": round(float(p90_depth[index]), 4),
                "risk_score": risk_score,
                "risk_class": risk_class,
                "drivers": drivers[index],
                "valid_area_share": round(valid_share, 6),
                "class": "derived",
            }
        )

    counts = {
        "total": n_districts,
        "very_high": sum(1 for d in districts_out if d["risk_class"] == "very_high"),
        "high": sum(1 for d in districts_out if d["risk_class"] == "high"),
        "moderate": sum(1 for d in districts_out if d["risk_class"] == "moderate"),
        "low": sum(1 for d in districts_out if d["risk_class"] == "low"),
        "no_data": sum(1 for d in districts_out if d["risk_score"] is None),
    }
    rank_by_id = {
        district_ids_list[index]: ranks[index] for index in range(n_districts) if index in ranks
    }
    ranked_out = sorted(
        [d for d in districts_out if d["risk_score"] is not None],
        key=lambda d: rank_by_id[d["district_id"]],
    )
    ranking = {
        "schema_version": "1.0.0",
        "scenario_id": scenario.scenario_id,
        "class": "derived",
        "generated_at": utc_now(),
        "weights": dict(district_cfg["weights"]),
        "reference_values": {
            "area_share_saturation": float(district_cfg["area_share_saturation"]),
            "duration_saturation_days": float(district_cfg["duration_saturation_days"]),
            "depth_reference_m": float(district_cfg["depth_reference_m"]),
        },
        "districts": [{**d, "rank": rank_by_id[d["district_id"]]} for d in ranked_out],
        "counts": counts,
    }
    out_ranking.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_ranking, ranking, indent=2, sort_keys=False)

    # Join risk attributes into the district GeoJSON, with a cap fallback that
    # only simplifies display geometry.
    base_by_id = {f["properties"]["district_id"]: f for f in district_features}
    risk_by_id = {d["district_id"]: d for d in districts_out}
    district_tolerance = float(cfg.pipeline["admin"]["simplify_district_m"])
    district_cap = int(cfg.pipeline["validation"]["file_caps_bytes"]["data/admin/assam-districts.geojson"])
    while True:
        joined = []
        for feature_item in district_features:
            props = feature_item["properties"]
            risk = risk_by_id[props["district_id"]]
            geom = shape(feature_item["geometry"])
            if district_tolerance > float(cfg.pipeline["admin"]["simplify_district_m"]):
                geom = _simplify_wgs(geom, district_tolerance, cfg)
                if geom is None:
                    geom = shape(feature_item["geometry"])
            joined_props = {
                **props,
                "risk_score": risk["risk_score"],
                "risk_class": risk["risk_class"],
                "rank": rank_by_id.get(props["district_id"]),
                "valid_area_share": risk["valid_area_share"],
                "class": "source",
                "derived_fields": ["risk_score", "risk_class", "rank"],
                "label": "District boundary (source); risk attributes (derived)",
            }
            item = feature(geom, joined_props, cfg.aoi.decimals)
            if item is not None:
                joined.append(item)
        payload = json_bytes(
            feature_collection("Assam districts with derived risk", "source", joined, version),
            indent=None,
        )
        if len(payload) <= district_cap or district_tolerance >= 400:
            break
        district_tolerance += 50
        print(f"[10] districts over cap; simplifying at {district_tolerance:.0f} m")
    if len(payload) > district_cap:
        raise RuntimeError(
            f"stage 10: districts {len(payload)} bytes exceed cap {district_cap}"
        )
    out_districts.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(out_districts, payload)

    # Hotspots.
    hotspot_cfg = risk_cfg["hotspots"]
    peak_wet = peak_step_wet
    eligible = (
        peak_wet
        & (hand <= float(hotspot_cfg["max_hand_m"]))
        & (distance >= float(hotspot_cfg["min_distance_m"]))
        & valid_hand
    )
    components, count = ndimage.label(eligible, structure=np.ones((3, 3), dtype=np.int8))
    hotspot_records = []
    if count:
        sizes = np.bincount(components.ravel(), minlength=count + 1)
        for component_id in range(1, count + 1):
            if sizes[component_id] < 2:
                continue
            ys, xs = np.nonzero(components == component_id)
            if ys.size == 0:
                continue
            area_km2 = float(areas[ys, 0].sum())
            if area_km2 < float(hotspot_cfg["min_area_km2"]):
                continue
            first_step_component = int(first_wet[ys, xs].min()) if first_wet[ys, xs].size else -1
            if first_step_component < 0 or first_step_component > int(hotspot_cfg["latest_first_wet_step"]):
                continue
            distance_values = distance[ys, xs]
            max_index = int(np.argmax(distance_values))
            py, px = int(ys[max_index]), int(xs[max_index])
            x_utm, y_utm = rasterio.transform.xy(transform, py, px, offset="center")
            from .geo import project_coords

            lon, lat = project_coords(
                [(float(x_utm), float(y_utm))],
                cfg.aoi.analysis_crs,
                cfg.aoi.output_crs,
            )[0]
            district_id = None
            if district_raster[py, px] > 0:
                district_id = district_ids_list[int(district_raster[py, px]) - 1]
            hotspot_records.append(
                {
                    "area_km2": area_km2,
                    "hand_mean_m": float(hand[ys, xs].mean()),
                    "distance_to_channel_m": float(distance_values.min()),
                    "first_step": first_step_component,
                    "peak_depth_m": float(peak_depth[ys, xs].max()),
                    "lon": float(lon),
                    "lat": float(lat),
                    "district_id": district_id,
                }
            )
    hotspot_records.sort(key=lambda r: (-r["area_km2"], -r["lon"], -r["lat"]))
    hotspot_records = hotspot_records[: int(hotspot_cfg["max_count"])]
    hotspot_features = []
    for rank, record in enumerate(hotspot_records, start=1):
        props = {
            "hotspot_id": f"HS-{rank:02d}",
            "rank": rank,
            "reason": "low_hand_backwater_pocket",
            "area_km2": round(record["area_km2"], 4),
            "hand_mean_m": round(record["hand_mean_m"], 3),
            "distance_to_channel_m": round(record["distance_to_channel_m"], 1),
            "first_step": record["first_step"],
            "peak_depth_m": round(record["peak_depth_m"], 3),
            "centroid_lon": round(record["lon"], 5),
            "centroid_lat": round(record["lat"], 5),
            "district_id": record["district_id"],
            "class": "derived",
            "label": "Derived inundation hotspot · low-HAND pocket (not a breach)",
        }
        item = feature(Point(record["lon"], record["lat"]), props, cfg.aoi.decimals)
        if item is not None:
            hotspot_features.append(item)
    hotspots = feature_collection("Derived inundation hotspots", "derived", hotspot_features, version)
    out_hotspots.parent.mkdir(parents=True, exist_ok=True)
    hotspot_payload = json_bytes(hotspots, indent=None)
    atomic_write_bytes(out_hotspots, hotspot_payload)

    # Stage-level assertions.
    for d in districts_out:
        if d["risk_score"] is not None and not (0 <= d["risk_score"] <= 100):
            raise RuntimeError(f"stage 10: district score out of range for {d['name']}")
    if len({d["district_id"] for d in districts_out}) != len(districts_out):
        raise RuntimeError("stage 10: duplicate district in ranking")
    if sorted(ranks.values()) != list(range(1, len(ranks) + 1)):
        raise RuntimeError("stage 10: rank is not dense")
    for feature_item in zone_features:
        props = feature_item["properties"]
        if props["risk_class"] != _class_from_thresholds(props["risk_score"], cell_cfg["thresholds"]):
            raise RuntimeError(
                f"stage 10: zone {props['zone_id']} class {props['risk_class']} does not "
                f"match score {props['risk_score']}"
            )
    if len(hotspot_features) > int(hotspot_cfg["max_count"]):
        raise RuntimeError("stage 10: too many hotspots")

    stage.out(out_zones, out_ranking, out_districts, out_hotspots)
    stage.metric("zone_count", len(zone_features))
    stage.metric("zone_bytes", len(payload))
    stage.metric("district_count", n_districts)
    stage.metric("ranked_districts", len(ranked))
    stage.metric("hotspot_count", len(hotspot_features))
    stage.metric("max_district_score", round(float(np.nanmax(scores)), 3))
    stage.metric("zone_simplify_m", zone_tolerance)
    stage.metric("zone_block_factor", block_factor)
    stage.metric("zone_grid_m", zone_grid_m)
    stage.finish(
        "Cell risk = 100 x (0.60 x (1 - HAND/6) + 0.40 x duration/136), only cells wet "
        "in >=1 step; risk zones vectorised on a block-majority grid "
        f"({zone_grid_m:.0f} m, factor {block_factor}) with 90 m cell statistics, "
        f"simplified at {zone_tolerance:.0f} m to satisfy the fixed 0.9 MB raw cap; "
        "district score = 0.45 area share + 0.35 duration + 0.20 p90 peak depth; "
        "hotspots are low-HAND distant pockets, not breaches. Wet masks and depth are "
        "read from the stage-09 uint8 per-step cache, not a float stack. No demographics."
    )
    print(
        f"[10] ok: {len(zone_features)} zones ({len(payload) / 1024:.0f} KB), "
        f"{len(ranked)} ranked districts, {len(hotspot_features)} hotspots, "
        f"districts {len(payload) if False else out_districts.stat().st_size / 1024:.0f} KB"
    )
    return ranking
