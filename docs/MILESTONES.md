# Baanh — Milestones

**Status:** implementation plan · **Version:** 1.0 · **Date:** 2026-10-21
**Related:** `docs/ARCHITECTURE.md` (contracts, budgets), `docs/DATA-PIPELINE.md` (model and
schemas), `docs/ARCHITECT-SELF-AUDIT.md` (brief coverage).

Three milestones only. M0 is the reviewer-facing vertical slice; M1 is feature parity with the
P0 + P1 table; M2 is optional polish. Each milestone has an executable acceptance command and an
explicit “not in this milestone” list. A milestone is done only when every acceptance check in
its section passes and the “not in” list is still absent from the build.

The app is static throughout. No milestone adds a backend, database, auth, paid key, runtime AI
call, or a dataset outside the five probed sources/pipeline output.

---

## M0 — Vertical slice (the causal story, end to end)

**Goal:** a reviewer opens the app and can see, in under four minutes, that monsoon rainfall and
a rising stage drive a terrain-derived flood extent across real Assam districts, with a ranked
risk panel and visible provenance. The app is already a real system, not a map with a slider.

**Scope:** eight of the nine P0 features — P0-01, P0-02, P0-03, P0-04, P0-05, P0-06, P0-08,
P0-09. P0-07 (the full layer-control rail) is deliberately deferred to M1; M0 has fixed layer
visibility and an automatic fallback, so it can still be reviewed.

### M0 exact files

All paths are relative to the repo root. Data files are committed; the reviewer does not run the
pipeline to start M0.

```text
.nvmrc
.gitignore
README.md
index.html
package.json
package-lock.json
tsconfig.json
tsconfig.node.json
vite.config.ts
playwright.config.ts

src/main.tsx
src/App.tsx
src/vite-env.d.ts

src/styles/tokens.css
src/styles/global.css

src/shell/TopBar.tsx
src/shell/RightRail.tsx
src/shell/PanelRouter.tsx
src/shell/StatusBar.tsx
src/shell/shell.module.css

src/map/MapCanvas.tsx
src/map/mapConfig.ts
src/map/mapStyle.ts
src/map/terrain.ts
src/map/tileHealth.ts
src/map/fallbackRaster.ts
src/map/cameraController.ts
src/map/layerRegistry.ts
src/map/map.module.css
src/map/layers/flood.ts
src/map/layers/admin.ts
src/map/layers/rivers.ts
src/map/layers/risk.ts
src/map/layers/selection.ts

src/timeline/TimelineDock.tsx
src/timeline/PlaybackControls.tsx
src/timeline/TimelineScrubber.tsx
src/timeline/usePlayback.ts
src/timeline/timeline.module.css

src/charts/ChartGrid.tsx
src/charts/TelemetryChart.tsx
src/charts/ChartDataTable.tsx
src/charts/charts.module.css

src/panels/OverviewPanel.tsx
src/panels/RiskPanel.tsx
src/panels/ProvenancePanel.tsx
src/panels/RiskRow.tsx
src/panels/panels.module.css

src/state/timelineStore.ts
src/state/selectionStore.ts
src/state/panelStore.ts

src/data/types.ts
src/data/schemas.ts
src/data/loadData.ts
src/data/useDataset.ts
src/data/format.ts
src/data/labels.ts
src/data/attribution.ts

public/favicon.svg
public/data/manifest.json
public/data/provenance.json
public/data/scenario.json
public/data/validation-report.json
public/data/admin/assam-districts.geojson
public/data/admin/assam-state.geojson
public/data/hydro/assam-rivers.geojson
public/data/flood/frame-index.json
public/data/flood/frames/step-00.png … step-11.png
public/data/flood/flood-summary.json
public/data/risk/risk-zones.geojson
public/data/risk/district-risk.json
public/data/series/monsoon-series.json
public/data/basemap/assam-hillshade.webp

scripts/check-data.mjs
scripts/check-budget.mjs
scripts/check-honesty.mjs

tests/e2e/m0.spec.ts
tests/e2e/fallback.spec.ts
tests/unit/timelineStore.test.ts
tests/unit/schema.test.ts

pipeline/README.md
pipeline/pyproject.toml
pipeline/requirements.txt
pipeline/config/aoi.json
pipeline/config/scenario.json
pipeline/config/sources.json
pipeline/config/transects.json
pipeline/src/baanh_pipeline/__init__.py
pipeline/src/baanh_pipeline/cli.py
pipeline/src/baanh_pipeline/config.py
pipeline/src/baanh_pipeline/geo.py
pipeline/src/baanh_pipeline/fetch_terrain.py
pipeline/src/baanh_pipeline/fetch_boundaries.py
pipeline/src/baanh_pipeline/fetch_rivers.py
pipeline/src/baanh_pipeline/build_dem.py
pipeline/src/baanh_pipeline/build_admin.py
pipeline/src/baanh_pipeline/build_rivers.py
pipeline/src/baanh_pipeline/burn_rivers.py
pipeline/src/baanh_pipeline/hand.py
pipeline/src/baanh_pipeline/inundation.py
pipeline/src/baanh_pipeline/risk.py
pipeline/src/baanh_pipeline/series.py
pipeline/src/baanh_pipeline/schemas.py
pipeline/src/baanh_pipeline/validate.py
pipeline/src/baanh_pipeline/publish.py
pipeline/tests/test_hand.py
pipeline/tests/test_inundation.py
pipeline/tests/test_schema.py
```

