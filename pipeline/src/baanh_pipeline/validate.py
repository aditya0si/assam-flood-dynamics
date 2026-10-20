"""Stage 14 — V01–V20 validation. A failing gate refuses to publish."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import jsonschema
from PIL import Image
from shapely.geometry import Polygon, shape
from shapely.validation import make_valid

from .config import Config
from .geo import geodesic_area_km2, iter_coords
from .schemas import (
    BANDS,
    CLASSES,
    RISK_CLASSES,
    SCHEMAS,
    VALIDATION_SCHEMA,
)
from .util import atomic_write_json, ensure_dirs, sha256_file, utc_now


REQUIRED_JSON = [
    "scenario.json",
    "flood/flood-summary.json",
    "flood/flood-frames.geojson",
    "admin/assam-districts.geojson",
    "admin/assam-state.geojson",
    "hydro/assam-rivers.geojson",
    "risk/risk-zones.geojson",
    "risk/district-risk.json",
    "series/monsoon-series.json",
    "validation-report.json",
]
OPTIONAL_JSON = [
    "risk/hotspots.geojson",
    "series/cross-sections.json",
    "assets/critical-facilities.geojson",
    "gauges/virtual-gauges.geojson",
]
FORBIDDEN_KEYS = {
    "casualties",
    "deaths",
    "displaced",
    "affected_persons",
    "incident_id",
    "agency_id",
    "relief_camp",
    "eta",
    "warning_issued",
    "casualty",
    "death",
    "displacement",
    "affected_people",
}


def _strict_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(
            handle,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant {value} in {path}")
            ),
        )


def _geo_features(data: dict):
    for feature in data.get("features", []):
        yield feature


def _all_json_numbers(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _all_json_numbers(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_json_numbers(item)
    elif isinstance(value, float):
        yield value


def _all_strings_and_keys(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield ("key", key)
            yield from _all_strings_and_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings_and_keys(item)
    elif isinstance(value, str):
        yield ("value", value)


def _ring_signed_area(coords: list[list[float]]) -> float:
    area = 0.0
    for first, second in zip(coords, coords[1:]):
        area += first[0] * second[1] - second[0] * first[1]
    return area / 2.0


def _check(id_: str, name: str, expected: str, actual: str, detail: str, status: str) -> dict:
    return {
        "id": id_,
        "name": name,
        "status": status,
        "expected": expected,
        "actual": actual,
        "detail": detail,
    }


def run(cfg: Config, data_path: Path, report_path: Path, version: str) -> dict:
    ensure_dirs()
    data_path = data_path if data_path.is_absolute() else cfg.root / data_path
    report_path = report_path if report_path.is_absolute() else cfg.root / report_path
    if version != str(cfg.pipeline["dataset_version"]):
        raise RuntimeError(
            f"stage 14: --version {version} does not match configured dataset_version "
            f"{cfg.pipeline['dataset_version']}"
        )
    files = sorted(p for p in data_path.rglob("*") if p.is_file())
    docs: dict[str, Any] = {}
    parse_errors: list[str] = []
    for path in files:
        if path.suffix.lower() not in (".json", ".geojson"):
            continue
        try:
            docs[path.relative_to(data_path).as_posix()] = _strict_json(path)
        except Exception as exc:
            parse_errors.append(f"{path.name}: {exc}")
    geo = {name: doc for name, doc in docs.items() if isinstance(doc, dict) and doc.get("type") == "FeatureCollection"}
    checks: list[dict] = []

    # V01 — schema validity.
    errors: list[str] = []
    checked = 0
    for relative in REQUIRED_JSON + OPTIONAL_JSON:
        path = data_path / relative
        if not path.exists():
            if relative in REQUIRED_JSON:
                errors.append(f"{relative}: missing")
            continue
        validator = jsonschema.Draft7Validator(SCHEMAS[relative])
        for error in sorted(validator.iter_errors(docs.get(relative)), key=lambda e: list(e.path)):
            errors.append(f"{relative}: {error.message}")
        checked += 1
    if report_path.exists():
        pass
    for relative in ("manifest.json", "provenance.json"):
        if relative in docs:
            validator = jsonschema.Draft7Validator(SCHEMAS[relative])
            for error in validator.iter_errors(docs[relative]):
                errors.append(f"{relative}: {error.message}")
            checked += 1
    checks.append(
        _check(
            "V01",
            "Schema validity",
            "every committed JSON/GeoJSON parses and matches its §6 schema",
            f"{checked} files schema-checked; {len(parse_errors)} parse error(s); {len(errors)} schema error(s)",
            "; ".join((parse_errors + errors)[:6]) if (parse_errors or errors) else "all checked files valid",
            "fail" if (parse_errors or errors) else "pass",
        )
    )

    # V02 — geometry validity.
    invalid_geoms = []
    feature_count = 0
    for name, doc in geo.items():
        for feature in _geo_features(doc):
            feature_count += 1
            geometry = feature.get("geometry")
            if not geometry or not geometry.get("coordinates") and geometry.get("type") != "GeometryCollection":
                invalid_geoms.append(f"{name}: null/empty geometry")
                continue
            try:
                geom = shape(geometry)
                if geom.is_empty:
                    invalid_geoms.append(f"{name}: empty geometry")
                    continue
                if not geom.is_valid:
                    repaired = make_valid(geom)
                    if repaired is None or repaired.is_empty or not repaired.is_valid:
                        invalid_geoms.append(f"{name}: invalid geometry")
            except Exception as exc:
                invalid_geoms.append(f"{name}: {exc}")
    checks.append(
        _check(
            "V02",
            "Geometry validity",
            "no null/empty geometry; is_valid true after make_valid",
            f"{feature_count} features, {len(invalid_geoms)} invalid",
            "; ".join(invalid_geoms[:5]) if invalid_geoms else "all geometries valid or repairable",
            "fail" if invalid_geoms else "pass",
        )
    )

    # V03 — bounds and lon/lat sanity.
    min_lon, min_lat, max_lon, max_lat = cfg.aoi.bbox
    margin = float(cfg.aoi.raw["coordinate_bounds_margin_deg"])
    out_of_bounds = []
    coordinate_count = 0
    for name, doc in geo.items():
        for feature in _geo_features(doc):
            for lon, lat in iter_coords(feature["geometry"]):
                coordinate_count += 1
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    out_of_bounds.append(f"{name}: ({lon},{lat}) not lon/lat")
                elif not (
                    min_lon - margin <= lon <= max_lon + margin
                    and min_lat - margin <= lat <= max_lat + margin
                ):
                    out_of_bounds.append(f"{name}: ({lon},{lat}) outside AOI")
    checks.append(
        _check(
            "V03",
            "Bounds",
            f"every coordinate inside AOI + {margin}°; no swapped lon/lat",
            f"{coordinate_count} coordinates, {len(out_of_bounds)} outside",
            "; ".join(out_of_bounds[:5]) if out_of_bounds else "all coordinates inside AOI",
            "fail" if out_of_bounds else "pass",
        )
    )

    # V04 — Assam containment.
    state_doc = docs.get("admin/assam-state.geojson")
    containment = []
    if isinstance(state_doc, dict) and state_doc.get("features"):
        state_geom = shape(state_doc["features"][0]["geometry"])
        buffered_state = state_geom.buffer(0.02)
        for name in ("admin/assam-districts.geojson",):
            doc = docs.get(name)
            if isinstance(doc, dict):
                for feature in _geo_features(doc):
                    if not shape(feature["geometry"]).intersects(state_geom):
                        containment.append(f"{name}: district does not intersect state")
        for name in ("flood/flood-frames.geojson", "risk/risk-zones.geojson", "risk/hotspots.geojson"):
            doc = docs.get(name)
            if not isinstance(doc, dict):
                continue
            for feature in _geo_features(doc):
                geom = shape(feature["geometry"])
                point = geom if geom.geom_type == "Point" else geom.representative_point()
                if not buffered_state.contains(point):
                    containment.append(f"{name}: centroid outside buffered Assam")
    else:
        containment.append("state outline missing")
    checks.append(
        _check(
            "V04",
            "Assam containment",
            "districts/state intersect Assam; flood/risk/hotspot centroids inside buffered state",
            f"{len(containment)} violation(s)",
            "; ".join(containment[:5]) if containment else "all layers contained",
            "fail" if containment else "pass",
        )
    )

    # V05/V06 — area hydrograph.
    summary = docs.get("flood/flood-summary.json") or {}
    steps = summary.get("steps", [])
    areas = [float(step["inundated_area_km2"]) for step in steps] if steps else []
    tol = float(cfg.pipeline["inundation"]["monotonic_tolerance"])
    rising_failures = []
    if len(areas) != 12:
        rising_failures.append(f"{len(areas)} steps")
    else:
        for index in range(7):
            if areas[index + 1] < areas[index] * (1.0 - tol):
                rising_failures.append(f"S{index:02d}->S{index + 1:02d}: {areas[index]:.1f}->{areas[index + 1]:.1f}")
    checks.append(
        _check(
            "V05",
            "Rising-limb area monotonicity",
            f"non-decreasing S00–S07, tolerance {tol:.1%}",
            "areas " + " -> ".join(f"{value:,.1f}" for value in areas[:8]) if areas else "no summary",
            "; ".join(rising_failures) if rising_failures else "steps 0–7 non-decreasing",
            "fail" if rising_failures else "pass",
        )
    )
    recession_failures = []
    if len(areas) == 12:
        for index in range(7, 11):
            if areas[index + 1] > areas[index] * (1.0 + tol):
                recession_failures.append(f"S{index:02d}->S{index + 1:02d}: {areas[index]:.1f}->{areas[index + 1]:.1f}")
        if int(summary.get("peak_step", -1)) != 7:
            recession_failures.append(f"peak_step={summary.get('peak_step')}")
        if max(areas) != areas[7]:
            recession_failures.append(f"max area at S{areas.index(max(areas)):02d}")
    else:
        recession_failures.append("summary step count is not 12")
    checks.append(
        _check(
            "V06",
            "Recession and peak",
            "S08–S11 non-increasing; peak step = 7",
            "areas " + " -> ".join(f"{value:,.1f}" for value in areas[7:]) if areas else "no summary",
            "; ".join(recession_failures) if recession_failures else "steps 8–11 non-increasing; peak at S07",
            "fail" if recession_failures else "pass",
        )
    )

    # V07 — finite numbers.
    non_finite = []
    for name, doc in docs.items():
        for value in _all_json_numbers(doc):
            if not math.isfinite(value):
                non_finite.append(name)
                break
    checks.append(
        _check(
            "V07",
            "Finite numbers",
            "no NaN/Infinity anywhere; JSON allow_nan=False",
            f"{len(non_finite)} file(s) with non-finite values",
            ", ".join(non_finite[:5]) if non_finite else "all numbers finite; strict JSON parse passed",
            "fail" if non_finite or parse_errors else "pass",
        )
    )

    # V08 — classes and labels.
    class_failures = []
    for name, doc in geo.items():
        if doc.get("class") not in CLASSES:
            class_failures.append(f"{name}: envelope class {doc.get('class')!r}")
        for feature in _geo_features(doc):
            props = feature.get("properties", {})
            if props.get("class") not in CLASSES:
                class_failures.append(f"{name}: feature class {props.get('class')!r}")
            if not isinstance(props.get("label"), str) or not props["label"].strip():
                class_failures.append(f"{name}: missing label")
    for name, key in (
        ("scenario.json", "class"),
        ("flood/flood-summary.json", "class"),
        ("risk/district-risk.json", "class"),
        ("series/monsoon-series.json", "class"),
        ("series/cross-sections.json", "class"),
    ):
        doc = docs.get(name)
        if isinstance(doc, dict) and doc.get(key) not in CLASSES:
            class_failures.append(f"{name}: class {doc.get(key)!r}")
    checks.append(
        _check(
            "V08",
            "Classes and labels",
            "every feature class in the five-value enum; labels/badges present",
            f"{len(geo)} GeoJSON layers, {len(class_failures)} class/label violations",
            "; ".join(class_failures[:6]) if class_failures else "all classes and labels valid",
            "fail" if class_failures else "pass",
        )
    )

    # V09 — file caps.
    caps = cfg.pipeline["validation"]["file_caps_bytes"]
    public_root = data_path.parent
    cap_failures = []
    total_data = 0
    for key, cap in caps.items():
        if key.startswith("meta_combined_cap_bytes"):
            continue
        path = public_root / key
        if not path.exists():
            continue
        size = path.stat().st_size
        total_data += size
        if size > int(cap):
            cap_failures.append(f"{key}: {size} > {cap}")
    total_cap = int(cfg.pipeline["validation"]["total_cap_bytes"])
    total_all = sum(path.stat().st_size for path in files)
    if total_all > total_cap:
        cap_failures.append(f"total {total_all} > {total_cap}")
    meta_cap = int(caps["meta_combined_cap_bytes"])
    meta_files = ["manifest.json", "provenance.json", "scenario.json", "validation-report.json"]
    meta_size = sum((data_path / name).stat().st_size for name in meta_files if (data_path / name).exists())
    if meta_size > meta_cap:
        cap_failures.append(f"meta combined {meta_size} > {meta_cap}")
    checks.append(
        _check(
            "V09",
            "File caps",
            "every file ≤ its §11 cap; total ≤14 MB",
            f"total {total_all / 1024 / 1024:.2f} MB; meta {meta_size / 1024:.0f} KB; {len(cap_failures)} over cap",
            "; ".join(cap_failures[:6]) if cap_failures else "all file caps satisfied",
            "fail" if cap_failures else "pass",
        )
    )

    # V10 — manifest integrity.
    manifest_path = data_path / "manifest.json"
    manifest = docs.get("manifest.json")
    manifest_failures = []
    if manifest is None:
        manifest_status = "pass"
        manifest_actual = f"manifest absent on first run; {len([p for p in files if p.name != 'manifest.json'])} files will be hashed by publish"
        manifest_detail = "first run: publish writes manifest.json after validate passes"
    else:
        entries = manifest.get("files", [])
        listed = [entry.get("path") for entry in entries]
        if len(listed) != len(set(listed)):
            manifest_failures.append("duplicate manifest entries")
        for entry in entries:
            path = public_root / entry["path"]
            if not path.exists():
                manifest_failures.append(f"missing {entry['path']}")
                continue
            size = path.stat().st_size
            if int(entry.get("bytes", -1)) != size:
                manifest_failures.append(f"{entry['path']}: bytes {entry.get('bytes')} != {size}")
            if sha256_file(path) != entry.get("sha256"):
                manifest_failures.append(f"{entry['path']}: sha256 mismatch")
        orphan = [
            path.relative_to(public_root).as_posix()
            for path in files
            if path.name != "manifest.json" and path.relative_to(public_root).as_posix() not in listed
        ]
        if orphan:
            manifest_failures.append(f"orphans: {orphan[:4]}")
        manifest_status = "fail" if manifest_failures else "pass"
        manifest_actual = f"{len(entries)} manifest entries, {len(manifest_failures)} mismatch(es)"
        manifest_detail = "; ".join(manifest_failures[:5]) if manifest_failures else "manifest hashes and sizes match"
    checks.append(
        _check(
            "V10",
            "Manifest integrity",
            "every file except manifest listed once; SHA-256 and bytes match; no orphan",
            manifest_actual,
            manifest_detail,
            manifest_status,
        )
    )

    # V11 — series and stage consistency.
    series_doc = docs.get("series/monsoon-series.json") or {}
    series_failures = []
    series_map = {item.get("id"): item for item in series_doc.get("series", [])}
    expected_keys = {
        "rainfall": "rainfall_mm_day",
        "mainstem_stage": "mainstem_stage_m",
        "backwater": "backwater_m",
        "stage_above_drainage": "stage_m",
    }
    for series_id, key in expected_keys.items():
        item = series_map.get(series_id)
        if not item or len(item.get("points", [])) != 12:
            series_failures.append(f"{series_id}: missing or not 12 points")
            continue
        for point in item["points"]:
            step = steps[point["step"]] if point["step"] < len(steps) else None
            if step is None or abs(float(point["value"]) - float(step[key])) > 1e-6:
                series_failures.append(f"{series_id} step {point['step']} != summary")
    threshold = series_doc.get("threshold", {}).get("value")
    if threshold is None or abs(float(threshold) - float(cfg.scenario.threshold_m)) > 1e-6:
        series_failures.append(f"threshold {threshold} != {cfg.scenario.threshold_m}")
    for step in steps:
        if abs(float(step["stage_m"]) - (float(step["mainstem_stage_m"]) + float(step["backwater_m"]))) > 1e-6:
            series_failures.append(f"stage sum mismatch at S{step['step']}")
    checks.append(
        _check(
            "V11",
            "Series and stage consistency",
            "series = summary at every step (1e−6); threshold = 4.0; stage = mainstem + backwater",
            f"{len(series_map)} series, {len(steps)} steps, {len(series_failures)} mismatch(es)",
            "; ".join(series_failures[:5]) if series_failures else "series and stage arithmetic consistent",
            "fail" if series_failures else "pass",
        )
    )

    # V12 — district join and rank.
    district_doc = docs.get("admin/assam-districts.geojson") or {}
    ranking = docs.get("risk/district-risk.json") or {}
    district_features = district_doc.get("features", [])
    district_by_id = {f["properties"].get("district_id"): f for f in district_features}
    join_failures = []
    if len(district_by_id) != len(district_features):
        join_failures.append("duplicate district_id in districts GeoJSON")
    ranked = ranking.get("districts", [])
    ranks = [int(item["rank"]) for item in ranked]
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        join_failures.append("rank is not dense from 1")
    for item in ranked:
        if item["district_id"] not in district_by_id:
            join_failures.append(f"{item['district_id']} missing from districts GeoJSON")
            continue
        if not (0 <= float(item["risk_score"]) <= 100):
            join_failures.append(f"{item['name']} score out of range")
        if item["risk_class"] != _district_class(float(item["risk_score"]), cfg):
            join_failures.append(f"{item['name']} class does not match score")
        props = district_by_id[item["district_id"]]["properties"]
        if props.get("risk_score") is None or abs(float(props["risk_score"]) - float(item["risk_score"])) > 1e-6:
            join_failures.append(f"{item['name']} score not joined into districts")
        if props.get("rank") != item["rank"]:
            join_failures.append(f"{item['name']} rank not joined into districts")
    for feature in district_features:
        props = feature["properties"]
        if props.get("risk_score") is not None and props.get("rank") is None:
            join_failures.append(f"{props.get('name')} has score but no rank")
    checks.append(
        _check(
            "V12",
            "District join",
            "every ranking district exists once; rank dense; score 0–100",
            f"{len(district_features)} districts, {len(ranked)} ranked, {len(join_failures)} violation(s)",
            "; ".join(join_failures[:5]) if join_failures else "district join and dense ranking valid",
            "fail" if join_failures else "pass",
        )
    )

    # V13 — forbidden fields and claims.
    banned = []
    for name, doc in docs.items():
        for kind, text in _all_strings_and_keys(doc):
            if kind == "key" and text.lower() in FORBIDDEN_KEYS:
                banned.append(f"{name}: key {text}")
            elif kind == "value":
                lowered = text.lower()
                for phrase in ("operational forecast", "official forecast", "flood forecast", "warning issued"):
                    if phrase in lowered:
                        banned.append(f"{name}: claim {phrase!r}")
                for match in re.finditer(r"forecast", lowered):
                    prefix = lowered[max(0, match.start() - 24) : match.start()]
                    if not re.search(r"(not|never|no)\s+(a\s+)?$", prefix):
                        banned.append(f"{name}: positive forecast claim")
                        break
    checks.append(
        _check(
            "V13",
            "Forbidden fields/claims",
            "no casualty/displacement/incident/agency/camp/eta fields; no positive forecast claim",
            f"{len(banned)} forbidden occurrence(s)",
            "; ".join(sorted(set(banned))[:6]) if banned else "no forbidden fields or positive forecast claims",
            "fail" if banned else "pass",
        )
    )

    # V14 — step count, labels and per-step features.
    step_failures = []
    if len(steps) != 12:
        step_failures.append(f"summary has {len(steps)} steps")
    scenario_steps = docs.get("scenario.json", {}).get("steps", [])
    if len(scenario_steps) != 12:
        step_failures.append(f"scenario has {len(scenario_steps)} steps")
    frame_steps = {}
    for feature in geo.get("flood/flood-frames.geojson", {}).get("features", []):
        props = feature["properties"]
        frame_steps.setdefault(int(props["step"]), 0)
        frame_steps[int(props["step"])] += 1
    for index in range(12):
        if frame_steps.get(index, 0) < 1:
            step_failures.append(f"step {index} has no flood feature")
    for index, step in enumerate(scenario_steps):
        if int(step["step"]) != index:
            step_failures.append(f"scenario step {index} out of order")
        if index < len(steps):
            if steps[index]["step_label"] != step["label"]:
                step_failures.append(f"step {index} label mismatch")
            if int(steps[index]["day_offset"]) != int(step["day_offset"]):
                step_failures.append(f"step {index} day mismatch")
            if steps[index]["phase"] != step["phase"]:
                step_failures.append(f"step {index} phase mismatch")
    checks.append(
        _check(
            "V14",
            "Step count",
            "exactly 12 steps; labels/days/phases match scenario; every step has ≥1 feature",
            f"summary {len(steps)} steps, scenario {len(scenario_steps)} steps, flood features by step {sorted(frame_steps)}",
            "; ".join(step_failures[:6]) if step_failures else "12 steps, matching labels/days/phases, every step has a feature",
            "fail" if step_failures else "pass",
        )
    )

    # V15 — coordinate hygiene.
    hygiene_failures = []
    checked_coords = 0
    for name, doc in geo.items():
        for feature in _geo_features(doc):
            geometry = feature["geometry"]
            kind = geometry.get("type")
            if kind == "Point":
                coords = [geometry["coordinates"]]
            elif kind == "MultiPoint":
                coords = geometry["coordinates"]
            elif kind == "LineString":
                coords = geometry["coordinates"]
            elif kind == "MultiLineString":
                coords = [pair for line in geometry["coordinates"] for pair in line]
            elif kind == "Polygon":
                coords = [pair for ring in geometry["coordinates"] for pair in ring]
            elif kind == "MultiPolygon":
                coords = [pair for poly in geometry["coordinates"] for ring in poly for pair in ring]
            else:
                continue
            for pair in coords:
                checked_coords += 1
                if abs(round(float(pair[0]), 5) - float(pair[0])) > 1e-9 or abs(
                    round(float(pair[1]), 5) - float(pair[1])
                ) > 1e-9:
                    hygiene_failures.append(f"{name}: coordinate not 5 dp")
                    break
            if kind in ("Polygon", "MultiPolygon"):
                polygons = [geometry["coordinates"]] if kind == "Polygon" else geometry["coordinates"]
                for polygon in polygons:
                    for ring_index, ring in enumerate(polygon):
                        if len(ring) < 4:
                            hygiene_failures.append(f"{name}: ring <4 points")
                            continue
                        for first, second in zip(ring, ring[1:]):
                            if first == second:
                                hygiene_failures.append(f"{name}: consecutive duplicate")
                                break
                        area = _ring_signed_area(ring)
                        if ring_index == 0 and area <= 0:
                            hygiene_failures.append(f"{name}: exterior not CCW")
                        if ring_index > 0 and area >= 0:
                            hygiene_failures.append(f"{name}: hole not CW")
                        if name == "flood/flood-frames.geojson":
                            ring_area = geodesic_area_km2(Polygon(ring))
                            if ring_area < 0.02:
                                hygiene_failures.append(f"{name}: ring <0.02 km²")
            elif kind in ("LineString", "MultiLineString"):
                lines = [coords] if kind == "LineString" else geometry["coordinates"]
                for line in lines:
                    for first, second in zip(line, line[1:]):
                        if first == second:
                            hygiene_failures.append(f"{name}: consecutive duplicate")
                            break
    checks.append(
        _check(
            "V15",
            "Coordinate hygiene",
            "5 decimals; no consecutive duplicates; RFC 7946 winding; no flood ring <0.02 km²",
            f"{checked_coords} coordinates checked, {len(hygiene_failures)} violation(s)",
            "; ".join(hygiene_failures[:6]) if hygiene_failures else "coordinates, winding and ring sizes valid",
            "fail" if hygiene_failures else "pass",
        )
    )

    # V16 — risk ranges and classes.
    risk_failures = []
    cell_thresholds = cfg.pipeline["risk"]["cell"]["thresholds"]
    for feature in geo.get("risk/risk-zones.geojson", {}).get("features", []):
        props = feature["properties"]
        score = float(props["risk_score"])
        if not (0 <= score <= 100):
            risk_failures.append(f"{props['zone_id']} score {score}")
        expected = (
            "very_high"
            if score >= cell_thresholds["very_high"]
            else "high"
            if score >= cell_thresholds["high"]
            else "moderate"
            if score >= cell_thresholds["moderate"]
            else "low"
        )
        if props["risk_class"] != expected:
            risk_failures.append(f"{props['zone_id']} class {props['risk_class']} != {expected}")
    for item in ranking.get("districts", []):
        if item["risk_class"] != _district_class(float(item["risk_score"]), cfg):
            risk_failures.append(f"{item['name']} district class mismatch")
    checks.append(
        _check(
            "V16",
            "Risk range",
            "all scores 0–100; zone and district classes match thresholds",
            f"{len(geo.get('risk/risk-zones.geojson', {}).get('features', []))} zones, {len(ranking.get('districts', []))} ranked districts, {len(risk_failures)} violation(s)",
            "; ".join(risk_failures[:5]) if risk_failures else "all risk scores and classes valid",
            "fail" if risk_failures else "pass",
        )
    )

    # V17 — channel coverage.
    hand_meta_path = cfg.root / "pipeline" / "work" / "hand-meta.json"
    hand_meta = _strict_json(hand_meta_path) if hand_meta_path.exists() else {}
    valid_share = float(hand_meta.get("valid_assam_share", 0.0))
    clamped_share = float(hand_meta.get("clamped_negative_share", 0.0))
    min_share = float(cfg.pipeline["validation"]["min_valid_hand_share"])
    warn_share = float(cfg.pipeline["validation"]["warn_valid_hand_share"])
    max_clamped = float(cfg.pipeline["validation"]["max_clamped_negative_share"])
    if valid_share < min_share:
        status = "fail"
    elif valid_share < warn_share:
        status = "warn"
    else:
        status = "pass"
    detail = f"valid Assam HAND share {valid_share:.2%}; clamped negatives {clamped_share:.2%}; nodata cells {hand_meta.get('nodata_cells')}"
    if clamped_share > max_clamped:
        status = "warn" if status != "fail" else status
        detail += "; clamped negatives exceed 2%"
    checks.append(
        _check(
            "V17",
            "Channel coverage",
            "≥85% of Assam-masked cells valid HAND; no-channel cells reported; clamped negatives ≤2%",
            f"valid {valid_share:.2%}, clamped {clamped_share:.2%}",
            detail,
            status,
        )
    )

    # V18 — fallback hillshade.
    hillshade_path = data_path / "basemap" / "assam-hillshade.webp"
    hillshade_failures = []
    if not hillshade_path.exists():
        hillshade_failures.append("missing")
    else:
        if hillshade_path.stat().st_size > 1_572_864:
            hillshade_failures.append("larger than 1.5 MB")
        try:
            with Image.open(hillshade_path) as image:
                image.load()
                if image.width != 2000:
                    hillshade_failures.append(f"width {image.width} != 2000")
                if image.mode == "L":
                    pass
                elif image.mode == "RGB":
                    import numpy as np

                    pixels = np.asarray(image)
                    if (
                        np.abs(pixels[:, :, 0].astype(int) - pixels[:, :, 1]).max() > 2
                        or np.abs(pixels[:, :, 0].astype(int) - pixels[:, :, 2]).max() > 2
                    ):
                        hillshade_failures.append("decoded RGB is not near-grayscale")
                else:
                    hillshade_failures.append(f"mode {image.mode} is not grayscale")
        except Exception as exc:
            hillshade_failures.append(f"decode failed: {exc}")
    checks.append(
        _check(
            "V18",
            "Fallback asset",
            "assam-hillshade.webp exists, ≤1.5 MB, decodes, width 2000, 8-bit grayscale",
            "missing" if not hillshade_path.exists() else f"{hillshade_path.stat().st_size / 1024:.0f} KB",
            "; ".join(hillshade_failures) if hillshade_failures else "hillshade present, decodes, width 2000",
            "fail" if hillshade_failures else "pass",
        )
    )

    # V19 — tier budgets.
    tier_caps = cfg.pipeline["validation"]["tier_caps_bytes"]
    file_meta = cfg.pipeline["files"]
    tiers = {"critical": 0, "animation": 0, "optional": 0, "fallback": 0}
    for key, meta in file_meta.items():
        if key == "data/manifest.json":
            continue
        path = public_root / key
        if path.exists():
            tier = meta["tier"]
            tiers[tier] = tiers.get(tier, 0) + path.stat().st_size
    budget_failures = []
    if tiers["critical"] > int(tier_caps["critical"]):
        budget_failures.append(f"critical {tiers['critical']} > {tier_caps['critical']}")
    if tiers["animation"] > int(tier_caps["animation"]):
        budget_failures.append(f"animation {tiers['animation']} > {tier_caps['animation']}")
    optional_total = tiers["optional"] + tiers["fallback"]
    if optional_total > int(tier_caps["optional"]):
        budget_failures.append(f"optional/fallback {optional_total} > {tier_caps['optional']}")
    checks.append(
        _check(
            "V19",
            "First-paint budget",
            "critical ≤3.5 MB; animation ≤7.6 MB; optional/fallback ≤3.0 MB",
            f"critical {tiers['critical'] / 1024 / 1024:.2f} MB, animation {tiers['animation'] / 1024 / 1024:.2f} MB, optional/fallback {optional_total / 1024 / 1024:.2f} MB",
            "; ".join(budget_failures) if budget_failures else "all tier budgets satisfied",
            "fail" if budget_failures else "pass",
        )
    )

    # V20 — provenance completeness.
    provenance = docs.get("provenance.json")
    provenance_failures = []
    if provenance is None:
        fragments = sorted((cfg.root / "pipeline" / "work" / "provenance").glob("*.json"))
        if len(fragments) < 8:
            provenance_failures.append(f"provenance.json absent and only {len(fragments)} stage fragments")
        provenance_actual = f"provenance.json absent on first run; {len(fragments)} stage fragments present"
        provenance_detail = "publish will aggregate fragments into provenance.json"
    else:
        entries = {entry.get("id"): entry for entry in provenance.get("entries", [])}
        required_entries = ["terrain", "boundaries", "rivers", "flood", "risk", "series", "hillshade"]
        for entry_id in required_entries:
            entry = entries.get(entry_id)
            if not entry:
                provenance_failures.append(f"missing entry {entry_id}")
                continue
            for field in ("source_name", "source_url", "licence"):
                if not entry.get(field):
                    provenance_failures.append(f"{entry_id}: missing {field}")
            if not entry.get("pipeline"):
                provenance_failures.append(f"{entry_id}: no pipeline stages")
            if not entry.get("output_paths"):
                provenance_failures.append(f"{entry_id}: no output paths")
        if "unosat" not in entries:
            provenance_failures.append("UNOSAT absence not noted")
        provenance_actual = f"{len(entries)} entries, {len(provenance_failures)} violation(s)"
        provenance_detail = "; ".join(provenance_failures[:5]) if provenance_failures else "required source→stage→file entries present"
    checks.append(
        _check(
            "V20",
            "Provenance completeness",
            "every committed dataset has source/licence/stage/output; UNOSAT absence noted",
            provenance_actual,
            provenance_detail,
            "fail" if provenance_failures else "pass",
        )
    )

    report = _build_report(checks, docs, files, version)
    report_errors = [
        error.message
        for error in jsonschema.Draft7Validator(VALIDATION_SCHEMA).iter_errors(report)
    ]
    if report_errors:
        raise RuntimeError(
            "stage 14: validation report does not match its schema: "
            + "; ".join(report_errors[:5])
        )
    atomic_write_json(report_path, report, indent=2, sort_keys=False)
    failures = [check for check in checks if check["status"] == "fail"]
    warnings = [check for check in checks if check["status"] == "warn"]
    print(
        f"[14] {'PASS' if not failures else 'FAIL'}: {len(checks)} checks, "
        f"{len(failures)} fail, {len(warnings)} warn, "
        f"{report['counts']['features']} features, {report['counts']['files']} files"
    )
    if failures:
        for check in failures:
            print(f"[14]   {check['id']} {check['name']}: expected {check['expected']} | actual {check['actual']} | {check['detail']}")
        raise RuntimeError(f"stage 14: {len(failures)} validation gate(s) failed")
    return report


def _district_class(score: float, cfg: Config) -> str:
    thresholds = cfg.pipeline["risk"]["district"]["thresholds"]
    if score >= thresholds["very_high"]:
        return "very_high"
    if score >= thresholds["high"]:
        return "high"
    if score >= thresholds["moderate"]:
        return "moderate"
    return "low"


def _build_report(checks: list[dict], docs: dict, files: list[Path], version: str) -> dict:
    feature_count = 0
    for doc in docs.values():
        if isinstance(doc, dict) and doc.get("type") == "FeatureCollection":
            feature_count += len(doc.get("features", []))
    failures = sum(1 for check in checks if check["status"] == "fail")
    warnings = sum(1 for check in checks if check["status"] == "warn")
    status = "pass" if failures == 0 and len(checks) >= 20 else "fail"
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "dataset_version": version,
        "status": status,
        "checks": checks,
        "counts": {
            "files": len(files),
            "steps": 12,
            "features": feature_count,
            "failures": failures,
            "warnings": warnings,
        },
    }
