# Baanh phase A5 — mask reconciled, V-A5 v4 shape gate, depth deciles and the published data set

**Status: PASS.** Phase A5 closes the mask question and the A4 block. Stages 09 → 10 → 11 → 12 →
13 → 14 → 15 are green; `public/data/validation-report.json` is `status: pass` with 31 checks,
0 failures and 0 warnings. No gate was widened, no committed JSON was hand-edited, and no
application code was touched.

- Run date: 2026-10-21 (local), Windows 11, Python 3.11.16 (64-bit).
- Repository: `C:\Users\oliad\Desktop\baanh`.
- Dataset version: `2026.10.0`.
- Interpreter: `$env:PYTHONPATH=(Resolve-Path pipeline\src).Path; python -m baanh_pipeline.cli …`.
- Commits: `d737542` (stage 09 green: D1/D2 + flood data), `3541508` (stages 10–13 green), and the
  A5 close-out commit containing this report, the docs amendments, the V13 self-reference fix and
  the validated/published `public/data/` tree.

## 1. What A5 changed

| Amendment | Applied as |
|---|---|
| **D1 — V-A5 v4** | `pipeline/config/pipeline.json` replaces the withdrawn 1.0–2.2 m absolute band with four shape rules: median ≥ 0.7 m, median ≤ peak stage − 0.5 m, p95 ≤ peak stage, p95 − median ≥ 0.6 m; clamped wet ≤ 30 %. Stage 09 and stage 14 now evaluate the same four rules on the area-filtered mask. At A5: median **2.354 m** ≤ **3.20 m**, p95 **3.700 m** = stage, spread **1.346 m** ≥ 0.6 m, clamp **21.0 %**. |
| **D2 — depth deciles** | Every `flood-summary.json` step now carries `wet_cells` and `delay_deciles` (`p10,p25,p50,p75,p90,p95`) over its wet cells. Stage 09 prints the same table; stage 14 checks the six values are ordered, non-negative, and that `p50`/`p95` equal the step median/p95. No consumer averages them. |
| **D3 — mask appendix** | §5 below names the HAND raster and its writing stage, the channel raster and the connectivity predicate in words and code, the order of AOI/connectivity/area filter, and the three areas at 3.70 m: **14,221.08 → 10,016.06 → 10,010.64 km²**. |
| **D4 — re-run scope** | 09 → 10 → 11 → 12 → 14 → 15 re-run; stage 13 re-run as well because the `public/data/` definition of done includes gauges. Committed at each green group. |

## 2. Stage 09 run (final mask)

Command (exact):

```powershell
$env:PYTHONPATH=(Resolve-Path pipeline\src).Path
python -m baanh_pipeline.cli build-inundation `
  --dem pipeline/work/dem-burned.tif `
  --hand pipeline/work/hand-90m.tif `
  --distance pipeline/work/channel-distance-90m.tif `
  --channels pipeline/work/channels-90m.tif `
  --state public/data/admin/assam-state.geojson `
  --scenario pipeline/config/scenario.json `
  --frame-index public/data/flood/frame-index.json `
  --out-summary public/data/flood/flood-summary.json `
  --out-masks pipeline/work/inundation-masks `
  --out-frames-dir public/data/flood/frames
```

Observed wall time **29.9 s** (stage-09 provenance fragment; V-A8 cap 600 s). Frame size
**3733 × 2611** px at ½ resolution (≈180 m/px), bbox
`[89.424203, 23.911344, 96.265512, 28.193794]`.

### 2.1 Per-frame PNG bytes, area and depth statistics

All areas are geodesic row-cell sums on the 90 m analysis grid. `Δ area` compares the committed
PNG wet-cell area with the summary area using the same mean cell area; V-A10 independently
recomputes the PNG area with a planar 180 m cell (0.0324 km²), which gives a maximum delta of
**0.535 %** — still under its 1 % gate.