Not present at M0: `src/panels/LayersPanel.tsx`, `src/state/layerStore.ts`, all P1 panels, all
P2 features. The pipeline’s `assets.py`/`gauges.py` are M1. At M0, `build-series` may write
cross-sections to `pipeline/work/` for pipeline testing; the committed
`public/data/series/cross-sections.json` and its UI are M1, and only `monsoon-series.json` is a
required M0 data file.

### M0 exact commands

**Start (reviewer):**

```powershell
npm ci
npm run dev
```

One-line form: `npm ci && npm run dev`. Open the printed local URL; with the fixed Pages base
path it is normally `http://localhost:5173/baanh/`. Node 24 is required; `.nvmrc` pins it.

**Acceptance:**

```powershell
npm run verify:m0
```

`verify:m0` must be defined in `package.json` as the sequence:

```text
npm run build
node scripts/check-data.mjs
node scripts/check-budget.mjs
node scripts/check-honesty.mjs
vitest run tests/unit/timelineStore.test.ts tests/unit/schema.test.ts
playwright test tests/e2e/m0.spec.ts tests/e2e/fallback.spec.ts
```

The build step is required because `check-budget.mjs` and `check-honesty.mjs` inspect `dist/`
for the JS/CSS caps and the built-string denylist.

The reviewer does not need Python, network, or a paid account for acceptance. Playwright lies
inside `devDependencies` and starts the Vite dev server via `playwright.config.ts`.

### M0 acceptance criteria (executable)

<!-- amended: REVIEW-02 / REVIEW-03 B3 -->

