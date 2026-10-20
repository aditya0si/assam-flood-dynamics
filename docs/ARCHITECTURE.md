# Baanh — Architecture

**Status:** implementation specification (architect hand-off) · **Version:** 1.0 · **Date:** 2026-10-21
**Product:** Baanh (Assamese: বান, “flood”) — Assam Flood Dynamics Analysis
**Scope of this document:** the shape of the finished static application, its components, its
data contracts, and the budgets a builder must hold. Application code is deliberately absent.

---

## 1. Product statement

Baanh is a browser-based, single-page **scenario explorer for how a Brahmaputra floodplain flood
develops**. It links five things on one timeline:

1. monsoon rainfall over the catchment (synthetic series, labelled),
2. main-stem stage and tributary level above local drainage (synthetic scenario, labelled),
3. a DEM-derived inundation sequence computed with HAND (height above nearest drainage),
4. the districts and terrain pockets that carry the longest/deepest inundation (derived), and
5. the provenance of every one of those layers (source → processing → committed file).

It is an **explanatory model**, not an operational forecast, not a warning service, and not a
record of a real event. The terrain, district boundaries and rivers are real; the water levels
and rainfall are a declared synthetic monsoon scenario; the flood extent and risk scores are
derived from those inputs with the model documented in `docs/DATA-PIPELINE.md`.

The product is a static site. No backend, database, authentication, paid tile key, runtime AI
call, or live feed. A GitHub Pages deploy is the reference target.

### Target user

**Primary:** a skeptical technical reviewer — hydrology-aware engineer, GIS lead, or recruiter —
who opens a link with no instructions and decides in about 60 seconds whether this is a real
system or a painted mock. They will look for real geography, a stated model, units, provenance,
and a timeline that actually drives every view.

**Secondary:** a student or planner who wants the causal chain “rain → stage → backwater →
inundation → risk” made legible without reading a report. They need labels, legends, and a
readable cross-section more than they need controls.

**Explicitly not the user:** an emergency responder needing live information. The UI must never
imply that it is suitable for that.

---

## 2. The 60-second demo script

This is the script the finished product (M1) must support without dead ends. The M0 slice
executes the same script through the “risk ranking” beat; P1-only panels are marked.

| Time | Viewer action / what is on screen | What it proves |
|---|---|---|
| 0–4 s | Page opens on an oblique 3D view of Assam. The Brahmaputra is a pale braided line through green relief; district borders are thin. Top bar: **Baanh · Assam Flood Dynamics · Composite monsoon scenario**. Badge: `SCENARIO`. | Real geography; the shell reads as a product, not a demo page. |
| 4–8 s | Right rail **Overview**: “Scenario stage 0.5 m above local drainage · 01 Jun · onset”. Timeline at S00/12. The rainfall and stage charts are flat-ish; inundated area is small. | Units, model state, and the starting condition are stated before any animation. |
| 8–16 s | Press **Play**. The scrubber advances through 12 steps. Flood polygons grow from the main stem and low tributary mouths into the floodplain. The three charts track in lockstep; the area chart climbs, the stage chart lags the rainfall peak. | One timeline is the source of truth for map and analytics. |
| 16–24 s | Pause at S05. Hover a depth band: “3.4–4.3 m above local drainage”. Open **Layers**, switch satellite → hillshade and back, drag flood opacity. Nothing jumps; the timeline stays put. | Layer control is real, not a mock; the map is not re-created. |
| 24–34 s | Step to **S07 · peak**. Extent is widest; stage 6.0 m; area readout from the derived data. Risk zones are visible beneath the water; the **Risk** panel ranks districts. Click a district: camera eases to it and the panel explains its score drivers — area share, duration, depth. No casualty or displacement number appears anywhere. | The causal story ends in a defensible, data-bounded ranking. |
| 34–43 s | P1: open the **Cross-section** tab. A transect across the valley shows ground, water surface at the current step, and depth. Scrub back to S03: the water line drops and the inundation ribbon narrows. | The model is a terrain model, not an animation of hand-drawn shapes. |
| 43–50 s | P1: open **Imagery compare**. A small Esri imagery PiP is paired with the scenario mask, explicitly labelled “basemap imagery, not an event observation”. Press ESC; panel closes. | The satellite view is honest about what it is and is not. |
| 50–58 s | Open **Provenance**. Source → processing stage → output file for terrain, districts, rivers, flood frames, risk. Model assumptions: HAND threshold, no levee failure, no flow routing, synthetic hydrograph. Badge: `NOT A FORECAST`. | The honesty contract is visible in the product, not buried in a README. |
| 58–60 s | Close the panel. The map is back at peak with the timeline parked. | A clean end state; no modal trap. |

M0 must be able to run the beats to 34 s. The P1 beats are part of M1 acceptance, not M0.

---

## 3. Feature parity table

Priorities: **P0** = required for the vertical slice, **P1** = parity build after M0,
**P2** = deliberately outside the first build. The **P0 count is 9**.

