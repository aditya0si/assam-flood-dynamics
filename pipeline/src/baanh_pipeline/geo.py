"""CRS, geodesic-area and GeoJSON hygiene helpers."""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np
from pyproj import Geod, Transformer
from rasterio.features import rasterize
from rasterio.transform import Affine, from_origin
from rasterio.warp import transform_bounds
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
    box,
    mapping,
    shape,
)
from shapely.geometry.polygon import orient
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union
from shapely.validation import make_valid

from .config import AoiConfig


@lru_cache(maxsize=16)
def _transformer(src: str, dst: str) -> Transformer:
    return Transformer.from_crs(src, dst, always_xy=True)


@lru_cache(maxsize=4)
def geod() -> Geod:
    return Geod(ellps="WGS84")


def project_geom(geom, src: str, dst: str):
    if geom.is_empty:
        return geom
    transformer = _transformer(src, dst)
    return shapely_transform(transformer.transform, geom)


def project_coords(coords: Iterable[tuple[float, float]], src: str, dst: str):
    transformer = _transformer(src, dst)
    xs, ys = zip(*coords)
    lon, lat = transformer.transform(xs, ys)
    return list(zip(lon, lat))


def valid(geom):
    if geom is None or geom.is_empty:
        return geom
    if geom.is_valid:
        return geom
    return make_valid(geom)


def geodesic_area_km2(geom) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    area, _ = geod().geometry_area_perimeter(geom)
    return abs(float(area)) / 1_000_000.0


def geodesic_length_km(geom) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    return abs(float(geod().geometry_length(geom))) / 1000.0


def analysis_grid(aoi: AoiConfig) -> tuple[Affine, int, int, tuple[float, float, float, float]]:
    """Snapped EPSG:32646 grid covering the WGS84 AOI rectangle."""
    minx, miny, maxx, maxy = transform_bounds(
        aoi.output_crs,
        aoi.analysis_crs,
        *aoi.bbox,
        densify_pts=101,
    )
    res = aoi.resolution_m
    minx = math.floor(minx / res) * res
    miny = math.floor(miny / res) * res
    maxx = math.ceil(maxx / res) * res
    maxy = math.ceil(maxy / res) * res
    width = int(round((maxx - minx) / res))
    height = int(round((maxy - miny) / res))
    return from_origin(minx, maxy, res, res), width, height, (minx, miny, maxx, maxy)


def row_cell_areas_km2(transform: Affine, height: int, width: int, src_crs: str) -> np.ndarray:
    """Geodesic area of one grid cell per raster row (km²).

    The UTM grid is nearly equal-area at this scale; using a per-row ellipsoidal
    area removes the latitude trend instead of treating every cell as planar.
    """
    res = abs(transform.a)
    x0 = transform.c
    x1 = transform.c + res
    rows = np.arange(height + 1, dtype=np.float64)
    ys = transform.f - rows * res
    xs = np.concatenate([np.full(height + 1, x0), np.full(height + 1, x1)])
    ys_all = np.concatenate([ys, ys])
    lon, lat = _transformer(src_crs, "EPSG:4326").transform(xs, ys_all)
    areas = np.empty(height, dtype=np.float64)
    for row in range(height):
        ring = [
            (float(lon[row]), float(lat[row])),
            (float(lon[height + 1 + row]), float(lat[height + 1 + row])),
            (float(lon[height + 2 + row]), float(lat[height + 2 + row])),
            (float(lon[row + 1]), float(lat[row + 1])),
        ]
        areas[row] = geodesic_area_km2(Polygon(ring))
    return areas.reshape(height, 1)


def clean_ring(coords: Iterable[Iterable[float]], decimals: int) -> list[list[float]]:
    cleaned: list[list[float]] = []
    for pair in coords:
        values = [round(float(pair[0]), decimals), round(float(pair[1]), decimals)]
        if cleaned and cleaned[-1] == values:
            continue
        cleaned.append(values)
    if cleaned and cleaned[0] != cleaned[-1]:
        cleaned.append(list(cleaned[0]))
    if len(cleaned) < 4:
        return []
    return cleaned


def _polygon_to_geojson(poly: Polygon, decimals: int) -> dict[str, Any] | None:
    poly = orient(poly, sign=1.0)  # RFC 7946 exterior counter-clockwise
    exterior = clean_ring(poly.exterior.coords, decimals)
    if not exterior:
        return None
    rings = [exterior]
    for interior in poly.interiors:
        ring = clean_ring(interior.coords, decimals)
        if ring:
            rings.append(ring)
    return {"type": "Polygon", "coordinates": rings}


def _line_to_geojson(line: LineString, decimals: int) -> dict[str, Any] | None:
    coords: list[list[float]] = []
    for pair in line.coords:
        values = [round(float(pair[0]), decimals), round(float(pair[1]), decimals)]
        if coords and coords[-1] == values:
            continue
        coords.append(values)
    if len(coords) < 2:
        return None
    return {"type": "LineString", "coordinates": coords}


