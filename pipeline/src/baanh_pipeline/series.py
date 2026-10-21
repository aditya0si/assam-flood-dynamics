"""Stage 11 — synthetic monsoon series and DEM/HAND cross-sections."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import rasterio

from .config import Config
from .geo import geod, load_geojson, project_coords
from .util import StageRecord, atomic_write_json, ensure_dirs


def run(
    cfg: Config,
    scenario_path: Path,
    summary_path: Path,
    dem_path: Path,
    channels_path: Path,
    transects_path: Path,
    out_series: Path,
    out_profiles: Path,
) -> dict:
    ensure_dirs()
    stage = StageRecord(
        "11",
        "build-series",
        inputs=[scenario_path, summary_path, dem_path, channels_path, transects_path],
    )
    scenario = cfg.scenario
    version = cfg.pipeline["dataset_version"]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    step_summaries = summary["steps"]
    if len(step_summaries) != scenario.step_count:
        raise RuntimeError("stage 11: flood summary step count mismatch")

    series_defs = [
        ("rainfall", "Rainfall (synthetic)", "mm/day", "synthetic", "rainfall_mm_day",
         "Parameterised monsoon curve; no gauge record."),
        ("mainstem_stage", "Main-stem stage anomaly (synthetic)", "m", "synthetic", "mainstem_stage_m",
         "Parameterised stage anomaly relative to a pre-monsoon baseline; not a gauge reading."),
        ("backwater", "Backwater allowance (synthetic)", "m", "synthetic", "backwater_m",
         "Declared additive allowance for tributary/backwater stacking; not a solved backwater term."),
        ("stage_above_drainage", "Stage above local drainage (scenario)", "m", "scenario", "stage_m",
         "Synthetic stage applied to the HAND threshold; not a gauge reading."),
    ]
    series = []
    for series_id, label, unit, cls, key, note in series_defs:
        points = [
            {
                "step": int(step["step"]),
                "day": int(step["day_offset"]),
                "value": step[key],
            }
            for step in step_summaries
        ]
        if len(points) != 12:
            raise RuntimeError(f"stage 11: series {series_id} has {len(points)} points")
        series.append(
            {
                "id": series_id,
                "label": label,
                "unit": unit,
                "class": cls,
                "source_note": note,
                "points": points,
            }
        )
    series_payload = {
        "schema_version": "1.0.0",
        "dataset_version": version,
        "scenario_id": scenario.scenario_id,
        "class": "synthetic",
        "series": series,
        "threshold": {
            "id": "scenario_threshold",
            "label": "Scenario threshold",
            "value": scenario.threshold_m,
            "unit": "m",
            "class": "scenario",
            "note": "Model parameter, not an official danger level.",
        },
    }
    out_series.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_series, series_payload, indent=2, sort_keys=False)

    transect_cfg = json.loads(transects_path.read_text(encoding="utf-8"))
    transforms = [float(step["stage_m"]) for step in scenario.steps]
    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        transform = src.transform
        height = src.height
        width = src.width
        dem_nodata = float(src.nodata if src.nodata is not None else cfg.aoi.nodata)
    with rasterio.open(channels_path) as src:
        channel = src.read(1) > 0
    nearest_path = dem_path.parent / "nearest-channel-elevation-90m.tif"
    if not nearest_path.exists():
        raise RuntimeError(
            f"stage 11: nearest-channel-elevation raster missing at {nearest_path}; "
            "re-run stage 08"
        )
    with rasterio.open(nearest_path) as src:
        nearest_z = src.read(1)
    hand_path = dem_path.parent / "hand-90m.tif"
    if not hand_path.exists():
        raise RuntimeError(f"stage 11: HAND raster missing at {hand_path}; re-run stage 08")
    with rasterio.open(hand_path) as src:
        hand = src.read(1)
    hand_nodata = float(src.nodata if src.nodata is not None else cfg.aoi.nodata)
    stage.inputs.extend([nearest_path, hand_path])

    spacing_km = float(cfg.pipeline["series"]["transect_spacing_km"])
    min_valid = int(cfg.pipeline["series"]["min_valid_samples"])
    transects_out = []
    for transect in transect_cfg.get("transects", []):
        start = transect["start"]
        end = transect["end"]
        _, _, length_m = geod().inv(start[0], start[1], end[0], end[1])
        length_km = length_m / 1000.0
        count = max(2, int(math.ceil(length_km / spacing_km)) + 1)
        intermediates = geod().npts(start[0], start[1], end[0], end[1], count - 2)
        points = [tuple(start)] + list(intermediates) + [tuple(end)]
        samples = []
        invalid = 0
        for point_index, (lon, lat) in enumerate(points):
            projected = project_coords([(lon, lat)], cfg.aoi.output_crs, cfg.aoi.analysis_crs)[0]
            col, row = ~transform * projected
            col = int(math.floor(col))
            row = int(math.floor(row))
            if row < 0 or col < 0 or row >= height or col >= width:
                invalid += 1
                continue
            ground = float(dem[row, col])
            hand_value = float(hand[row, col])
            channel_z = float(nearest_z[row, col])
            if ground == dem_nodata or hand_value == hand_nodata or channel_z == dem_nodata:
                invalid += 1
                continue
            _, _, distance_m = geod().inv(start[0], start[1], lon, lat)
            # REVIEW-03 B2: depth = stage - max(HAND, 0), the same clamped
            # bathtub convention as stage 09, so depth never exceeds the stage.
            depth = [max(0.0, stage_m - max(hand_value, 0.0)) for stage_m in transforms]
            water = [ground + value for value in depth]
            samples.append(
                {
                    "distance_km": round(distance_m / 1000.0, 4),
                    "lon": round(lon, 5),
                    "lat": round(lat, 5),
                    "ground_m": round(ground, 2),
                    "hand_m": round(hand_value, 2),
                    "water_surface_m": [round(value, 3) for value in water],
                    "depth_m": [round(value, 3) for value in depth],
                }
            )
        if len(samples) < min_valid:
            raise RuntimeError(
                f"stage 11: transect {transect['transect_id']} has {len(samples)} valid "
                f"samples, below {min_valid}"
            )
        transects_out.append(
            {
                "transect_id": transect["transect_id"],
                "label": transect["label"],
                "start": start,
                "end": end,
                "length_km": round(length_km, 3),
                "sample_count": len(samples),
                "samples": samples,
                "class": "derived",
                "label_note": "DEM + HAND profile; not a surveyed section.",
                "invalid_samples_omitted": invalid,
            }
        )

    profiles = {
        "schema_version": "1.0.0",
        "dataset_version": version,
        "scenario_id": scenario.scenario_id,
        "class": "derived",
        "transects": transects_out,
    }
    out_profiles.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_profiles, profiles, indent=None)

    # Stage assertions: series equality and a channel sanity check.
    for series_item in series:
        for point in series_item["points"]:
            step = step_summaries[point["step"]]
            key = {
                "rainfall": "rainfall_mm_day",
                "mainstem_stage": "mainstem_stage_m",
                "backwater": "backwater_m",
                "stage_above_drainage": "stage_m",
            }[series_item["id"]]
            if abs(float(point["value"]) - float(step[key])) > 1e-9:
                raise RuntimeError(
                    f"stage 11: series {series_item['id']} step {point['step']} differs from summary"
                )
    total_samples = sum(t["sample_count"] for t in transects_out)
    stage.out(out_series, out_profiles)
    stage.metric("series_count", len(series))
    stage.metric("transect_count", len(transects_out))
    stage.metric("valid_samples", total_samples)
    stage.metric("channel_cells", int(channel.sum()))
    stage.finish(
        "Series values are copied from flood-summary.json (no independent curve). "
        "Cross-sections sample the DEM, HAND and nearest-channel elevation at 2 km; "
        "nodata samples are omitted and counted."
    )
    print(
        f"[11] ok: {len(series)} series x 12 points, {len(transects_out)} transects, "
        f"{total_samples} valid samples, series {out_series.stat().st_size / 1024:.1f} KB, "
        f"profiles {out_profiles.stat().st_size / 1024:.1f} KB"
    )
    return profiles
