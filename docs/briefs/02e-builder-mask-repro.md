# Builder brief — phase A5: close the mask question and finish the data set

Read `docs/REVIEW-05-depth-gate-and-mask-reproducibility.md`. It supersedes only `V-A5`.
`REVIEW-04` C1/C3 (frame contract, app-side contract) and the accepted A4 results stand.

## Your two jobs

1. **Explain the mask (blocking).** Add the `D3` mask definition appendix naming the HAND raster,
   the connectivity predicate, the filter order, and **three numbers** for stage 3.70 m: area before
   connectivity, after connectivity, after the area filter. Reviewers measured 6,302.5 km² (contains
   a channel cell) and 8,129.6 km² (contains or within one cell) from the committed rasters; your
   pipeline reports 10,010.6 km². Reconcile it. If the shipped code disagrees with the spec's
   predicate, fix whichever is wrong and say which.
2. **Apply D1 + D2**, then re-run **09 → 10 → 11 → 12 → 14 → 15**, commit at each green group.

## D1 — V-A5 v4 (shape-based)

median peak depth ≥0.7 m and ≤ (peak stage − 0.5 m); p95 ≤ peak stage; p95 − median ≥0.6 m;
clamped share of wet ≤30 %.

## D2 — depth deciles

`flood-summary.json` gains per step `wet_cells` and `delay_deciles`
`{p10,p25,p50,p75,p90,p95}` over wet cells, and the pipeline report prints the same table. No
downstream consumer may average these into one number.

## Definition of done

- `public/data/` complete and published: frames + `frame-index.json` + summary (with deciles) +
  risk + district ranking + series + assets/gauges (P1 scope as specified) + manifest + provenance
  + `validation-report.json` = `pass` with every gate named.
- Peak extent 4,000–12,000 km²; V-A5 v4 all four rules pass; per-frame PNG ≤400 KB; animation
  ≤4.0 MB; `public/data/` ≤9.0 MB; stage 09 ≤600 s.
- Mask appendix reconciles the three areas, or names the defect that prevented it.
- No widened gate, no hand-edited JSON, no application code.

## Stop and report when

The mask cannot be reconciled after an honest attempt — say which of the two predicates the shipped
code implements, and what the third number is, rather than publishing a total you cannot derive.
