# Builder brief — Baanh M0, phase A: the data pipeline

Follow `docs/briefs/02-builder-m0.md` for standing rules (env facts, honesty rules, no invented
data, dependency limits). This brief narrows your run to **phase A only**: build and run the
offline pipeline, and produce the committed data set plus its validation report.

**Do not write application code, components, CSS, `index.html`, or Playwright specs in this run.**
The app is phase B, dispatched after a reviewer verifies your data.

## Deliverables

1. `pipeline/` — the Python package and stage CLI exactly as `docs/DATA-PIPELINE.md` §4 specced:
   `python -m baanh_pipeline.cli <stage>` for every stage in §5, one module per stage group,
   config in one place, no notebooks, no mystery constants (values live in config, not in code).
2. Run stages 01→15 in order. All outputs land under `public/data/` in the paths and schemas of
   `DATA-PIPELINE.md` §6.
3. `public/data/validation-report.json` with every gate V01–V20 evaluated and `status: "pass"`
   only if all pass. A failing gate prints the gate id, the observed value and the expected rule.
4. `pipeline/README.md` — how to re-run from scratch, how long each stage took, what is cached and
   where, and the exact command that reproduces the committed bytes.
5. Commit after each green stage group (sources 01–03, geometry 04–07, model 08–10,
   series/validation 11–15), each commit message naming the stages and the output sizes.
   Do not commit `pipeline/cache/` or raw downloads (gitignore them).
6. `docs/PIPELINE-REPORT.md`: per stage — command, wall time, bytes in / bytes out, exit code,
   and deviations with reasons. Include the AOI bbox, tile counts, and the final committed data
   size per tag (critical / animation).

## Practical constraints

- Cache every HTTP response under `pipeline/cache/` keyed by URL, and make re-runs idempotent.
- Terrarium tile fetch: bounded concurrency (4–6), ≥3 retries with backoff, hard fail if a tile
  stays missing after retries (do not fabricate elevation).
- Overpass: 180 s timeout, one retry, then fall back to the Natural Earth river layer and record
  in `provenance.json` that the fallback was used. Never mix both in one run silently.
- Memory: work tile-by-tile, never hold the full mosaic plus every band at once. If a stage needs
  more than ~2 GB RSS, reduce with windowed processing rather than lowering resolution silently.
- Data caps from `DATA-PIPELINE.md` §11 are hard. If a layer exceeds its cap, simplify geometry
  and re-run the validation gate.

## Definition of done (phase A)

- All 15 stages run end-to-end on a clean `pipeline/cache/` (state the wall time).
- `public/data/` contains every file in §6 with the specified schema; no file is hand-edited.
- `validation-report.json` is `pass`, `provenance.json` lists source → stage → file for every
  dataset, and committed data is inside the size caps.
- `docs/PIPELINE-REPORT.md` written, with real numbers from your run.
- Nothing outside `pipeline/`, `public/data/`, `.gitignore`, `docs/PIPELINE-REPORT.md` changed.

## Stop and report instead of improvising when

A stage needs a dataset or key not in `docs/reference-analysis.md`; the fallback also fails; a
validation gate cannot pass without falsifying data. Print the failing command, the observed and
expected values, then stop.