def geom_to_geojson(geom, decimals: int = 5) -> dict[str, Any] | None:
    """GeoJSON mapping with rounded coordinates, deduplicated rings and winding."""
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return _polygon_to_geojson(geom, decimals)
    if isinstance(geom, MultiPolygon):
        parts = [_polygon_to_geojson(p, decimals) for p in geom.geoms]
        parts = [p for p in parts if p]
        return {"type": "MultiPolygon", "coordinates": [p["coordinates"] for p in parts]} if parts else None
    if isinstance(geom, LineString):
        return _line_to_geojson(geom, decimals)
    if isinstance(geom, MultiLineString):
        lines = [_line_to_geojson(line, decimals) for line in geom.geoms]
        lines = [line for line in lines if line]
        return {"type": "MultiLineString", "coordinates": [line["coordinates"] for line in lines]} if lines else None
    if isinstance(geom, Point):
        return {"type": "Point", "coordinates": [round(geom.x, decimals), round(geom.y, decimals)]}
    if isinstance(geom, MultiPoint):
        return {
            "type": "MultiPoint",
            "coordinates": [[round(p.x, decimals), round(p.y, decimals)] for p in geom.geoms],
        }
    if isinstance(geom, GeometryCollection):
        parts = [geom_to_geojson(g, decimals) for g in geom.geoms]
        parts = [p for p in parts if p]
        return {"type": "GeometryCollection", "geometries": parts} if parts else None
    raise TypeError(f"unsupported geometry type: {geom.geom_type}")


def feature(geom, properties: dict[str, Any], decimals: int = 5) -> dict[str, Any] | None:
    mapping_geom = geom_to_geojson(geom, decimals)
    if mapping_geom is None:
        return None
    return {"type": "Feature", "geometry": mapping_geom, "properties": properties}


def feature_collection(
    name: str,
    cls: str,
    features: list[dict[str, Any]],
    dataset_version: str,
    *,
    schema_version: str = "1.0.0",
) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "name": name,
        "schema_version": schema_version,
        "dataset_version": dataset_version,
        "class": cls,
        "features": features,
    }


def polygon_parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    if isinstance(geom, GeometryCollection):
        parts: list[Polygon] = []
        for item in geom.geoms:
            parts.extend(polygon_parts(item))
        return parts
    return []


def union_polygons(geoms: Iterable[Any]):
    items = [g for g in geoms if g is not None and not g.is_empty]
    if not items:
        return Polygon()
    # union_all is the fast Shapely 2 path and is deterministic for a fixed order.
    return unary_union(items)


def drop_small_parts(geom, min_area_km2: float, *, fill_small_holes: bool = True):
    """Drop polygon parts below the threshold and fill small holes."""
    parts = polygon_parts(geom)
    kept: list[Polygon] = []
    for part in parts:
        if geodesic_area_km2(part) < min_area_km2:
            continue
        if fill_small_holes and part.interiors:
            holes = []
            for interior in part.interiors:
                hole = Polygon(interior)
                if geodesic_area_km2(hole) >= min_area_km2:
                    holes.append(interior)
            part = Polygon(part.exterior, holes)
        kept.append(part)
    if not kept:
        return Polygon()
    return unary_union(kept)


def rasterize_geom(geom, transform: Affine, width: int, height: int, *, all_touched: bool = False, dtype="uint8"):
    return rasterize(
        [(geom, 1)],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        all_touched=all_touched,
        dtype=dtype,
    )


def rasterize_values(shapes: Iterable[tuple[Any, int]], transform: Affine, width: int, height: int, dtype="int32"):
    return rasterize(
        list(shapes),
        out_shape=(height, width),
        transform=transform,
        fill=0,
        all_touched=False,
        dtype=dtype,
    )


def load_geojson(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    return value


def iter_coords(geometry: dict[str, Any]) -> Iterator[tuple[float, float]]:
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "Point":
        yield (float(coords[0]), float(coords[1]))
    elif kind in ("MultiPoint", "LineString"):
        for pair in coords:
            yield (float(pair[0]), float(pair[1]))
    elif kind in ("MultiLineString", "Polygon"):
        for part in coords:
            for pair in part:
                yield (float(pair[0]), float(pair[1]))
    elif kind == "MultiPolygon":
        for poly in coords:
            for part in poly:
                for pair in part:
                    yield (float(pair[0]), float(pair[1]))
    elif kind == "GeometryCollection":
        for item in geometry.get("geometries", []):
            yield from iter_coords(item)


def bbox_polygon(bbox: tuple[float, float, float, float]):
    return box(*bbox)


def buffered_aoi(aoi: AoiConfig, buffer_km: float):
    geom = project_geom(bbox_polygon(aoi.bbox), aoi.output_crs, aoi.analysis_crs)
    return geom.buffer(buffer_km * 1000.0)


def point_in_geom(lon: float, lat: float, geom) -> bool:
    return geom.contains(Point(lon, lat)) or geom.touches(Point(lon, lat))


def grid_window_for_bounds(transform: Affine, bounds, pad_cells: int = 0):
    from rasterio.transform import rowcol

    left, bottom, right, top = bounds
    row_min, col_min = rowcol(transform, left, top, op=math.floor)
    row_max, col_max = rowcol(transform, right, bottom, op=math.ceil)
    row_min = max(0, row_min - pad_cells)
    col_min = max(0, col_min - pad_cells)
    row_max = row_max + pad_cells
    col_max = col_max + pad_cells
    return row_min, row_max, col_min, col_max


def transformer(src: str, dst: str) -> Transformer:
    return _transformer(src, dst)
