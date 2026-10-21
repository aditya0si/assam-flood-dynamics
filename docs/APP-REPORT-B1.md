# App report — phase B1

**Status:** B1 implementation complete; browser acceptance partly blocked by the harness sandbox.
**Scope:** Vite 7 + React 19 + TypeScript shell, MapLibre 3D terrain, 12-frame crossfaded flood timeline,
timeline dock with one uPlot area chart, readouts from `public/data`, honesty chrome.
**Date:** 2026-10-21

---

## 1. What was built

| Area | Implementation |
|---|---|
| Scaffold | Vite 7.3.7, React 19.3.1, TypeScript 5.9 strict (`tsc --noEmit` in `npm run build`). No router, backend, CSS framework, web fonts, icon package or paid key. |
| Shell | Top bar + full-bleed map viewport + bottom timeline dock. Persistent `NOT A FORECAST` chip, data-derived `SCENARIO` badge, dataset version, current Sxx/date/phase readout. |
| Map | MapLibre GL 5.24: AWS Terrarium `raster-dem` (source `maxzoom: 12`), terrain at **1.4×** exaggeration; Esri World Imagery raster; committed `basemap/assam-hillshade.webp` as an image source underneath; district outlines and 860 river lines from committed GeoJSON; camera fitted to the manifest AOI with pitch **55°**, bearing **-15°**; `maxPitch 75`, `maxZoom 13`, `renderWorldCopies: false`. A second Terrarium `raster-dem` source feeds the hillshade layer so MapLibre does not warn about sharing one DEM source with terrain. |
| Flood layer | `frame-index.json` read once. Two image sources, `flood-raster-current` / `flood-raster-outgoing`, placed with the frame WGS84 bbox. On step change the sources are updated through `ImageSource.updateImage({ url })` and `raster-opacity` is animated 0 → **0.62** over **220 ms**. No source remove/add and no vector tiling. The preload cache keeps only a small working set (previous, current, next), not all 12 frames. |
| Timeline | Zustand store is the single clock. Play/pause, prev/next, first, 12-stop range scrubber, 12 clickable Sxx ticks, speeds 0.5×/1×/2×; Space toggles play, ArrowLeft/Right step, Home/End jump, PageUp/PageDown jump by 3. rAF playback at 1200 ms/speed; stops at the last step; pauses when hidden; reduced motion steps once per press. |
| Readouts | Step label, phase, scenario stage, inundated area, share of Assam, share of flood-prone area, and class badge. All values come from `flood-summary.json`; no reading is hard-coded. S07 renders `25 Aug`, `3.7 m`, `10010.6 km²`, `12.8%` of Assam and `32.2%` of the flood-prone area. |
| Chart | One uPlot area chart of `inundated_area_km2` over the 12 steps, with an amber playhead line tied to the store step, click-to-step, and a screen-reader data table. |
| Honesty | `NOT A FORECAST` in the top bar; `SCENARIO` from `summary.class`; `SYNTHETIC` from `summary.series_class.rainfall` on the dock's rainfall/stage series note; stage explicitly labelled “Scenario stage”; all model copy says scenario, not forecast or warning. |
| Resilience | Tile health state machine: 6 s without a successful tile or repeated errors marks DEM/imagery offline. Imagery is hidden to reveal the committed relief; DEM loss drops terrain and clamps pitch. Frames still animate with both tile hosts unreachable. MapLibre errors from the two tile sources are `preventDefault`ed. |
| Accessibility | Slider `aria-valuetext` from data, live polite step announcement, focus-visible rings, map `role="img"` with an imperative step-aware label, chart data table, prefers-reduced-motion handling. |

---

## 2. Commands run (actual exit codes)

| Command | Result |
|---|---|
| `npm install` | **exit 0** (reproducible with the committed `.npmrc`; see §4) |
| `npm run build` | **exit 0**, `dist/` produced: `index.html` 1.40 kB, CSS 91.54 kB, React chunk 12.64 kB, uPlot 52.27 kB, app 337.66 kB, MapLibre 1,052.86 kB |
| `npx tsc -p tsconfig.node.json --noEmit` | **exit 0** |
| `npm run dev` | Vite ready on **http://localhost:5173/** |
| `GET /` on the dev server | **200**, `text/html` |
| `GET /data/manifest.json` | **200**, `application/json` |
| `GET /data/flood/frames/step-07.png` | **200**, `image/png`, 254,791 B |
| Production preview (`npm run preview`) | served `http://localhost:4173/baanh/`; manifest and step-07 PNG returned 200 at `/baanh/data/...` |

