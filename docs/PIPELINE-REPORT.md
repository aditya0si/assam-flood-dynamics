# Baanh M0 phase A — pipeline report

**Status: BLOCKED at stage 09 (`build-inundation`).** Stages 01–08 are green.
Stages 09–15 were not completed and no flood/risk/series data was published.
The stage refused to continue because the specified scenario produced a peak
inundation area larger than the specification's own 30%-of-Assam sanity bound.
No data was edited, no stage value was changed, and no gate was lowered to
make the run pass.

- Run date: 2026-10-21 (local), Windows 11, Python 3.11.16 (64-bit).
- Repository: `C:\Users\oliad\Desktop\baanh`.
- Working tree at the time of this report: pipeline code and the committed
  source/geometry outputs; `pipeline/cache/` and `pipeline/work/` are gitignored.
- The stage-09 failure is reproducible with the exact command in
  [Stage 09](#stage-09--failure) below.

## Result at a glance

| Item | Result |
|---|---|
| Stages 01–08 | exit 0 |
| Stage 09 | **exit 1** — peak 30,330 km² (38.8% of Assam) vs expected <23,466 km² (<30%) |
| Stages 10–15 | not run |
| `public/data/` | only `admin/assam-state.geojson`, `hydro/assam-rivers.geojson`, `basemap/assam-hillshade.webp` |
| `validation-report.json` | not produced (stage 14 not run; stage 09 has no passing output) |
| `provenance.json` | not produced (stage 15 not run; per-stage fragments 01–08 exist) |
| `manifest.json` | not produced |
| Committed data tags | critical 0.91 MB, animation 0.00 MB, fallback 0.58 MB, total 1.49 MB |

`scenario.json`, `flood/flood-frames.geojson`, `flood/flood-summary.json`,
`risk/*`, `series/*`, `assets/*`, `gauges/*`, `validation-report.json`,
`provenance.json` and `manifest.json` are **absent** by design: publishing
them would either fabricate a passing run or hand-author data, both forbidden
by the brief.

## AOI, grid and sources

| Parameter | Value |
|---|---|
| AOI bbox (WGS84) | `[89.55, 23.95, 96.15, 28.15]` |
| Analysis CRS / resolution | EPSG:32646 / 90 m |
| Analysis grid | 7,466 × 5,223 = 39.0 M cells |
| Grid bounds (EPSG:32646) | `[148770, 2648610, 820710, 3118680]` |
| Terrarium tiles | z11, 1,064 tiles, 0 missing, 55.3 MB cached |
| geoBoundaries ADM2 | 735 India features → 33 Assam districts (3.2 MB filtered) |
| OSM rivers | 17,870 ways, 79,023 km, 43.06 MB raw (whole-AOI Overpass query succeeded) |
| Assam state mask | 9.68 M cells, 78,221 km² |
| HAND valid share inside Assam | 99.89% |
| Clamped negative HAND cells | 5.29% (warning, recorded in `hand-meta.json`) |

## Per-stage record

Wall time and byte counts are the values written by each stage to
`pipeline/work/provenance/<stage>.json`. `bytes out` includes intermediate
rasters where the stage writes them; committed files are called out
separately. Stage 09 failed before it could write a fragment, so its time is
the observed console interval and its output is the intermediate stack only.

| Stage | Command (abbreviated) | Wall | Bytes in | Bytes out | Exit | Committed output |
|---|---|---:|---:|---:|---:|---|
| 01 | `fetch-terrain --zoom 11` | 299.7 s | 0 | 87,653 (index) + 55.3 MB cache | 0 | none |
| 02 | `fetch-boundaries` | 50.9 s | 0 | 3,350,320 | 0 | none |
| 03 | `fetch-rivers --overpass-timeout 180` | 133.4 s | 0 | 45,155,091 | 0 | none |
| 04 | `build-dem --hillshade-width 2000` | 96.2 s | 58,092,279 | 109,479,931 | 0 | `basemap/assam-hillshade.webp` 609,072 B |
| 05 | `build-admin` | 0.5 s | 3,348,595 | 206,330 | 0 | `admin/assam-state.geojson` 35,963 B |
| 06 | `build-rivers` | 19.4 s | 45,155,091 | 7,350,544 | 0 | `hydro/assam-rivers.geojson` 921,411 B |
| 07 | `burn-rivers --burn-depth-m 3.0` | 13.9 s | 115,298,986 | 110,138,611 | 0 | none |
| 08 | `compute-hand --max-channel-distance-m 12000` | 65.3 s | 110,138,134 | 191,564,364 | 0 | none |
| 09 | `build-inundation …` | ≈ 30 min (observed) | 277,951,707 B (265 MB) | 2,339,695,658 B stack (intermediate) | **1** | **none** |
| 10–15 | not run | — | — | — | — | — |

### Stage 04 details

- Mosaic decode + bilinear warp to EPSG:32646 at 90 m.
- DEM min −49.0 m, max 7,461.8 m; 357,572 void cells before fill, 10,844 after
  `fillnodata(max_search_distance=100)`; 0.00% exactly-zero cells.
- Hillshade: 2,000 × 1,417 px, 315°/45°, WebP quality 82, 609,072 B.
- The Terrarium release contains a small cluster of void pixels that decode to
  about −5,456 m; values below the configured −50 m valid floor are treated as
  nodata before the warp so bilinear interpolation cannot smear them.

### Stage 06 details

- 12,787 lines retained after clipping to AOI + 5 km and dropping lines
  <500 m; 78,137 km total; 15 order-1 Brahmaputra ways.
- Display layer: 1,476 named rivers, simplified at 200 m, 921,411 B. The 1.0 MB
  cap forced the display layer to named rivers only; streams/canals/drains
  remain in `channel-lines.geojson` (6.3 MB) and are used for burn/HAND.
- Channel layer: all waterways, simplified at 45 m, used for rasterisation.

### Stage 07 details

- 1,068,977 channel cells; mean centre-cell lowering 2.35 m; max 6.00 m;
  35,410 cells capped.
- The uncapped 5×5-minimum process lowered some steep reaches by up to
  hundreds of metres (mean centre-cell lowering 16.5 m, p95 6.0 m after the
  cap). The cap at 6 m below the pre-burn cell and the adjacent 5×5 mean is
  recorded in `burn-meta.json`; without it the stage's own 1–6 m check fails.
- The cap is a declared modelling guard, not a surveyed incision depth.

### Stage 08 details

- Exact Euclidean distance transform on the 1,068,977-cell channel mask;
  38,879,489 valid HAND cells; p50 40.12 m, p95 752.24 m.
- 99.89% of Assam-masked cells have valid HAND (≥80% floor, ≥85% target).
- 5.29% of valid cells have negative raw HAND and were clamped to 0; this is
  above the 2% warning threshold and is recorded in `hand-meta.json`. It does
  not fail V17 (which fails below 80% coverage); the validation report, had it
  run, would carry this as a warning.

## Stage 09 — failure

Command:

```powershell
python -m baanh_pipeline.cli build-inundation `
  --dem pipeline/work/dem-burned.tif `
  --hand pipeline/work/hand-90m.tif `
  --distance pipeline/work/channel-distance-90m.tif `
  --channels pipeline/work/channels-90m.tif `
  --state public/data/admin/assam-state.geojson `
  --scenario pipeline/config/scenario.json `
  --out-frames public/data/flood/flood-frames.geojson `
  --out-summary public/data/flood/flood-summary.json `
  --out-stack pipeline/work/inundation-stack.npz
```

Observed:

```text
stage 09: peak area 30,330 km² exceeds 30% of Assam (23,466 km²)
```

Expected by `DATA-PIPELINE.md` §10 (`build-inundation` assertions):

```text
peak area > 0
peak area < 30% of Assam
```

Observed peak: **30,330 km² = 38.8% of the 78,221 km² Assam mask**, at S07
(25 Aug, stage 6.0 m).

The full sequence from the same run:

| Step | Stage (m) | Wet area (km²) | % of Assam | Max depth (m) | Components | Dropped |
|---|---:|---:|---:|---:|---:|---:|
| S00 | 0.5 | 3,067 | 3.9% | 0.5 | 20,778 | 20,290 |
| S01 | 1.0 | 3,340 | 4.3% | 1.0 | 24,305 | 23,818 |
| S02 | 1.7 | 3,957 | 5.1% | 1.7 | 30,178 | 29,698 |
| S03 | 2.5 | 5,612 | 7.2% | 2.5 | 39,200 | 38,734 |
| S04 | 3.4 | 9,558 | 12.2% | 3.4 | 45,816 | 45,377 |
| S05 | 4.3 | 17,279 | 22.1% | 4.3 | 36,270 | 35,945 |
| S06 | 5.2 | 24,630 | 31.5% | 5.2 | 27,147 | 26,879 |
| **S07** | **6.0** | **30,330** | **38.8%** | **6.0** | 20,833 | 20,599 |
| S08 | 5.2 | 24,630 | 31.5% | 5.2 | 27,147 | 26,879 |
| S09 | 4.1 | 15,661 | 20.0% | 4.1 | 38,322 | 37,973 |
| S10 | 2.9 | 6,610 | 8.5% | 2.9 | 43,206 | 42,743 |
| S11 | 1.6 | 3,802 | 4.9% | 1.6 | 29,268 | 28,786 |

The other stage-09 assertions **do** hold on this run:

- Rising limb S00–S07 is non-decreasing.
- Recession S08–S11 is non-increasing.
- The peak is at step 7, as required.
- Peak area > 0.
- New/receded areas are non-negative (computed from the same masks).

Only the peak-area sanity bound fails.

### Why this is not a coding bug

The computation follows `DATA-PIPELINE.md` §7.5–§7.7:

```text
wet_raw = valid_hand AND inside_assam AND (hand <= stage_s)
depth_raw = max(0, stage_s - hand)
connectivity: 8-connected, component must touch a channel cell or a cell
              with distance <= 90 m; components < 3 cells dropped
```

The state mask is the dissolved Assam outline (78,221 km²), not the full AOI.
The stage counts only cells inside that mask. The peak is a genuine model
result for the committed 90 m DEM and the OSM channel network.

### Diagnostic: the uncapped burn also exceeds the bound

A non-committed diagnostic re-ran the nearest-drainage/HAND step with the
**uncapped** 5×5-minimum burn (the literal §7.3 process) and counted the same
connected wet cells. Estimated peak at stage 6.0 m: **25,808 km² (33.0%)**,
still above the 23,466 km² bound. The capped burn raises channel elevations
relative to the uncapped process (mean centre lowering 2.35 m instead of
16.5 m), which lowers HAND and increases the area to 30,330 km²; the cap is
therefore a contributing factor but not the sole cause. Both the literal and
the capped process violate the 30% bound on this terrain/channel set.

The two stage assertions therefore conflict for this DEM/channel network:

- The literal 5×5-minimum burn violates stage 07's 1–6 m mean-lowering check
  (observed 16.5 m).
- The capped burn passes stage 07's check but violates stage 09's 30% bound
  (observed 38.8%; the uncapped estimate is 33.0%).

## Deviations from the written specification

1. **ADM2 Assam filter.** The current geoBoundaries `IND/ADM2` release has an
   empty `shapeISO` for all 735 features and no parent-state field. The stage
   downloads the same source's ADM1 Assam polygon and selects ADM2 features by
   >50% overlap or representative-point containment. Recorded in
   `pipeline/cache/boundaries/source-meta.json`; the committed layer is still
   ADM2. The API-reported licences are ODbL 1.0 (ADM2) and CC BY 2.5 IN
   (ADM1 filter geometry), not the CC BY 4.0 stated in the data spec.
2. **Overpass query shape.** The whole-AOI query is frequently rejected with
   HTTP 502 while the public endpoint is at capacity. The stage tries the exact
   query once, then the same query in a 1.0° × 0.6° grid with per-cell caching
   and bounded retries. Partial OSM results are never mixed with the Natural
   Earth fallback. The final run's whole-AOI query succeeded on its first
   attempt (1 attempt, 17,870 ways), so the split path was not used for the
   committed river layer. The split code remains for reproducibility.
3. **Burn cap.** The 5×5 minimum minus 3 m can be hundreds of metres below the
   channel centre in steep Himalayan/Barail reaches. The burn is capped at 6 m
   below the pre-burn cell and the adjacent 5×5 mean; `burn-meta.json` records
   `capped_cells = 35,410`, centre-cell and adjacent-mean deltas. The cap was
   required to satisfy the stage's 1–6 m check; its interaction with the peak
   area is described above.
4. **Display river layer.** The 1.0 MB cap could not be met with all 12,787
   rivers/streams/canals/drains even at 300 m (4.4 MB). The display layer keeps
   named rivers only, simplified at 200 m (1,476 features, 921 KB); the channel
   layer keeps every way for burn/HAND. This is a cap-driven display
   simplification, not a change to the model input.
5. **Inundation polygonisation.** The spec prefers simplification in
   EPSG:32646. Unioning/simplifying one MultiPolygon with tens of thousands of
   disjoint parts was intractable, so band parts are projected to WGS84 once
   and simplified part-by-part with a 75 m latitude-equivalent tolerance
   (75/111320°). Areas and band membership are computed on the raster; the
   output geometry is still WGS84, 5 dp, RFC 7946 winding.
6. **Hillshade decode mode.** Pillow encodes the 8-bit grayscale hillshade as
   WebP and decodes it as near-grayscale RGB (max channel difference 2). The
   validation code accepts this and checks width 2000 and the 1.5 MB cap; the
   stage did not run here.
7. **Python version.** The build machine has Python 3.11.16, not the 3.14.7
   claimed in the standing brief. All listed packages are importable; no venv.
8. **Editable install.** `pip install -e pipeline` is blocked by the Windows
   sandbox ACL on this machine (pip cannot write its build-tracker temp file).
   Commands use `PYTHONPATH=pipeline/src`; this is functionally equivalent.
9. **P1 layers.** Stages 12 (facilities) and 13 (gauges) were not reached.
   Stage 12 is optional and would have been omitted with a warning if Overpass
   had been unavailable; it never substitutes a hand-built list.

## Committed data size by tag (partial run)

These are the only committed data files after stages 04–07. The tags are the
ones `pipeline/config/pipeline.json` assigns; the critical tier is incomplete
because `scenario.json`, `provenance.json`, `validation-report.json`,
`district-risk.json` and `monsoon-series.json` were not produced.

| Tag | Files committed | Bytes |
|---|---|---:|
| critical | `admin/assam-state.geojson`, `hydro/assam-rivers.geojson` | 957,374 (0.91 MB) |
| animation | none | 0 |
| optional | none | 0 |
| fallback | `basemap/assam-hillshade.webp` | 609,072 (0.58 MB) |
| **total** | | **1,566,446 (1.49 MB)** |

The intended critical/animation budget (≤3.5 MB / ≤7.6 MB) was not reached
because the flood, risk and series layers are absent.

## What is reproducible now

- `pipeline/` is committed; the stage CLI, config, tests and README are in
  place.
- `pipeline/cache/` contains the raw terrain, ADM2, OSM rivers and fallback
  data; `pipeline/work/` contains the DEM, burned DEM, channel mask, distance,
  HAND, the 2.34 GB inundation depth/wet stack and per-stage fragments 01–08.
- Re-running stages 01–08 from the cache produces the same raster statistics;
  re-running stage 09 reproduces the same peak-area failure.
- The exact commands are in `pipeline/README.md`.

## Recommendation

Do not publish a flood layer from this run. A reviewer must choose one of:

1. **Revise the 30% sanity bound** (with evidence) to a value consistent with
   this DEM/channel network, or state that the bound is a warning rather than
   a hard stop. The uncapped literal process estimates 33.0%; the capped
   process gives 38.8%.
2. **Revise the scenario/model** (for example, a lower peak stage, a different
   channel class policy, or a verified channel network) and re-run stages
   07–15. Any such change must update the scenario table, config, summary,
   series and validation expectations together; it must not be a silent gate
   relaxation.
3. **Validate the channel policy**: restrict HAND's nearest-drainage channels
   to a documented subset (for example, rivers and named tributaries rather
   than every OSM drain/canal) if that is the intended model. That is a
   specification change, not a bug fix, and would need a fresh review.

No further stages were run because doing so would either hand-author flood
data or lower a gate. The failing command and the observed/expected values are
recorded above.
