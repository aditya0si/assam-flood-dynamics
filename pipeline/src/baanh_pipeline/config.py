"""Configuration loading for the Baanh pipeline.

Every tunable value lives in ``pipeline/config/*.json``.  Modules import the
configuration objects from here rather than defining constants inline.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .util import pipeline_dir, repo_root


class ConfigError(RuntimeError):
    pass


def _reject_constant(value: str) -> None:
    raise ConfigError(f"non-finite JSON constant not allowed: {value}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle, parse_constant=_reject_constant)
    except FileNotFoundError as exc:
        raise ConfigError(f"missing config file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"top-level JSON object expected in {path}")
    return value


@dataclass(frozen=True)
class AoiConfig:
    raw: dict[str, Any]

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return tuple(float(v) for v in self.raw["bbox"])  # type: ignore[return-value]

    @property
    def analysis_crs(self) -> str:
        return str(self.raw["analysis_crs"])

    @property
    def output_crs(self) -> str:
        return str(self.raw["output_crs"])

    @property
    def resolution_m(self) -> float:
        return float(self.raw["resolution_m"])

    @property
    def nodata(self) -> float:
        return float(self.raw["nodata"])

    @property
    def terrain_zoom(self) -> int:
        return int(self.raw["terrain_zoom"])

    @property
    def max_channel_distance_m(self) -> float:
        return float(self.raw["max_channel_distance_m"])

    @property
    def decimals(self) -> int:
        return int(self.raw["coordinate_decimals"])

    @property
    def state_iso(self) -> str:
        return str(self.raw["state_filter"]["iso"])

    @property
    def state_name(self) -> str:
        return str(self.raw["state_filter"]["name"])


@dataclass(frozen=True)
class Scenario:
    raw: dict[str, Any]

    @property
    def scenario_id(self) -> str:
        return str(self.raw["scenario_id"])

    @property
    def steps(self) -> list[dict[str, Any]]:
        return list(self.raw["steps"])

    @property
    def step_count(self) -> int:
        return int(self.raw["step_count"])

    @property
    def peak_step(self) -> int:
        return int(self.raw["peak_step"])

    @property
    def threshold_m(self) -> float:
        return float(self.raw["threshold_stage_m"])

    @property
    def model(self) -> dict[str, Any]:
        return dict(self.raw["model"])

    @property
    def model_version(self) -> str:
        return str(self.raw["model"]["version"])

    @property
    def days(self) -> list[int]:
        return [int(s["day_offset"]) for s in self.steps]

    @property
    def stages(self) -> list[float]:
        return [float(s["stage_m"]) for s in self.steps]

    def weighted_duration(self, depth_raster) -> None:
        """Implemented in risk.py; present for type clarity only."""
        raise NotImplementedError


@dataclass(frozen=True)
class Config:
    aoi: AoiConfig
    scenario: Scenario
    sources: dict[str, Any]
    pipeline: dict[str, Any]
    transects: dict[str, Any]
    root: Path

    def stage_meta(self) -> dict[str, str]:
        return {
            "pipeline_version": str(self.pipeline.get("version", "1.0.0")),
            "schema_version": str(self.pipeline.get("schema_version", "1.0.0")),
        }


def load_config() -> Config:
    base = pipeline_dir() / "config"
    aoi = AoiConfig(load_json(base / "aoi.json"))
    scenario = Scenario(load_json(base / "scenario.json"))
    sources = load_json(base / "sources.json")
    pipe_cfg = load_json(base / "pipeline.json")
    transects = load_json(base / "transects.json")
    if len(scenario.steps) != scenario.step_count:
        raise ConfigError("scenario step_count does not match steps[]")
    for index, step in enumerate(scenario.steps):
        if int(step["step"]) != index:
            raise ConfigError("scenario steps must be contiguous from 0")
        expected = round(float(step["mainstem_stage_m"]) + float(step["backwater_m"]), 6)
        if abs(expected - float(step["stage_m"])) > 1e-9:
            raise ConfigError(f"scenario stage sum mismatch at step {index}")
    return Config(aoi, scenario, sources, pipe_cfg, transects, repo_root())
