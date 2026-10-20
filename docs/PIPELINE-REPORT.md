# Baanh M0 phase A2 — pipeline report

**Status: BLOCKED at stage 09 (`build-inundation`).** Stages 06–08 are green and
committed. Stage 09 computed a complete sequence and then refused to write the
committed frames because the combined file is 25,885,838 bytes against the
6,815,744-byte cap. Two A4 gates already fail on the same run: **V-A5**
(peak median depth 2.50 m vs ≤1.5 m) and **V-A6** (clamped HAND inside AOI v2
5.32 % vs ≤3.0 %). No gate was widened, no data was hand-edited, and no
flood/risk/series layer was published.

- Run date: 2026-10-21 (local), Windows 11, Python 3.11.16 (64-bit).
- Repository: `C:\Users\oliad\Desktop\baanh`.
- Interpreter invocation: `$env:PYTHONPATH='pipeline/src'; python -m baanh_pipeline.cli <stage>`.
  An editable install remains blocked by the sandbox ACL; this is the same
  workaround as phase A and is recorded in each provenance fragment.
- Working tree at the time of this report: A1/A2/A3/A5 code and config, the A4
  validator gates, the amended docs, and the committed river/state/hillshade
  outputs. `pipeline/cache/` and `pipeline/work/` are gitignored.

## Result at a glance

| Item | Result |
|---|---|
| Stages 06–08 | exit 0; stage 06 and 07 gates green, stage 08 completes with the V-A6 warning below |
| Stage 09 | **exit 1** — frames 25,885,838 B vs 6,815,744 B cap; V-A5 and V-A6 also fail |
| Stages 10–15 | not run (stage 09 has no passing accepted output) |
| `public/data/` | `admin/assam-state.geojson`, `hydro/assam-rivers.geojson`, `basemap/assam-hillshade.webp` only |
| `validation-report.json` | not produced; stage 14 was not run because stage 09 is blocked |
| `provenance.json` / `manifest.json` | not produced; per-stage fragments 06–08 exist |
| Committed data | critical 1,009,380 B (0.96 MB), animation 0 B, fallback 609,072 B (0.58 MB), total 1,618,452 B (1.54 MB) |

`scenario.json`, `flood/flood-frames.geojson`, `flood/flood-summary.json`,
`risk/*`, `series/*`, `assets/*`, `gauges/*`, `validation-report.json`,
`provenance.json` and `manifest.json` are absent by design. Publishing them
would either fabricate a passing run or hand-author data.

## AOI v2, grid and denominators

| Parameter | Measured value |
|---|---|
| AOI v2 definition | `(inside Assam) ∩ (DEM ≤ 120 m)` |
| AOI v2 core area | **52,240.7 km²** (6,463,969 cells) |
| AOI v2 2 km edge buffer | 61,655.7 km² (7,628,917 cells) — continuity only, not counted |
| AOI v2 + 5 km channel clip | 70,086.0 km² (8,672,040 cells) |
| Assam raster area | 78,220.6 km² (reference 78,523 km²) |
| Flood-prone denominator | 31,050 km² (Government of Assam, Water Resources Department; 39.6 % of 78,523 km²) |
| Analysis CRS / resolution | EPSG:32646 / 90 m |
| Analysis grid | 7,466 × 5,223 = 39.0 M cells |
| Grid bounds (EPSG:32646) | `[148770, 2648610, 820710, 3118680]` |

The flood-prone figure is a published **flood-prone-area statistic, not a
single event’s observed extent**. It is recorded in `sources.json` and will be
an explicit reference entry in `provenance.json`; V-A4 uses it only as a
plausibility denominator.

The 2 km edge buffer is 61,655.7 km², which is above V-A1’s 56,000 km² ceiling.
That is intentional and documented: V-A1 and all flood metrics use the **core**
mask; the buffer exists only so edge channels/terrain are continuous.

## Channel policy v2 (stage 06)

| Item | Measured value |
|---|---:|
| Raw OSM ways | 17,870 |
| `waterway=river` candidates after policy | 860 |
| Excluded: not `river` | 13,025 |
| Excluded: midpoint outside AOI v2 + 5 km | 3,517 |
| Excluded: clipped length <2 km | 468 |
| Kept ways | **860** |
| Total kept length | **14,096.7 km** |
| Order-1 Brahmaputra ways | 11 |
| Pruned shortest ways for the 4.0 % gate | **0** |
| Channel cells inside AOI v2 (stage 06 rasterisation) | 184,988 = **2.86 %** |
| Channel cells inside AOI v2 (stage 07, 45 m-simplified lines) | 181,114 = **2.80 %** |
| Display layer | 973,417 B (951 KB), 860 features, 50 m simplification |
| Channel layer | 958,087 B (936 KB) |