| # | FireTrace feature | Baanh equivalent | Priority | Why |
|---|---|---|---|---|
| P0-01 | Shell: top bar, 3D viewport, right rail, bottom timeline | Same shell: `TopBar`, `MapCanvas`, `RightRail` + `PanelRouter`, `TimelineDock` | **P0** | Parity of information architecture; every later feature hangs off it. No avatar/account because there is no auth. |
| P0-02 | Oblique 3D satellite terrain with hillshade | MapLibre terrain from AWS Terrarium DEM, Esri World Imagery drape, hillshade layer, sky | **P0** | The product is about terrain; a flat map cannot show the valley/relief relationship. |
| P0-03 | Fire perimeter / burn scar (dNBR) | Scenario flood extent per step, filled by **depth band** (`0–0.5`, `0.5–1.5`, `1.5–3`, `3+ m`) | **P0** | Direct stand-in for the perimeter/scar pair; depth is the analogue of burn severity. |
| P0-04 | Date scrubber, play/pause/step | 12-step scenario timeline with play/pause, step, scrub, speed 0.5×/1×/2× | **P0** | The causal story is temporal; this is the spine of the app. |
| P0-05 | Weather & fire behaviour + area/RoS charts | Monsoon rainfall, scenario stage above local drainage vs scenario threshold, inundated area (km²) — three synced charts | **P0** | Makes the rainfall→stage→area lag legible, not merely decorative. |
| P0-06 | Fire spread probability (DEM-derived) | HAND/duration risk zones + district risk ranking, with drivers | **P0** | The “where is it going / where does it hurt” question, answered from terrain with no invented demographics. |
| P0-07 | Layers rail with opacity and base-mode switch | Layer registry + visibility/opacity for flood, risk, rivers, districts, hillshade/imagery; no map re-init | **P0** | Reviewers test layer controls first; it also proves the registry is real. |
| P0-08 | Incident overview (name, agency id, size, containment) | **Model & provenance overview**: scenario id, step, stage, area, source→stage→file, assumptions, `NOT A FORECAST` | **P0** | The honesty rules require provenance and labels; there is no agency/incident id to show. |
| P0-09 | Graceful operation when tiles fail | Committed hillshade + all vector overlays; terrain/imagery degraded states in status bar | **P0** | Hard constraint: meaningful render when tile servers are unreachable. |
| P1-01 | Hotspot dots | Derived **inundation hotspots** (low-HAND backwater pockets), never called breaches | P1 | Adds spatial detail without inventing observed breach points. |
| P1-02 | Elevation/temperature profile | Brahmaputra valley cross-section: ground, water surface, depth by step | P1 | The strongest evidence that HAND is doing real work. |
| P1-03 | Drone fleet + thermal PiP | Imagery compare PiP (Esri basemap vs scenario mask), no claimed capture time | P1 | Preserves the PiP interaction without fabricating a live sensor feed. |
| P1-04 | Aircraft follow-cam + HUD | Camera focus/fly-to for a district or valley reach; no fake altitude/speed HUD | P1 | Camera movement is useful; instrument HUD would imply telemetry that does not exist. |
| P1-05 | Drone/sensor fleet | **Virtual gauges**: 6–8 synthetic stations at mapped river points, stage series shown as synthetic | P1 | Gives the “fleet” density and a station readout, clearly labelled synthetic. |
| P1-06 | Key events / detections table | Flood chronology: onset, rising, peak, recession steps, each `scenario` | P1 | The scenario has phases; a table makes them scannable. |
| P1-07 | 2D analytical overlay mode | 2D/flat map mode with risk zones and outlines, terrain off | P1 | Useful analytical view; cheap once the layer registry exists. |
| P1-08 | Thermal / grayscale base modes | Grayscale hillshade base mode; satellite mode | P1 | The honest analogue of thermal/grayscale; no thermal sensor exists. |
| P1-09 | Share | URL hash encodes step, panel, visible layers, camera; copy-link button | P1 | Reproducible views for review; static-host friendly. |
| P1-10 | — | OSM critical-facility exposure (hospitals/clinics/schools) joined to peak mask, completeness caveat | P1 | The mission’s “assets at risk”; real OSM points, no invented facilities, explicitly incomplete. |
| P2-01 | Evacuation zones | **Not built** | P2 | No verified evacuation corridor or relief-camp dataset among the probed sources. Synthetic camps would imply real operational guidance. |
| P2-02 | Resources table (D-425, Water Tender, ETA) | **Not built** | P2 | No deployment, fleet, or ETA data exists; inventing it violates honesty rule 4. |
| P2-03 | Full drone/aircraft HUD and flight paths | **Not built** | P2 | No flight data; P1 keeps only the camera behaviour. |
| P2-04 | Multiple historical events, time compare | Single declared composite scenario only | P2 | Adding a second event needs verified event extents/levels not in the probed sources. |
| P2-05 | 30 m analysis, exports, live gauge adapter | 90 m analysis; no export; no live adapter | P2 | 30 m multiplies pipeline memory by ~9; exports/live data add scope without improving the story. |

**P0 feature count: 9.** The vertical slice M0 implements eight of the nine (all except P0-07,
the full layer control rail); M1 closes P0-07 and adds P1. This split is defined in
`docs/MILESTONES.md`.

---

## 4. Tech stack

Node 24 + npm 11. The application is a Vite static build with no server runtime.

| Dependency | Version | Role | One-line rationale |
|---|---|---|---|
| `vite` | ^7 | dev server, build, static output | The smallest well-understood toolchain that produces a GitHub-Pages-ready bundle with hashed assets. |
| `react` + `react-dom` | ^19 | shell, panels, charts wrappers, controls | Component model matches the panel/dock layout; no server features are needed or used. |
| `typescript` | ^5.7 | application and data types | The data contracts in §6 and `DATA-PIPELINE.md` are the product; types make them enforceable. |
| `maplibre-gl` | ^5 | 3D terrain, raster drape, GeoJSON layers, camera | Only mainstream open-source renderer that gives DEM terrain, hillshade, raster basemaps and vector overlays without a paid token. |
| `zustand` | ^5 | timeline, layers, selection, panel stores | ~1 KB, works outside React’s render loop, so 60 fps playback does not re-render the map tree. |
| `uplot` | ^1.6 | rainfall/stage/area time-series charts | Canvas charts with a shared cursor and ~15 KB gzip; SVG chart libraries re-render too much during playback. |
| `zod` | ^4 | runtime validation of every committed JSON/GeoJSON payload | A malformed or stale data file fails visibly at load instead of producing a silently wrong map. |
| `@playwright/test` (dev) | ^1.5 | M0/M1 acceptance, fallback and a11y smoke tests | The milestones demand executable reviewer checks, including network-failure behaviour. |
| `vitest` (dev) | ^3 | unit tests for stores, formatters, risk presentation | Fast tests where a browser is unnecessary. |

No date library (12 steps are pre-labelled), no charting dashboard framework, no CSS framework,
no icon package (inline SVG), no web fonts (system stack), no state persistence middleware, no
service worker, no analytics, no backend SDK.

Python is **not** a runtime dependency. It is only the offline pipeline described in
`docs/DATA-PIPELINE.md` (Python 3.11+, NumPy/SciPy/Rasterio/Shapely/pyproj/Pillow/mercantile/
requests). The committed outputs are what ships.

### Rejected alternatives

| Decision | Chosen | Rejected | Why rejected |
|---|---|---|---|
| 3D renderer | **MapLibre GL JS** | **CesiumJS** | Cesium’s globe and 3D Tiles are excellent but unnecessary for one regional AOI; it is several times the bundle, opinionated about asset/ion services, and its terrain/imagery stack is harder to run key-free and offline. |
| 3D renderer | **MapLibre GL JS** | **three.js** | three.js would require building the DEM tile pyramid, terrain mesh, projection, camera constraints, raster draping, hit-testing, and basemap compositing. That is a research project, not a 60-second demo, and it would still need MapLibre for tiles. |
| 3D renderer | **MapLibre GL JS** | Mapbox GL JS | Paid token and licence terms conflict with the no-paid-key constraint. |
| Charts | **uPlot + hand-written SVG cross-section** | Recharts | Recharts’ SVG reconciliation and animation are wasteful when the playhead moves 12 times and the map is also rendering; bundle is larger. |
| Charts | **uPlot + hand-written SVG cross-section** | Chart.js | Canvas but imperative plugin/cursor work is comparable; uPlot is smaller and its shared-cursor model fits the synced dock. |
| Charts | **uPlot + hand-written SVG cross-section** | D3 full | D3 is a toolkit, not a chart; we would rebuild axes/cursor/tooltip anyway. The cross-section alone does not justify the dependency. |
| State | **Zustand** | Redux Toolkit | Boilerplate and bundle for four small stores; no time-travel or middleware requirement. |
| State | **Zustand** | React Context only | A context update on every playback tick re-renders the shell; the map needs an imperative subscription instead. |
| State | **Zustand** | Jotai/Valtio | Both are credible; Zustand’s transient `subscribe` is the simplest fit for “store changes, map updates without React render”. |
| Styling | **CSS Modules + custom properties** | Tailwind | Utility strings obscure the data-heavy layout; a design-token layer is enough and avoids another build plugin. |
| Styling | **CSS Modules + custom properties** | styled-components / Emotion | Runtime style cost and React 19 integration risk for no benefit on a fixed shell. |
| Styling | **CSS Modules + custom properties** | vanilla-extract | Build-time type safety is nice, but the added toolchain is not justified by ~10 components. |
| Routing | **No router** | React Router | One page, no path hierarchy. P1 share state is a hash payload, not routes. |
| App framework | **Vite + React SPA** | Next.js | No server rendering, no backend, no SEO requirement; Next adds a runtime and deployment assumptions that conflict with GitHub Pages. |
| Data transport | **Committed GeoJSON + JSON** | PMTiles/vector tiles | 12 simplified frames plus admin layers fit the budget; a tile pipeline would add tooling and a custom source for no first-build gain. |
| DEM | **AWS Terrarium raster-dem** | Mapbox terrain RGB | Terrarium is key-free and probed 200; Mapbox terrain needs a token. |
| Labels | **DOM markers** | MapLibre symbol layers | Symbol layers require a glyph PBF endpoint. Committed glyphs are possible but add a binary asset and a font-licence question; DOM labels keep the app fully offline. |

