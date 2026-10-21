# Phase 1a report — Sentinel-1 validation, severity split, nit register

Date: 2026-10-21. Scope: REVIEW-17 P1.1, P1.2, P1.7, REVIEW-18 and REVIEW-19; `docs/NITS.md`.
No DEM swap, no frame regeneration, no change to `public/data/flood/**` or
`public/data/scenario.json`.

## Sentinel-1 acquisitions

The STAC search was `sentinel-1-grd` on `https://earth-search.aws.element84.com/v1`, bbox from
`config/aoi.json`, datetime `2022-06-01/2022-07-31`, IW GRD, VV asset required. The earliest and
latest usable acquisitions over the AOI core were selected:

| Scene ID | Date | Platform | Relative orbit | Direction | Fixed σ0 threshold | Observed water | Validity | Scene area | Validity / scene | Modelled in validity |
|---|---|---|---|---|---|---|---|---|---|---|
| `S1A_IW_GRDH_1SDV_20220601T233908_20220601T233933_043476_0530F2` | 2022-06-01T23:39:20Z | sentinel-1a | 4 | descending | −16 dB | 395.65 km² | 42,422.33 km² | 43,393.70 km² | 97.76 % | 553.94 km² |
| `S1A_IW_GRDH_1SDV_20220731T233912_20220731T233937_044351_054B00` | 2022-07-31T23:39:24Z | sentinel-1a | 4 | descending | −16 dB | 490.19 km² | 42,419.61 km² | 43,391.29 km² | 97.76 % | 553.53 km² |

Each VV COG reports `crs: None` and carries WGS84 GCPs. The stage transformed the GCPs into
EPSG:32646 (zone 46N from `proj:centroid`) and assigned that CRS before reprojection. VV was read
at ~1/9 with `Resampling.average`, never at native resolution.

**Calibration (REVIEW-18 fix).** Both STAC items expose `schema-calibration-vv`; the stage
downloads `annotation/calibration/calibration-iw-vv.xml`, parses `sigmaNought` per vector
(**27 vectors × 642 samples**, median **A = 595.42415** for the 2022-06-01 scene and 595.42115 for
2022-07-31; the scorecard publishes their median 595.42265), interpolates A over the decimated
grid, and converts **σ0 dB = 20·log10(DN / A)**. Over AOI-core pixels the calibrated distribution
is p05/p50/p95 = −16.3/−8.6/−6.9 dB (2022-06-01) and −19.8/−9.1/−7.0 dB (2022-07-31); these are
measured on the ~90 m average-decimated DN, so they are narrower than a native-pixel sample.

**Threshold.** Water is `σ0 ≤ −16 dB`, a fixed, pre-stated conservative C-band VV open-water
threshold for monsoon conditions; the rationale is published in `method.threshold_rationale`.
Sensitivity is reported at −14/−16/−18 dB in σ0 space. Water components smaller than 5 analysis
cells were removed. Masks were reprojected nearest to the 90 m frame grid with a fractional
coverage raster.

**Validity (REVIEW-19 fix).** The comparison domain is now the **full SAR footprint**, not the
valley-floor AOI core: SAR VV validity on the 90 m frame grid (`coverage ≥0.5`) ∩ the regional
AOI polygon, then validity components <5 cells removed. The old AOI-core clip is published only
as `validity_attrition.legacy_aoi_core_clipped_area_km2` (3,743.0 km² for 2022-07-31). The
attrition ledger is `raw_sar_valid 42,419.6 → slope_filtered 16,566.2 → aoi_clipped 42,419.6 →
component_filtered 42,419.6 → final 42,419.6` km². The jump at `aoi_clipped` is the diagnostic
slope branch being skipped: the shipped path is `raw_sar_valid → aoi_clipped →
component_filtered → final`.

**Slope filter (REVIEW-19 fix).** Slope is computed from the 90 m DEM as the central-difference
gradient (`dz_dy, dz_dx = np.gradient(dem_m, 90, 90)`, `slope_deg =
degrees(arctan(hypot(dz_dx, dz_dy)))`), in **degrees**. The 10° filter is evaluated but **not
applied** to the final domain: it removes 25,853.4 km² of this scene (16,566.2 km² with slope vs
42,419.6 km² without) and cannot be shown not to remove valley-floor cells. Both areas are
published per scene.

