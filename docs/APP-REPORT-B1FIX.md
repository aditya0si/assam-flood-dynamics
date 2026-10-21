# App report — B1 fix (R1–R5)

**Scope:** playback, tile health, initial framing, probe hooks, portable scripts.
**Data:** `public/data/` and `pipeline/` were not modified. The app still reads only the committed
dataset.
**Build:** Vite 7.3.7, React 19, TypeScript strict, MapLibre GL 5.

---

## 1. R1 — playback must advance

### Root cause (named mechanism)

The transport was gated on a single boolean, `framesReady`, and **the only writer in the old code was
inside `map.on('load', …)`**:

```ts
map.on('load', () => {
  setTerrain(map, true);
  const controller = createFloodController(...);
  void controller.start(initialStep).then((ready) => {
    useTimelineStore.getState().setFramesReady(ready); // <-- only writer
  });
});
```

MapLibre's `load` event is not "the style document is ready". It fires from `Map._render()` only when
`Map.loaded()` is true, and `Map.loaded()` walks:

```text
Map.loaded()
  -> Style.loaded()
     -> every TileManager.loaded()
        -> every in-view tile must be state "loaded" or "errored"
```

So a remote DEM or Esri tile that is still pending — or a host that never settles — defers `load`
indefinitely. In the probe, imagery was unavailable and the in-view tile set did not settle within
the 7 s wait. `framesReady` therefore stayed `false`:

- `PlaybackControls` rendered the Play button with `disabled={!framesReady}`;
- the store's `play()` early-returns on `!framesReady`;
- synthetic `Space` calls `toggle()` → `play()`, which is the same no-op.

That is why the counter stayed at `1/12` with **zero console errors**: no exception was thrown, the
store was simply never allowed to start. `prefers-reduced-motion` was not the cause (that path would
have moved one step, not zero); the separate reduced-motion branch was a second way to stop the
transport, and it has also been removed.

A second latent freeze path was removed at the same time: `setFramesReady(ready)` also accepted
`false` when the first local PNG failed to decode, permanently disabling Play for a local-image
error.

### Fix

1. **Readiness moved off `load`.** Scene setup now starts on `style.load` / `styledata` and checks
   for the presence of the background layer and flood source. Those events describe the style
   document; they do not wait for remote tiles.
2. **The transport is marked ready when the local frame controller is installed**, not when the
   first PNG decodes and never on a remote tile. A failed local frame sets the existing frame-warning
   chip but leaves Play usable.
3. **The clock moved into the store** as `tick(deltaMs)`. The rAF hook only feeds elapsed time. The
   store owns the one-step-per-interval rule, the accumulator, and the stop at the last step. This is
   what makes the required test possible without a browser or a map.
4. **Reduced motion no longer freezes playback.** The `prefersReducedMotion` early `pause()` in
   `usePlayback` is gone; the flood crossfade already collapses to an instant opacity switch in
   `flood.ts`. Reduced motion shortens the animation, not the transport.

### Test (`npm test`, Node test runner)

`src/state/timelineStore.test.ts` covers:

- play from 0 advances `0→11` one step at a time and stops at the end;
- pause holds the step across subsequent ticks;
- next/prev move exactly one and clamp at both ends;
- play on the last step rewinds to 0;
- play is refused until the local frame source is ready;
- a long tick advances one visible step rather than skipping.

All 13 tests in the store + health suites pass.

---

## 2. R2 — one tile-health source of truth

### What changed

There is now one runtime record, `useTileHealthStore` in `src/state/tileHealthStore.ts`. The map's
`createTileHealthTracker` writes its outcomes; the map chip, the status bar and `window.__baanh` read
the same record. The old `MapCanvas` local `health` state and `App` `health` state are gone, so two
indicators cannot diverge.

Both indicators call the same pure `tileHealthCopy(snapshot)` from `src/map/tileHealthState.ts`.
The overlay and status bar therefore render one string, not two independent interpretations.

