"""Output schema definitions used by V01 and the stage writers."""
from __future__ import annotations

from typing import Any

CLASSES = ["source", "reference", "derived", "scenario", "synthetic"]
PHASES = ["onset", "rising", "peak", "receding"]
RISK_CLASSES = ["low", "moderate", "high", "very_high"]
BANDS = ["0.0-0.5", "0.5-1.5", "1.5-3.0", "3.0+"]

NUMBER_OR_NULL = {"type": ["number", "null"]}
STRING_OR_NULL = {"type": ["string", "null"]}


def _geometry_schema(point_only: bool = False) -> dict[str, Any]:
    if point_only:
        return {
            "type": "object",
            "required": ["type", "coordinates"],
            "properties": {
                "type": {"const": "Point"},
                "coordinates": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "items": {"type": "number"},
                },
            },
        }
    return {
        "type": "object",
        "required": ["type"],
        "properties": {
            "type": {
                "enum": [
                    "Point",
                    "MultiPoint",
                    "LineString",
                    "MultiLineString",
                    "Polygon",
                    "MultiPolygon",
                    "GeometryCollection",
                ]
            }
        },
    }


def geojson_schema(
    props: dict[str, Any], envelope_class: str, *, point_only: bool = False
) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["type", "name", "schema_version", "dataset_version", "class", "features"],
        "properties": {
            "type": {"const": "FeatureCollection"},
            "name": {"type": "string", "minLength": 1},
            "schema_version": {"const": "1.0.0"},
            "dataset_version": {"type": "string", "pattern": r"^\d{4}\.\d{2}\.\d+$"},
            "class": {"const": envelope_class},
            "features": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["type", "geometry", "properties"],
                    "properties": {
                        "type": {"const": "Feature"},
                        "geometry": _geometry_schema(point_only),
                        "properties": {
                            "type": "object",
                            "required": ["class"],
                            "properties": {
                                **props,
                                "class": {"enum": CLASSES},
                            },
                        },
                    },
                },
            },
        },
    }


