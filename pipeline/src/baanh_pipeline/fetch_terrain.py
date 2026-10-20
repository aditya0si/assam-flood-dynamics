"""Stage 01 — fetch Terrarium elevation tiles with a bounded pool."""
from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import mercantile
from PIL import Image
from rasterio.warp import transform_bounds

from .config import Config
from .http import FetchError, fetch_bytes
from .util import StageRecord, atomic_write_json, ensure_dirs, utc_now, work_dir


def _valid_png(payload: bytes, size: int) -> bool:
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
            return image.size == (size, size)
    except Exception:
        return False


def run(cfg: Config, cache: Path, zoom: int, refresh: bool = False) -> dict:
    ensure_dirs()
    stage = StageRecord("01", "fetch-terrain")
    terrain = cfg.sources["terrain"]
    zoom = int(zoom or terrain["zoom"])
    tile_size = int(terrain["tile_size"])
    cache = cache if cache.is_absolute() else cfg.root / cache
    cache.mkdir(parents=True, exist_ok=True)

    tiles = list(mercantile.tiles(*cfg.aoi.bbox, zooms=[zoom]))
    tiles.sort(key=lambda t: (t.y, t.x))
    missing: list[str] = []
    tile_rows: list[dict] = []
    fetched = 0
    from_cache = 0

    def fetch_one(tile) -> tuple[mercantile.Tile, int | None, str | None, bool]:
        path = cache / str(tile.z) / str(tile.x) / f"{tile.y}.png"
        if path.exists() and path.stat().st_size > 0 and not refresh:
            payload = path.read_bytes()
            if _valid_png(payload, tile_size):
                return tile, len(payload), None, True
            path.unlink()
        url = terrain["url_template"].format(z=tile.z, x=tile.x, y=tile.y)
        try:
            result = fetch_bytes(cfg, url, path, refresh=True)
        except FetchError as exc:
            return tile, None, str(exc), False
        if not _valid_png(result.payload, tile_size):
            path.unlink(missing_ok=True)
            return tile, None, f"invalid PNG for {tile.z}/{tile.x}/{tile.y}", False
        return tile, len(result.payload), None, result.from_cache

    with ThreadPoolExecutor(max_workers=int(cfg.sources["http"]["terrain_concurrency"])) as pool:
        futures = [pool.submit(fetch_one, tile) for tile in tiles]
        for index, future in enumerate(as_completed(futures), start=1):
            tile, size, error, cached = future.result()
            if error:
                missing.append(f"{tile.z}/{tile.x}/{tile.y}: {error}")
            else:
                if cached:
                    from_cache += 1
                else:
                    fetched += 1
                tile_rows.append(
                    {"z": tile.z, "x": tile.x, "y": tile.y, "bytes": size}
                )
            if index % 100 == 0 or index == len(tiles):
                print(f"[01] tiles {index}/{len(tiles)} fetched={fetched} cached={from_cache} missing={len(missing)}")

    minx, miny, maxx, maxy = transform_bounds("EPSG:4326", "EPSG:3857", *cfg.aoi.bbox, densify_pts=21)
    index_payload = {
        "schema_version": "1.0.0",
        "zoom": zoom,
        "tile_count": len(tiles),
        "tile_count_present": len(tile_rows),
        "missing_count": len(missing),
        "missing_tiles": missing,
        "bbox_mercator": [minx, miny, maxx, maxy],
        "bbox_wgs84": list(cfg.aoi.bbox),
        "fetched_at": utc_now(),
        "tile_size_px": tile_size,
        "tiles": tile_rows,
    }
    index_path = work_dir() / "terrain-index.json"
    atomic_write_json(index_path, index_payload, indent=2, sort_keys=True)
    stage.out(index_path)
    stage.metric("tile_count", len(tiles))
    stage.metric("present", len(tile_rows))
    stage.metric("missing", len(missing))
    stage.metric("fetched_this_run", fetched)
    stage.metric("cache_hits", from_cache)
    stage.source(terrain["name"], terrain["url_template"], terrain["licence"])
    stage.finish(
        f"z{zoom}; bounded pool {cfg.sources['http']['terrain_concurrency']}; "
        f"retries {cfg.sources['http']['retries']} with backoff."
    )

    missing_fraction = len(missing) / max(1, len(tiles))
    if missing_fraction > float(terrain["missing_fraction_fail"]):
        raise RuntimeError(
            f"stage 01: {len(missing)}/{len(tiles)} tiles missing "
            f"({missing_fraction:.3%} > {float(terrain['missing_fraction_fail']):.3%}); "
            f"first failures: {missing[:5]}"
        )
    print(
        f"[01] ok: {len(tiles)} tiles, {len(missing)} missing, "
        f"{sum(r['bytes'] or 0 for r in tile_rows) / 1024 / 1024:.1f} MB cached"
    )
    return index_payload
