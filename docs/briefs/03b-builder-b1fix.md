# Builder brief — B1 fix: playback, tile health, framing, portability, probe hooks

Read `docs/REVIEW-06-b1-runtime.md`. Your build is green and the data binding is correct — the app
was probed in real Chromium and S00/S07 read exactly what `flood-summary.json` says. These five
items are what stands between it and B2.

## R1 — Playback must advance (blocker)

Clicking `Play scenario playback` at S00 leaves the counter at `1/12` for 7 s; synthetic `Space`
does nothing. Find the cause, do not paper over it with a CSS animation. Add a unit test on the
store: play from 0 advances 0→11 one step at a time and stops at the end; pause holds; next/prev
move exactly one. If `prefers-reduced-motion` is what stops it, reduce the motion, not the
behaviour — the control must still play.

## R2 — One tile-health source of truth (blocker)

The overlay says `Imagery offline · hillshade terrain` while the status bar says
`Terrain and imagery live`, on a page where an Esri tile fetch returns 200. Derive health from
actual request outcomes only; render it once and share it. Never claim `live` before a tile
resolves; never claim `offline` while requests succeed.

## R3 — Frame the subject

Initial camera on the flood-prone belt (`aoi_v2` core), not the state bbox; reduce pitch; review
`FLOOD_OPACITY` (0.62). A 10,000 km² flood must read at a glance. Do not touch the data.

## R4 — Probe hooks

Map container: `data-ready`, `data-step`, `data-frame-file`, `data-tile-health`; plus
`window.__baanh = { step, frameFile, isPlaying, tileHealth }` kept current.

## R5 — Portable default scripts

`npm run dev` / `npm run build` must be plain `vite`; move the sandbox shim to
`dev:sandbox` / `build:sandbox` and explain it in one line in `README.md`. The vendored
esbuild-wasm package stays, out of the default path.

## Acceptance (reviewer runs all five)

1. `npm run build` → exit 0 via plain vite.
2. Load the app: `data-ready="true"`, `data-tile-health` agrees with a real tile fetch, no console
   errors.
3. Click S00 → Play → step advances within ~2 s and continues; counter/pixels change; pause holds.
4. `window.__baanh.step` / `frameFile` track the visible frame; stepping changes `frameFile`.
5. Screenshot at S07 shows the flood belt filling a meaningful part of the viewport, not a smear.

Report in `docs/APP-REPORT-B1FIX.md`: root cause of R1 (name the mechanism, not a guess), the
health-state machine, before/after framing, and commands with exit codes.
