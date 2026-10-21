# Baanh M0 phase A3 — pipeline report

**Status: BLOCKED at stage 09 (`build-inundation`).** B1–B4 are applied to the scenario,
config, validator and docs, and the stage→area calibration was measured on the A2 channel
set. The measured curve does **not** reproduce the REVIEW-03 table, and no peak stage satisfies
V-A4 and V-A5 together. At the B1 peak of 3.70 m stage 09 passes V-A4, V-A6, V-A7 and V-A8 but
fails **V-A5** (median 2.485 m vs 1.00–2.2 m), and the combined frames fail **V09** (21,017,334 B
raw / 5,346,071 B gzip vs 6,815,744 B / 1,572,864 B). No gate was widened, no committed JSON was
hand-edited, and no flood/risk/series layer was committed. Stages 10–15 were not run because
stage 09 has no accepted output.

- Run date: 2026-10-21 (local), Windows 11, Python 3.11.16 (64-bit).
- Repository: `C:\Users\oliad\Desktop\baanh`.
- Interpreter invocation: `$env:PYTHONPATH='pipeline/src'; python -m baanh_pipeline.cli <stage>`.
  The editable install remains blocked by the sandbox ACL; this is the same workaround as
  phases A and A2.
- Working tree: B1–B4 in `pipeline/config/`, `pipeline/src/baanh_pipeline/` and the superseded
  doc sections; the committed `admin/`, `hydro/` and `basemap/` outputs are unchanged.
- `pipeline/cache/`, `pipeline/work/` and the failed stage-09 staging files are gitignored.

## What B1–B4 changed

| Amendment | Applied as |
|---|---|
| **B1** stage scale | `scenario.json` is the ×1.48 table: S00 0.30 … S07 **3.70** … S11 1.05 m; threshold 2.0 m; main-stem/backwater rescaled with the 2-decimal reconciliation so `stage = mainstem + backwater` holds. |
| **B2** depth formula | `depth = stage − max(HAND, 0)` in stage 09 and stage 11; the conservative-shallow bias is stated in `scenario.json`, `DATA-PIPELINE.md` §7.6 and this report. |
| **B3** gates | V-A5 is now median 1.0–2.2 m, p95 ≤ peak stage, clamped wet share ≤30 %; V-A6 is ≤6.0 % of AOI v2; V09 adds a 1,572,864-byte gzip cap; **V-A9** is new (3×3 opening + <0.10 km² part drop before polygonisation, both counts recorded). |
| **B4** frame budget | V09 first, gzip included; the two-class (0–1 m / ≥1 m) rendering is documented in `ARCHITECTURE.md` §7.2 and `DATA-PIPELINE.md` §11.1 as the **only** recorded fallback. It was not used: it cannot close a 3.1× raw gap, and no polygons were dropped. |

`REVIEW-02` A1, A2 and A5 remain in force. Its A3/A4 are marked superseded; the current values
live in `scenario.json`, `pipeline.json` and `REVIEW-03`.

## Measured calibration curve (A2 channel set)

Reference rasters (unchanged from the A2 commit): `dem-90m.tif`, `dem-burned.tif`,
`channels-90m.tif`, `nearest-channel-elevation-90m.tif`, AOI v2 core mask. Procedure: AOI v2 /
valid HAND → 8-connected connectivity (component touches a channel or one cell from it, ≥3 cells)
→ **V-A9** 3×3 binary opening → drop wet parts <0.10 km² → depth `stage − max(HAND, 0)` → 75 m
simplified, four-band polygonisation, 0.02 km² ring floor. The frame columns are one peak-step
FeatureCollection, exactly as measured by the stage-09 code path.

