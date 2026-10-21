# Review 20 — Phase 1a accepted; Phase 1b scope (observed forcing, exposure, class labels)

## 1a acceptance (commit `67a40f9`, `d36a5ea`; CI `39671490436` success)

Reviewer-verified after the validity fix:

| Quantity (2022-07-31 scene) | Reviewer | Shipped | Verdict |
|---|---|---|---|
| Scene area | 43,389 km² | 43,391.3 km² | ✓ agree |
| Validity | 41,193 km² (94.9 %) | **42,419.6 km² (97.76 %)** | ✓ within 3 %, edge treatment |
| Observed @ −16 dB | 467.1 km² | 490.19 km² | ✓ within 5 % |
| Model in validity | 568.2 km² | 553.53 km² | ✓ within 3 % |
| IoU | 0.0827 | **0.0995** | same family; delta is co-registration |
| Precision / recall | 0.139 / 0.169 | **0.171 / 0.193** | ✓ recall halved from the false 0.39 |
| `TP+FP` and `TP+FN` identities | — | hold to < 0.0002 km² | ✓ |

Attrition is now a published object with per-step area, `applied_to_final`, and reasons — including
the **diagnostic** legacy AOI core (3,743 km²) whose note records exactly the defect: *"clipping to
the valley-floor core kept 3,735 km² of this scene and selected the model's wet area."* The slope
branch is computed (16,566 km²) and explicitly not applied, with a stated reason. Summary now reads
mean IoU **0.0934**, precision **0.154**, recall **0.193**, mean validity fraction **97.76 %**.

Three defects were caught in this phase, all in the same family — numbers that looked fine:

1. a caveat asserting calibration was unavailable when a 1 MB LUT shipped beside the asset;
2. a sensitivity band measured in uncalibrated units, where ±2 dB has no physical meaning;
3. a validity footprint of 8.6 % of the scene that inflated IoU by 63 % and recall by 2.3×.

The honest baseline now stands: **the HAND scenario captures ~19 % of observed Sentinel-1 water at
−16 dB, and ~83 % of its modelled extent sits where SAR sees dry land.** That is the number Phase 2
must beat, and it is published in the app.

## Phase 1b scope

### P1.3 — Real forcing, labelled correctly

- Pull **ERA5 precipitation** from the Open-Meteo archive (`archive-api.open-meteo.com`, verified 200):
  daily totals 2015-01-01 → 2025-12-31 at a documented grid, plus district areal means over the
  existing district polygons.
- Pull **Open-Meteo forecast** for the current window and store it separately; it must be visually
  distinguishable from the archive series.
- **Label discipline — this is the point of the task.** ERA5 is a *reanalysis*, not an observation.
  Publish a three-way `class` on every series: `observed` (gauge, SAR), `reanalysis` (ERA5),
  `scenario` (synthetic). No series may be labelled `observed` unless it is a direct measurement.
  `check-data` must fail if an `observed` label appears on an ERA5-derived series.
- Publish the monsoon-season rainfall total per district for 2022 and the 2015–2025 mean, so the
  scenario can be compared against a real season in the UI.
- Provenance: endpoint, query, retrieval timestamp, grid resolution, units, and the caveat that ERA5
  is model-based and biased in complex terrain.

### P1.5 — Exposure (estimates, explicitly labelled)

- WorldPop REST (`worldpop.org/rest/data/pop/wpgp?iso3=IND`, verified 200): population per cell at
  the finest available resolution; aggregate to the peak flood mask and to districts.
- Publish `potentially_exposed_residents` per district with `class: derived`, the WorldPop vintage,
  and the method sentence. **Never "affected", "displaced", or "casualties".** `check-data` already
  forbids those fields; extend it to forbid them inside exposure files too.
- Include the uncertainty statement: this is a static population raster crossed with a synthetic
  flood mask; it is not an impact assessment.

### P1.6 — Class badges and data age

- Every data surface (layer control, chart, panel, legend) carries one of
  `OBSERVED · REANALYSIS · DERIVED · SCENARIO`, plus a `data as of` age.
- The scenario timeline keeps `SCENARIO` even where it is informed by `REANALYSIS` rainfall.
- Playwright: assert each badge type appears at least once, and that the Validation tab and the
  rainfall chart both expose an age.

### Explicitly out of scope for 1b

DEM swap (P1.4) and OSM facilities — both are heavier and go after the forcing/exposure pairing.

## Gates

`check-data` additions: series `class` enum and the ERA5-not-observed rule; exposure field-name
forbidden list; `data_as_of` present on every published series and panel feed. All existing gates,
unit tests, pipeline pytest, build and CI stay green. Report the district monsoon totals for 2022 vs
mean, the exposed-population totals with the caveat, and the commit SHAs.
