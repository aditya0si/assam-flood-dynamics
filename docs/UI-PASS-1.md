# UI pass 1 — shipped design and 1C closeout

Baseline: the seven measured faults in `docs/briefs/UI-PASS-1.md`, before `2444418`.
Design implementation: `2444418`. This report documents shipped code, not a new screenshot review.
The 1C changes tighten acceptance and reduce repeated browser initialization; they do not redesign the UI.

## Before / after

| Measured fault before | Shipped after | Evidence / limit |
| --- | --- | --- |
| Map not primary; competing panels and obscured district rows | Compact expandable legend; right rail 380px default, 520px expanded, 44px collapsed; analytics dock 290px default / 90px collapsed at desktop | `shell.module.css`, `timeline.module.css`; 1C measures actual map rect height / innerHeight at 1440×900, >=0.60 default and >=0.75 with both rails explicitly collapsed. These are acceptance thresholds, not newly measured local browser results. |
| Legend contradicted map colours | Four ordered cyan-to-indigo entries in `DEPTH_PRESENTATION`; decoded flood pixels recoloured from that same mapping, legend uses `depthPresentationColor`; no saturation/contrast adjustment | `depthPalette.ts`, `mapStyle.ts`, `MapCanvas.tsx`; 1C reads visible swatches with `getComputedStyle(...).backgroundColor` and compares RGB strings derived from the imported constant. Source PNGs unchanged. |
| Six warnings competed for attention | One persistent header warning; four class types remain dot-and-word badges; data ages remain at panel/surface level rather than each chart | `TopBar.tsx`, `DataBadge.tsx`, panel headers; 1C checks unfiltered `getByText('NOT A FORECAST')` count 1 across every analysis tab and with collapsed rails, plus direct text-node count. |
| One-volume typography, mostly small spaced capitals | Main metrics 34px; secondary metrics 20px; section titles 15px; primary copy 13px; metadata 11px; system sans and tabular numerals | Actual scale below. This is not a claim that every legacy selector was normalized: shell retains 17/18px and 11.5px styles. |
| Amber did three jobs | Warning gets dedicated vermilion `#e2553d`; badge classes have distinct quiet colours; stage series and threshold become slate `#b8cbd3` | Legacy `--amber*` names now resolve to neutral colours. Existing status-warn shadow still contains an amber RGBA literal; no claim of zero amber literals across all CSS. |
| Formula clipped and chart labels collided | Formula wraps; compact risk rows expose five ranks/scores; chart hosts have explicit 76px height, axes on each small multiple, plot-aware playhead/threshold coordinates | Existing M0 row/header/formula checks preserved; UI steps keep rank/score and panel bounds assertions. Not a blanket guarantee for every viewport. |
| Flat S00 charts looked broken | Snapshot explicitly says “Onset — no accumulated change yet.”; plotted series and values remain unchanged | UI acceptance checks the timeline analytics region at S00. No invented observations or artificial chart variation. |

## Tokens actually shipped

Sources: `src/styles/tokens.css`, `src/shell/dataBadge.module.css`,
`src/map/depthPalette.ts`, and component CSS. Alpha is listed separately where
an opaque hex would misrepresent the actual colour.

| Token / role | Value |
| --- | --- |
| `--bg`, `--bg-deep` | `#050d11`, `#040b0e` |
| `--panel` | `#08141a` at 94% (`rgba(8,20,26,0.94)`) |
| `--panel-2`, `--panel-3` | `#11242c`, `#162d36` |
| `--line`, `--line-strong` | `#1e3440`, `#2a4754` |
| `--text`, `--text-soft` | `#e7f0f4`, `#c2d3da` |
| `--muted`, `--faint` | `#8aa2ad`, `#849ca6` |
| `--warning` | `#e2553d` (NOT A FORECAST) |
| `--accent`, `--accent-strong`, `--accent-wash` | `#7cc7e8`, `#b6e6f8`, `#7cc7e8` at 12% |
| Legacy `--amber`, `--amber-strong`, `--amber-wash` | `#8aa2ad`, `#c2d3da`, `#c2d3da` at 6% |
| `--ok` | `#7fd4b0` |
| `--danger`, `--danger-wash` | `#e07a63`, `#e07a63` at 10% |
| OBSERVED / REANALYSIS / DERIVED / SCENARIO badges | `#ffffff` / `#7cc7e8` / `#9d8ce0` / `#8aa2ad` |
| Depth classes 1 / 2 / 3 / 4 | `#d6f2fb` / `#8fcce3` / `#5288bd` / `#343d7e` |
| Chart area / stage / rainfall | `#7cc7e8` / `#b8cbd3` / `#7fd4b0` |
| Main type scale | 34 / 20 / 15 / 13 / 11px |
| Metric line heights | 34px type / 36px line; secondary 20px / 24px |
| Family | system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif; `--mono` aliases `--sans` |
| Numerals | `font-variant-numeric: tabular-nums` on metrics/readouts |
| `--radius-sm`, `--radius`, `--radius-lg` | all 2px |
| Radius exceptions retained | circular status/badge dots; 8px brand mark; legacy panel 9px/4px local declarations |
| Rules / shadows / focus | 1px rules; `--shadow: none`; focus rings 2px background + 4px accent |

