"""Tests for the nearest-drainage helpers and geodesic cell areas."""
from __future__ import annotations

import numpy as np
from rasterio.transform import from_origin

from baanh_pipeline.geo import row_cell_areas_km2
from baanh_pipeline.inundation import _band_index, _component_filter


def test_band_index_boundaries():
    depth = np.array([[0.0, 0.1, 0.5, 0.6, 1.5, 1.6, 3.0, 3.1]], dtype=np.float32)
    bands = _band_index(depth, [0.0, 0.5, 1.5, 3.0, None])
    assert bands.tolist() == [[0, 1, 1, 2, 2, 3, 3, 4]]


def test_component_filter_drops_isolated_speck():
    wet = np.zeros((9, 9), dtype=bool)
    wet[4, 4] = True  # channel cell
    wet[4, 5] = True
    wet[3, 5] = True
    wet[0, 0] = True  # isolated speck, no channel within one cell
    distance = np.full((9, 9), 1000.0, dtype=np.float32)
    distance[4, 4] = 0.0
    distance[4, 5] = 90.0
    distance[3, 5] = 90.0
    distance[0, 0] = 5000.0
    filtered, count, dropped = _component_filter(wet, distance, 3, 90.0)
    assert count >= 2
    assert dropped >= 1
    assert filtered[4, 4] and filtered[4, 5] and filtered[3, 5]
    assert not filtered[0, 0]


def test_row_cell_area_is_cell_sized():
    transform = from_origin(500000.0, 2900000.0, 90.0, 90.0)
    areas = row_cell_areas_km2(transform, 4, 10, "EPSG:32646")
    assert areas.shape == (4, 1)
    assert np.allclose(areas, 0.0081, atol=0.0002)
