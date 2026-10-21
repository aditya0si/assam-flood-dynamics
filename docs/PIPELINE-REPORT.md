# Baanh M0 phase A4 — raster frame contract and area filter

**Status: BLOCKED at stage 09 (`build-inundation`) on V-A5.** C1–C3 are implemented: the frame
contract is now one half-resolution 5-class paletted PNG per step plus `frame-index.json`, with no
per-band GeoJSON and no vector outline; the 3×3 morphological opening is gone and a ≥9-cell
connected-component area filter is applied before statistics, masks and rendering. Stage 09 now
runs in **29.6 s**, writes 12 PNGs of **65.8–254.8 KB** (1,469,150 B total), and passes V-A4, V-A8,
V-A9 and the PNG side of V09/V-A10. It still fails **V-A5** on the documented channel-proximity
connectivity mask: peak median **2.354 m** against the 1.00–2.20 m gate. The reviewer's
"area filter ≥9 cells" alternative was measured at 1.92 m and 6,303 km²; on these rasters that
combination is not reproducible (see §3). No gate was widened, no committed JSON was hand-edited,
and no failing `public/data/flood/` file was published.

- Run date: 2026-10-21 (local), Windows 11, Python 3.11.16 (64-bit).
- Repository: `C:\Users\oliad\Desktop\baanh`.
- Interpreter: `$env:PYTHONPATH=(Resolve-Path pipeline\src).Path; python -m baanh_pipeline.cli …`.
- Working tree: C1–C3 in `pipeline/config/`, `pipeline/src/baanh_pipeline/` and the amended
  `ARCHITECTURE.md` / `DATA-PIPELINE.md` / `MILESTONES.md`; committed `admin/`, `hydro/` and
  `basemap/` outputs are unchanged.
- `pipeline/cache/`, `pipeline/work/` and the stage-09 staging frames are gitignored.

## 1. What C1–C3 changed

| Amendment | Applied as |
|---|---|
| **C1** frame contract v3 | Stage 09 emits `public/data/flood/frames/step-XX.png` (3733×2611, 5-class P-mode PNG, class 0 transparent) and `public/data/flood/frame-index.json` (`bbox`, `width`, `height`, palette, per-step `file`/`area_km2`/PNG bytes). The per-band GeoJSON, the combined `flood-frames.geojson`, the per-step vector outline and all polygonisation/simplification code are removed. |
| **C2** gates | `V-A9` is now the ≥9-cell component-area filter with no opening; it records raw/connectivity/before/after component counts and dropped km² and is re-derived from the wet masks. `V-A10` is new: index bbox/half-resolution within 1 pixel and PNG wet-cell area within 1 %. `V09` is per-frame PNG ≤400 KB, animation tier ≤4.0 MB, `public/data/` ≤9.0 MB, PNG gated raw and JSON gated on gzip. `V-A4`/`V-A5` bands are unchanged. |
| **C3** architecture | `ARCHITECTURE.md` §6.7 loads `frame-index.json` once and then only the current/next PNG (two-image working set); §7.2 keeps the flood band under the vector overlays but as two raster `image` layers; §7.4 is the two-image opacity crossfade with no re-tiling/source rebuild; the legend reads the same class list from the index. `DATA-PIPELINE.md` §6.7/§6.8/§7.7/§7.8/§10/§11 are rewritten. |
| **No opening** | `binary_opening` is not imported by stage 09. The only wet-mask operation after connectivity is `scipy.ndimage.label` + a component-size floor of 9 cells (≈0.073 km²). |

## 2. Stage 09 run (final model: connectivity + area filter)

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

Observed wall time: **29.6 s** (stage 09), exit code 1 at the V-A5 check. All 12 PNGs were written
to the gitignored staging directory and measured; the publish step is after every gate, so no
`public/data/flood/` file exists. The per-step uint8 masks are in
`pipeline/work/inundation-masks/`; `pipeline/work/flood-frames/` holds the 12 staging PNGs.

### Per-frame PNG bytes and depth statistics (final model)