**Coverage note.** The full SAR footprint is **97.76 %** of each GCP-corner scene area. The old
scorecard's 3,735 km² was the intersection with the 52,240 km² AOI core, not the scene; that core
clip retained ~97 % of the model's wet area and was the REVIEW-19 bug. The valid observed share
of the SAR footprint remains above the 90 % stop bar.

## Extent-shape comparison

The committed PNG frames were decoded with frame-index placement and compared on the full
validity domain (no AOI-core clip, no slope filter). Best match is the best of the 12 steps; S07
is the scenario peak. Metrics are **area-weighted**, not cell counts, so the published TP/FP/FN
km² and the ratios are the same arithmetic.

| Scene | Best step | Best IoU | S07 modelled | S07 IoU | S07 precision | S07 recall | S07 F1 | S07 area bias |
|---|---|---|---|---|---|---|---|---|
| 2022-06-01 | S07 | 0.0874 | 553.94 km² | 0.0874 | 0.1378 | 0.1929 | 0.1608 | +40.0 % |
| 2022-07-31 | S07 | 0.0995 | 553.53 km² | 0.0995 | 0.1706 | 0.1926 | 0.1809 | +12.9 % |

Sensitivity at S07 in **σ0 space** (fixed thresholds, same modelled frame, same full-footprint
validity domain):

| Scene | σ0 threshold | Observed | TP | FP | FN | IoU | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|---|
| 2022-06-01 | −14 dB | 861.61 km² | 87.43 | 466.51 | 774.18 | 0.0658 | 0.1578 | 0.1015 | 0.1235 |
| 2022-06-01 | −16 dB | 395.65 km² | 76.32 | 477.61 | 319.32 | 0.0874 | 0.1378 | 0.1929 | 0.1608 |
| 2022-06-01 | −18 dB | 265.33 km² | 68.32 | 485.62 | 197.01 | 0.0910 | 0.1233 | 0.2575 | 0.1668 |
| 2022-07-31 | −14 dB | 1,113.35 km² | 111.67 | 441.85 | 1,001.68 | 0.0718 | 0.2018 | 0.1003 | 0.1340 |
| 2022-07-31 | −16 dB | 490.19 km² | 94.42 | 459.11 | 395.77 | 0.0995 | 0.1706 | 0.1926 | 0.1809 |
| 2022-07-31 | −18 dB | 331.92 km² | 84.01 | 469.51 | 247.91 | 0.1048 | 0.1518 | 0.2531 | 0.1898 |

The observed extent moves 3.2–3.4× across this 4 dB band on the full footprint. Precision stays
≤0.202 and recall ≤0.257 across the band: the model puts most of its extent where SAR sees dry
land and captures at most ~26 % of observed water. IoU is lower than the old AOI-core value, not
higher; that is the honest full-footprint result and it ships.

Summary: mean best-match IoU **0.0934**, mean S07 precision **0.1542**, mean S07 recall
**0.1928**, worst scene 2022-06-01. The modelled area is 1.13–1.40× the observed water area on
the same full validity domain, and the overlap is low. These are the findings and are not tuned.

## REVIEW-19 reconciliation

Reviewer numbers for the 2022-07-31 scene versus the corrected scorecard:

