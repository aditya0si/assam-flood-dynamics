# Review 03 — resolving the A2 block: my thresholds were wrong, not the model

Reviewer: Hermes. Builder run: phase A2 (`2a0b7d8c23e2`). Builder stopped, correctly, rather
than widening a gate or hand-editing JSON. This document owns the error and replaces
`REVIEW-02` §A3–§A4 where it differs.

## Verdict on phase A2

- A1 (valley AOI), A2 (river-only channel policy), A5 (perf: 221 s, no 2.34 GB stack) are
  **accepted**. Channel cells are now 1,671 km² = 2.1 % of Assam, inside the 4 % cap.
- The block is real but it is **my fault, not the builder's**: `REVIEW-02` calibrated the stage
  table against the *old, over-wide* channel set. After A2 pruned the network, the same stage no
  longer produces the same extent, so the peak area collapsed to ~4,000 km² and the wet band
  became dominated by clamped cells — exactly the degeneracy the builder reported.

## Measured calibration on the A2 channel set (reviewer-run, connectivity + speckle control applied)

Reference: `dem-90m.tif`, `channels-90m.tif` (A2 set), `nearest-channel-elevation-90m.tif`,
valley AOI 52,358 km², Assam 78,396 km², flood-prone belt 31,050 km².

| Peak stage | Area km² | % Assam | % flood-prone | Clamped share of wet | Median depth | p95 depth | Polygon parts |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.5 | 745 | 1.0 % | 2.4 % | 50.2 % | 2.50 | 2.50 | 290 |
| 2.8 | 936 | 1.2 % | 3.0 % | 47.2 % | 2.80 | 2.80 | 377 |
| 3.1 | 2,114 | 2.7 % | 6.8 % | 37.1 % | 2.19 | 3.10 | 698 |
| 3.4 | 3,937 | 5.0 % | 12.7 % | 31.7 % | 2.07 | 3.40 | 1,167 |
| **3.7** | **6,568** | **8.4 %** | **21.2 %** | **24.2 %** | **1.81** | **3.70** | **2,184** |
| 4.0 | 10,011 | 12.8 % | 32.2 % | 20.2 % | 1.70 | 4.00 | 3,806 |

Two things this table settles:

1. **The valley "fills" between 3.1 m and 4.0 m.** There is no smooth mid-range; a 0.3 m change
   around 3.5 m doubles the extent. That is real flat-floodplain behaviour, and it means the peak
   stage must be chosen from a measured curve, never copied from a document.
2. **Speckle control alone fixes the frame budget.** 10,820 parts collapse to 2,184 at a
   comparable extent, because most parts were 1–3 cell DEM speckle, not islands. No band
   reduction, no coarse simplification, no budget change is needed.

## Binding amendments (supersede REVIEW-02 §A3, §A4; keep §A1, §A2, §A5)

### B1 — Peak stage 3.70 m, table rescaled ×1.48

The scenario keeps its shape; only the scale changes. All values remain synthetic.

| Step | Stage (m) | Above 2.0 m flag |
|---|---:|---|
| S00 | 0.30 | no |
| S01 | 0.60 | no |
| S02 | 1.05 | no |
| S03 | 1.55 | no |
| S04 | 2.15 | yes |
| S05 | 2.65 | yes |
| S06 | 3.25 | yes |
| S07 | **3.70** | yes |
| S08 | 3.25 | yes |
| S09 | 2.50 | yes |
| S10 | 1.80 | no |
| S11 | 1.05 | no |

If the main-stem/backwater split is kept in the schema, scale both columns by the same factor so
`stage = mainstem + backwater` still holds. **The builder re-derives the final peak value by
measurement**: it must produce the measured curve (stage → area, clamped share, median/p95 depth)
in `docs/PIPELINE-REPORT.md` and pick the peak inside the gates below. My 3.70 m is a starting
point from the reviewer's own run, not a value to hard-code without re-measuring.

### B2 — Depth formula (explicit, unchanged in effect)

`depth = stage − max(HAND, 0)`, i.e. the bathtub convention, so depth ≤ stage and a cell below the
datum reports the full stage. **State this bias in the docs and the UI methodology note:** the
model is conservative-shallow for cells below the datum, because there is no levee or bathymetry
data to give them a deeper surface.

### B3 — Gate revisions

| Gate | REVIEW-02 | **REVIEW-03 (binding)** | Why |
|---|---|---|---|
| `V-A4` peak extent | 4,000–12,000 km², ≤40 % flood-prone | unchanged | calibrated peak 3.7 m → 6,568 km² (21 %) |
| `V-A5` depth | median ≤1.5 m, max ≤2.6 m | **median 1.0–2.2 m; p95 ≤ peak stage; clamped share of wet cells ≤ 30 %** | the old max-depth bound was unachievable in a clamped bathtub model; the clamped share is the real degeneracy signal |
| `V-A6` clamp | ≤3.0 % of AOI | **≤6.0 % of AOI** | the 3 m datum correction leaves ~5 % of valley cells below the burnt reference; that is a declared artefact, gated rather than hidden |
| `V09` frames | ≤6,815,744 B | **≤6,815,744 B raw AND ≤1.5 MB gzip, with mandatory speckle control** | measures transfer size, which is what a reviewer's browser pays |
| new `V-A9` | — | speckle control applied: 3×3 binary opening on the wet mask and parts < 0.1 km² dropped **before** polygonisation; both counts recorded | 10,820 → ~2,200 parts, and the dropped parts are DEM noise |

### B4 — Frame budget resolution

The frame-cap conflict is closed by `V-A9`, not by raising the cap. If, after speckle control, a
frame still exceeds 6.5 MB, the builder may switch that step to a **two-class depth rendering**
(shallow 0–1 m / deep ≥1 m) and record the change in `ARCHITECTURE.md` §7.2 and the manifest —
but it may not silently drop real polygons to make the number fit.

## What the builder must do next (phase A3)

1. Apply B1–B3 to config, scenario, validator, and the docs sections they supersede.
2. Re-run stage 09 → 10 → 11 → 12 → 14 → 15.
3. Publish the measured calibration curve and the chosen peak value in `docs/PIPELINE-REPORT.md`.
4. Commit at 09 green, then 10–12 and 14–15 green.

## Process note

The builder's refusal was the right call and the loop worked: the reviewer's thresholds were the
defect. Future briefs from me will state gates as *measured bands with a required calibration
table*, not as fixed numbers copied from an earlier channel set.
