"""Stage 02 — fetch geoBoundaries ADM2 and select Assam districts.

The current geoBoundaries IND/ADM2 release has an empty ``shapeISO`` and no
state-name field, so the spec's ADM2-only filter is not usable as written.  The
same source's ADM1 Assam polygon is downloaded as a filter geometry and ADM2
features are selected by overlap / representative point.  The deviation is
recorded in source-meta.json and provenance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from shapely.geometry import shape

from .config import Config
from .geo import valid
from .http import FetchError, fetch_bytes
from .util import StageRecord, atomic_write_json, ensure_dirs, json_bytes, relative, utc_now


def _polygon_only(geometry: dict) -> bool:
    return geometry.get("type") in ("Polygon", "MultiPolygon")


def run(cfg: Config, cache: Path, refresh: bool = False) -> dict:
    ensure_dirs()
    stage = StageRecord("02", "fetch-boundaries")
    boundaries = cfg.sources["boundaries"]
    cache = cache if cache.is_absolute() else cfg.root / cache
    cache.mkdir(parents=True, exist_ok=True)

    api_path = cache / "api-adm2.json"
    api_payload = fetch_bytes(cfg, boundaries["api_url"], api_path, refresh=refresh)
    api = json.loads(api_payload.payload.decode("utf-8"))
    gj_url = api.get("gjDownloadURL")
    if not gj_url:
        raise RuntimeError("stage 02: geoBoundaries ADM2 API response has no gjDownloadURL")

    raw_path = cache / "geoboundaries-ind-adm2-full.json"
    raw_payload = fetch_bytes(cfg, gj_url, raw_path, refresh=refresh)
    raw_geojson = json.loads(raw_payload.payload.decode("utf-8"))
    raw_features = raw_geojson.get("features", [])
    if not raw_features:
        raise RuntimeError("stage 02: ADM2 download contains no features")

    adm1_api_path = cache / "api-adm1.json"
    adm1_api_payload = fetch_bytes(
        cfg, boundaries["adm1_api_url"], adm1_api_path, refresh=refresh
    )
    adm1_api = json.loads(adm1_api_payload.payload.decode("utf-8"))
    adm1_url = adm1_api.get("gjDownloadURL")
    if not adm1_url:
        raise RuntimeError("stage 02: geoBoundaries ADM1 API response has no gjDownloadURL")
    adm1_raw_path = cache / "geoboundaries-ind-adm1-full.json"
    adm1_payload = fetch_bytes(cfg, adm1_url, adm1_raw_path, refresh=refresh)
    adm1_geojson = json.loads(adm1_payload.payload.decode("utf-8"))

    state_feature = None
    for feature in adm1_geojson.get("features", []):
        props = feature.get("properties", {})
        iso = (props.get("shapeISO") or "").upper()
        name = (props.get("shapeName") or "").strip().lower()
        if iso == boundaries["state_iso"].upper() or name == boundaries["state_name"].lower():
            state_feature = feature
            break
    if state_feature is None:
        raise RuntimeError("stage 02: geoBoundaries ADM1 has no Assam feature")
    state_geom = valid(shape(state_feature["geometry"]))
    if state_geom is None or state_geom.is_empty:
        raise RuntimeError("stage 02: Assam ADM1 filter geometry is empty")

    selected: list[dict] = []
    overlap_threshold = float(boundaries["overlap_threshold"])
    rejected_non_polygon = 0
    for feature in raw_features:
        geometry = feature.get("geometry") or {}
        if not _polygon_only(geometry):
            rejected_non_polygon += 1
            continue
        geom = valid(shape(geometry))
        if geom is None or geom.is_empty:
            continue
        if not geom.intersects(state_geom):
            continue
        intersection = geom.intersection(state_geom)
        overlap = intersection.area / geom.area if geom.area else 0.0
        representative = geom.representative_point()
        if overlap < overlap_threshold and not state_geom.contains(representative):
            continue
        props = feature.get("properties", {})
        selected.append(
            {
                "type": "Feature",
                "properties": {
                    "shapeID": props.get("shapeID"),
                    "shapeName": props.get("shapeName"),
                    "shapeISO": props.get("shapeISO") or "",
                },
                "geometry": geometry,
            }
        )

    if not selected:
        raise RuntimeError("stage 02: zero Assam features after spatial filter")
    if rejected_non_polygon:
        print(f"[02] ignored {rejected_non_polygon} non-polygon ADM2 features")

    selected.sort(key=lambda f: (f["properties"].get("shapeName") or ""))
    filtered = {
        "type": "FeatureCollection",
        "name": "geoBoundaries IND ADM2 — Assam selection",
        "features": selected,
    }
    filtered_path = cache / "geoboundaries-ind-adm2.json"
    payload = json_bytes(filtered, indent=2, sort_keys=True)
    from .util import atomic_write_bytes

    atomic_write_bytes(filtered_path, payload)

    meta = {
        "schema_version": "1.0.0",
        "source": boundaries["name"],
        "api_url": boundaries["api_url"],
        "download_url": gj_url,
        "last_updated": api.get("sourceDataUpdateDate"),
        "build_date": api.get("buildDate"),
        "licence": api.get("boundaryLicense"),
        "licence_detail": api.get("licenseDetail"),
        "attribution": api.get("boundarySource"),
        "feature_count": len(raw_features),
        "assam_feature_count": len(selected),
        "sha256_full_download": hashlib.sha256(raw_payload.payload).hexdigest(),
        "size_full_download": len(raw_payload.payload),
        "filter_method": (
            "ADM2 features retained when >50% of the polygon overlaps the "
            "geoBoundaries ADM1 Assam polygon or the representative point is "
            "inside it; ADM2 shapeISO is empty in this release."
        ),
        "adm1_filter": {
            "api_url": boundaries["adm1_api_url"],
            "download_url": adm1_url,
            "shape_id": state_feature["properties"].get("shapeID"),
            "shape_iso": state_feature["properties"].get("shapeISO"),
            "shape_name": state_feature["properties"].get("shapeName"),
            "licence": adm1_api.get("boundaryLicense"),
            "sha256_full_download": hashlib.sha256(adm1_payload.payload).hexdigest(),
        },
        "fetched_at": utc_now(),
        "cached_files": [relative(filtered_path), relative(raw_path), relative(adm1_raw_path)],
    }
    meta_path = cache / "source-meta.json"
    atomic_write_json(meta_path, meta, indent=2, sort_keys=True)

    stage.out(filtered_path, meta_path)
    stage.metric("feature_count", len(raw_features))
    stage.metric("assam_feature_count", len(selected))
    stage.metric("sha256_full_download", meta["sha256_full_download"])
    stage.source(
        boundaries["name"], gj_url, str(api.get("boundaryLicense") or "unknown")
    )
    stage.source(
        "geoBoundaries ADM1 Assam filter geometry",
        adm1_url,
        str(adm1_api.get("boundaryLicense") or "unknown"),
    )
    stage.finish(
        "ADM2 shapeISO empty; spatial filter against geoBoundaries ADM1 Assam. "
        "The ADM1 layer is a filter geometry only and is not a committed dataset."
    )

    print(
        f"[02] ok: {len(selected)} Assam ADM2 features of {len(raw_features)} "
        f"({len(payload) / 1024 / 1024:.1f} MB filtered)"
    )
    return meta
