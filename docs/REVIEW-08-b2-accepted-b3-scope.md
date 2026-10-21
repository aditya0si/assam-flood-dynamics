# Review 08 — B2 accepted; one layout defect; B3 scope (tests, CI, publish)

Reviewer: Hermes. Target: B2, commit `f434c2c`. Probed in a dedicated Chromium session against the
rebuilt `dist/` under `/baanh/`.

## Accepted, with runtime evidence

| Item | Evidence |
|---|---|
| Risk panel | 33 rows; top 5 `Sivasagar 71.9 very_high`, `Majuli 61.9`, `Hojai 61.5`, `Nalbari 59.4`, `Nagaon 58.2`; each row carries area share and duration; no `NaN` |
| Provenance | renders `NOT A FORECAST`, the synthetic/derived split and source→stage→file rows |
| Methodology | HAND screening + bathtub convention + conservative-shallow bias text present |
| Layers | 6 layers with visibility + opacity; `baseMode: imagery`; checkbox and slider both mutate state (`flood` removed from `visible`, opacity `0.8 → 0.2`) |
| Charts | three series + six-value decile strip reading `0.3809 / 0.863 / 2.354 / 3.7 / 3.7 / 3.7` |
| Hooks | `__baanh.panel/.layers/.districtTop` all live |
| Playback | still advances `2/12 → 5/12` with the new panels mounted |
| Console | zero errors through load, panel switches, layer toggles and playback |

## The 5 %-pixel gate was mine, and it was wrong

Toggling the flood layer moves only **2.0 %** of the screenshot. I traced that before calling it a
bug:

- flood-only contribution at S07 with risk zones and hotspots off: **2.00 %** of the full screenshot;
- the painted mask is a **coherent valley band, correctly aligned** to the terrain and rivers — not
  a rectangle, not a misregistered image (verified by rendering the on−off diff);
- the mask spans x 13–1200, y 153–403 of a **1920×869** screenshot — i.e. the map viewport is only
  about **400 px of 869**, and the band covers ≈11 % of that viewport.

So the paint is correct and the number the app prints (10,010 km², 12.8 % of Assam) is consistent
with what is drawn. The failure is that the hero visual is cramped: roughly half the page is dock
and rail, so a genuinely large flood reads small.

**R6 (fix in B3):** make the map the dominant surface — target ≥62 % of viewport height at 900 px
tall (map height 62–68vh), with the timeline dock compacted and the analysis rail overlaying the map
rather than shrinking it. Re-run the same measurement: flood-only contribution at S07 should land
≥6 % of the screenshot at 1920×869, or the layout change is not doing its job. Do not change the
data.

## B3 scope — from "runs" to "publishable"

1. **R6 layout** as above, verified by the same pixel measurement.
2. **Executable acceptance**: `npm run verify:m0` = `check-data.mjs` + `check-budget.mjs` +
   `check-honesty.mjs` + unit tests + Playwright `m0.spec.ts` + `fallback.spec.ts`, exactly as
   `MILESTONES.md` §M0 defines it. The Playwright specs must assert against `__baanh` hooks, not
   CSS classes, and must include the blocked-tile run.
3. **Honesty gate** (`check-honesty.mjs`): fail the build on banned strings in `public/data` and
   in built output (`casualties`, `deaths`, `displaced`, `affected_persons`, `incident_id`,
   `agency_id`, `relief_camp`, unqualified `forecast`, `warning issued`), allowing the required
   `NOT A FORECAST`.
4. **Data/budget gates**: `check-data.mjs` validates every committed JSON against its schema and
   re-checks the A-series invariants; `check-budget.mjs` enforces the caps (≤400 KB/frame, ≤4 MB
   animation, ≤9 MB total).
5. **Accessibility baseline**: keyboard path (tab → timeline, space play, arrows step, enter opens a
   risk row, ESC returns focus), visible focus rings, `aria-label`s on all controls, and no
   `prefers-reduced-motion` freeze (playback lengthens instead).
6. **Docs for a stranger**: `README.md` with what it is, the honesty framing, `npm ci && npm run
   dev`, the model's limits, data provenance summary, and a screenshot; `docs/M0-REPORT.md` with
   commands and exit codes.
7. **CI**: `.github/workflows/pages.yml` building with plain `npm ci && npm run build` and deploying
   `dist/` to Pages, plus a `ci.yml` running `verify:m0` headless on Linux. Keep the sandbox scripts
   out of CI.

## Acceptance (reviewer runs)

- `npm run verify:m0` exits 0 on a machine where Chromium can launch; every gate prints its name.
- Blocked-tile run: app loads, health `offline`, playback works (already proven manually).
- Honesty gate actually fails when I inject `casualties` into a copy of the data — a gate that has
  never failed is not a gate.
- Screenshot at 1920×869: flood contributes ≥6 %.
- Clean clone → `npm ci` → `npm run build` → exit 0.