| Step | Label | Stage m | Area km² | Wet cells | Median m | p95 m | Clamp wet | Components before→after | Dropped km² | PNG B | PNG wet cells | PNG area km² | Δ area |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S00 | 01 Jun | 0.30 | 1,833.9 | 226,918 | 0.300 | 0.300 | 19.6 % | 535→248 | 6.4574 | 67,354 | 56,905 | 1,839.59 | 0.31 % |
| S01 | 15 Jun | 0.60 | 1,904.1 | 235,598 | 0.600 | 0.600 | 21.1 % | 533→249 | 6.3442 | 70,185 | 59,082 | 1,909.96 | 0.31 % |
| S02 | 01 Jul | 1.05 | 2,149.1 | 265,919 | 1.050 | 1.050 | 25.9 % | 530→246 | 6.3442 | 75,947 | 66,581 | 2,152.39 | 0.15 % |
| S03 | 15 Jul | 1.55 | 2,464.7 | 304,964 | 1.550 | 1.550 | 28.2 % | 529→245 | 6.4816 | 87,225 | 76,437 | 2,471.01 | 0.26 % |
| S04 | 25 Jul | 2.15 | 3,284.9 | 406,457 | 2.150 | 2.150 | 29.8 % | 523→245 | 6.2715 | 106,091 | 101,786 | 3,290.47 | 0.17 % |
| S05 | 05 Aug | 2.65 | 4,275.1 | 528,982 | 2.650 | 2.650 | 29.2 % | 516→240 | 6.1503 | 128,137 | 132,419 | 4,280.75 | 0.13 % |
| S06 | 15 Aug | 3.25 | 6,857.4 | 848,498 | 2.842 | 3.250 | 24.6 % | 499→238 | 6.0452 | 193,215 | 212,146 | 6,858.12 | 0.01 % |
| **S07** | **25 Aug** | **3.70** | **10,010.6** | **1,238,659** | **2.354** | **3.700** | **21.0 %** | **454→222** | **5.4229** | **254,791** | **309,751** | **10,013.43** | **0.03 %** |
| S08 | 05 Sep | 3.25 | 6,857.4 | 848,498 | 2.842 | 3.250 | 24.6 % | 499→238 | 6.0452 | 193,215 | 212,146 | 6,858.12 | 0.01 % |
| S09 | 15 Sep | 2.50 | 4,003.1 | 495,319 | 2.500 | 2.500 | 30.0 % | 517→240 | 6.2634 | 121,703 | 123,971 | 4,007.65 | 0.11 % |
| S10 | 30 Sep | 1.80 | 2,769.5 | 342,684 | 1.800 | 1.800 | 29.5 % | 527→246 | 6.4089 | 95,340 | 85,860 | 2,775.63 | 0.22 % |
| S11 | 15 Oct | 1.05 | 2,149.1 | 265,919 | 1.050 | 1.050 | 25.9 % | 530→246 | 6.3442 | 75,947 | 66,581 | 2,152.39 | 0.15 % |
| **total** | — | — | — | — | — | — | — | — | **74.579** | **1,469,150** | — | — | max **0.31 %** |

- **V09:** max PNG **254,791 B** ≤ 409,600 B; 12-frame animation **1,469,150 B (1.40 MB)** ≤ 4.0 MB.
- **V-A9:** opening `none`; peak 454 → 222 components, 232 dropped, 5.4229 km² dropped; total
  74.579 km² over 12 steps. Re-derived from the committed masks by stage 14.
- **V-A10:** 12 frames checked; max area delta 0.535 % (planar convention), max bbox delta
  0.495 px.
- The 5-class palette, half-resolution contract and frame-index are unchanged from REVIEW-04 C1.

### 2.2 Depth deciles (REVIEW-05 D2)

`delay_deciles` are the 10/25/50/75/90/95th percentile of depth over wet cells. `p50` equals
`median_depth_m` and `p95` equals `p95_depth_m` at every step. The p75–p95 pile-up is the
bathtub-bound signature D1's spread rule is designed to expose; the peak p10–p25 tail is the
shallow fringe.

