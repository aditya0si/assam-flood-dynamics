# Baanh offline data pipeline (phase A)

This package fetches the probed public sources once, computes the 12-step
HAND-threshold monsoon scenario, and writes the committed GeoJSON/JSON under
`public/data/`. It is offline after the raw responses are cached. Nothing here
is an operational forecast: rainfall, stage and the scenario threshold are
synthetic; terrain, boundaries and rivers are source data; inundation and risk
are derived.

## Environment

- Python 3.11.16 (64-bit) on Windows 11.
- Installed/importable: `numpy 2.4.3`, `scipy 1.17.1`, `rasterio 1.4.4`,
  `shapely 2.2.0`, `pyproj 3.7.2`, `Pillow 12.3.0`, `mercantile 1.2.1`,
  `requests 2.33.0`, `jsonschema 4.26.0`, `pytest 9.1.1`.
- No GDAL system install, no venv, no paid key.

Install (optional) and run:

```powershell
python -m pip install -e pipeline
python -m baanh_pipeline.cli --help
```

If the editable install is blocked by a sandbox ACL (as on the build machine),
use the source path directly; every command below is equivalent:

```powershell
$env:PYTHONPATH = (Resolve-Path pipeline\src).Path
python -m baanh_pipeline.cli --help
```

## Configuration

All constants live in `pipeline/config/`, never in stage code:

| File | Contents |
|---|---|
| `aoi.json` | AOI bbox `[89.55, 23.95, 96.15, 28.15]`, EPSG:32646, 90 m, nodata, zoom, buffers |
| `scenario.json` | 12 synthetic steps, stage/rainfall/backwater table, model parameters, assumptions, limitations |
| `sources.json` | exact source URLs, licences, attribution, HTTP retry/timeout policy |
| `pipeline.json` | DEM decode/fill/hillshade constants, river/burn/risk/series thresholds, size caps, tier metadata |
| `transects.json` | three cross-section endpoints |

## Stages and commands

All commands run from the repository root. `$py` below means
`python -m baanh_pipeline.cli`.