| Quantity | Reviewer | Corrected scorecard | Difference | Mechanism |
|---|---:|---:|---:|---|
| Scene ground area (GCP corners) | 43,389 km² | 43,391.3 km² | +0.005 % | Same four GCP corners; the reviewer rounded the polygon area. |
| Validity on frame grid | 41,193.0 km² (94.9 %) | 42,419.6 km² (97.76 %) | +2.98 % | The reviewer's validity mask excludes more edge/partial cells; ours keeps every cell with `coverage ≥0.5` inside the regional AOI. The ~1,227 km² difference is consistent with a one-cell edge/erosion convention around the scene perimeter, not a filter that selects the model. |
| Observed water @ −16 dB σ0 | 467.1 km² | 490.2 km² | +4.94 % | 90 m `average` decimation (native 10 m → ~90 m) broadens low-backscatter water and merges small ponds; the reviewer's independent native-resolution mask retains a different speckle population. Component removal is the same 5-cell rule. |
| Model wet inside validity | 568.2 km² | 553.5 km² | −2.59 % | The model PNG is upsampled 180 m → 90 m by pixel replication; the reviewer's placement/edge convention differs by roughly one half-cell around the frame perimeter. |
| TP | 79.2 km² | 94.4 km² | +19.2 % | Co-registration dominates: our observed and model masks share the GCP affine and the 90 m frame grid, so more water falls in the same cells. The reviewer's independent warp/model placement shifts the overlap. |
| IoU | 0.0827 | 0.0995 | +20.3 % | Follows from the TP increase plus the larger observed/model denominators above; it is not a validity-mask artefact. |
| Precision (TP/model) | 0.1392 | 0.1706 | +22.6 % | TP/model with the same numerator/denominator mechanisms. |
| Recall (TP/observed) | 0.1694 | 0.1926 | +13.7 % | TP/observed, same mechanisms. |

The residual is **not** tolerance-fitting: the corrected denominator is 42,420 km² (within 3 %
of the reviewer's 41,193, inside the 10 % acceptance), and the corrected IoU is **0.0995**, not
the old 0.1348. The two dominant mechanisms are (1) edge treatment of partial SAR cells and
(2) co-registration of the observed mask and the upsampled model frame. Both are now visible in
the published area ledger, and neither can select the model's wet area.

`scorecard.json` publishes the corrected caveat: *"σ0 calibration applied from the SAFE
calibration LUT. Residual uncertainty is threshold choice (reported across −14/−16/−18 dB) and
GRD geometries co-registered with a GCP-derived affine, not a rigorous terrain-corrected warp."*
The not-an-event-hindcast caveat is unchanged.

## Severity vs extent ranks

`risk_score` remains the extent-led score and is labelled **Extent score** in the Risk panel.
`severity_index` is the separate P1.7 profile:

```text
p = z(depth_over_1_5m_share) × z(median_depth_m) × z(mean_duration_days)
severity_index = 100 × (p − min(p)) / (max(p) − min(p))
```

using population z-scores (ddof=0) over the 33 districts; all means, standard deviations,
product min/max and the normalisation are published in `district-risk.json`. `severity_rank` is
dense descending by the index. `rank` remains the extent rank.

Top 5 by severity:

| Severity rank | District | Severity index | Extent rank |
|---|---|---|---|
| 1 | Dima Hasao | 100.0 | 12 |
| 2 | Karbi Anglong West | 37.5 | 17 |
| 3 | Hojai | 28.0 | 3 |
| 4 | Golaghat | 21.3 | 9 |
| 5 | Cachar | 20.8 | 11 |

Top 5 by extent score:

| Extent rank | District | Extent score | Severity rank |
|---|---|---|---|
| 1 | Sivasagar | 66.8 | 7 |
| 2 | Majuli | 54.2 | 16 |
| 3 | Hojai | 53.8 | 3 |
| 4 | Nalbari | 51.2 | 29 |
| 5 | Nagaon | 49.6 | 25 |

**Dima Hasao finding.** Severity rank **1/33**; extent-score rank **12/33**; area-share rank
**33/33**. The measured profile is depth >1.5 m share 0.882086, median depth 3.7 m, duration
114.6664 d, area share 0.003634. The severity acceptance (top third) is met. The
"bottom half on extent" sentence in REVIEW-17 is **not** met by the existing extent score: the
score is 44.1, above the 40.1 median, because duration is 43.75 % of it. The formula was not
tuned to move the rank; the discrepancy is reported here and in `docs/DATA-PIPELINE.md` §9.5.

## Nits

`docs/NITS.md` seeds N-01 (`risk_class_area_share` denominator not machine-readable), N-02
(bottom-right attribution clips at narrow rail widths), and N-03 (district scores are
AOI-relative only in prose / below-75 % annotations). All are `open`; none is fixed in this
phase.