| ID | Criterion | Where it is checked |
|---|---|---|
| M0-A1 | The app loads with no uncaught exception and no console error other than expected tile-network failures. | `m0.spec.ts` page-error/console listeners |
| M0-A2 | A WebGL canvas mounts and the map is interactive (pan/orbit does not throw); the status bar reports `ok` when tile fetches succeed or the committed fallback when they do not. | `m0.spec.ts` |
| M0-A3 | The timeline exposes exactly 12 steps, starts at step 0/phase `onset`, and displays the step label and scenario stage. | `m0.spec.ts`, DOM readouts |
| M0-A4 | Play advances the step automatically; pause holds it; next/prev move exactly one step; Home/End jump to the first/last step. | `m0.spec.ts`, `timelineStore.test.ts` |
| M0-A5 | Scrubbing to S07 (`25 Aug`, `peak`) updates the map readout, all three chart cursors, and the area value without a page reload or a console error. | `m0.spec.ts` |
| M0-A6 | The flood map shows the current step’s extent and changes between S00, S04, and S07 (canvas pixel diff above a small threshold, plus the textual step/area readout). | `m0.spec.ts` |
| M0-A7 | The risk panel lists at least 5 districts sorted by descending score, each with class text and a visible explanation of its two drivers; no score is `NaN`. | `m0.spec.ts`, `check-data.mjs` |
| M0-A8 | Every visible layer/panel has a class badge (`SOURCE`, `DERIVED`, `SCENARIO`, `SYNTHETIC`); Provenance shows source → stage → file for terrain, districts, rivers, flood, and risk; “NOT A FORECAST” is visible. | `m0.spec.ts`, `check-honesty.mjs` |
| M0-A9 | With both DEM and imagery tile hosts aborted, the app still renders the committed relief and all vector overlays, reports the offline status, and the timeline still steps. | `fallback.spec.ts` |
| M0-A10 | Keyboard-only: Tab reaches the timeline, Space toggles play, ArrowRight steps, Enter opens the first risk row, ESC returns focus to the panel trigger. | `m0.spec.ts` |
| M0-A11 | `frame-index.json` + 12 half-resolution PNGs: one frame per step, all 5 classes valid, PNG within AOI v2, no `NaN`; rising-limb area non-decreasing and recession non-increasing (V-A7); peak extent 4,000–12,000 km² and ≤40% of the 31,050 km² flood-prone area (V-A4); peak median depth 1.0–2.2 m, p95 ≤ peak stage and clamped wet share ≤30% (V-A5); clamped AOI share ≤6% (V-A6); ≥9-cell component-area filter before statistics/rendering, no opening, counts and dropped area recorded (V-A9); index/PNG area and bbox agree within 1% / 1 pixel (V-A10); per-frame PNG ≤400 KB, animation tier ≤4.0 MB, total ≤9.0 MB (V09). | `check-data.mjs` + committed `validation-report.json` (V-A1…V-A10) |
| M0-A12 | Committed data sizes are within the caps in `DATA-PIPELINE.md` §11; critical tier ≤3.5 MB; animation tier ≤4.0 MB raw; total ≤9.0 MB. | `check-budget.mjs` |
| M0-A13 | No banned claim or field appears in data or built strings (`casualties`, `deaths`, `displaced`, `affected_persons`, `incident_id`, `agency_id`, `relief_camp`, positive “forecast”, `warning issued`); the required “NOT A FORECAST” disclaimer is explicitly allowed. | `check-honesty.mjs` |
| M0-A14 | The map is meaningful **without reading the docs**: the reviewer can point to rainfall, stage, extent, and district risk in the UI. | Manual 60-second check below |

**Manual 60-second check (M0):** open the app, press Play, wait for S05, pause, step to S07,
open Risk, click the top district, open Provenance. The reviewer should be able to say, unprompted:
“Rainfall peaks before the river stage; the stage floods low HAND terrain; the risk panel ranks
districts by how much area is wet, for how long, and how deep.” If any of those four clauses is
not visible, M0 is not done.

### M0 data provenance requirement

The committed M0 data must have been produced by the M0 pipeline stages, not hand-authored:

```powershell
python -m baanh_pipeline.cli fetch-terrain …
python -m baanh_pipeline.cli fetch-boundaries …
python -m baanh_pipeline.cli fetch-rivers …
python -m baanh_pipeline.cli build-dem …
python -m baanh_pipeline.cli build-admin …
python -m baanh_pipeline.cli build-rivers …
python -m baanh_pipeline.cli burn-rivers …
python -m baanh_pipeline.cli compute-hand …
python -m baanh_pipeline.cli build-inundation …
python -m baanh_pipeline.cli build-risk …
python -m baanh_pipeline.cli build-series …
python -m baanh_pipeline.cli validate …
python -m baanh_pipeline.cli publish …
```

