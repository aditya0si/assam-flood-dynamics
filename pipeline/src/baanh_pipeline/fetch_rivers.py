"""Stage 03 — fetch river centrelines from Overpass, with the documented
Natural Earth 10m fallback.  The two sources are never mixed in one run.

The public endpoint rejects the single whole-AOI query when it is at capacity
(HTTP 502).  The stage first tries the exact whole-AOI query, then runs the same
query split into a configurable lon/lat grid, each cell cached separately.  This
preserves the documented query semantics and source; partial OSM results are
never mixed with the fallback.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from shapely.geometry import LineString, MultiLineString, shape

from .config import Config
from .geo import buffered_aoi, geodesic_length_km, project_geom
from .http import FetchError, fetch_bytes
from .util import StageRecord, atomic_write_json, ensure_dirs, json_bytes, relative, utc_now


def _overpass_query(bbox: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox
    return (
        '[out:json][timeout:180];'
        'way["waterway"~"^(river|stream|canal|drain)$"]'
        f"({south},{west},{north},{east});out geom;"
    )


def _overpass_features(payload: bytes, cfg: Config):
    data = json.loads(payload.decode("utf-8"))
    elements = data.get("elements", [])
    if not elements:
        raise RuntimeError("overpass response contains no elements")
    clip_geom = buffered_aoi(cfg.aoi, float(cfg.aoi.raw["rivers_clip_buffer_km"]))
    best: dict[str, tuple[float, dict]] = {}
    for element in elements:
        if element.get("type") != "way":
            continue
        geometry = element.get("geometry") or []
        tags = element.get("tags") or {}
        waterway = tags.get("waterway")
        if waterway not in ("river", "stream", "canal", "drain"):
            continue
        coords = [(float(p["lon"]), float(p["lat"])) for p in geometry if "lon" in p and "lat" in p]
        if len(coords) < 2:
            continue
        line = LineString(coords)
        if line.length <= 0:
            continue
        projected = project_geom(line, cfg.aoi.output_crs, cfg.aoi.analysis_crs)
        clipped = projected.intersection(clip_geom)
        if clipped.is_empty:
            continue
        clipped_wgs = project_geom(clipped, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
        parts = []
        if isinstance(clipped_wgs, LineString):
            parts = [clipped_wgs]
        elif isinstance(clipped_wgs, MultiLineString):
            parts = list(clipped_wgs.geoms)
        for part in parts:
            if len(part.coords) < 2 or part.length <= 0:
                continue
            osm_id = str(element.get("id"))
            river_id = f"osm:way/{osm_id}"
            length = geodesic_length_km(part)
            candidate = {
                "type": "Feature",
                "properties": {
                    "river_id": river_id,
                    "source_id": osm_id,
                    "name": tags.get("name"),
                    "waterway": waterway,
                    "source": "osm",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[float(x), float(y)] for x, y in part.coords],
                },
            }
            existing = best.get(river_id)
            if existing is None or length > existing[0]:
                best[river_id] = (length, candidate)
    return [item[1] for item in best.values()]


def _natural_earth_features(payload: bytes, cfg: Config):
    data = json.loads(payload.decode("utf-8"))
    clip_geom = buffered_aoi(cfg.aoi, float(cfg.aoi.raw["rivers_clip_buffer_km"]))
    features = []
    for index, feature in enumerate(data.get("features", [])):
        props = feature.get("properties") or {}
        feature_class = props.get("featurecla") or ""
        if feature_class != "River":
            continue
        geometry = feature.get("geometry")
        if not geometry or not geometry.get("coordinates"):
            continue
        geom = shape(geometry)
        if geom.is_empty:
            continue
        projected = project_geom(geom, cfg.aoi.output_crs, cfg.aoi.analysis_crs)
        clipped = projected.intersection(clip_geom)
        if clipped.is_empty:
            continue
        clipped_wgs = project_geom(clipped, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
        parts = []
        if isinstance(clipped_wgs, LineString):
            parts = [clipped_wgs]
        elif isinstance(clipped_wgs, MultiLineString):
            parts = list(clipped_wgs.geoms)
        for part_index, part in enumerate(parts):
            if len(part.coords) < 2 or part.length <= 0:
                continue
            native_id = props.get("rivernum")
            if native_id is None:
                native_id = f"{index}-{part_index}"
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "river_id": f"ne:{native_id}-{part_index}",
                        "source_id": str(native_id),
                        "name": props.get("name"),
                        "waterway": "river",
                        "source": "natural-earth",
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[float(x), float(y)] for x, y in part.coords],
                    },
                }
            )
    return features


def _split_bboxes(bbox: tuple[float, float, float, float], lon_step: float, lat_step: float):
    west, south, east, north = bbox
    boxes = []
    lat = south
    while lat < north - 1e-9:
        lon = west
        while lon < east - 1e-9:
            boxes.append(
                (
                    round(lon, 6),
                    round(lat, 6),
                    round(min(lon + lon_step, east), 6),
                    round(min(lat + lat_step, north), 6),
                )
            )
            lon += lon_step
        lat += lat_step
    return boxes


def run(cfg: Config, cache: Path, overpass_timeout: int = 180, refresh: bool = False) -> dict:
    ensure_dirs()
    stage = StageRecord("03", "fetch-rivers")
    rivers_cfg = cfg.sources["rivers"]
    grid_cfg = cfg.pipeline["rivers"]
    cache = cache if cache.is_absolute() else cfg.root / cache
    cache.mkdir(parents=True, exist_ok=True)

    overpass_path = cache / "overpass-rivers.json"
    raw_geojson_path = cache / "rivers-raw.geojson"
    source_path = cache / "rivers-source.json"

    attempts = 0
    fallback_reason = None
    source_used = None
    features: list[dict] = []
    raw_payload = b""
    source_url = rivers_cfg["overpass_url"]
    licence = rivers_cfg["licence_osm"]
    fetched_at = utc_now()
    split_cells = 0
    skipped_cells = 0
    query_mode = "whole-aoi"

    if overpass_path.exists() and not refresh:
        try:
            features = _overpass_features(overpass_path.read_bytes(), cfg)
            if features:
                source_used = "osm"
                raw_payload = overpass_path.read_bytes()
                fetched_at = "cache"
        except Exception:
            features = []

    if not features:
        last_error = ""
        split_dir_existing = cache / "overpass-split"
        resume_split = split_dir_existing.exists() and any(split_dir_existing.glob("*.json"))
        # 1) Exact whole-AOI query, one attempt on the documented endpoint.
        try:
            if resume_split:
                raise RuntimeError("resuming a previously started split-grid fetch")
            attempts += 1
            result = fetch_bytes(
                cfg,
                rivers_cfg["overpass_url"],
                overpass_path,
                refresh=True,
                method="POST",
                data={"data": _overpass_query(cfg.aoi.bbox)},
                timeout_s=float(overpass_timeout),
                retries=1,
                accept="application/json",
            )
            raw_payload = result.payload
            features = _overpass_features(raw_payload, cfg)
            if not features:
                raise RuntimeError("whole-AOI Overpass query returned zero usable river ways")
            source_used = "osm"
            fetched_at = result.fetched_at
            print(f"[03] whole-AOI Overpass query succeeded: {len(features)} features")
        except (FetchError, RuntimeError, ValueError, KeyError) as exc:
            last_error = str(exc)
            features = []
            print(f"[03] whole-AOI query failed ({last_error[:180]}); trying split grid")

        # 2) Same query split into lon/lat cells. Each successful cell is cached.
        if not features:
            boxes = _split_bboxes(
                cfg.aoi.bbox,
                float(grid_cfg["overpass_grid_lon_deg"]),
                float(grid_cfg["overpass_grid_lat_deg"]),
            )
            split_cells = len(boxes)
            split_dir = cache / "overpass-split"
            split_dir.mkdir(parents=True, exist_ok=True)
            # Channels farther than the HAND search limit from Assam cannot
            # affect any output cell.  Skip grid cells that are entirely
            # outside the state + 12 km + 5 km clip buffer.
            skipped_cells = 0
            state_path = cfg.root / "public" / "data" / "admin" / "assam-state.geojson"
            if state_path.exists():
                from shapely.geometry import box

                from .geo import load_geojson

                state_doc = load_geojson(state_path)
                state_geoms = [shape(f["geometry"]) for f in state_doc.get("features", [])]
                if state_geoms:
                    from shapely.ops import unary_union

                    buffer_m = float(cfg.aoi.max_channel_distance_m) + float(
                        cfg.aoi.raw["rivers_clip_buffer_km"]
                    ) * 1000.0
                    needed = project_geom(
                        unary_union(state_geoms),
                        cfg.aoi.output_crs,
                        cfg.aoi.analysis_crs,
                    ).buffer(buffer_m)
                    required_boxes = []
                    for index, bbox in boxes:
                        bbox_utm = project_geom(
                            box(*bbox), cfg.aoi.output_crs, cfg.aoi.analysis_crs
                        )
                        if bbox_utm.intersects(needed):
                            required_boxes.append((index, bbox))
                    skipped_cells = len(boxes) - len(required_boxes)
                    boxes = required_boxes
                    print(
                        f"[03] {len(boxes)}/{len(boxes) + skipped_cells} split cells intersect "
                        f"the Assam + {buffer_m / 1000:.0f} km buffer; {skipped_cells} skipped"
                    )
            merged_elements: list[dict] = []
            cell_attempts = int(grid_cfg["overpass_cell_attempts"])
            max_passes = int(grid_cfg["overpass_passes"])
            pending = list(enumerate(boxes))
            pass_number = 0
            while pending and pass_number < max_passes:
                pass_number += 1
                next_pending = []
                for index, bbox in pending:
                    cell_path = split_dir / f"{index:03d}.json"
                    cell_elements = None
                    if cell_path.exists() and not refresh:
                        try:
                            cached = json.loads(cell_path.read_text(encoding="utf-8"))
                            cell_elements = cached.get("elements", [])
                        except Exception:
                            cell_elements = None
                    if cell_elements is None:
                        query = _overpass_query(bbox)
                        for cell_attempt in range(1, cell_attempts + 1):
                            attempts += 1
                            try:
                                result = fetch_bytes(
                                    cfg,
                                    rivers_cfg["overpass_url"],
                                    cell_path,
                                    refresh=True,
                                    method="POST",
                                    data={"data": query},
                                    timeout_s=float(overpass_timeout),
                                    retries=1,
                                    accept="application/json",
                                )
                                cell_payload = json.loads(result.payload.decode("utf-8"))
                                cell_elements = cell_payload.get("elements", [])
                                break
                            except (FetchError, ValueError, KeyError) as exc:
                                last_error = str(exc)
                                if cell_attempt < cell_attempts:
                                    delay = min(60, 5 * (2 ** (cell_attempt - 1)))
                                    print(
                                        f"[03] cell {index + 1}/{len(boxes)} pass {pass_number} "
                                        f"attempt {cell_attempt}/{cell_attempts} failed; retrying in {delay}s"
                                    )
                                    time.sleep(delay)
                    if cell_elements is None:
                        next_pending.append((index, bbox))
                        print(f"[03] cell {index + 1}/{len(boxes)} queued for a later pass")
                    else:
                        merged_elements.extend(cell_elements)
                        print(
                            f"[03] cell {index + 1}/{len(boxes)} ok "
                            f"({len(cell_elements)} elements, {len(merged_elements)} total)"
                        )
                pending = next_pending
                if pending and pass_number < max_passes:
                    wait = min(90, 15 * pass_number)
                    print(
                        f"[03] {len(pending)} cell(s) still pending after pass {pass_number}; "
                        f"waiting {wait}s before pass {pass_number + 1}"
                    )
                    time.sleep(wait)
            failed_cells = pending
            if not failed_cells and merged_elements:
                merged = json.dumps({"elements": merged_elements}, separators=(",", ":"))
                raw_payload = merged.encode("utf-8")
                try:
                    features = _overpass_features(raw_payload, cfg)
                except Exception as exc:
                    last_error = str(exc)
                    features = []
                if features:
                    source_used = "osm"
                    fetched_at = utc_now()
                    query_mode = "split-grid"
                    print(f"[03] split-grid Overpass query succeeded: {len(features)} features")
            if not features:
                fallback_reason = (
                    f"whole-AOI and split-grid Overpass queries failed after {attempts} attempts; "
                    f"last error: {last_error}"
                )

        # 3) Documented fallback.
        if not features:
            ne_path = cache / "ne_10m_rivers_lake_centerlines.geojson"
            try:
                ne_result = fetch_bytes(
                    cfg, rivers_cfg["fallback_url"], ne_path, refresh=refresh, timeout_s=120
                )
            except FetchError as exc:
                raise RuntimeError(
                    f"stage 03: Overpass failed ({fallback_reason}); Natural Earth fallback also failed: {exc}"
                ) from exc
            raw_payload = ne_result.payload
            features = _natural_earth_features(raw_payload, cfg)
            if not features:
                raise RuntimeError("stage 03: Natural Earth fallback yielded no river features in the AOI")
            source_used = "natural-earth"
            source_url = rivers_cfg["fallback_url"]
            licence = rivers_cfg["licence_fallback"]
            fetched_at = ne_result.fetched_at
            query_mode = "natural-earth"
            print(f"[03] fallback to Natural Earth: {len(features)} features")

    features.sort(key=lambda f: (f["properties"]["source"], f["properties"]["river_id"], f["properties"]["source_id"]))
    collection = {
        "type": "FeatureCollection",
        "name": "Baanh raw rivers",
        "schema_version": "1.0.0",
        "class": "source",
        "features": features,
    }
    payload = json_bytes(collection, indent=None)
    from .util import atomic_write_bytes

    atomic_write_bytes(raw_geojson_path, payload)

    total_length = sum(geodesic_length_km(LineString(f["geometry"]["coordinates"])) for f in features)
    source_record = {
        "schema_version": "1.0.0",
        "source_used": source_used,
        "attempts": attempts,
        "feature_count": len(features),
        "fetched_at": fetched_at,
        "fallback_reason": fallback_reason,
        "source_url": source_url,
        "licence": licence,
        "sha256": hashlib.sha256(raw_payload).hexdigest(),
        "bytes": len(raw_payload),
        "total_length_km": round(total_length, 2),
        "query_mode": query_mode,
        "split_cells": split_cells,
        "skipped_cells_outside_assam_buffer": skipped_cells,
        "query": _overpass_query(cfg.aoi.bbox) if source_used == "osm" else None,
    }
    atomic_write_json(source_path, source_record, indent=2, sort_keys=True)

    stage.out(raw_geojson_path, source_path)
    stage.metric("source_used", source_used)
    stage.metric("attempts", attempts)
    stage.metric("feature_count", len(features))
    stage.metric("total_length_km", round(total_length, 2))
    stage.metric("query_mode", query_mode)
    stage.metric("split_cells", split_cells)
    stage.metric("skipped_cells", skipped_cells)
    stage.metric("fallback_reason", fallback_reason)
    stage.source(
        rivers_cfg["name"] if source_used == "osm" else rivers_cfg["fallback_name"],
        source_url,
        licence,
    )
    notes = (
        f"Overpass response cached verbatim ({query_mode})."
        if source_used == "osm"
        else f"Overpass failed; documented Natural Earth fallback used. Reason: {fallback_reason}"
    )
    stage.finish(notes)

    print(
        f"[03] ok: {len(features)} features from {source_used} ({query_mode}), "
        f"{total_length:,.0f} km, {len(payload) / 1024 / 1024:.2f} MB raw"
    )
    return source_record