The small stage-06/stage-07 cell difference (184,988 vs 181,114) is the 45 m
channel-line simplification used for burn rasterisation. Both are under the
4.0 % gate; V-A2 reads the stage-07 mask, which is the model input.

Stage 06 wall time was 14.2 s; stage 07 was 16.4 s.

## Stage 07 — burn

| Item | Measured value |
|---|---:|
| Channel cells (all, including clip buffer) | 206,235 |
| Channel cells inside AOI v2 | 181,114 |
| Mean centre-cell lowering | 4.33 m |
| Max lowering | 6.00 m |
| Capped cells | 103,280 |
| Burned DEM | 103.9 MB |

Only the 11 order-1 Brahmaputra ways receive 2-cell dilation; every other river
is one cell. The 1–6 m mean-lowering check passes at 4.33 m. The cap is the
phase-A guard, now applied to the narrower river-only set.

## Stage 08 — HAND

| Item | Measured value |
|---|---:|
| Valid HAND cells inside AOI v2 | 6,454,354 |
| Valid AOI v2 share | **99.85 %** |
| Clamped negative cells inside AOI v2 | 343,165 = **5.32 %** (V-A6 fails) |
| Clamped negative cells globally | 504,455 = 4.48 % |
| HAND p10 / p50 / p90 / p95 inside AOI v2 | **0.80 / 5.74 / 14.75 / 23.03 m** |
| HAND p50 globally | 8.85 m |
| Stage 08 wall time | 17.7 s |

The AOI v2 HAND percentiles are close to the review’s p10 0.69 / p50 5.59 /
p90 13.86 m. The clamped share is not: the review expected the river-only
policy to bring 5.29 % below 3.0 %, and the measured value is **5.32 %** of
AOI v2 (4.48 % if the global valid-cell denominator is used). Neither
denominator passes V-A6.

## Stage 09 — computed sequence and the three failures

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
  --out-masks pipeline/work/inundation-masks `
  --out-frames-dir pipeline/work/flood-frames
```

The stage built 12 per-step uint8 wet masks and 12 per-step frame files, then
failed at the combined-frame cap. Observed wall time was **221.2 s** (3.7 min),
measured with a stopwatch around the exact command; it did not write a
provenance fragment because it failed before `StageRecord.finish`. The wall
time alone would pass V-A8’s 10-minute limit, but V-A8 cannot be evaluated from
a missing fragment.

### Full S00–S11 sequence (measured from the per-step masks)

| Step | Label | Stage (m) | Wet area (km²) | % AOI v2 | % Assam | % flood-prone | Median depth (m) | Max depth (m) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| S00 | 01 Jun | 0.20 | 1,821.8 | 3.5 % | 2.3 % | 5.9 % | 0.20 | 0.20 |
| S01 | 15 Jun | 0.40 | 1,857.0 | 3.6 % | 2.4 % | 6.0 % | 0.40 | 0.40 |
| S02 | 01 Jul | 0.70 | 1,959.7 | 3.8 % | 2.5 % | 6.3 % | 0.70 | 0.70 |
| S03 | 15 Jul | 1.05 | 2,153.6 | 4.1 % | 2.8 % | 6.9 % | 1.05 | 1.05 |
| S04 | 25 Jul | 1.45 | 2,416.7 | 4.6 % | 3.1 % | 7.8 % | 1.45 | 1.45 |
| S05 | 05 Aug | 1.80 | 2,774.1 | 5.3 % | 3.5 % | 8.9 % | 1.80 | 1.80 |
| S06 | 15 Aug | 2.20 | 3,447.5 | 6.6 % | 4.4 % | 11.1 % | 2.20 | 2.20 |
| **S07** | **25 Aug** | **2.50** | **4,007.5** | **7.7 %** | **5.1 %** | **12.9 %** | **2.50** | **2.50** |
| S08 | 05 Sep | 2.20 | 3,447.5 | 6.6 % | 4.4 % | 11.1 % | 2.20 | 2.20 |
| S09 | 15 Sep | 1.70 | 2,685.9 | 5.1 % | 3.4 % | 8.7 % | 1.70 | 1.70 |
| S10 | 30 Sep | 1.20 | 2,221.4 | 4.3 % | 2.8 % | 7.2 % | 1.20 | 1.20 |
| S11 | 15 Oct | 0.70 | 1,959.7 | 3.8 % | 2.5 % | 6.3 % | 0.70 | 0.70 |