---

## 5. File tree

`P1` marks files that may be absent at M0. Every source and data file in the finished repo is
listed; generated pipeline intermediates are shown separately because they are gitignored.

```text
baanh/
├─ .github/
│  └─ workflows/
│     └─ pages.yml                     # build dist and deploy to GitHub Pages on main
├─ .gitignore                          # node_modules, dist, .venv, pipeline/cache, pipeline/work
├─ .nvmrc                              # 24
├─ README.md                           # what it is, npm ci && npm run dev, data provenance summary
├─ index.html                          # Vite entry; meta description; noscript fallback text
├─ package.json                        # scripts: dev, build, preview, verify:m0, verify:m1, test
├─ package-lock.json                   # locked dependency graph
├─ tsconfig.json                       # strict app TypeScript config
├─ tsconfig.node.json                  # config for vite.config.ts
├─ vite.config.ts                      # React plugin, base path, chunk split, data served from public/
├─ playwright.config.ts                # Chromium project, webServer: npm run dev, baseURL
├─ docs/
│  ├─ ARCHITECTURE.md                  # this document
│  ├─ DATA-PIPELINE.md                 # AOI, stages, schemas, model, validation
│  ├─ MILESTONES.md                    # M0/M1/M2 acceptance and exclusions
│  ├─ ARCHITECT-SELF-AUDIT.md          # brief requirement → location → status
│  ├─ reference-analysis.md            # verified reference inventory and honesty rules
│  └─ briefs/
│     └─ 01-architect.md               # the brief this spec answers
├─ public/
│  ├─ .nojekyll                        # harmless with Actions; prevents Jekyll surprises on manual deploy
│  ├─ favicon.svg                      # flood-mark icon, no external asset
│  └─ data/
│     ├─ manifest.json                 # dataset version, bbox, file list, hashes, classes, load tier
│     ├─ provenance.json               # source → pipeline stage → output entries, licences, fetch dates
│     ├─ scenario.json                 # scenario id, 12 steps, model parameters, assumptions, limitations
│     ├─ validation-report.json        # last pipeline validation run; status + every check
│     ├─ admin/
│     │  ├─ assam-districts.geojson    # geoBoundaries ADM2 filtered to Assam; risk attributes joined
│     │  └─ assam-state.geojson        # dissolved Assam outline for mask/outline (derived from ADM2)
│     ├─ hydro/
│     │  └─ assam-rivers.geojson       # OSM rivers with Natural Earth fallback; channel display layer
│     ├─ flood/
│     │  ├─ flood-frames.geojson       # all 12 scenario extents, depth bands, one feature set per step
│     │  └─ flood-summary.json         # per-step rainfall/stage/area/depth aggregates for charts
│     ├─ risk/
│     │  ├─ risk-zones.geojson         # derived HAND × duration zones, P0 risk layer
│     │  ├─ district-risk.json         # ranked districts, score drivers, weights, coverage
│     │  └─ hotspots.geojson           # P1 derived low-HAND backwater pockets (not breaches)
│     ├─ series/
│     │  ├─ monsoon-series.json        # synthetic rainfall + scenario stage + threshold
│     │  └─ cross-sections.json        # P1 valley transects: ground, water, depth by step
│     ├─ basemap/
│     │  └─ assam-hillshade.webp       # committed relief raster used when terrain/imagery tiles fail
│     ├─ assets/
│     │  └─ critical-facilities.geojson # P1 OSM hospitals/clinics/schools + derived peak exposure
│     └─ gauges/
│        └─ virtual-gauges.geojson     # P1 synthetic stations on mapped rivers with stage series
├─ scripts/
│  ├─ check-data.mjs                   # validates manifest, sizes, step count, no NaN, hashes
│  ├─ check-honesty.mjs                # scans built strings/data for banned claims and fields
│  └─ check-budget.mjs                 # asserts JS/CSS/data budgets from dist/ and public/data/
├─ src/
│  ├─ main.tsx                         # React root, global CSS import, error boundary
│  ├─ App.tsx                          # AppShell: top bar + viewport + rail + dock; no routing
│  ├─ vite-env.d.ts                    # Vite types
│  ├─ shell/
│  │  ├─ TopBar.tsx                    # product name, scenario label, step readout, share (P1)
│  │  ├─ RightRail.tsx                 # panel host, collapse/mobile sheet behaviour
│  │  ├─ PanelRouter.tsx               # maps active panel id → panel component; focus management
│  │  ├─ StatusBar.tsx                 # terrain/imagery health, data version, loading progress
│  │  ├─ MobileSheet.tsx               # P1 bottom-sheet presentation of the rail under 900 px
│  │  └─ shell.module.css              # shell layout, rail, top bar, focus rings
│  ├─ map/
│  │  ├─ MapCanvas.tsx                 # creates map once; subscribes to stores; cleanup on unmount
│  │  ├─ mapConfig.ts                  # home view, max bounds, zoom/pitch limits, source URLs
│  │  ├─ mapStyle.ts                   # style skeleton + ordered layer array (see §7)
│  │  ├─ terrain.ts                    # terrain enable/disable, exaggeration, health handshake
│  │  ├─ tileHealth.ts                 # per-source load/error/timeout state machine
│  │  ├─ fallbackRaster.ts             # georeferenced committed hillshade image source
│  │  ├─ cameraController.ts           # home/reset/fly-to/focus reach, reduced-motion handling
│  │  ├─ layerRegistry.ts              # declarative LayerSpec[]: id, source, paint order, legend
│  │  ├─ map.module.css                # canvas, fallback banner, map controls, attribution
│  │  └─ layers/
│  │     ├─ flood.ts                   # current/outgoing fill layers, filters, rAF crossfade
│  │     ├─ risk.ts                    # risk-zone fill/outline + district risk outline
│  │     ├─ admin.ts                   # district/state outlines, district hit-test
│  │     ├─ rivers.ts                  # river lines by source/order
│  │     ├─ hotspots.ts                # P1 hotspot circles + selection
│  │     ├─ assets.ts                  # P1 critical-facility circles
│  │     ├─ gauges.ts                  # P1 virtual-gauge points
│  │     └─ selection.ts               # selected district/hotspot highlight
│  ├─ panels/
│  │  ├─ OverviewPanel.tsx             # scenario state, stage/area, model limitations short form
│  │  ├─ LayersPanel.tsx               # visibility, opacity, base mode, badges (P0-07)
│  │  ├─ RiskPanel.tsx                 # ranked district table, score drivers, coverage caveat
│  │  ├─ ProvenancePanel.tsx           # source → stage → file, licences, assumptions, NOT A FORECAST
│  │  ├─ StoryPanel.tsx                # P1 flood chronology phases
│  │  ├─ CrossSectionPanel.tsx         # P1 transect selector + cross-section chart
│  │  ├─ ImageryPanel.tsx              # P1 imagery compare PiP + mask
│  │  ├─ GaugePanel.tsx                # P1 virtual gauge list + synthetic stage readout
│  │  ├─ panels.module.css             # tables, score bars, badges, provenance list
│  │  └─ RiskRow.tsx                   # one ranked district row; keyboard selectable
│  ├─ charts/
│  │  ├─ ChartGrid.tsx                 # three synced charts + shared playhead; owns uPlot instances
│  │  ├─ TelemetryChart.tsx            # uPlot wrapper: series, threshold, units, cursor sync
│  │  ├─ CrossSectionChart.tsx         # P1 SVG ground/water/depth profile
│  │  ├─ ChartDataTable.tsx            # accessible table toggle for every chart
│  │  └─ charts.module.css             # chart grid, legend, tooltip, table styles
│  ├─ timeline/
│  │  ├─ TimelineDock.tsx              # dock layout: controls + scrubber + charts
│  │  ├─ PlaybackControls.tsx          # play/pause, prev/next, speed, keyboard bindings
│  │  ├─ TimelineScrubber.tsx          # 12-stop slider with phase labels and aria-valuetext
│  │  ├─ usePlayback.ts                # rAF accumulator, tab-hidden pause, reduced-motion guard
│  │  └─ timeline.module.css           # dock, scrubber, phase ticks, transport buttons
│  ├─ state/
│  │  ├─ timelineStore.ts              # step/playing/speed/peak; the single source of truth
│  │  ├─ layerStore.ts                 # per-layer visibility/opacity/base mode
│  │  ├─ panelStore.ts                 # active panel, last panel, mobile sheet open
│  │  ├─ selectionStore.ts             # selected district/hotspot/reach, hover
│  │  └─ urlState.ts                   # P1 hash encode/decode: step, panel, layers, camera
│  ├─ data/
│  │  ├─ types.ts                      # TS types mirroring every schema in DATA-PIPELINE.md
│  │  ├─ schemas.ts                    # zod schemas for manifest, scenario, frames, risk, series
│  │  ├─ loadData.ts                   # tiered fetch, zod parse, integrity/size checks, cache
│  │  ├─ useDataset.ts                 # React hook exposing load state + typed dataset
│  │  ├─ format.ts                     # km², m, mm/day, step labels, locale-stable numbers
│  │  ├─ labels.ts                     # class badges, legend labels, phase labels
│  │  └─ attribution.ts                # source attribution strings shown in UI
│  └─ styles/
│     ├─ tokens.css                    # colour, spacing, type, depth palette, risk palette
│     └─ global.css                    # reset, base typography, focus-visible, reduced motion
├─ tests/
│  ├─ e2e/
│  │  ├─ m0.spec.ts                    # 12 steps, play, peak, charts, risk, provenance
│  │  ├─ m1.spec.ts                    # P1 panels, share state, layer parity
│  │  ├─ fallback.spec.ts              # abort DEM/imagery routes; overlays still render
│  │  └─ a11y.spec.ts                  # axe scan + keyboard-only timeline/panel path
│  └─ unit/
│     ├─ timelineStore.test.ts         # clamping, step, play/pause, speed
│     ├─ format.test.ts                # units, labels, no NaN/undefined
│     └─ schema.test.ts                # fixtures parse/reject
└─ pipeline/
   ├─ README.md                        # offline pipeline quickstart + stage list
   ├─ pyproject.toml                   # package metadata; installable with pip install -e pipeline
   ├─ requirements.txt                 # pinned Python deps (numpy, scipy, rasterio, shapely, ...)
   ├─ config/
   │  ├─ aoi.json                      # bbox, CRS, resolution, Assam filter, max channel distance
   │  ├─ scenario.json                 # 12 steps, rainfall/stage arrays, model parameters
   │  ├─ sources.json                  # exact source URLs, licences, attribution, timeouts
   │  └─ transects.json                # cross-section endpoints (P1 UI; consumed by build-series)
   ├─ src/baanh_pipeline/
   │  ├─ __init__.py                   # package marker/version
   │  ├─ cli.py                        # argparse subcommands; one per stage; exit codes
   │  ├─ config.py                     # load/validate JSON configs; frozen dataclasses
   │  ├─ geo.py                        # CRS helpers, geodesic area, reprojection, winding
   │  ├─ fetch_terrain.py              # Terrarium tile fetch + cache + index
   │  ├─ fetch_boundaries.py           # geoBoundaries IND ADM2 fetch + Assam filter
   │  ├─ fetch_rivers.py               # Overpass query with Natural Earth 10m fallback
   │  ├─ build_dem.py                  # decode/mosaic/warp 90 m DEM + hillshade WebP
   │  ├─ build_admin.py                # district/state GeoJSON, centroids, simplification
   │  ├─ build_rivers.py               # clip/merge/classify river lines; channel line output
   │  ├─ burn_rivers.py                # rasterize channels, lower them, write burned DEM
   │  ├─ hand.py                       # nearest-channel EDT, HAND, distance, metadata
   │  ├─ inundation.py                 # stage masks, connectivity, depth bands, polygons
   │  ├─ risk.py                       # risk zones, district scores, hotspots
   │  ├─ series.py                     # monsoon series + cross-sections
   │  ├─ assets.py                     # P1 Overpass facilities + peak exposure join
   │  ├─ gauges.py                     # P1 virtual stations + synthetic stage series
   │  ├─ schemas.py                    # output schema constants and validation helpers
   │  ├─ validate.py                   # V01–V20 checks, writes validation-report.json
   │  └─ publish.py                     # manifest hashes/sizes, provenance aggregation, atomic copy
   └─ tests/
      ├─ test_hand.py                  # synthetic DEM/channel fixtures; known HAND values
      ├─ test_inundation.py            # connectivity, no-channel cells, monotonic growth
      ├─ test_risk.py                  # formula bounds, zero-area district, coverage
      └─ test_schema.py                # every published file validates against schema
```

