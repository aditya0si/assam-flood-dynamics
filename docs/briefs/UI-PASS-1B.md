# UI pass 1B — three fixes, bounded (astra)

Repo: `C:\Users\oliad\Desktop\baanh`, branch `ui/pass-1`. This is a **narrow** pass. Do these three
things, in this order, and stop. Do not redesign anything else.

## Fix 1 — the right rail hides its own content (highest value, do first)

`src/panels/RiskPanel.tsx` + `src/shell/RightRail.tsx` + the CSS modules: the rail advertises
"33 districts ordered by the extent score" but the rows are clipped behind an internal scroll
container. Make the tab body a proper flex column with `min-height: 0`, a sticky panel header, and a
scroll area that actually shows rows. Acceptance: the first five district rows are visible without
scrolling inside the panel, and the extent-score formula is not clipped
(`scrollWidth <= clientWidth + 2`).

Commit after this fix (`git add -A && git commit -m "ui: rail scroll and header"`).

## Fix 2 — one depth palette, shared by map and legend

Find where the map colours the depth classes (`src/map/`) and where the legend renders swatches
(`src/panels/` or `src/map/` legend component). Define the ramp **once** in a TS constant
(`src/map/depthPalette.ts` already exists — extend it if so) and import it in both places.
Four ordered classes, sequential single hue, pale → deep: `#d6f2fb`, `#8fd4ee`, `#3f9fd0`, `#1b5a8a`.
Acceptance: no second hard-coded list of depth hex values anywhere in `src/`; the legend renders the
values from the constant.

Commit after this fix (`ui: single depth palette`).

## Fix 3 — de-duplicate the warning and the metadata

`NOT A FORECAST` appears in the header, the left legend, the right rail, and the chart region.
`data as of … · N day old` repeats per chart. Keep **one** `NOT A FORECAST` in the top bar and one
`data as of` per panel header. Remove the rest of those repeats (keep the class badges: OBSERVED /
REANALYSIS / DERIVED / SCENARIO).

Acceptance: exactly one element in the rendered DOM contains `NOT A FORECAST`.

Commit after this fix (`ui: single warning and metadata`).

## Rules

- Touch only `src/**` and `tests/e2e/**`. Never `public/data/**`, `pipeline/**`, or `scripts/check-*.mjs`.
- Keep test hooks: `data-ready`, `__baanh.renderSeq`, `data-tile-health`, `window.__baanh.*`, skip links.
- Run after each fix: `node scripts/check-data.mjs`, `node scripts/check-budget.mjs`,
  `node scripts/check-honesty.mjs`, `npm run build:sandbox`. All must stay green. Playwright may fail
  locally (`spawn EPERM`) — say so rather than claiming a browser result.
- Add one Playwright assertion for Fix 1 (five district rows visible) and one for Fix 3 (single
  warning) in `tests/e2e/m0.spec.ts`.
- Work fast. If something resists for more than ~10 tool calls, commit what is green, write what is
  stuck in `docs/UI-PASS-1B.md`, and stop. Partial and honest beats complete and broken.
