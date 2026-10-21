# App report — B2: analysis rail, overlays, charts and hooks

**Scope:** REVIEW-07 B2 items 1–6. The right rail (Risk / Provenance / Methodology / Layers),
risk-zone and hotspot overlays, three synced charts plus the depth-decile strip, DOM district
labels, the palette/attribution fixes, and the extended `window.__baanh` probe.
**Data:** every new panel value, chart point, overlay and label comes from the committed
`public/data/` JSON/GeoJSON. `public/data/**` and `pipeline/**` were not modified.
**Build:** Vite 7, React 19, TypeScript strict, MapLibre GL 5, uPlot.

---

## 1. Data contract

`src/data/schemas.ts` now validates the B2 payloads instead of treating them as untyped blobs:

| File | Validation added |
|---|---|
| `provenance.json` | dataset version, entries, source/stage/file fields, licences, nullable fetched dates |
| `risk/district-risk.json` | 33 ranking rows, weights, reference values, counts, finite scores, unique ranks |
| `series/monsoon-series.json` | rainfall/stage/backwater series, points, threshold |
| `risk/risk-zones.geojson` | all 1,747 features and their risk properties |
| `risk/hotspots.geojson` | 20 point features and their hotspot properties |
| `flood/flood-summary.json` | per-step `wet_cells`, `delay_deciles`, `max_depth_m`, `mean_depth_m` |
| `scenario.json` | model parameters, component filter, assumptions and limitations |

`loadDataset()` fetches those files in the existing start-up batch and rejects a mismatched
`dataset_version` or `scenario_id`. The committed data was parsed against every new schema: **9/9
files pass**. The ranking check also verifies `counts.total == districts.length`, that every score
is finite, and that no rank is duplicated.

---

## 2. Right rail — four data-bound panels

`src/shell/RightRail.tsx` hosts `PanelRouter`, with tab buttons for **Risk / Provenance /
Methodology / Layers**. The active tab is a real ARIA tab with arrow/Home/End keyboard movement.
Panel changes move focus to the panel heading. The rail sits beside the map in the shell grid; the
map is never unmounted or re-created.

### Risk

- Renders **all 33 rows** from `district-risk.json`, sorted by `rank` (then score).
- Top row: **Sivasagar / 71.9**.
- Each row shows score, class, and the three drivers with committed values: peak flooded area
  (km²), mean duration (days), p90 peak depth (m). Driver names come from the data's `drivers`.
- Shows the score weights/reference values and a `valid_area_share` caveat for incomplete districts.
- Clicking a row selects the district; `MapCanvas` flies to its committed centroid. The caveat
  says this is scenario-conditional terrain exposure, not expected loss.

### Provenance

- Renders the five required datasets (terrain, boundaries, rivers, flood, risk) as
  **source → stage chips → committed file paths**.
- Includes the visible `NOT A FORECAST` statement, source/licence details, and the full
  `scenario.assumptions` list.
- Stage chips carry the pipeline command in their tooltip. File paths are the committed
  `data/...` paths.

### Methodology

- Plain-language HAND screening model, with model name/version, depth formula, burn depth and
  component filter read from `scenario.model`.
- The **bathtub** depth convention and its **conservative-shallow** bias are stated explicitly:
  `depth = stage − max(HAND, 0)`, with the committed explanation that a cell below the burnt datum
  reports the full stage because no levee/bathymetry data exists.
- Lists synthetic vs scenario vs derived vs source series at the point of use, plus the district
  weights and the first five committed model limitations.

### Layers

- Six registry rows: flood, risk zones, rivers, districts, hillshade, hotspots. Each has visibility
  and a 0–100 opacity control; the five required layers are all present.
- Base mode switches **Imagery ↔ Hillshade**. Visibility/opacity/base changes mutate the existing
  style layers through the layer store; no map re-init.
- The layer registry (`src/map/layerRegistry.ts`) is the single list used by the panel, the map
  application code and the probe.

---

## 3. Overlays and labels

- **Risk zones:** `risk-zones.geojson` is a MapLibre GeoJSON source with a class-driven fill and
  line layer. The fill uses a `match` on `risk_class` (low / moderate / high / very_high), drawn
  beneath the flood raster. Opacity and visibility are controlled by the Layers panel.
- **Hotspots:** the 20 committed points render as small circles sized by `area_km2` and drawn above
  the flood. Clicking one opens a MapLibre popup with the district name + hotspot id, **rank score**
  (`rank N of 20`, plus the district risk score), area, HAND, distance to channel, reason, peak
  depth, and the explicit “backwater pocket, not an embankment breach” caveat.
- **District labels:** DOM `Marker`s (no glyph endpoint) for the top 10 districts by `rank`, using
  the committed `centroid_lon`/`centroid_lat`, name and score. They are hidden below zoom **6.0**
  and when the district layer is off; they never block map drag/click.

---

## 4. Three synced charts and the decile strip

`src/charts/ChartGrid.tsx` replaces the single B1 area chart:

1. **Inundated area** (`flood-summary.steps[].inundated_area_km2`),
2. **Scenario stage above local drainage** (`flood-summary.steps[].stage_m`), with a dashed
   threshold from `monsoon-series.threshold`,
3. **Rainfall** (`monsoon-series.series[id=rainfall].points[].value`).

Each is a uPlot instance with the same x scale (0–11), a shared cursor sync key, its own amber
playhead driven by `timelineStore.step`, click-to-step, and a screen-reader table containing all
three series. **Three chart rows and three series are present in rendered markup.**

`DepthDecileStrip` reads the current `flood-summary.steps[step].delay_deciles` and renders six
cells, p10/p25/p50/p75/p90/p95. At **S07** the rendered values are exactly
`0.3809 / 0.863 / 2.354 / 3.7 / 3.7 / 3.7`.