## Runtime diagnosis and scoped fix

Evidence retrieved from GitHub Actions job metadata and logs:

- Run `40108839515`, verify job `120916170169`: **18m24s job total**.
  Chromium dependency installation ran 15:51:29–15:58:53 UTC (**7m24s**).
  Apt explicitly reported **25.9 MB in 7min 2s, 61.4 kB/s**. This was a slow
  OS-package download, not a CSS transition or an assertion timeout.
- That run's M0 command ran 15:59:02–16:09:41 UTC (**10m39s**), including build
  and gates; Playwright reported **20 passed (10.4m)**.
- The six UI tests introduced by `2444418` each called `openApp` on a fresh
  browser page, mounting MapLibre and loading the app/frame again. Their logged
  durations were **34.4, 22.2, 16.8, 19.0, 24.6, 6.5 seconds**. Those are whole-test
  durations, not isolated startup measurements. The separate added M0 risk test
  took 22.5s. The suite was not unchanged plus one test.
- Comparison run `39672793736` reported **12 passed (5.2m)**. It is an older
  phase baseline (30 data gates, 23 pipeline tests), not a controlled comparison
  of this UI commit alone. Run `40127200431`, with unchanged UI/test code and only
  documentation changes, reported **20 passed (7.1m)**, demonstrating runner variance.
- Inspection of the UI commit found no changes to `helpers.ts`, `POLL_TIMEOUT`,
  `SETTLE_TIMEOUT`, or the Playwright config; its CSS diff removed transitions.
  The pre-existing 180-second pixel-test timeout is untouched.

Fix within the permitted scope: all six UI acceptance checks now execute as six
named `test.step` blocks on **one isolated page / one `openApp` call**, removing
five cold WebGL app loads. Rails are restored to default before row checks; the
legend is closed after its colour check. No assertion is dropped; existing M0
checks remain intact, including the separate risk/header test. Collection is now
15 tests, with the six UI requirements reported as steps rather than six fixtures.
No waits or timeout increases were added. Other tests retain page isolation.

This addresses the avoidable test-structure cost, not the entire 18m24s job.
Dependency installation lives in `.github/workflows/ci.yml`, outside this brief's
allowed paths; it was deliberately not changed. A measured speedup, and the
combined test's 75-second default budget, must be verified on the next CI run.
The previous status document's unconditional “no per-test regression” conclusion
was too strong: the logs separate costs but do not provide a controlled benchmark.

## What I deliberately did not change

- Data, PNGs, pipeline, model math, scores, ranking semantics, and data/honesty
  gate scripts: presentation must not rewrite scientific evidence.
- The single persistent warning, all four class badges, panel data ages,
  Extent score versus Severity rank, full SAR footprint / SAFE LUT / fixed −16 dB
  validation caveats: these are interpretation safeguards, not removable chrome.
- `data-ready`, `__baanh.renderSeq`, `data-tile-health`, and all existing
  `window.__baanh.*` hooks; readiness and pixel tests must keep their real signals.
  The bottom rail gains an additive `data-rail-size` hook; `data-expanded` stays.
- Existing M0/fallback assertions, repaint/settle helpers, external tile-health
  behavior, timeouts, worker count, and CI infrastructure: do not obtain a fast
  green by weakening coverage, masking tile failures, or changing unrelated files.
- Accepted visual design, small legacy CSS exceptions, and outstanding data nits:
  1C is closure, not a second design or data pass.
- `main` and PR merge state: this work belongs on `ui/pass-1`; no merge requested.

## Local verification for 1C

- `npm run build:sandbox`: PASS (TypeScript and Vite).
- `node scripts/check-data.mjs`: **38/38 PASS**.
- `node scripts/check-budget.mjs`: PASS, committed data **4.80 MB**.
- `node scripts/check-honesty.mjs`: PASS; `--self-test`: PASS, all nine injected violations rejected.
- `npm run test:unit`: **14/14 PASS**.
- `PYTHONPATH=pipeline/src python -m pytest pipeline/tests -q`: **29 PASS**,
  one Rasterio pending-deprecation warning.
- Playwright `--list`: **15 tests collected**. Collection is not browser execution.
- Local Playwright browser execution is not claimed: this Windows host has the
  reported `spawn EPERM` limitation. CI on the next push is the browser and runtime
  measurement. No fresh screenshot or visual-browser result is claimed here.