Build warnings are limited to two Rollup comment-annotation notices inside `zod`; they are not errors and do not appear in the app.

### Data-contract smoke check (Vite SSR, not a committed test)

`loadDataset()` was executed against the running dev server through Vite's SSR module runner:

```text
loaded 12 steps; peak 7; index version 2026.10.0
S07 25 Aug peak stage 3.7 area 10010.6411 assam 0.12798 prone 0.322404
formatted: 3.7 m 10010.6 km2 12.8% 32.2%
frame file frames/step-07.png bbox 89.424203,23.911344,96.265512,28.193794 classes 5
districts 33 rivers 860
```

A second SSR render of `TopBar` and `TimelineDock` with the real dataset and store at step 7 produced
`NOT A FORECAST`, `SCENARIO`, `SYNTHETIC`, `25 Aug`, `3.7`, `10010.6`, and exactly **12**
`data-step` tick buttons. The store smoke check confirmed clamping, the frames-ready play gate,
restart-from-end, and pause.

### Headless-browser limitation

This workspace's process sandbox refuses the named pipe/Mojo channel that Chromium needs. Chrome and
the Playwright Chromium headless shell both terminate with:

```text
FATAL:mojo/public/cpp/platform/platform_channel.cc:112
Check failed: . : Access is denied. (0x5)
```

Approval for a wider sandbox was not available (`no approval channel`). Therefore the WebGL-canvas,
browser-console and real playback checks in B1 acceptance §3–§4 were **not** executed here. They are
covered structurally by the SSR/store checks above and should be run by the reviewer with an
unrestricted Chromium. No browser console output is fabricated in this report.

---

## 3. Files created / changed

**Root:** `package.json`, `package-lock.json`, `.npmrc`, `.nvmrc`, `.gitignore` (added Node cache/profile exclusions), `index.html`, `tsconfig.json`, `tsconfig.node.json`, `vite.config.ts`.

**Public shell assets:** `public/.nojekyll`, `public/favicon.svg`. No file under `public/data/` was edited.

**Application source:**

- `src/main.tsx`, `src/App.tsx`, `src/vite-env.d.ts`
- `src/data/`: `schemas.ts` (zod contracts for manifest, scenario, summary, frame index and GeoJSON), `types.ts`, `loadData.ts`, `format.ts`, `labels.ts`, `attribution.ts`
- `src/state/timelineStore.ts`
- `src/lib/motion.ts`
- `src/map/`: `MapCanvas.tsx`, `mapConfig.ts`, `mapStyle.ts`, `fallbackRaster.ts`, `flood.ts`, `tileHealth.ts`, `map.module.css`
- `src/shell/`: `TopBar.tsx`, `StatusBar.tsx`, `ErrorBoundary.tsx`, `shell.module.css`
- `src/timeline/`: `TimelineDock.tsx`, `PlaybackControls.tsx`, `TimelineScrubber.tsx`, `usePlayback.ts`, `timeline.module.css`
- `src/charts/TelemetryChart.tsx`
- `src/styles/tokens.css`, `src/styles/global.css`
- `docs/APP-REPORT-B1.md` (this file)

**Sandbox build tooling (not runtime code):** `scripts/vite-run.mjs`, `scripts/esbuild-loader.mjs`, `scripts/prebundle.mjs`, `vendor/esbuild-inprocess/package.json`, `vendor/esbuild-inprocess/index.mjs`.

---

## 4. Deviations and why

1. **Dev base path is `/`, production base is `/baanh/`.**
   `ARCHITECTURE.md` §9 says both should be `/baanh/`, but B1 acceptance §2 requires `GET /` on the dev
   server to return 200. Vite 7 makes `GET /` a redirect/404 when the dev base is a project path, so the
   dev server runs at `/` while the build keeps `/baanh/`. Every fetch and asset URL is generated from
   `import.meta.env.BASE_URL`, so the data path is correct in both modes (and in the preview at
   `/baanh/`).

