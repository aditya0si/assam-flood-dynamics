"""Stage 05 — build district and dissolved state administrative layers."""
from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import shape

from .config import Config
from .geo import (
    feature,
    feature_collection,
    geodesic_area_km2,
    geom_to_geojson,
    load_geojson,
    polygon_parts,
    project_geom,
    valid,
)
from .util import StageRecord, atomic_write_json, ensure_dirs, utc_now


def run(
    cfg: Config,
    raw_path: Path,
    out_districts: Path,
    out_state: Path,
    out_centroids: Path,
) -> dict:
    ensure_dirs()
    stage = StageRecord("05", "build-admin", inputs=[raw_path])
    admin_cfg = cfg.pipeline["admin"]
    version = cfg.pipeline["dataset_version"]
    min_area = float(admin_cfg["min_district_area_km2"])

    raw = load_geojson(raw_path)
    features = raw.get("features", [])
    if not features:
        raise RuntimeError("stage 05: no Assam ADM2 features in the raw layer")

    projected = []
    seen_ids: set[str] = set()
    for source_feature in features:
        props = source_feature.get("properties", {})
        district_id = props.get("shapeID")
        name = props.get("shapeName")
        if not district_id:
            raise RuntimeError("stage 05: ADM2 feature has no shapeID")
        if district_id in seen_ids:
            raise RuntimeError(f"stage 05: duplicate district_id {district_id}")
        seen_ids.add(district_id)
        geom_wgs = valid(shape(source_feature["geometry"]))
        if geom_wgs is None or geom_wgs.is_empty:
            raise RuntimeError(f"stage 05: empty geometry for {name}")
        if geom_wgs.geom_type not in ("Polygon", "MultiPolygon"):
            raise RuntimeError(f"stage 05: non-polygon geometry for {name}: {geom_wgs.geom_type}")
        area = geodesic_area_km2(geom_wgs)
        if area < min_area:
            print(f"[05] dropping sliver {name}: {area:.4f} km²")
            continue
        geom_proj = valid(project_geom(geom_wgs, cfg.aoi.output_crs, cfg.aoi.analysis_crs))
        if geom_proj is None or geom_proj.is_empty:
            raise RuntimeError(f"stage 05: projected geometry empty for {name}")
        rep = geom_proj.representative_point()
        if not (geom_proj.contains(rep) or geom_proj.touches(rep)):
            raise RuntimeError(f"stage 05: representative point outside district {name}")
        rep_wgs = project_geom(rep, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
        label_geom = geom_proj.simplify(
            float(admin_cfg["simplify_district_m"]), preserve_topology=True
        )
        label_geom = valid(label_geom)
        if label_geom is None or label_geom.is_empty:
            raise RuntimeError(f"stage 05: simplification destroyed geometry for {name}")
        label_wgs = project_geom(label_geom, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
        properties = {
            "district_id": district_id,
            "name": name,
            "iso": props.get("shapeISO") or "",
            "area_km2": round(area, 4),
            "centroid_lon": round(float(rep_wgs.x), 5),
            "centroid_lat": round(float(rep_wgs.y), 5),
            "class": "source",
            "label": "District boundary (source)",
        }
        item = feature(label_wgs, properties, cfg.aoi.decimals)
        if item is None:
            raise RuntimeError(f"stage 05: could not serialise district {name}")
        projected.append((district_id, name, area, geom_proj, item))
        stage.metric(f"area_{district_id}", round(area, 4))

    if not projected:
        raise RuntimeError("stage 05: no districts after sliver filtering")

    projected.sort(key=lambda item: item[1])
    district_features = [item[4] for item in projected]
    districts_collection = feature_collection(
        "Assam districts (geoBoundaries ADM2)", "source", district_features, version
    )
    out_districts.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_districts, districts_collection, indent=None)

    union = valid(
        __import__("shapely.ops", fromlist=["unary_union"]).unary_union(
            [item[3] for item in projected]
        )
    )
    if union is None or union.is_empty:
        raise RuntimeError("stage 05: state dissolve produced empty geometry")
    state_area = geodesic_area_km2(
        project_geom(union, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
    )
    district_sum = sum(item[2] for item in projected)
    if district_sum <= 0:
        raise RuntimeError("stage 05: district area sum is zero")
    tolerance = float(admin_cfg["state_area_tolerance"])
    relative_error = abs(state_area - district_sum) / district_sum
    print(
        f"[05] districts {len(projected)}, district sum {district_sum:.1f} km², "
        f"state {state_area:.1f} km² (delta {relative_error:.4%})"
    )
    if relative_error > tolerance:
        raise RuntimeError(
            f"stage 05: state area {state_area:.3f} km² differs from district sum "
            f"{district_sum:.3f} km² by {relative_error:.3%} > {tolerance:.1%}"
        )
    state_simplified = valid(
        union.simplify(float(admin_cfg["simplify_state_m"]), preserve_topology=True)
    )
    state_wgs = project_geom(state_simplified, cfg.aoi.analysis_crs, cfg.aoi.output_crs)
    state_feature = feature(
        state_wgs,
        {
            "state_id": cfg.aoi.state_iso,
            "name": cfg.aoi.state_name,
            "area_km2": round(state_area, 4),
            "district_count": len(projected),
            "class": "source",
            "label": "Assam outline, dissolved from ADM2 (source)",
        },
        cfg.aoi.decimals,
    )
    if state_feature is None:
        raise RuntimeError("stage 05: could not serialise state outline")
    state_collection = feature_collection(
        "Assam state outline", "source", [state_feature], version
    )
    out_state.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_state, state_collection, indent=None)

    centroids = {
        "schema_version": "1.0.0",
        "dataset_version": version,
        "note": "Representative points inside each district; DOM label positions, not committed map data.",
        "centroids": [
            {
                "district_id": item[0],
                "name": item[1],
                "lon": item[4]["properties"]["centroid_lon"],
                "lat": item[4]["properties"]["centroid_lat"],
            }
            for item in projected
        ],
        "generated_at": utc_now(),
    }
    out_centroids.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_centroids, centroids, indent=2, sort_keys=True)

    stage.out(out_districts, out_state, out_centroids)
    stage.metric("district_count", len(projected))
    stage.metric("state_area_km2", round(state_area, 3))
    stage.metric("district_area_sum_km2", round(district_sum, 3))
    stage.metric("state_area_relative_delta", round(relative_error, 8))
    stage.source(
        cfg.sources["boundaries"]["name"],
        raw.get("name", cfg.sources["boundaries"]["api_url"]),
        "licence recorded from geoBoundaries API (ODbL 1.0 for ADM2; see provenance)",
    )
    stage.finish(
        "Projected to EPSG:32646, make_valid, slivers <0.05 km² dropped, geodesic "
        "areas, representative points, display simplify 150 m / state 200 m."
    )
    print(
        f"[05] ok: districts {out_districts.stat().st_size / 1024:.0f} KB, "
        f"state {out_state.stat().st_size / 1024:.0f} KB"
    )
    return {"district_count": len(projected), "state_area_km2": state_area}
