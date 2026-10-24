# UI pass 1 — make Baanh read like a survey instrument, not a dashboard

You are the designer-developer for a single UI pass on **Baanh** (`C:\Users\oliad\Desktop\baanh`),
a MapLibre flood-scenario explorer for Assam. The product's substance is already strong — validated
Sentinel-1 scorecard, calibrated rainfall, masked exposure, honest labels. The interface is what is
letting it down.

## What the current screen does badly (measured, not guessed)

1. **The map is not the primary surface.** Four floating panels (top bar, left legend, right rail,
   bottom analytics rail) cover most of it, and the right rail's own content is clipped behind an
   internal scrollbar — the district rows it advertises are **not visible**.
2. **The depth legend does not match the map.** Swatches read cyan/teal/purple/blue while the map
   cells are yellow / olive / orange / red-maroon / green. A user cannot decode depth from the map.
3. **Status noise.** `NOT A FORECAST`, `SCENARIO`, and `data as of … · 1 day old` are repeated in the
   header, both side panels, every chart and the bottom rail. Repeating a warning 6× makes it
   invisible.
4. **Typography has one volume.** Most text is 9–12 px, letter-spaced, ALL CAPS. KPIs (stage, area,
   share) carry no more weight than metadata, so nothing leads.
5. **Amber means three different things** — warning, data-source chip, threshold annotation.
6. **Clipping.** The extent-score formula is cut off; chart labels and the bottom edge collide.
7. **Flat charts look broken.** At S00 three near-flat series render with no explanation.

## Design direction (follow this; do not substitute your own defaults)

The subject is a monsoon floodplain measured by instruments. Lean **cartographic survey instrument**:
deep ink ground, hairline rules, precise small type with real hierarchy, one reserved warning colour,
data that reads like a chart from a technical report. Not a SaaS dashboard, not glassmorphism, not
rounded cards floating on a blurred map.

- **Palette.** Keep the ink base but quieten it: `--bg #050d11`, panels `rgba(8,20,26,0.94)` with a
  1px hairline and radius **2px** (instrument, not card). Reserve `--warning: #e2553d` **exclusively**
  for the `NOT A FORECAST` statement. Accent `#7cc7e8` stays for interaction and water only.
  Remove amber from data-source chips.
- **Class badges become quiet dots + word**, one colour each, used once per surface:
  OBSERVED `#ffffff`, REANALYSIS `#7cc7e8`, DERIVED `#9d8ce0`, SCENARIO `#8aa2ad`.
- **Type.** One family. Tabular numerals for every metric (`font-variant-numeric: tabular-nums`).
  Scale: 34 / 20 / 15 / 13 / 11. Body and metadata **minimum 13 px and 11 px**; no letter-spaced caps
  except the single H1 subtitle and KPI labels. KPIs lead; metadata recedes.
- **Depth ramp.** One sequential single-hue ramp (pale cyan → deep indigo) for the four depth classes,
  defined **once** in a shared TS constant that both the map layers and the legend import, so the
  legend cannot drift from the map again.
- **Layout, map first.** Right rail collapsible (collapsed 44 px / default 380 px / expanded 520 px)
  with a visible control; bottom analytics rail collapsible; left legend compact with an expand
  affordance. The map must own the screen when rails are collapsed.
- **Repeated metadata.** Publish `data as of` and the class once per panel header, never per chart.
  One `NOT A FORECAST`, persistent, in the header only.
- **Empty and flat states.** At S00 the charts say so in words: "Onset — no accumulated change yet."

## Hard constraints

- **UI only:** `src/**`, `tests/e2e/**`, and existing CSS modules. Do **not** touch `public/data/**`,
  `pipeline/**`, `scripts/check-data.mjs`, or `scripts/check-honesty.mjs`. If you believe a data change
  is needed, stop and say so instead.
- **Preserve every honesty affordance:** `NOT A FORECAST`, the four class badges, per-panel data ages,
  `Extent score` vs `Severity rank`, the validation caveats (`full SAR footprint`, `SAFE LUT`,
  `fixed −16 dB`). Do not soften or relocate them out of sight.
- **Preserve test hooks:** `data-ready`, `__baanh.renderSeq`, `data-tile-health`, `window.__baanh.*`,
  the skip links, and the existing Playwright assertions in `tests/e2e/m0.spec.ts`.
- **No new runtime dependencies.** Bundle budget: total data stays ~4.8 MB; keep the JS bundle within
  +60 kB gzip of current.
- **Accessibility:** visible focus rings, keyboard reachable rails/tabs, `prefers-reduced-motion`
  respected, contrast ≥ 4.5:1 for body text, ≥ 3:1 for large numerals.

## Acceptance tests you must add (Playwright)

1. **Map owns the screen:** at 1440×900 with rails expanded, `.maplibregl-map` height ≥ 60 vh, and
   ≥ 75 vh after collapsing both rails.
2. **District rows visible:** the Risk tab shows at least 5 district rows with rank and score text;
   the first row is inside the panel's visible scroll area.
3. **Legend matches map:** the legend swatch colour strings equal the shared constant's hex values
   (import or duplicate the constant in the test — but assert equality, not eyeballing).
4. **No clipped formulas:** the extent-score formula element's `scrollWidth <= clientWidth + 2`.
5. **Single warning:** exactly one element contains `NOT A FORECAST` in the rendered DOM.
6. **Flat-state copy:** at S00 the charts region contains the onset empty-state sentence.

## Deliverables

- The redesigned UI, committed on a branch `ui/pass-1` (do not push to `main`).
- `docs/UI-PASS-1.md` — before/after of the seven problems above, the token table you used, and a
  short "what I deliberately did not change" list.
- All existing gates green: `node scripts/check-data.mjs` (38/38), `check-budget`, `check-honesty`
  + `--self-test`, `npm run test:unit` (14), `PYTHONPATH=pipeline/src python -m pytest pipeline/tests`
  (29), `npm run build:sandbox`. Playwright may fail locally (`spawn EPERM` on Windows) — if so, say
  so and leave it to CI; do not claim browser results you did not obtain.

Work file-by-file, keep diffs tight, and prefer deleting UI chrome over adding it. When in doubt,
remove one accessory.