DISTRICT_PROPS = {
    "district_id": {"type": "string", "minLength": 1},
    "name": {"type": "string", "minLength": 1},
    "iso": {"type": "string"},
    "area_km2": {"type": "number", "minimum": 0},
    "centroid_lon": {"type": "number"},
    "centroid_lat": {"type": "number"},
    "risk_score": NUMBER_OR_NULL,
    "risk_class": {"anyOf": [{"enum": RISK_CLASSES}, {"type": "null"}]},
    "rank": {"anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]},
    "valid_area_share": {"type": "number", "minimum": 0, "maximum": 1},
    "derived_fields": {"type": "array", "items": {"type": "string"}},
    "label": {"type": "string"},
}

STATE_PROPS = {
    "state_id": {"type": "string"},
    "name": {"type": "string"},
    "area_km2": {"type": "number", "minimum": 0},
    "district_count": {"type": "integer", "minimum": 1},
    "label": {"type": "string"},
}

RIVER_PROPS = {
    "river_id": {"type": "string"},
    "name": STRING_OR_NULL,
    "waterway": {"enum": ["river", "stream", "canal", "drain"]},
    "order": {"type": "integer", "minimum": 1, "maximum": 5},
    "source": {"enum": ["osm", "natural-earth"]},
    "source_id": {"type": "string"},
    "label": {"type": "string"},
}

FLOOD_PROPS = {
    "step": {"type": "integer", "minimum": 0, "maximum": 11},
    "step_label": {"type": "string"},
    "phase": {"enum": PHASES},
    "depth_band": {"enum": BANDS},
    "depth_m_lo": {"type": "number"},
    "depth_m_hi": NUMBER_OR_NULL,
    "band_area_km2": {"type": "number", "minimum": 0},
    "step_area_km2": {"type": "number", "minimum": 0},
    "model_version": {"type": "string"},
    "label": {"type": "string"},
}

ZONE_PROPS = {
    "zone_id": {"type": "string", "pattern": r"^RZ-\d{4}$"},
    "risk_class": {"enum": RISK_CLASSES},
    "risk_score": {"type": "number", "minimum": 0, "maximum": 100},
    "mean_hand_m": {"type": "number"},
    "mean_duration_days": {"type": "number", "minimum": 0},
    "peak_depth_m": {"type": "number", "minimum": 0},
    "area_km2": {"type": "number", "minimum": 0},
    "model_version": {"type": "string"},
    "label": {"type": "string"},
}

HOTSPOT_PROPS = {
    "hotspot_id": {"type": "string", "pattern": r"^HS-\d{2}$"},
    "rank": {"type": "integer", "minimum": 1, "maximum": 20},
    "reason": {"const": "low_hand_backwater_pocket"},
    "area_km2": {"type": "number", "minimum": 0},
    "hand_mean_m": {"type": "number"},
    "distance_to_channel_m": {"type": "number", "minimum": 0},
    "first_step": {"type": "integer", "minimum": 0, "maximum": 11},
    "peak_depth_m": {"type": "number", "minimum": 0},
    "centroid_lon": {"type": "number"},
    "centroid_lat": {"type": "number"},
    "district_id": STRING_OR_NULL,
    "label": {"type": "string"},
}

ASSET_PROPS = {
    "osm_id": {"type": "string", "pattern": r"^node/\d+$"},
    "facility": {"enum": ["hospital", "clinic", "school"]},
    "name": STRING_OR_NULL,
    "district_id": STRING_OR_NULL,
    "lon": {"type": "number"},
    "lat": {"type": "number"},
    "peak_depth_m": NUMBER_OR_NULL,
    "first_step": {"anyOf": [{"type": "integer", "minimum": 0, "maximum": 11}, {"type": "null"}]},
    "exposure_class": {"enum": ["none", "minor", "moderate", "major"]},
    "derived_fields": {"type": "array", "items": {"type": "string"}},
    "completeness": {"const": "incomplete-osm"},
    "label": {"type": "string"},
}

GAUGE_PROPS = {
    "gauge_id": {"type": "string", "pattern": r"^VG-\d{2}$"},
    "label": {"type": "string"},
    "river_name": STRING_OR_NULL,
    "river_id": {"type": "string"},
    "lon": {"type": "number"},
    "lat": {"type": "number"},
    "stage_series_m": {
        "type": "array",
        "minItems": 12,
        "maxItems": 12,
        "items": {"type": "number"},
    },
    "peak_step": {"type": "integer", "minimum": 0, "maximum": 11},
    "note": {"type": "string"},
}


SCENARIO_SCHEMA = {
    "type": "object",
    "required": [
        "schema_version",
        "scenario_id",
        "name",
        "class",
        "not_a_forecast",
        "step_count",
        "total_days",
        "peak_step",
        "threshold_stage_m",
        "grid",
        "steps",
        "model",
        "assumptions",
        "limitations",
    ],
    "properties": {
        "schema_version": {"const": "1.0.0"},
        "scenario_id": {"type": "string"},
        "name": {"type": "string"},
        "class": {"const": "synthetic"},
        "not_a_forecast": {"const": True},
        "step_count": {"const": 12},
        "total_days": {"type": "integer", "minimum": 1},
        "peak_step": {"type": "integer", "minimum": 0, "maximum": 11},
        "threshold_stage_m": {"type": "number"},
        "grid": {"type": "object"},
        "steps": {
            "type": "array",
            "minItems": 12,
            "maxItems": 12,
            "items": {
                "type": "object",
                "required": [
                    "step",
                    "label",
                    "day_offset",
                    "phase",
                    "rainfall_mm_day",
                    "mainstem_stage_m",
                    "backwater_m",
                    "stage_m",
                ],
                "properties": {
                    "step": {"type": "integer"},
                    "label": {"type": "string"},
                    "day_offset": {"type": "integer"},
                    "phase": {"enum": PHASES},
                    "rainfall_mm_day": {"type": "number"},
                    "mainstem_stage_m": {"type": "number"},
                    "backwater_m": {"type": "number"},
                    "stage_m": {"type": "number"},
                },
            },
        },
        "model": {"type": "object"},
        "assumptions": {"type": "array", "minItems": 4, "items": {"type": "string"}},
        "limitations": {"type": "array", "minItems": 5, "items": {"type": "string"}},
    },
}

FLOOD_SUMMARY_SCHEMA = {
    "type": "object",
    "required": [
        "schema_version",
        "scenario_id",
        "class",
        "peak_step",
        "series_class",
        "steps",
        "totals",
    ],
    "properties": {
        "schema_version": {"const": "1.0.0"},
        "scenario_id": {"type": "string"},
        "class": {"const": "scenario"},
        "peak_step": {"type": "integer"},
        "series_class": {"type": "object"},
        "steps": {
            "type": "array",
            "minItems": 12,
            "maxItems": 12,
            "items": {
                "type": "object",
                "required": [
                    "step",
                    "step_label",
                    "day_offset",
                    "phase",
                    "rainfall_mm_day",
                    "mainstem_stage_m",
                    "backwater_m",
                    "stage_m",
                    "above_threshold",
                    "inundated_area_km2",
                    "wet_cells",
                    "new_inundation_km2",
                    "receded_area_km2",
                    "max_depth_m",
                    "mean_depth_m",
                    "median_depth_m",
                    "p95_depth_m",
                    "delay_deciles",
                    "clamped_wet_share",
                    "component_filter",
                    "frame_file",
                    "frame_png_bytes",
                    "frame_width",
                    "frame_height",
                    "png_wet_cells",
                    "png_area_km2",
                    "affected_district_count",
                    "valid_cell_share",
                ],
                "properties": {
                    "step": {"type": "integer", "minimum": 0, "maximum": 11},
                    "step_label": {"type": "string"},
                    "day_offset": {"type": "integer"},
                    "phase": {"enum": PHASES},
                    "rainfall_mm_day": {"type": "number"},
                    "mainstem_stage_m": {"type": "number"},
                    "backwater_m": {"type": "number"},
                    "stage_m": {"type": "number"},
                    "above_threshold": {"type": "boolean"},
                    "inundated_area_km2": {"type": "number", "minimum": 0},
                    "wet_cells": {"type": "integer", "minimum": 0},
                    "new_inundation_km2": {"type": "number", "minimum": 0},
                    "receded_area_km2": {"type": "number", "minimum": 0},
                    "max_depth_m": NUMBER_OR_NULL,
                    "mean_depth_m": NUMBER_OR_NULL,
                    "median_depth_m": NUMBER_OR_NULL,
                    "p95_depth_m": NUMBER_OR_NULL,
                    "delay_deciles": {
                        "type": "object",
                        "required": ["p10", "p25", "p50", "p75", "p90", "p95"],
                        "properties": {
                            "p10": {"type": "number", "minimum": 0},
                            "p25": {"type": "number", "minimum": 0},
                            "p50": {"type": "number", "minimum": 0},
                            "p75": {"type": "number", "minimum": 0},
                            "p90": {"type": "number", "minimum": 0},
                            "p95": {"type": "number", "minimum": 0},
                        },
                    },
                    "clamped_wet_share": NUMBER_OR_NULL,
                    "component_filter": {
                        "type": "object",
                        "required": [
                            "method",
                            "min_cells",
                            "opening",
                            "components_before",
                            "components_after",
                            "dropped_area_km2",
                        ],
                        "properties": {
                            "method": {"const": "component_area_filter"},
                            "min_cells": {"type": "integer", "minimum": 9},
                            "opening": {"const": "none"},
                            "components_before": {"type": "integer", "minimum": 0},
                            "components_after": {"type": "integer", "minimum": 0},
                            "dropped_area_km2": {"type": "number", "minimum": 0},
                        },
                    },
                    "frame_file": {"type": "string", "pattern": r"^frames/step-\d{2}\.png$"},
                    "frame_png_bytes": {"type": "integer", "minimum": 1},
                    "frame_width": {"type": "integer", "minimum": 1},
                    "frame_height": {"type": "integer", "minimum": 1},
                    "png_wet_cells": {"type": "integer", "minimum": 0},
                    "png_area_km2": {"type": "number", "minimum": 0},
                    "affected_district_count": {"type": "integer", "minimum": 0},
                    "valid_cell_share": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "totals": {"type": "object"},
    },
}


FRAME_INDEX_SCHEMA = {
    "type": "object",
    "required": [
        "schema_version",
        "dataset_version",
        "scenario_id",
        "class",
        "bbox",
        "width",
        "height",
        "crs",
        "frame_resolution_m",
        "classes",
        "steps",
    ],
    "properties": {
        "schema_version": {"const": "1.0.0"},
        "dataset_version": {"type": "string"},
        "scenario_id": {"type": "string"},
        "class": {"const": "scenario"},
        "bbox": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {"type": "number"},
        },
        "width": {"type": "integer", "minimum": 1},
        "height": {"type": "integer", "minimum": 1},
        "crs": {"const": "EPSG:4326"},
        "frame_resolution_m": {"type": "number", "minimum": 1},
        "classes": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {
                "type": "object",
                "required": ["id", "label", "color", "min_m", "max_m"],
                "properties": {
                    "id": {"type": "integer", "minimum": 0, "maximum": 4},
                    "label": {"type": "string"},
                    "color": {"type": "string", "pattern": r"^#[0-9a-f]{6}$"},
                    "min_m": NUMBER_OR_NULL,
                    "max_m": NUMBER_OR_NULL,
                },
            },
        },
        "steps": {
            "type": "array",
            "minItems": 12,
            "maxItems": 12,
            "items": {
                "type": "object",
                "required": ["id", "label", "stage_m", "file", "area_km2"],
                "properties": {
                    "id": {"type": "integer", "minimum": 0, "maximum": 11},
                    "label": {"type": "string"},
                    "stage_m": {"type": "number"},
                    "file": {"type": "string", "pattern": r"^frames/step-\d{2}\.png$"},
                    "area_km2": {"type": "number", "minimum": 0},
                    "png_bytes": {"type": "integer", "minimum": 1},
                    "png_wet_cells": {"type": "integer", "minimum": 0},
                    "png_area_km2": {"type": "number", "minimum": 0},
                },
            },
        },
    },
}

DISTRICT_RISK_SCHEMA = {
    "type": "object",
    "required": [
        "schema_version",
        "scenario_id",
        "class",
        "generated_at",
        "weights_version",
        "weights",
        "reference_values",
        "risk_class_area_share",
        "districts",
        "counts",
    ],
    "properties": {
        "schema_version": {"const": "1.0.0"},
        "scenario_id": {"type": "string"},
        "class": {"const": "derived"},
        "generated_at": {"type": "string"},
        "weights_version": {"type": "string", "minLength": 1},
        "weights": {
            "type": "object",
            "required": ["area_share", "duration"],
            "properties": {
                "area_share": {"type": "number", "minimum": 0, "maximum": 1},
                "duration": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "additionalProperties": False,
        },
        "reference_values": {
            "type": "object",
            "required": ["area_share_saturation", "duration_saturation_days"],
            "properties": {
                "area_share_saturation": {"type": "number", "minimum": 0},
                "duration_saturation_days": {"type": "number", "minimum": 0},
            },
        },
        "risk_class_area_share": {
            "type": "object",
            "description": (
                "Area share of the four per-cell risk classes over all analysis cells "
                "wet at the scenario peak step (S07) with valid HAND in AOI v2. The "
                "denominator is peak wet area, not district polygon area; the four "
                "shares sum to 1."
            ),
            "required": ["low", "moderate", "high", "very_high"],
            "properties": {
                "low": {"type": "number", "minimum": 0, "maximum": 1},
                "moderate": {"type": "number", "minimum": 0, "maximum": 1},
                "high": {"type": "number", "minimum": 0, "maximum": 1},
                "very_high": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "additionalProperties": False,
        },
        "districts": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "rank",
                    "district_id",
                    "name",
                    "area_km2",
                    "peak_flooded_area_km2",
                    "area_share",
                    "mean_duration_days",
                    "p90_peak_depth_m",
                    "depth_over_1_5m_share",
                    "median_depth_m",
                    "risk_score",
                    "risk_class",
                    "drivers",
                    "valid_area_share",
                    "class",
                ],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1},
                    "district_id": {"type": "string"},
                    "name": {"type": "string"},
                    "area_km2": {"type": "number"},
                    "peak_flooded_area_km2": {"type": "number"},
                    "area_share": {"type": "number", "minimum": 0, "maximum": 1},
                    "mean_duration_days": {"type": "number"},
                    "p90_peak_depth_m": {"type": "number"},
                    "depth_over_1_5m_share": {"type": "number", "minimum": 0, "maximum": 1},
                    "median_depth_m": {"type": "number", "minimum": 0},
                    "risk_score": {"type": "number", "minimum": 0, "maximum": 100},
                    "risk_class": {"enum": RISK_CLASSES},
                    "drivers": {"type": "array", "maxItems": 2, "items": {"enum": ["area", "duration"]}},
                    "valid_area_share": {"type": "number", "minimum": 0, "maximum": 1},
                    "class": {"const": "derived"},
                },
            },
        },
        "counts": {"type": "object"},
    },
}

