# Builder brief — phase A2: apply Review 02 and finish the data set

Standing rules from `docs/briefs/02-builder-m0.md` still apply (env facts, honesty, dependencies,
no app code). Your run is narrow:

**Read `docs/REVIEW-02-aoi-and-stage-amendment.md` first. It supersedes `DATA-PIPELINE.md` §3,
§7.3, §8 and the stage-09 gate. Where the amendment and the spec disagree, the amendment wins —
and you also update the spec text so they cannot disagree again.**

## What to do

1. Apply **A1** (analysis domain), **A2** (channel policy), **A3** (stage table), **A5**
   (performance) to the pipeline code and config.
2. Apply **A4** gates to the validator; keep V01–V20 that still apply, replace the old peak-area
   rule with `V-A4`, and make `validation-report.json` name every gate it evaluated.
3. Update `docs/DATA-PIPELINE.md` (§3, §7.3, §8, §12 gates) and `docs/MILESTONES.md` (the M0
   acceptance row that quotes a 30 % bound) to match the amendment. Keep the architect's voice;
   mark each edited section with `<!-- amended: REVIEW-02 -->`.
4. Re-run the scope in **A6**: stages 06 → 07 → 08 → 09 → 10 → 11 → 12 → 14 → 15.
5. Commit at: 06–08 green, 09 green, 10–12 green, 14–15 green.

## Definition of done

- `public/data/` complete: manifest, provenance, scenario, flood frames + summary, risk zones +
  district ranking, series, admin, hydro, basemap, `validation-report.json`.
- `validation-report.json` is `pass` with `V-A1…V-A8` explicitly listed alongside the retained
  V-gates; no gate is skipped or hard-coded to pass.
- Stage 09 wall time ≤ 10 min and no committed or working artifact above 300 MB from stage 09.
- `docs/PIPELINE-REPORT.md` updated with: the AOI area actually used, channel cell share, the full
  S00–S11 area table, peak extent against both the Assam and the flood-prone denominator, clamped
  share, per-stage wall times, and every deviation.
- Every claim in the report is a number you measured in this run — not copied from phase A.

## Non-negotiables

- If a gate still cannot pass, stop and report observed vs expected. Do **not** widen a gate,
  prune data until the number looks nice, or hand-edit any committed JSON.
- If the valley-floored AOI turns out to exclude a district that is genuinely flood-prone, say so
  in the report rather than silently stretching the threshold.
- No application code, no UI, no Playwright in this run.