| Stage m | Area km² | % Assam | % flood-prone | Clamped wet | Median depth m | p95 depth m | Frame parts | Frame raw B | Frame gzip B |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.50 | 2,255 | 2.9 % | 7.3 % | 49.8 % | 2.50 | 2.50 | 7,314 | 1,439,787 | 369,926 |
| 2.80 | 2,936 | 3.8 % | 9.5 % | 45.4 % | 2.80 | 2.80 | 9,806 | 1,890,083 | 484,104 |
| 3.10 | 3,973 | 5.1 % | 12.8 % | 38.6 % | 2.69 | 3.10 | 21,840 | 3,576,237 | 903,453 |
| 3.40 | 5,248 | 6.7 % | 16.9 % | 33.4 % | 2.55 | 3.40 | 29,506 | 4,799,209 | 1,213,587 |
| **3.70** | **6,924** | **8.9 %** | **22.3 %** | **29.3 %** | **2.49** | **3.70** | **40,353** | **6,485,848** | **1,635,055** |
| 4.00 | 8,779 | 11.2 % | 28.3 % | 24.6 % | 2.37 | 4.00 | 53,938 | 8,561,376 | 2,158,066 |
| 4.30 | 10,649 | 13.6 % | 34.3 % | 21.2 % | 2.31 | 4.30 | 67,738 | 10,653,500 | 2,680,108 |

Clamped AOI share is 5.318 % at every stage: it is a property of the HAND raster, not of the
stage. The AOI v2 core is 52,240.748 km², Assam 78,220.613 km², flood-prone reference
31,050 km².

### Chosen peak and why the run stops

B1's 3.70 m is applied. **It is inside V-A4** (6,924 km², 22.3 % of flood-prone) **but outside
V-A5** (median 2.485 m > 2.2 m). The table shows why another stage does not rescue it:

- Every stage with area ≥4,000 km² (3.10 m and above) has median ≥2.31 m. The minimum in the
  V-A4 band is **2.314 m at 4.30 m** — still 0.114 m above the V-A5 ceiling — and at 4.30 m the
  frame is already 10.65 MB raw.
- Every stage with median ≤2.2 m (2.50 m and below) has area ≤2,255 km², far below the V-A4 floor.
- The median is high because 29.3 % of the wet area is clamped at HAND 0 and therefore at the
  full 3.70 m depth; the retained shallow fringe is not large enough to pull the median down.
  This is the bathtub behaviour B2 declares, not a summary bug.

So there is **no peak stage inside V-A4 and V-A5** on this channel set with the specified V-A9
speckle control. Stopping here follows the brief's instruction: report observed vs expected
rather than widen a gate or hand-fit a stage.

### The measured curve does not reproduce REVIEW-03's table

| At 3.70 m | REVIEW-03 | Measured | Difference |
|---|---:|---:|---:|
| Area km² | 6,568 | 6,924 | +356 (+5.4 %) |
| Clamped share of wet | 24.2 % | 29.3 % | +5.1 pp |
| Median depth m | 1.81 | 2.485 | +0.675 |
| p95 depth m | 3.70 | 3.70 | 0 |
| Polygon parts | 2,184 | 40,353 frame parts (3,477 wet components) | 18.5× / 1.6× |

At 4.00 m the divergence is larger: measured 8,779 km² and median 2.365 m versus 10,011 km² and
1.70 m; measured 53,938 frame parts versus 3,806.

The pattern is diagnostic. The review's median (1.81 m) is almost exactly the median of the
**raw, unconnected `HAND ≤ 3.70` band** (1.865 m over 14,221 km²), while its area (6,568 km²) is
close to the **post-opening** mask (6,924 km²), and its parts (2,184) are between our wet
components (3,477) and a band-polygon count. No single consistent mask — connectivity,
opening, or band-polygon stage — reproduces that row. The reviewer's table appears to mix
statistics from different stages of the filter, which is consistent with REVIEW-03's own
process note that the thresholds were the defect. We did not tune the implementation to match
the row.

## Stage 09 run

Command (exact):

