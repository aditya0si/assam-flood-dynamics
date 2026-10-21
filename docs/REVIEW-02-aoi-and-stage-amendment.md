# Review 02 — phase A verdict, root cause, and binding amendments

> **Superseded in part by `REVIEW-03-stage-calibration.md`.** A3 (stage table), A4 (gates) and
> their restatements below are replaced by REVIEW-03 B1–B4. A1, A2 and A5 remain in force.
> This document is kept as the record of what phase A decided, not as current gate values.

Reviewer: Hermes (orchestrator + reviewer). Builder run: phase A (`2a`), commits
`e441d03` (stages 01–03), `c1add67` (04–07), `7267189` (08 + blocked stage 09).

## Verdict

- Stages **01–08: accepted.** Data exists, sizes match the report, provenance chain intact.
- Stage **09: correct failure, correctly reported.** The builder refused to fabricate a pass and
  left the tree committed at the last green stage. That is the behaviour the brief demanded.
- Stages **10–15: not runnable** until the amendment below is applied.

The gate did not fail because it was strict. It failed because the **scenario stage values are
one order of magnitude too large for the HAND distribution**, and the channel mask is roughly
4× too wide.

## Measured evidence (recomputed by the reviewer from `pipeline/work/`, not taken from the report)

Grid: 5,223 × 7,466 @ 90 m, EPSG:32646, 0.0081 km²/cell. Assam rasterises to **78,396 km²**
(official 78,523) — the grid is correct.

| Measurement | Value | Reading |
|---|---|---|
| Channel cells (`channels-90m.tif`) | 1,068,977 = **8,659 km² = 11.0 % of Assam** | 4× too wide; includes reaches outside Assam (Bhutan `Puna Tsang Chhu`, `Drangme Chhu`, Tibetan `娘姆江曲` appear in the display layer) |
| DEM ≤ 120 m (valley floor) | **52,358 km² = 66.8 % of Assam** | The hill districts carry 33 % of the state; flooding them with a uniform stage is not meaningful |
| HAND inside valley ≤ 120 m | p10 **0.69 m**, p50 **5.59 m**, p90 **13.86 m** | The median valley cell is 5.6 m above local drainage |
| Stage 6.0 m over valley | **28,520 km² = 36.4 % of Assam / 54.5 % of valley** | A 6 m uniform stage is above the 60th percentile of valley HAND — it must flood most of the valley |
| Stage 2.5 m over valley | 9,016 km² = 11.5 % of Assam / 17.2 % of valley | Inside the plausible band |
| Stage 1.7 m over valley | 6,968 km² = 8.9 % of Assam | Early monsoon scale |
| Clamped HAND cells | 5.29 % | Above the 2 % warning: consistent with an over-wide, over-deep burn |

**Conclusion:** the 30 % gate was also too loose, but loosening it would have shipped a map that
claims half of Assam floods at once. The fix is to rescale the scenario to the actual HAND
distribution and to narrow the channel network — not to move the goalposts.

## Citable anchor for the plausibility band

Government of Assam, Water Resources Department: the state's **flood-prone area is 31.05 lakh
hectares (≈31,050 km²) against a state area of 78.523 lakh hectares — 39.6 % of the state**
(source: `https://waterresources.assam.gov.in/portlets/flood-erosion-problems`, retrieved
2026-10-21). This is a *flood-prone area* statistic, not a single event's extent, and the docs
must say so. It gives two defensible numbers: the analysis domain should sit inside the
flood-prone belt, and a peak scenario should not exceed it.

## Binding amendments (supersede `DATA-PIPELINE.md` §3, §7.3, §8; renumber gates)

### A1 — Analysis domain (AOI v2)

`AOI_v2 = (inside Assam) ∩ (DEM ≤ 120 m)`, with a 2 km buffer kept for edge continuity.
Metrics are reported against three denominators: `AOI_v2`, Assam (78,523 km²), and the
flood-prone area (31,050 km²). State the source of the flood-prone figure in `provenance.json`.

### A2 — Channel policy v2

1. `waterway=river` only. Drop `stream`, `canal`, `drain`, `ditch`.
2. Clip to `AOI_v2` buffered by 5 km. A way whose midpoint is outside that buffer is excluded
   from both the burn and the display layer — no upstream foreign reaches.
3. Drop ways shorter than 2 km after clipping.
4. Keep the Brahmaputra main stem as `order 1`; 2-cell dilation applies to it only. All other
   channels: 1 cell, no dilation.
