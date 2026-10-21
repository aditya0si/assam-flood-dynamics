"""Stage 12 (P1) — OSM facility exposure join. Optional layer."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from shapely.geometry import Point, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .config import Config
from .geo import feature, feature_collection, load_geojson, project_coords
from .http import FetchError, fetch_bytes
from .util import StageRecord, atomic_write_json, ensure_dirs


QUERY = (
    '[out:json][timeout:180];'
    '(node["amenity"~"^(hospital|clinic|school)$"](23.95,89.55,28.15,96.15););'
    "out body;"
)


def _exposure(peak: float | None) -> str:
    if peak is None or peak < 0.1:
        return "none"
    if peak < 1.0:
        return "minor"
    if peak < 3.0:
        return "moderate"
    return "major"


def run(
    cfg: Config,
    masks_dir: Path,
    hand_path: Path,
    frame_index_path: Path,
    districts_path: Path,
    out_path: Path,
    refresh: bool = False,
) -> dict | None:
    ensure_dirs()
    stage = StageRecord(
        "12", "build-assets", inputs=[masks_dir, hand_path, frame_index_path, districts_path]
    )
    cache = cfg.root / "pipeline" / "cache" / "assets"
    cache.mkdir(parents=True, exist_ok=True)
    raw_path = cache / "overpass-facilities.json"

    try:
        result = fetch_bytes(
            cfg,
            cfg.sources["rivers"]["overpass_url"],
            raw_path,
            refresh=True,
            method="POST",
            data={"data": QUERY},
            timeout_s=180,
            retries=1,
            accept="application/json",
        )
        payload = json.loads(result.payload.decode("utf-8"))
        elements = payload.get("elements", [])
        if not elements:
            raise RuntimeError("Overpass returned zero facilities")
    except (FetchError, RuntimeError, ValueError, KeyError) as exc:
        print(f"[12] optional facility layer omitted: {exc}")
        if out_path.exists():
            out_path.unlink()
        stage.status = "skipped"
        stage.finish(
            f"Optional P1 facility layer omitted: Overpass unavailable ({exc}). "
            "M0/M1 still pass without assets; no hand-built facility list is used."
        )
        return None

    districts = load_geojson(districts_path)
    district_geoms = []
    district_ids = []
    for feature_item in districts.get("features", []):
        district_geoms.append(shape(feature_item["geometry"]))
        district_ids.append(feature_item["properties"]["district_id"])
    tree = STRtree(district_geoms)
    state = unary_union(district_geoms)

    with rasterio.open(hand_path) as src:
        transform = src.transform
        height, width = src.height, src.width
        hand = src.read(1)
        hand_nodata = float(src.nodata if src.nodata is not None else cfg.aoi.nodata)
    step_count = int(cfg.scenario.step_count)
    mask_paths = [masks_dir / f"step-{index:02d}-wet.tif" for index in range(step_count)]
    missing_masks = [path for path in mask_paths if not path.exists()]
    if missing_masks:
        raise RuntimeError(
            "stage 12: per-step wet masks are missing; re-run stage 09 "
            f"({', '.join(path.name for path in missing_masks[:3])})"
        )

    candidates = []
    for element in elements:
        if element.get("type") != "node" or "lat" not in element or "lon" not in element:
            continue
        lon = float(element["lon"])
        lat = float(element["lat"])
        point = Point(lon, lat)
        if not state.contains(point):
            continue
        tags = element.get("tags") or {}
        amenity = tags.get("amenity")
        if amenity not in ("hospital", "clinic", "school"):
            continue
        ux, uy = project_coords([(lon, lat)], cfg.aoi.output_crs, cfg.aoi.analysis_crs)[0]
        col, row = ~transform * (ux, uy)
        col = int(np.floor(col))
        row = int(np.floor(row))
        if row < 0 or col < 0 or row >= height or col >= width:
            continue
        candidates.append(
            {
                "element": element,
                "point": point,
                "lon": lon,
                "lat": lat,
                "row": row,
                "col": col,
                "amenity": amenity,
                "tags": tags,
            }
        )

    if not candidates:
        print("[12] optional facility layer omitted: no facilities inside Assam")
        if out_path.exists():
            out_path.unlink()
        stage.status = "skipped"
        stage.finish("Optional P1 facility layer omitted: no OSM facilities inside Assam.")
        return None

    rows = np.array([c["row"] for c in candidates])
    cols = np.array([c["col"] for c in candidates])
    series = np.zeros((step_count, len(candidates)), dtype=np.float32)
    hand_values = hand[rows, cols]
    for step in range(step_count):
        stage_m = float(cfg.scenario.steps[step]["stage_m"])
        with rasterio.open(mask_paths[step]) as src:
            wet = src.read(1)[rows, cols] > 0
        series[step] = np.where(wet, stage_m - hand_values, 0.0)
        series[step][hand_values == hand_nodata] = 0.0

    features = []
    for index, candidate in enumerate(candidates):
        values = series[:, index]
        first_step = None
        for step, value in enumerate(values):
            if value > 0:
                first_step = step
                break
        peak = float(values.max()) if values.size else None
        district_id = None
        matches = tree.query(candidate["point"])
        for match in matches:
            if district_geoms[int(match)].contains(candidate["point"]):
                district_id = district_ids[int(match)]
                break
        name = candidate["tags"].get("name")
        props = {
            "osm_id": f"node/{candidate['element']['id']}",
            "facility": candidate["amenity"],
            "name": name,
            "district_id": district_id,
            "lon": round(candidate["lon"], 5),
            "lat": round(candidate["lat"], 5),
            "peak_depth_m": round(peak, 3) if peak is not None else None,
            "first_step": first_step,
            "exposure_class": _exposure(peak),
            "class": "source",
            "derived_fields": ["peak_depth_m", "first_step", "exposure_class"],
            "completeness": "incomplete-osm",
            "label": "OSM facility (source); exposure derived from scenario",
        }
        item = feature(candidate["point"], props, cfg.aoi.decimals)
        if item is not None:
            features.append(item)

    features.sort(key=lambda item: (item["properties"]["facility"], item["properties"]["osm_id"]))
    collection = feature_collection(
        "OSM facilities with scenario depth exposure",
        "source",
        features,
        cfg.pipeline["dataset_version"],
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_path, collection, indent=None)
    cap = int(
        cfg.pipeline["validation"]["file_caps_bytes"]["data/assets/critical-facilities.geojson"]
    )
    if out_path.stat().st_size > cap:
        raise RuntimeError(
            f"stage 12: facilities {out_path.stat().st_size} bytes exceed cap {cap}"
        )
    stage.out(out_path)
    stage.metric("facility_count", len(features))
    stage.metric("hospital", sum(1 for f in features if f["properties"]["facility"] == "hospital"))
    stage.metric("clinic", sum(1 for f in features if f["properties"]["facility"] == "clinic"))
    stage.metric("school", sum(1 for f in features if f["properties"]["facility"] == "school"))
    stage.source(
        "OpenStreetMap Overpass facilities",
        cfg.sources["rivers"]["overpass_url"],
        "ODbL 1.0 (OpenStreetMap contributors)",
    )
    stage.finish(
        "OSM points inside Assam; depth sampled from the stage-09 per-step uint8 wet "
        "masks and HAND (no float stack); completeness unknown (incomplete-osm); no "
        "capacity, staff or operational status inferred."
    )
    print(f"[12] ok: {len(features)} facilities, {out_path.stat().st_size / 1024:.0f} KB")
    return {"facility_count": len(features)}
