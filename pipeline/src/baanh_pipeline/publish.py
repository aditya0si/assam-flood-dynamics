"""Stage 15 — aggregate provenance and publish the manifest with hashes."""
from __future__ import annotations

import json
from pathlib import Path

from .config import Config
from .util import (
    StageRecord,
    atomic_write_json,
    ensure_dirs,
    installed_versions,
    load_fragments,
    sha256_file,
    utc_now,
)


def _stage_pipeline(fragments: dict, stages: list[str]) -> list[dict]:
    pipeline = []
    for stage in stages:
        fragment = fragments.get(stage, {})
        pipeline.append(
            {
                "stage": stage,
                "command": fragment.get("command", f"python -m baanh_pipeline.cli <stage-{stage}>"),
                "version": fragment.get("version", "1.0.0"),
            }
        )
    return pipeline


def _fetched_at(fragments: dict, stage: str) -> str | None:
    fragment = fragments.get(stage, {})
    return fragment.get("finished_at") or fragment.get("started_at")


def run(cfg: Config, data_path: Path, version: str, manifest_path: Path, provenance_path: Path) -> dict:
    ensure_dirs()
    data_path = data_path if data_path.is_absolute() else cfg.root / data_path
    manifest_path = manifest_path if manifest_path.is_absolute() else cfg.root / manifest_path
    provenance_path = provenance_path if provenance_path.is_absolute() else cfg.root / provenance_path
    if version != str(cfg.pipeline["dataset_version"]):
        raise RuntimeError(
            f"stage 15: --version {version} does not match configured dataset_version "
            f"{cfg.pipeline['dataset_version']}"
        )
    report_path = data_path / "validation-report.json"
    if not report_path.exists():
        raise RuntimeError("stage 15: validation-report.json is missing; run stage 14")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "pass":
        raise RuntimeError(
            "stage 15: refusing to publish because validation-report.json status is "
            f"{report.get('status')!r}"
        )
    fragments = load_fragments()
    if len(fragments) < 8:
        raise RuntimeError(f"stage 15: only {len(fragments)} stage fragments found")

    sources = cfg.sources
    terrain = sources["terrain"]
    boundaries = sources["boundaries"]
    rivers = sources["rivers"]
    rivers_source_path = cfg.root / "pipeline" / "cache" / "rivers" / "rivers-source.json"
    rivers_source = (
        json.loads(rivers_source_path.read_text(encoding="utf-8"))
        if rivers_source_path.exists()
        else {}
    )
    source_used = rivers_source.get("source_used", "osm")
    rivers_url = rivers_source.get("source_url", rivers["overpass_url"])
    rivers_licence = rivers_source.get("licence", rivers["licence_osm"])
    rivers_name = rivers["name"] if source_used == "osm" else rivers["fallback_name"]
    fallback_note = (
        ""
        if source_used == "osm"
        else f" Overpass failed and the documented Natural Earth fallback was used ({rivers_source.get('fallback_reason', 'reason not recorded')})."
    )

    public_root = data_path.parent
    committed = {
        path.relative_to(public_root).as_posix()
        for path in data_path.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }

    def present(*paths: str) -> list[str]:
        return [path for path in paths if path in committed]

    entries = [
        {
            "id": "terrain",
            "dataset": "AWS Terrarium DEM mosaic",
            "class": "source",
            "source_name": terrain["name"],
            "source_url": terrain["url_template"],
            "licence": terrain["licence"],
            "fetched_at": _fetched_at(fragments, "01"),
            "pipeline": _stage_pipeline(fragments, ["01", "04"]),
            "output_paths": present("data/basemap/assam-hillshade.webp"),
            "notes": "Bilinear warp z11 Web Mercator to EPSG:32646 at 90 m; hillshade 315°/45°, 8-bit WebP. The DEM GeoTIFF is an intermediate and is not committed.",
        },
        {
            "id": "boundaries",
            "dataset": "geoBoundaries ADM2 Assam districts and dissolved state",
            "class": "source",
            "source_name": boundaries["name"],
            "source_url": boundaries["api_url"],
            "licence": "geoBoundaries API metadata: ADM2 Open Data Commons ODbL 1.0; ADM1 filter CC BY 2.5 IN",
            "fetched_at": _fetched_at(fragments, "02"),
            "pipeline": _stage_pipeline(fragments, ["02", "05", "10"]),
            "output_paths": present(
                "data/admin/assam-state.geojson", "data/admin/assam-districts.geojson"
            ),
            "notes": "ADM2 shapeISO is empty in the fetched release, so Assam districts were selected against the same source's ADM1 Assam polygon. State outline is dissolved from the selected ADM2 features. District risk attributes are derived in stage 10.",
        },
        {
            "id": "rivers",
            "dataset": "Mapped river centrelines",
            "class": "source",
            "source_name": rivers_name,
            "source_url": rivers_url,
            "licence": rivers_licence,
            "fetched_at": _fetched_at(fragments, "03"),
            "pipeline": _stage_pipeline(fragments, ["03", "06", "07", "08"]),
            "output_paths": present("data/hydro/assam-rivers.geojson"),
            "notes": f"Clipped to AOI + 5 km; lines below 500 m dropped; order by name/waterway heuristic; display simplification 50 m.{fallback_note}",
        },
        {
            "id": "flood",
            "dataset": "Scenario inundation depth bands and summary",
            "class": "scenario",
            "source_name": "Derived from AWS Terrarium DEM + mapped channels + synthetic scenario",
            "source_url": terrain["url_template"],
            "licence": terrain["licence"] + "; see rivers entry",
            "fetched_at": _fetched_at(fragments, "09"),
            "pipeline": _stage_pipeline(fragments, ["07", "08", "09"]),
            "output_paths": present(
                "data/flood/flood-frames.geojson", "data/flood/flood-summary.json"
            ),
            "notes": "HAND threshold with 8-connected connectivity; uniform stage per step; synthetic stage is not a gauge reading. Polygonised per depth band, simplified in EPSG:32646, clipped to Assam.",
        },
        {
            "id": "risk",
            "dataset": "Scenario-conditional risk zones and district ranking",
            "class": "derived",
            "source_name": "Derived from HAND, scenario duration/depth and Assam districts",
            "source_url": boundaries["api_url"],
            "licence": "Derived output; source licences as recorded for terrain, boundaries and rivers",
            "fetched_at": _fetched_at(fragments, "10"),
            "pipeline": _stage_pipeline(fragments, ["08", "09", "10"]),
            "output_paths": present(
                "data/risk/risk-zones.geojson", "data/risk/district-risk.json"
            ),
            "notes": "Cell risk weights HAND 0.60 and duration 0.40; district score weights area share 0.45, duration 0.35, p90 peak depth 0.20. No population, asset loss, agency or incident field exists.",
        },
        {
            "id": "series",
            "dataset": "Synthetic monsoon series and derived cross-sections",
            "class": "synthetic",
            "source_name": "Synthetic scenario parameters + DEM/HAND profiles",
            "source_url": "pipeline/config/scenario.json",
            "licence": "Synthetic model parameters; terrain and channel licences as recorded",
            "fetched_at": _fetched_at(fragments, "11"),
            "pipeline": _stage_pipeline(fragments, ["09", "11"]),
            "output_paths": present(
                "data/series/monsoon-series.json", "data/series/cross-sections.json"
            ),
            "notes": "Rainfall, main-stem stage and backwater values are declared synthetic; the series repeats flood-summary values exactly. Cross-sections sample DEM/HAND at 2 km and are not surveyed sections.",
        },
        {
            "id": "hillshade",
            "dataset": "Assam relief hillshade fallback",
            "class": "source",
            "source_name": terrain["name"],
            "source_url": terrain["url_template"],
            "licence": terrain["licence"],
            "fetched_at": _fetched_at(fragments, "04"),
            "pipeline": _stage_pipeline(fragments, ["01", "04"]),
            "output_paths": present("data/basemap/assam-hillshade.webp"),
            "notes": "8-bit grayscale WebP, 2000 px wide, quality 82; positions with the AOI Mercator corners; relief only, no labels, water or flood extent.",
        },
    ]

    if "data/risk/hotspots.geojson" in committed:
        entries.append(
            {
                "id": "hotspots",
                "dataset": "Derived inundation hotspots",
                "class": "derived",
                "source_name": "Derived from peak scenario wet mask, HAND and channel distance",
                "source_url": terrain["url_template"],
                "licence": "Derived output; source licences as recorded for terrain and rivers",
                "fetched_at": _fetched_at(fragments, "10"),
                "pipeline": _stage_pipeline(fragments, ["08", "09", "10"]),
                "output_paths": present("data/risk/hotspots.geojson"),
                "notes": "Low-HAND, >1.5 km from a channel, at least 2 km², first wet by step 6. These are backwater pockets, not embankment breaches; no breach dataset exists.",
            }
        )
    if "data/assets/critical-facilities.geojson" in committed:
        entries.append(
            {
                "id": "assets",
                "dataset": "OSM facility exposure",
                "class": "source",
                "source_name": "OpenStreetMap Overpass hospitals, clinics and schools",
                "source_url": rivers["overpass_url"],
                "licence": "ODbL 1.0 (OpenStreetMap contributors)",
                "fetched_at": _fetched_at(fragments, "12"),
                "pipeline": _stage_pipeline(fragments, ["09", "12"]),
                "output_paths": present("data/assets/critical-facilities.geojson"),
                "notes": "Completeness unknown (incomplete-osm); exposure is a scenario depth join, not damage, capacity or operational status. No facility list was hand-built.",
            }
        )
    if "data/gauges/virtual-gauges.geojson" in committed:
        entries.append(
            {
                "id": "gauges",
                "dataset": "Virtual gauges",
                "class": "synthetic",
                "source_name": "Points on mapped rivers with the synthetic scenario stage",
                "source_url": rivers_url,
                "licence": "Synthetic output; river geometry licence as recorded",
                "fetched_at": _fetched_at(fragments, "13"),
                "pipeline": _stage_pipeline(fragments, ["03", "13"]),
                "output_paths": present("data/gauges/virtual-gauges.geojson"),
                "notes": "No agency, station code, datum or measurement. Stage series is copied from the scenario with no local variation.",
            }
        )

    entries.append(
        {
            "id": "unosat",
            "dataset": "UNOSAT flood products",
            "class": "reference",
            "source_name": sources["unosat"]["name"],
            "source_url": sources["unosat"]["url"],
            "licence": "UNOSAT terms; not ingested",
            "fetched_at": None,
            "pipeline": [
                {
                    "stage": "00",
                    "command": "not ingested in M0; reserved for future event-context cross-check",
                    "version": "1.0.0",
                }
            ],
            "output_paths": [],
            "notes": "UNOSAT is explicitly not used in this build. No UNOSAT layer, incident context or event statistic feeds the app.",
        }
    )

    provenance = {
        "schema_version": "1.0.0",
        "dataset_version": version,
        "generated_at": utc_now(),
        "versions": installed_versions(),
        "entries": entries,
    }
    atomic_write_json(provenance_path, provenance, indent=2, sort_keys=True)

    # Manifest: every file except itself, fixed order, with hashes.
    files_meta = cfg.pipeline["files"]
    manifest_files = []
    tiers = {"critical": [], "animation": [], "optional": [], "fallback": []}
    missing_meta = []
    for path in sorted(data_path.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        relative = path.relative_to(public_root).as_posix()
        meta = files_meta.get(relative)
        if meta is None:
            missing_meta.append(relative)
            continue
        size = path.stat().st_size
        manifest_files.append(
            {
                "path": relative,
                "bytes": size,
                "sha256": sha256_file(path),
                "class": meta["class"],
                "tier": meta["tier"],
                "description": meta["description"],
            }
        )
        tiers[meta["tier"]].append(relative)
    if missing_meta:
        raise RuntimeError(
            "stage 15: data directory contains files without manifest metadata: "
            + ", ".join(missing_meta)
        )
    total = sum(item["bytes"] for item in manifest_files)
    if total > int(cfg.pipeline["validation"]["total_cap_bytes"]):
        raise RuntimeError(f"stage 15: committed data {total} bytes exceeds the 14 MB cap")
    for item in manifest_files:
        cap = cfg.pipeline["validation"]["file_caps_bytes"].get(item["path"])
        if cap is not None and item["bytes"] > int(cap):
            raise RuntimeError(f"stage 15: {item['path']} exceeds its file cap")

    scenario = json.loads((data_path / "scenario.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": "1.0.0",
        "dataset_version": version,
        "app_min_version": str(cfg.pipeline["app_min_version"]),
        "scenario_id": scenario["scenario_id"],
        "generated_at": utc_now(),
        "crs": "EPSG:4326",
        "analysis_crs": "EPSG:32646",
        "bbox": list(cfg.aoi.bbox),
        "step_count": int(scenario["step_count"]),
        "load_tiers": {
            "critical": sorted(tiers["critical"]),
            "animation": sorted(tiers["animation"]),
            "optional": sorted(tiers["optional"]),
            "fallback": sorted(tiers["fallback"]),
        },
        "files": manifest_files,
        "attribution": [
            {
                "name": item["name"],
                "url": item["url"],
                "licence": item["licence"],
            }
            for item in sources["attribution"]
        ],
    }
    atomic_write_json(manifest_path, manifest, indent=2, sort_keys=False)

    stage_record = StageRecord("15", "publish", inputs=[report_path])
    stage_record.out(provenance_path, manifest_path)
    stage_record.metric("files", len(manifest_files))
    stage_record.metric("total_bytes", total)
    stage_record.metric("tier_bytes", {key: sum((public_root / p).stat().st_size for p in paths) for key, paths in tiers.items()})
    stage_record.finish(
        "Manifest hashes every committed data file except itself; provenance aggregates "
        "stage fragments and records the UNOSAT absence."
    )

    print("[15] published files:")
    for item in manifest_files:
        print(f"[15]   {item['path']:50s} {item['bytes'] / 1024:8.1f} KB  {item['tier']}")
    print(
        f"[15] ok: {len(manifest_files)} files, {total / 1024 / 1024:.2f} MB, "
        f"critical {sum((public_root / p).stat().st_size for p in tiers['critical']) / 1024 / 1024:.2f} MB, "
        f"animation {sum((public_root / p).stat().st_size for p in tiers['animation']) / 1024 / 1024:.2f} MB"
    )
    return manifest
