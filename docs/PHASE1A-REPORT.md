# Phase 1a report — Sentinel-1 validation, severity split, nit register

Date: 2026-10-21. Scope: REVIEW-17 P1.1, P1.2, P1.7 and `docs/NITS.md`. No DEM swap, no frame
regeneration, no change to `public/data/flood/**` or `public/data/scenario.json`.

## Sentinel-1 acquisitions

The STAC search was `sentinel-1-grd` on `https://earth-search.aws.element84.com/v1`, bbox from
`config/aoi.json`, datetime `2022-06-01/2022-07-31`, IW GRD, VV asset required. The earliest and
latest usable acquisitions over the AOI core were selected:

| Scene ID | Date | Platform | Relative orbit | Direction | Otsu threshold | Observed water | Observed fraction |
|---|---|---|---|---|---|---|---|
| `S1A_IW_GRDH_1SDV_20220601T233908_20220601T233933_043476_0530F2` | 2022-06-01T23:39:20Z | sentinel-1a | 4 | descending | 20.035 dB | 202.66 km² | 5.42 % of observed AOI |
| `S1A_IW_GRDH_1SDV_20220731T233912_20220731T233937_044351_054B00` | 2022-07-31T23:39:24Z | sentinel-1a | 4 | descending | 19.971 dB | 262.33 km² | 7.02 % of observed AOI |

Each VV COG reports `crs: None` and carries WGS84 GCPs. The stage transformed the GCPs into
EPSG:32646 (zone 46N from `proj:centroid`) and assigned that CRS before reprojection. VV was read
at ~1/9 with `Resampling.average`, never at native resolution. Otsu was computed on
`10·log10(DN)` over AOI core pixels only; water components smaller than 5 analysis cells and DEM
slope >10° were removed. Masks were reprojected nearest to the 90 m frame grid with a fractional
coverage raster.

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
| 2022-06-01 | S09 | 0.1234 | 552.29 km² | 0.1203 | 0.1468 | 0.4000 | 0.2147 | +172.5 % |
| 2022-07-31 | S07 | 0.1400 | 551.87 km² | 0.1400 | 0.1812 | 0.3811 | 0.2456 | +110.4 % |

Sensitivity at S07 (observed mask at Otsu ±2 dB, same modelled frame, same domain):

| Scene | Otsu−2 dB IoU / P / R | Otsu IoU / P / R | Otsu+2 dB IoU / P / R |
|---|---|---|---|
| 2022-06-01 | 0.0999 / 0.1165 / 0.4122 | 0.1203 / 0.1468 / 0.4000 | 0.1826 / 0.2797 / 0.3448 |
| 2022-07-31 | 0.1182 / 0.1429 / 0.4061 | 0.1400 / 0.1812 / 0.3811 | 0.1808 / 0.3570 / 0.2680 |

Summary: mean best-match IoU 0.1317, mean S07 precision 0.1640, mean S07 recall 0.3906, worst
scene 2022-06-01. The modelled area is roughly 2× the observed water area on the same domain,
and the overlap is low. These are the findings and are not tuned.

The two required caveats ship verbatim in `scorecard.json`: this is an extent-shape comparison,
not an event hindcast, and absolute SAR calibration was unavailable; masks use an Otsu threshold
with a ±2 dB band.

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