Exact flags are in `DATA-PIPELINE.md` §5. The reviewer does not need to run these to start M0;
they exist so the committed data is reproducible. `validation-report.json` must be `pass` and
the manifest hashes must match.

### M0 explicit “not in this milestone”

- P0-07 layer panel with per-layer opacity/base-mode controls (fixed visibility only).
- P1-01 hotspots, P1-02 cross-section, P1-03 imagery PiP, P1-04 camera reach focus, P1-05
  virtual gauges, P1-06 chronology, P1-07 2D mode, P1-08 grayscale mode, P1-09 share URL,
  P1-10 OSM facility exposure.
- Mobile bottom-sheet rail; share/deep links; a11y axe suite (basic keyboard path is M0).
- Pipeline `build-assets`, `build-gauges`.
- Every P2 item, including evacuation zones, relief resources, multi-event comparison, 30 m
  analysis, exports, live feeds.
- Any backend, auth, database, paid tile key, runtime AI, or external font.

### M0 definition of done

All M0 files exist; `npm ci && npm run dev` works on Node 24; `npm run verify:m0` exits 0; the
manual check passes; `validation-report.json` is `pass`; no P1/P2 UI is present; no P2 data is
committed. The M0 app must never be positively described as a forecast; the required
“NOT A FORECAST” disclaimer must remain visible.

---

## M1 — Parity with P0 + P1

**Goal:** the full 60-second script in `ARCHITECTURE.md` §2, with all nine P0 features and all
ten P1 features. This is the shippable product.

**Scope:** M0 + P0-07 + P1-01 … P1-10, plus the accessibility and performance acceptance that
were deferred from M0.

### M1 additions (exact files)

```text
src/panels/LayersPanel.tsx
src/panels/StoryPanel.tsx
src/panels/CrossSectionPanel.tsx
src/panels/ImageryPanel.tsx
src/panels/GaugePanel.tsx
src/shell/MobileSheet.tsx

src/state/layerStore.ts
src/state/urlState.ts

src/map/layers/hotspots.ts
src/map/layers/assets.ts
src/map/layers/gauges.ts

src/charts/CrossSectionChart.tsx

public/data/risk/hotspots.geojson
public/data/series/cross-sections.json
public/data/assets/critical-facilities.geojson
public/data/gauges/virtual-gauges.geojson

pipeline/src/baanh_pipeline/assets.py
pipeline/src/baanh_pipeline/gauges.py
pipeline/config/transects.json          # already present at M0; now consumed by the UI

tests/e2e/m1.spec.ts
tests/e2e/a11y.spec.ts
tests/unit/format.test.ts
pipeline/tests/test_risk.py
```

### M1 exact command

```powershell
npm run verify:m1
npm run build
npm run preview
```

`verify:m1` must run the M0 checks plus:

```text
playwright test tests/e2e/m1.spec.ts tests/e2e/a11y.spec.ts
```

Optional full data revalidation (requires the Python environment and committed data):

```powershell
python -m baanh_pipeline.cli validate --data public/data --config pipeline/config --report public/data/validation-report.json --version 2026.10.0
```

### M1 acceptance criteria

Every row in the feature table marked P0 or P1 must have a working UI path and a test. The
acceptance matrix:

| Feature | Executable check |
|---|---|
| P0-01 shell | Existing M0 shell still passes; rail/dock reachable at 1280 px and 390 px. |
| P0-02 terrain | 3D terrain present with satellite and hillshade modes; pitch/zoom limits enforced. |
| P0-03 flood extent | All 12 steps render; depth bands match legend; S07 is the visual maximum. |
| P0-04 timeline | Play/pause/speed 0.5/1/2/step/scrub; reduced-motion path steps without animation. |
| P0-05 charts | Three charts share a cursor; rainfall, stage, area values match `flood-summary` at every step. |
| P0-06 risk | Risk zones layer toggles; ranking sorted; click focuses district and shows drivers; classes/thresholds match schema. |
| P0-07 layers | Every registry layer toggles; opacity clamps 0–100; base mode switches; no map re-init; state survives panel switches. |
| P0-08 provenance | Every layer has source/stage/file/licence/class; assumptions and limitations visible; “NOT A FORECAST”. |
| P0-09 fallback | M0 fallback spec still passes; hillshade is fetched only on failure. |
| P1-01 hotspots | Layer shows ≤20 derived pockets; click shows reason/hand/distance; label says “not a breach”. |
| P1-02 cross-section | Three transects; water line moves with step; ground/water/depth values finite; data-table toggle. |
| P1-03 imagery PiP | Opens, shows Esri attribution and “basemap imagery, not an event observation”; ESC closes and restores focus. |
| P1-04 camera | District/reach focus flies once; reduced motion jumps; reset returns to home. |
| P1-05 gauges | 6–8 synthetic stations; stage updates with timeline; every label carries synthetic badge. |
| P1-06 chronology | Onset/rising/peak/receding rows; selecting a row sets the step; all rows `scenario`. |
| P1-07 2D mode | Terrain off, pitch 0, risk/flood layers still align; switching back restores terrain. |
| P1-08 grayscale | Hillshade-only base mode; imagery hidden; attribution for elevation remains. |
| P1-09 share | Hash round-trip preserves step/panel/layers/camera; invalid hash falls back safely. |
| P1-10 assets | OSM facilities load, expose peak depth band and completeness caveat; no capacity/status claim. |

Cross-cutting M1 exits:

| ID | Criterion | Check |
|---|---|---|
| M1-X1 | `npm run verify:m0` and `npm run verify:m1` both exit 0. | CI/local |
| M1-X2 | `validation-report.json` status is `pass`; no warnings other than V17 coverage if applicable. | `check-data.mjs` |
| M1-X3 | Data caps: total ≤9 MB; flood frames per PNG ≤400 KB raw, animation tier ≤4.0 MB raw; critical ≤3.5 MB. | `check-budget.mjs` |
| M1-X4 | JS initial ≤350 KB gzip, CSS ≤25 KB gzip; no font/analytics/network requests outside the two tile hosts. | `check-budget.mjs` + Playwright request log |
| M1-X5 | 60 fps pan/orbit target; p95 frame ≤22 ms; no playback frame >50 ms on the reference laptop. | Manual Chrome performance trace, recorded in the M1 PR |
| M1-X6 | Axe: zero critical violations on Overview, Layers, Risk, Provenance, Cross-section; keyboard-only path complete. | `a11y.spec.ts` |
| M1-X7 | Offline: both tile hosts aborted; all P0/P1 non-tile features still work; only hillshade/imagery degrade. | `fallback.spec.ts` + manual |
| M1-X8 | Honesty: no banned fields/claims; all layers labelled; synthetic series labelled at point of use. | `check-honesty.mjs`, `m1.spec.ts` |
| M1-X9 | No P2 UI or data is present. | file/route audit + test |
| M1-X10 | Full 60-second script (ARCHITECTURE §2) runs without a dead end. | Manual, recorded as a checklist in the PR |

### M1 explicit “not in this milestone”

- Evacuation corridors, relief-camp locations, resources/deployment table, ETAs.
- Multi-event historical comparison; any claim that the scenario is a real event.
- 30 m analysis, exports (GeoTIFF/CSV/PDF), live gauge/rainfall adapters, service-worker offline
  install, full mobile app, 3D buildings/trees, time-of-day lighting.
- Any backend, database, auth, paid key, runtime AI, analytics, or user accounts.

### M1 definition of done

