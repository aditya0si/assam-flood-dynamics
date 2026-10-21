# Review 12 — B5 result: 7/10; three precise failures left

Reviewer run: `npm run verify:m0:sandbox` → **7 passed, 3 failed (9.9 min)**, EXIT=1.
Static gates green (check-data 24/24, budget PASS, honesty PASS + self-test, unit 14/14).

| # | Test | Error | Cause |
|---|---|---|---|
| 1 | `fallback.spec` blocked-tile | expected `offline`, received **`degraded`** at 12.8 s | Either the test's route patterns do not actually block the DEM host (so only imagery fails, and `degraded` is *correct* under the "both must fail" rule), or the machine needs a longer window. Find out which before changing either. |
| 2 | `m0` A6 painted share | **`page.waitForTimeout` — test timeout 75 s exceeded** (line 154) | Not an assertion failure: the test spends its budget waiting (map init ~10 s per navigation, repeated screenshots). Raise this test's timeout and cut redundant waits. |
| 3 | `R6` hero camera | **`locator.uncheck` 10 s timeout** (line 343) | The flood checkbox still is not actionable for `uncheck()`: the element is likely re-rendered or visually unstable when the layer toggles, so Playwright's stability check never settles. |

## B6 scope (narrow — do not refactor anything else)

1. **Fallback**: log which host(s) the test actually blocks and what each source's state is at
   assertion time. If both are blocked and one source still has no confirmed error, fix the state
   machine so a blocked request counts as a confirmed error for that source within 2 s. If the test
   only blocks one host, fix the test to block both (imagery + `elevation-tiles-prod`). Then
   `offline` must be reached **≤8 s** and playback must still work.
2. **A6**: give this test its own timeout (`test.setTimeout(180_000)`), reuse one page for all three
   steps instead of re-navigating, and keep the `S00 < S04 < S07` + `≥3` point assertions intact.
3. **R6 checkbox**: make the control stable — the real `<input type="checkbox">` visually hidden but
   focusable under a styled track inside a `<label>`, with no layout change on toggle; the test must
   pass `uncheck()` **without `force`**.
4. Commit, then re-run `npm run build:sandbox` + the static gates and report. Do not claim Playwright
   results — the reviewer runs them.

## Acceptance (mine)

`verify:m0:sandbox` → **10/10**, clean-clone `npm ci && npm run build` → exit 0, then publish to
`aditya0si/assam-flood-dynamics` and verify the live URL by content type.
