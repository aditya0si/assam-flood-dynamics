# Phase 1a report — Sentinel-1 validation, severity split, nit register

Date: 2026-10-21. Scope: REVIEW-17 P1.1, P1.2, P1.7 and `docs/NITS.md`. No DEM swap, no frame
regeneration, no change to `public/data/flood/**` or `public/data/scenario.json`.

## Sentinel-1 acquisitions

The STAC search was `sentinel-1-grd` on `https://earth-search.aws.element84.com/v1`, bbox from
`config/aoi.json`, datetime `2022-06-01/2022-07-31`, IW GRD, VV asset required. The earliest and
latest usable acquisitions over the AOI core were selected:

| Scene ID | Date | Platform | Relative orbit | Direction | Fixed σ0 threshold | Observed water | Observed fraction | Validity area | Modelled in validity |
|---|---|---|---|---|---|---|---|---|---|
| `S1A_IW_GRDH_1SDV_20220601T233908_20220601T233933_043476_0530F2` | 2022-06-01T23:39:20Z | sentinel-1a | 4 | descending | −16 dB | 187.64 km² | 5.02 % of validity | 3,737.44 km² | 552.29 km² |
| `S1A_IW_GRDH_1SDV_20220731T233912_20220731T233937_044351_054B00` | 2022-07-31T23:39:24Z | sentinel-1a | 4 | descending | −16 dB | 240.05 km² | 6.43 % of validity | 3,735.09 km² | 551.87 km² |

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
cells and DEM slope >10° were removed. Masks were reprojected nearest to the 90 m frame grid with
a fractional coverage raster; `validity_area_km2` is that comparison domain and
`modelled_in_validity_km2` is the S07 model area inside it.

**Coverage note.** A single Sentinel-1 GRD slice covers about 7.3 % of the full 52,240 km² AOI
core. The valid observed share of each slice's AOI footprint is 98.3 %, above the 90 % stop bar;
the scorecard is therefore a comparison over the observed footprint, not over the full AOI. The
full-AOI footprint share is recorded in the cache metadata and stage log.

## Extent-shape comparison

The committed PNG frames were decoded with frame-index placement and compared on the observed
domain (coverage ≥0.5, AOI core, slope ≤10°). Best match is the best of the 12 steps; S07 is the
scenario peak. Sensitivity is at S07.

| Scene | Best step | Best IoU | S07 modelled | S07 IoU | S07 precision | S07 recall | S07 F1 | S07 area bias |
|---|---|---|---|---|---|---|---|---|
| 2022-06-01 | S09 | 0.1189 | 552.29 km² | 0.1145 | 0.1376 | 0.4050 | 0.2054 | +194.3 % |
| 2022-07-31 | S06 | 0.1352 | 551.87 km² | 0.1348 | 0.1704 | 0.3918 | 0.2375 | +129.9 % |

Sensitivity at S07 in **σ0 space** (fixed thresholds, same modelled frame, same validity domain):

| Scene | σ0 threshold | Observed | IoU | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| 2022-06-01 | −14 dB | 223.53 km² | 0.1264 | 0.1577 | 0.3896 | 0.2245 |
| 2022-06-01 | −16 dB | 187.64 km² | 0.1145 | 0.1376 | 0.4050 | 0.2054 |
| 2022-06-01 | −18 dB | 165.14 km² | 0.1048 | 0.1232 | 0.4120 | 0.1897 |
| 2022-07-31 | −14 dB | 316.91 km² | 0.1469 | 0.2016 | 0.3511 | 0.2561 |
| 2022-07-31 | −16 dB | 240.05 km² | 0.1348 | 0.1704 | 0.3918 | 0.2375 |
| 2022-07-31 | −18 dB | 207.73 km² | 0.1238 | 0.1516 | 0.4028 | 0.2203 |

The observed extent moves 1.35–1.53× across this 4 dB band on the 90 m averaged grid. Precision
stays ≤0.202 and recall ≤0.412 across the band: the model puts most of its extent where SAR sees
dry land and captures at most ~41 % of observed water. The sign of the threshold effect is
consistent with REVIEW-18, and the smaller spread is a property of thresholding the ~90 m
average-decimated DN rather than native pixels; both are published rather than tuned.

Summary: mean best-match IoU 0.1270, mean S07 precision 0.1540, mean S07 recall 0.3984, worst
scene 2022-06-01. The modelled area is roughly 2–3× the observed water area on the same validity
domain, and the overlap is low. These are the findings and are not tuned.

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
