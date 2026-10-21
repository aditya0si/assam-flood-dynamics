# Review 15 — Phase 0: make the risk numbers honest before adding new data

Source: `docs/panel/08-claims-verified.md`. Two confirmed defects, both fixable without new data.
**No new datasets in this phase.** Everything here can be verified from committed artifacts.

## P0.1 — Remove the inert depth weight (the important one)

`p90_peak_depth_m` is 3.7 for all 33 districts because the bathtub convention caps depth at the
stage. The UI publishes `45 % area + 35 % duration + 20 % depth`; the depth term is a constant.

Do this:

1. Score on **area share + duration only**, re-normalised: `area 0.5625`, `duration 0.4375`
   (45/35 ÷ 80). Keep the same per-driver saturation (`area_share_saturation: 0.6`,
   `duration_saturation_days: 90`) and the same class thresholds unless the data forces a change —
   if it does, say so with the before/after distribution.
2. Write the applied weights into `risk/district-risk.json` → `weights` (must equal what the code
   actually multiplies) and add `weights_version`.
3. Update the UI formula text and the methodology panel: **two drivers**, plus one sentence stating
   that bathtub depth saturates at the stage and is therefore reported but not scored.
4. Acceptance: the published weights equal the applied weights; ranking order is unchanged (a
   constant term cannot reorder) or every change is explained; `check-data` rejects a district-risk
   file whose `weights` do not sum to 1.0.

## P0.2 — Add a depth metric that actually discriminates (reported, not scored)

Add per district, computed in the pipeline from the peak frame depth raster:

- `depth_over_1_5m_share` — share of the district's **wet** cells with depth > 1.5 m at peak;
- `median_depth_m` — median depth over the district's wet cells at peak.

Surface both in the Risk panel as context bars next to the score. Acceptance: `depth_over_1_5m_share`
has **more than one distinct value** across the 33 districts, and the panel renders it; a test fails
if the field is constant.

## P0.3 — Coverage caveat

In `RiskPanel`, when `valid_area_share < 0.75`, show a `coverage 47 %` badge next to the score and
annotate the row (`Scored on the AOI-covered share only`). Acceptance: Playwright asserts the badge
exists for the lowest-coverage district and that its score row carries the annotation.

## P0.4 — Answer the class-width question from artifacts

Write into `risk/district-risk.json` (or a sibling block) a `risk_class_area_share` computed over
**wet-at-peak cells**: share per class (`low`, `moderate`, `high`, `very_high`). Document the
denominator in the schema. Acceptance: the four shares sum to 1.0 ± 0.01, and `check-data` asserts
it. This settles the "79 % in one class" claim with a number instead of an argument.

## P0.5 — Docs and gates

- `DATA-PIPELINE.md` §9 (risk scoring) and `ARCHITECTURE.md` §3 P0-06 / §11 updated to match;
  mark edits `<!-- amended: PHASE-0 -->`.
- `check-data.mjs` gains the three new assertions (weights sum, depth-share variance, class-share sum).
- `verify:m0` must stay green; Playwright test count unchanged except the new coverage badge case.

## P0.6 — Publish

Run `npm run build:sandbox`, the static gates and `npm run test:unit`, commit, push. CI must go
green on Linux and Pages must redeploy. Report the commit SHA, the new district table (top 5), the
class-share numbers, and the distinct-value count for `depth_over_1_5m_share`.

## Do not

- Do not regenerate flood frames or change the scenario.
- Do not change the ranking to make it look better; a constant term cannot reorder, so any reorder is
  a bug.
- Do not hand-edit `public/data/` — the pipeline produces it.
- Do not claim browser results you cannot run; the reviewer runs Playwright.
