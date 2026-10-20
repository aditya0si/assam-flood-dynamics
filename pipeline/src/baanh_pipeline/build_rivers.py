"""Stage 06 — AOI v2, channel policy v2 and the display river layer.

REVIEW-02 A2: only ``waterway=river``, clipped to AOI v2 + 5 km, midpoint
inside that buffer, clipped length >= 2 km, Brahmaputra main stem as order 1
(2-cell dilation), everything else 1 cell.  The channel-cell share of AOI v2
is a hard 4.0 % gate; the shortest ways are pruned until it passes and the
count is recorded in provenance.  The display layer shows exactly the kept
set.
"""
from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import LineString, MultiLineString, shape

from . import aoi_domain
from .channels import rasterize_channels
from .config import Config
from .geo import (
    feature,
    feature_collection,
    geodesic_length_km,
    load_geojson,
    project_geom,
    valid,
)
from .util import (
    StageRecord,
    atomic_write_bytes,
    atomic_write_json,
    ensure_dirs,
    json_bytes,
)


def _parts(geom) -> list[LineString]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, LineString)]


def run(
    cfg: Config,
    raw_path: Path,
    dem_path: Path,
    state_path: Path,
    out_display: Path,
    out_channels: Path,
) -> dict:
    ensure_dirs()
    stage = StageRecord(
        "06", "build-rivers", inputs=[raw_path, dem_path, state_path]
    )
    rivers_cfg = cfg.pipeline["rivers"]
    version = cfg.pipeline["dataset_version"]

    aoi = aoi_domain.build(cfg, dem_path, state_path)
    aoi_paths = aoi_domain.save(cfg, aoi)
    stage.out(aoi_paths["core"], aoi_paths["edge"], aoi_paths["clip"], aoi_paths["meta"])
    clip_geom = aoi.geometry("clip")
    print(
        f"[06] AOI v2 core {aoi.core_area_km2:,.1f} km² ({aoi.core_cells:,} cells); "
        f"clip +5 km {aoi.clip_area_km2:,.1f} km²"
    )

    raw = load_geojson(raw_path)
    source_record_path = raw_path.parent / "rivers-source.json"
    source_record = {}
    if source_record_path.exists():
        source_record = json.loads(source_record_path.read_text(encoding="utf-8"))
        stage.inputs.append(source_record_path)

    allowed = {str(value) for value in rivers_cfg["waterway_policy"]}
    min_length_m = float(rivers_cfg["min_length_m"])
    main_match = str(cfg.sources["rivers"]["main_stem_name_match"]).lower()

    candidates: list[dict] = []
    excluded = {
        "waterway": 0,
        "empty": 0,
        "midpoint_outside_clip": 0,
        "shorter_than_min": 0,
    }
    for raw_feature in raw.get("features", []):
        props = raw_feature.get("properties", {})
        waterway = str(props.get("waterway") or "river")
        if waterway not in allowed:
            excluded["waterway"] += 1
            continue
        name = props.get("name")
        source = str(props.get("source") or "osm")
        source_id = str(props.get("source_id") or "")
        river_id = str(props.get("river_id") or f"{source}:{source_id}")
        geom = valid(shape(raw_feature["geometry"]))
        if geom is None or geom.is_empty:
            excluded["empty"] += 1
            continue
        geom_proj = project_geom(geom, cfg.aoi.output_crs, cfg.aoi.analysis_crs)
        midpoint = geom_proj.interpolate(0.5, normalized=True)
        if not clip_geom.covers(midpoint):
            excluded["midpoint_outside_clip"] += 1
            continue
        clipped = valid(geom_proj.intersection(clip_geom))
        if clipped is None or clipped.is_empty:
            excluded["empty"] += 1
            continue
        length_km = geodesic_length_km(
            project_geom(clipped, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
        )
        if length_km * 1000.0 < min_length_m:
            excluded["shorter_than_min"] += 1
            continue
        is_main = bool(name) and main_match in str(name).lower()
        candidates.append(
            {
                "river_id": river_id,
                "name": name,
                "waterway": waterway,
                "source": source,
                "source_id": source_id,
                "geom": clipped,
                "length_km": length_km,
                "length_m": length_km * 1000.0,
                "order": 1 if is_main else 2,
            }
        )

    if not candidates:
        raise RuntimeError("stage 06: no waterway=river ways remain after AOI v2 clipping")
    main_items = [item for item in candidates if item["order"] == 1]
    if not main_items:
        raise RuntimeError(
            "stage 06: no Brahmaputra main-stem way matched after AOI v2 clipping; "
            "order-1 dilation would be undefined"
        )

    limit_share = float(rivers_cfg["max_channel_cell_share_of_aoi_v2"])
    limit_cells = int(limit_share * aoi.core_cells)
    main_width = int(cfg.pipeline["burn"]["main_stem_width_cells"])

    def channel_count(items: list[dict]) -> int:
        channel, _ = rasterize_channels(
            [item["geom"] for item in items],
            [item["geom"] for item in items if item["order"] == 1],
            aoi.transform,
            aoi.height,
            aoi.width,
            main_width,
        )
        return int(channel[aoi.core].sum())

    kept = list(candidates)
    pruned = 0
    prune_threshold_m = None
    channel_cells = channel_count(kept)
    if channel_cells > limit_cells:
        lengths = sorted(
            {round(item["length_m"], 3) for item in candidates if item["order"] != 1}
        )
        low, high = 0, len(lengths) - 1
        best_threshold = None
        best_cells = None
        while low <= high:
            middle = (low + high) // 2
            threshold = lengths[middle]
            trial = [
                item
                for item in candidates
                if item["order"] == 1 or item["length_m"] >= threshold - 1e-9
            ]
            trial_cells = channel_count(trial)
            if trial_cells <= limit_cells:
                best_threshold, best_cells = threshold, trial_cells
                high = middle - 1
            else:
                low = middle + 1
        if best_threshold is None:
            raise RuntimeError(
                f"stage 06: even the main stem alone gives {channel_cells:,} channel "
                f"cells, above the {limit_share:.1%} AOI v2 limit ({limit_cells:,} cells)"
            )
        kept = [
            item
            for item in candidates
            if item["order"] == 1 or item["length_m"] >= best_threshold - 1e-9
        ]
        pruned = len(candidates) - len(kept)
        prune_threshold_m = best_threshold
        channel_cells = best_cells if best_cells is not None else channel_count(kept)
        print(
            f"[06] channel gate: pruned {pruned} shortest ways below "
            f"{best_threshold:,.0f} m; {channel_cells:,} cells"
        )
    if channel_cells > limit_cells:
        raise RuntimeError(
            f"stage 06: channel cells inside AOI v2 {channel_cells:,} exceed the "
            f"{limit_share:.1%} limit ({limit_cells:,} cells)"
        )

    main_stem_count = sum(1 for item in kept if item["order"] == 1)
    total_length = sum(item["length_km"] for item in kept)
    if total_length <= float(rivers_cfg["total_channel_min_km"]):
        raise RuntimeError(
            f"stage 06: total channel length {total_length:.1f} km <= "
            f"{rivers_cfg['total_channel_min_km']} km"
        )

    def build(channel: bool, tolerance_m: float):
        features = []
        for item in kept:
            geom = item["geom"]
            if tolerance_m > 0:
                simplified = valid(geom.simplify(tolerance_m, preserve_topology=True))
                if simplified is not None and not simplified.is_empty:
                    geom = simplified
            geom_wgs = project_geom(geom, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
            label = (
                "River centreline (OSM/ODbL)"
                if item["source"] == "osm"
                else "River centreline (Natural Earth, public domain)"
            )
            props = {
                "river_id": item["river_id"],
                "name": item["name"],
                "waterway": item["waterway"],
                "order": int(item["order"]),
                "source": item["source"],
                "source_id": item["source_id"],
                "length_km": round(float(item["length_km"]), 4),
                "class": "source",
                "label": label,
            }
            if channel:
                props = {
                    "river_id": item["river_id"],
                    "name": item["name"],
                    "waterway": item["waterway"],
                    "order": int(item["order"]),
                    "length_km": round(float(item["length_km"]), 4),
                    "class": "source",
                }
            feat = feature(geom_wgs, props, cfg.aoi.decimals)
            if feat is not None:
                features.append(feat)
        features.sort(
            key=lambda f: (
                f["properties"].get("order", 0),
                f["properties"].get("river_id", ""),
                json.dumps(f["geometry"])[:120],
            )
        )
        return feature_collection(
            "Assam rivers — channel lines" if channel else "Assam mapped rivers",
            "source",
            features,
            version,
        )

    display_tolerance = float(rivers_cfg["display_simplify_m"])
    cap = int(
        cfg.pipeline["validation"]["file_caps_bytes"]["data/hydro/assam-rivers.geojson"]
    )
    display = build(False, display_tolerance)
    payload = json_bytes(display, indent=None)
    while len(payload) > cap and display_tolerance < 300:
        display_tolerance += 25
        print(f"[06] display layer over cap; simplifying at {display_tolerance:.0f} m")
        display = build(False, display_tolerance)
        payload = json_bytes(display, indent=None)
    if len(payload) > cap:
        raise RuntimeError(
            f"stage 06: rivers display layer {len(payload)} bytes exceeds cap {cap} at "
            f"{display_tolerance:.0f} m; the kept set must not be pruned for the display cap"
        )
    out_display.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(out_display, payload)

    channels = build(True, float(rivers_cfg["channel_simplify_m"]))
    channel_payload = json_bytes(channels, indent=None)
    out_channels.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(out_channels, channel_payload)

    for item in kept:
        if not item["geom"].is_valid:
            raise RuntimeError(f"stage 06: invalid channel geometry for {item['river_id']}")

    aoi.meta.update(
        {
            "channel_waterway_policy": sorted(allowed),
            "channel_candidate_way_count": len(candidates),
            "channel_kept_way_count": len(kept),
            "channel_pruned_way_count": pruned,
            "channel_prune_length_threshold_m": prune_threshold_m,
            "channel_cells_in_aoi_v2": channel_cells,
            "channel_cell_share_of_aoi_v2": round(channel_cells / aoi.core_cells, 9),
            "channel_cell_limit_share": limit_share,
            "channel_cells_limit": limit_cells,
            "channel_ways_excluded": excluded,
            "channel_ways_outside_clip": 0,
        }
    )
    atomic_write_json(aoi_paths["meta"], aoi.meta, indent=2, sort_keys=True)

    stage.out(out_display, out_channels)
    stage.metric("aoi_v2_core_area_km2", round(aoi.core_area_km2, 4))
    stage.metric("aoi_v2_edge_area_km2", round(aoi.edge_area_km2, 4))
    stage.metric("aoi_v2_clip_area_km2", round(aoi.clip_area_km2, 4))
    stage.metric("candidate_way_count", len(candidates))
    stage.metric("kept_way_count", len(kept))
    stage.metric("pruned_way_count", pruned)
    stage.metric("prune_length_threshold_m", prune_threshold_m)
    stage.metric("channel_cells_aoi_v2", channel_cells)
    stage.metric("channel_cell_share_aoi_v2", round(channel_cells / aoi.core_cells, 9))
    stage.metric("channel_cell_limit_share", limit_share)
    stage.metric("excluded_way_counts", excluded)
    stage.metric("total_length_km", round(total_length, 2))
    stage.metric("main_stem_count", main_stem_count)
    stage.metric("source_used", source_record.get("source_used"))
    stage.metric("display_simplify_m", display_tolerance)
    stage.metric("display_feature_count", len(display["features"]))
    stage.source(
        cfg.sources["rivers"]["name"],
        source_record.get("source_url", cfg.sources["rivers"]["overpass_url"]),
        source_record.get("licence", cfg.sources["rivers"]["licence_osm"]),
    )
    stage.finish(
        "REVIEW-02 A1/A2: AOI v2 = inside Assam and DEM <= 120 m (2 km edge buffer for "
        "continuity, not area); waterway=river only; clipped to AOI v2 + 5 km; midpoint "
        f"inside clip; clipped length >= {min_length_m:.0f} m; shortest ways pruned until "
        f"channel cells <= {limit_share:.1%} of AOI v2 ({pruned} pruned). Display shows "
        "the same kept set; only simplification increases to meet the 1.0 MB cap."
    )
    print(
        f"[06] ok: {len(kept)} river ways ({pruned} pruned), {total_length:.0f} km, "
        f"channel {channel_cells:,} cells = {channel_cells / aoi.core_cells:.2%} of AOI v2, "
        f"display {len(payload) / 1024:.0f} KB, channels {len(channel_payload) / 1024:.0f} KB"
    )
    return {
        "features": len(kept),
        "total_length_km": total_length,
        "channel_cells": channel_cells,
        "pruned": pruned,
    }