| Step | Label | Stage m | Area km² | Median m | p95 m | Clamp wet | Components before→after | Dropped km² | PNG B | PNG wet cells | PNG area km² | Δ area |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S00 | 01 Jun | 0.30 | 1,833.9 | 0.300 | 0.300 | 19.6 % | 535→248 | 6.5 | 67,354 | 56,905 | 1,839.59 | 0.31 % |
| S01 | 15 Jun | 0.60 | 1,904.1 | 0.600 | 0.600 | 21.1 % | 533→249 | 6.3 | 70,185 | 59,082 | 1,909.96 | 0.31 % |
| S02 | 01 Jul | 1.05 | 2,149.1 | 1.050 | 1.050 | 25.9 % | 530→246 | 6.3 | 75,947 | 66,581 | 2,152.39 | 0.15 % |
| S03 | 15 Jul | 1.55 | 2,464.7 | 1.550 | 1.550 | 28.2 % | 529→245 | 6.5 | 87,225 | 76,437 | 2,471.01 | 0.26 % |
| S04 | 25 Jul | 2.15 | 3,284.9 | 2.150 | 2.150 | 29.8 % | 523→245 | 6.3 | 106,091 | 101,786 | 3,290.47 | 0.17 % |
| S05 | 05 Aug | 2.65 | 4,275.1 | 2.650 | 2.650 | 29.2 % | 516→240 | 6.2 | 128,137 | 132,419 | 4,280.75 | 0.13 % |
| S06 | 15 Aug | 3.25 | 6,857.4 | 2.842 | 3.250 | 24.6 % | 499→238 | 6.0 | 193,215 | 212,146 | 6,858.12 | 0.01 % |
| **S07** | **25 Aug** | **3.70** | **10,010.6** | **2.354** | **3.700** | **21.0 %** | **454→222** | **5.4** | **254,791** | **309,751** | **10,013.43** | **0.03 %** |
| S08 | 05 Sep | 3.25 | 6,857.4 | 2.842 | 3.250 | 24.6 % | 499→238 | 6.0 | 193,215 | 212,146 | 6,858.12 | 0.01 % |
| S09 | 15 Sep | 2.50 | 4,003.1 | 2.500 | 2.500 | 30.0 % | 517→240 | 6.3 | 121,703 | 123,971 | 4,007.65 | 0.11 % |
| S10 | 30 Sep | 1.80 | 2,769.5 | 1.800 | 1.800 | 29.5 % | 527→246 | 6.4 | 95,340 | 85,860 | 2,775.63 | 0.22 % |
| S11 | 15 Oct | 1.05 | 2,149.1 | 1.050 | 1.050 | 25.9 % | 530→246 | 6.3 | 75,947 | 66,581 | 2,152.39 | 0.15 % |
| **total** | — | — | — | — | — | — | — | **74.6** | **1,469,150** | — | — | max **0.31 %** |

- Frame size: **3733 × 2611** px (width × height), half of the 7466 × 5223 analysis grid at
  ≈180 m/px. `frame-index.json` bbox is `[89.424203, 23.911344, 96.265512, 28.193794]`.
- **V09:** max PNG **254,791 B** (≤409,600 B), total animation frames **1.47 MB** (≤4.0 MB).
  The projected animation tier including `frame-index.json`, `flood-summary.json` and
  `risk-zones.geojson` is well under 4.0 MB; `public/data/` is not published, so the 9.0 MB total
  is not yet measured.
- **V-A10 (PNG side):** the PNG wet-cell area is within **0.31 %** of the summary area at every
  step (≤1 %). PNG mode is `P`; the index width/height and bbox reproduce the frame footprint.
  The full validator run (V-A10 bbox check) is not reachable because stage 09 stops at V-A5.
- **Component-filter audit (peak):** 454 connectivity components → **222** after the ≥9-cell
  filter; **232 components dropped**, **5.4229 km²** dropped at the peak; 74.579 km² dropped over
  all 12 steps. `opening` is `none`. This is the final model's audit and is re-derived from the
  masks by V-A9.

### Why the run stops