| Stage | Command | Committed output |
|---|---|---|
| 01 | `$py fetch-terrain --aoi pipeline/config/aoi.json --sources pipeline/config/sources.json --zoom 11 --cache pipeline/cache/terrain` | none (tile cache + `pipeline/work/terrain-index.json`) |
| 02 | `$py fetch-boundaries --aoi ... --sources ... --cache pipeline/cache/boundaries` | none (raw ADM2 + `source-meta.json`) |
| 03 | `$py fetch-rivers --aoi ... --sources ... --cache pipeline/cache/rivers --overpass-timeout 180` | none (raw rivers + `rivers-source.json`) |
| 04 | `$py build-dem --tiles pipeline/cache/terrain --index pipeline/work/terrain-index.json --aoi ... --out-dem pipeline/work/dem-90m.tif --out-hillshade public/data/basemap/assam-hillshade.webp --hillshade-width 2000` | `basemap/assam-hillshade.webp` |
| 05 | `$py build-admin --raw pipeline/cache/boundaries/geoboundaries-ind-adm2.json --aoi ... --out-districts pipeline/work/districts-base.geojson --out-state public/data/admin/assam-state.geojson --out-centroids pipeline/work/district-centroids.json` | `admin/assam-state.geojson` |
| 06 | `$py build-rivers --raw pipeline/cache/rivers/rivers-raw.geojson --dem pipeline/work/dem-90m.tif --state public/data/admin/assam-state.geojson --aoi ... --out public/data/hydro/assam-rivers.geojson --out-channels pipeline/work/channel-lines.geojson` | `hydro/assam-rivers.geojson` (AOI v2 + waterway=river policy) |
| 07 | `$py burn-rivers --dem pipeline/work/dem-90m.tif --channels pipeline/work/channel-lines.geojson --out-dem pipeline/work/dem-burned.tif --out-channels pipeline/work/channels-90m.tif --burn-depth-m 3.0` | none |
| 08 | `$py compute-hand --dem-burned pipeline/work/dem-burned.tif --channels pipeline/work/channels-90m.tif --max-channel-distance-m 12000 --out-hand pipeline/work/hand-90m.tif --out-distance pipeline/work/channel-distance-90m.tif --out-meta pipeline/work/hand-meta.json` | none |
| 09 | `$py build-inundation --dem pipeline/work/dem-burned.tif --hand pipeline/work/hand-90m.tif --distance pipeline/work/channel-distance-90m.tif --channels pipeline/work/channels-90m.tif --state public/data/admin/assam-state.geojson --scenario pipeline/config/scenario.json --out-frames public/data/flood/flood-frames.geojson --out-summary public/data/flood/flood-summary.json --out-masks pipeline/work/inundation-masks --out-frames-dir pipeline/work/flood-frames` | `flood/flood-frames.geojson`, `flood/flood-summary.json`, `scenario.json` (copy) |
| 10 | `$py build-risk --masks pipeline/work/inundation-masks --hand ... --distance ... --channels ... --districts pipeline/work/districts-base.geojson --scenario ... --out-zones public/data/risk/risk-zones.geojson --out-ranking public/data/risk/district-risk.json --out-districts public/data/admin/assam-districts.geojson --out-hotspots public/data/risk/hotspots.geojson` | districts, risk zones, ranking, hotspots |
| 11 | `$py build-series --scenario ... --summary public/data/flood/flood-summary.json --dem pipeline/work/dem-90m.tif --channels ... --transects pipeline/config/transects.json --out-series public/data/series/monsoon-series.json --out-profiles public/data/series/cross-sections.json` | series + cross-sections |
| 12 | `$py build-assets --aoi ... --sources ... --masks pipeline/work/inundation-masks --hand pipeline/work/hand-90m.tif --frames ... --districts ... --out public/data/assets/critical-facilities.geojson` | optional, omitted if Overpass is unavailable |
| 13 | `$py build-gauges --rivers public/data/hydro/assam-rivers.geojson --summary public/data/flood/flood-summary.json --out public/data/gauges/virtual-gauges.geojson` | optional virtual gauges |
| 14 | `$py validate --data public/data --config pipeline/config --report public/data/validation-report.json --version 2026.10.0` | `validation-report.json` |
| 15 | `$py publish --data public/data --version 2026.10.0 --manifest public/data/manifest.json --provenance public/data/provenance.json` | `manifest.json`, `provenance.json` |
| 16 | `$py build-validation --aoi pipeline/config/aoi.json --sources pipeline/config/sources.json --core-mask pipeline/work/aoi-v2-core-90m.tif --dem pipeline/work/dem-90m.tif --frame-index public/data/flood/frame-index.json --frames public/data/flood/frames --scenario pipeline/config/scenario.json --out public/data/validation/scorecard.json --cache pipeline/cache/s1` | `validation/scorecard.json` (P1; no scene or mask committed) |
| 17 | `$py build-rainfall --cache pipeline/cache/era5 --out-rainfall public/data/series/rainfall.json --out-forecast public/data/series/rainfall-forecast.json` | `series/rainfall.json` (ERA5 JJAS 06-01..09-30 only, 2015-2025, district 2022 JJAS and 2015-2025 JJAS means; 32-point calls cached per year/chunk, ≥10 s apart, resumable on 429) and `series/rainfall-forecast.json` (separate current-window model series) |
| 18 | `$py build-exposure --cache pipeline/cache/worldpop --masks pipeline/work/inundation-masks --out public/data/exposure/district-exposure.json` | `exposure/district-exposure.json` (WorldPop 2020 masked zonal `potentially_exposed_residents`, `district_population`, `exposed_share_of_district`; AOI-clipped `population_within_aoi`) |

Each stage writes `pipeline/work/provenance/<stage>.json` with the command,
wall time, byte counts, source URLs, resolved package versions and output
hashes. `publish` aggregates those fragments. Writes are atomic
(temp file + `os.replace`), JSON is UTF-8 without BOM and uses
`allow_nan=False`.

## Re-run from scratch

```powershell
$env:PYTHONPATH = (Resolve-Path pipeline\src).Path
Remove-Item -Recurse -Force pipeline/cache, pipeline/work, public/data -ErrorAction SilentlyContinue
# run stages 01..18 in the table above, in order
```

`public/data/` is rebuilt entirely by stages 04–18. Do not hand-edit it.

## Cache and intermediates