Peak: **4,007.5 km² = 7.7 % of AOI v2, 5.1 % of Assam, 12.9 % of the
31,050 km² flood-prone area.** The rising limb is strictly non-decreasing, the
recession strictly non-increasing, and the peak is at S07, so V-A7 passes and
V-A4 passes by a 7.5 km² margin above its 4,000 km² floor.

### V-A5 — peak depth fails

The peak-step median depth over wet cells is **2.50 m**, expected ≤1.5 m; the
max is 2.50 m, expected ≤2.60 m (that half passes). This is not a summary bug:
the depth is computed exactly as `stage - HAND`. The cause is visible in the
HAND distribution conditional on being wet. At stage 2.50 m the raw
`HAND ≤ 2.50` band inside AOI v2 is 8,861.0 km², with median raw HAND 0.18 m;
37.1 % of that raw band has **negative** raw HAND (it is clamped to 0 by the
HAND step). The connected wet mask keeps 4,007.5 km², and more than half of
those cells have HAND near 0, so their depth is near the full stage.

The review’s 9,016 km² estimate at 2.5 m was computed from the **old,
all-waterway HAND** (phase A, 1,068,977 channel cells). This run has 206,235
channel cells (river-only) and a different nearest-drainage set; its raw
`HAND ≤ 2.5` area is 8,861.0 km², and the connectivity filter reduces it to
4,007.5 km². The V-A5 median expectation does not hold for this conditional
HAND distribution.

### V-A6 — clamped HAND fails

Clamped negatives are **343,165 cells = 5.32 %** of AOI v2 valid cells
(4.48 % globally), expected ≤3.0 %. The river-only policy did **not** reduce
clamping. It removed the small streams that previously supplied a nearby,
lower nearest-drainage elevation, so many valley cells now select a larger
river whose bed is higher than the local ground. 37.1 % of the raw
`HAND ≤ 2.50` band at the peak is in this state. Narrowing the channel mask
from 1,068,977 to 206,235 cells therefore made V-A6 harder, not easier.

### V09 — flood-frame cap fails

The combined `flood-frames.geojson` is **25,885,838 bytes** against the
**6,815,744-byte** cap (3.8×). It contains only 27 features (one per non-empty
depth band per step) but **10,820 polygon parts at the peak step**; at 5-decimal
coordinates and 75 m simplification the peak step alone is 3,289,475 bytes.
This is fragmented river-following geometry, not duplicated data.

Measured probes on the peak step (not committed):

| Generalisation | Peak-step bytes | Result |
|---|---:|---|
| 75 m, parts ≥0.02 km² (spec) | 3,289,475 | 25.9 MB over 12 steps |
| 75 m, parts ≥0.20 km² | 2,124,990 | still ~20 MB over 12 steps |
| ~167 m (0.0015°), parts ≥0.02 km² | ~1.83 MB | still over the 6.5 MB cap |
| ~334 m (0.003°), parts ≥0.02 km² | ~1.44 MB | still over the 6.5 MB cap |

Fitting 6.5 MB would require generalising well beyond 75 m, dropping genuine
parts, or changing the frame contract. None was done, because the brief forbids
pruning data until the number looks nice.

## A4 gate status from this run

| Gate | Rule | Observed | Status |
|---|---|---|---|
| V-A1 | AOI v2 45,000–56,000 km² | 52,240.7 km² | pass |
| V-A2 | channel cells ≤4.0 %; 0 midpoints outside AOI v2 + 5 km | 2.80 %; 0; all `river` | pass |
| V-A3 | strict rise/fall; peak 2.50 m | 0.20→2.50→0.70; peak S07 | pass |
| V-A4 | peak 4,000–12,000 km²; ≤40 % flood-prone | 4,007.5 km²; 12.9 % | pass (7.5 km² margin) |
| V-A5 | peak median ≤1.5 m; max ≤2.60 m | **2.50 m**; 2.50 m | **fail** |
| V-A6 | clamped AOI v2 ≤3.0 % | **5.32 %** (4.48 % global) | **fail** |
| V-A7 | rising non-decreasing; recession non-increasing; peak S07 | exact; peak S07 | pass |
| V-A8 | wall ≤10 min; no artifact >300 MB | 221.2 s; masks 2.97 MB; no `.npz` | pass on observation, no fragment |
| V09 | `flood-frames.geojson` ≤6.5 MB | **25,885,838 B** | **fail** |

