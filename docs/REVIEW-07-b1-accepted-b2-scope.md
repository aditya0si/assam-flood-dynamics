# Review 07 — B1-fix accepted; B2 scope

Reviewer: Hermes. Target: B1-fix (committed by reviewer as `775f3db`; the builder left the tree
dirty, which I will not repeat — future briefs require a commit).

## Accepted, with runtime evidence

| Item | Evidence |
|---|---|
| **R1 playback** | From S00, Play advanced `1/12 → 2/12 → … → 7/12` at ~1.3 s/step with `frameFile` tracking `step-00 → step-06`; pause held at `7/12` for 2.5 s with `isPlaying=false`. Store unit tests: 13/13 pass, including 0→11 sequential, stop-at-end, long-tick no-skip. |
| **R2 tile health** | One state machine, one claim on screen (`Terrain and imagery live`, `data-tile-health="live"`). With `server.arcgisonline.com` and both elevation hosts blocked at the CDP layer: `data-tile-health="offline"`, status text `offline · committed relief`, hillshade fallback renders, and playback still steps. No contradictory badge. |
| **R3 framing** | Camera fits the flood-prone belt, pitch 38°, opacity 0.80. S00→S07 screen diff rose from 2.57 % to 4.67 % of pixels. |
| **R4 hooks** | `data-ready`, `data-step`, `data-frame-file`, `data-tile-health` and read-only `window.__baanh` all present and correct. |
| **R5 portability** | **Clean clone → `npm install` (101 pkgs, 51 s) → plain `npm run build` → exit 0 in 11.4 s.** The sandbox shim is no longer in the default path. |
| No regressions | Zero console errors across load, playback, stepping and the blocked-tile reload. `public/data/` untouched. |

One harness lesson recorded: several tabs in one browser session exhausted WebGL contexts and made
the map report `data-ready=false` with an empty frame — an artifact of my probe, not the app. Probes
now run in a dedicated session.

## Still weak (B2 work, not B1 failures)

The flood reads as a blue web rather than crisp extent because the shallow class `#9ecae1` is too
close to the river colour, and the hillshade competes at valley scale. Depth-class discrimination is
the product's core claim, so B2 must fix the palette and de-emphasise the basemap.

## B2 scope — the analysis rail and the rest of M0

1. **Right rail** with four panels, all data-bound:
   - `Risk` — district ranking (33 rows, sorted, top rows showing score, class, and the three
     drivers: inundated area, duration, peak depth). Top row must read **Sivasagar 71.9**.
   - `Provenance` — source → stage → file for terrain, boundaries, rivers, flood, risk; the
     "NOT A FORECAST" statement and the model-assumption list.
   - `Methodology` — HAND screening model in plain language, the bathtub depth convention and its
     conservative-shallow bias, synthetic-vs-derived labels.
   - `Layers` (P0-07) — visibility + opacity for flood, risk zones, rivers, districts, hillshade;
     base mode imagery ↔ hillshade. No map re-init.
2. **Risk overlay** — `risk-zones.geojson` (1,747 features) styled by class with opacity control;
   `hotspots.geojson` (20) as small markers with a name/score popover.
3. **Charts** — three synced series (inundated area, scenario stage, rainfall) with a shared
   playhead, plus a **depth-decile strip** for the current step from `delay_deciles`.
4. **District labels** — DOM markers for the top-risk districts (no glyph endpoint), hidden below a
   zoom threshold.
5. **Visual fixes** — river colour must not read as flood; shallow flood class needs separation from
   both river and hillshade; attribution strip must not collide with the health pill.
6. **Extend the probe hooks** — `window.__baanh.panel`, `.layers` (visible ids + opacity),
   `.districtTop` so the rail and layer controls are assertable without DOM scraping.

## Acceptance (reviewer runs)

- Panels: Risk top row `Sivasagar / 71.9`, 33 rows, no `NaN`; Provenance lists ≥5 datasets with
  file paths; Methodology contains the bathtub-bias sentence.
- Layers: toggling flood off removes the extent (screen diff > 5 %), toggling back restores it;
  opacity change alters pixels; base mode switch swaps imagery for hillshade.
- Charts: three series present, playhead follows the step; decile strip shows six values matching
  `delay_deciles` at S07 (`0.3809 / 0.863 / 2.354 / 3.7 / 3.7 / 3.7`).
- No console errors; playback still advances; `public/data/` untouched; everything committed.