5. **Hard gate:** channel cells ≤ **4.0 %** of `AOI_v2`. If exceeded, prune the shortest ways
   until it passes; record how many were pruned in `provenance.json`.
6. The display layer (`hydro/assam-rivers.geojson`) shows the same pruned set as the model. It
   must never show a river the model does not use.

### A3 — Stage table v2 (replaces `DATA-PIPELINE.md` §8.1)

> **Superseded by REVIEW-03 B1.** The ×0.42 table below collapsed to ~4,000 km² on the pruned A2
> channel set; the current table is ×1.48 with a measured peak of 3.70 m.

Rescale the existing curve shape by ×0.42 so the peak sits inside the HAND distribution.
All values remain **synthetic scenario parameters**; the split into main-stem and backwater is
still a narrative device.

| Step | Label | Stage above drainage (m) | Above 1.5 m flag |
|---|---|---:|---|
| S00 | 01 Jun | 0.20 | no |
| S01 | 15 Jun | 0.40 | no |
| S02 | 01 Jul | 0.70 | no |
| S03 | 15 Jul | 1.05 | no |
| S04 | 25 Jul | 1.45 | no |
| S05 | 05 Aug | 1.80 | yes |
| S06 | 15 Aug | 2.20 | yes |
| S07 | 25 Aug | **2.50** | yes |
| S08 | 05 Sep | 2.20 | yes |
| S09 | 15 Sep | 1.70 | yes |
| S10 | 30 Sep | 1.20 | no |
| S11 | 15 Oct | 0.70 | no |

The rainfall, main-stem and backwater columns are untouched (they are narrative only); if the
schema asserts `stage = mainstem + backwater`, then rescale those two columns ×0.42 as well so
the identity still holds, and keep both labeled synthetic.

### A4 — Gates v2 (replace stage-09's single 30 % rule)

> **Superseded by REVIEW-03 B3.** V-A3's peak, V-A5's depth bounds and V-A6's 3.0 % clamp are
> replaced; V-A9 (speckle control) is new and V09 now measures gzip as well. V-A4 is unchanged.

| Gate | Rule |
|---|---|
| `V-A1` | `AOI_v2` area between 45,000 and 56,000 km² |
| `V-A2` | channel cells ≤ 4.0 % of `AOI_v2`; zero channel ways with midpoint outside Assam + 5 km |
| `V-A3` | stage series strictly increases S00→S07, strictly decreases S08→S11, peak = 2.50 m |
| `V-A4` | peak extent between **4,000 and 12,000 km²**, and ≤ 40 % of the 31,050 km² flood-prone area |
| `V-A5` | peak depth: median ≤ 1.5 m, max ≤ 2.60 m (stage − HAND) |
| `V-A6` | clamped HAND cells ≤ 3.0 % (down from 5.29 %) |
| `V-A7` | every rising-limb step's area is non-decreasing; recession non-increasing; peak at S07 |
| `V-A8` | stage 09 wall time ≤ 10 min and `pipeline/work/inundation-stack.npz` ≤ 300 MB |

`V-A4` is a **plausibility band chosen by the reviewer**, not a calibrated observation. Say so in
`provenance.json` and in `docs/PIPELINE-REPORT.md`.

### A5 — Performance fix for stage 09

The phase-A run held a 2.34 GB float stack and took ~30 min. Required changes:

1. Build masks per step in `uint8`, never a float stack of all steps.
2. Clip to `AOI_v2` **before** polygonisation; never polygonise the full state grid.
3. Write `flood/frames/step-XX.geojson` incrementally, one file per step, then the combined
   `flood-frames.geojson` from those (or keep frames separate and update the manifest — say
   which, and make `ARCHITECTURE.md` §6.7's load contract match the choice).
4. Delete the giant `.npz` from the accepted path; if a cache is needed, cap it at 300 MB.

### A6 — Re-run scope

Keep stages 01–03 outputs and their commits. Re-run **06 (rivers clip), 07, 08, 09, 10, 11, 12,
14, 15**, plus 04/05 only if the AOI change alters the hillshade or state output (it should not).
Commit after 06–08 and again after 09, then after 10–12, then 14–15.

## Process notes (no action required)

- The builder used Python 3.11.16 with `PYTHONPATH` because an editable install was blocked by
  the sandbox. Acceptable, but record the interpreter and the exact invocation in the report so a
  reviewer can reproduce it.
- The 30 % gate in `MILESTONES.md` and the V-gates in `DATA-PIPELINE.md` §12 must be updated to
  point at this amendment, so the docs and the code cannot disagree later.