| Step | Wet cells | p10 | p25 | p50 | p75 | p90 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| S00 | 226,918 | 0.3000 | 0.3000 | 0.3000 | 0.3000 | 0.3000 | 0.3000 |
| S01 | 235,598 | 0.6000 | 0.6000 | 0.6000 | 0.6000 | 0.6000 | 0.6000 |
| S02 | 265,919 | 1.0500 | 1.0500 | 1.0500 | 1.0500 | 1.0500 | 1.0500 |
| S03 | 304,964 | 1.2045 | 1.5500 | 1.5500 | 1.5500 | 1.5500 | 1.5500 |
| S04 | 406,457 | 0.7898 | 2.0717 | 2.1500 | 2.1500 | 2.1500 | 2.1500 |
| S05 | 528,982 | 0.6648 | 1.6921 | 2.6500 | 2.6500 | 2.6500 | 2.6500 |
| S06 | 848,498 | 0.2500 | 1.0586 | 2.8422 | 3.2500 | 3.2500 | 3.2500 |
| **S07** | **1,238,659** | **0.3809** | **0.8630** | **2.3540** | **3.7000** | **3.7000** | **3.7000** |
| S08 | 848,498 | 0.2500 | 1.0586 | 2.8422 | 3.2500 | 3.2500 | 3.2500 |
| S09 | 495,319 | 0.6984 | 1.7760 | 2.5000 | 2.5000 | 2.5000 | 2.5000 |
| S10 | 342,684 | 0.9716 | 1.8000 | 1.8000 | 1.8000 | 1.8000 | 1.8000 |
| S11 | 265,919 | 1.0500 | 1.0500 | 1.0500 | 1.0500 | 1.0500 | 1.0500 |

The table is also printed by stage 09 and stored under
`totals.delay_deciles_at_peak` for the peak. It is a distribution artifact, not a scalar to be
averaged.

## 3. Mask definition appendix (REVIEW-05 D3)

**Status: reconciled. The shipped code implements the documented predicate; no code fix was
needed. The reviewers' 6,302.5 km² and 8,129.6 km² reproduce exactly in component count when HAND
is computed from the unburned `dem-90m.tif` against the burned channel datum — a mixed surface,
not the committed HAND.**

### 3.1 The raster that supplies HAND

| Item | Value |
|---|---|
| HAND raster | `pipeline/work/hand-90m.tif` (`float32`, nodata −9999) |
| Written by | **stage 08 `compute-hand`** (`pipeline/src/baanh_pipeline/hand.py`) |
| Terrain input | `pipeline/work/dem-burned.tif`, written by **stage 07 `burn-rivers`** |
| Channel input | `pipeline/work/channels-90m.tif`, written by **stage 07** |
| Formula | `HAND = max(dem_burned − nearest_channel_elevation, 0)`; nodata where distance > 12,000 m |
| Stage 09 input | `--hand pipeline/work/hand-90m.tif` |

The nearest-channel elevation is sampled at the nearest channel cell of the **same burned DEM**
(`nearest-channel-elevation-90m.tif`, also written by stage 08). HAND and its channel datum
therefore describe one surface. The unburned `pipeline/work/dem-90m.tif` is not an input to HAND.

### 3.2 Channel raster and connectivity predicate

| Item | Value |
|---|---|
| Channel raster | `pipeline/work/channels-90m.tif` (uint8; `1` = burned channel cell) |
| Distance raster | `pipeline/work/channel-distance-90m.tif`, stage 08 Euclidean EDT with 90 m sampling |
| Predicate (words) | Label `wet_raw` with 8-connectivity. Retain a component if it contains **at least one cell whose distance to a channel is ≤ 90 m** — i.e. a channel cell itself or an orthogonal one-cell neighbour. |
| Predicate (code) | `near = wet_raw & (distance <= 90.0)`; `has_channel[np.unique(labels_raw[near])] = True`; `wet_connected = has_channel[labels_raw]` |
| Threshold source | `pipeline/config/scenario.json` → `model.connectivity.max_channel_distance_m = 90` |

The 90 m distance is one analysis cell. Diagonals are 127.3 m and are not included; the
predicate is exactly the documented "channel cell or within one cell".

### 3.3 Order of operations at each step

