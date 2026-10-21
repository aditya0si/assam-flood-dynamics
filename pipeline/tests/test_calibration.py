"""REVIEW-17 P1.1/P1.2 unit tests: Otsu and scorecard metric maths."""
from __future__ import annotations

import numpy as np

from baanh_pipeline.calibration_s1 import mask_metrics, otsu_threshold


def test_otsu_separates_synthetic_bimodal_sample():
    rng = np.random.default_rng(17)
    low = rng.normal(20.0, 0.45, 20_000)
    high = rng.normal(25.0, 0.45, 20_000)
    values = np.concatenate([low, high])

    threshold = otsu_threshold(values)

    assert 21.5 < threshold < 23.5, threshold
    water = values <= threshold
    assert 0.45 < water.mean() < 0.55, water.mean()


def test_otsu_is_additively_invariant_to_a_scale_in_dn():
    rng = np.random.default_rng(23)
    values = np.concatenate(
        [rng.normal(20.0, 0.4, 10_000), rng.normal(25.0, 0.4, 10_000)]
    )
    # A multiplicative scale in DN is an additive shift in dB; the Otsu
    # threshold must move by the same constant.
    threshold = otsu_threshold(values)
    shifted = otsu_threshold(values + 7.5)
    assert abs((shifted - 7.5) - threshold) < 0.2


def test_otsu_rejects_a_constant_sample():
    threshold = otsu_threshold(np.full(1000, 22.0))
    assert threshold == 22.0


def test_mask_metrics_perfect_overlap_is_one():
    observed = np.zeros((8, 8), dtype=bool)
    observed[2:6, 2:6] = True
    metrics = mask_metrics(observed, observed.copy())
    assert metrics["iou"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0


def test_mask_metrics_disjoint_is_zero():
    observed = np.zeros((8, 8), dtype=bool)
    modelled = np.zeros((8, 8), dtype=bool)
    observed[:, :4] = True
    modelled[:, 4:] = True
    metrics = mask_metrics(observed, modelled)
    assert metrics["iou"] == 0.0
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0


def test_mask_metrics_known_partial_counts():
    observed = np.zeros((10, 10), dtype=bool)
    modelled = np.zeros((10, 10), dtype=bool)
    observed[0:5, 0:5] = True  # 25 cells
    modelled[0:5, 0:4] = True  # 20 cells, 20 shared
    metrics = mask_metrics(observed, modelled)
    assert metrics["tp"] == 20
    assert metrics["fp"] == 0
    assert metrics["fn"] == 5
    assert metrics["iou"] == 0.8
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 0.8
    assert abs(metrics["f1"] - (2 * 0.8 / 1.8)) < 1e-12


def test_mask_metrics_rejects_shape_mismatch():
    try:
        mask_metrics(np.zeros((4, 4), dtype=bool), np.zeros((4, 5), dtype=bool))
    except ValueError as exc:
        assert "shape mismatch" in str(exc)
    else:  # pragma: no cover - the assertion above must fire
        raise AssertionError("shape mismatch was accepted")