### Generated, never committed

```text
pipeline/cache/terrain/{z}/{x}/{y}.png   # raw Terrarium tiles
pipeline/cache/boundaries/*.json         # raw geoBoundaries response
pipeline/cache/rivers/*.geojson          # raw Overpass / Natural Earth responses
pipeline/work/dem-90m.tif                # warped DEM
pipeline/work/dem-burned.tif             # DEM with channels lowered
pipeline/work/channels-90m.tif           # rasterized channel mask
pipeline/work/channel-distance-90m.tif   # metres to nearest channel
pipeline/work/hand-90m.tif               # HAND raster; -9999 = no channel within limit
pipeline/work/hand-meta.json             # counts, clamp/no-data statistics
pipeline/work/inundation-stack.npz       # depth[step, y, x] float32 for risk/series
pipeline/work/provenance/*.json          # per-stage provenance fragments
```

`pipeline/work/` and `pipeline/cache/` are gitignored. The app never reads them.

---

## 6. Component and state contract

### 6.1 Principles

- **One clock.** `timelineStore.step` is the only time value. Charts, map layers, panel readouts
  and the scrubber derive from it. No component keeps a second step state.
- **Map updates bypass React.** `MapCanvas` subscribes to the timeline/layer stores with Zustand
  transient subscriptions and mutates MapLibre directly. React renders only when panel content,
  selection, or a displayed readout changes.
- **The layer registry is declarative.** Adding a layer means adding a `LayerSpec` and a style
  layer builder, not editing five components.
- **Data is validated once.** `loadData.ts` fetches and parses with zod; components receive typed
  objects and never parse raw JSON.
