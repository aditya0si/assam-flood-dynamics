"""Tests for risk weights and class thresholds."""
from __future__ import annotations

import json
from pathlib import Path

from baanh_pipeline.config import load_config
from baanh_pipeline.risk import _duration_weights


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