1. AOI mask: `domain = aoi-v2-core-90m.tif & (hand != nodata)`.
2. Raw threshold: `wet_raw = domain & (hand <= stage_m)`.
3. Connectivity: 8-connected components of `wet_raw`; retain a component if any of its cells is
   within 90 m of a channel (`_component_area_filter`, connectivity branch).
4. Area filter: re-label the retained mask with 8-connectivity; drop every component smaller than
   **9 cells** (≈0.073 km²) (`_component_area_filter`, area branch).
5. Statistics (`area_km2`, depth median/p95/deciles, clamp shares), wet mask write and half-res
   PNG rendering, all on the area-filtered mask.
6. **No polygonisation** of flood bands, no vector outline, no morphological opening. The frame
   is the raster contract of REVIEW-04 C1.

### 3.4 Three areas at stage 3.70 m

From `pipeline/work/stage09-attempt.json` and re-measured from the committed rasters:

| Stage of the mask | Cells | Area km² | Components |
|---|---:|---:|---:|
| Before connectivity (raw HAND threshold inside AOI v2) | 1,759,634 | **14,221.0767** | 37,164 |
| After connectivity (distance ≤ 90 m at component level) | — | **10,016.0640** | 454 |
| After ≥9-cell area filter (final committed mask) | 1,238,659 | **10,010.6411** | 222 |

The area filter removes 232 components and **5.4229 km²** at the peak. The 10,010.6 km² total is
therefore derived, not asserted: `14,221.08 − 4,205.01 (connectivity) − 5.42 (area filter) =
10,010.64 km²`.

### 3.5 Reconciliation with the reviewers' 6,302.5 and 8,129.6 km²

The reviewers' two numbers are not two predicates on the shipped mask. They are the same
component-level predicate at two distance thresholds applied to a **mixed HAND surface**:

```text
mixed_hand = dem-90m.tif − nearest-channel-elevation-90m.tif
```

`dem-90m.tif` is the unburned terrain; `nearest-channel-elevation-90m.tif` is the burned channel
datum. Mixing them raises HAND near burned channels and shrinks the mask. Re-running the shipped
predicate on that surface reproduces the reviewers' component counts exactly:

| Reconstruction | HAND surface | Predicate | Raw km² | After connectivity | After area filter | Components (connectivity→final) | Median | Clamp wet |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **Shipped pipeline** | `dem-burned − nearest_z` (`hand-90m.tif`) | distance ≤ 90 m | 14,221.08 | **10,016.06** | **10,010.64** | 454→222 | **2.354** | 21.0 % |
| Reviewer "contains a channel cell" (reproduced) | `dem-90m − nearest_z` | distance = 0 | 13,131.2 | 6,551.02 | **6,286.26** | **12,700→2,885** | **1.922** | 25.21 % |
| Reviewer "contains or within one cell" (reproduced) | `dem-90m − nearest_z` | distance ≤ 90 m | 13,131.2 | 8,461.19 | **8,099.06** | **18,439→4,248** | **1.910** | 24.94 % |

- The reproduced component counts are **identical** to the reviewers' table (12,700→2,885 and
  18,439→4,248); medians are 1.922 and 1.910 (reviewer 1.922/1.913); clamp is 25.21 %/24.94 %
  (reviewer 25.2 %/25.0 %).
- The reproduced areas are 6,286.26 and 8,099.06 km², **0.26 % / 0.38 % below** the reviewers'
  6,302.5 and 8,129.6 km². The residual is the cell-area convention: those totals are consistent
  with a planar ≈8,100 m² cell, while this pipeline uses geodesic per-row cell areas. The
  component counts and depth statistics do not depend on that convention and match.
- On the **shipped** HAND even the strictest predicate (component contains a channel cell,
  distance = 0) gives **10,010.07 km² / 219 components**, not 6,302.5 km². That rules out "the
  pipeline silently uses a looser predicate": the shipped 90 m predicate is the documented one,
  and the reviewers' mask is a different HAND surface.

**Conclusion.** The shipped code agrees with the spec's predicate:
`DATA-PIPELINE.md` §7.7 and `_component_area_filter` both retain a component that contains a
channel cell or a cell within `distance_m <= 90`. No predicate or gate was changed. The
undocumented factor was the HAND input: the reconstruction used `dem-90m.tif` (unburned) instead
of `dem-burned.tif` (the surface the channel datum was burned into). The pipeline's three areas
reconcile: 14,221.08 → 10,016.06 → 10,010.64 km².