## Deviations from the written specification

1. **AOI v2 edge buffer.** The 2 km buffer is 61,655.7 km², above V-A1’s
   56,000 km² ceiling. V-A1 and all flood metrics use the core mask
   (52,240.7 km²); the buffer is continuity only. This is stated in
   `aoi-v2.json`, the docs and this report, not silently counted.
2. **Channel cell counts differ by 3,874 between stage 06 and stage 07.**
   Stage 06 rasterises the unsimplified clipped lines; stage 07 rasterises the
   45 m-simplified channel layer. Both are under 4.0 %; V-A2 reads the stage-07
   mask.
3. **Flood polygonisation.** Inherited from phase A: band parts are projected
   to WGS84 and simplified part-by-part at a 75 m latitude-equivalent tolerance
   rather than unioning one huge MultiPolygon in EPSG:32646. Areas and band
   membership are computed on the raster.
4. **Per-step frames are staging.** Stage 09 writes
   `pipeline/work/flood-frames/step-XX.geojson`, combines them into the one
   committed `flood-frames.geojson`, and removes the staging files. The app’s
   load contract remains one file; `ARCHITECTURE.md` §6.7 now says so.
5. **No `inundation-stack.npz`.** Stage 09 writes uint8 per-step wet masks
   (`pipeline/work/inundation-masks/`, 2.97 MB) instead. Stages 10/12 read those
   masks and reconstruct depth from `stage - HAND`. The old 2.34 GB `.npz` was
   deleted from the working tree.
6. **Flood-prone source.** The 31,050 km² figure is a published
   flood-prone-area statistic, not an event extent; `sources.json` records the
   URL, retrieval date and caveat, and `publish` emits it as a `reference`
   entry.
7. **P1 layers.** Stages 12–13 were not reached because stage 09 is blocked.
8. **Python/editable install.** Python 3.11.16 with `PYTHONPATH=pipeline/src`;
   the editable install is still blocked by the sandbox ACL.

## What is reproducible now

- Stage 06 reproduces AOI v2 52,240.7 km², 860 rivers, 14,096.7 km, 0 pruned,
  2.86 % channel share, 951 KB display.
- Stage 07 reproduces 206,235 channel cells, 4.33 m mean lowering, 103,280
  capped cells.
- Stage 08 reproduces 99.85 % valid AOI v2 HAND, 5.32 % clamped, p50 5.74 m.
- Stage 09 reproduces the full S00–S11 table, peak 4,007.5 km², and the same
  frame-cap failure in 221 s.
- The exact commands are in `pipeline/README.md`; the gate logic is in
  `pipeline/src/baanh_pipeline/validate.py` and was not run because publishing
  a partial data set would misstate the run.

## Recommendation

Do not publish this run. The reviewer must resolve the **policy conflict**
rather than lower a gate:

1. **V-A5/V-A6 versus A2.** River-only channels leave too many valley cells
   below their nearest mapped river (37.1 % of the raw peak band) and
   concentrate the retained wet cells at HAND ≈0. Either the model needs a
   documented drainage/burn policy that supplies a lower nearest elevation
   (e.g. a routed or depression-aware HAND, or a reviewed burn rule), or the
   A4 depth/clamp thresholds need a new evidence basis. Widening V-A5 or V-A6
   in place would not fix the underlying geometry.
2. **Frame contract versus geometry.** The 6.5 MB cap is incompatible with
   10,820 river-following parts at 5-decimal/75 m. A reviewer decision is
   needed on: a larger animation budget, a different frame format/contract, or
   an explicit, recorded generalisation policy (tolerance and minimum part
   area) that is applied before the cap and reported — not a quiet prune.
3. **V-A4 margin.** Peak 4,007.5 km² passes by 7.5 km². Any change to the
   channel or burn policy will move it; keep the gate and re-measure rather than
   tuning the peak.

The failing command and the observed/expected values are recorded above. No
further stage was run because doing so would either hand-author flood data or
publish a data set that fails its own gates.