| Gate | Rule | Observed | Status |
|---|---|---|---|
| V-A4 | peak 4,000–12,000 km², ≤40 % flood-prone | 10,010.6 km², 32.2 % | pass |
| V-A5 | peak median 1.0–2.2 m; p95 ≤ stage; clamp wet ≤30 % | **median 2.354 m**; p95 3.700 m; clamp 21.0 % | **fail** |
| V-A6 | clamped AOI ≤6.0 % | 5.3168 % | pass |
| V-A7 | rising non-decreasing; recession non-increasing; peak S07 | 1,833.9→10,010.6→2,149.1; peak S07 | pass |
| V-A8 | stage 09 ≤600 s; no artifact >300 MB | **29.6 s**; masks 1.4 MB; no `.npz` | pass |
| V-A9 | ≥9-cell area filter, no opening, counts and dropped area recorded | applied; peak 454→222, 5.4229 km² dropped | pass |
| V09 | per-frame PNG ≤400 KB; animation ≤4.0 MB; total ≤9.0 MB | max 254,791 B; frames 1.47 MB; total not published | pass on frames |
| V-A10 | index/PNG extent within 1 px; area within 1 % | max area Δ 0.31 %; bbox built from the raster footprint | pass on PNG side |

The first hard failure is V-A5, median 2.354 m. Removing the opening lowered the median from
A3's 2.485 m to 2.354 m; it did **not** reach the reviewer's 1.92 m, because the channel-proximity
connectivity filter (unchanged by REVIEW-04) still removes the shallow, hydraulically isolated
components that pull the median down.

## 3. The reviewer's area-filter variant is not reproducible

REVIEW-04 §"Measured alternative" gives **6,303 km²**, **2,885 components**, **median 1.92 m**,
**clamp 25.2 %**, **8,413 raw rings** at 3.70 m for "area filter ≥9 cells, no opening". I measured
the two coherent interpretations of that instruction on the same rasters:

| Variant | Peak components | Peak area km² | Median m | p95 m | Clamp wet | Max PNG B | Frames B | Gate result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Area filter on the connectivity mask (final model) | 454 → 222 | 10,010.6 | 2.354 | 3.70 | 21.0 % | 254,791 | 1,469,150 | **V-A5 fail** |
| Area filter on the raw HAND mask (no connectivity) | 37,164 → 7,197 | 13,579.3 | 1.995 | 3.70 | 20.3 % | ≈333,500 | ≈2.44 MB | **V-A4 fail** |
| REVIEW-04 expected | 12,700 → 2,885 | 6,303 | 1.92 | 3.70 | 25.2 % | — | ≈2.1 MB | — |

The raw-mask variant reproduces the reviewer's **median** (1.995 vs 1.92) but its peak extent is
13,579 km², 13.2 % above the 12,000 km² V-A4 ceiling. The connectivity variant reproduces the
**extent** (10,011 km²) but not the median. Neither reproduces **6,303 km² and 2,885 components
at the same time**; the reviewer's 6,303 km² is between the A3 opened mask (6,924 km²) and the
area-filtered connectivity mask (10,011 km²), while their 1.92 m median is characteristic of the
unconnected raw mask. This is the same mixed-mask pattern that REVIEW-03's table showed, and the
process note in REVIEW-04 ("a gate that constrains output size must be backed by an artifact I
generated and measured") applies here too.

The A3 opening did fragment the mask (326 → 3,477 components); removing it is correct. But the
opening was **not** the only cause of the median gap: the connectivity filter contributes ~0.36 m
of it, and the reviewer's 1.92 m is only reachable by keeping hydraulically isolated shallow
components that the documented model drops.

## 4. What would make this green (reviewer decision, not a builder edit)

1. **Define V-A5 on one mask.** State whether the median is computed on the raw HAND threshold,
   the connectivity-filtered mask, the area-filtered mask, or a chosen combination. On the mask
   stage 09 actually commits, the 3.70 m median is 2.354 m.
2. **Reconcile V-A4 with the area filter.** If the area filter replaces connectivity, the peak is
   13,579 km² and V-A4 needs a measured re-band or a re-derived peak stage. If connectivity stays,
   V-A5 needs a measured re-band. Either change must be a reviewer amendment backed by the
   committed mask/PNG artifact, not a builder threshold edit.
3. **Keep the raster contract.** The PNG contract itself is green: 12 frames, 1.47 MB total, max
   254.8 KB, 0.31 % area agreement, 29.6 s. V09/V-A10 do not need changing.

No data was committed at a failing gate. The committed tree remains at the last green state:
`admin/assam-state.geojson`, `hydro/assam-rivers.geojson` and `basemap/assam-hillshade.webp` only.
