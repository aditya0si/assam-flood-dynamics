# Review 13 — 5/10: the E2E layer is fighting the host, not the product

Reviewer run #2 on a quiet host (all my static servers killed): **5 passed, 5 failed, 11.9 min**.
Static layer remains fully green (check-data 24/24, budget PASS, honesty PASS + self-test, unit 14/14).

Every remaining failure is a **test-design** defect. None of them is a product defect, and each has a
specific mechanism:

| # | Failure | Evidence | Cause |
|---|---|---|---|
| 1 | `fallback` | `app load must leave room for the 8 s offline budget. Expected > 0, Received -6182` | The test subtracts load time from an 8 s budget; on this host the map takes ~14 s to become ready, so the precondition fails before the offline assertion ever runs. The budget must be per-assertion (`expect.poll`), not a global deadline. |
| 2 | A6 painted share | `measured S00 55.47% < S04 11.43% < S07 27.97%` | S00's baseline is contaminated: the first screenshot pair is taken while imagery tiles are still streaming, so the "flood off" frame contains newly arrived basemap. The diff then measures tile loading, not flood. |
| 3 | layer controls | `locator.uncheck: Timeout 10000ms exceeded` | B6 made the input `1×1, opacity 0`. Playwright treats that as **not visible**, so `uncheck()` without `force` can never pass. For a deliberately hidden input the test must `getByLabel(...).click()` or `setChecked(..., { force: true })`. |
| 4 | provenance | `Timeout 10000ms exceeded while waiting on the predicate` | Same class: a `expect.poll` predicate with a 10 s budget on a host where a panel switch plus re-render takes longer. |
| 5 | R6 hero camera | fails alongside #2 | It reuses the same painted-share measurement, so it inherits the contaminated baseline. |

## B7 scope — test design only, no product changes

1. **Settle before measuring.** For A6 and R6: set the base mode to **hillshade** (committed raster,
   no network) before the measurement, wait for `__baanh.tileHealth` to stop being `loading` **and**
   for two consecutive animation frames with identical `data-frame-file`, then screenshot. Add a
   guard: if the measured S00 share exceeds 20 %, fail with a diagnostic that says "baseline not
   settled" rather than reporting nonsense growth.
2. **Per-assertion budgets.** Replace the global "8 s offline budget" arithmetic with
   `expect.poll(..., { timeout: 30_000 })` for the `offline` state, and log — do not fail — the load
   duration. Same for the provenance predicate and any other 10 s poll.
3. **Hidden input interaction.** Use `page.getByLabel('Show Scenario flood extent').click()` (or
   `setChecked(false, { force: true })`) since the input is intentionally invisible; assert the
   resulting `__baanh.layers.visible` state rather than the element's checked property.
4. Re-run the static gates and `npx playwright test --list`; commit. Do not touch `public/data`,
   `pipeline/`, or any product behaviour.

## After B7 (reviewer)

- `verify:m0:sandbox` → 10/10 ⇒ publish (REVIEW-10 sequence).
- If a residual failure is purely a host-timeout (no assertion), publish with the E2E suite delegated
  to Linux CI, and say exactly that in `M0-REPORT.md` — no claim of a local 10/10.
