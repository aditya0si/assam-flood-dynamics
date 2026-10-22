"""Small shared utilities: paths, atomic writes, hashing, provenance."""
from __future__ import annotations

import gzip
import hashlib
import importlib.metadata
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def repo_root() -> Path:
    # .../pipeline/src/baanh_pipeline/util.py -> repo root
    return Path(__file__).resolve().parents[3]


def pipeline_dir() -> Path:
    return repo_root() / "pipeline"


def cache_dir() -> Path:
    return pipeline_dir() / "cache"


def work_dir() -> Path:
    return pipeline_dir() / "work"


def provenance_dir() -> Path:
    return work_dir() / "provenance"


def data_dir() -> Path:
    return repo_root() / "public" / "data"


def ensure_dirs() -> None:
    for path in (
        cache_dir(),
        work_dir(),
        provenance_dir(),
        data_dir() / "admin",
        data_dir() / "hydro",
        data_dir() / "flood",
        data_dir() / "risk",
        data_dir() / "series",
        data_dir() / "exposure",
        data_dir() / "basemap",
        data_dir() / "assets",
        data_dir() / "gauges",
        data_dir() / "validation",
    ):
        path.mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def command_string() -> str:
    return "python -m baanh_pipeline.cli " + " ".join(sys.argv[1:])


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"not JSON serialisable: {type(value)!r}")


def json_bytes(value: Any, *, indent: int | None = None, sort_keys: bool = False) -> bytes:
    text = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        indent=indent,
        sort_keys=sort_keys,
        separators=(",", ":") if indent is None else None,
        default=_json_default,
    )
    return text.encode("utf-8")


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    )
    tmp = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def atomic_write_json(path: Path, value: Any, *, indent: int | None = None, sort_keys: bool = False) -> int:
    payload = json_bytes(value, indent=indent, sort_keys=sort_keys)
    atomic_write_bytes(path, payload)
    return len(payload)


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def path_size(path: Path) -> int:
    if path.is_dir():
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return path.stat().st_size if path.exists() else 0


def gzip_size(path: Path) -> int:
    """Transfer size a browser pays for ``path`` after gzip -9 (no metadata)."""
    if not path.is_file():
        return 0
    payload = path.read_bytes()
    return len(gzip.compress(payload, 9, mtime=0))


def gzip_bytes(payload: bytes) -> int:
    return len(gzip.compress(payload, 9, mtime=0))


def total_bytes(paths: Iterable[Path]) -> int:
    return sum(path_size(p) for p in paths)


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root()).as_posix()
    except ValueError:
        return path.as_posix()


def installed_versions() -> dict[str, str]:
    names = [
        "numpy",
        "scipy",
        "rasterio",
        "shapely",
        "pyproj",
        "Pillow",
        "mercantile",
        "requests",
        "jsonschema",
    ]
    versions: dict[str, str] = {"python": sys.version.split()[0]}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "unknown"
    return versions


class StageRecord:
    """Collect metrics for one stage and write its provenance fragment."""

    def __init__(self, stage: str, name: str, inputs: list[Path] | None = None):
        self.stage = stage
        self.name = name
        self.started_at = utc_now()
        self._start = time.perf_counter()
        self.inputs = list(inputs or [])
        self.outputs: list[Path] = []
        self.sources: list[dict[str, Any]] = []
        self.metrics: dict[str, Any] = {}
        self.notes = ""
        self.status = "ok"

    def out(self, *paths: Path) -> None:
        for path in paths:
            if path not in self.outputs:
                self.outputs.append(path)

    def source(self, name: str, url: str, licence: str, **extra: Any) -> None:
        self.sources.append({"name": name, "url": url, "licence": licence, **extra})

    def metric(self, key: str, value: Any) -> None:
        self.metrics[key] = value

    def finish(self, notes: str = "") -> dict[str, Any]:
        wall = round(time.perf_counter() - self._start, 3)
        self.notes = notes or self.notes
        fragment = {
            "schema_version": "1.0.0",
            "stage": self.stage,
            "name": self.name,
            "command": command_string(),
            "version": "1.0.0",
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": utc_now(),
            "wall_seconds": wall,
            "bytes_in": total_bytes(self.inputs),
            "bytes_out": total_bytes(self.outputs),
            "inputs": [
                {"path": relative(p), "bytes": path_size(p) if p.exists() else 0}
                for p in self.inputs
            ],
            "outputs": [
                {
                    "path": relative(p),
                    "bytes": path_size(p) if p.exists() else 0,
                    "sha256": sha256_file(p) if p.is_file() and p.exists() else None,
                }
                for p in self.outputs
            ],
            "sources": self.sources,
            "metrics": self.metrics,
            "versions": installed_versions(),
            "notes": self.notes,
        }
        path = provenance_dir() / f"{self.stage}.json"
        atomic_write_json(path, fragment, indent=2, sort_keys=True)
        return fragment


def load_fragments() -> dict[str, dict[str, Any]]:
    fragments: dict[str, dict[str, Any]] = {}
    for path in sorted(provenance_dir().glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                fragments[path.stem] = json.load(handle)
        except Exception:
            continue
    return fragments


def human_mb(value: int) -> str:
    return f"{value / (1024 * 1024):.2f} MB"