MONSOON_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "scenario_id", "class", "series", "threshold"],
    "properties": {
        "schema_version": {"const": "1.0.0"},
        "scenario_id": {"type": "string"},
        "class": {"const": "synthetic"},
        "series": {
            "type": "array",
            "minItems": 4,
            "items": {
                "type": "object",
                "required": ["id", "label", "unit", "class", "source_note", "points"],
                "properties": {
                    "id": {
                        "enum": [
                            "rainfall",
                            "mainstem_stage",
                            "backwater",
                            "stage_above_drainage",
                        ]
                    },
                    "label": {"type": "string"},
                    "unit": {"type": "string"},
                    "class": {"enum": ["synthetic", "scenario"]},
                    "source_note": {"type": "string"},
                    "points": {
                        "type": "array",
                        "minItems": 12,
                        "maxItems": 12,
                        "items": {
                            "type": "object",
                            "required": ["step", "day", "value"],
                            "properties": {
                                "step": {"type": "integer"},
                                "day": {"type": "integer"},
                                "value": {"type": "number"},
                            },
                        },
                    },
                },
            },
        },
        "threshold": {"type": "object"},
    },
}

CROSS_SECTION_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "scenario_id", "class", "transects"],
    "properties": {
        "schema_version": {"const": "1.0.0"},
        "scenario_id": {"type": "string"},
        "class": {"const": "derived"},
        "transects": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "transect_id",
                    "label",
                    "start",
                    "end",
                    "length_km",
                    "sample_count",
                    "samples",
                    "class",
                    "label_note",
                ],
                "properties": {
                    "transect_id": {"type": "string"},
                    "label": {"type": "string"},
                    "start": {"type": "array", "minItems": 2, "maxItems": 2},
                    "end": {"type": "array", "minItems": 2, "maxItems": 2},
                    "length_km": {"type": "number"},
                    "sample_count": {"type": "integer", "minimum": 30},
                    "samples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "distance_km",
                                "lon",
                                "lat",
                                "ground_m",
                                "hand_m",
                                "water_surface_m",
                                "depth_m",
                            ],
                            "properties": {
                                "distance_km": {"type": "number"},
                                "lon": {"type": "number"},
                                "lat": {"type": "number"},
                                "ground_m": {"type": "number"},
                                "hand_m": {"type": "number"},
                                "water_surface_m": {"type": "array", "minItems": 12, "maxItems": 12},
                                "depth_m": {"type": "array", "minItems": 12, "maxItems": 12},
                            },
                        },
                    },
                    "class": {"const": "derived"},
                    "label_note": {"type": "string"},
                },
            },
        },
    },
}

