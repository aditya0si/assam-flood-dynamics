"""Stage 17 - ERA5 daily precipitation, district areal means and a separate
Open-Meteo current-window series.

ERA5 is a reanalysis, never an observation.  The archive series and every
district aggregate carry ``class: "reanalysis"``.  The current-window series is
stored in a separate file and is labelled ``scenario`` with
``source_kind: "model_current_window"`` so it cannot be confused with the
archive or with a gauge/SAR observation.
"""
from __future__ import annotations

import json
import math
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from shapely.geometry import box, shape
from shapely.validation import make_valid

from .config import Config
from .geo import load_geojson, project_geom
from .http import FetchError, fetch_bytes
from .util import StageRecord, atomic_write_json, ensure_dirs, utc_now

CLASS_REANALYSIS = "reanalysis"
CLASS_SCENARIO = "scenario"

# REVIEW-22: fetch only the 122-day JJAS window, in 32-point calls.  Open-Meteo
# weights a call by locations x days, so the old 128-point x 4,017-day calls were
# over the hourly cap.  Cache keys are (year, chunk start), which makes a
# rate-limited run resumable without mixing years or partial windows.
CHUNK_SIZE = 32
ARCHIVE_RETRIES = 6
ARCHIVE_SLEEP_S = 10.0
OFF_SEASON_CAVEAT = (
    "Only the monsoon season is published; off-season days are omitted because "
    "the fetch is rate-limited, not because they are unavailable."
)


class ArchiveRateLimited(RuntimeError):
    """Raised when Open-Meteo returns HTTP 429 for an archive chunk."""

    def __init__(self, message: str, cached_pairs: list[tuple[int, int]]):
        super().__init__(message)
        self.cached_pairs = cached_pairs


def _jjas_window(year: int) -> tuple[str, str, list[str]]:
    start = date(year, 6, 1)
    end = date(year, 9, 30)
    days = [
        (start + timedelta(days=offset)).isoformat()
        for offset in range((end - start).days + 1)
    ]
    if len(days) != 122:
        raise RuntimeError(f"stage 17: JJAS window {year} has {len(days)} days, expected 122")
    return start.isoformat(), end.isoformat(), days


