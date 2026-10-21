# M0 report — B3 acceptance run

**Commit at report time:** the B3 commit in this repository (see `git log -1`).
**Environment:** Windows 11, Node `v24.14.1`, npm `11.11.0`, Playwright `1.64.1`
(Chromium 1248 cached). No data or pipeline file was changed for B3.

> **Harness note.** The DSH Windows sandbox used to build this branch denies
> `child_process` spawns with piped/named-pipe stdio. That blocks Vite's esbuild child and
> Chromium's Mojo channel (`spawn EPERM`, `platform_channel.cc: Access is denied`). The
> static gates and unit tests below ran here; the browser specs are written against the same
> built `dist/` and run in `.github/workflows/ci.yml` on Linux, where Chromium launches. The
> plain `npm run build` path is the committed/CI path; `build:sandbox` is the local shim.

## Commands and exit codes

| # | Command | Exit | Result |
|---|---|---|---|
| 1 | `npm run build:sandbox` | **0** | `tsc -p tsconfig.json --noEmit` + Vite production build, 175 modules, 5 assets |
| 2 | `node scripts/check-data.mjs` | **0** | 24/24 gates; 0 failures |
| 3 | `node scripts/check-budget.mjs` | **0** | 4.63 MB total; animation 2.24 MB; largest frame 248.8 KB |
| 4 | `node scripts/check-honesty.mjs` | **0** | 0 banned strings; `NOT A FORECAST` present in `dist/` |
| 5 | `node scripts/check-honesty.mjs --self-test` | **0** | clean copy passes; injected copy produces 9 violations and is rejected |
| 6 | `npm run test:unit` | **0** | 13 tests, 13 pass, 0 fail |
| 7 | `npx playwright test --list` | **0** | 10 tests discovered in `m0.spec.ts` + `fallback.spec.ts` |
| 8 | `npm run verify:m0` | not runnable here | blocked at step 1 (plain Vite esbuild spawn) and step 7 (Chromium spawn) by the DSH sandbox |
| 9 | `npx playwright test tests/e2e/...` | blocked here | Chromium launch: `spawn EPERM`; system Chrome: `mojo platform_channel: Access is denied` |

`npm run verify:m0` is wired exactly as the acceptance path:

```text
npm run build
node scripts/check-data.mjs
node scripts/check-budget.mjs
node scripts/check-honesty.mjs
node scripts/check-honesty.mjs --self-test
npm run test:unit
playwright test tests/e2e/m0.spec.ts tests/e2e/fallback.spec.ts
```

On a machine where Chromium can launch (and outside this Windows sandbox), step 1 uses plain
Vite and step 7 runs headless. CI performs both.

## Data gates (check-data.mjs)

- Every committed JSON/GeoJSON parses; strict JSON rejects non-finite values.
- App Zod schemas validate manifest, scenario, flood summary, frame index, district risk,
  monsoon series and provenance. Risk-zone and hotspot feature collections are schema-checked.
- Manifest integrity: 28 listed files, every committed file listed exactly once, byte sizes and
  SHA-256 agree.
- GeoJSON: geometry present, finite coordinates inside the frame AOI, valid class/label, unique
  IDs, 33 districts, 860 rivers, 1,747 risk zones, 20 hotspots, 1,183 facilities, 8 gauges.
- District risk: 33 dense ranks, finite 0–100 scores, counts agree; top row is
  `Sivasagar 71.944`.
- A-series invariants re-checked:
  - V-A1 AOI v2 52,240.7 km².
  - V-A2 channel share 2.80% (≤4%).
  - V-A3 strict rise to S07, strict fall after, peak 3.70 m.
  - V-A4 peak 10,010.6 km² (32.2% of flood-prone, inside 4,000–12,000 km² and ≤40%).
  - V-A5 peak median 2.354 m, p95 3.70 m, p95−median 1.346 m, clamped wet 21.0%; all 12 steps
    carry ordered deciles whose p50/p95 equal the step median/p95.
  - V-A6 clamped AOI share 5.32% (≤6%).
  - V-A7 rising limb non-decreasing, recession non-increasing, peak S07.
  - V-A9 component-area filter ≥9 cells, no opening, before statistics, counts recorded.
  - V-A10 real PNG decode: 3,733 × 2,611, wet-cell counts match `png_wet_cells`, decoded area
    within 1% of `png_area_km2` for all 12 frames.
- Step contract, shares/totals, series↔summary equality, provenance source→stage→file, and
  cross-section/gauge completeness are checked separately.

## Budget gate (check-budget.mjs)

```text
critical tier:      1.18 MB / 3.50 MB
animation tier:     2.24 MB / 4.00 MB
optional+fallback:  1.20 MB / 3.00 MB
public/data total:  4.63 MB / 9.00 MB
largest frame:     248.8 KB / 400.0 KB
```

## Honesty gate

