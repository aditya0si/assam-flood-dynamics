# Baanh — Assam flood-dynamics scenario explorer

A static Vite + React + MapLibre explorer for a synthetic, terrain-derived Assam monsoon
scenario. It reads committed JSON and PNG data under `public/data/`; it is **not a forecast**,
a warning service, or a record of a real event.

## Commands

```bash
npm install
npm run dev       # plain Vite dev server
npm run build     # tsc --noEmit, then plain vite build
npm run preview   # plain vite preview
npm test          # vitest store/health unit tests
```

`dev:sandbox` / `build:sandbox` keep the in-process esbuild shim for the restricted Windows
workspace; normal development and CI use plain `vite` and never touch the vendored shim.

## Data and provenance

All values come from the committed dataset (`data/manifest.json`, `data/flood/flood-summary.json`,
`data/flood/frame-index.json`). The app does not fetch a live feed, invent values, or fall back to
partial geometry. The two remote tile hosts (AWS Terrarium DEM and Esri World Imagery) are optional
visual basemaps; the committed hillshade and the local flood frames render without them.
