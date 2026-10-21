# Review 06 — B1 verdict: build green, runtime not

Reviewer: Hermes. Target: phase B1, commit `1490e85`. Probed in real Chromium against the built
`dist/` served under its configured base path `/baanh/`.

## What passed, verified at runtime

| Check | Evidence |
|---|---|
| App mounts, no console errors | 2 canvases (map + uPlot), `window.__errs` empty after 9 s |
| `NOT A FORECAST` + class badges | in the top bar and on every data surface |
| 12 timeline steps | steps S00–S11 as `data-step` buttons, counter `1/12` … `8/12` |
| **Values are data-bound** | S00 shows `0.3 m` / `1833.9 km²` / `2.3 %` / `5.9 %`; S07 shows `3.7 m` / `10010.6 km²` / `12.8 %` / `32.2 %` — exactly `flood-summary.json` |
| uPlot chart | renders with the playhead on the active step |
| Tile-failure fallback | imagery unavailable in the probe, and the map still rendered 3D hillshade terrain with all overlays |
| Frame rasters are honest | step-07 PNG = 309,751 opaque px × (180 m)² = **10,036 km²**, matching the 10,011 km² summary |

So the build, the data contract and the honesty chrome are real. Two runtime defects are not.

## Defects (blocking B2)

### R1 — Playback does not advance (P0-04 blocker)

Repro: load the app → click the `S00` step button → click `Play scenario playback` → wait 7 s.
Observed: counter stays `1/12`. Same with a synthetic `Space` keydown. Zero console errors, so the
button click is handled and the store likely flips `isPlaying`, but nothing advances.

Hypotheses to check, in order: the play loop reads `isPlaying` through a transient subscription that
never re-subscribes; an effect keyed on a selector that is not in the dependency list; a timer that
is cleared by the same render that starts it; `prefers-reduced-motion` defaulting to true in the
probe browser and silently disabling playback (if so, it must not disable the control — reduced
motion should lengthen the step, not freeze the app).

Required: a unit test asserting the store advances step by step from 0 to 11 and stops at the end,
plus a runtime assertion path the reviewer can use (see R4).

### R2 — Tile status contradicts itself

Observed on the same screen: map overlay badge **"Imagery offline · hillshade terrain"** while the
status bar reads **"Terrain and imagery live"**, and a page-level `fetch` of an Esri tile returns
**200**. One component is reporting a stale or unverified state. A status strip that can lie
undermines the whole provenance premise.

Required: one health source of truth, derived from actual tile request outcomes (success/failure
counts since load), applied to both indicators; no string that claims "live" before a tile has
resolved, and none that claims "offline" while requests are succeeding.

### R3 — Initial framing hides the subject (design, not correctness)

The flood occupies **3.2 % of the frame PNG** and roughly that order of the viewport, because the
camera fits the whole state including the hill districts. At S07 the app's own headline number is
10,010 km² and the viewer sees a thin blue smear. Fix in the B2 pass: initial camera on the
flood-prone belt (the `aoi_v2` core, not the state bbox), pitch reduced, and consider raising
`FLOOD_OPACITY` from 0.62. Do not change the data to make the picture louder.

## Deviation to clean up (R5)

`package.json` routes `dev` and `build` through `scripts/vite-run.mjs`, which monkey-patches
`child_process.exec` and registers `vendor/esbuild-inprocess` (esbuild-wasm). That was justified by
*this* sandbox, which cannot spawn esbuild's binary — but it is now the shipped default for a
portfolio repo, and a reviewer on a normal machine will see a bespoke runner where `vite` is
expected.

Required: `npm run dev` / `npm run build` use plain `vite`; the sandbox path becomes `dev:sandbox` /
`build:sandbox`, documented in `README.md` with one sentence explaining why it exists. The vendored
shim stays for reproducibility, out of the default path.

## New testability requirement (R4)

Expose stable, non-visual hooks so a reviewer (or CI) can assert state without reaching into React
fibers:

- map container: `data-ready="true"` once the style has loaded and the first frame is drawn,
  `data-frame-file`, `data-step`, `data-tile-health="live|degraded|offline"`;
- `window.__baanh = { step, frameFile, isPlaying, tileHealth }` updated on change, read-only.

These are cheap, they do not leak data, and they convert my three runtime checks into one-liners.

## Verdict

B1 is **not accepted as the base for B2** until R1 and R2 are fixed. R3, R4 and R5 may land in the
same run. Data, build and honesty chrome are accepted.
