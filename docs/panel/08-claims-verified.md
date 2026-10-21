# Panelist claims, verified by the reviewer

minimax-m3.1-flash (bounded re-run, 19.7 KB) produced three *internal* defect claims rather than
only data gaps. Measured against the committed data:

| Claim | Verdict | Evidence |
|---|---|---|
| **The depth term is inert** | **CONFIRMED** | `public/data/risk/district-risk.json`: `p90_peak_depth_m` is **3.7 for all 33 districts** — exactly the peak stage. In the bathtub convention `depth = stage − max(HAND,0)` is bounded by the stage, so at peak every district's p90 depth saturates. The published formula ("45 % area + 35 % duration + 20 % depth") therefore contains a constant: the 20 % depth weight discriminates nothing. |
| A single risk class covers ~79 % of the area | **NOT REPRODUCED** | Area-weighted shares of `risk/risk-zones.geojson` are `high 36.5 % · moderate 34.4 % · very_high 24.3 % · low 4.9 %`. No class reaches 79 %; `very_high + high = 60.8 %`. If the claim used a different denominator (e.g. only cells wet at peak), that denominator is not documented in the repo. |
| Hill districts are scored on low coverage | **PARTIALLY CONFIRMED** | `valid_area_share` ranges **0.466 → 1.0** (15 distinct values). Districts near the AOI edge have their score computed over as little as 46.6 % of their area, and that is not surfaced in the Risk panel. |
| Duration term | claim implied it is degenerate | **INCORRECT** — `mean_duration_days` varies 35.9 → 114.7 days across districts; that term is live. |

## What this changes

Two cheap, no-new-data fixes belong **before** Phase 1's data work, because they affect what the
current numbers mean:

1. **Depth term.** Either (a) replace `p90_peak_depth_m` with a discriminating metric — median
   depth, depth-duration integral, or the share of district area above 1.5 m — or (b) set the depth
   weight to 0 and re-normalise area/duration, documenting that bathtub depth saturates at the
   stage. Do not leave a formula in the UI that implies three drivers when one is constant.
   Acceptance: the three published weights sum to the weights actually applied, and the depth
   driver varies across districts (or is absent from the formula and the UI).
2. **Coverage caveat.** In `RiskPanel`, when `valid_area_share < 0.75`, show a coverage badge and
   the covered share next to the score; do not rank a district on <75 % coverage without saying so.
   Acceptance: Playwright asserts the badge appears for the lowest-coverage district and that its
   score is annotated.
3. **Re-check the class-width claim** with an explicit denominator in `flood-summary.json`
   (share of wet-at-peak cells per class), so the question is answerable from committed artifacts
   instead of re-litigated.

Cost: under a day, no new data. Both are honesty defects in the same family the REVIEW-01…14 trail
has been chasing: a number that looks like it carries information but does not.
