"""Tests for risk weights and class thresholds."""
from __future__ import annotations

import json
from pathlib import Path

from baanh_pipeline.config import load_config
from baanh_pipeline.risk import _duration_weights, _severity


def test_duration_weights_sum_to_total_days():
    cfg = load_config()
    weights = _duration_weights(cfg.scenario.days)
    assert abs(float(weights.sum()) - 136.0) < 1e-3
    assert weights[0] == 7.0
    assert weights[-1] == 7.5


def test_scenario_stage_arithmetic():
    cfg = load_config()
    for step in cfg.scenario.steps:
        assert abs(
            float(step["stage_m"])
            - (float(step["mainstem_stage_m"]) + float(step["backwater_m"]))
        ) < 1e-9


def test_district_weights_are_two_live_drivers():
    cfg = load_config()
    district = cfg.pipeline["risk"]["district"]
    weights = district["weights"]
    assert set(weights) == {"area_share", "duration"}
    assert abs(float(weights["area_share"]) - 0.5625) < 1e-12
    assert abs(float(weights["duration"]) - 0.4375) < 1e-12
    assert abs(sum(float(value) for value in weights.values()) - 1.0) < 1e-12
    assert district["weights_version"] == "area-duration-v1"


def test_severity_is_a_separate_zero_to_hundred_product_profile():
    rows = [
        {"name": "A", "depth_over_1_5m_share": 0.9, "median_depth_m": 3.7, "mean_duration_days": 110.0},
        {"name": "B", "depth_over_1_5m_share": 0.7, "median_depth_m": 2.0, "mean_duration_days": 60.0},
        {"name": "C", "depth_over_1_5m_share": 0.5, "median_depth_m": 1.0, "mean_duration_days": 20.0},
        {"name": "D", "depth_over_1_5m_share": 0.6, "median_depth_m": 1.5, "mean_duration_days": 40.0},
    ]
    indices, ranks, metadata = _severity(rows)

    assert all(value is not None and 0.0 <= value <= 100.0 for value in indices)
    assert len(set(indices)) >= 3
    assert sorted(rank for rank in ranks if rank is not None) == [1, 2, 3, 4]
    assert ranks[0] == 1  # A has the strongest per-wet-cell profile
    assert max(indices) == 100.0
    assert metadata["inputs"] == [
        "depth_over_1_5m_share",
        "median_depth_m",
        "mean_duration_days",
    ]
    assert "min-max" in metadata["normalisation"]["method"]
    assert metadata["normalisation"]["n_districts"] == 4


def test_committed_severity_ranks_are_dense_and_distinct():
    path = Path(__file__).resolve().parents[2] / "public" / "data" / "risk" / "district-risk.json"
    if not path.exists():  # pragma: no cover - committed data is present in this repo
        return
    risk = json.loads(path.read_text(encoding="utf-8"))
    values = [district["severity_index"] for district in risk["districts"]]
    ranks = sorted(district["severity_rank"] for district in risk["districts"])
    assert len({round(value, 6) for value in values}) > 5
    assert ranks == list(range(1, len(ranks) + 1))
    dima = next(district for district in risk["districts"] if district["name"] == "Dima Hasao")
    assert dima["severity_rank"] <= 11
    assert dima["area_share"] < 0.01