- **No hidden global.** Stores are module singletons imported by name; no context provider is
  required for map access.

### 6.2 Timeline store

```ts
type Speed = 0.5 | 1 | 2;

interface TimelineState {
  step: number;                 // 0..11, clamped
  playing: boolean;
  speed: Speed;
  stepCount: number;            // 12, from scenario.json
  peakStep: number;             // 7, from flood-summary.json
  framesReady: boolean;         // flood source loaded; Play disabled until true
  setStep: (step: number, source?: 'user' | 'playback' | 'url' | 'init') => void;
  stepBy: (delta: number) => void;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  setSpeed: (speed: Speed) => void;
  setFramesReady: (ready: boolean) => void;
}
```

- `setStep` clamps to `[0, stepCount - 1]` and is a no-op if unchanged.
- `usePlayback` owns the timer: `requestAnimationFrame`, accumulator threshold
  `1200 ms / speed`, stops at the last step (does not loop), pauses on `visibilitychange`.
  Calling `play()` while parked at the last step restarts at step 0 before running.
- Autoplay is off on load. If `prefers-reduced-motion: reduce`, `play()` steps once per explicit
  press rather than running an animation; the scrubber and step buttons still work.
- Subscribers: `MapCanvas` (flood filters + crossfade), `ChartGrid` (cursor), `TimelineDock`
  (readout), `OverviewPanel` (stage/area), `StatusBar` (frame readiness).
- Emits no DOM events. `data-step` on the app root is for tests/analytics-free debugging.

### 6.3 Layer registry

```ts
type LayerId =
  | 'imagery' | 'hillshade' | 'districts' | 'rivers'
  | 'flood' | 'flood-outline' | 'risk-zones'
  | 'hotspots' | 'assets' | 'gauges' | 'selection';

type LayerClass = 'source' | 'derived' | 'scenario' | 'synthetic' | 'reference';

interface LayerSpec {
  id: LayerId;
  label: string;                 // UI string, e.g. "Scenario flood extent"
  group: 'Base' | 'Hazard' | 'Context' | 'Exposure';
  kind: 'raster' | 'fill' | 'line' | 'circle' | 'image';
  sourceId: string;              // MapLibre source id
  styleLayerIds: string[];       // one or more layers, in paint order
  paintOrder: number;            // lower = closer to the basemap
  defaultVisible: boolean;
  defaultOpacity: number;        // 0..1
  class: LayerClass;             // drives the badge in Layers/Provenance
  legend: 'depth' | 'risk' | 'river' | 'facility' | 'none';
  dataPath?: string;             // public/data path for provenance and lazy loading
  requiresTiles?: 'dem' | 'imagery';
  minZoom?: number;
}
```

`layerRegistry.ts` exports `LAYERS: LayerSpec[]` sorted by `paintOrder` and helpers
`byId`, `styleLayerOrder`. `LayersPanel` renders only registry entries; it never knows MapLibre
ids. `layerStore` holds `{ visible: Record<LayerId, boolean>; opacity: Record<LayerId, number>;
baseMode: 'satellite' | 'hillshade' | 'relief' }` and actions `toggle`, `setOpacity`,
`setBaseMode`, `reset`. Visibility of `flood-outline` follows `flood`; `selection` is controlled
by `selectionStore`, not the panel.

### 6.4 Panel router

```ts
type PanelId = 'overview' | 'layers' | 'risk' | 'provenance'
             | 'story' | 'cross-section' | 'imagery' | 'gauges';

interface PanelState {
  activePanel: PanelId;
  lastPanel: PanelId;            // default 'overview'
  mobileSheetOpen: boolean;
  open: (panel: PanelId) => void;
  close: () => void;             // returns to lastPanel, never null
  setMobileSheetOpen: (open: boolean) => void;
}
```

- `PanelRouter` receives no props; it reads `activePanel` and renders one panel. The map is never
  unmounted.
- On panel change, focus moves to the panel `<h2 tabindex="-1">`; ESC closes a modal/PiP (P1)
  and returns focus to the trigger.
- P1 panels are code-split with `React.lazy`; M0 only ships overview, risk, provenance, layers.
- `urlState.ts` (P1) serialises `{step, panel, layers, camera}` into the hash; invalid payloads
  fall back to defaults without throwing.

### 6.5 Camera controller

```ts
interface CameraController {
  mount(map: Map): void;
  reset(): void;                                  // home view, 900 ms ease or jump
  focusDistrict(districtId: string): void;        // fit bounds with padding, pitch 55
  focusReach(reachId: 'brahmaputra-mid' | 'brahmaputra-upper' | 'tributary'): void;
  setMode(mode: '3d' | 'flat'): void;             // flat = pitch 0, terrain off
  onStatus(cb: (s: CameraStatus) => void): () => void;
  destroy(): void;
}

interface CameraStatus {
  center: [number, number];
  zoom: number;
  pitch: number;
  bearing: number;
  idle: boolean;
}
```

- Home: center `[92.60, 26.35]`, zoom `6.8`, pitch `52`, bearing `-20`.
- Bounds: `[[88.90, 23.30], [96.80, 28.80]]`; `maxPitch 75`, `minZoom 5.5`, `maxZoom 13`,
  `renderWorldCopies: false`.
- `focusDistrict` reads the district bbox from `assam-districts.geojson`; if the district is
  very large, padding is clamped so the camera does not zoom out past 9.
- Reduced motion: `flyTo` becomes `jumpTo`; no auto-orbit; terrain exaggeration stays but
  playback fades are shortened.
- Emits status only on `moveend`/`idle`, not every frame; `StatusBar` shows coordinates and zoom.
- Selection store → controller subscription: selecting a district flies once; re-selecting the
  same district does not re-fly.

### 6.6 Component contracts

| Component | Receives | Emits / mutates | Notes |
|---|---|---|---|
| `App` | nothing | renders shell | Owns error boundary and dataset load gate. |
| `TopBar` | scenario label, current step, framesReady | `open('provenance')`, `play/pause`, P1 share | No step logic beyond display. |
| `MapCanvas` | dataset, stores | map events → `selectionStore`; tile health → `StatusBar` | Creates map once; destroys on unmount only. |
| `MapCanvas` → `flood.ts` | `step`, `stepCount`, `framesReady` | filter/paint updates | Crossfade uses two fill layers; see §7.4. |
| `LayerRegistry` | none | `LayerSpec[]` | Pure data; no React. |
| `LayersPanel` | `LAYERS`, `layerStore` | `toggle`, `setOpacity`, `setBaseMode` | Opacity slider 0–100, keyboard step 5. |
| `TimelineDock` | `timelineStore` | user actions | Contains scrubber, transport, charts. |
| `TimelineScrubber` | `step`, `stepCount`, labels | `setStep` | `role="slider"`, arrows/Home/End/PageUp/Down. |
| `usePlayback` | store | `setStep` on tick | No `setInterval`; no timer when paused/hidden. |
| `ChartGrid` | series, summary, `step` | none (cursor readout) | Three uPlot instances share cursor; click sets step. |
| `TelemetryChart` | series, threshold, unit, step | `onPickStep` | Data table toggle; no animation of data beyond cursor. |
| `RiskPanel` | `district-risk.json`, risk zones | `selectionStore.selectDistrict` | Ranked list; drivers; coverage caveat. |
| `ProvenancePanel` | `provenance.json`, `scenario.json` | none | Renders source→stage→file; labels. |
| `OverviewPanel` | summary at `step`, scenario | `play`, `open('risk')` | Model limitations short form. |
| `StatusBar` | tile health, data version, framesReady | `retryTiles` | Never blocks the map. |
| `cameraController` | map, selection | status callbacks | Imperative class, not a React hook. |
| `CameraController` consumers | `selectionStore` | `focusDistrict` | One flight per selection id. |