All P0 and P1 rows in the parity table are implemented and tested; `verify:m0` and `verify:m1`
pass; axe critical is zero; the data validation report is `pass`; the 60-second script runs
without a dead end; no P2 feature or fake operational claim has slipped in.

---

## M2 — Polish / optional

**Goal:** improve depth and finish without changing the product’s honesty posture. M2 is not
required for “definition of done” of the assignment; it is where a builder goes only after M1 is
green and only if the data to support a feature exists.

### Candidate work (each independently optional)

| Candidate | Precondition | Acceptance if attempted |
|---|---|---|
| 30 m analysis refinement | Pipeline memory/time budget raised; tiles at z12/z13; outputs still ≤14 MB after simplification | `validate` pass; flood cap met; visual comparison against M1 documented; no claim of higher accuracy without calibration |
| Multi-event comparison | A second event with verified extent/level data from a probed source | Both scenarios labelled; no invented event ids; compare UI does not imply forecast skill |
| GeoTIFF/CSV export | Client-side export only; no backend | Export contains class/provenance metadata; file size bounded; test round-trip |
| Service-worker offline install | Static cache only; versioned data; clear stale-cache path | Lighthouse PWA basics; no stale app/data mix; fallback still works |
| Full mobile layout | M1 responsive baseline exists | 360 px no horizontal scroll; timeline usable; a11y scan passes |
| Print/PDF summary | Print stylesheet only | Map + risk table + provenance legible; no invented stats |
| Additional cross-sections | Transects config expanded; data regenerated | Samples valid; performance cap holds |

### M2 commands

```powershell
npm run verify:m0
npm run verify:m1
npm run verify:m2        # exists only if M2 work is attempted
```

`verify:m2` must include all previous checks plus one test per attempted candidate. A feature
without a test and a provenance entry is not done.

### M2 explicit “not in this milestone”

- Live operational feeds, warnings, evacuation routing, relief deployment, casualty/loss
  estimates.
- Paid imagery/tiles, backend services, auth, databases, runtime AI.
- A second event built from a non-probed source or from invented levels/extents.
- Any feature that makes the product look like an official Assam/CWC/NDRF system.

M2 may be skipped entirely. Skipping it is not a defect; claiming a P2 feature without its
precondition is.

---

## Build order and dependencies

1. **Data first, but only to M0 depth.** Implement pipeline stages 01–11 for one scenario; run
   `validate`; do not start UI work against hand-written GeoJSON. The app must fail visibly on a
   bad schema from day one.
2. **Shell + map.** `App`, `MapCanvas`, `mapStyle`, terrain, tile health, fallback. Prove the
   map works with no overlay before adding the timeline.
3. **Timeline + flood.** One source, two fill layers, filters, rAF crossfade. Prove no re-tiling
   and no frame over 50 ms at 12 steps.
4. **Charts + risk.** Read from the same summary; no duplicated constants; click a risk row.
5. **Provenance + honesty.** Add badges, the provenance panel, `check-honesty`, and the fallback
   test before calling M0 done.
6. **M1 breadth.** Layer store/panel first, then hotspots/cross-section/gauges/assets, then share
   and mobile, then a11y/perf hardening.
7. **M2 only after M1 is green.** No parallel P2 work that could contaminate the honesty model.

## Reviewer command summary

| Purpose | Command |
|---|---|
| Install and start M0 | `npm ci && npm run dev` |
| Run M0 acceptance | `npm run verify:m0` |
| Run M1 acceptance | `npm run verify:m1` |
| Revalidate committed data | `python -m baanh_pipeline.cli validate --data public/data --config pipeline/config --report public/data/validation-report.json --version 2026.10.0` |
| Build production bundle | `npm run build` |
| Preview production bundle | `npm run preview` |

The build must remain static: `dist/` contains HTML, JS, CSS, and `data/`, nothing else. A
successful `npm run build` followed by `npm run preview` is part of M1 acceptance.
