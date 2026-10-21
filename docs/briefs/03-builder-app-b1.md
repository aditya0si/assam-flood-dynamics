# Builder brief — phase B1: app shell, 3D map, animated flood timeline

The data set is accepted: `public/data/` is complete (28 files, 4.84 MB, `validation-report.json`
= pass, 31/31 checks, manifest hashes verified). You are now the app builder.

Read: `docs/ARCHITECTURE.md` (§3 P0 table, §4 stack, §5 file tree, §6 state contracts, §7 rendering)
— **as amended by `REVIEW-04` §C3** (flood layer is raster image sources, not vector bands), then
`public/data/flood/frame-index.json` and `public/data/flood/flood-summary.json` for the real field
names. Build against the actual JSON, not against the doc's assumed names.

## Scope of this run (B1 only)

1. Scaffold the Vite 7 + React 19 + TypeScript app at the repo root per `ARCHITECTURE.md` §5.
   Dependencies from §4 only. `npm install` once; commit `package-lock.json`.
2. **MapCanvas**: MapLibre GL JS 5 with
   - AWS Terrarium `raster-dem` (z12 render cap) as terrain, terrain on, ~1.4× exaggeration;
   - Esri World Imagery raster basemap over the AOI;
   - committed `basemap/assam-hillshade.webp` as an `image` source underneath, so the AOI is never
     blank when tile hosts fail;
   - 12 flood frames as **two `image` sources** (`cur`/`next`) with an opacity crossfade on step
     change — no source rebuild, no re-tiling;
   - districts outline + rivers from the committed GeoJSON (thin, legible, no labels yet);
   - camera: fit the AOI bbox, pitch ~55°, bearing ~-15°, terrain-relative.
3. **Timeline store + dock**: 12 steps from `flood-summary.json`; play/pause/prev/next/scrub; speeds
   0.5×/1×/2×; Space toggles play, ArrowLeft/Right step, Home/End jump. All state in Zustand with a
   transient subscription so playback does not re-render the map tree.
4. **Readouts, from data only**: step label, stage (m), inundated area (km²), share of Assam and of
   the flood-prone area, and the `class` badge (`SCENARIO`). One uPlot chart in the dock: inundated
   area over the 12 steps with the playhead cursor. No hard-coded numbers anywhere.
5. **Honesty chrome**: a persistent `NOT A FORECAST` chip in the top bar, and a `SYNTHETIC` badge on
   the rainfall/stage series once it appears. These are P0-08/P0-09 requirements, not decoration.
6. `docs/APP-REPORT-B1.md`: commands run with exit codes, files created, deviations, and what is
   deliberately absent (right rail panels, risk ranking, remaining charts, tests → B2/B3).

## Constraints

- No backend, no router, no CSS framework, no web fonts, no icon package (inline SVG), no paid key.
- `public/data/` is read-only input. Do not regenerate, edit or re-emit it.
- Every number on screen comes from a committed JSON field; no literal `10010` in the source.
- The app must still render and animate if both tile hosts are unreachable (hillshade + frames).
- Windows: pass native `C:/...` paths to node; do not use `/tmp` or `/c/...` in scripts.

## Acceptance for B1 (reviewer will run these)

1. `npm install` → exit 0; `npm run build` → exit 0, `dist/` produced.
2. `npm run dev` serves on 5173 and `GET /` returns 200.
3. In a headless browser: a WebGL canvas mounts, **no console errors**, the top bar shows
   `NOT A FORECAST`, exactly 12 timeline steps exist, and stepping to S07 changes the displayed
   step label, stage (`3.7`), and area (`10010.6` km²) — values matching the summary JSON.
4. Playback advances steps without a page reload and without a console error.
5. `git status` clean after your commits; no changes under `public/data/` or `pipeline/`.

## Stop and report instead of improvising

A dependency fails to install twice; MapLibre cannot load a frame image source from a relative path
under Vite (say so and propose the fix rather than switching to vector); or a required field is
missing from the committed JSON (name the file and field — do not invent it).