### 6.7 Data load contract

`loadData.ts` exposes `loadDataset(): Promise<Dataset>` and a small state machine:
`idle → manifest → critical → frames → ready | error`. It reads `manifest.json` first, validates
`schema_version` and `dataset_version`, then fetches in tiers:

1. **critical** (`≤3.5 MB` raw): scenario, provenance, districts, state, rivers, district-risk,
   monsoon series.
2. **animation** (`≤7.6 MB` raw): flood-frames, flood-summary, risk-zones. Frames must be parsed
   and added to the map as one source before `framesReady = true`; Play is disabled until then.
3. **optional** (P1): cross-sections, hotspots, assets, gauges.
4. **failure only**: `assam-hillshade.webp` if terrain/imagery tiles fail.

Every payload is parsed with the matching zod schema. On failure the app shows a blocking
"Data contract error" panel naming the file and path; it does not render partial geometry.
Hashes in the manifest are verified by CI (`scripts/check-data.mjs`), not in the browser (hashing
10 MB at startup is not worth the delay).

---

## 7. Rendering plan

### 7.1 Terrain and basemap

| Item | Choice |
|---|---|
| DEM source | `raster-dem` from `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`, `encoding: 'terrarium'`, `tileSize: 256`, `maxzoom: 12` |
| Terrain | `map.setTerrain({ source: 'dem', exaggeration: 1.35 })`; disabled when DEM health is `offline` |
| Satellite | `raster` source from Esri World Imagery `.../tile/{z}/{y}/{x}`, `tileSize: 256`, `maxzoom: 17`, attribution required |
| Hillshade | MapLibre `hillshade` layer over both base modes: illumination direction `315`, exaggeration `0.32`, shadow/highlight colours from tokens |
| Sky | `sky` layer with horizon/fog colours matched to the page background; no sun animation |
| Fallback relief | `image` source from `public/data/basemap/assam-hillshade.webp`, `coordinates` = AOI corners in Mercator; visible only when imagery is offline |
| Projection | Web Mercator (MapLibre default). Analysis is done in EPSG:32646; rendering reprojects the committed WGS84 GeoJSON. |

The terrain exaggeration is fixed at 1.35. It is a readability choice, **not** a vertical scale
claim; the UI says “vertical exaggeration 1.35×” in the Layers panel. No 3D trees, buildings, or
extruded assets: they would imply data we do not have.

### 7.2 Layer ordering (bottom → top)

MapLibre draws in style-layer array order. `paintOrder` in the registry matches this table.

| # | Style layer | Source | Paint |
|---|---|---|---|
| 1 | `background` | — | page background colour |
| 2 | `satellite` | Esri raster | opacity 1; hidden in `hillshade`/`relief` mode |
| 3 | `fallback-relief` | committed image | visible only when imagery offline |
| 4 | `hillshade` | DEM | opacity 0.30 over satellite, 0.55 in hillshade mode |
| 5 | `district-fill` | districts | very light neutral fill at low zoom; no risk colour |
| 6 | `risk-zones-fill` | risk-zones | class colour, opacity 0.32 |
| 7 | `risk-zones-line` | risk-zones | class colour, 0.8 px, opacity 0.55 |
| 8 | `flood-fill-outgoing` | flood-frames | step `n−1`, fading 0.62 → 0 over 220 ms |
| 9 | `flood-fill-current` | flood-frames | step `n`, fading 0 → 0.62 over 220 ms |
| 10 | `flood-outline` | flood-frames | step `n`, `#d9f3ff`, 0.9 px, opacity 0.85 |
| 11 | `rivers` | rivers | `#7cc7e8`, width by `order`, opacity 0.85 |
| 12 | `district-line` | districts | risk-class tint at 0.7 px; selected 2 px `#ffffff` |
| 13 | `state-outline` | state | `#dfe9ef`, 1.4 px, opacity 0.7 |
| 14 | `hotspots` (P1) | hotspots | amber circle + white halo; radius by `area_km2` |
| 15 | `assets` (P1) | assets | facility glyph circles, muted until zoom ≥ 8 |
| 16 | `gauges` (P1) | gauges | cyan rings; selected larger |
| 17 | `selection` | districts/hotspots | white outline + soft halo |
| 18 | `sky` | — | horizon/fog |

District names and hotspot labels are DOM `Marker`s positioned from committed centroids, not
MapLibre symbol layers, so no glyph endpoint is required. They are hidden below zoom 6.5 to avoid
clutter and have `pointer-events: none` except hotspot labels.

### 7.3 Painting the risk layer

- `risk-zones.geojson` features carry `risk_class` ∈ `low | moderate | high | very_high` and
  `risk_score`. Fill uses a `match` expression on class, not a continuous ramp, so the legend is
  discrete and colour-blind-safe. The palette is ordered light-teal → amber → deep magenta; the
  panel repeats the class name in text so colour is never the only signal.
- District risk is a **line tint** on `district-line`, not a second choropleth; two filled
  choropleths would fight the flood layer. The ranked table carries the precise scores.
- Risk zones are drawn **under** the flood fill so the water remains the primary reading. The
  opacity 0.32 keeps the zones visible through the semi-transparent flood.

### 7.4 Animating flood extent between steps without re-tiling

All 12 extents live in **one** GeoJSON source, `flood-frames`, loaded once. Each feature has a
numeric `step` (0–11) and a `depth_band`. The two fill layers are filtered to the current and
previous step:

```text
flood-fill-current   filter: ["==", ["get", "step"], <step>]
flood-fill-outgoing  filter: ["==", ["get", "step"], <previousStep>]
```

On a step change:

1. Set the outgoing filter to the old step and the current filter to the new step. No source
   data changes, no `setData`, no source removal/re-add, and therefore no GeoJSON re-parse or
   tile rebuild.
2. Animate `fill-opacity` on the two layers with a single `requestAnimationFrame` loop over
   220 ms: outgoing `0.62 × (1 − t)`, current `0.62 × t`. `setPaintProperty` only changes a
   uniform; it does not touch geometry.
3. At `t = 1`, the outgoing layer is left at opacity 0 and the current layer at 0.62.

Depth band colours are a `match` expression on `depth_band`, so a step change never recolours
features. The outline layer switches filter immediately at the start of the crossfade.

Why this satisfies the no-re-tiling requirement: MapLibre’s GeoJSON source is tiled internally
once when added. Filter and paint changes re-evaluate features already in the source; they do
not enqueue source/tile work. The app preloads the source before enabling Play, so the first
press of Play cannot trigger a fetch. Camera movement still causes normal raster tile requests;
that is not the animation path.

The trade-off is memory: all frames are resident (~6.5 MB raw). That is accepted and budgeted in
§8. If the budget is exceeded, the fallback is to reduce depth bands from four to three, not to
stream frames during playback.

### 7.5 Hotspots, gauges, facilities

- **Hotspots (P1):** `circle` layer, `circle-radius` interpolated from `area_km2` (4–11 px),
  `circle-color` `#f2a33a`, `circle-stroke-color` `#1a1207`, `circle-stroke-width` 1.2,
  `circle-pitch-alignment: 'map'` so they sit on the terrain. Clicking selects and opens a small
  callout with `reason`, `hand_m`, `distance_to_channel_m`. They are labelled **derived
  inundation hotspots**, never “breach”.
