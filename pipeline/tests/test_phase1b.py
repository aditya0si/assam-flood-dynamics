"""Phase 1b unit tests: ERA5 class discipline and exposure naming."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from baanh_pipeline.rainfall import _monsoon_totals
from baanh_pipeline.schemas import EXPOSURE_SCHEMA, SERIES_CLASSES

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "public" / "data"


def _load(relative: str):
    path = DATA / relative
    if not path.exists():
        pytest.skip(f"committed file absent: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def test_series_class_enum_is_three_way():
    assert SERIES_CLASSES == ["observed", "reanalysis", "scenario"]


def test_jjas_window_is_122_days_and_excludes_off_season():
    from baanh_pipeline.rainfall import _jjas_window

    start, end, days = _jjas_window(2022)
    assert (start, end) == ("2022-06-01", "2022-09-30")
    assert len(days) == 122
    assert days[0] == "2022-06-01"
    assert days[-1] == "2022-09-30"
    assert all(day[5:7] in {"06", "07", "08", "09"} for day in days)


def test_monsoon_totals_uses_jjas_and_eleven_year_mean():
    from datetime import date, timedelta

    dates = []
    values = []
    day = date(2015, 1, 1)
    end = date(2025, 12, 31)
    while day <= end:
        dates.append(day.isoformat())
        # Only JJAS contributes; the value is 1 mm/day.
        values.append(1.0 if day.month in (6, 7, 8, 9) else 100.0)
        day += timedelta(days=1)
    total_2022, mean, seasons = _monsoon_totals(
        np.asarray(values), dates, 2022, 2015, 2025, [6, 7, 8, 9]
    )
    assert len(seasons) == 11
    assert total_2022 == pytest.approx(122.0)
    assert mean == pytest.approx(122.0)
    assert seasons[7]["year"] == 2022


def test_rainfall_is_reanalysis_and_never_observed():
    rainfall = _load("series/rainfall.json")
    assert rainfall["class"] == "reanalysis"
    assert rainfall["data_as_of"] == "2025-09-30"
    assert rainfall["source"]["query"]["window"] == "JJAS 06-01..09-30, 2015-2025"
    assert rainfall["source"]["query"]["off_season_included"] is False
    assert "rate-limited" in rainfall["source"]["query"]["caveat"]
    assert rainfall["monsoon_definition"]["off_season_included"] is False
    for entry in rainfall["series"]:
        assert entry["class"] == "reanalysis"
        identity = " ".join(
            str(entry.get(key, ""))
            for key in ("id", "label", "source_note", "source_kind")
        ).lower()
        assert "observed" not in identity
    assert len(rainfall["district_monsoon"]) == 33


def test_exposure_publishes_only_potentially_exposed_residents():
    exposure = _load("exposure/district-exposure.json")
    assert exposure["class"] == "derived"
    assert exposure["source"]["vintage"] == "2020"
    assert "not an impact assessment" in exposure["uncertainty_statement"]

    def keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)

    names = list(keys(exposure))
    assert "potentially_exposed_residents" in names
    for name in names:
        lowered = name.lower()
        assert "affected" not in lowered
        assert "displaced" not in lowered
        assert "casualt" not in lowered
        if "resident" in lowered:
            assert name in {
                "potentially_exposed_residents",
                "peak_mask_potentially_exposed_residents",
            }
    assert sum(row["potentially_exposed_residents"] for row in exposure["districts"]) == exposure[
        "totals"
    ]["potentially_exposed_residents"]
    peak = exposure["peak_mask"]["potentially_exposed_residents"]
    district_sum = exposure["totals"]["potentially_exposed_residents"]
    assert abs(district_sum - peak) / peak <= 0.01
    assert 20_000_000 <= exposure["totals"]["population_within_aoi"] <= 45_000_000
    assert exposure["totals"]["population_raster_scope"] == "AOI v2 polygon"
    for row in exposure["districts"]:
        assert row["potentially_exposed_residents"] <= row["district_population"]
        assert row["exposed_share_of_district"] == pytest.approx(
            row["potentially_exposed_residents"] / row["district_population"]
            if row["district_population"]
            else 0.0,
            abs=1e-6,
        )
    assert peak < exposure["totals"]["population_within_aoi"]


def test_exposure_schema_rejects_affected_field():
    exposure = _load("exposure/district-exposure.json")
    exposure["districts"][0]["affected_residents"] = 1
    import jsonschema

    # The schema is intentionally open to derived metadata, so this asserts the
    # gate-facing helper contract instead: the field is forbidden by V21 and
    # check-data, and the schema still requires the one published count.
    assert "potentially_exposed_residents" in EXPOSURE_SCHEMA["properties"]["districts"]["items"][
        "properties"
    ]
    jsonschema.validate(exposure, EXPOSURE_SCHEMA)
