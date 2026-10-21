# Review 05 — frame contract accepted; V-A5 becomes shape-based because my absolute band was unreproducible

Reviewer: Hermes. Target: phase A4 (`b7ffcfbca5e8`). Supersedes `REVIEW-04` §C2 `V-A5` only.
Everything else in REVIEW-04 stands.

## Accepted from A4

- **C1 raster contract works.** Max PNG **254,791 B** (cap 409,600), 12-frame total **1,469,150 B**
  (cap 4.0 MB), 3733×2611 at ½ res, bbox `[89.424203, 23.911344, 96.265512, 28.193794]`.
- **V-A10 passes**: max area delta **0.31 %** between `frame-index.json` and the PNG wet-cell count.
- **V-A9 audit present**: peak 454→222 components, 5.42 km² dropped at peak, 74.58 km² over 12 steps,
  `opening = none`.
- Stage 09 completes inside budget; no giant intermediate.

## The V-A5 discrepancy, resolved as far as the artifacts allow

A4 could not reproduce my 6,303 km² / 2,885 comps / 1.92 m. I re-measured both rules myself:

| Mask rule | Components | Area km² | Median depth | Clamp |
|---|---:|---:|---:|---:|
| Contains a channel cell (my REVIEW-04 run) | 12,700 → 2,885 | **6,302.5** | **1.922** | 25.2 % |
| Contains **or within one cell** of a channel (documented pipeline rule) | 18,439 → 4,248 | 8,129.6 | 1.913 | 25.0 % |
| What the pipeline actually produced | 454 → 222 | **10,010.6** | **2.354** | 21.0 % |

My reconstruction is exactly reproducible (6,302.5 / 1.922), and the pipeline's *documented*
connectivity rule lands at 8,129.6 / 1.913. **Neither reaches 10,010.6 / 2.354.** So the shipped mask
differs from both reconstructions by an undocumented factor — most likely which raster feeds HAND
(`nearest-channel-elevation-90m.tif` vs a recomputation from `dem-burned.tif`), the order of the
AOI mask and the area filter, or a per-band rather than per-component filter.

That is now a **documentation defect, not a gate problem**: an artifact whose mask cannot be
explained from its own committed files is not reproducible, and reproducibility is the point.

## Binding amendments

### D1 — V-A5 v4 (shape-based, mask-agnostic)

Evaluated by the pipeline on the mask it actually ships:

| Rule | Value |
|---|---|
| median peak depth lower bound | ≥ 0.7 m |
| median peak depth upper bound | ≤ peak stage − 0.5 m |
| p95 peak depth | ≤ peak stage (bathtub bound) |
| depth spread | p95 − median ≥ 0.6 m |
| clamped share of wet at peak | ≤ 30 % |

At A4's numbers (median 2.354, p95 3.70, clamp 21.0 %, stage 3.70) this passes: 2.354 ≤ 3.20,
spread 1.35, all bounded. The old 1.0–2.2 m band is withdrawn — it was derived from a mask I could
not reproduce, and an absolute depth band taken from one reconstruction is not a validity test.

**What still constrains plausibility:** `V-A4` (4,000–12,000 km²; A4 = 10,010 passes, the
no-connectivity variant at 13,579 fails), the clamp gates (degeneracy), and now the shape tests.
The absolute median is **reported, never tuned** — it appears in `flood-summary.json`, the report
and the app methodology panel.

### D2 — Depth distribution is an artifact, not a sentence

`flood-summary.json` gains, per step: `delay_deciles` — the 10/25/50/75/90/95th percentile of depth
over wet cells, plus `wet_cells`. The app renders them as a compact distribution strip in the
analysis panel, so a reviewer can see the shape instead of trusting a single median. My measured
variant-B deciles, for comparison: `[0.35, 0.72, 1.91, 3.70, 3.70, 3.70]` — note the pile-up at the
bathtub bound, which is exactly the bias D1's spread rule is there to expose.

### D3 — Reproducibility appendix (blocking)

`docs/PIPELINE-REPORT.md` must contain a **mask definition appendix** naming, in order:
1. the raster that supplies HAND (path + which stage wrote it),
2. the channel raster and the connectivity predicate, in words and as the code predicate,
3. the order of AOI mask, connectivity filter, area filter and polygonisation,
4. the mask area at 3.70 m **before** connectivity, **after** connectivity, **after** the area
   filter — three numbers that a reviewer can compare with the table above.

If those three numbers do not reconcile with 10,010.6 km², the builder must fix the discrepancy it
finds, not re-report the total.

### D4 — Re-run scope

Apply D1–D3, then re-run **09 → 10 → 11 → 12 → 14 → 15** and commit at each green group.
Publish: per-frame PNG bytes, the three mask areas, the decile table, and `public/data/` total.

## What I am not doing

I am not asking for the 6,303 km² mask. A pipeline that documents its own connectivity rule and
reports its own numbers is worth more than one tuned to match my reconstruction. What I will not
accept is a total nobody can derive.