- **Gauges (P1):** small rings, not pins; selected ring gets a 2 px stroke and a DOM label with
  the synthetic stage at the current step. No gauge datum is claimed.
- **Facilities (P1):** muted circular glyphs by facility type, shown only at zoom ≥ 8 and when
  the layer is on; selected facility shows OSM name (or “unnamed”) and peak depth. A completeness
  note is always visible in the panel.

### 7.6 Camera and lighting

- Camera: constrained orbit, no roll, `dragRotate` enabled, `touchPitch` enabled, keyboard
  pan/zoom retained. Home view is deliberately oblique (pitch 52) so relief reads immediately.
- Lighting: static hillshade key light from the north-west (315°) at 45° altitude, implemented
  via MapLibre hillshade parameters. There is **no time-of-day model**; a sun slider would imply
  solar simulation we do not run. The sky is a visual frame, not a lighting computation.
- Selection flight: `flyTo` 900 ms, `essential: true` only when reduced motion is off; padding
  80 px, max zoom 9.5 for large districts.
- On terrain failure, pitch is clamped to 0–20 and the camera controller reports `mode: 'flat'`;
  the fallback relief image remains georeferenced and the overlays stay aligned.

### 7.7 Tile-health and fallback matrix

`tileHealth.ts` tracks each raster source: `unknown → loading → ok | degraded | offline`.
`offline` after 6 s with no successful tile, or >50% errored tiles after 8 s; `degraded` on
partial failure. A manual “Retry tiles” action resets the state.

| DEM | Imagery | What renders | Status copy |
|---|---|---|---|
| ok | ok | 3D terrain + satellite + hillshade + all overlays | “Terrain and imagery live” |
| ok | offline | 3D hillshaded terrain + all overlays | “Imagery offline · hillshade terrain” |
| offline | ok | Flat satellite (pitch ≤ 20) + all overlays | “3D terrain offline · flat satellite” |
| offline | offline | Committed relief image + all overlays, flat | “Offline basemap · committed relief” |
| any | any, data file failed | Error panel naming the file; no partial map | “Data contract error” |

If WebGL2 is unavailable, the app renders a static relief image with an accessible data table and
a clear “WebGL2 required for the 3D view” message; it does not pretend to be interactive.

---

## 8. Performance budget

Target machine: 2020-class 4-core laptop, integrated GPU, 1440×900, Chromium 120+, cold cache,
20 Mbps. Budgets are acceptance targets, not measured claims.

### 8.1 Frame and interaction

| Metric | Budget |
|---|---|
| Pan/orbit frame time | 16.7 ms target; p95 ≤ 22 ms |
| Longest frame during playback | ≤ 50 ms |
| Step change (filter + crossfade start) | ≤ 12 ms main-thread |
| Panel switch | ≤ 100 ms; P1 panels lazy-loaded |
| Initial map ready | ≤ 2.5 s |
| First meaningful paint (shell + terrain + districts) | ≤ 3.0 s |
| Play enabled (all frames parsed) | ≤ 5.0 s |
| Memory after full load | ≤ 400 MB tab RSS |
| Draw calls | ≤ 60 |
| Visible vector features | ≤ 8,000 at peak |

### 8.2 Transfer and data

| Bucket | Cap (raw) | Cap (gzip) |
|---|---|---|
| JS initial | — | ≤ 350 KB |
| CSS | — | ≤ 25 KB |
| Critical data (scenario, districts, state, rivers, risk summary, series, manifest) | ≤ 3.5 MB | ≤ 1.2 MB |
| Animation data (flood frames, summary, risk zones) | ≤ 7.6 MB | ≤ 1.9 MB |
| Optional/fallback (hillshade, cross-sections, hotspots, assets, gauges) | ≤ 3.0 MB | ≤ 0.9 MB |
| Total committed data | ≤ 14 MB | ≤ 4.5 MB |

First meaningful paint is well under the reference’s ~8 MB because the animation bucket is
fetched after the shell and terrain render. The Play button stays disabled with a progress
label until the bucket is parsed. The fallback hillshade is fetched only on tile failure, not on
the happy path.

Per-file hard caps enforced by `scripts/check-data.mjs` and pipeline validation:

| File | Cap |
|---|---|
| `flood/flood-frames.geojson` | 6.5 MB |
| `admin/assam-districts.geojson` | 1.2 MB |
| `admin/assam-state.geojson` | 0.15 MB |
| `hydro/assam-rivers.geojson` | 1.0 MB |
| `risk/risk-zones.geojson` | 0.9 MB |
| `risk/district-risk.json` | 0.15 MB |
| `risk/hotspots.geojson` | 0.10 MB |
| `series/monsoon-series.json` | 0.05 MB |
| `series/cross-sections.json` | 0.20 MB |
| `basemap/assam-hillshade.webp` | 1.5 MB |
| `assets/critical-facilities.geojson` | 1.0 MB |
| `gauges/virtual-gauges.geojson` | 0.10 MB |
| manifest + provenance + scenario + validation | 0.25 MB combined |

### 8.3 Geometry and rendering tactics

- Analysis grid 90 m; flood polygons simplified at 75 m tolerance, minimum ring area 0.02 km²,
  coordinates quantised to 5 decimal places (~1 m). Risk zones simplified at 100 m, minimum
  0.05 km². Districts simplified at 150 m; state at 200 m; rivers at 50 m.
- Depth bands: four (`0–0.5`, `0.5–1.5`, `1.5–3.0`, `3.0+` m). If the flood frame cap is
  exceeded, drop to three bands (`0–1`, `1–3`, `3+`) rather than coarsening geography.
- No `fill-antialias` on the outgoing layer; no symbols; no extrusions; no shadows beyond
  hillshade. `maxzoom` on raster sources prevents over-fetching.
- DPR capped at 2; on `devicePixelRatio > 2` the app renders at 2 and lets CSS upscale.
- Panels are code-split; uPlot is imported only when the dock mounts.
- Frames are parsed in a worker-free path because 6.5 MB at 12 steps is acceptable; if parsing
  exceeds 400 ms, the loader chunks features by step and adds them in two batches before
  `framesReady` (still one source before Play). This is a builder fallback, not the default.

### 8.4 Load milestones and degradation

| Milestone | Target | If missed |
|---|---|---|
| HTML + JS shell | 1.2 s | Show skeleton shell; log budget warning in dev. |
| Map first frame | 2.5 s | Show committed relief + “loading terrain”; keep controls responsive. |
| Critical overlays | 3.5 s | Panels still render text from summary; map waits. |
| Frames ready / Play enabled | 5.0 s | Play disabled with progress; step buttons still work if frames loaded partially (not expected). |
| Tile health decision | 6 s | Switch to fallback matrix in §7.7. |
| Full load | 6.0 s | Lazy P1 assets remain off the critical path. |

No layout shift after the shell mounts: the rail, dock and canvas have fixed grid tracks at each
breakpoint.

---

## 9. Deploy (static host)

- **Host:** GitHub Pages, project site at `https://<owner>.github.io/baanh/`.
- **Workflow:** `.github/workflows/pages.yml` on push to `main` (and manual dispatch):
  `actions/checkout` → `actions/setup-node` with Node 24 → `npm ci` → `npm run build` →
  `actions/upload-pages-artifact` with `dist/` → `actions/deploy-pages`.
