# Builder brief — Baanh M0 (vertical slice)

You are the **builder**. You own every line of application and pipeline code in this repo.
Read, in order: `docs/ARCHITECTURE.md`, `docs/DATA-PIPELINE.md`, `docs/MILESTONES.md`
(section **M0**), then `docs/reference-analysis.md` for the honesty rules.

Your only milestone is **M0**. Do not build P1 or P2 features, and do not add files "for later".

## Verified environment facts (do not re-derive, do not change)

- Windows 11, bash (git-bash) shell, `git`, Node **24.14.1**, npm **11.11.0**.
- Python is `python` (3.14.7). Already installed and importable:
  `numpy 2.4.3`, `scipy 1.17.1`, `shapely 2.2.0`, `pyproj 3.7.2`, `rasterio 1.4.4`,
  `mercantile 1.2.1`, `Pillow 12.3.0`, `requests 2.33.0`.
  Do **not** create a venv and do not pin Python 3.11. No GDAL install step is needed.
- Network is available but flaky: every HTTP fetch needs a timeout, ≥3 retries with backoff,
  and a `User-Agent` header. Overpass took ~30 s on a probe — treat it as slow, not dead.
- The five data hosts in `docs/reference-analysis.md` all answered 200 from this machine.

## Order of work (do not reorder)

1. **Pipeline first.** Create `pipeline/` exactly as `DATA-PIPELINE.md` §4–§5 specifies, then run
   stages 01→15 in order and leave the outputs in `public/data/`. Commit after stage groups:
   sources (01–03), geometry (04–07), model (08–10), series+validation (11–15).
2. **App shell** (`index.html`, Vite config, `src/` per `ARCHITECTURE.md` §5) against the
   committed data. No placeholder data, no hard-coded numbers that belong in `scenario.json`.
3. **Checks**: `scripts/check-data.mjs`, `check-budget.mjs`, `check-honesty.mjs`, the unit tests,
   and the two Playwright specs, wired into `npm run verify:m0` exactly as `MILESTONES.md` §M0
   defines it.
4. **Last commit**: `M0: vertical slice green` only after `npm run verify:m0` exits 0.

## Non-negotiable rules

- **Committed GeoJSON/JSON must be produced by the pipeline**, never hand-authored. If a stage
  cannot run, stop and report the stage, the command, and the error. Do not invent output to
  unblock the app.
- Every visible data surface carries its class badge (`SOURCE` / `DERIVED` / `SCENARIO` /
  `SYNTHETIC`), and "NOT A FORECAST" is visible without opening a menu.
- No invented agencies, incident ids, casualty/displacement figures, relief camps, resource
  fleets, or telemetry. The schema in `DATA-PIPELINE.md` deliberately has no such fields.
- Dependencies: only those in `ARCHITECTURE.md` §4. Adding anything else requires a written
  justification in the commit message and a line in `README.md`.
- No backend, no database, no auth, no paid key, no runtime AI call, no web fonts.
- Honour the data size caps. If a layer exceeds its cap, simplify geometry rather than raise the cap.
- Windows paths: pass native `C:/...` paths to node/python, never `/c/...` or `/tmp`.

## Definition of done (M0)

- `npm ci && npm run dev` serves the app on Node 24.
- `npm run verify:m0` exits 0, including the tile-failure fallback spec.
- `public/data/validation-report.json` is `pass`; `npm run build` produces a static `dist/`.
- The manual 60-second check in `MILESTONES.md` passes: rainfall peaks before stage, stage floods
  low-HAND terrain, risk ranks districts by area/duration/depth — all visible in the UI.
- `docs/M0-REPORT.md` written by you: what exists, the exact commands run with their exit codes,
  the data sizes produced, every deviation from the spec (with reason), and what is still broken.

## Stop and report instead of improvising when

A stage needs a dataset, key, or service that `docs/reference-analysis.md` does not list; a
dependency fails to install twice; or a spec instruction contradicts observed reality. Print the
failing command and its error, then stop — a clean blocked report is worth more than a working
looking fake.