def _archive_pairs(
    cache_dir: Path, years: list[int], chunk_starts: list[int]
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    cached: list[tuple[int, int]] = []
    missing: list[tuple[int, int]] = []
    for year in years:
        for start_index in chunk_starts:
            path = cache_dir / f"archive-{year}-{start_index:03d}.json"
            if path.exists() and path.stat().st_size > 0:
                cached.append((year, start_index))
            else:
                missing.append((year, start_index))
    return cached, missing


def _format_pairs(pairs: list[tuple[int, int]], limit: int = 40) -> str:
    shown = ", ".join(f"{year}:{start_index:03d}" for year, start_index in pairs[:limit])
    if len(pairs) > limit:
        shown += f", ... (+{len(pairs) - limit} more)"
    return shown


def _grid_nodes(cfg: Config) -> tuple[list[float], list[float]]:
    source = cfg.sources["era5"]
    step = float(source["grid_resolution_deg"])
    min_lon, min_lat, max_lon, max_lat = cfg.aoi.bbox
    lon_start = math.floor(min_lon / step) * step
    lon_end = math.ceil(max_lon / step) * step
    lat_start = math.floor(min_lat / step) * step
    lat_end = math.ceil(max_lat / step) * step
    lons = np.round(np.arange(lon_start, lon_end + step * 0.5, step), 6).tolist()
    lats = np.round(np.arange(lat_start, lat_end + step * 0.5, step), 6).tolist()
    return [float(value) for value in lons], [float(value) for value in lats]


def _parse_archive(payload: bytes, expected_days: int, label: str) -> dict:
    data = json.loads(payload.decode("utf-8"))
    entries = data if isinstance(data, list) else [data]
    out = []
    for entry in entries:
        daily = entry.get("daily") or {}
        times = daily.get("time") or []
        values = daily.get("precipitation_sum")
        if len(times) != expected_days or not isinstance(values, list) or len(values) != expected_days:
            raise RuntimeError(
                f"stage 17: {label} has {len(times)} days and "
                f"{len(values) if isinstance(values, list) else 'no'} values, expected {expected_days}"
            )
        if any(value is None for value in values):
            raise RuntimeError(f"stage 17: {label} contains a null precipitation value")
        numeric = np.asarray(values, dtype=np.float64)
        if not np.all(np.isfinite(numeric)) or float(numeric.min()) < 0.0:
            raise RuntimeError(f"stage 17: {label} precipitation is non-finite or negative")
        out.append(
            {
                "latitude": float(entry.get("latitude")),
                "longitude": float(entry.get("longitude")),
                "time": times,
                "precipitation_sum": numeric.tolist(),
            }
        )
    return {"entries": out}


def _fetch_archive(cfg: Config, cache_dir: Path, refresh: bool, lons: list[float], lats: list[float]) -> dict:
    source = cfg.sources["era5"]
    mean_start = int(source["mean_start_year"])
    mean_end = int(source["mean_end_year"])
    years = list(range(mean_start, mean_end + 1))
    points = [(lon, lat) for lat in lats for lon in lons]
    chunk_starts = list(range(0, len(points), CHUNK_SIZE))
    batch_size = CHUNK_SIZE
    point_series: list[list[float]] = [[] for _ in points]
    dates: list[str] = []

    for year in years:
        start, end, expected_dates = _jjas_window(year)
        year_dates: list[str] | None = None
        for start_index in chunk_starts:
            batch = points[start_index : start_index + batch_size]
            chunk_len = len(batch)
            latitude = ",".join(f"{lat:.6f}" for _, lat in batch)
            longitude = ",".join(f"{lon:.6f}" for lon, _ in batch)
            params = (
                f"latitude={latitude}&longitude={longitude}"
                f"&start_date={start}&end_date={end}"
                "&daily=precipitation_sum&timezone=UTC&models=era5"
            )
            url = f"{source['endpoint']}?{params}"
            # REVIEW-22: one cache file per (year, chunk).  The old full-year
            # archive-batch-*.json files are deliberately ignored: they contain
            # 4,017 days and cannot satisfy the 122-day parser contract.
            cache_path = cache_dir / f"archive-{year}-{start_index:03d}.json"
            try:
                result = fetch_bytes(
                    cfg,
                    url,
                    cache_path,
                    refresh=refresh,
                    timeout_s=300,
                    retries=ARCHIVE_RETRIES,
                    abort_on_rate_limit=True,
                )
            except FetchError as exc:
                if "HTTP 429" in str(exc):
                    cached, _missing = _archive_pairs(cache_dir, years, chunk_starts)
                    message = (
                        f"stage 17: Open-Meteo HTTP 429 while fetching {year} chunk "
                        f"{start_index:03d}; stopping without writing rainfall. "
                        f"{len(cached)} of {len(years) * len(chunk_starts)} "
                        f"(year, chunk) pairs are cached"
                    )
                    if cached:
                        message += f": {_format_pairs(cached)}"
                    message += ". Re-run build-rainfall to resume from the cache."
                    raise ArchiveRateLimited(message, cached) from exc
                raise
            parsed = _parse_archive(
                result.payload,
                len(expected_dates),
                f"archive {year} chunk {start_index:03d}",
            )
            if len(parsed["entries"]) != chunk_len:
                raise RuntimeError(
                    f"stage 17: archive {year} chunk {start_index:03d} returned "
                    f"{len(parsed['entries'])} locations, expected {chunk_len}"
                )
            entry_dates = parsed["entries"][0]["time"]
            if entry_dates != expected_dates:
                missing = sorted(set(expected_dates) - set(entry_dates))
                extra = sorted(set(entry_dates) - set(expected_dates))
                raise RuntimeError(
                    f"stage 17: archive {year} chunk {start_index:03d} date window "
                    f"does not match 06-01..09-30 (missing={missing[:3]}, extra={extra[:3]})"
                )
            if year_dates is None:
                year_dates = entry_dates
                dates.extend(entry_dates)
            elif entry_dates != year_dates:
                raise RuntimeError(
                    f"stage 17: archive {year} chunk {start_index:03d} date order "
                    "differs from the first chunk of the same year"
                )
            for offset, entry in enumerate(parsed["entries"]):
                if entry["time"] != year_dates:
                    raise RuntimeError(
                        f"stage 17: archive {year} chunk {start_index:03d} location "
                        f"{start_index + offset} has a different date window"
                    )
                values = entry["precipitation_sum"]
                if len(values) != len(year_dates):
                    raise RuntimeError(
                        f"stage 17: archive {year} chunk {start_index:03d} location "
                        f"{start_index + offset} has {len(values)} values for "
                        f"{len(year_dates)} dates"
                    )
                point_series[start_index + offset].extend(values)
            if not result.from_cache:
                # REVIEW-22: at least 10 s between Open-Meteo archive calls.
                time.sleep(ARCHIVE_SLEEP_S)

    expected_all_dates: list[str] = []
    for year in years:
        expected_all_dates.extend(_jjas_window(year)[2])
    if len(dates) != len(set(dates)):
        duplicates = sorted({day for day in dates if dates.count(day) > 1})
        raise RuntimeError(
            f"stage 17: concatenated JJAS series has duplicate dates: {duplicates[:5]}"
        )
    missing_dates = [day for day in expected_all_dates if day not in set(dates)]
    extra_dates = [day for day in dates if day not in set(expected_all_dates)]
    if missing_dates or extra_dates or dates != expected_all_dates:
        raise RuntimeError(
            "stage 17: concatenated JJAS series is not the ordered 2015-2025 window "
            f"(missing={missing_dates[:5]}, extra={extra_dates[:5]}, "
            f"days={len(dates)}/{len(expected_all_dates)})"
        )

    combined: list[dict] = []
    for (lon, lat), values in zip(points, point_series):
        if len(values) != len(dates):
            raise RuntimeError(
                f"stage 17: grid point ({lon}, {lat}) has {len(values)} values for "
                f"{len(dates)} dates"
            )
        combined.append(
            {
                "latitude": lat,
                "longitude": lon,
                "requested_lon": lon,
                "requested_lat": lat,
                "time": dates,
                "precipitation_sum": values,
            }
        )

    return {
        "time": dates,
        "points": combined,
        "query": {
            "endpoint": source["endpoint"],
            "daily": "precipitation_sum",
            "start_date": f"{years[0]}-06-01",
            "end_date": f"{years[-1]}-09-30",
            "window": f"JJAS 06-01..09-30, {years[0]}-{years[-1]}",
            "off_season_included": False,
            "caveat": OFF_SEASON_CAVEAT,
            "years": years,
            "window_days_per_year": 122,
            "day_count": len(dates),
            "timezone": "UTC",
            "models": "era5",
            "grid_resolution_deg": float(source["grid_resolution_deg"]),
            "grid_resolution_km": float(source["grid_resolution_km"]),
            "point_count": len(combined),
            "units": source["units"],
            "chunk_size": batch_size,
            "batches": int(math.ceil(len(points) / batch_size)) * len(years),
            "cache_pattern": "archive-{year}-{start_index:03d}.json",
            "rate_limit_note": (
                "Calls are spaced by at least 10 s with retries=6; a 429 stops the "
                "stage so the next run resumes from cached (year, chunk) pairs."
            ),
        },
    }


def _fetch_current_window(cfg: Config, cache_dir: Path, refresh: bool) -> dict:
    source = cfg.sources["era5"]
    min_lon, min_lat, max_lon, max_lat = cfg.aoi.bbox
    lon = round((min_lon + max_lon) / 2.0, 4)
    lat = round((min_lat + max_lat) / 2.0, 4)
    params = (
        f"latitude={lat}&longitude={lon}"
        f"&daily=precipitation_sum&timezone=UTC"
        f"&past_days={int(source['forecast_past_days'])}"
        f"&forecast_days={int(source['forecast_days'])}"
    )
    url = f"{source['forecast_endpoint']}?{params}"
    cache_path = cache_dir / "current-window.json"
    result = fetch_bytes(cfg, url, cache_path, refresh=refresh, timeout_s=120, retries=4)
    payload = json.loads(result.payload.decode("utf-8"))
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    values = daily.get("precipitation_sum") or []
    if len(times) != len(values) or not times:
        raise RuntimeError("stage 17: current-window response has no usable daily series")
    # The forecast endpoint returns null for days it cannot fill. Those days are
    # dropped and counted, never interpolated or zero-filled.
    numeric = np.asarray([np.nan if value is None else value for value in values], dtype=np.float64)
    finite = np.isfinite(numeric)
    dropped_null_days = int((~finite).sum())
    if not bool(finite.any()):
        raise RuntimeError("stage 17: current-window response has no finite precipitation values")
    if float(np.nanmin(numeric)) < 0.0:
        raise RuntimeError("stage 17: current-window precipitation is negative")
    return {
        "endpoint": source["forecast_endpoint"],
        "query": {
            "latitude": lat,
            "longitude": lon,
            "daily": "precipitation_sum",
            "timezone": "UTC",
            "past_days": int(source["forecast_past_days"]),
            "forecast_days": int(source["forecast_days"]),
            "units": source["units"],
        },
        "retrieved_at": result.fetched_at if result.fetched_at != "cache" else utc_now(),
        "window_start": times[0],
        "window_end": times[-1],
        "dropped_null_days": dropped_null_days,
        "points": [
            {"date": day, "value": round(float(value), 3)}
            for day, value, keep in zip(times, numeric, finite)
            if keep
        ],
    }


def _district_weights(
    cfg: Config,
    districts_path: Path,
    lons: list[float],
    lats: list[float],
) -> list[dict]:
    step = float(cfg.sources["era5"]["grid_resolution_deg"])
    half = step / 2.0
    districts = load_geojson(districts_path)
    cells = []
    for lat in lats:
        for lon in lons:
            cell = project_geom(box(lon - half, lat - half, lon + half, lat + half), "EPSG:4326", cfg.aoi.analysis_crs)
            cells.append(cell)
    rows = []
    for feature in districts.get("features", []):
        props = feature.get("properties", {})
        geom = project_geom(make_valid(shape(feature["geometry"])), "EPSG:4326", cfg.aoi.analysis_crs)
        if geom.is_empty:
            raise RuntimeError(f"stage 17: district {props.get('district_id')} has an empty polygon")
        weights = np.zeros(len(cells), dtype=np.float64)
        for index, cell in enumerate(cells):
            if not geom.intersects(cell):
                continue
            intersection = geom.intersection(cell)
            if intersection.is_empty:
                continue
            # EPSG:32646 is metric and effectively equal-area at this scale; a
            # planar intersection area is the weight used for the areal mean.
            weights[index] = intersection.area / 1_000_000.0
        total = float(weights.sum())
        if total <= 0.0:
            raise RuntimeError(
                f"stage 17: district {props.get('district_id')} does not intersect the ERA5 grid"
            )
        rows.append(
            {
                "district_id": str(props["district_id"]),
                "name": str(props.get("name", props["district_id"])),
                "weights": (weights / total).tolist(),
                "grid_cells": int((weights > 0).sum()),
                "covered_area_km2": round(total, 3),
            }
        )
    return rows


def _state_weights(cfg: Config, state_path: Path, lons: list[float], lats: list[float]) -> np.ndarray:
    step = float(cfg.sources["era5"]["grid_resolution_deg"])
    half = step / 2.0
    state = load_geojson(state_path)
    feature = state.get("features", [{}])[0]
    geom = project_geom(make_valid(shape(feature["geometry"])), "EPSG:4326", cfg.aoi.analysis_crs)
    weights = np.zeros(len(lons) * len(lats), dtype=np.float64)
    index = 0
    for lat in lats:
        for lon in lons:
            cell = project_geom(box(lon - half, lat - half, lon + half, lat + half), "EPSG:4326", cfg.aoi.analysis_crs)
            if geom.intersects(cell):
                intersection = geom.intersection(cell)
                if not intersection.is_empty:
                    weights[index] = intersection.area / 1_000_000.0
            index += 1
    total = float(weights.sum())
    if total <= 0.0:
        raise RuntimeError("stage 17: the Assam state outline does not intersect the ERA5 grid")
    return weights / total


def _monsoon_totals(
    values: np.ndarray,
    dates: list[str],
    target_year: int,
    mean_start: int,
    mean_end: int,
    months: list[int],
) -> tuple[float, float, list[dict]]:
    year = np.asarray([int(day[0:4]) for day in dates], dtype=np.int64)
    month = np.asarray([int(day[5:7]) for day in dates], dtype=np.int64)
    in_season = np.isin(month, months)
    seasons = []
    for season_year in range(mean_start, mean_end + 1):
        mask = in_season & (year == season_year)
        seasons.append(
            {
                "year": season_year,
                "monsoon_mm": round(float(values[mask].sum()), 2),
                "days": int(mask.sum()),
            }
        )
    total_2022 = next(
        (entry["monsoon_mm"] for entry in seasons if entry["year"] == target_year),
        None,
    )
    if total_2022 is None:
        raise RuntimeError(f"stage 17: no monsoon season for {target_year}")
    mean = round(float(np.mean([entry["monsoon_mm"] for entry in seasons])), 2)
    return float(total_2022), mean, seasons


def run(
    cfg: Config,
    cache_dir: Path,
    out_rainfall: Path,
    out_forecast: Path,
    refresh: bool = False,
) -> dict:
    ensure_dirs()
    source = cfg.sources["era5"]
    cache_dir = cache_dir if cache_dir.is_absolute() else cfg.root / cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    districts_path = cfg.root / "public" / "data" / "admin" / "assam-districts.geojson"
    state_path = cfg.root / "public" / "data" / "admin" / "assam-state.geojson"
    stage = StageRecord(
        "17",
        "build-rainfall",
        inputs=[districts_path, state_path],
    )
    out_rainfall = out_rainfall if out_rainfall.is_absolute() else cfg.root / out_rainfall
    out_forecast = out_forecast if out_forecast.is_absolute() else cfg.root / out_forecast

    lons, lats = _grid_nodes(cfg)
    archive = _fetch_archive(cfg, cache_dir, refresh, lons, lats)
    archive["query"]["grid_definition"] = (
        f"regular {float(cfg.sources['era5']['grid_resolution_deg'])} degree cell-centre "
        f"nodes from lon {lons[0]} to {lons[-1]} and lat {lats[0]} to {lats[-1]}; "
        f"{len(lons)} x {len(lats)} = {len(lons) * len(lats)} nodes"
    )
    dates = archive["time"]
    matrix = np.asarray(
        [entry["precipitation_sum"] for entry in archive["points"]], dtype=np.float64
    )
    if matrix.shape != (len(lons) * len(lats), len(dates)):
        raise RuntimeError(f"stage 17: archive matrix shape {matrix.shape} does not match the grid")
    if matrix.min() < 0.0 or not np.all(np.isfinite(matrix)):
        raise RuntimeError("stage 17: archive precipitation is non-finite or negative")

    state_weights = _state_weights(cfg, state_path, lons, lats)
    aoi_daily = state_weights @ matrix
    district_rows = _district_weights(cfg, districts_path, lons, lats)
    target_year = int(source["target_year"])
    mean_start = int(source["mean_start_year"])
    mean_end = int(source["mean_end_year"])
    months = [int(value) for value in source["monsoon_months"]]
    data_as_of = str(archive["query"]["end_date"])
    aoi_2022, aoi_mean, aoi_seasons = _monsoon_totals(
        aoi_daily, dates, target_year, mean_start, mean_end, months
    )

    district_monsoon = []
    for row in district_rows:
        daily = np.asarray(row["weights"], dtype=np.float64) @ matrix
        year_2022, mean, _ = _monsoon_totals(
            daily, dates, target_year, mean_start, mean_end, months
        )
        district_monsoon.append(
            {
                "district_id": row["district_id"],
                "name": row["name"],
                "monsoon_2022_mm": round(year_2022, 2),
                "monsoon_2015_2025_mean_mm": round(mean, 2),
                "anomaly_2022_vs_mean_mm": round(year_2022 - mean, 2),
                "anomaly_2022_vs_mean_pct": (
                    round(100.0 * (year_2022 - mean) / mean, 2) if mean > 0 else None
                ),
                "class": CLASS_REANALYSIS,
                "data_as_of": data_as_of,
                "grid_cells": row["grid_cells"],
                "covered_area_km2": row["covered_area_km2"],
            }
        )
    if len(district_monsoon) != 33:
        raise RuntimeError(f"stage 17: expected 33 district totals, found {len(district_monsoon)}")

    retrieved_at = utc_now()
    rainfall = {
        "schema_version": "1.0.0",
        "dataset_version": str(cfg.pipeline["dataset_version"]),
        "class": CLASS_REANALYSIS,
        "data_as_of": data_as_of,
        "source": {
            "name": source["name"],
            "endpoint": source["endpoint"],
            "query": archive["query"],
            "retrieved_at": retrieved_at,
            "model": source["model"],
            "grid_resolution_deg": float(source["grid_resolution_deg"]),
            "grid_resolution_km": float(source["grid_resolution_km"]),
            "units": source["units"],
            "licence": source["licence"],
            "caveat": f"{source['caveat']} {OFF_SEASON_CAVEAT}",
            "retrieval_note": (
                "The archive response is cached per (year, chunk); retrieved_at is "
                "the build time of this published file. The published series is the "
                "ordered JJAS window only."
            ),
        },
        "monsoon_definition": {
            "months": months,
            "label": "JJAS (June-September)",
            "window": "06-01..09-30",
            "off_season_included": False,
            "target_year": target_year,
            "mean_start_year": mean_start,
            "mean_end_year": mean_end,
        },
        "series": [
            {
                "id": "era5_rainfall_aoi",
                "label": "ERA5 daily precipitation (AOI areal mean)",
                "unit": source["units"],
                "class": CLASS_REANALYSIS,
                "source_note": (
                    "Area-weighted mean of the 0.25 degree ERA5 grid over the Assam "
                    "state polygon, JJAS 06-01..09-30 only. Reanalysis, not a gauge "
                    "observation."
                ),
                "data_as_of": data_as_of,
                "points": [
                    {"date": day, "value": round(float(value), 3)}
                    for day, value in zip(dates, aoi_daily.tolist())
                ],
            }
        ],
        "aoi_monsoon": {
            "monsoon_2022_mm": round(aoi_2022, 2),
            "monsoon_2015_2025_mean_mm": round(aoi_mean, 2),
            "anomaly_2022_vs_mean_mm": round(aoi_2022 - aoi_mean, 2),
            "anomaly_2022_vs_mean_pct": (
                round(100.0 * (aoi_2022 - aoi_mean) / aoi_mean, 2) if aoi_mean > 0 else None
            ),
            "seasons": aoi_seasons,
            "class": CLASS_REANALYSIS,
            "data_as_of": data_as_of,
        },
        "district_monsoon": district_monsoon,
    }
    atomic_write_json(out_rainfall, rainfall, indent=2, sort_keys=False)

    forecast = _fetch_current_window(cfg, cache_dir, refresh)
    forecast_payload = {
        "schema_version": "1.0.0",
        "dataset_version": str(cfg.pipeline["dataset_version"]),
        "class": CLASS_SCENARIO,
        "data_as_of": forecast["retrieved_at"][:10],
        "source": {
            "name": "Open-Meteo current-window model guidance (stored separately)",
            "endpoint": forecast["endpoint"],
            "query": forecast["query"],
            "retrieved_at": forecast["retrieved_at"],
            "units": source["units"],
            "licence": source["licence"],
            "note": (
                "This is a model current-window series, not an archive reanalysis and not an "
                "observation. It is stored in a separate file and is never mixed into the ERA5 "
                "archive series or used to drive the flood scenario."
            ),
        },
        "forecast_window": {
            "id": "open_meteo_current_window",
            "label": "Open-Meteo current-window daily precipitation (AOI centre)",
            "class": CLASS_SCENARIO,
            "source_kind": "model_current_window",
            "data_as_of": forecast["retrieved_at"][:10],
            "window_start": forecast["window_start"],
            "window_end": forecast["window_end"],
            "points": forecast["points"],
        },
    }
    atomic_write_json(out_forecast, forecast_payload, indent=2, sort_keys=False)

    stage.source(source["name"], source["endpoint"], source["licence"])
    stage.source(source["name"] + " current-window endpoint", source["forecast_endpoint"], source["licence"])
    stage.out(out_rainfall, out_forecast)
    stage.metric("grid_lon_count", len(lons))
    stage.metric("grid_lat_count", len(lats))
    stage.metric("grid_point_count", len(lons) * len(lats))
    stage.metric("day_count", len(dates))
    stage.metric("district_count", len(district_monsoon))
    stage.metric("aoi_monsoon_2022_mm", round(aoi_2022, 2))
    stage.metric("aoi_monsoon_mean_mm", round(aoi_mean, 2))
    stage.metric("archive_bytes", out_rainfall.stat().st_size)
    stage.metric("forecast_bytes", out_forecast.stat().st_size)
    stage.finish(
        "ERA5 reanalysis daily precipitation on a documented 0.25 degree grid "
        f"({len(lons)} x {len(lats)} nodes, {len(dates)} days = JJAS 06-01..09-30 for "
        f"{mean_start}-{mean_end}), area-weighted over the existing Assam district "
        "polygons. 2022 JJAS totals and the 2015-2025 JJAS mean are published per "
        "district. Off-season days are omitted because the Open-Meteo fetch is "
        "rate-limited, not because they are unavailable. All archive series carry "
        "class=reanalysis. The current-window endpoint is stored separately, labelled "
        "scenario/model_current_window, and never presented as observed. ERA5 is "
        "model-based and biased in complex terrain."
    )
    print(
        f"[17] ok: {len(lons)}x{len(lats)} ERA5 nodes x {len(dates)} JJAS days, "
        f"{len(district_monsoon)} district totals, AOI 2022 JJAS {aoi_2022:,.0f} mm "
        f"(mean {aoi_mean:,.0f} mm), rainfall {out_rainfall.stat().st_size / 1024:.1f} KB, "
        f"current-window {out_forecast.stat().st_size / 1024:.1f} KB"
    )
    return rainfall
