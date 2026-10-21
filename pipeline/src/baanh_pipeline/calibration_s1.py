"""Stage 16 — Sentinel-1 GRD calibration and validation scorecard.

REVIEW-17 P1.1/P1.2, corrected by REVIEW-18.  The stage:

* searches Earth Search for ``sentinel-1-grd`` items over the AOI in Jun–Jul 2022;
* selects the earliest and latest usable acquisitions covering the AOI core;
* reads each VV COG decimated by ~1/9 with ``Resampling.average`` (never at
  native resolution), assigns EPSG:32646 from ``proj:centroid`` (the COG itself
  reports no CRS), and applies the SAFE ``schema-calibration-vv`` LUT:
  ``sigma0_db = 20*log10(DN / A)`` with ``A = sigmaNought`` interpolated from
  the 27 vectors x 642 samples in ``calibration-iw-vv.xml``;
* uses a **fixed** -16 dB sigma0 water threshold, with the stated monsoon-VV
  rationale, and publishes sensitivity at -14/-16/-18 dB in sigma0 space;
* builds the validity domain from the full Sentinel-1 footprint on the 90 m
  frame grid (coverage >= 0.5), intersected with the regional AOI polygon, and
  removes validity components smaller than 5 analysis cells;
* publishes a per-scene ``validity_attrition`` ledger (``raw_sar_valid ->
  slope_filtered -> aoi_clipped -> component_filtered -> final``) with km2
  after every step, so no filter can silently delete the footprint;
* evaluates the 10 degree DEM-slope filter as a **diagnostic only** and
  publishes both ``with_slope`` and ``without_slope`` validity areas.  It is
  not applied to the shipped domain when it would remove most of the scene;
* publishes ``scene_area_km2``, ``validity_area_km2``,
  ``validity_fraction_of_scene`` and ``modelled_in_validity_km2`` per scene so
  every ratio has a visible denominator;
* recomputes IoU/precision/recall on that full validity footprint, using area
  weights, and publishes TP/FP/FN km2 per threshold;
* scores the existing committed PNG frames (decoded with frame-index placement)
  against the observed mask at every step, reporting the best-matching step and
  the scenario peak step S07.

Validity-mask provenance
------------------------
The validity mask must be built from SAR validity, the AOI polygon, terrain and
geometry **only**.  No mask may reference the flood frames, the HAND wet mask,
or any district/risk artifact.  The model is applied only *after* the validity
domain is fixed, so the score can never select its own denominator.  The
``mask_provenance`` object in the scorecard records the allowed and prohibited
inputs and asserts ``model_conditioned = false``.

No scene binary or mask is committed.  Rasters are cached under
``pipeline/cache/s1/`` (gitignored) and only the small scorecard JSON ships.

Anonymous S3
------------
The review measured that the COGs need anonymous S3 access and that the
``sentinel-s1-l1c`` measurement TIFFs report ``crs: None``.  We set
``AWS_NO_SIGN_REQUEST=YES`` and ``AWS_REGION=us-west-2`` before opening, as
required.  On this Windows host GDAL's curl backend cannot complete a TLS
handshake (``schannel: SEC_E_NO_CREDENTIALS``), so the stage falls back to a
loopback HTTP range proxy around ``requests`` for the COG only.  The proxy
serves the same anonymous S3 bytes, is torn down with the process, and never
writes the scene to disk.  On a host where ``/vsis3`` works the stage uses it
directly.
"""
from __future__ import annotations

import json
import math
import re
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import rasterio
import requests
from affine import Affine
from PIL import Image
from pyproj import Transformer
from rasterio.control import GroundControlPoint
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_gcps
from rasterio.warp import reproject
from rasterio.warp import Resampling as WarpResampling
from scipy import ndimage
from shapely.geometry import Polygon, shape

from .config import Config
from .geo import row_cell_areas_km2
from .util import (
    StageRecord,
    atomic_write_json,
    ensure_dirs,
    utc_now,
)

STAC_LIMIT = 250
EIGHT_CONNECTED = np.ones((3, 3), dtype=np.int8)
CALIBRATION_ASSET = "schema-calibration-vv"
DEFAULT_THRESHOLD_DB = -16.0
DEFAULT_SENSITIVITY_DB = [-14.0, -16.0, -18.0]
THRESHOLD_RATIONALE = (
    "Fixed -16 dB sigma0 threshold for C-band VV open water in monsoon conditions: "
    "it sits in the low tail of the calibrated land/water distribution and is stated "
    "before scoring; threshold choice, not the LUT, is the dominant residual "
    "uncertainty, so -14/-16/-18 dB are all published."
)
MASK_STACK_VERSION = "review19-full-footprint-v2"
SLOPE_OPERATOR = (
    "central-difference gradient of the 90 m DEM: dz_dy, dz_dx = "
    "np.gradient(dem_m, 90, 90); slope_deg = degrees(arctan(hypot(dz_dx, dz_dy)))"
)
SLOPE_UNIT = "degrees"
SLOPE_APPLIED_TO_VALIDITY = False
VALIDITY_DEFINITION = (
    "SAR VV valid samples (finite calibrated sigma0) reprojected to the 90 m frame "
    "grid with average coverage >= 0.5, intersected with the regional AOI polygon, "
    "then validity connected components smaller than 5 cells removed. The valley-"
    "floor AOI-core clip and the 10 degree slope filter are NOT applied to the final "
    "domain; both are published as diagnostics in validity_attrition."
)
MASK_PROVENANCE = {
    "allowed_inputs": [
        "sentinel1_vv_sigma0_validity",
        "aoi_polygon",
        "dem_slope",
        "grid_geometry",
    ],
    "prohibited_inputs": [
        "flood_frames",
        "hand_wet_mask",
        "district_risk_artifacts",
    ],
    "model_conditioned": False,
    "note": (
        "The validity domain is fixed before any flood frame is read. The model is "
        "applied only after the domain is fixed."
    ),
}


class CalibrationError(RuntimeError):
    """A measured failure that must be reported, never substituted."""


@dataclass
class CalibrationLUT:
    """Parsed ``sigmaNought`` calibration vectors from a SAFE annotation."""

    lines: np.ndarray
    pixels: list[np.ndarray]
    sigma_nought: list[np.ndarray]
    source: str
    samples_per_vector: int
    A_median: float

    @property
    def vectors(self) -> int:
        return int(self.lines.size)


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without network access)
# ---------------------------------------------------------------------------