- **Base path:** `vite.config.ts` sets `base: '/baanh/'` for both dev and the Pages build, so
  routes and data URLs are identical locally and in production. All data fetches use
  `import.meta.env.BASE_URL + 'data/...'`, never a root-absolute `/data/...`.
- **No secrets, no environment variables at runtime.** The only remote requests are the two
  probed tile hosts (AWS Terrarium, Esri World Imagery). No fonts, analytics, or APIs.
- **Caching:** Vite hashed JS/CSS are immutable. Data is versioned by `dataset_version`; the
  loader appends `?v=<version>` to data URLs so a Pages deploy cannot serve a stale mix.
- **Rollback:** redeploy a previous tagged commit; data and app version are checked together via
  the manifest’s `app_min_version`.
- **Local/offline build:** after one `npm ci` on a connected machine, `npm run build` needs no
  network. Runtime offline behaviour is the §7.7 fallback; the build itself never downloads data.
- **No SPA rewrite needed:** there are no routes. A direct hit on `/baanh/` is the only entry;
  P1 hash state is client-side. `404.html` is not required.
- **Verification after deploy:** `npm run verify:m0` against the local preview, plus a manual
  check that the Pages URL loads with the correct base path and that the two tile hosts are the
  only third-party origins in the network panel.

---

## 10. Accessibility baseline

Target: **WCAG 2.2 AA** for the shell, timeline, panels and charts. The map is a visualisation,
not the only path to the information.

- **Timeline:** `TimelineScrubber` is a real `role="slider"` with `aria-valuemin=0`,
  `aria-valuemax=11`, `aria-valuenow`, and `aria-valuetext` such as “Step 7 of 12, 25 August,
  peak, scenario stage 6.0 metres”. Arrow keys step, Home/End jump, PageUp/PageDown jump by 3.
  Space toggles play only when focus is not in an input. Play/pause has an accessible name that
  changes with state.
- **Live updates:** a polite `aria-live` region announces step changes at most once per 400 ms
  (not every animation frame): “Step 7, peak, 6.0 metres, 8,412 square kilometres inundated”
  (numbers read from data, not hard-coded).
- **Charts:** each chart is a `<figure>` with `<figcaption>`, axis labels with units, and a
  “Show data table” toggle rendering an accessible table. uPlot’s canvas gets
  `aria-hidden="true"`; the table is the accessible equivalent. Colour is not the only encoding:
  line styles differ and the legend names units.
- **Map:** container is `role="img"` with a dynamic `aria-label` summarising the current view
  (“Oblique terrain map of Assam; scenario flood extent at step 7 of 12”). A “Map data” section
  in Overview gives the same numbers as text. All map-only interactions have panel equivalents:
  step via timeline, district selection via the risk table, layer toggles via the Layers panel.
- **Contrast and colour:** text ≥ 4.5:1, large text ≥ 3:1, UI boundaries ≥ 3:1. Depth palette is
  ordered and colour-blind-safe (light cyan → teal → blue → indigo) and accompanied by numeric
  depth bands. Risk classes use text labels and ordered luminance, not red/green alone.
- **Focus:** visible 2 px focus ring, logical DOM order (top bar → map skip link → rail → dock),
  focus trap only in the P1 PiP/mobile sheet, ESC closes it and restores focus.
- **Motion:** honour `prefers-reduced-motion`. No autoplay; playback fade is 0 ms and camera
  flights become jumps. No parallax or looping decoration.
- **Targets and zoom:** interactive targets ≥ 24×24 px; layout works at 200% zoom and at 360 px
  width (P1 mobile sheet); no horizontal scroll at 320 px for text panels.
- **Tables:** ranked risk table has `<caption>`, column `scope="col"`, sortable columns via
  buttons (P1), and a text explanation of the score weights.
- **No time limit:** playback can be paused indefinitely; the app never expires a session.
- **Testing:** `tests/e2e/a11y.spec.ts` runs axe on the default, Layers, Risk and Provenance
  panels and a keyboard-only path from load → step 7 → risk row → provenance. Critical axe
  violations fail M1; serious violations are triaged and listed in the audit.

---

## 11. Honesty and provenance enforcement

These are product requirements, not documentation decoration.

1. **Every layer has a class badge** in Layers and in the panel that presents it:
   `SOURCE` (terrain/rivers/districts/facilities), `DERIVED` (HAND, risk, hotspots, exposure),
   `SCENARIO` (flood extent, stage), `SYNTHETIC` (rainfall, virtual gauges), `REFERENCE` only
   when a documented external figure is quoted (none in P0/P1).
2. **Provenance panel** lists source name, URL, licence, fetch date, pipeline stage(s), command,
   output path, and class for every dataset. `provenance.json` is the single source for this.
3. **Model assumptions and limitations** are shown next to the model, not only in docs:
   uniform stage applied to mapped channels; the stage is a synthetic sum of a main-stem anomaly
   and a backwater allowance, not a routed water surface; no levee/embankment failure; no flow
   routing or hydrodynamic solver; no calibration to a gauge; no population or asset loss model;
   the hydrograph is synthetic; mapped rivers are incomplete; HAND is a terrain index, not a
   forecast.
4. **No invented identifiers or statistics.** The data schemas have no fields for agency id,
   incident number, casualties, affected people, relief camp, or deployment ETA. UI copy avoids
   claiming a forecast, an official warning, or a live feed: positive forms of “forecast”,
   “official”, and “warning issued” are banned, while the required disclaimer “not a forecast”
   is explicitly allowed. The stage threshold is called a **scenario threshold**, not a danger
   level.
5. **`scripts/check-honesty.mjs`** fails the build if built output or data contains banned
   strings/fields (`casualties`, `deaths`, `displaced`, `affected_persons`, `incident_id`,
   `agency_id`, `relief_camp`, `warning issued`, a positive `operational/official/flood
   forecast`, or a positive claim that a CWC/NDRF feed was used) or a data feature lacks a valid
   `class`. A bare `forecast` is accepted only inside `not a forecast` / `never a forecast` or
   the boolean key `not_a_forecast`; negative disclaimers such as “no CWC gauge record” are
   allowed. All other false positives are handled by an explicit allowlist, not by weakening the
   check.
6. **Synthetic series are labelled at the point of use**, not only in a footnote: chart titles
   include “(synthetic)”, the stage readout says “scenario stage”, and the Overview panel states
   that no gauge record was used.
7. **No real-person data** of any kind. OSM facility names (P1) are organisational/place names
   from a public map, not personal data, and are attributed.

---

## 12. Explicit non-goals and limits

- Not a forecast, nowcast, warning, or evacuation tool. No claim of operational fitness.
- No hydrodynamic routing, levee breaching, sediment, or tidal/backwater solver. The model is
  HAND-threshold based; this is stated in-app.
- No live gauge, satellite tasking, drone, aircraft, or social-media feed.
- No population, casualty, displacement, economic-loss, or relief-deployment data.
- No user accounts, saved projects, backend, database, or server-side rendering.
- No multi-event comparison in the first build; the scenario is one declared composite.
- No 30 m analysis, no globe view, no 3D buildings/trees, no time-of-day lighting.
- No editing or drawing tools; the app is a read-only explainer.

If a future request needs a paid key, a backend, or a dataset that is not among the five probed
sources, the correct response is to stop and report, not to synthesize a plausible substitute.