## 4. Stages 10–13 — risk, series, assets, gauges

### 4.1 Stage 10 — risk zones, district ranking, hotspots

Command (exact):

```powershell
python -m baanh_pipeline.cli build-risk `
  --masks pipeline/work/inundation-masks `
  --hand pipeline/work/hand-90m.tif `
  --distance pipeline/work/channel-distance-90m.tif `
  --channels pipeline/work/channels-90m.tif `
  --districts pipeline/work/districts-base.geojson `
  --scenario pipeline/config/scenario.json `
  --out-zones public/data/risk/risk-zones.geojson `
  --out-ranking public/data/risk/district-risk.json `
  --out-districts public/data/admin/assam-districts.geojson `
  --out-hotspots public/data/risk/hotspots.geojson
```

Observed wall time **806.8 s**. The original per-component implementation (`unary_union` of ~75k
class polygons, then one `rasterize` per retained record) did not finish in 20+ minutes; it was
replaced with a label/ndimage join. No risk formula changed.

Outputs:

| File | Bytes | Content |
|---|---:|---|
| `data/risk/risk-zones.geojson` | **855,563** | 1,747 zones, 33 districts' worth of class areas |
| `data/risk/district-risk.json` | 15,398 | 33 ranked districts; top Sivasagar 71.944 (`very_high`) |
| `data/admin/assam-districts.geojson` | 170,859 | district polygons with joined risk fields |
| `data/risk/hotspots.geojson` | 9,023 | 20 low-HAND distant pockets |

**Fixed-cap generalisation (documented, not a widened gate).** The 0.9 MB raw cap cannot be met
by one polygon per 90 m component: the retained components alone are ~12k and produce multiple MB
at 100 m simplification (7.2 MB in the measured run; 8.3 MB with topology-preserving
simplification), and even at 600 m simplification they produce 2.91 MB while covering only
5,085 km².
Stage 10 therefore vectorises a block-majority grid and records the first grid factor in
`risk.zone.vector_block_factors` that fits the cap. A5 uses **1,080 m blocks (factor 12)** with a
**45 % wet-cell threshold** and the unchanged 100 m simplification / 0.05 km² floor. Zone
statistics (`risk_score`, HAND, duration, peak depth) are still computed from the 90 m cells under
each zone. Result: 1,747 zones, 855,563 B, total zone area **9,192.9 km² = 91.8 %** of the
10,010.6 km² peak. The residual is sub-block fringe below the 45 % wet threshold; district
ranking and hotspots use the full 90 m masks and are unaffected. The cap, the min-area floor and
the risk thresholds were not changed.

### 4.2 Stage 11 — series and cross-sections

**3.1 s.** 4 series × 12 points, 3 transects, 227 valid samples. `monsoon-series.json` 5,564 B;
`cross-sections.json` 58,222 B.

### 4.3 Stage 12 — critical-facility exposure (P1)

**50.3 s.** 1,183 OSM facilities with scenario exposure; `critical-facilities.geojson`
574,243 B. Completeness remains `incomplete-osm`; no capacity or operational status is inferred.

### 4.4 Stage 13 — virtual gauges (P1)

**0.1 s.** 8 synthetic gauges, 3,430 B; no agency, station code or datum.

## 5. Stage 14 validation and stage 15 publish

Stage 14: **PASS — 31 checks, 0 fail, 0 warn, 3,852 features, 28 files.** The report names every
gate: `V01–V20` and `V-A1–V-A10` (the existing duplicate `V14` step/frame check is emitted twice;
all required IDs are present). Key results:

| Gate | Result |
|---|---|
| V-A4 | peak **10,010.6 km²** = 32.2 % of flood-prone, inside 4,000–12,000 km² |
| V-A5 v4 | median **2.354 m** (≥0.7, ≤3.20), p95 **3.700 m** (≤stage), spread **1.346 m** (≥0.6), clamp **21.0 %** (≤30 %), deciles 12/12 steps |
| V-A6 | clamped AOI **5.32 %** ≤ 6 % |
| V-A7 | rising limb non-decreasing, recession non-increasing, peak S07 |
| V-A8 | stage 09 **29.9 s**; masks 1.4 MB; no `.npz` |
| V-A9 | 454→222 components, 5.4229 km² dropped at peak, 74.579 km² total; opening `none`; `wet_cells` matches every committed mask |
| V-A10 | 12 frames; max area Δ 0.535 %, max bbox Δ 0.495 px |
| V09 | max PNG 254,791 B; frames 1,469,150 B; `public/data/` 4.63 MB including manifest |
| V19 | critical 1.18 MB; animation 2.24 MB; optional/fallback 1.20 MB |
| V10/V13/V16 | no stale manifest on the validated tree; no forbidden claim/field; 1,747 zones and 33 districts consistent |

Stage 15: **28 files, 4,843,574 B (4.62 MB)** under the 9.0 MB total cap; V09 reports **4.63 MB**
including `manifest.json` itself.

| Tier | Bytes | MB |
|---|---:|---:|
| critical | 1,239,082 | 1.18 |
| animation | 2,350,502 | 2.24 |
| optional | 644,918 | 0.62 |
| fallback | 609,072 | 0.58 |

Largest committed files: `hydro/assam-rivers.geojson` 973,417 B (950.6 KB);
`risk/risk-zones.geojson` 855,563 B (835.5 KB);
`assets/critical-facilities.geojson` 574,243 B (560.8 KB);
`basemap/assam-hillshade.webp` 609,072 B (594.8 KB). Max frame 254,791 B.

## 6. Definition-of-done checklist

- [x] `public/data/` complete: frames + `frame-index.json` + summary with deciles + risk zones +
      district ranking + series + assets + gauges + manifest + provenance +
      `validation-report.json` = `pass`.
- [x] Peak extent **10,010.6 km²** inside 4,000–12,000 km²; V-A5 v4 all four shape rules pass.
- [x] Per-frame PNG ≤400 KB (max 254,791 B); animation 1,469,150 B ≤4.0 MB; `public/data/`
      4,843,574 B across 28 hashed files (4.63 MB including `manifest.json`) ≤9.0 MB; stage 09
      29.9 s ≤600 s.
- [x] Mask appendix reconciles the three areas (14,221.08 → 10,016.06 → 10,010.64 km²) and
      explains the reviewers' 6,302.5/8,129.6 km² as a mixed-HAND reconstruction.
- [x] No widened gate, no hand-edited JSON, no application code.

## 7. Reproduction

The full sequence is the stage commands in §2, §4.1 and `docs/DATA-PIPELINE.md` §5, run from the
repository root with `pipeline/src` on `PYTHONPATH`. Stage 14 must run on a tree with no stale
`manifest.json` (it verifies the previous manifest's hashes); delete the generated
`public/data/manifest.json` before re-validating after a data change, then run
`validate` → `publish`. Stage 15 writes the manifest and provenance atomically and refuses to
publish unless the validation report is `pass`.

The A5 work tree keeps no committed intermediates: `pipeline/cache/`, `pipeline/work/`,
`pipeline/work/flood-frames/` and the uint8 masks are gitignored. The committed inputs to the
artifacts are the stage-08 HAND/distance rasters and the stage-07 channel raster described in §3.

## 8. Limitations carried forward

- The HAND model is a static threshold, not routed hydraulics; the absolute median depth is
  reported, never tuned. V-A5 v4 is a shape test, not a calibration to an observed event.
- Risk zones are a cartographic block-majority generalisation required by the fixed 0.9 MB cap;
  they cover 91.8 % of the peak area, while district ranking and hotspots use the full 90 m masks.
- The 5.32 % clamped AOI share is inside V-A6 but reflects burned-channel cells below their
  nearest-channel datum; it is reported in `flood-summary.json` and the app must not present the
  depth as surveyed bathymetry.
- OSM facility completeness is unknown; asset exposure is a scenario depth join, not damage.
