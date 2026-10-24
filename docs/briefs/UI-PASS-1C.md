# UI pass 1C — close the gaps left by 1B

Your pass landed on `ui/pass-1` (commit `2444418`, plus docs) and **CI is green**: `pipeline pytest`
pass, `verify:m0` Playwright **pass 18 m 24 s**, GitGuardian pass, PR #1 `MERGEABLE`. The design work
is accepted. This brief is only about the three things you did not finish.

## 1. Three acceptance assertions are missing

The brief asked for six. You delivered three (district rows in view, formula not clipped, onset copy).
Add the missing three to `tests/e2e/` — real assertions, not restatements of existing ones:

- **Map owns the screen.** At 1440×900, `.maplibregl-map` height ≥ 60 vh with the right and bottom
  rails in their default state, and ≥ 75 vh after collapsing both (`data-rail-size="collapsed"`).
  Measure with `getBoundingClientRect().height / innerHeight`, not CSS parsing.
- **Exactly one warning.** `page.getByText('NOT A FORECAST')` must have **count 1** across the whole
  DOM. Today's tests only assert `.first()` is visible, which would pass with six copies — the exact
  defect this pass was supposed to remove.
- **Legend matches map.** Assert the rendered legend swatch colours equal the values exported by
  `DEPTH_PRESENTATION` in `src/map/depthPalette.ts`, read from the DOM via
  `getComputedStyle(el).backgroundColor` and compared as `rgb(...)`. Do not hard-code a second hex
  list in the test — import the constant or assert against the module's exported values.

## 2. CI runtime regressed 2.5× and you must say why

`verify:m0` was ~7 minutes before this pass and is **18 m 24 s** now, on an unchanged suite plus your
new test. That is a real regression even though it is green. Find it and fix it:

- Look first at anything you added that every test traverses: settle helpers, `waitForTimeout`,
  transitions/animations that Playwright must wait out, or a longer `POLL_TIMEOUT`.
- `test.setTimeout(180_000)` at `m0.spec.ts:146` is pre-existing, not your regression — do not "fix"
  the runtime by raising timeouts.
- Report the mechanism (e.g. "a 700 ms CSS transition on the rail makes every visibility assertion
  wait it out; capped at 120 ms under `prefers-reduced-motion`"), not just the new number. CI on the
  next push is the measurement.

## 3. The pass report is missing

`docs/UI-PASS-1.md` does not exist — you wrote `docs/briefs/UI-PASS-1B.md` instead. Write the
deliverable the brief asked for:

- before/after for each of the seven measured faults (map not primary; legend contradicting the map;
  six warnings; one-volume typography; amber doing three jobs; clipping; flat charts);
- the token table you actually shipped (hex values, type scale, radii);
- a "what I deliberately did not change" list, with reasons.

## Constraints (unchanged)

- UI and tests only: `src/**`, `tests/e2e/**`, `docs/**`. **No** `public/data/**`, `pipeline/**`,
  `scripts/check-data.mjs`, `scripts/check-honesty.mjs`.
- Keep every honesty affordance: the single `NOT A FORECAST`, the four class badges, per-panel data
  ages, `Extent score` vs `Severity rank`, the validation caveats.
- Keep the test hooks: `data-ready`, `__baanh.renderSeq`, `data-tile-health`, `window.__baanh.*`.
- Commit to `ui/pass-1` and push. **Do not merge, do not touch `main`.**
- Local Playwright cannot fork on this Windows host (`spawn EPERM`) — do not claim browser results you
  did not obtain; state that CI is the measurement.

## Done means

Three new assertions present and meaningful, a named mechanism for the runtime regression with a fix
committed, `docs/UI-PASS-1.md` written, gates still green locally (`check-data` 38/38, `check-budget`,
`check-honesty` + `--self-test`, unit 14, pipeline pytest 29, `build:sandbox`), branch pushed, and a
short report of what changed and what you could not verify.