2. **Sandbox-only esbuild shim.**
   This harness blocks `child_process` spawns with piped stdio, which is how Vite's normal esbuild
   binary and its Windows `net use` realpath probe work. To make the required `npm install` /
   `npm run build` pass here:
   - `.npmrc` points npm at a workspace cache and sets `ignore-scripts=true` (no package here needs a
     postinstall script for the app);
   - `scripts/vite-run.mjs` short-circuits Vite's `net use` probe and runs Vite with the runner config
     loader;
   - `scripts/esbuild-loader.mjs` redirects `esbuild` to the committed in-process WASM shim in
     `vendor/esbuild-inprocess/`;
   - `esbuild-wasm` is a dev-only dependency.
   Production output is still produced by Vite 7 + Rollup. No application code imports these tools.
   On a machine where the normal esbuild binary runs, the shim can be removed without changing
   `src/`.

3. **Dev-only React/MapLibre prebundle.**
   Because Vite's dependency optimiser also uses the esbuild child process, `npm run dev` first runs
   `scripts/prebundle.mjs` to emit single ESM modules for React (one shared instance for React and
   ReactDOM) and MapLibre into `node_modules/.vite-deps/`. `vite.config.ts` aliases these only for
   `serve`, not for `build`. This is a dev-server workaround; the production graph is the normal one.

4. **`SYNTHETIC` badge appears now, before the rainfall/stage charts.**
   The brief allows the badge “on the rainfall/stage series once it appears”. The B1 dock therefore
   carries a short series note with a `SYNTHETIC` badge and states that rainfall, main-stem stage and
   backwater are synthetic while the area is scenario-derived. The actual rainfall/stage charts remain
   B2 scope.

5. **Frame updates use `ImageSource.updateImage({ url })`.**
   `map.updateImage(id, image)` in MapLibre updates style images (`map.addImage`), not image sources.
   Using it would have produced “The map has no image with that id” and no frames. The two image
   sources are therefore updated through their own `updateImage` method, which keeps the source and
   coordinates and satisfies the no-source-rebuild rule.

6. **The fallback hillshade is placed with the manifest AOI bbox.**
   The WebP is not georeferenced in-file; `DATA-PIPELINE.md` §6.17 says to use the AOI Mercator
   corners. The frame bbox is slightly larger than the AOI, so the committed relief covers the AOI
   core, not the frame margins. It is a fallback only, underneath the Esri raster.

7. **Browser verification gap (sandbox).** See §2. This is a harness limitation, not a known app
   failure; the reviewer should run the B1 browser checks in an unrestricted Chromium.

---

## 5. Deliberately absent (B2/B3)

- No right rail, `PanelRouter`, Overview/Layers/Risk/Provenance panels, or mobile sheet.
- No layer registry or layer opacity controls; fixed B1 visibility for imagery, fallback, flood,
  rivers, districts and state.
- No rainfall, stage or threshold charts; only the single area chart required for B1.
- No district risk ranking, risk-zone layer, hotspots, cross-section, gauges, facilities or imagery PiP.
- No camera fly-to/selection, no URL state, no share, no labels/markers.
- No Playwright/vitest suites, `scripts/check-*`, or Pages workflow; tests are B2/B3.
- No data or pipeline regeneration; `public/data/` and `pipeline/` were treated as read-only.

---

## 6. Acceptance checklist for the reviewer

- [x] `npm install` exit 0.
- [x] `npm run build` exit 0 and `dist/` created.
- [x] `npm run dev` on 5173 and `GET /` 200.
- [x] Exactly 12 steps in the source data and 12 scrubber tick buttons.
- [x] S07 readout `25 Aug · 3.7 m · 10010.6 km²` matches `flood-summary.json`.
- [x] `NOT A FORECAST`, `SCENARIO`, `SYNTHETIC` present in rendered markup.
- [x] No changes under `public/data/` or `pipeline/`.
- [ ] WebGL canvas, no browser-console errors, and real playback observed in a headless browser —
  blocked by the harness sandbox; run this check externally.