The clean gate scans all text/JSON under `public/data` and all text/HTML/JS/CSS under `dist`.
It bans `casualties`, `deaths`, `displaced`, `affected_persons`, `incident_id`, `agency_id`,
`relief_camp`, `warning issued`, and any `forecast` not inside an explicit negation. It also
requires the built output to contain `NOT A FORECAST`.

The self-test copies the data, injects every banned string, and asserts the same gate detects
each one. The observed injected output:

```text
injected copy: FAIL as intended (9 violations)
  detected [casualties] at scenario.json:7
  detected [deaths] at scenario.json:7
  detected [displaced] at scenario.json:7
  detected [affected_persons] at scenario.json:7
  detected [incident_id] at scenario.json:7
  detected [agency_id] at scenario.json:7
  detected [relief_camp] at scenario.json:7
  detected [warning issued] at scenario.json:7
  detected [unqualified forecast] at scenario.json:7
check-honesty self-test: PASS (real gate rejects each banned string)
```

Manual reviewer injection works the same way:

```powershell
Copy-Item -Recurse public/data $env:TEMP\baanh-data
# add "casualties" to a copy
node scripts/check-honesty.mjs --data $env:TEMP\baanh-data --dist dist
# exit 1, names the file/line/rule
```

## Unit tests

`npm run test:unit` compiles the test tsconfig and runs Node's test runner:

- 7 tile-health tests: no false `live`, no false `offline`, success recovery, shared copy.
- 6 timeline-store tests: 0→11 advance, pause, step/clamp, restart at end, frame gating,
  long-tick no-skip.
- 13 pass, 0 fail (78 ms).

## Browser acceptance (CI command)

```bash
npx playwright install --with-deps chromium
npm run verify:m0
```

`m0.spec.ts` (8 tests) asserts through `window.__baanh`:

- Load: step 0/12, `01 Jun`/`onset`, frame `step-00.png`, six layers, risk/panel hooks,
  `Sivasagar 71.9`, no unexpected console/page errors.
- Keyboard: first tab is the timeline skip link; Space plays/pauses; arrows step; Home/End jump.
- S07: step 7, `25 Aug`/`peak`, `step-07.png`, 10,010.6411 km², all three chart values.
- Canvas: S00→S04 and S00→S07 pixel diffs above threshold.
- Risk: 33 rows, first `Sivasagar` 71.9, Enter selects, Escape returns focus to the Risk tab.
- Layers: flood visibility and opacity 0→0.2→1, base-mode switch, all through the probe.
- Provenance: source→stage→file for terrain/boundaries/rivers/flood/risk, assumptions,
  “NOT A FORECAST”, `conservative-shallow`.
- Reduced motion: playback still advances (lengthened dwell, no freeze).
- R6 at 1920×869: `#map-viewport` height must be 62–68% of 869 px; with risk zones and hotspots
  off, the S07 flood-on/off canvas diff must be ≥6% of the full 1920×869 screenshot. The test
  logs `R6 map height` and `R6 flood-only contribution` for the reviewer.

`fallback.spec.ts` aborts both tile hosts, waits for `__baanh.tileHealth === 'offline'`, asserts
the “Tile hosts offline · committed relief” copy, six overlays, S07 frame/area, and playback
stepping. Tile-network console errors are the only ones allow-listed.

The local harness cannot produce the browser numbers because Chromium cannot create its Mojo
channel here; the first CI run writes them to the job log and the uploaded Playwright report.

## R6 layout implementation

- Top bar 58 px; analysis rail is an absolute overlay on the right (388 px max, stopping above
  attribution), so it no longer subtracts from map width.
- Dock is compact (`clamp(248px, 26.5vh, 290px)`), with 32 px sparklines and a 32 px decile strip.
- `#map-viewport` is the full remaining height: 563 px at 1920×869 (64.8%) and 594 px at
  1920×900 (66.0%).
- The camera fits the core flood belt, then eases in 0.4 zoom (presentation only); flood opacity
  is 0.88 with higher saturation/contrast so the mask reads at a glance. No data changed.

## Files added/changed for B3

```text
package.json, README.md, playwright.config.ts
scripts/check-data.mjs, scripts/check-budget.mjs, scripts/check-honesty.mjs
scripts/lib/png.mjs
tests/e2e/helpers.ts, tests/e2e/m0.spec.ts, tests/e2e/fallback.spec.ts
src/App.tsx, src/shell/shell.module.css, src/shell/RightRail.tsx
src/timeline/TimelineDock.tsx, TimelineScrubber.tsx, PlaybackControls.tsx,
src/timeline/usePlayback.ts, src/timeline/timeline.module.css
src/panels/LayersPanel.tsx, src/panels/panels.module.css
src/map/MapCanvas.tsx, src/map/mapStyle.ts, src/map/mapConfig.ts, src/map/map.module.css
src/styles/global.css, src/state/timelineStore.ts
.github/workflows/ci.yml, .github/workflows/pages.yml
docs/screenshot-m0.png, docs/M0-REPORT.md
```

`public/data/**` and `pipeline/**` are byte-for-byte unchanged.