VALIDATION_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "generated_at", "dataset_version", "status", "checks", "counts"],
    "properties": {
        "schema_version": {"const": "1.0.0"},
        "generated_at": {"type": "string"},
        "dataset_version": {"type": "string"},
        "status": {"enum": ["pass", "fail"]},
        "checks": {
            "type": "array",
            "minItems": 30,
            "items": {
                "type": "object",
                "required": ["id", "name", "status", "expected", "actual", "detail"],
                "properties": {
                    "id": {"type": "string", "pattern": r"^(V\d{2}|V-A(?:10|[1-9]))$"},
                    "name": {"type": "string"},
                    "status": {"enum": ["pass", "warn", "fail"]},
                    "expected": {"type": "string"},
                    "actual": {"type": "string"},
                    "detail": {"type": "string"},
                },
            },
        },
        "counts": {"type": "object"},
    },
}

MANIFEST_SCHEMA = {
    "type": "object",
    "required": [
        "schema_version",
        "dataset_version",
        "app_min_version",
        "scenario_id",
        "generated_at",
        "crs",
        "analysis_crs",
        "bbox",
        "step_count",
        "load_tiers",
        "files",
        "attribution",
    ],
    "properties": {
        "schema_version": {"const": "1.0.0"},
        "dataset_version": {"type": "string"},
        "app_min_version": {"type": "string"},
        "scenario_id": {"type": "string"},
        "generated_at": {"type": "string"},
        "crs": {"const": "EPSG:4326"},
        "analysis_crs": {"const": "EPSG:32646"},
        "bbox": {"type": "array", "minItems": 4, "maxItems": 4},
        "step_count": {"const": 12},
        "load_tiers": {"type": "object"},
        "files": {"type": "array", "minItems": 1},
        "attribution": {"type": "array"},
    },
}

