"""REVIEW-17 P1.1/P1.2 and REVIEW-18 unit tests: calibration and metric maths."""
from __future__ import annotations

import numpy as np

from baanh_pipeline.calibration_s1 import (
    CalibrationError,
    _validity_stack,
    area_mask_metrics,
    calibration_scale_grid,
    mask_metrics,
    otsu_threshold,
    parse_calibration,
    sigma0_db,
)


def _synthetic_calibration_xml() -> bytes:
    return b"""<calibration>
  <calibrationVectorList count="2">
    <calibrationVector>
      <line>0</line>
      <pixel count="3">0 100 200</pixel>
      <sigmaNought count="3">500 500 500</sigmaNought>
    </calibrationVector>
    <calibrationVector>
      <line>100</line>
      <pixel count="3">0 100 200</pixel>
      <sigmaNought count="3">700 700 700</sigmaNought>
    </calibrationVector>
  </calibrationVectorList>
</calibration>"""


def test_parse_calibration_reads_vectors_and_median_A():
    lut = parse_calibration(_synthetic_calibration_xml(), "test-lut")
    assert lut.vectors == 2
    assert lut.samples_per_vector == 3
    assert lut.A_median == 600.0


def test_parse_calibration_rejects_a_missing_lut():
    try:
        parse_calibration(b"<calibration/>", "test-lut")
    except CalibrationError as exc:
        assert "calibrationVector" in str(exc)
    else:  # pragma: no cover - the assertion above must fire
        raise AssertionError("a calibration XML without vectors was accepted")


def test_calibration_scale_grid_interpolates_between_vectors():
    lut = parse_calibration(_synthetic_calibration_xml(), "test-lut")
    grid = calibration_scale_grid(lut, height=2, width=3, scale_y=50.0, scale_x=50.0)
    # Row centres 25 and 75 lie 25 % / 75 % between the two vectors.
    assert np.allclose(grid[0], 550.0)
    assert np.allclose(grid[1], 650.0)


def test_sigma0_db_is_twenty_log10_dn_over_a():
    scale = np.full((2, 2), 595.42415, dtype=np.float32)
    data = np.array([[595.42415, 1190.8483], [0.0, 300.0]], dtype=np.float32)
    db = sigma0_db(data, scale)
    assert abs(float(db[0, 0])) < 1e-4
    assert abs(float(db[0, 1]) - 6.0206) < 1e-4
    assert np.isnan(db[1, 0])


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


def test_area_mask_metrics_identity_and_ratios():
    area = np.full((4, 4), 0.5, dtype=np.float64)
    observed = np.zeros((4, 4), dtype=bool)
    modelled = np.zeros((4, 4), dtype=bool)
    observed[0:2, :] = True
    modelled[:, 1:3] = True
    metrics = area_mask_metrics(observed, modelled, area)
    assert metrics["tp"] == 2.0
    assert metrics["fp"] == 2.0
    assert metrics["fn"] == 2.0
    assert metrics["tp"] + metrics["fp"] == 4.0
    assert metrics["tp"] + metrics["fn"] == 4.0
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["iou"] == 1.0 / 3.0


def test_validity_stack_is_monotonic_and_never_uses_the_model():
    area = np.ones((6, 6), dtype=np.float64)
    raw = np.zeros((6, 6), dtype=bool)
    raw[:, :] = True
    aoi = np.ones((6, 6), dtype=bool)
    aoi[0, :] = False  # regional clip removes one row
    slope = np.zeros((6, 6), dtype=np.float64)
    slope[:, 4:] = 20.0  # slope branch removes the last two columns
    stack = _validity_stack(raw, aoi, slope, 10.0, 2, area)
    attrition = stack["attrition"]
    for step in (
        "raw_sar_valid",
        "slope_filtered",
        "aoi_clipped",
        "component_filtered",
        "final",
    ):
        assert step in attrition
        assert "area_km2" in attrition[step]
    assert attrition["raw_sar_valid"]["area_km2"] == 36.0
    assert attrition["slope_filtered"]["area_km2"] < attrition["raw_sar_valid"]["area_km2"]
    assert attrition["slope_filtered"]["applied_to_final"] is False
    assert attrition["aoi_clipped"]["area_km2"] == 30.0
    assert attrition["final"]["area_km2"] == 30.0
    assert attrition["without_slope_area_km2"] == 30.0
    assert attrition["with_slope_area_km2"] == 20.0
    assert stack["validity"].sum() == 30
