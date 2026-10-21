# Review 09 — B3 gates accepted; R6 pixel criterion genuinely unmet; B4 polish

Reviewer: Hermes. Target: B3, commit `98a186b`. Gates run by the reviewer, not taken from the report.

## Accepted, with evidence

| Gate | Evidence |
|---|---|
| `check-data.mjs` | **24/24 pass** — schemas, manifest SHA-256 integrity, V-A1…V-A10, PNG decoding for frame areas, provenance coverage, forbidden-field scan |
| `check-budget.mjs` | PASS — total **4.63 MB**/9, animation 2.24 MB/4, largest frame **248.8 KB**/400 |
| `check-honesty.mjs` | PASS on clean data; **I falsified it myself**: injected `casualties displaced incident_id` into a copy of `scenario.json`, `--data <tampered>` → **exit 1, 3 violations**; same command on clean data → exit 0 |
| Unit tests | 13/13 pass |
| Playwright | **runs in this environment**: 8 passed, 1 failed in 2.1 min |
| Docs / CI | `README.md`, `docs/M0-REPORT.md`, `ci.yml`, `pages.yml` present; workflows use plain `npm ci` / `npm run build` |

The honesty gate is now a real gate: it has been seen to fail.

## R6 — my criterion was not met

Both instruments agree the flood covers **5.3 %** of a 1920×869 screenshot at S07 (my harness: 5.28 %;
Playwright `m0.spec.ts` R6 test: failed). The map *is* dominant (61.8–64.8 % of viewport height, inside
the 62–68 % band), so the layout half of R6 is done. The subject-share half is not.

I will not lower the 6 % bar — it is the only pixel-level proxy I have for "the flood reads at a
glance", and the visual review says the extent is legible but diffuse. The fix belongs in the camera:
the app frames the flood-prone belt (a ~480 × 178 km box), while the peak flood occupies ~12 % of
that box in plan view. **Fit the camera to the peak wet extent instead of the belt bbox**, with
padding and pitch ~42°, and the share roughly quadruples without touching a byte of data.

## Other defects from the visual review (fix in B4)

1. **Bottom clipping** — the depth-decile strip and footnote are cut off at the viewport bottom at
   1920×869 and cramped at 1280×800.
2. **Skip link exposed** — "Skip to analysis panels" renders as a bright primary-looking button at
   top-left instead of appearing only on focus.
3. **Unexplained district markers** — orange `Sivasagar 71.9` style badges have no on-screen key;
   a viewer cannot tell the number is a 0–100 risk score.
4. **Blue does too much work** — flood depth, UI accents, chart lines, selected states all blue; the
   four depth classes are close together. Use a distinct depth ramp (cyan → teal → indigo → violet)
   and reserve UI blue for controls.
5. **Microtext** — attribution, ticks and layer descriptions are ~10 px and low-contrast.

## B4 scope (final polish, then publish)

1. Camera fits the peak wet extent (derive it at runtime from the step-07 frame PNG's alpha channel,
   or ship `peak_bounds` in `frame-index.json` via a pipeline-free script that writes a small JSON —
   do not regenerate the flood data), padding ~8 %, pitch 42.
2. Dock layout with no clipping at 1920×869 and 1280×800; decile strip fully visible.
3. Skip links hidden until focused; visible focus ring on focus.
4. District markers: add a key (one line: "district risk score 0–100, rank in the panel") and show
   `#1 · 71.9` rather than a bare number.
5. Depth palette separation + 11 px minimum for functional text with ≥4.5:1 contrast.
6. Re-run `npm run verify:m0` until **10/10** Playwright tests pass, including the R6 share test
   (≥6 % must be earned by the camera, not by relaxing the test).

## Publish gate (after B4)

Do not push anywhere yet. Repo name, visibility and Pages are the user's call; the reviewer will ask
before any remote is created.