```powershell
$env:PYTHONPATH='pipeline/src'
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

Observed wall time: **237.6 s** (3.96 min), stopwatch around the exact command. Exit code 1 at
the V-A5 check, after all 12 per-step frames were polygonised and written to
`pipeline/work/flood-frames/` and all 12 uint8 wet masks to
`pipeline/work/inundation-masks/` (1,419,350 B). The per-step staging files are retained for
audit; stage 09 stops before combining them or writing any `public/data/flood/` file, so no
failing dataset was published.

### Per-step sequence — geometry and depth

| Step | Label | Stage m | Area km² | % AOI v2 | % Assam | % flood-prone | Median m | p95 m | Clamped wet | Wet parts before→after | Frame parts | Frame raw B | Frame gzip B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S00 | 01 Jun | 0.30 | 475.7 | 0.9 % | 0.6 % | 1.5 % | 0.30 | 0.30 | 60.9 % | 364→305 | 360 | 162,653 | 43,776 |
| S01 | 15 Jun | 0.60 | 529.3 | 1.0 % | 0.7 % | 1.7 % | 0.60 | 0.60 | 62.6 % | 363→357 | 514 | 200,796 | 54,075 |
| S02 | 01 Jul | 1.05 | 723.8 | 1.4 % | 0.9 % | 2.3 % | 1.05 | 1.05 | 65.9 % | 358→462 | 740 | 270,781 | 72,605 |
| S03 | 15 Jul | 1.55 | 977.1 | 1.9 % | 1.2 % | 3.1 % | 1.55 | 1.55 | 63.0 % | 358→604 | 2,728 | 573,954 | 149,239 |
| S04 | 25 Jul | 2.15 | 1,657.0 | 3.2 % | 2.1 % | 5.3 % | 2.15 | 2.15 | 54.3 % | 354→918 | 5,519 | 1,078,860 | 277,391 |
| S05 | 05 Aug | 2.65 | 2,476.4 | 4.7 % | 3.2 % | 8.0 % | 2.65 | 2.65 | 47.4 % | 345→1,285 | 8,259 | 1,599,783 | 409,622 |
| S06 | 15 Aug | 3.25 | 4,535.2 | 8.7 % | 5.8 % | 14.6 % | 2.59 | 3.25 | 35.5 % | 350→2,070 | 25,066 | 4,085,145 | 1,033,031 |
| **S07** | **25 Aug** | **3.70** | **6,924.0** | **13.3 %** | **8.9 %** | **22.3 %** | **2.49** | **3.70** | **29.3 %** | **326→3,477** | **40,353** | **6,485,848** | **1,635,055** |
| S08 | 05 Sep | 3.25 | 4,535.2 | 8.7 % | 5.8 % | 14.6 % | 2.59 | 3.25 | 35.5 % | 350→2,070 | 25,066 | 4,085,153 | 1,033,025 |
| S09 | 15 Sep | 2.50 | 2,255.2 | 4.3 % | 2.9 % | 7.3 % | 2.50 | 2.50 | 49.8 % | 346→1,162 | 7,314 | 1,439,799 | 369,925 |
| S10 | 30 Sep | 1.80 | 1,228.5 | 2.4 % | 1.6 % | 4.0 % | 1.80 | 1.80 | 60.0 % | 359→722 | 3,776 | 765,623 | 197,210 |
| S11 | 15 Oct | 1.05 | 723.8 | 1.4 % | 0.9 % | 2.3 % | 1.05 | 1.05 | 65.9 % | 358→462 | 740 | 270,787 | 72,606 |
| **combined** | — | — | — | — | — | — | — | — | — | — | **34 features** | **21,017,334** | **5,346,071** |

The combined raw/gzip sizes are measured on the exact `FeatureCollection` the stage would
write, built from the 12 staging files; the sum of per-step raw sizes is 21,019,182 B, so the
combined envelope is 1,848 B smaller. The animation tier is already over budget from the frames
alone; adding `flood-summary.json` and `risk-zones.geojson` would only increase it.

**V09:** the peak frame alone passes the raw cap (6,485,848 ≤ 6,815,744) but fails the gzip cap
(1,635,055 > 1,572,864, +62,191 B). The combined file fails both caps by 3.08× raw and 3.40×
gzip. The two-class fallback would reduce band features at best, not the 3.1× raw gap, so it
was not applied.

## Gate status from this run

| Gate | Rule (REVIEW-03 B3) | Observed | Status |
|---|---|---|---|
| V-A1 | AOI v2 45,000–56,000 km² | 52,240.7 km² | pass |
| V-A2 | channel cells ≤4.0 %; midpoints inside AOI v2 + 5 km | 2.80 %; 0 outside | pass |
| V-A3 | strict rise S00→S07, fall S08→S11, peak 3.70 m, threshold 2.0 m | 0.30→3.70→1.05; peak S07 | pass |
| V-A4 | peak 4,000–12,000 km²; ≤40 % flood-prone | 6,924.0 km²; 22.3 % | pass |
| V-A5 | peak median 1.0–2.2 m; p95 ≤ stage; clamped wet ≤30 % | median **2.485 m**; p95 3.70 m; clamped wet 29.3 % | **fail** |
| V-A6 | clamped AOI ≤6.0 % | 5.318 % | pass |
| V-A7 | rising non-decreasing; recession non-increasing; peak S07 | 475.7→6,924.0→723.8; peak S07 | pass |
| V-A8 | stage 09 ≤10 min; no artifact >300 MB | 237.6 s; masks 1.35 MB; no `.npz` | pass |
| V-A9 | 3×3 opening + <0.10 km² part drop before polygonisation; both counts recorded | applied; peak 326→3,477 wet parts, 40,353 frame parts | applied (validator comparison not reached) |
| V09 | frames ≤6,815,744 B raw and ≤1,572,864 B gzip | combined 21,017,334 B / 5,346,071 B | **fail** |

The first hard failure is V-A5. V-A9's evidence is recorded in
`pipeline/work/stage09-attempt.json`; the formal V-A9 check (committed feature part count equals
the summary) could not run because stage 09 stopped before combining.

## Per-stage wall times

| Stage | Command | Wall time | Output |
|---|---|---:|---|
| 09 | `build-inundation` | **237.6 s** | 12 masks + 12 staging frames; stopped before public write |
| 10 | `build-risk` | not run | blocked by 09 |
| 11 | `build-series` | not run | blocked by 09 |
| 12 | `build-assets` | not run | blocked by 09 |
| 14 | `validate` | not run | no complete `public/data/` |
| 15 | `publish` | not run | no passing report |

Stages 06–08 were not re-run: their committed outputs and `hand-meta.json` are the A2 set the
calibration refers to. Their recorded wall times remain 14.2 s (06), 16.4 s (07) and 17.7 s (08).

## Observed vs expected — the stop condition

| Gate | Expected | Observed | Gap |
|---|---:|---:|---:|
| V-A5 median at 3.70 m | 1.00–2.20 m | 2.485 m | **+0.285 m** |
| V-A5 median, best in V-A4 band | ≤2.20 m | 2.314 m at 4.30 m | **+0.114 m** |
| V09 combined raw | ≤6,815,744 B | 21,017,334 B | **3.08×** |
| V09 combined gzip | ≤1,572,864 B | 5,346,071 B | **3.40×** |
| V09 peak-frame gzip | ≤1,572,864 B | 1,635,055 B | **+62,191 B** |
| V-A9 peak frame parts (review expectation) | ~2,184 | 40,353 | **18.5×** |

V-A4, V-A6, V-A7 and V-A8 pass. The stop is not caused by a missing input, a crash, or a
widened gate: the measured data simply does not satisfy V-A5, and the frame tier does not
satisfy V09.

## Deviations and observations

1. **No peak passes V-A4 + V-A5.** This is the blocking finding. The calibration table is the
   evidence; 3.70 m is kept as the B1 value and the run stops rather than choosing a stage that
   fails the gate or quietly changing the gate.
2. **The REVIEW-03 table is not reproducible from the A2 rasters.** Its median/parts are close
   to the raw unconnected band and its area is close to the opened mask; no single mask matches
   the row. The builder did not tune the filter to reproduce the numbers.
3. **V-A9 opening fragments the mask at high stage.** At 3.70 m the connected wet mask has 326
   components; after the 3×3 opening and 0.10 km² drop it has 3,477, and the four-band split
   yields 40,353 frame polygons. The opening removes thin connections and creates more, smaller
   parts, the opposite of the REVIEW-03 "10,820 → 2,184" claim. This is why the frame budget
   did not improve.
4. **Per-step frames are staging, not committed.** Stage 09 writes
   `pipeline/work/flood-frames/step-XX.geojson`, then combines them. The V-A5 check runs before
   the combine, so the failed run leaves only staging files and no `public/data/flood/` file.
   That is intentional: a failing frame set is never published.
5. **Depth bias.** `depth = stage − max(HAND, 0)` is conservative-shallow; a below-datum cell
   reports the full stage. At 3.70 m, 29.3 % of the wet area is in this state. The UI methodology
   note and `scenario.json` state the bias; it is not a measured depth.
6. **Stage 11 cross-sections** now use the same B2 depth (`stage − max(HAND, 0)`) rather than
   `surface − ground` on the raw HAND, so a below-datum sample cannot report a depth above the
   stage. Stage 11 was not run.
7. **Stage 12/13 optional layers** (facilities, gauges) were not run. No hand-built substitute
   was created.
8. **No application code, UI or Playwright was touched.** Only the pipeline, config, schemas,
   validator and docs changed.

## Reproducing the measurement

```powershell
$env:PYTHONPATH=(Resolve-Path pipeline\src).Path
python pipeline\work\_calibrate_stages.py 2.5 2.8 3.1 3.4 3.7 4.0 4.3
python pipeline\work\_combine_size.py
python -m baanh_pipeline.cli build-inundation <flags above>
```

The probe is read-only except for `pipeline/work/calibration-curve.json`,
`pipeline/work/calibration-variants.json` and `pipeline/work/stage09-attempt.json`; all are
gitignored. The stage-09 command is exactly the one in the previous section.

## Recommendation

The reviewer must resolve the calibration contract, not the builder lower a gate:

1. **Define the V-A5 statistic on one mask.** State whether median/p95/clamped share are
   computed on the raw `HAND ≤ stage` band, the connected mask, the opened mask, or the
   committed polygons. The current table mixes regimes; a reproducible script and the chosen
   mask should be part of the amendment. On the mask the stage actually commits, the 3.70 m
   median is 2.485 m and no V-A4 stage reaches 2.2 m.
2. **Reconcile V-A5 with V-A9.** A 3×3 opening plus a 0.10 km² part floor cannot both remove
   speckle and keep the shallow fringe that lowers the median; on this grid it fragments the
   wet mask. Either the depth gate needs a new evidence basis or the speckle policy needs a
   specification that states what is removed and what is retained.
3. **Resolve the frame contract.** V09 fails by 3.1× raw / 3.4× gzip before any two-class
   change. A two-class rendering is a feature-count reduction, not a 3× geometry reduction; the
   frame format, per-step file split, or budget needs an explicit reviewer decision. Dropping
   real polygons to fit is still forbidden.
4. **Keep V-A4 as measured.** The 3.70 m peak is 6,924 km² = 22.3 % of the flood-prone reference,
   comfortably inside the band; the blocker is depth and transfer size, not extent.

No data was committed at a failing gate. The committed tree remains at the last green state:
`admin/assam-state.geojson`, `hydro/assam-rivers.geojson` and
`basemap/assam-hillshade.webp` only.
