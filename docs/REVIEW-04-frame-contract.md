# Review 04 — frame contract v3: raster frames, area filter, no morphological opening

Reviewer: Hermes. Target: phase A3 (`16a6ae14112c`). Supersedes `REVIEW-03` §B3 (`V-A5`, `V-A9`,
`V09`) and changes the flood-frame file contract in `DATA-PIPELINE.md` §6.7 and
`ARCHITECTURE.md` §6.7 / §7.4.

## What A3 proved

A3 fixed the model: peak **6,924 km² (22.3 % flood-prone)** at 3.70 m, hydrograph monotone with
the peak at S07, clamp 29.3 % of wet / 5.32 % of AOI, stage 09 in 238 s with no 2.34 GB stack.
Those gates passed. It then failed the two gates that describe *rendering*, and it was right
about why.

**My V-A9 was wrong.** A 3×3 binary **opening** erodes one-cell-wide fringes and does not
reconnect them: at the peak it *fragmented* 326 components into 3,477 and the frame polygons grew
to 40,353. The speckle remedy is a **component-area filter, never an opening**.

## Measured alternative (reviewer-run, same rasters, stage 3.70 m)

| Variant | Components | Area km² | Median depth | p95 | Clamp | Parts |
|---|---:|---:|---:|---:|---:|---:|
| Opening 3×3 + <0.1 km² (A3) | 326 → 3,477 | 6,924 | 2.485 | 3.70 | 29.3 % | 40,353 (12 frames) |
| **Area filter ≥9 cells, no opening** | 12,700 → **2,885** | **6,303** | **1.92** | 3.70 | 25.2 % | 8,413 raw rings at peak |

Opening was also the cause of the median-depth failure: eroding the shallow fringe leaves the deep
core, inflating the median from 1.92 m to 2.485 m. The model was never the problem.

## Frame sizes, measured (not estimated)

| Representation | Size | Verdict |
|---|---:|---|
| PNG, 5-class depth, full res 7466×5223 | 484 KB/frame | viable but 5.8 MB for 12 frames |
| **PNG, 5-class depth, ½ res 3733×2611** | **175 KB/frame** | **chosen: ≈2.1 MB for 12 frames** |
| PNG, ¼ res 1866×1305 | 62 KB/frame | fallback for slow links |
| Vector bands (A3) | 21.0 MB raw / 5.35 MB gzip | rejected |
| Single outline, 150 m simplify, ≥0.5 km² | 2.57 MB raw / 0.92 MB gzip **per frame** | rejected for M0 |

The vector outline is as expensive as the bands because a flat floodplain at 90 m genuinely has
hundreds of disjoint rings. Rendering them is not worth 11 MB. Depth bands belong in a raster;
interaction belongs to district polygons and `flood-summary.json`, which the pipeline already
produces.

## Binding amendments

### C1 — Frame contract v3 (replaces per-band GeoJSON)

Per step, the pipeline writes:

- `public/data/flood/frames/step-XX.png` — 5-class palette raster (0 = transparent/dry,
  1 = 0–0.5 m, 2 = 0.5–1.5 m, 3 = 1.5–3.0 m, 4 = 3.0+ m) at **½ the analysis resolution**
  (≈180 m/px), palette + transparency baked in, optimized PNG.
- `public/data/flood/frame-index.json` — `{ bbox: [w,s,e,n], width, height, classes: [...],
  steps: [{ id, label, stage_m, file, area_km2 }] }`, enough for the app to place each image
  without knowing the projection.
- `public/data/flood/flood-summary.json` — unchanged schema (per-step area, district shares).

No per-band GeoJSON and no per-step vector outline in M0. A peak-extent outline is allowed as
**P1** with its own cap; do not ship it in M0.

### C2 — Gate revisions

| Gate | New rule |
|---|---|
| `V-A5` | median peak depth **1.0–2.2 m**, p95 ≤ peak stage, clamped share of wet ≤30 %, computed on the area-filtered mask |
| `V-A9` | **component-area filter ≥9 cells (0.073 km²)** applied before statistics and rendering; **morphological opening is forbidden** (record: components before/after, km² dropped) |
| `V-A4` | peak extent 4,000–12,000 km², measured after the area filter (6,303 km² expected at 3.70 m) |
| `V09` | per-frame PNG ≤ **400 KB**; animation tier ≤ **4.0 MB**; `public/data/` total ≤ **9.0 MB**; PNG size gated raw (already compressed), JSON gated on gzip |
| `V-A10` | `frame-index.json` bbox/resolution reproduce every frame's extent within 1 pixel; each step's `area_km2` matches the PNG's wet-cell count × cell area within 1 % |

### C3 — App-side consequences (patch the architecture, do not redesign it)

- `ARCHITECTURE.md` §7.4 becomes **two raster `image` sources with an opacity crossfade** instead
  of two filtered fill layers; keep the "no re-tiling, no source rebuild" rule.
- §7.2 paint order keeps the flood layer in the same band; it is now a raster layer under the
  vector overlays.
- §6.7 data-load contract loads `frame-index.json` once and then the current/next step PNG only
  (two-image working set), not all 12.
- Depth class colours come from the palette baked into the PNGs; the legend in the UI reads the
  same class list from `frame-index.json` so the two cannot drift.

### C4 — Re-run scope

Apply C1–C3, then re-run **09 → 10 → 11 → 12 → 14 → 15**. Commit at 09 green, 10–12 green,
14–15 green. Publish per-frame PNG sizes and the component-filter audit in
`docs/PIPELINE-REPORT.md`.

## Process correction

Two of my three gates in REVIEW-03 were wrong in the same way: I wrote a rendering gate from a
prototype that measured polygon *counts* but never wrote a frame. From here, a gate that constrains
output size must be backed by an artifact I generated and measured — PNG bytes, GeoJSON bytes —
not a count I extrapolated.