PROVENANCE_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "generated_at", "entries"],
    "properties": {
        "schema_version": {"const": "1.0.0"},
        "generated_at": {"type": "string"},
        "entries": {
            "type": "array",
            "minItems": 8,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "dataset",
                    "class",
                    "source_name",
                    "source_url",
                    "licence",
                    "pipeline",
                    "output_paths",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "class": {"enum": CLASSES},
                    "pipeline": {"type": "array", "minItems": 1},
                    "output_paths": {"type": "array", "minItems": 0},
                },
            },
        },
    },
}


SCHEMAS: dict[str, dict[str, Any]] = {
    "scenario.json": SCENARIO_SCHEMA,
    "flood/flood-summary.json": FLOOD_SUMMARY_SCHEMA,
    "flood/frame-index.json": FRAME_INDEX_SCHEMA,
    "admin/assam-districts.geojson": geojson_schema(DISTRICT_PROPS, "source"),
    "admin/assam-state.geojson": geojson_schema(STATE_PROPS, "source"),
    "hydro/assam-rivers.geojson": geojson_schema(RIVER_PROPS, "source"),
    "risk/risk-zones.geojson": geojson_schema(ZONE_PROPS, "derived"),
    "risk/district-risk.json": DISTRICT_RISK_SCHEMA,
    "risk/hotspots.geojson": geojson_schema(HOTSPOT_PROPS, "derived", point_only=True),
    "series/monsoon-series.json": MONSOON_SCHEMA,
    "series/cross-sections.json": CROSS_SECTION_SCHEMA,
    "assets/critical-facilities.geojson": geojson_schema(ASSET_PROPS, "source", point_only=True),
    "gauges/virtual-gauges.geojson": geojson_schema(GAUGE_PROPS, "synthetic", point_only=True),
    "validation-report.json": VALIDATION_SCHEMA,
    "manifest.json": MANIFEST_SCHEMA,
    "provenance.json": PROVENANCE_SCHEMA,
}
