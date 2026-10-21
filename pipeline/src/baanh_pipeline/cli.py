"""Stage CLI for the Baanh offline pipeline."""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from . import __version__
from .config import load_config
from .util import ensure_dirs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m baanh_pipeline.cli",
        description="Baanh offline data pipeline (HAND-threshold Assam flood scenario).",
    )
    parser.add_argument("--version", action="version", version=f"baanh-pipeline {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str):
        command = sub.add_parser(name, help=help_text)
        return command

    p = add("fetch-terrain", "Stage 01: fetch cached Terrarium z11 elevation tiles")
    p.add_argument("--aoi", required=True)
    p.add_argument("--sources", required=True)
    p.add_argument("--zoom", type=int, default=11)
    p.add_argument("--cache", required=True)
    p.add_argument("--refresh", action="store_true")

    p = add("fetch-boundaries", "Stage 02: fetch geoBoundaries ADM2 and select Assam")
    p.add_argument("--aoi", required=True)
    p.add_argument("--sources", required=True)
    p.add_argument("--cache", required=True)
    p.add_argument("--refresh", action="store_true")

    p = add("fetch-rivers", "Stage 03: fetch OSM rivers or the Natural Earth fallback")
    p.add_argument("--aoi", required=True)
    p.add_argument("--sources", required=True)
    p.add_argument("--cache", required=True)
    p.add_argument("--overpass-timeout", type=int, default=180)
    p.add_argument("--refresh", action="store_true")

    p = add("build-dem", "Stage 04: mosaic/warp the DEM and write the hillshade")
    p.add_argument("--tiles", required=True)
    p.add_argument("--index", required=True)
    p.add_argument("--aoi", required=True)
    p.add_argument("--out-dem", required=True)
    p.add_argument("--out-hillshade", required=True)
    p.add_argument("--hillshade-width", type=int, default=2000)
    p.add_argument("--refresh", action="store_true")

    p = add("build-admin", "Stage 05: build district/state GeoJSON and centroids")
    p.add_argument("--raw", required=True)
    p.add_argument("--aoi", required=True)
    p.add_argument("--out-districts", required=True)
    p.add_argument("--out-state", required=True)
    p.add_argument("--out-centroids", required=True)

    p = add("build-rivers", "Stage 06: AOI v2, channel policy v2 and display rivers")
    p.add_argument("--raw", required=True)
    p.add_argument("--dem", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--aoi", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--out-channels", required=True)

    p = add("burn-rivers", "Stage 07: burn channel cells into the DEM")
    p.add_argument("--dem", required=True)
    p.add_argument("--channels", required=True)
    p.add_argument("--out-dem", required=True)
    p.add_argument("--out-channels", required=True)
    p.add_argument("--burn-depth-m", type=float, default=3.0)

    p = add("compute-hand", "Stage 08: nearest drainage distance and HAND")
    p.add_argument("--dem-burned", required=True)
    p.add_argument("--channels", required=True)
    p.add_argument("--max-channel-distance-m", type=float, default=12000)
    p.add_argument("--out-hand", required=True)
    p.add_argument("--out-distance", required=True)
    p.add_argument("--out-meta", required=True)

    p = add("build-inundation", "Stage 09: scenario inundation frames and summary")
    p.add_argument("--dem", required=True)
    p.add_argument("--hand", required=True)
    p.add_argument("--distance", required=True)
    p.add_argument("--channels", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--scenario", required=True)
    p.add_argument("--out-frames", required=True)
    p.add_argument("--out-summary", required=True)
    p.add_argument("--out-masks", required=True)
    p.add_argument("--out-frames-dir", required=True)

    p = add("build-risk", "Stage 10: risk zones, district ranking and hotspots")
    p.add_argument("--masks", required=True)
    p.add_argument("--hand", required=True)
    p.add_argument("--distance", required=True)
    p.add_argument("--channels", required=True)
    p.add_argument("--districts", required=True)
    p.add_argument("--scenario", required=True)
    p.add_argument("--out-zones", required=True)
    p.add_argument("--out-ranking", required=True)
    p.add_argument("--out-districts", required=True)
    p.add_argument("--out-hotspots", required=True)

    p = add("build-series", "Stage 11: monsoon series and cross-sections")
    p.add_argument("--scenario", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--dem", required=True)
    p.add_argument("--channels", required=True)
    p.add_argument("--transects", required=True)
    p.add_argument("--out-series", required=True)
    p.add_argument("--out-profiles", required=True)

    p = add("build-assets", "Stage 12 (P1): OSM facility exposure")
    p.add_argument("--aoi", required=True)
    p.add_argument("--sources", required=True)
    p.add_argument("--masks", required=True)
    p.add_argument("--hand", required=True)
    p.add_argument("--frames", required=True)
    p.add_argument("--districts", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--refresh", action="store_true")

    p = add("build-gauges", "Stage 13 (P1): virtual gauges")
    p.add_argument("--rivers", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--out", required=True)

    p = add("validate", "Stage 14: run V01–V20 and V-A1–V-A9, write the validation report")
    p.add_argument("--data", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--version", required=True)

    p = add("publish", "Stage 15: write manifest.json and provenance.json")
    p.add_argument("--data", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--provenance", required=True)

    return parser


def _dispatch(args) -> None:
    cfg = load_config()
    root = cfg.root

    def rel(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else root / path

    if args.command == "fetch-terrain":
        from . import fetch_terrain

        fetch_terrain.run(cfg, rel(args.cache), args.zoom, args.refresh)
    elif args.command == "fetch-boundaries":
        from . import fetch_boundaries

        fetch_boundaries.run(cfg, rel(args.cache), args.refresh)
    elif args.command == "fetch-rivers":
        from . import fetch_rivers

        fetch_rivers.run(cfg, rel(args.cache), args.overpass_timeout, args.refresh)
    elif args.command == "build-dem":
        from . import build_dem

        build_dem.run(
            cfg,
            rel(args.tiles),
            rel(args.index),
            rel(args.out_dem),
            rel(args.out_hillshade),
            args.hillshade_width,
        )
    elif args.command == "build-admin":
        from . import build_admin

        build_admin.run(cfg, rel(args.raw), rel(args.out_districts), rel(args.out_state), rel(args.out_centroids))
    elif args.command == "build-rivers":
        from . import build_rivers

        build_rivers.run(
            cfg, rel(args.raw), rel(args.dem), rel(args.state), rel(args.out), rel(args.out_channels)
        )
    elif args.command == "burn-rivers":
        from . import burn_rivers

        burn_rivers.run(cfg, rel(args.dem), rel(args.channels), rel(args.out_dem), rel(args.out_channels), args.burn_depth_m)
    elif args.command == "compute-hand":
        from . import hand

        hand.run(
            cfg,
            rel(args.dem_burned),
            rel(args.channels),
            rel(args.out_hand),
            rel(args.out_distance),
            rel(args.out_meta),
            args.max_channel_distance_m,
        )
    elif args.command == "build-inundation":
        from . import inundation

        inundation.run(
            cfg,
            rel(args.dem),
            rel(args.hand),
            rel(args.distance),
            rel(args.channels),
            rel(args.state),
            rel(args.scenario),
            rel(args.out_frames),
            rel(args.out_summary),
            rel(args.out_masks),
            rel(args.out_frames_dir),
        )
    elif args.command == "build-risk":
        from . import risk

        risk.run(
            cfg,
            rel(args.masks),
            rel(args.hand),
            rel(args.distance),
            rel(args.channels),
            rel(args.districts),
            rel(args.scenario),
            rel(args.out_zones),
            rel(args.out_ranking),
            rel(args.out_districts),
            rel(args.out_hotspots),
        )
    elif args.command == "build-series":
        from . import series

        series.run(
            cfg,
            rel(args.scenario),
            rel(args.summary),
            rel(args.dem),
            rel(args.channels),
            rel(args.transects),
            rel(args.out_series),
            rel(args.out_profiles),
        )
    elif args.command == "build-assets":
        from . import assets

        assets.run(
            cfg,
            rel(args.masks),
            rel(args.hand),
            rel(args.frames),
            rel(args.districts),
            rel(args.out),
            args.refresh,
        )
    elif args.command == "build-gauges":
        from . import gauges

        gauges.run(cfg, rel(args.rivers), rel(args.summary), rel(args.out))
    elif args.command == "validate":
        from . import validate

        validate.run(cfg, rel(args.data), rel(args.report), args.version)
    elif args.command == "publish":
        from . import publish

        publish.run(cfg, rel(args.data), args.version, rel(args.manifest), rel(args.provenance))
    else:  # pragma: no cover - argparse prevents this
        raise SystemExit(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    ensure_dirs()
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        _dispatch(args)
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        print(f"\n[FAIL] {args.command}: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
