# Builder brief — phase A3: land the data set under REVIEW-03

Standing rules from `docs/briefs/02-builder-m0.md` still apply. Your blockers are resolved in
`docs/REVIEW-03-stage-calibration.md`, which supersedes `REVIEW-02` §A3–§A4. Read both.

**The reviewer was wrong about the stage table and the depth gate. You were right to stop.**
The fix is a measured calibration, not a widened gate.

## Work

1. Apply **B1** (stage scale), **B2** (depth formula, documented bias), **B3** (gate revisions
   incl. new `V-A9` speckle control), **B4** (frame budget: `V-A9` first, two-class rendering only
   as the recorded fallback) to config, scenario, validator and the superseded doc sections.
2. **Calibrate by measurement.** Produce the stage → (area, clamped share, median depth, p95
   depth, polygon parts) curve on the A2 channel set, choose the peak stage inside `V-A4`/`V-A5`,
   and put the table in `docs/PIPELINE-REPORT.md` with the chosen value named. Do not hard-code
   3.70 m without showing the curve that justifies it.
3. Re-run stages **09 → 10 → 11 → 12 → 14 → 15**. Commit at 09 green, then 10–12 green, then
   14–15 green.
4. Report raw **and** gzip size per animation frame and for the whole animation tier.

## Definition of done

- `public/data/` complete, `validation-report.json` `pass`, all gates named including `V-A9`.
- Peak extent inside 4,000–12,000 km²; median peak depth 1.0–2.2 m; clamped share of wet ≤30 %;
  clamped share of AOI ≤6 %; stage-09 ≤10 min; animation tier ≤6.5 MB raw and ≤1.5 MB gzip.
- `docs/PIPELINE-REPORT.md` carries the measured calibration table, per-stage wall times, per-frame
  sizes (raw/gzip), and every deviation.
- No application code, no UI, no Playwright.

## Still forbidden

Widening a gate, dropping real polygons to fit a cap without recording it, hand-editing committed
JSON, or copying a number from a document instead of measuring it.