| Path | Contents | Committed? |
|---|---|---|
| `pipeline/cache/terrain/11/{x}/{y}.png` | 1,064 Terrarium z11 tiles (55.3 MB) | no |
| `pipeline/cache/boundaries/` | geoBoundaries ADM2 + ADM1 Assam filter geometry, source metadata | no |
| `pipeline/cache/rivers/overpass-rivers.json` | exact whole-AOI Overpass response, when it succeeds | no |
| `pipeline/cache/rivers/overpass-split/*.json` | same query split into 1.0° × 0.6° cells, cached per cell | no |
| `pipeline/cache/rivers/ne_10m_rivers_lake_centerlines.geojson` | Natural Earth fallback copy | no |
| `pipeline/cache/era5/` | Open-Meteo archive batches (0.25° ERA5 grid) and the separate current-window response | no |
| `pipeline/cache/worldpop/` | WorldPop 2020 India 1 km Aggregated population raster (~19 MB) | no |
| `pipeline/work/*.tif` | DEM, burned DEM, channel mask, distance, HAND, nearest-channel elevation | no |
| `pipeline/work/inundation-masks/step-XX-wet.tif` | per-step uint8 wet masks (≤300 MB total), consumed by stages 10 and 12 | no |
| `pipeline/work/aoi-v2-*.tif`, `aoi-v2.json` | AOI v2 core/edge/clip masks and measured areas | no |
| `pipeline/work/provenance/*.json` | per-stage provenance fragments | no |

The terrain, boundary and split-river caches are reused on re-runs unless
`--refresh` is passed. A re-run is idempotent: timestamps change, numeric
outputs do not.

## Reproducing the committed bytes

The committed outputs are the artifact. Given the same cached raw responses,
the numeric outputs are deterministic; the timestamps in
`validation-report.json`, `provenance.json` and `manifest.json` differ between
runs and are excluded from geometric comparisons. The exact command sequence
is the stage table above, in order, with `--version 2026.10.0`. The manifest
records SHA-256 and byte size for every committed file; `validate` and
`publish` refuse on any mismatch or failed gate.

## Deviations from the written spec (with reasons)

1. **ADM2 Assam filter.** The current geoBoundaries `IND/ADM2` release has an
   empty `shapeISO` for every feature and no parent-state field. The stage
   downloads the same source's ADM1 Assam polygon and selects ADM2 features by
   >50% overlap or representative-point containment. This is recorded in
   `source-meta.json` and provenance; the committed output is still ADM2.
2. **Overpass query shape.** The whole-AOI query is frequently rejected with
   HTTP 502 while the public endpoint is at capacity. The stage tries the exact
   query once, then runs the same query in a 1.0° × 0.6° grid with per-cell
   caching and bounded retries. Partial OSM results are never mixed with the
   Natural Earth fallback: if any cell cannot be fetched, the stage falls back
   to Natural Earth and records why.
3. **Burn cap.** The 5×5 minimum minus 3 m can be hundreds of metres below the
   channel centre in the steep Himalayan/Barail reaches included for
   continuity. The burn is capped at 6 m below the pre-burn channel elevation
   and the adjacent 5×5 mean, so a modelling device cannot become an
   unrealistic canyon. `burn-meta.json` records `capped_cells` and both
   centre-cell and adjacent-mean deltas.
4. **Hillshade decode mode.** Pillow encodes the 8-bit grayscale hillshade as
   WebP and decodes it as near-grayscale RGB (max channel difference ≤2).
   `validate` accepts that and checks width 2000 and the 1.5 MB cap.
5. **Python version.** The build machine has Python 3.11.16, not the 3.14.7
   claimed in the standing brief. All listed packages are importable and the
   environment is 64-bit; no venv is used.
6. **Editable install.** `pip install -e pipeline` is blocked by the Windows
   sandbox ACL on this machine (pip cannot write its build-tracker temp file).
   Commands use `PYTHONPATH=pipeline/src`; this is functionally equivalent to
   the editable install and does not change any output.
7. **P1 layers.** Stages 12 (facilities) and 13 (gauges) are optional P1
   outputs. If Overpass is unavailable, stage 12 omits the layer and records a
   warning; it never substitutes a hand-built facility list.

## Timings

See `docs/PIPELINE-REPORT.md` for the measured wall time, peak RSS where
observed, bytes in/out and exit code of every stage from the phase-A run.
