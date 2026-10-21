# Review 17 — Phase 1a: Sentinel-1 validation scorecard, severity split, nit register

Scope: **P1.1 + P1.2 + P1.7** from `docs/panel/07-plan.md`, plus a nit register. No DEM swap, no
frame regeneration, no new UI sections beyond a Validation tab and the Risk panel changes.

The reviewer has already executed the Sentinel-1 path by hand. The four pitfalls below are **measured
on this machine**, not guessed — follow them exactly or the build will waste a day.

## Measured facts about the Sentinel-1 path (do not rediscover these)

1. **Anonymous S3 needs an env flag.** Opening the asset without it raises
   `CPLE_AWSInvalidCredentialsError: AWS_SECRET_ACCESS_KEY and AWS_NO_SIGN_REQUEST configuration
   options not defined`. Set `AWS_NO_SIGN_REQUEST=YES` and `AWS_REGION=us-west-2` in the process env
   (and in the pipeline config so CI is deterministic).
2. **STAC assets are dicts, hrefs are `s3://`.** Use `feature["assets"]["vv"]["href"]`. The
   collection is `sentinel-1-grd` on `https://earth-search.aws.element84.com/v1`.
3. **The COG reports `crs: None`** and the STAC `proj:epsg` is `4326` (that is the item's bbox CRS,
   not the raster's). The data is UTM. Compute the zone from `proj:centroid` (Assam 90–96 °E →
   **EPSG:32646**) and assign it explicitly before any reprojection.
4. **There is no scale/offset in `raster:bands`.** Absolute dB calibration is therefore ambiguous:
   `10·log10(DN)` gives ~+22 dB for land, `/1000` gives ~−7 dB, and neither matches a textbook VV
   water threshold because the constant is unknown. **Do not hard-code a dB threshold.** Use
   **Otsu on `10·log10(DN)`**, which is invariant to an unknown multiplicative scale (additive in dB),
   report the threshold it chooses, and add a **±2 dB sensitivity band**. Report IoU at Otsu, Otsu−2
   and Otsu+2 so the reader sees the spread.
5. **Never load a scene at native resolution.** A scene is 25,619 × 16,742 px. Read with
   `out_shape=` decimated to the ~90 m analysis grid (factor ≈ 9) using
   `Resampling.average`, then reproject onto the frame grid.

## P1.1 — Calibration script

`pipeline/src/baanh_pipeline/calibration_s1.py`, wired as a CLI stage (`build-validation`):

- STAC search: collection `sentinel-1-grd`, bbox from `config/aoi.json`, `datetime`
  `2022-06-01/2022-07-31`, instrument mode IW, GRD. Select **2 scenes** — the earliest and latest
  usable acquisitions covering the AOI — and record `scene_id`, `datetime`, `platform`,
  `relative_orbit`, `orbit_direction`, asset hrefs.
- Water mask: decimate VV → `10·log10(DN)` → Otsu threshold over AOI pixels → mask; drop connected
  components smaller than 5 analysis cells (≈4 ha at 90 m); exclude cells whose DEM slope > 10°
  (derive from the existing DEM stage output, do not fetch a new DEM).
- Reproject to **EPSG:32646, 90 m, aligned to the frame grid transform** (nearest, and also keep the
  fractional coverage raster so partial cells are honest).
- Cache rasters under `pipeline/cache/s1/` (gitignored). **Commit no scene binaries and no masks.**

**Stop-and-report rule:** if a scene cannot be fetched or the AOI coverage is < 90 %, stop and report
the failure with the exact error. Do not substitute a different date silently and do not lower the
coverage bar to make it pass.

## P1.2 — Scorecard

`public/data/validation/scorecard.json`, produced by the stage:

```
schema_version, generated_at, method{collection, threshold_method: "otsu", sensitivity_db: [-2,0,2],
slope_mask_deg: 10, min_component_cells: 5, resampling: "average→nearest", crs: "EPSG:32646", resolution_m: 90},
scenes: [ { scene_id, datetime, platform, relative_orbit, observed_area_km2, observed_water_fraction_of_aoi,
            best_match_step, best_match_iou, peak_step: {step, modelled_area_km2, iou, precision, recall, f1, area_bias_pct},
            sensitivity: { "minus2db": {iou, precision, recall}, "plus2db": {...} } } ],
summary: { mean_iou_over_scenes, mean_precision, mean_recall, worst_scene, caveats: [...] } ]
```

- Score modelled masks from the **existing PNG frames** decoded with `frame-index.json` placement;
  do not touch or regenerate the frames.
- Report metrics against **both** the best-matching step and peak S07, because the scenario is
  synthetic and has no date correspondence. The caveats array must contain, verbatim in substance:
  *"This is an extent-shape comparison against real Sentinel-1 acquisitions, not an event hindcast.
  The scenario's stage and duration were not fitted to these dates."*
  and *"Absolute SAR calibration was unavailable; masks use an Otsu threshold with a ±2 dB band."*

## P1.7 — Severity beside extent

Add to `risk/district-risk.json` per district: `severity_index` (0–100), `severity_rank`. Define it
explicitly and document it: `severity_index = 100 · z(depth_over_1_5m_share) · z(median_depth_m) ·
z(mean_duration_days)` normalised to 0–100 (**state the exact formula and normalisation in
`DATA-PIPELINE.md`; no hidden constants**). Keep `risk_score` as the extent-led score and rename it
in the UI to **"Extent score"**; show **both ranks** in the Risk panel with a one-line explanation.

Acceptance: **Dima Hasao ranks in the top third on severity and in the bottom half on extent**
(measured profile: depth>1.5 m share 0.882, median depth 3.7 m, duration 114.7 d, area share 0.004).
If your formula does not do that, the formula is wrong — say so rather than tuning it to pass.

## Nit register

Create `docs/NITS.md` with a table: `id | found in | description | blocks | status`. Seed it with:

- **N-01** `risk_class_area_share` has no machine-readable denominator in the JSON
  (`risk_class_area_share_denominator`), documented only in prose.
- **N-02** bottom-right attribution clips at narrow rail widths.
- **N-03** the Risk panel does not state that district scores are AOI-relative, only rows below 75 %
  coverage are annotated.

Statuses are `open`. Nits are **not** fixed in this phase.

## Gates and delivery

- Extend `check-data.mjs`: scorecard schema + presence, `iou/precision/recall/f1 ∈ [0,1]`,
  `observed_area_km2 > 0`, caveats non-empty and containing "not an event hindcast",
  `severity_index` distinct across districts (> 5 values), both ranks present.
- Unit tests: Otsu implementation on synthetic bimodal input; scorecard metric maths on known masks
  (e.g. perfect overlap → IoU 1.0; disjoint → 0.0).
- `npm run build:sandbox`, `check-data`, `check-budget`, `check-honesty`, `npm run test:unit`,
  pipeline `pytest`. Commit and push; CI must go green on Linux.
- Report: scene IDs + dates, observed vs modelled area per scene, IoU/precision/recall at Otsu and
  the ±2 dB band, the top 5 districts by severity rank vs extent rank, and the commit SHA.

## Do not

- Do not touch `public/data/flood/**`, `config/scenario.json`, or the frames.
- Do not commit SAR imagery, masks, or cache files.
- Do not claim a browser result you cannot produce; CI is the E2E authority.
- Do not "improve" the score a scene gives you. A bad IoU is the finding, and it ships.