---

## 5. Palette and attribution fixes

| Problem | Change |
|---|---|
| River colour read as flood water | Rivers are now warm sand `#cbb58a`, width/opacity retained; they no longer share the shallow flood's blue. |
| Shallow flood competed with hillshade | Hillshade exaggeration was reduced to `0.22`, shadow/highlight/accent desaturated, and its opacity default is `0.28`; flood rasters get a small saturation/contrast lift. |
| Risk overlay needed class colours | Discrete low/moderate/high/very-high palette (teal → amber → coral → magenta), repeated as text in the panel. |
| Attribution collided with the health pill | The health/status pill is bottom-centre above the control row; MapLibre attribution is pinned bottom-right with a reserved gutter and 7 px inset. The expanded attribution also sits below the pill. |

The committed flood PNG palette is untouched: class colours still come from `frame-index.json`,
and the shallow class `#9ecae1` remains the data's colour. The separation is achieved in the
surrounding map layers (river and hillshade), not by rewriting data.

---

## 6. Extended `window.__baanh`

The read-only probe is still frozen on `window`. Existing fields are unchanged; B2 adds:

| Hook | Value |
|---|---|
| `panel` | Active panel id: `risk`, `provenance`, `methodology`, `layers` |
| `layers.visible` | Visible registry ids, e.g. `['flood', 'risk-zones', ...]` |
| `layers.opacity` | Per-layer 0–1 opacity map |
| `layers.baseMode` | `'imagery'` or `'hillshade'` |
| `districtTop` | Top-ranked district object: `name`, rounded `score` (71.9), raw `riskScore` (71.944), `scoreLabel`, `riskClass`, `rank`, `districtId`, `areaShare`, `durationDays`, `peakDepthM`, and `toString()` → name |

All are getters over the live stores/dataset, so panel and layer changes are visible without DOM
scraping. `districtTop` returns `null` if the ranking is empty.

---

## 7. Verification (actual exit codes)

| Check | Exit | Result |
|---|---|---|
| `npx tsc -p tsconfig.json --noEmit` | **0** | strict type-check clean |
| `npm test` | **0** | 13/13 tests pass |
| Committed-data schema parse (9 files) | **0** | all nine B2 payloads validate; 33 districts, top Sivasagar 71.944; S07 deciles match |
| MapLibre style validator on the generated B2 style | **0** | 12 layers, 11 sources, no validation errors |
| SSR render of the rail with the real dataset | **0** | 46,526 chars; 33 district rows; Sivasagar and 71.9 present; no `NaN` |
| SSR render of Provenance | **0** | 5 datasets and the five required file paths present; `NOT A FORECAST` and assumptions present |
| SSR render of Methodology | **0** | “Bathtub convention”, “conservative-shallow” and synthetic/derived labels present |
| SSR render of Layers | **0** | 6 layer controls; flood label present |
| SSR render of ChartGrid / DepthDecileStrip | **0** | 3 chart rows; 6 decile cells; S07 values `0.3809 / 0.863 / 2.354 / 3.7 / 3.7 / 3.7` |
| `npm run build:sandbox` | **0** | 175 modules transformed; production `dist/` built in 13.1 s |
| `npm run dev:sandbox` + Node fetch | **200** | `/`, main/RightRail/ChartGrid modules, risk-zones (853,816 B) and hotspots (9,003 B) |
| `npm run preview:sandbox` + Node fetch | **200** | `/baanh/`, manifest, provenance, risk-zones and hotspots |
| `npm run build` (plain) | **1** | Vite starts, then its esbuild child is denied: `spawn EPERM` (workspace sandbox, same as B1) |

The sandbox production build warning is limited to two Rollup comment-annotation notices inside
`zod`; it is not an app error.

---

## 8. Browser acceptance limitation

The real-Chromium pass could not be executed in this workspace. Chrome terminates before page
creation with:

```text
FATAL:mojo/public/cpp/platform/platform_channel.cc:112
Check failed: . : Access is denied. (0x5)
```

This is the same harness restriction recorded in B1. Consequently I did **not** fabricate console
output, screen-diff numbers, or a visual S07 screenshot. The style validator, SSR panel renders,
schema checks, preview fetches, type-check and production build above cover the data/UI structure;
the reviewer should run the B2 layer, playback and no-console checks in an unrestricted Chromium.

---

## 9. Files changed

**New:** `src/shell/RightRail.tsx`, `src/shell/PanelRouter.tsx`, `src/panels/RiskPanel.tsx`,
`src/panels/RiskRow.tsx`, `src/panels/ProvenancePanel.tsx`, `src/panels/MethodologyPanel.tsx`,
`src/panels/LayersPanel.tsx`, `src/panels/panels.module.css`, `src/charts/ChartGrid.tsx`,
`src/charts/DepthDecileStrip.tsx`, `src/state/panelStore.ts`, `src/state/layerStore.ts`,
`src/state/selectionStore.ts`, `src/map/layerRegistry.ts`, `src/data/risk.ts`.

**Modified:** `src/App.tsx`, `src/charts/TelemetryChart.tsx`, `src/data/format.ts`,
`src/data/loadData.ts`, `src/data/schemas.ts`, `src/data/types.ts`, `src/map/MapCanvas.tsx`,
`src/map/flood.ts`, `src/map/mapConfig.ts`, `src/map/mapStyle.ts`, `src/map/map.module.css`,
`src/shell/shell.module.css`, `src/styles/global.css`, `src/timeline/TimelineDock.tsx`,
`src/timeline/timeline.module.css`, `src/vite-env.d.ts`.

**Untouched:** `public/data/**`, `pipeline/**`.
