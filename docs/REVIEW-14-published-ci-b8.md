# Review 14 — published; CI failing on two pixel tests; B8 = settle predicate + live polish

Published: **https://aditya0si.github.io/assam-flood-dynamics/** (repo `aditya0si/assam-flood-dynamics`, public,
Pages `build_type=workflow`, deploy run `39591027361` green in 34 s).

## Live verification (reviewer, against the public URL)

| Check | Result |
|---|---|
| Content types | `/` → `200 text/html`; `/assets/index-*.js` → `200 application/javascript`; `/data/manifest.json` → `200 application/json`; `/data/flood/frames/step-07.png` → `200 image/png`; a bogus asset → `404` (no SPA-fallback 200s) |
| Boot | `data-ready=true`, `tileHealth=live`, hero camera `[94.609, 26.981] zoom 9.5 pitch 42`, `panel=risk` |
| Data binding | S00 `1/12 · 1833.9 km²`; S07 after pause `8/12 · 10010.6 km² · 3.7 m · frames/step-07.png` |
| Playback | advanced `2/12 → 5/12` on the live site |
| Honesty chrome | `NOT A FORECAST`, `SCENARIO`, `SYNTHETIC`, `DERIVED` all visible |
| Console | zero errors |

Visual read at S07: the flood now fills a substantial, coherent part of the hero map (depth classes
visible, Majuli/Sivasagar markers keyed with rank + score, rail showing
`Score = 45 % area + 35 % duration + 20 % depth`). Credible as a scenario tool.

## CI: 8/10, two failures — both my pixel tests, both on the settle predicate

`verify:m0 (headless Linux)` fails exactly on A6 and R6 with
`page.waitForFunction: Timeout 30000ms exceeded` (both retries). The settle helper added in B7 waits
for a condition that never becomes true in headless CI. Everything else passes on Linux, including
the blocked-tile fallback, provenance and reduced-motion tests.

**B8 scope**

1. **Deterministic settle.** Expose `__baanh.renderSeq` (increment on every rendered map frame) and
   `__baanh.styleLoaded`. The helper waits for `styleLoaded && renderSeq advances by ≥2` with a 60 s
   budget, then screenshots. No dependence on tile network state. Applies to A6 and R6 only.
2. **Live polish** found in the published screenshot:
   - `Bathub` → **Bathtub** (methodology text);
   - duplicated units in labels: `km² km²`, `mm/day mm/day` → single unit;
   - truncated `SHARE OF FLOOD-PRONE AR…` → wrap or shorten the label;
   - deep-flood class and `very_high` risk both render magenta — move the deepest depth band to a
     distinct hue so colour semantics stay single-purpose;
   - the `Terrain and imagery live` toast overlaps the attribution line — dock it clear of the
     attribution (e.g. above it, right-aligned).
3. Keep every threshold unchanged (`S00 < S04 < S07`, `S07 − S00 ≥ 3` points, `≥10 %` of the map
   viewport, 62–68 % map height).
4. Commit and push; CI must go green on Linux before this is called done.

## Do not

Change `public/data/`, `pipeline/`, the model numbers, or any threshold. If the settle hook cannot
be made deterministic, say so and report the measured values from both runs instead of loosening an
assertion.
