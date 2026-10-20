"""Stage 06 — clip/classify river centrelines and create burn channel lines."""
from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import LineString, MultiLineString, shape

from .config import Config
from .geo import (
    feature,
    feature_collection,
    geodesic_length_km,
    load_geojson,
    project_geom,
    valid,
)
from .util import StageRecord, atomic_write_json, ensure_dirs


def _parts(geom) -> list[LineString]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, LineString)]


def _order(waterway: str, name: str | None, main_match: str) -> int:
    if name and main_match in name.lower():
        return 1
    if waterway == "river" and name:
        return 2
    if waterway == "river":
        return 3
    if waterway == "stream":
        return 4
    return 5


def run(cfg: Config, raw_path: Path, out_display: Path, out_channels: Path) -> dict:
    ensure_dirs()
    stage = StageRecord("06", "build-rivers", inputs=[raw_path])
    rivers_cfg = cfg.pipeline["rivers"]
    version = cfg.pipeline["dataset_version"]
    raw = load_geojson(raw_path)
    source_record_path = raw_path.parent / "rivers-source.json"
    source_record = {}
    if source_record_path.exists():
        source_record = json.loads(source_record_path.read_text(encoding="utf-8"))
        stage.inputs.append(source_record_path)

    buffer_km = float(cfg.aoi.raw["rivers_clip_buffer_km"])
    from .geo import project_geom as pg
    from shapely.geometry import box

    clip_geom = pg(box(*cfg.aoi.bbox), cfg.aoi.output_crs, cfg.aoi.analysis_crs).buffer(buffer_km * 1000.0)
    min_length = float(rivers_cfg["min_length_m"])
    main_match = str(cfg.sources["rivers"]["main_stem_name_match"]).lower()

    items = []
    for raw_feature in raw.get("features", []):
        props = raw_feature.get("properties", {})
        waterway = str(props.get("waterway") or "river")
        name = props.get("name")
        source = str(props.get("source") or "osm")
        source_id = str(props.get("source_id") or "")
        river_id = str(props.get("river_id") or f"{source}:{source_id}")
        geom = shape(raw_feature["geometry"])
        geom = valid(geom)
        if geom is None or geom.is_empty:
            continue
        geom_proj = project_geom(geom, cfg.aoi.output_crs, cfg.aoi.analysis_crs)
        clipped = geom_proj.intersection(clip_geom)
        if clipped.is_empty:
            continue
        length_km = geodesic_length_km(
            project_geom(clipped, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
        )
        if length_km * 1000.0 < min_length:
            continue
        items.append(
            {
                "river_id": river_id,
                "name": name,
                "waterway": waterway,
                "source": source,
                "source_id": source_id,
                "geom": clipped,
                "length_km": length_km,
                "order": _order(waterway, name, main_match),
            }
        )

    if not items:
        raise RuntimeError("stage 06: no river lines remain after clipping")
    if not any(item["order"] == 1 for item in items):
        longest = max(items, key=lambda item: item["length_km"])
        longest["order"] = 1
        print(f"[06] no name match for main stem; longest river promoted: {longest['name']!r}")

    def build(
        collection,
        tolerance_m: float,
        channel: bool,
        river_only: bool = False,
        named_only: bool = False,
    ):
        features = []
        for item in items:
            if river_only and item["waterway"] != "river":
                continue
            if named_only and not item["name"]:
                continue
            geom = item["geom"]
            if tolerance_m > 0:
                simplified = geom.simplify(tolerance_m, preserve_topology=True)
                simplified = valid(simplified)
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
                "class": "source",
                "label": label,
            }
            if channel:
                props = {
                    "river_id": item["river_id"],
                    "order": int(item["order"]),
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
    cap = int(cfg.pipeline["validation"]["file_caps_bytes"]["data/hydro/assam-rivers.geojson"])
    from .util import json_bytes

    river_only = False
    named_only = False
    display = build("display", display_tolerance, False, river_only, named_only)
    payload = json_bytes(display, indent=None)
    if len(payload) > cap:
        # The 1.0 MB cap is hard.  The river/stream/canal/drain channel layer
        # keeps every way for the burn and HAND; the display layer falls back
        # to mapped rivers, then to named rivers, then simplifies more.
        river_only = True
        display = build("display", display_tolerance, False, river_only, named_only)
        payload = json_bytes(display, indent=None)
        print("[06] display layer over cap; dropping streams/canals/drains from display")
    if len(payload) > cap:
        named_only = True
        display_tolerance = float(rivers_cfg["display_simplify_m"])
        display = build("display", display_tolerance, False, river_only, named_only)
        payload = json_bytes(display, indent=None)
        print("[06] display layer still over cap; keeping named rivers only")
    while len(payload) > cap and display_tolerance < 300:
        display_tolerance += 50
        print(f"[06] display layer over cap; simplifying at {display_tolerance:.0f} m")
        display = build("display", display_tolerance, False, river_only, named_only)
        payload = json_bytes(display, indent=None)
    if len(payload) > cap:
        raise RuntimeError(
            f"stage 06: rivers display layer {len(payload)} bytes exceeds cap {cap} at "
            f"{display_tolerance:.0f} m (river-only={river_only}, named-only={named_only})"
        )
    out_display.parent.mkdir(parents=True, exist_ok=True)
    from .util import atomic_write_bytes

    atomic_write_bytes(out_display, payload)

    channels = build("channels", float(rivers_cfg["channel_simplify_m"]), True)
    channel_payload = json_bytes(channels, indent=None)
    out_channels.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(out_channels, channel_payload)

    total_length = sum(item["length_km"] for item in items)
    if total_length <= float(rivers_cfg["total_channel_min_km"]):
        raise RuntimeError(
            f"stage 06: total channel length {total_length:.1f} km <= "
            f"{rivers_cfg['total_channel_min_km']} km"
        )
    if not any(item["order"] == 1 for item in items):
        raise RuntimeError("stage 06: no order-1 main-stem line")
    for item in items:
        if not item["geom"].is_valid:
            raise RuntimeError(f"stage 06: invalid channel geometry for {item['river_id']}")

    stage.out(out_display, out_channels)
    stage.metric("feature_count", len(items))
    stage.metric("total_length_km", round(total_length, 2))
    stage.metric("main_stem_count", sum(1 for item in items if item["order"] == 1))
    stage.metric("source_used", source_record.get("source_used"))
    stage.metric("display_simplify_m", display_tolerance)
    stage.metric("display_river_only", river_only)
    stage.metric("display_named_only", named_only)
    stage.metric("display_feature_count", len(display["features"]))
    stage.source(
        cfg.sources["rivers"]["name"],
        source_record.get("source_url", cfg.sources["rivers"]["overpass_url"]),
        source_record.get("licence", cfg.sources["rivers"]["licence_osm"]),
    )
    stage.finish(
        "Clipped to AOI + 5 km, lines <500 m dropped, order by name/waterway heuristic, "
        f"display simplify {display_tolerance:.0f} m, channel simplify "
        f"{rivers_cfg['channel_simplify_m']} m."
    )
    print(
        f"[06] ok: {len(items)} lines, {total_length:.0f} km, display "
        f"{len(payload) / 1024:.0f} KB, channels {len(channel_payload) / 1024:.0f} KB"
    )
    return {"features": len(items), "total_length_km": total_length}
