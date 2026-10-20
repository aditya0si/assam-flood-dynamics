"""Stage 13 (P1) — virtual gauges on mapped rivers with the synthetic stage."""
from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import LineString, MultiLineString, shape

from .config import Config
from .geo import feature, feature_collection, geodesic_length_km, load_geojson
from .util import StageRecord, atomic_write_json, ensure_dirs, utc_now


def _lines(geom) -> list[LineString]:
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    return []


def run(cfg: Config, rivers_path: Path, summary_path: Path, out_path: Path) -> dict:
    ensure_dirs()
    stage = StageRecord("13", "build-gauges", inputs=[rivers_path, summary_path])
    scenario = cfg.scenario
    version = cfg.pipeline["dataset_version"]
    rivers = load_geojson(rivers_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    stages = [float(step["stage_m"]) for step in summary["steps"]]
    if len(stages) != 12:
        raise RuntimeError("stage 13: flood summary does not have 12 stages")

    main = []
    tributaries = []
    for feature_item in rivers.get("features", []):
        props = feature_item["properties"]
        geom = shape(feature_item["geometry"])
        length = sum(geodesic_length_km(line) for line in _lines(geom))
        entry = (length, props, geom)
        if int(props.get("order", 0)) == 1:
            main.append(entry)
        elif int(props.get("order", 0)) == 2:
            tributaries.append(entry)
    main.sort(key=lambda item: -item[0])
    tributaries.sort(key=lambda item: -item[0])
    if not main:
        raise RuntimeError("stage 13: no main-stem river to place gauges on")

    selected: list[tuple[str, str | None, float, float]] = []
    fractions = [0.12, 0.28, 0.44, 0.60, 0.76, 0.90]
    main_line = max(_lines(main[0][2]), key=lambda line: line.length)
    for fraction in fractions:
        point = main_line.interpolate(fraction, normalized=True)
        selected.append((main[0][1].get("river_id"), main[0][1].get("name"), point.x, point.y))
    for length, props, geom in tributaries[:2]:
        line = max(_lines(geom), key=lambda item: item.length)
        point = line.interpolate(0.55, normalized=True)
        selected.append((props.get("river_id"), props.get("name"), point.x, point.y))
    while len(selected) < 6 and tributaries:
        # One extra midpoint on the longest tributary if fewer than six points.
        length, props, geom = tributaries[0]
        line = max(_lines(geom), key=lambda item: item.length)
        for fraction in (0.3, 0.7):
            point = line.interpolate(fraction, normalized=True)
            selected.append((props.get("river_id"), props.get("name"), point.x, point.y))
            if len(selected) >= 6:
                break
    selected = selected[:8]
    if len(selected) < 6:
        raise RuntimeError(f"stage 13: only {len(selected)} gauge points could be placed")

    features = []
    for index, (river_id, river_name, lon, lat) in enumerate(selected, start=1):
        props = {
            "gauge_id": f"VG-{index:02d}",
            "label": f"Virtual gauge VG-{index:02d} (synthetic)",
            "river_name": river_name,
            "river_id": river_id,
            "lon": round(lon, 5),
            "lat": round(lat, 5),
            "stage_series_m": [round(value, 3) for value in stages],
            "peak_step": scenario.peak_step,
            "class": "synthetic",
            "note": "No agency, station code, datum, or measurement.",
        }
        item = feature(__import__("shapely.geometry", fromlist=["Point"]).Point(lon, lat), props, cfg.aoi.decimals)
        if item is not None:
            features.append(item)

    collection = feature_collection("Virtual gauges (synthetic)", "synthetic", features, version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_path, collection, indent=None)
    cap = int(cfg.pipeline["validation"]["file_caps_bytes"]["data/gauges/virtual-gauges.geojson"])
    if out_path.stat().st_size > cap:
        raise RuntimeError(
            f"stage 13: virtual gauges {out_path.stat().st_size} bytes exceed cap {cap}"
        )
    for item in features:
        if len(item["properties"]["stage_series_m"]) != 12:
            raise RuntimeError("stage 13: a gauge does not have 12 stage values")
        if "synthetic" not in item["properties"]["label"].lower():
            raise RuntimeError("stage 13: a gauge label does not say synthetic")

    stage.out(out_path)
    stage.metric("gauge_count", len(features))
    stage.metric("main_stem_gauges", len(fractions))
    stage.metric("tributary_gauges", max(0, len(features) - len(fractions)))
    stage.finish(
        "Stations are points on mapped river vertices; the stage series is copied "
        "from the synthetic scenario with no local variation, agency, code or datum."
    )
    print(f"[13] ok: {len(features)} virtual gauges, {out_path.stat().st_size} bytes")
    return {"gauge_count": len(features)}
