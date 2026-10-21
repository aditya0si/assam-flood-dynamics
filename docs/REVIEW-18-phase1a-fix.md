# Review 18 — Phase 1a: model numbers verified, one blocking method correction

Commit `e3e67ff`, CI `39656475815` **success** (7 m 17 s), Pages `39656475680` success.
Reviewer recomputed the Sentinel-1 comparison from scratch (separate code, direct S3 COG read,
GCP georeferencing, independent Otsu) rather than trusting `docs/PHASE1A-REPORT.md`.

## Verified correct

| Item | Reviewer measurement |
|---|---|
| Model area inside SAR validity | **568.16 km²** vs scorecard `551.87 km²` — 2.9 % apart, same quantity. (An earlier reviewer estimate of 1,413 km² used the scene's *bbox*, not the SAR validity footprint — that estimate was wrong, not the scorecard.) |
| Geometry of the SAR scene | GCP affine gives a rotated footprint whose bbox `93.05–95.87 °E, 24.96–26.88 °N` matches STAC `proj:bbox`; georeferencing is sound |
| Severity split | `severity_index` 32 distinct values, formula + z-stats + normalisation published in the JSON; **Dima Hasao severity #1 (100.0) vs extent #12 (44.09)** — top third on severity, and the review's "bottom half on extent" target **not** met, reported rather than tuned |
| Gates | `check-data` **30/30**, unit 14/14, pipeline pytest 17 passed, budget and honesty pass |
| Live | Validation tab renders `IoU 0.1`, Otsu, `OBSERVED WATER`, and the *not an event hindcast* caveat; zero console errors |

## Blocking: the caveat is factually false

The scorecard publishes:

> *"Absolute SAR calibration was unavailable; masks use an Otsu threshold with a ±2 dB band."*

Measured: the STAC item exposes **`schema-calibration-vv`** — a 1.0 MB calibration LUT, 27 vectors ×
642 samples, `sigmaNought` median **A = 595.42**, reachable anonymously
(`s3://sentinel-s1-l1c/…/annotation/calibration/calibration-iw-vv.xml`). Calibration was available
and was not used.

With the LUT applied, σ0 p05/p50/p95 = **−13.2 / −8.3 / −3.4 dB**, which is sane VV land. The
scorecard's Otsu (19.97 dB in uncalibrated 10·log10 DN) corresponds to roughly **−15.5 dB σ0** — a
defensible water threshold chosen by luck rather than by calibration, then documented as impossible.

## Blocking: the metric is threshold-dominated, and the sensitivity was measured in the wrong space

Fixed σ0 thresholds, same scene, reviewer computation:

| σ0 threshold | observed | IoU | precision | recall |
|---|---|---|---|---|
| −12 dB | 3,534.9 km² | 0.0375 | 0.042 | 0.261 |
| −14 dB | 1,002.6 km² | 0.0639 | 0.094 | 0.166 |
| −15.5 dB | 529.8 km² | 0.0806 | 0.155 | 0.144 |
| −16 dB | 467.1 km² | 0.0827 | 0.169 | 0.139 |
| −18 dB | 312.9 km² | 0.0865 | 0.224 | 0.123 |
| −20 dB | 215.6 km² | 0.0883 | 0.295 | 0.112 |

Observed extent moves **16×** across an 8 dB band, and the scorecard's ±2 dB band was applied to an
uncalibrated scale where ±2 dB has no physical meaning. The published IoU is therefore dominated by
threshold choice, and precision/recall asymmetry (P ≤ 0.30, R ≤ 0.26 across the whole band) is the
number that actually carries the finding: **the model puts most of its extent where SAR sees dry
land and captures at most a quarter of observed water.** That is a genuine, useful, unflattering
result — and it is stated far more weakly than the data allows.

## Phase 1a-fix (bounded, ~1 builder run)

1. Read `schema-calibration-vv`, parse `sigmaNought` per vector, convert to σ0 dB
   (`20·log10(DN/A)`), and record `method.calibration = {source, vectors, samples_per_vector, A_median}`.
2. Use a **fixed** threshold with a stated rationale (default **−16 dB** for VV water in monsoon
   conditions), and publish sensitivity across **−14 / −16 / −18 dB in σ0 space** with observed area
   and all metrics per threshold — not `±2 dB` around an uncalibrated Otsu.
3. Publish `validity_area_km2` and `modelled_in_validity_km2` per scene, so the denominator of every
   ratio is visible.
4. Replace the caveat with the truth: *"σ0 calibration applied from the SAFE calibration LUT.
   Residual uncertainty is threshold choice (reported across −14/−16/−18 dB) and GRD geometries
   co-registered with a GCP-derived affine, not a rigorous terrain-corrected warp."*
5. Add `check-data` assertions: `method.calibration` present with `A_median` non-null; sensitivity
   has exactly three σ0 thresholds; **no caveat string contains "calibration was unavailable"**.
6. Re-run both scenes, all gates, push, report the new per-scene table.

Keep everything else from Phase 1a — severity work, Validation tab, nit register — unchanged.