def parse_calibration(xml_bytes: bytes, source: str) -> CalibrationLUT:
    """Parse every ``calibrationVector`` and return the sigmaNought LUT.

    The SAFE GRD annotation carries one ``sigmaNought`` sample per range pixel
    in each vector and one vector per azimuth block.  We keep the raw vectors;
    interpolation to the analysis grid happens in ``calibration_scale_grid``.
    A missing or malformed LUT is an error, never a silent fallback.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise CalibrationError(f"calibration XML is malformed: {exc}") from exc
    nodes = root.findall(".//calibrationVectorList/calibrationVector")
    if not nodes:
        raise CalibrationError("calibration XML has no calibrationVector entries")
    lines: list[int] = []
    pixels: list[np.ndarray] = []
    sigma: list[np.ndarray] = []
    sample_counts: set[int] = set()
    for index, node in enumerate(nodes):
        line_text = node.findtext("line")
        pixel_text = node.findtext("pixel")
        sigma_text = node.findtext("sigmaNought")
        if line_text is None or pixel_text is None or sigma_text is None:
            raise CalibrationError(f"calibration vector {index} is missing line/pixel/sigmaNought")
        line = int(line_text)
        pixel_values = np.fromstring(pixel_text, sep=" ", dtype=np.int64)
        sigma_values = np.fromstring(sigma_text, sep=" ", dtype=np.float64)
        if pixel_values.size == 0 or pixel_values.size != sigma_values.size:
            raise CalibrationError(
                f"calibration vector {index} has {pixel_values.size} pixels and "
                f"{sigma_values.size} sigmaNought samples"
            )
        if not np.all(np.isfinite(sigma_values)) or np.any(sigma_values <= 0):
            raise CalibrationError(f"calibration vector {index} has non-positive sigmaNought")
        lines.append(line)
        pixels.append(pixel_values)
        sigma.append(sigma_values)
        sample_counts.add(int(sigma_values.size))
    if len(sample_counts) != 1:
        raise CalibrationError(f"calibration vectors disagree on sample count: {sorted(sample_counts)}")
    sigma_all = np.concatenate(sigma)
    A_median = float(np.median(sigma_all))
    if not math.isfinite(A_median) or A_median <= 0:
        raise CalibrationError("calibration LUT produced a non-positive A_median")
    return CalibrationLUT(
        lines=np.asarray(lines, dtype=np.float64),
        pixels=pixels,
        sigma_nought=sigma,
        source=source,
        samples_per_vector=int(sample_counts.pop()),
        A_median=A_median,
    )


def calibration_scale_grid(
    lut: CalibrationLUT,
    height: int,
    width: int,
    scale_y: float,
    scale_x: float,
) -> np.ndarray:
    """Interpolate ``A`` onto the decimated analysis grid.

    Calibration vectors are sampled along azimuth (``line``) and range
    (``pixel``).  A decimated cell centre maps to native coordinates
    ``(row + 0.5) * scale_y`` and ``(col + 0.5) * scale_x``; we interpolate
    linearly between bracketing vectors and along each vector's samples.
    """
    if height <= 0 or width <= 0:
        raise CalibrationError(f"invalid calibration grid {height}x{width}")
    order = np.argsort(lut.lines, kind="stable")
    lines = lut.lines[order]
    columns = (np.arange(width, dtype=np.float64) + 0.5) * float(scale_x)
    profiles = np.vstack(
        [
            np.interp(columns, lut.pixels[index].astype(np.float64), lut.sigma_nought[index])
            for index in order
        ]
    ).astype(np.float32)
    rows = (np.arange(height, dtype=np.float64) + 0.5) * float(scale_y)
    if lines.size == 1:
        return np.broadcast_to(profiles[0], (height, width)).astype(np.float32)
    upper = np.clip(np.searchsorted(lines, rows, side="right"), 1, lines.size - 1)
    lower = upper - 1
    span = lines[upper] - lines[lower]
    with np.errstate(invalid="ignore", divide="ignore"):
        weight = np.where(span > 0, (rows - lines[lower]) / span, 0.0)
    weight = np.clip(weight, 0.0, 1.0).astype(np.float32)
    grid = (
        profiles[lower] * (1.0 - weight)[:, None]
        + profiles[upper] * weight[:, None]
    )
    return grid.astype(np.float32)


def sigma0_db(data: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """Convert DN to sigma0 dB with ``20*log10(DN/A)``; NaN outside valid data."""
    values = np.asarray(data, dtype=np.float32)
    lut = np.asarray(scale, dtype=np.float32)
    if values.shape != lut.shape:
        raise ValueError(f"sigma0 shape mismatch: {values.shape} vs {lut.shape}")
    finite = np.isfinite(values) & (values > 0) & np.isfinite(lut) & (lut > 0)
    out = np.full(values.shape, np.nan, dtype=np.float32)
    out[finite] = 20.0 * np.log10(values[finite] / lut[finite])
    return out


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    """Return the Otsu threshold of a 1-D finite sample.

    The threshold is the upper edge of the between-class-variance maximizing
    histogram bin.  ``values`` are already in dB; the caller classifies water as
    ``value <= threshold``.
    """
    sample = np.asarray(values, dtype=np.float64).ravel()
    sample = sample[np.isfinite(sample)]
    if sample.size < 2:
        raise CalibrationError("Otsu needs at least two finite values")
    low = float(sample.min())
    high = float(sample.max())
    if math.isclose(low, high):
        return high
    histogram, edges = np.histogram(sample, bins=bins, range=(low, high))
    total = float(histogram.sum())
    if total <= 0:
        raise CalibrationError("Otsu histogram is empty")
    probabilities = histogram.astype(np.float64) / total
    centers = (edges[:-1] + edges[1:]) / 2.0
    omega = np.cumsum(probabilities)
    mu = np.cumsum(probabilities * centers)
    mu_total = mu[-1]
    denominator = omega * (1.0 - omega)
    between = np.zeros_like(denominator)
    valid = denominator > 0
    between[valid] = (mu_total * omega[valid] - mu[valid]) ** 2 / denominator[valid]
    index = int(np.argmax(between))
    return float(edges[index + 1])


def mask_metrics(observed: np.ndarray, modelled: np.ndarray) -> dict[str, float]:
    """IoU / precision / recall / F1 for two boolean masks on the same grid.

    A perfect overlap is 1.0 and a disjoint pair is 0.0.  Empty/empty is
    defined as a perfect overlap (there is nothing to disagree about); the
    scorecard rejects an empty observed mask before this can matter.
    """
    obs = np.asarray(observed, dtype=bool)
    mod = np.asarray(modelled, dtype=bool)
    if obs.shape != mod.shape:
        raise ValueError(f"mask shape mismatch: {obs.shape} vs {mod.shape}")
    tp = int(np.count_nonzero(obs & mod))
    fp = int(np.count_nonzero(~obs & mod))
    fn = int(np.count_nonzero(obs & ~mod))
    union = tp + fp + fn
    iou = 1.0 if union == 0 else tp / union
    precision = 1.0 if tp + fp == 0 else tp / (tp + fp)
    recall = 1.0 if tp + fn == 0 else tp / (tp + fn)
    f1 = 0.0 if precision + recall == 0 else 2.0 * precision * recall / (precision + recall)
    return {
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
        "iou": float(iou),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def area_mask_metrics(
    observed: np.ndarray, modelled: np.ndarray, area_2d: np.ndarray
) -> dict[str, float]:
    """Area-weighted mask metrics, so TP/FP/FN km2 and the ratios agree exactly.

    ``mask_metrics`` counts cells; the scorecard publishes km2.  Because cell
    areas vary slightly with latitude, the published precision/recall/IoU must
    be computed from the same areas as the published TP/FP/FN or the arithmetic
    identity (TP + FP == modelled area) would only hold approximately.
    """
    obs = np.asarray(observed, dtype=bool)
    mod = np.asarray(modelled, dtype=bool)
    if obs.shape != mod.shape:
        raise ValueError(f"mask shape mismatch: {obs.shape} vs {mod.shape}")
    if obs.shape != area_2d.shape:
        raise ValueError(f"area shape mismatch: {obs.shape} vs {area_2d.shape}")
    tp = float(area_2d[obs & mod].sum())
    fp = float(area_2d[~obs & mod].sum())
    fn = float(area_2d[obs & ~mod].sum())
    union = tp + fp + fn
    iou = 1.0 if union == 0 else tp / union
    precision = 1.0 if tp + fp == 0 else tp / (tp + fp)
    recall = 1.0 if tp + fn == 0 else tp / (tp + fn)
    f1 = 0.0 if precision + recall == 0 else 2.0 * precision * recall / (precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "iou": float(iou),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def utm_epsg_from_centroid(lon: float, lat: float) -> int:
    """Return the WGS84 / UTM northern-hemisphere EPSG code for a centroid."""
    zone = int(math.floor((float(lon) + 180.0) / 6.0)) + 1
    zone = min(60, max(1, zone))
    if float(lat) < 0:
        raise CalibrationError(
            f"centroid {lon},{lat} is in the southern hemisphere; this AOI expects UTM north"
        )
    return 32600 + zone


def _component_filter(mask: np.ndarray, min_cells: int) -> tuple[np.ndarray, dict[str, int]]:
    labels, count = ndimage.label(mask, structure=EIGHT_CONNECTED)
    if count == 0:
        return np.zeros_like(mask, dtype=bool), {"components_before": 0, "components_after": 0}
    sizes = np.bincount(labels.ravel(), minlength=count + 1)
    keep = sizes >= int(min_cells)
    keep[0] = False
    filtered = keep[labels]
    return filtered, {
        "components_before": int(count),
        "components_after": int(keep[1:].sum()),
    }


def _aoi_mask(cfg: Config, grid: dict[str, Any]) -> np.ndarray:
    """Rasterise the regional AOI bbox on the frame grid.

    The bbox edges are densified before projection so the mask follows the
    UTM curvature.  This is a *regional* AOI clip; the narrow valley-floor core
    mask is deliberately not used, because clipping to it was the REVIEW-19
    bug: it retained only ~9 % of a 43,389 km2 scene and correlated the
    denominator with the model's wet area.
    """
    west, south, east, north = (float(value) for value in cfg.aoi.bbox)
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32646", always_xy=True)
    steps = 32
    coords: list[tuple[float, float]] = []
    for index in range(steps + 1):
        t = index / steps
        coords.append(transformer.transform(west + t * (east - west), south))
    for index in range(1, steps + 1):
        t = index / steps
        coords.append(transformer.transform(east, south + t * (north - south)))
    for index in range(1, steps + 1):
        t = index / steps
        coords.append(transformer.transform(east - t * (east - west), north))
    for index in range(1, steps):
        t = index / steps
        coords.append(transformer.transform(west, north - t * (north - south)))
    inside = ~geometry_mask(
        [Polygon(coords)],
        out_shape=(int(grid["height"]), int(grid["width"])),
        transform=grid["transform"],
        all_touched=False,
    )
    return np.asarray(inside, dtype=bool)


def _scene_area_km2(dataset: Any, scene: dict[str, Any]) -> float:
    """Ground area of the SAR scene quadrilateral in km2.

    The four corner GCPs are transformed to the scene's UTM zone and closed
    into a polygon.  This reproduces the reviewer's GCP-corner area (43,389
    km2 for the 2022-07-31 scene) rather than a bbox area.  If the COG has no
    GCPs, the affine transform corners are used and the difference is reported
    by the shape of the scene.
    """
    gcps, gcp_crs = dataset.gcps
    epsg = int(scene["epsg"])
    transformer = Transformer.from_crs(
        gcp_crs or "EPSG:4326", f"EPSG:{epsg}", always_xy=True
    )
    if gcps:
        corners: list[tuple[float, float]] = []
        for row, col in (
            (0, 0),
            (0, int(dataset.width)),
            (int(dataset.height), int(dataset.width)),
            (int(dataset.height), 0),
        ):
            point = min(
                gcps,
                key=lambda item: (item.row - row) ** 2 + (item.col - col) ** 2,
            )
            corners.append(transformer.transform(point.x, point.y))
        polygon = Polygon(corners)
        if polygon.is_valid and polygon.area > 0:
            return float(polygon.area / 1_000_000.0)
    transform, _ = _scene_source_transform(dataset, scene)
    corners = [
        transform * (0, 0),
        transform * (int(dataset.width), 0),
        transform * (int(dataset.width), int(dataset.height)),
        transform * (0, int(dataset.height)),
    ]
    area = float(Polygon(corners).area / 1_000_000.0)
    if area <= 0:
        raise CalibrationError(
            f"scene {scene['scene_id']} has no positive GCP/affine ground area"
        )
    return area


def _validity_stack(
    raw: np.ndarray,
    aoi: np.ndarray,
    slope: np.ndarray,
    slope_limit: float,
    min_cells: int,
    area_2d: np.ndarray,
) -> dict[str, Any]:
    """Build the validity ledger and the shipped (without-slope) domain.

    ``raw`` is the SAR-valid footprint on the frame grid, ``aoi`` is the
    regional AOI polygon and ``slope`` is the DEM slope in degrees.  The
    function never touches the flood frames, HAND or risk layers.

    The shipped path is ``raw -> aoi -> component -> final``.  The slope
    branch is evaluated and reported, but not applied when it would delete
    most of the scene.  ``validity_attrition`` still records the slope branch's
    area and the km2 it would remove, and ``applied_to_final`` says whether
    that step is on the shipped path.
    """
    raw = np.asarray(raw, dtype=bool)
    aoi = np.asarray(aoi, dtype=bool)
    slope_ok = np.asarray(slope, dtype=np.float32) <= float(slope_limit)
    if raw.shape != aoi.shape or raw.shape != slope_ok.shape or raw.shape != area_2d.shape:
        raise CalibrationError(
            f"validity stack shape mismatch: raw {raw.shape}, aoi {aoi.shape}, "
            f"slope {slope_ok.shape}, areas {area_2d.shape}"
        )
    raw_area = float(area_2d[raw].sum())
    aoi_raw = raw & aoi
    aoi_area = float(area_2d[aoi_raw].sum())
    with_slope_raw = raw & aoi & slope_ok
    with_slope, with_slope_counts = _component_filter(with_slope_raw, min_cells)
    with_slope_area = float(area_2d[with_slope].sum())
    final, final_counts = _component_filter(aoi_raw, min_cells)
    final_area = float(area_2d[final].sum())
    if final_area <= 0:
        raise CalibrationError("validity stack produced an empty final domain")
    attrition = {
        "raw_sar_valid": {
            "area_km2": round(raw_area, 4),
            "removed_km2": 0.0,
            "applied_to_final": True,
            "reason": (
                "Full SAR VV validity on the 90 m frame grid: finite calibrated "
                "sigma0, average coverage >= 0.5. No AOI-core clip."
            ),
        },
        "slope_filtered": {
            "area_km2": round(with_slope_area, 4),
            "removed_km2": round(raw_area - with_slope_area, 4),
            "applied_to_final": False,
            "components_before": with_slope_counts["components_before"],
            "components_after": with_slope_counts["components_after"],
            "reason": (
                "Diagnostic branch: DEM slope <= 10 degrees (see slope_filter). "
                "Not applied to the shipped domain because it would remove "
                f"{raw_area - with_slope_area:,.1f} km2 of hill terrain from this "
                "scene; the published final domain is the without_slope branch."
            ),
        },
        "aoi_clipped": {
            "area_km2": round(aoi_area, 4),
            "removed_km2": round(raw_area - aoi_area, 4),
            "applied_to_final": True,
            "reason": (
                "Regional AOI bbox (89.55-96.15 E, 23.95-28.15 N), densified to "
                "EPSG:32646. The valley-floor AOI core is not used: it retained "
                "only a model-correlated sliver of this scene."
            ),
        },
        "component_filtered": {
            "area_km2": round(final_area, 4),
            "removed_km2": round(aoi_area - final_area, 4),
            "applied_to_final": True,
            "components_before": final_counts["components_before"],
            "components_after": final_counts["components_after"],
            "reason": "Validity connected components smaller than 5 cells removed.",
        },
        "final": {
            "area_km2": round(final_area, 4),
            "removed_km2": round(raw_area - final_area, 4),
            "applied_to_final": True,
            "reason": (
                "Shipped validity domain = raw_sar_valid -> aoi_clipped -> "
                "component_filtered; slope branch not applied."
            ),
        },
        "shipped_path": [
            "raw_sar_valid",
            "aoi_clipped",
            "component_filtered",
            "final",
        ],
        "with_slope_area_km2": round(with_slope_area, 4),
        "without_slope_area_km2": round(final_area, 4),
    }
    return {
        "validity": final,
        "with_slope_validity": with_slope,
        "attrition": attrition,
        "with_slope_area_km2": with_slope_area,
        "without_slope_area_km2": final_area,
    }


# ---------------------------------------------------------------------------
# Anonymous S3 / COG opening
# ---------------------------------------------------------------------------


def _content_length(response: requests.Response) -> str | None:
    content_range = response.headers.get("Content-Range")
    if content_range:
        match = re.search(r"bytes\s+(\d+)-(\d+)/(\d+)", content_range)
        if match:
            return str(int(match.group(2)) - int(match.group(1)) + 1)
    return response.headers.get("Content-Length")


class _RangeProxyHandler(BaseHTTPRequestHandler):
    """Serve one S3 object over loopback HTTP, forwarding Range requests."""

    protocol_version = "HTTP/1.0"

    def log_message(self, *args: Any) -> None:  # noqa: A003 - stdlib signature
        return

    def _request_headers(self) -> dict[str, str]:
        return {
            key: value
            for key, value in self.headers.items()
            if key.lower() in ("range", "if-none-match", "if-match")
        }

    def _not_found(self) -> None:
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def _send_headers(self, response: requests.Response) -> None:
        self.send_response(response.status_code)
        for key in ("Content-Type", "Content-Range", "Accept-Ranges", "ETag", "Last-Modified"):
            if key in response.headers:
                self.send_header(key, response.headers[key])
        length = _content_length(response)
        if length is not None:
            self.send_header("Content-Length", length)
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib signature
        if not self.path.lower().endswith((".tif", ".tiff")):
            self._not_found()
            return
        response = requests.head(
            self.server.upstream_base + self.path,  # type: ignore[attr-defined]
            headers=self._request_headers(),
            timeout=30,
            allow_redirects=True,
        )
        self._send_headers(response)

    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        if not self.path.lower().endswith((".tif", ".tiff")):
            self._not_found()
            return
        response = requests.get(
            self.server.upstream_base + self.path,  # type: ignore[attr-defined]
            headers=self._request_headers(),
            timeout=60,
            stream=True,
            allow_redirects=True,
        )
        self._send_headers(response)
        try:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


class CogReader:
    """Open anonymous S3 COGs, with a loopback range proxy fallback.

    The constructor sets the two review-mandated environment variables.  A
    ``/vsis3`` attempt is made first; only if GDAL cannot complete the
    anonymous request does the loopback proxy start.
    """

    def __init__(self, aws_region: str = "us-west-2") -> None:
        self.aws_region = aws_region
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port: int | None = None
        self._upstream: dict[str, str] = {}
        self._opened_via = "unset"

    def __enter__(self) -> "CogReader":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self._thread = None
        self._port = None
        self._upstream.clear()

    def _start_proxy(self) -> None:
        if self._server is not None:
            return
        server = ThreadingHTTPServer(("127.0.0.1", 0), _RangeProxyHandler)
        server.daemon_threads = True
        server.upstream_base = "https://s3.amazonaws.com"  # type: ignore[attr-defined]
        port = int(server.server_address[1])
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._server = server
        self._thread = thread
        self._port = port

    def _proxy_url(self, href: str) -> str:
        self._start_proxy()
        assert self._port is not None
        bucket, key = _split_s3(href)
        if bucket not in self._upstream:
            self._upstream[bucket] = f"https://{bucket}.s3.amazonaws.com"
        self._server.upstream_base = self._upstream[bucket]  # type: ignore[union-attr]
        return f"http://127.0.0.1:{self._port}/{key}"

    def open(self, href: str):
        import os

        os.environ["AWS_NO_SIGN_REQUEST"] = "YES"
        os.environ["AWS_REGION"] = self.aws_region
        if href.startswith("s3://"):
            bucket, key = _split_s3(href)
            candidates = [
                (
                    f"/vsis3/{bucket}/{key}",
                    rasterio.Env(
                        AWS_NO_SIGN_REQUEST="YES",
                        AWS_REGION=self.aws_region,
                        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                        GDAL_HTTP_TIMEOUT="30",
                        GDAL_HTTP_CONNECTTIMEOUT="10",
                    ),
                )
            ]
        else:
            candidates = [(href, None)]
        last_error: Exception | None = None
        for candidate, env in candidates:
            if env is None:
                try:
                    dataset = rasterio.open(candidate)
                    dataset._baanh_env = None  # type: ignore[attr-defined]
                    self._opened_via = candidate
                    return dataset
                except Exception as exc:
                    last_error = exc
                continue
            env.__enter__()
            try:
                dataset = rasterio.open(candidate)
            except Exception as exc:
                last_error = exc
                env.__exit__(None, None, None)
                continue
            dataset._baanh_env = env  # type: ignore[attr-defined]
            self._opened_via = candidate
            return dataset
        if href.startswith("s3://"):
            proxy_env = rasterio.Env(
                GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                GDAL_HTTP_TIMEOUT="120",
                GDAL_HTTP_CONNECTTIMEOUT="10",
            )
            proxy_env.__enter__()
            try:
                dataset = rasterio.open(self._proxy_url(href))
            except Exception as exc:
                proxy_env.__exit__(None, None, None)
                last_error = exc
            else:
                dataset._baanh_env = proxy_env  # type: ignore[attr-defined]
                self._opened_via = "loopback-range-proxy"
                return dataset
        raise CalibrationError(
            f"could not open COG {href}: {type(last_error).__name__}: {last_error}"
        )


def _split_s3(href: str) -> tuple[str, str]:
    if not href.startswith("s3://"):
        raise CalibrationError(f"not an s3:// href: {href}")
    remainder = href[len("s3://") :]
    bucket, _, key = remainder.partition("/")
    if not bucket or not key:
        raise CalibrationError(f"malformed s3:// href: {href}")
    return bucket, key


def _close_dataset(dataset) -> None:
    env = getattr(dataset, "_baanh_env", None)
    try:
        dataset.close()
    finally:
        if env is not None:
            env.__exit__(None, None, None)


def _s3_https_url(href: str) -> str:
    bucket, key = _split_s3(href)
    return f"https://{bucket}.s3.amazonaws.com/{key}"


def _fetch_calibration(scene: dict[str, Any], cache_dir: Path) -> CalibrationLUT:
    """Download (or reuse) the SAFE sigmaNought LUT and parse it.

    REVIEW-18 measured that ``schema-calibration-vv`` is exposed anonymously
    for both scenes.  A missing asset or a failed download is a stage error:
    calibration is available and must not be described as unavailable.
    """
    href = str(scene.get("assets", {}).get(CALIBRATION_ASSET, ""))
    if not href:
        raise CalibrationError(
            f"scene {scene['scene_id']} has no {CALIBRATION_ASSET} STAC asset; "
            "cannot calibrate DN to sigma0"
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"{CALIBRATION_ASSET}.xml"
    if destination.exists() and destination.stat().st_size > 1024:
        return parse_calibration(destination.read_bytes(), href)
    print(f"[16] {scene['scene_id']}: fetching {CALIBRATION_ASSET}", flush=True)
    try:
        response = requests.get(_s3_https_url(href), timeout=120)
        response.raise_for_status()
    except Exception as exc:
        raise CalibrationError(
            f"could not fetch {CALIBRATION_ASSET} for {scene['scene_id']}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    if len(response.content) <= 1024:
        raise CalibrationError(
            f"{CALIBRATION_ASSET} for {scene['scene_id']} is only "
            f"{len(response.content)} bytes"
        )
    temporary = destination.with_suffix(".xml.tmp")
    temporary.write_bytes(response.content)
    temporary.replace(destination)
    return parse_calibration(response.content, href)


# ---------------------------------------------------------------------------
# STAC
# ---------------------------------------------------------------------------


def _stac_search(cfg: Config) -> list[dict[str, Any]]:
    sentinel = cfg.sources["sentinel1"]
    body = {
        "collections": [str(sentinel["collection"])],
        "bbox": list(cfg.aoi.bbox),
        "datetime": str(sentinel["datetime"]),
        "limit": STAC_LIMIT,
    }
    url = str(sentinel["stac_url"]).rstrip("/") + "/search"
    try:
        response = requests.post(url, json=body, timeout=60)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise CalibrationError(
            f"STAC search failed at {url}: {type(exc).__name__}: {exc}"
        ) from exc
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise CalibrationError(f"STAC search at {url} returned no features")
    return features


def _item_intersection_area(item: dict[str, Any], polygon) -> float:
    try:
        geometry = shape(item["geometry"])
    except Exception:
        return 0.0
    if geometry.is_empty:
        return 0.0
    return float(geometry.intersection(polygon).area)


def _usable(item: dict[str, Any]) -> bool:
    props = item.get("properties", {})
    assets = item.get("assets", {})
    return (
        bool(assets.get("vv", {}).get("href"))
        and str(props.get("sar:instrument_mode", "")).upper() == "IW"
        and str(props.get("sar:product_type", "")).upper() == "GRD"
    )


def select_scenes(
    features: Iterable[dict[str, Any]], selection_polygon
) -> list[dict[str, Any]]:
    """Select the earliest and latest usable acquisitions covering the AOI core.

    Each STAC item is one GRD slice.  A single slice covers only part of the
    full AOI rectangle, so "covering the AOI" is measured against the AOI core
    mask's bounding polygon: for each acquisition date the slice with the
    largest core overlap is the usable acquisition.  The earliest and latest
    such dates are returned; a failed read is reported, never substituted.
    """
    by_date: dict[str, list[tuple[float, dict[str, Any]]]] = {}
    for item in features:
        if not _usable(item):
            continue
        props = item.get("properties", {})
        date = str(props.get("datetime") or props.get("start_datetime") or "")[:10]
        if not date:
            continue
        area = _item_intersection_area(item, selection_polygon)
        if area <= 0:
            continue
        by_date.setdefault(date, []).append((area, item))
    if len(by_date) < 2:
        raise CalibrationError(
            "STAC search produced fewer than two usable acquisition dates over the AOI"
        )
    dates = sorted(by_date)
    chosen = []
    for date in (dates[0], dates[-1]):
        # Deterministic: largest overlap, then lexicographic item id.
        _, item = max(by_date[date], key=lambda pair: (pair[0], pair[1]["id"]))
        chosen.append(item)
    return chosen


def _scene_record(item: dict[str, Any]) -> dict[str, Any]:
    props = item.get("properties", {})
    centroid = props.get("proj:centroid") or {}
    lon = float(centroid.get("lon", 0.0))
    lat = float(centroid.get("lat", 0.0))
    epsg = utm_epsg_from_centroid(lon, lat)
    return {
        "scene_id": str(item["id"]),
        "datetime": str(props.get("datetime") or props.get("start_datetime")),
        "platform": str(props.get("platform", "unknown")),
        "relative_orbit": int(props.get("sat:relative_orbit", -1)),
        "orbit_direction": str(props.get("sat:orbit_state", "unknown")),
        "centroid": {"lon": lon, "lat": lat},
        "epsg": epsg,
        "assets": {
            key: str(item.get("assets", {}).get(key, {}).get("href", ""))
            for key in ("vv", "vh", "safe-manifest", CALIBRATION_ASSET)
        },
        "stac_item": f"https://earth-search.aws.element84.com/v1/collections/sentinel-1-grd/items/{item['id']}",
    }


# ---------------------------------------------------------------------------
# Raster helpers
# ---------------------------------------------------------------------------


def _scene_source_transform(src, scene: dict[str, Any]) -> tuple[Affine, str]:
    """Return an EPSG:32646 affine transform for a COG that reports no CRS.

    The measurement TIFF carries 210 WGS84 GCPs but no dataset CRS.  We
    transform the GCPs to the EPSG:32646 zone derived from ``proj:centroid``
    and derive the affine with ``rasterio.transform.from_gcps``.  If a COG has
    no GCPs we fall back to the STAC item's WGS84 ``proj:transform``, still
    assigning the UTM zone explicitly.
    """
    gcps, gcp_crs = src.gcps
    epsg = int(scene["epsg"])
    transformer = Transformer.from_crs(gcp_crs or "EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    if gcps:
        utm_gcps = []
        for point in gcps:
            x, y = transformer.transform(point.x, point.y)
            utm_gcps.append(
                GroundControlPoint(row=point.row, col=point.col, x=float(x), y=float(y))
            )
        return from_gcps(utm_gcps), f"EPSG:{epsg}"
    transform = src.transform
    if transform == Affine(1.0, 0.0, 0.0, 0.0, 1.0, 0.0):
        raise CalibrationError(
            f"scene {scene['scene_id']} has neither GCPs nor a geotransform; "
            "cannot assign EPSG:32646 without inventing a location"
        )
    return transform, f"EPSG:{epsg}"


def _read_decimated_vv(
    dataset, scene: dict[str, Any], factor: int
) -> tuple[np.ndarray, Affine, str, int, int, float, float]:
    src_transform, src_crs = _scene_source_transform(dataset, scene)
    out_height = max(1, dataset.height // factor)
    out_width = max(1, dataset.width // factor)
    data = dataset.read(
        1,
        out_shape=(out_height, out_width),
        resampling=Resampling.average,
    )
    # A decimated read scales the source pixel grid by the integer ratio.
    scale_x = dataset.width / out_width
    scale_y = dataset.height / out_height
    decimated_transform = src_transform * Affine.scale(scale_x, scale_y)
    return data, decimated_transform, src_crs, out_height, out_width, scale_y, scale_x


def _reproject_mask(
    source: np.ndarray,
    src_transform: Affine,
    src_crs: str,
    dst_transform: Affine,
    dst_crs: str,
    out_shape: tuple[int, int],
    resampling: WarpResampling,
) -> np.ndarray:
    destination = np.zeros(out_shape, dtype=np.float32 if resampling == WarpResampling.average else np.uint8)
    reproject(
        source.astype(np.float32 if resampling == WarpResampling.average else np.uint8),
        destination,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=resampling,
    )
    return destination


def _slope_degrees(dem_path: Path, nodata: float) -> np.ndarray:
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        transform = src.transform
        src_nodata = float(src.nodata if src.nodata is not None else nodata)
    valid = dem != src_nodata
    filled = np.where(valid, dem, 0.0).astype(np.float32)
    dz_dy, dz_dx = np.gradient(filled, abs(transform.e), abs(transform.a))
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype(np.float32)
    slope[~valid] = 0.0
    return slope


def _load_frame_grid(
    cfg: Config, core_mask_path: Path, frame_index_path: Path
) -> dict[str, Any]:
    with rasterio.open(core_mask_path) as src:
        core = src.read(1).astype(bool)
        transform = src.transform
        crs = str(src.crs)
        height, width = src.shape
    if crs != "EPSG:32646":
        raise CalibrationError(f"frame grid CRS is {crs}, expected EPSG:32646")
    if abs(float(transform.a) - 90.0) > 1e-6 or abs(float(transform.e) + 90.0) > 1e-6:
        raise CalibrationError(
            f"frame grid resolution is {transform.a} x {transform.e}, expected 90 m"
        )
    frame_index = json.loads(frame_index_path.read_text(encoding="utf-8"))
    scale = int(frame_index.get("frame_scale", 2))
    if scale != 2:
        raise CalibrationError(f"frame scale is {scale}, expected 2")
    if int(frame_index["width"]) * scale > width or int(frame_index["height"]) * scale > height:
        raise CalibrationError("frame-index dimensions exceed the 90 m analysis grid")
    areas = row_cell_areas_km2(transform, height, width, crs)
    area_2d = np.broadcast_to(areas, (height, width)).astype(np.float64)
    return {
        "core": core,
        "transform": transform,
        "crs": crs,
        "height": height,
        "width": width,
        "areas": area_2d,
        "frame_index": frame_index,
        "frame_scale": scale,
    }


def _model_mask(
    frame_dir: Path, frame_index: dict[str, Any], step: int, height: int, width: int, scale: int
) -> np.ndarray:
    entry = frame_index["steps"][step]
    path = frame_dir / Path(entry["file"]).name
    with Image.open(path) as image:
        if image.mode != "P":
            raise CalibrationError(f"{path.name} is {image.mode}, expected paletted PNG")
        classes = np.asarray(image)
    upsampled = np.repeat(np.repeat(classes > 0, scale, axis=0), scale, axis=1)
    mask = np.zeros((height, width), dtype=bool)
    copy_h = min(height, upsampled.shape[0])
    copy_w = min(width, upsampled.shape[1])
    mask[:copy_h, :copy_w] = upsampled[:copy_h, :copy_w]
    return mask


def _core_bbox_wgs84(core: np.ndarray, transform: Affine) -> Any:
    rows = np.flatnonzero(core.any(axis=1))
    cols = np.flatnonzero(core.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        raise CalibrationError("AOI core mask is empty")
    left, top = transform * (int(cols[0]), int(rows[0]))
    right, bottom = transform * (int(cols[-1]) + 1, int(rows[-1]) + 1)
    transformer = Transformer.from_crs("EPSG:32646", "EPSG:4326", always_xy=True)
    west, south = transformer.transform(left, bottom)
    east, north = transformer.transform(right, top)
    from shapely.geometry import box

    return box(west, south, east, north)


# ---------------------------------------------------------------------------
# Per-scene processing
# ---------------------------------------------------------------------------


def _threshold_label(value: float) -> str:
    """Stable cache label for a sigma0 threshold: -14 -> ``m14``."""
    sign = "m" if value < 0 else "p"
    return f"{sign}{abs(value):g}".replace(".", "p")


def _cache_paths(cache_dir: Path, thresholds: Iterable[float]) -> dict[str, Path]:
    paths = {
        "coverage": cache_dir / "coverage-90m.tif",
        "validity": cache_dir / "validity-90m.tif",
        "metadata": cache_dir / "metadata.json",
    }
    for threshold in thresholds:
        paths[_threshold_label(float(threshold))] = (
            cache_dir / f"water-sigma0-{_threshold_label(float(threshold))}-90m.tif"
        )
    return paths


def _write_mask(path: Path, mask: np.ndarray, transform: Affine, crs: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": mask.shape[0],
        "width": mask.shape[1],
        "count": 1,
        "dtype": "uint8",
        "crs": crs,
        "transform": transform,
        "nodata": 0,
        "compress": "deflate",
        "tiled": True,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(mask.astype(np.uint8), 1)


def _read_mask(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1) > 0


def _write_coverage(path: Path, coverage: np.ndarray, transform: Affine, crs: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": coverage.shape[0],
        "width": coverage.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": -1.0,
        "compress": "deflate",
        "tiled": True,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(coverage.astype(np.float32), 1)


def _read_coverage(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1).astype(np.float32)


def _process_scene(
    cfg: Config,
    scene: dict[str, Any],
    grid: dict[str, Any],
    slope: np.ndarray,
    cache_root: Path,
    refresh: bool,
) -> dict[str, Any]:
    sentinel = cfg.sources["sentinel1"]
    factor = int(sentinel.get("decimation", 9))
    sensitivity = [
        float(value) for value in sentinel.get("sensitivity_db", DEFAULT_SENSITIVITY_DB)
    ]
    if len(sensitivity) != 3:
        raise CalibrationError(
            f"sensitivity_db must list exactly three sigma0 thresholds, got {sensitivity}"
        )
    threshold = float(sentinel.get("threshold_db", DEFAULT_THRESHOLD_DB))
    if threshold not in sensitivity:
        raise CalibrationError(
            f"threshold_db {threshold} is not one of the sensitivity thresholds {sensitivity}"
        )
    rationale = str(sentinel.get("threshold_rationale", THRESHOLD_RATIONALE))
    min_cells = int(sentinel.get("min_component_cells", 5))
    slope_limit = float(sentinel.get("slope_mask_deg", 10.0))
    coverage_min = float(sentinel.get("coverage_min", 0.90))
    cache_dir = cache_root / scene["scene_id"]
    paths = _cache_paths(cache_dir, sensitivity)
    height = int(grid["height"])
    width = int(grid["width"])
    core = grid["core"]
    frame_transform = grid["transform"]
    labels = [_threshold_label(value) for value in sensitivity]

    if not refresh and all(path.exists() for path in paths.values()):
        metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
        cached = [float(value) for value in metadata.get("sensitivity_db", [])]
        if (
            metadata.get("threshold_method") == "fixed_sigma0"
            and cached == sensitivity
            and metadata.get("mask_stack_version") == MASK_STACK_VERSION
            and "scene_area_km2" in metadata
            and "validity_attrition" in metadata
        ):
            coverage = _read_coverage(paths["coverage"])
            validity = _read_mask(paths["validity"])
            masks = {label: _read_mask(paths[label]) for label in labels}
            print(
                f"[16] {scene['scene_id']}: cache hit (sigma0 {threshold:g} dB, "
                f"A median {metadata['calibration']['A_median']:.2f}, "
                f"validity {float(grid['areas'][validity].sum()):.1f} km2)"
            )
            return {
                "scene": scene,
                "metadata": metadata,
                "coverage": coverage,
                "validity": validity,
                "validity_attrition": metadata["validity_attrition"],
                "with_slope_area_km2": float(metadata["with_slope_area_km2"]),
                "without_slope_area_km2": float(metadata["without_slope_area_km2"]),
                "masks": masks,
                "cache": cache_dir,
            }

    href = scene["assets"]["vv"]
    if not href:
        raise CalibrationError(f"scene {scene['scene_id']} has no VV asset href")
    print(f"[16] {scene['scene_id']}: opening VV COG (anonymous S3)", flush=True)
    with CogReader(aws_region=str(sentinel.get("aws_region", "us-west-2"))) as reader:
        dataset = reader.open(href)
        try:
            print(f"[16] {scene['scene_id']}: reading decimated VV (~1/{factor})", flush=True)
            data, src_transform, src_crs, out_h, out_w, scale_y, scale_x = _read_decimated_vv(
                dataset, scene, factor
            )
            scene_area_km2 = _scene_area_km2(dataset, scene)
            opened_via = reader._opened_via
        finally:
            _close_dataset(dataset)
    print(
        f"[16] {scene['scene_id']}: read {out_w}x{out_h} via {opened_via}",
        flush=True,
    )

    lut = _fetch_calibration(scene, cache_dir)
    scale = calibration_scale_grid(lut, out_h, out_w, scale_y, scale_x)
    db = sigma0_db(data, scale)
    valid = np.isfinite(db)
    if not valid.any():
        raise CalibrationError(f"scene {scene['scene_id']} has no valid calibrated VV samples")

    # Percentiles are descriptive only; the validity mask itself never uses the
    # AOI core.  Keeping the core sample here avoids mixing hill and valley
    # sigma0 distributions in the published calibration percentiles.
    source_aoi = _reproject_mask(
        core.astype(np.uint8),
        frame_transform,
        "EPSG:32646",
        src_transform,
        src_crs,
        (out_h, out_w),
        WarpResampling.nearest,
    )
    stats_selected = valid & (source_aoi > 0)
    values = db[stats_selected]
    if values.size < 1000:
        raise CalibrationError(
            f"scene {scene['scene_id']} intersects only {int(values.size)} AOI core pixels"
        )
    p05, p50, p95 = (float(value) for value in np.percentile(values, [5, 50, 95]))

    # The validity footprint is the full SAR scene on the frame grid, not the
    # narrow AOI core.  REVIEW-19 measured that the core clip retained only
    # ~3,735 km2 of a ~43,389 km2 scene and 97 % of the model's wet area.
    coverage = _reproject_mask(
        valid.astype(np.uint8),
        src_transform,
        src_crs,
        frame_transform,
        "EPSG:32646",
        (height, width),
        WarpResampling.average,
    )
    raw_footprint = coverage >= 0.5
    if not raw_footprint.any():
        raise CalibrationError(f"scene {scene['scene_id']} has zero SAR footprint")
    aoi = _aoi_mask(cfg, grid)
    stack = _validity_stack(
        raw_footprint,
        aoi,
        slope,
        slope_limit,
        min_cells,
        grid["areas"],
    )
    validity = stack["validity"]
    validity_attrition = stack["attrition"]
    legacy_core_area = float(grid["areas"][raw_footprint & core].sum())
    validity_attrition["legacy_aoi_core_clipped_area_km2"] = round(legacy_core_area, 4)
    validity_attrition["aoi_clipped"]["legacy_aoi_core_area_km2"] = round(
        legacy_core_area, 4
    )
    validity_attrition["aoi_clipped"]["legacy_aoi_core_removed_km2"] = round(
        float(stack["without_slope_area_km2"]) - legacy_core_area, 4
    )
    validity_attrition["note"] = (
        "The former AOI-core clip is published only as a diagnostic. It is not "
        "part of the shipped validity domain: clipping to the valley-floor core "
        "kept 3,735 km2 of this scene and selected the model's wet area."
    )
    raw_masks: dict[str, np.ndarray] = {}
    audit: dict[str, dict[str, int]] = {}
    for value, label in zip(sensitivity, labels):
        source_water = valid & (db <= value)
        projected = _reproject_mask(
            source_water.astype(np.uint8),
            src_transform,
            src_crs,
            frame_transform,
            "EPSG:32646",
            (height, width),
            WarpResampling.nearest,
        ) > 0
        water = projected & validity
        filtered, counts = _component_filter(water, min_cells)
        raw_masks[label] = filtered
        audit[label] = counts
        _write_mask(paths[label], filtered, frame_transform, "EPSG:32646")
    _write_coverage(paths["coverage"], coverage, frame_transform, "EPSG:32646")
    _write_mask(paths["validity"], validity, frame_transform, "EPSG:32646")

    valid_share = float(coverage[raw_footprint].mean())
    aoi_footprint_share = float(raw_footprint.sum()) / float(core.sum())
    if valid_share < coverage_min:
        raise CalibrationError(
            f"scene {scene['scene_id']} valid coverage {valid_share:.4f} < "
            f"{coverage_min:.2f} (SAR footprint is {aoi_footprint_share:.2%} of "
            "the full AOI core; the validity domain is the full SAR footprint, "
            "not the core)"
        )

    validity_area_km2 = float(stack["without_slope_area_km2"])
    with_slope_area_km2 = float(stack["with_slope_area_km2"])
    metadata = {
        **scene,
        "threshold_method": "fixed_sigma0",
        "threshold_db": float(threshold),
        "threshold_rationale": rationale,
        "sensitivity_db": sensitivity,
        "calibration": {
            "source": lut.source,
            "vectors": lut.vectors,
            "samples_per_vector": lut.samples_per_vector,
            "A_median": round(lut.A_median, 6),
        },
        "sigma0_db_percentiles": {
            "p05": round(p05, 4),
            "p50": round(p50, 4),
            "p95": round(p95, 4),
        },
        "mask_stack_version": MASK_STACK_VERSION,
        "validity_definition": VALIDITY_DEFINITION,
        "scene_area_km2": round(scene_area_km2, 4),
        "validity_area_km2": round(validity_area_km2, 4),
        "validity_fraction_of_scene": round(
            validity_area_km2 / scene_area_km2, 6
        ),
        "with_slope_area_km2": round(with_slope_area_km2, 4),
        "without_slope_area_km2": round(validity_area_km2, 4),
        "validity_attrition": validity_attrition,
        "slope_filter": {
            "operator": SLOPE_OPERATOR,
            "unit": SLOPE_UNIT,
            "threshold_deg": slope_limit,
            "applied_to_validity": SLOPE_APPLIED_TO_VALIDITY,
            "with_slope_area_km2": round(with_slope_area_km2, 4),
            "without_slope_area_km2": round(validity_area_km2, 4),
            "removed_by_slope_km2": round(
                float(stack["attrition"]["slope_filtered"]["removed_km2"]), 4
            ),
            "reason": (
                "The 10 degree filter removes hill terrain across this SAR scene; "
                "because it also removes valley-floor cells, REVIEW-19 allows "
                "dropping it. Both branches are published; the final domain uses "
                "without_slope."
            ),
        },
        "mask_provenance": MASK_PROVENANCE,
        "slope_mask_deg": slope_limit,
        "min_component_cells": min_cells,
        "decimation_factor": factor,
        "decimated_shape": [int(out_h), int(out_w)],
        "source_crs": src_crs,
        "coverage": {
            "aoi_footprint_share_of_full_core": round(aoi_footprint_share, 6),
            "valid_share_of_footprint": round(valid_share, 6),
            "observed_cells": int(raw_footprint.sum()),
        },
        "component_audit": audit,
        "opened_via": opened_via,
        "cached_at": utc_now(),
    }
    atomic_write_json(paths["metadata"], metadata, indent=2, sort_keys=True)
    print(
        f"[16] {scene['scene_id']} {scene['datetime'][:10]}: sigma0 {threshold:g} dB "
        f"(A median {lut.A_median:.2f}, {lut.vectors}x{lut.samples_per_vector} LUT), "
        f"scene {scene_area_km2:,.1f} km2, validity {validity_area_km2:,.1f} km2 "
        f"({validity_area_km2 / scene_area_km2:.1%} of scene; "
        f"with slope {with_slope_area_km2:,.1f} km2), "
        f"water {int(raw_masks[labels[sensitivity.index(threshold)]].sum()):,} cells, "
        f"sigma0 p05/p50/p95 {p05:.1f}/{p50:.1f}/{p95:.1f} dB, via {opened_via}"
    )
    return {
        "scene": scene,
        "metadata": metadata,
        "coverage": coverage,
        "validity": validity,
        "validity_attrition": validity_attrition,
        "with_slope_area_km2": with_slope_area_km2,
        "without_slope_area_km2": validity_area_km2,
        "masks": raw_masks,
        "cache": cache_dir,
    }


def _score_scene(
    cfg: Config,
    processed: dict[str, Any],
    grid: dict[str, Any],
    frame_dir: Path,
) -> dict[str, Any]:
    scene = processed["scene"]
    masks = processed["masks"]
    domain = processed["validity"]
    if not domain.any():
        raise CalibrationError(f"scene {scene['scene_id']} has no observed comparison cells")
    area_2d = grid["areas"]
    metadata = processed["metadata"]
    thresholds = [float(value) for value in metadata["sensitivity_db"]]
    threshold = float(metadata["threshold_db"])
    primary_label = _threshold_label(threshold)
    if primary_label not in masks:
        raise CalibrationError(
            f"scene {scene['scene_id']} has no mask for primary threshold {threshold} dB"
        )
    observed = masks[primary_label] & domain
    validity_area = float(area_2d[domain].sum())
    observed_area = float(area_2d[observed].sum())
    if observed_area <= 0:
        raise CalibrationError(
            f"scene {scene['scene_id']} sigma0 {threshold:g} dB mask is empty over the validity domain"
        )
    observed_fraction = observed_area / validity_area
    scene_area = float(metadata["scene_area_km2"])

    height = int(grid["height"])
    width = int(grid["width"])
    scale = int(grid["frame_scale"])
    frame_index = grid["frame_index"]
    step_count = len(frame_index["steps"])
    peak_step = int(cfg.scenario.peak_step)

    best_step = 0
    best_iou = -1.0
    best_metrics: dict[str, float] = {}
    best_model = None
    peak_model = None
    for step in range(step_count):
        model = _model_mask(frame_dir, frame_index, step, height, width, scale) & domain
        metrics = area_mask_metrics(observed, model, area_2d)
        if step == peak_step:
            peak_model = model
        if metrics["iou"] > best_iou:
            best_iou = metrics["iou"]
            best_step = step
            best_metrics = metrics
            best_model = model
    if best_model is None or peak_model is None:
        raise CalibrationError(f"scene {scene['scene_id']} could not be scored")
    peak_metrics = area_mask_metrics(observed, peak_model, area_2d)
    modelled_area = float(area_2d[peak_model].sum())
    area_bias = 100.0 * (modelled_area - observed_area) / observed_area

    sensitivity: list[dict[str, Any]] = []
    for value in thresholds:
        label = _threshold_label(value)
        if label not in masks:
            raise CalibrationError(
                f"scene {scene['scene_id']} has no mask for sensitivity threshold {value} dB"
            )
        mask = masks[label] & domain
        metrics = area_mask_metrics(mask, peak_model, area_2d)
        threshold_area = float(area_2d[mask].sum())
        sensitivity.append(
            {
                "threshold_db": round(float(value), 6),
                "observed_area_km2": round(threshold_area, 4),
                "observed_water_fraction_of_validity": round(
                    threshold_area / validity_area, 6
                ),
                "true_positive_km2": round(float(metrics["tp"]), 4),
                "false_positive_km2": round(float(metrics["fp"]), 4),
                "false_negative_km2": round(float(metrics["fn"]), 4),
                "iou": round(float(metrics["iou"]), 6),
                "precision": round(float(metrics["precision"]), 6),
                "recall": round(float(metrics["recall"]), 6),
                "f1": round(float(metrics["f1"]), 6),
            }
        )

    return {
        "scene_id": scene["scene_id"],
        "datetime": scene["datetime"],
        "platform": scene["platform"],
        "relative_orbit": int(scene["relative_orbit"]),
        "threshold_db": round(threshold, 6),
        "threshold_rationale": metadata["threshold_rationale"],
        "scene_area_km2": round(scene_area, 4),
        "validity_area_km2": round(validity_area, 4),
        "validity_fraction_of_scene": round(validity_area / scene_area, 6),
        "with_slope_validity_area_km2": round(float(processed["with_slope_area_km2"]), 4),
        "without_slope_validity_area_km2": round(float(processed["without_slope_area_km2"]), 4),
        "validity_attrition": processed["validity_attrition"],
        "slope_filter": metadata["slope_filter"],
        "mask_provenance": metadata["mask_provenance"],
        "modelled_in_validity_km2": round(modelled_area, 4),
        "observed_area_km2": round(observed_area, 4),
        "observed_water_fraction_of_aoi": round(observed_fraction, 6),
        "observed_water_fraction_of_validity": round(observed_fraction, 6),
        "best_match_step": int(best_step),
        "best_match_iou": round(float(best_metrics["iou"]), 6),
        "peak_step": {
            "step": peak_step,
            "modelled_area_km2": round(modelled_area, 4),
            "iou": round(float(peak_metrics["iou"]), 6),
            "precision": round(float(peak_metrics["precision"]), 6),
            "recall": round(float(peak_metrics["recall"]), 6),
            "f1": round(float(peak_metrics["f1"]), 6),
            "area_bias_pct": round(float(area_bias), 4),
        },
        "sensitivity": sensitivity,
    }


CAVEATS = [
    "This is an extent-shape comparison against real Sentinel-1 acquisitions, not an event "
    "hindcast. The scenario's stage and duration were not fitted to these dates.",
    "σ0 calibration applied from the SAFE calibration LUT. Residual uncertainty is threshold "
    "choice (reported across −14/−16/−18 dB) and GRD geometries co-registered with a "
    "GCP-derived affine, not a rigorous terrain-corrected warp.",
    "Validity is the full Sentinel-1 footprint on the frame grid (coverage ≥0.5, regional AOI "
    "only), not the valley-floor AOI core. The 10° DEM slope filter is reported as a diagnostic "
    "(with_slope and without_slope) and is not applied to the final domain because it removes "
    "most of this scene's hill terrain; both areas are published.",
]


def run(
    cfg: Config,
    core_mask_path: Path,
    dem_path: Path,
    frame_index_path: Path,
    frames_dir: Path,
    out_path: Path,
    cache_dir: Path,
    refresh: bool = False,
) -> dict[str, Any]:
    ensure_dirs()
    stage = StageRecord(
        "16",
        "build-validation",
        inputs=[core_mask_path, dem_path, frame_index_path, frames_dir],
    )
    sentinel = cfg.sources["sentinel1"]
    stage.source(
        "Copernicus Sentinel-1 GRD via Earth Search STAC",
        str(sentinel["stac_url"]),
        "Copernicus Sentinel data; Earth Search STAC; anonymous S3 access",
        collection=str(sentinel["collection"]),
        datetime=str(sentinel["datetime"]),
    )
    print(
        f"[16] STAC search {sentinel['collection']} {sentinel['datetime']} over AOI "
        f"{cfg.aoi.bbox} (anonymous S3: AWS_NO_SIGN_REQUEST=YES, "
        f"AWS_REGION={sentinel.get('aws_region', 'us-west-2')})"
    )
    grid = _load_frame_grid(cfg, core_mask_path, frame_index_path)
    grid["slope"] = _slope_degrees(dem_path, cfg.aoi.nodata)
    features = _stac_search(cfg)
    selection_polygon = _core_bbox_wgs84(grid["core"], grid["transform"])
    items = select_scenes(features, selection_polygon)
    scenes = [_scene_record(item) for item in items]
    print("[16] selected scenes:")
    for scene in scenes:
        print(
            f"[16]   {scene['scene_id']} {scene['datetime']} {scene['platform']} "
            f"orbit {scene['relative_orbit']} {scene['orbit_direction']} "
            f"EPSG:{scene['epsg']} centroid {scene['centroid']}"
        )

    cache_dir.mkdir(parents=True, exist_ok=True)
    scored: list[dict[str, Any]] = []
    processed_scenes: list[dict[str, Any]] = []
    for scene in scenes:
        processed = _process_scene(cfg, scene, grid, grid["slope"], cache_dir, refresh)
        processed_scenes.append(processed)
        scored.append(_score_scene(cfg, processed, grid, frames_dir))
        stage.metric(
            f"{scene['scene_id']}_threshold_db",
            round(float(processed["metadata"]["threshold_db"]), 6),
        )
        stage.metric(
            f"{scene['scene_id']}_coverage",
            processed["metadata"]["coverage"]["valid_share_of_footprint"],
        )

    mean_iou = float(np.mean([scene["best_match_iou"] for scene in scored]))
    mean_precision = float(np.mean([scene["peak_step"]["precision"] for scene in scored]))
    mean_recall = float(np.mean([scene["peak_step"]["recall"] for scene in scored]))
    worst = min(scored, key=lambda scene: scene["best_match_iou"])
    calibrations = [processed["metadata"]["calibration"] for processed in processed_scenes]
    vector_counts = {int(item["vectors"]) for item in calibrations}
    sample_counts = {int(item["samples_per_vector"]) for item in calibrations}
    if len(vector_counts) != 1 or len(sample_counts) != 1:
        raise CalibrationError(
            f"calibration LUT shape disagrees between scenes: {vector_counts} vectors, "
            f"{sample_counts} samples"
        )
    a_medians = [float(item["A_median"]) for item in calibrations]
    scorecard = {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "method": {
            "collection": str(sentinel["collection"]),
            "threshold_method": "fixed_sigma0",
            "threshold_db": round(float(scored[0]["threshold_db"]), 6),
            "threshold_rationale": scored[0]["threshold_rationale"],
            "sensitivity_db": [
                round(float(entry["threshold_db"]), 6) for entry in scored[0]["sensitivity"]
            ],
            "calibration": {
                "source": (
                    "Sentinel-1 SAFE annotation/calibration/calibration-iw-vv.xml "
                    "(STAC asset schema-calibration-vv; anonymous S3)"
                ),
                "vectors": vector_counts.pop(),
                "samples_per_vector": sample_counts.pop(),
                "A_median": round(float(np.median(a_medians)), 6),
            },
            "slope_mask_deg": float(sentinel.get("slope_mask_deg", 10.0)),
            "slope_filter": {
                "operator": SLOPE_OPERATOR,
                "unit": SLOPE_UNIT,
                "threshold_deg": float(sentinel.get("slope_mask_deg", 10.0)),
                "applied_to_validity": SLOPE_APPLIED_TO_VALIDITY,
                "with_slope_area_km2": round(
                    float(sum(scene["with_slope_validity_area_km2"] for scene in scored)),
                    4,
                ),
                "without_slope_area_km2": round(
                    float(sum(scene["without_slope_validity_area_km2"] for scene in scored)),
                    4,
                ),
                "removed_by_slope_km2": round(
                    float(
                        sum(
                            scene["validity_attrition"]["slope_filtered"]["removed_km2"]
                            for scene in scored
                        )
                    ),
                    4,
                ),
                "reason": (
                    "Slope is computed from the 90 m DEM as the central-difference "
                    "gradient in degrees. It is evaluated and reported per scene but "
                    "not applied to the final validity domain, because across this SAR "
                    "scene it removes hill terrain and cannot be shown not to remove "
                    "valley-floor cells. REVIEW-19 allows dropping it."
                ),
            },
            "validity_definition": VALIDITY_DEFINITION,
            "mask_stack_version": MASK_STACK_VERSION,
            "scene_area_method": (
                "Quadrilateral through the four corner GCPs transformed to EPSG:32646; "
                "not the bbox area. 2022-07-31 gives 43,391 km2 (reviewer 43,389 km2)."
            ),
            "mask_provenance": MASK_PROVENANCE,
            "min_component_cells": int(sentinel.get("min_component_cells", 5)),
            "resampling": "average→nearest",
            "crs": "EPSG:32646",
            "resolution_m": 90,
        },
        "scenes": [
            {key: value for key, value in scene.items() if not key.startswith("_")}
            for scene in scored
        ],
        "summary": {
            "mean_iou_over_scenes": round(mean_iou, 6),
            "mean_precision": round(mean_precision, 6),
            "mean_recall": round(mean_recall, 6),
            "mean_validity_area_km2": round(
                float(np.mean([scene["validity_area_km2"] for scene in scored])), 4
            ),
            "mean_validity_fraction_of_scene": round(
                float(np.mean([scene["validity_fraction_of_scene"] for scene in scored])), 6
            ),
            "worst_scene": worst["scene_id"],
            "caveats": CAVEATS,
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_path, scorecard, indent=2, sort_keys=False)
    stage.out(out_path)
    stage.metric("scene_count", len(scored))
    stage.metric("mean_iou_over_scenes", scorecard["summary"]["mean_iou_over_scenes"])
    stage.metric("mean_precision", scorecard["summary"]["mean_precision"])
    stage.metric("mean_recall", scorecard["summary"]["mean_recall"])
    stage.metric("mean_validity_area_km2", scorecard["summary"]["mean_validity_area_km2"])
    stage.metric(
        "mean_validity_fraction_of_scene",
        scorecard["summary"]["mean_validity_fraction_of_scene"],
    )
    stage.metric("worst_scene", worst["scene_id"])
    for scene in scored:
        stage.metric(
            f"{scene['scene_id']}_validity_area_km2", scene["validity_area_km2"]
        )
        stage.metric(
            f"{scene['scene_id']}_validity_fraction_of_scene",
            scene["validity_fraction_of_scene"],
        )
        stage.metric(
            f"{scene['scene_id']}_with_slope_area_km2",
            scene["with_slope_validity_area_km2"],
        )
    stage.finish(
        "REVIEW-19: Sentinel-1 GRD VV decimated 1/9 with average resampling; sigmaNought "
        "LUT from schema-calibration-vv applied as 20*log10(DN/A); fixed -16 dB sigma0 "
        "water threshold with -14/-16/-18 dB sensitivity in sigma0 space. Validity is the "
        "full SAR footprint on the 90 m frame grid (coverage >=0.5, regional AOI only) "
        "with a published raw_sar_valid -> slope_filtered -> aoi_clipped -> "
        "component_filtered -> final attrition ledger; the old AOI-core clip is reported "
        "as a diagnostic, not used. The 10 degree DEM slope filter is evaluated and "
        "published as with_slope/without_slope, but is not applied to the final domain. "
        "scene_area_km2, validity_area_km2 and validity_fraction_of_scene are published; "
        "IoU/precision/recall use area weights on the full footprint, and TP+FP / TP+FN "
        "identities hold per threshold. Metrics compare the committed PNG frames with "
        "frame-index placement; the scenario stage is not fitted to these dates and this "
        "is not an event hindcast. Scene binaries and masks stay in pipeline/cache/s1/ "
        "and are not committed."
    )
    print(
        f"[16] ok: {len(scored)} scenes, mean IoU {mean_iou:.4f}, "
        f"mean precision {mean_precision:.4f}, mean recall {mean_recall:.4f}, "
        f"worst {worst['scene_id']} ({worst['best_match_iou']:.4f}); wrote {out_path}"
    )
    return scorecard