The old failure mode had two parts. First, `MapCanvas` and `App` each kept a `health` copy, so the
two indicators had separate render paths. Second, the old tracker declared a source offline after a
single 6 s timer whenever it had not yet seen a success, then hid the imagery layer as a fallback —
which stopped the layer from making further requests, so an unverified `offline` could never recover
even when the host was answering. The new machine requires confirmed failures (or two full windows),
counts pending requests as `degraded`, and leaves the imagery layer mounted so a late success is
observed and recovers it.

### State machine (per source: `dem`, `imagery`)

`dem` is driven by the terrain source (`aws-terrarium-dem`), not by the separate hillshade source:
a hillshade tile cannot make detached 3D terrain look live.

Inputs are actual request outcomes only:

- `sourcedataloading` with a tile → `pending += 1`;
- `sourcedata` with a tile → `pending -= 1`, `successes += 1`, error streak reset;
- `error` with a tracked `sourceId` → `pending -= 1`, `errors += 1`, streak `+1`;
- `sourcedataabort` → `pending -= 1`;
- a 6 s window increments `timeoutRounds`.

| successes | condition | status |
|---|---|---|
| 0 | no outcome, no window yet | `loading` |
| 0 | 1–2 errors, or one elapsed window without a success | `degraded` |
| 0 | 3 errors, or two full windows with no success | `offline` |
| ≥ 1 | fewer than 3 consecutive errors | `live` |
| ≥ 1 | 3 consecutive errors | `degraded` |
| any | a later success | back to `live` |

The invariant that closes the reviewer's contradiction: **a source with at least one success can
never be reported `offline`**, and `live` is never emitted before a tile resolves. A recovering host
is observed because the imagery layer is left mounted (failed tiles paint nothing and reveal the
committed hillshade); only terrain is detached while the DEM is offline, and it is restored on
recovery.

Overall level (used by `data-tile-health`):

| dem | imagery | overall |
|---|---|---|
| `offline` | `offline` | `offline` |
| any `offline` / `degraded` | anything | `degraded` |
| `live` | `live` | `live` |
| anything else (including loading) | anything else | `degraded` |

The copy table in `tileHealthState.ts` turns those states into the single strings both indicators
show, including `Imagery offline · hillshade terrain` only when imagery has genuinely earned
`offline` and `Terrain and imagery live` only when both sources are `live`.

---

## 3. R3 — frame the subject

### Before → after

| | Before | After |
|---|---|---|
| Camera bounds | manifest/state bbox `[89.55, 23.95, 96.15, 28.15]` | AOI v2 core belt `[90.15, 25.95, 95.0, 27.55]` |
| Initial centre / zoom | bbox centre / 6.0 | belt centre / 7.2 |
| Pitch / bearing | 55° / -15° | 38° / -12° |
| `FLOOD_OPACITY` | 0.62 | 0.80 |

`AOI_CORE_BOUNDS` is the Brahmaputra flood-prone belt, derived offline from the committed peak frame
(`step-07.png`): the 5th–95th percentile of wet pixels in the main valley, with the Barak-valley tail
excluded. The state box is about 308,000 km²; the new subject box is about 85,000 km², **≈3.6×
smaller in area**. The 10,010.6 km² peak therefore rises from **≈3.2 % of the framed box** to **≈11.7 %**,
before the lower pitch and the raised opacity make the belt read as a body of water rather than a
thin blue line. No data file or pipeline value was touched.

---

## 4. R4 — probe hooks

Installed on the map container (`div` with `role="img"`):

| Hook | Value / timing |
|---|---|
| `data-ready` | `"false"` at mount, `"true"` after the style is parsed and the first local frame is applied (2 s fallback if the frame cannot decode) |
| `data-step` | current store step, updated on every step change |
| `data-frame-file` | frame-index file actually applied to the map sources, e.g. `frames/step-07.png`; it does not change until the visible frame changes |
| `data-tile-health` | shared overall level: `live` / `degraded` / `offline` |

`window.__baanh` is installed once per map and is read-only:

```ts
window.__baanh = {
  step,        // store step
  frameFile,   // last frame applied to the map
  isPlaying,   // store playing flag
  tileHealth,  // shared overall health level
};
```

Each field is a getter over the live store/ref, and the object is frozen with a non-writable window
property, so a reviewer can assert state without reaching into React fibers and cannot overwrite it.
Stepping changes `data-frame-file` and `window.__baanh.frameFile` as soon as the new image is handed
to the map sources.

---

## 5. R5 — portable scripts

| Script | Command |
|---|---|
| `npm run dev` | `vite` |
| `npm run build` | `tsc -p tsconfig.json --noEmit && vite build` |
| `npm run preview` | `vite preview` |
| `npm run dev:sandbox` | prebundle + `scripts/vite-run.mjs` |
| `npm run build:sandbox` | `tsc` + `scripts/vite-run.mjs build` |
| `npm run preview:sandbox` | `scripts/vite-run.mjs preview` |
| `npm test` | Node test runner, with a strict test type-check |

`vite.config.ts` only enables the React/MapLibre prebundle aliases when `BAANH_SANDBOX=1`, which only
`scripts/vite-run.mjs` sets. Plain Vite never resolves `node_modules/.vite-deps` and never loads the
in-process esbuild shim. The vendored `esbuild-wasm` package and `scripts/esbuild-loader.mjs` remain
committed for the sandbox path only. `README.md` explains the split in one sentence.

---

## 6. Commands run (actual exit codes)

| Command | Exit | Result |
|---|---|---|
| `npx tsc -p tsconfig.json --noEmit` | **0** | strict type-check clean |
| `npm test` | **0** | 13 tests, 13 pass (store playback + health state machine) |
| `npm run build:sandbox` | **0** | 160 modules transformed; `dist/` produced |
| `npm run dev:sandbox` | started | Vite ready in 792 ms; `/` 200, `/src/main.tsx` 200, `/data/manifest.json` 200, `/data/flood/frames/step-07.png` 200 (254,791 B) |
| `npm run preview:sandbox` | started | built app served at `/baanh/`; `/baanh/` 200, `/baanh/data/manifest.json` 200, `/baanh/data/flood/frames/step-07.png` 200 (254,791 B) |
| `npm run build` (plain) | **1 in this workspace** | Vite itself starts, but its esbuild child is denied: `Error: spawn EPERM` while loading the config. On a machine that permits child processes this is the required plain `vite` build. |
| `npm run dev` (plain) | **1 in this workspace** | same harness denial: `spawn EPERM` |

The plain-script failure is the workspace process sandbox, not the app: the old `vite-run.mjs`
monkey-patched `child_process.exec` and registered the WASM shim precisely because this harness
cannot spawn esbuild. That shim is now out of the default path; `build:sandbox` proves the same
source builds here.

I could not run the real-Chromium acceptance pass in this workspace: Chromium still dies at
`mojo/public/cpp/platform/platform_channel.cc:112` (`Access is denied`) before a page is created, so
the runtime items (Play in the browser, live tile fetch, S07 screenshot) remain for the reviewer. The
store clock, readiness decoupling, shared health machine, probe hooks and production build are
covered by the tests/source/build above.

---

## 7. Files changed

**App:** `src/state/timelineStore.ts`, `src/state/tileHealthStore.ts` (new),
`src/map/tileHealthState.ts` (new), `src/map/tileHealth.ts`, `src/map/MapCanvas.tsx`,
`src/map/flood.ts`, `src/map/mapConfig.ts`, `src/map/map.module.css`, `src/shell/StatusBar.tsx`,
`src/App.tsx`, `src/timeline/usePlayback.ts`, `src/vite-env.d.ts`.

**Tests:** `src/state/timelineStore.test.ts`, `src/map/tileHealth.test.ts`.

**Tooling / docs:** `package.json`, `vite.config.ts`, `scripts/vite-run.mjs`, `tsconfig.json`,
`tsconfig.test.json`, `README.md`, `docs/APP-REPORT-B1FIX.md`.

**Untouched:** `public/data/**`, `pipeline/**`.
