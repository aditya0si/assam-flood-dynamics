"""Stage 18 - WorldPop population aggregated to the scenario peak mask and
districts.

The only resident-count field published is ``potentially_exposed_residents``.
The file is classed ``derived`` because it is a static population raster crossed
with a synthetic flood mask, not an impact assessment.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject
from shapely.geometry import shape
from shapely.validation import make_valid

from .config import Config
from .geo import load_geojson, project_geom
from .http import FetchError, fetch_bytes
from .util import StageRecord, atomic_write_json, ensure_dirs, utc_now


def _try_rest_catalogue(cfg: Config, cache_dir: Path, refresh: bool) -> tuple[bool, str, str | None]:
    source = cfg.sources["worldpop"]
    try:
        result = fetch_bytes(
            cfg,
            source["rest_endpoint"],
            cache_dir / "rest-catalogue.json",
            refresh=refresh,
            timeout_s=20,
            retries=1,
            accept="application/json",
        )
        payload = json.loads(result.payload.decode("utf-8"))
        urls: list[str] = []

        def visit(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if isinstance(item, str) and item.lower().endswith((".tif", ".tiff")):
                        if "ppp" in item.lower() and "ind" in item.lower():
                            urls.append(item)
                    else:
                        visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        visit(payload)
        # The REST catalogue can expose very large 100 m national rasters.  This
        # stage deliberately uses the 1 km Aggregated product (the finest
        # resolution that is a single, practical national download); the chosen
        # endpoint and the REST status are both published.
        chosen = next((url for url in urls if "1km" in url.lower() or "aggreg" in url.lower()), None)
        return True, "reachable", chosen
    except (FetchError, ValueError, json.JSONDecodeError) as exc:
        return False, f"unreachable ({type(exc).__name__})", None


def _fetch_population(cfg: Config, cache_dir: Path, refresh: bool) -> tuple[Path, dict]:
    source = cfg.sources["worldpop"]
    rest_ok, rest_status, rest_url = _try_rest_catalogue(cfg, cache_dir, refresh)
    endpoint = rest_url or source["endpoint"]
    cache_path = cache_dir / "ind_ppp_2020_1km_Aggregated.tif"
    result = fetch_bytes(cfg, endpoint, cache_path, refresh=refresh, timeout_s=600, retries=3)
    return cache_path, {
        "rest_endpoint": source["rest_endpoint"],
        "rest_status": rest_status,
        "rest_catalogue_used": bool(rest_ok and rest_url),
        "endpoint_used": endpoint,
        "retrieved_at": result.fetched_at if result.fetched_at != "cache" else utc_now(),
        "from_cache": result.from_cache,
    }


def _aoi_fraction(cfg: Config, shape_: tuple[int, int], transform, crs) -> np.ndarray:
    """Fractional AOI v2 coverage on the population grid.

    REVIEW-21: the WorldPop raster is an India-wide product.  Totals published
    beside Assam districts must be clipped to AOI v2, never the full raster.
    """
    core_path = cfg.root / "pipeline" / "work" / "aoi-v2-core-90m.tif"
    aoi_meta_path = cfg.root / "pipeline" / "work" / "aoi-v2.json"
    if not core_path.exists():
        raise RuntimeError(f"stage 18: AOI v2 core mask missing at {core_path}")
    if not aoi_meta_path.exists():
        raise RuntimeError(f"stage 18: AOI v2 metadata missing at {aoi_meta_path}")
    with rasterio.open(core_path) as src:
        core = src.read(1).astype(np.float32)
        core_transform = src.transform
        core_crs = src.crs
    fraction = np.zeros(shape_, dtype=np.float32)
    reproject(
        source=core,
        destination=fraction,
        src_transform=core_transform,
        src_crs=core_crs,
        dst_transform=transform,
        dst_crs=crs,
        resampling=Resampling.average,
        src_nodata=0,
        dst_nodata=0,
    )
    return np.clip(fraction, 0.0, 1.0)


def _district_population(
    pop: np.ndarray,
    masked: np.ndarray,
    transform,
    crs,
    districts: dict,
) -> tuple[list[dict], int, int]:
    shapes = []
    by_index = {}
    for index, feature in enumerate(districts.get("features", []), start=1):
        props = feature.get("properties", {})
        geom = project_geom(make_valid(shape(feature["geometry"])), "EPSG:4326", str(crs))
        shapes.append((geom, index))
        by_index[index] = {
            "district_id": str(props["district_id"]),
            "name": str(props.get("name", props["district_id"])),
        }
    district_raster = rasterize(
        shapes,
        out_shape=pop.shape,
        transform=transform,
        fill=0,
        all_touched=False,
        dtype="int16",
    )
    rows = []
    exposed_total = 0
    population_total = 0
    for index, info in by_index.items():
        in_district = district_raster == index
        district_population = int(round(float(pop[in_district].sum())))
        # REVIEW-21: the district exposure value is the zonal sum of the masked
        # population (pop x wet_fraction), not raw district population.
        exposed = int(round(float(masked[in_district].sum())))
        exposed_total += exposed
        population_total += district_population
        rows.append(
            {
                **info,
                "district_population": district_population,
                "potentially_exposed_residents": exposed,
                "exposed_share_of_district": (
                    round(exposed / district_population, 6) if district_population > 0 else 0.0
                ),
                "class": "derived",
            }
        )
    return rows, exposed_total, population_total


def _peak_population(
    cfg: Config,
    pop: np.ndarray,
    pop_transform,
    pop_crs,
    masks_dir: Path,
    peak_step: int,
) -> tuple[int, np.ndarray, float, str]:
    mask_path = masks_dir / f"step-{peak_step:02d}-wet.tif"
    if not mask_path.exists():
        raise RuntimeError(f"stage 18: peak wet mask missing at {mask_path}")
    with rasterio.open(mask_path) as src:
        wet = src.read(1).astype(np.uint8)
        wet_transform = src.transform
        wet_crs = src.crs
        wet_area_km2 = float(wet.sum()) * abs(src.transform.a * src.transform.e) / 1_000_000.0
    wet_fraction = np.zeros(pop.shape, dtype=np.float32)
    reproject(
        source=wet.astype(np.float32),
        destination=wet_fraction,
        src_transform=wet_transform,
        src_crs=wet_crs,
        dst_transform=pop_transform,
        dst_crs=pop_crs,
        resampling=Resampling.average,
        src_nodata=None,
        dst_nodata=0.0,
    )
    wet_fraction = np.clip(wet_fraction, 0.0, 1.0)
    total = float((pop * wet_fraction).sum())
    return int(round(total)), wet_fraction, wet_area_km2, mask_path.name


def _validate_counts(value: int) -> int:
    if value < 0 or value > 100_000_000:
        raise RuntimeError(f"stage 18: implausible population count {value}")
    return value


def run(
    cfg: Config,
    cache_dir: Path,
    masks_dir: Path,
    out: Path,
    refresh: bool = False,
) -> dict:
    ensure_dirs()
    source = cfg.sources["worldpop"]
    cache_dir = cache_dir if cache_dir.is_absolute() else cfg.root / cache_dir
    masks_dir = masks_dir if masks_dir.is_absolute() else cfg.root / masks_dir
    out = out if out.is_absolute() else cfg.root / out
    cache_dir.mkdir(parents=True, exist_ok=True)
    districts_path = cfg.root / "public" / "data" / "admin" / "assam-districts.geojson"
    roads_path = cfg.root / "public" / "data" / "flood" / "flood-summary.json"
    districts_doc = load_geojson(districts_path)
    summary = json.loads(roads_path.read_text(encoding="utf-8"))
    peak_step = int(summary["peak_step"])

    stage = StageRecord("18", "build-exposure", inputs=[districts_path, roads_path])
    pop_path, fetch_meta = _fetch_population(cfg, cache_dir, refresh)
    with rasterio.open(pop_path) as src:
        pop = src.read(1, masked=True)
        transform = src.transform
        crs = src.crs
        nodata = src.nodata
        pop = np.where(np.ma.getmaskarray(pop), 0.0, np.ma.filled(pop, 0.0)).astype(np.float64)
        pop = np.where(np.isfinite(pop), pop, 0.0)
        if float(pop.min()) < 0.0:
            pop = np.where(pop < 0.0, 0.0, pop)
    if nodata is not None:
        pop = np.where(pop == float(nodata), 0.0, pop)
    pop_total = int(round(float(pop.sum())))

    aoi_fraction = _aoi_fraction(cfg, pop.shape, transform, crs)
    population_within_aoi = int(round(float((pop * aoi_fraction).sum())))
    worldpop_cells_within_aoi = int((aoi_fraction > 0).sum())

    peak_count, wet_fraction, peak_wet_km2, peak_mask_name = _peak_population(
        cfg, pop, transform, crs, masks_dir, peak_step
    )
    masked_population = pop * wet_fraction
    district_rows, district_total, district_population_total = _district_population(
        pop, masked_population, transform, crs, districts_doc
    )
    for row in district_rows:
        row["district_population"] = _validate_counts(row["district_population"])
        row["potentially_exposed_residents"] = _validate_counts(row["potentially_exposed_residents"])
    peak_count = _validate_counts(peak_count)
    district_total = _validate_counts(district_total)
    district_population_total = _validate_counts(district_population_total)
    population_within_aoi = _validate_counts(population_within_aoi)

    # REVIEW-21 value-level gates.  A table that reports more exposed residents
    # than the mask contains, or more than live in a district, must not publish.
    if peak_count <= 0 or population_within_aoi <= 0:
        raise RuntimeError("stage 18: empty peak mask or AOI population")
    difference = abs(district_total - peak_count) / peak_count
    if difference > 0.01:
        raise RuntimeError(
            f"stage 18: district exposure sum {district_total:,} differs from the "
            f"peak mask {peak_count:,} by {difference:.2%} (>1%)"
        )
    if not (20_000_000 <= population_within_aoi <= 45_000_000):
        raise RuntimeError(
            f"stage 18: AOI population {population_within_aoi:,} is outside the "
            "plausible Assam band 20,000,000-45,000,000"
        )
    for row in district_rows:
        if row["potentially_exposed_residents"] > row["district_population"]:
            raise RuntimeError(
                f"stage 18: {row['name']} exposes {row['potentially_exposed_residents']:,} "
                f"residents but has only {row['district_population']:,}"
            )
    if peak_count >= population_within_aoi:
        raise RuntimeError(
            f"stage 18: peak mask exposure {peak_count:,} is not a strict subset of "
            f"AOI population {population_within_aoi:,}"
        )

    retrieved_at = utc_now()
    exposure = {
        "schema_version": "1.0.0",
        "dataset_version": str(cfg.pipeline["dataset_version"]),
        "class": "derived",
        "data_as_of": "2020-01-01",
        "source": {
            "name": source["name"],
            "rest_endpoint": source["rest_endpoint"],
            "rest_status": fetch_meta["rest_status"],
            "rest_catalogue_used": fetch_meta["rest_catalogue_used"],
            "rest_fallback_note": (
                "The public REST catalogue host timed out from this build host. The published "
                "product is the same WorldPop 2020 India 1 km Aggregated raster fetched directly "
                "from data.worldpop.org. The 1 km Aggregated grid is the practical national "
                "product; the 100 m national raster is 1.8 GB and is not used."
            ),
            "endpoint_used": fetch_meta["endpoint_used"],
            "vintage": source["vintage"],
            "resolution_m": int(source["resolution_m"]),
            "resolution_deg": float(source["resolution_deg"]),
            "units": source["units"],
            "licence": source["licence"],
            "retrieved_at": retrieved_at,
            "method": source["method"],
            "uncertainty": source["uncertainty"],
            # REVIEW-21: the unclipped raster total is India-wide and is kept only
            # under an explicit scope so it cannot be read as Assam's population.
            "raster_total_unclipped": pop_total,
            "raster_scope_unclipped": "India",
            "raster_cell_count_unclipped": int(pop.size),
        },
        "method_sentence": source["method"],
        "uncertainty_statement": source["uncertainty"],
        "caveat": (
            "Static WorldPop 2020 population crossed with a synthetic flood mask. "
            "This is a derived exposure estimate, not an impact assessment and not "
            "a record of a real event."
        ),
        "peak_mask": {
            "step": peak_step,
            "step_label": str(summary["steps"][peak_step]["step_label"]),
            "wet_area_km2": round(peak_wet_km2, 3),
            "mask_file": peak_mask_name,
            "potentially_exposed_residents": peak_count,
            "class": "derived",
            "data_as_of": "2020-01-01",
        },
        "districts": [
            {
                **row,
                "data_as_of": "2020-01-01",
            }
            for row in district_rows
        ],
        "totals": {
            "potentially_exposed_residents": district_total,
            "peak_mask_potentially_exposed_residents": peak_count,
            "district_count": len(district_rows),
            "district_population_total": district_population_total,
            "population_within_aoi": population_within_aoi,
            "population_raster_scope": "AOI v2 polygon",
            "worldpop_cell_count_within_aoi": worldpop_cells_within_aoi,
        },
    }
    if len(exposure["districts"]) != 33:
        raise RuntimeError(f"stage 18: expected 33 district exposure rows, found {len(exposure['districts'])}")
    atomic_write_json(out, exposure, indent=2, sort_keys=False)

    stage.source(source["name"], fetch_meta["endpoint_used"], source["licence"])
    stage.inputs.append(pop_path)
    stage.out(out)
    stage.metric("vintage", source["vintage"])
    stage.metric("rest_status", fetch_meta["rest_status"])
    stage.metric("grid_resolution_m", int(source["resolution_m"]))
    stage.metric("district_count", len(district_rows))
    stage.metric("peak_step", peak_step)
    stage.metric("peak_mask_potentially_exposed_residents", peak_count)
    stage.metric("district_potentially_exposed_residents", district_total)
    stage.metric("district_population_total", district_population_total)
    stage.metric("population_within_aoi", population_within_aoi)
    stage.metric("worldpop_total_residents_unclipped", pop_total)
    stage.metric("peak_wet_area_km2", round(peak_wet_km2, 3))
    stage.finish(
        "WorldPop 2020 1 km Aggregated population. District exposure is the zonal "
        "sum of pop x peak-mask wet fraction (fractional 1 km coverage of the 90 m "
        "mask), so district values reconcile to the peak-mask value within 1%. "
        "district_population is the raw zonal population and exposed_share_of_district "
        "is the exposed share of it. Totals are clipped to the AOI v2 core mask and "
        "published as population_within_aoi; the unclipped India-wide raster total is "
        "only in source.raster_total_unclipped with scope=India. The only resident-count "
        "field is potentially_exposed_residents. Class is derived. Static population x "
        "synthetic flood mask is not an impact assessment; the uncertainty statement is "
        "published in the file and UI."
    )
    print(
        f"[18] ok: WorldPop {source['vintage']} {source['resolution_m']} m; "
        f"peak mask {peak_count:,} potentially exposed residents over "
        f"{peak_wet_km2:,.0f} km²; district sum {district_total:,} "
        f"(delta {difference:.3%}); AOI population {population_within_aoi:,}; "
        f"{out.stat().st_size / 1024:.1f} KB"
    )
    return exposure
