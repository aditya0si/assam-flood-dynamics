# Review 11 — B4 result: camera improved but R6 still unmet; three tests need honest calibration

Reviewer: Hermes. Target: B4, commit `65d0f21`. I ran `npm run verify:m0:sandbox` myself (the
builder's sandbox cannot launch Chromium; mine can). Result: **6 passed, 4 failed in 11.1 min**.
Static gates all green: check-data 24/24, check-budget PASS, check-honesty PASS + self-test, unit 13/13.

## The four failures, with numbers

| # | Test | Observed | Verdict |
|---|---|---|---|
| 1 | `fallback.spec` blocked-tile | `data-tile-health` = **`degraded`**, expected `offline` | Real gap: with both hosts blocked the machine settles on `degraded` inside the test window. My manual CDP-block test reached `offline` after ~12 s, so the transition exists but is slower than the assertion. |
| 2 | `m0-A6` flood surface changes | canvas diff **S00→S04 = 2.47 %**, S00→S07 = 6.35 % | The threshold is too strict for real growth: the first third of the flood is thin shallow margins. Test must assert *monotone growth*, not a fixed early delta. |
| 3 | layer controls | `locator.click` **timeout 10000 ms** | Real bug: one control is not clickable after the B4 dock rework (likely the range input needs `fill`/keyboard, or an overlay intercepts). |
| 4 | **R6 share** | **4.50 %** vs ≥6 % required | Camera improved (5.28 % → 4.50 % is worse, in fact) — fitting the peak extent does not help because the flood is a long thin diagonal band: its bounding box is mostly dry. |

## R6 is a geometry problem, and my metric was naive

The peak flood is ~480 km long and ~20–40 km wide. Any bbox fit of that shape includes large dry
triangles, so the painted share of the frame stays low no matter how the fit is padded. The fix is
not a bigger zoom on the belt — it is **choosing a hero reach**: frame the most-affected part of the
valley (top-ranked district), where the band fills the viewport, and let the user zoom out to the
belt.

So R6 changes shape:

- default camera = the **top-ranked district's reach** (Sivasagar), mid-zoom, pitch 42°;
- the R6 assertion becomes: at the default camera the S07 flood covers **≥ 10 % of the map viewport**
  (not of the full screenshot), measured from the map element's box, plus the existing 62–68 % map
  height band. 10 % is a calibration of the hero framing, not a physical constant, and it is written
  down as such.

## B5 scope (app fixes + publish prep)

1. **Camera**: hero reach at the top-ranked district. Expose `__baanh.camera = {center, zoom, pitch}`
   so the test asserts the camera, not just pixels.
2. **fallback**: make the both-hosts-blocked path reach `offline` deterministically within **8 s**
   (the state machine already has the inputs: both sources have confirmed errors), and keep
   `degraded` as the honest intermediate. Assert the sequence `degraded → offline`, then playback.
3. **A6**: assert monotone painted share `S00 < S04 < S07` and `S07 − S00 ≥ 3` percentage points on
   the map box; keep the measured values in the failure message.
4. **layer controls**: fix the unclickable control; the test may use `fill()` for the range input and
   `Space` to toggle checkboxes, but the control itself must be reachable by keyboard.
5. **R6**: hero-reach camera + viewport-relative assertion (≥10 %).
6. **Base path** for publishing (see `REVIEW-10`): `/assam-flood-dynamics/` for build and preview,
   `/` for dev, overridable via `BAANH_BASE`; update tests/preview URLs and README links.
7. Commit, then run `npm run verify:m0:sandbox` and report the exact pass/fail list. Do **not** claim
   Playwright results you could not execute — I will run them.

## Acceptance (mine)

`npm run verify:m0:sandbox` → **10/10**; then clean-clone `npm ci && npm run build` → exit 0; then I
publish and verify the live Pages URL by content-type, not by status code.
