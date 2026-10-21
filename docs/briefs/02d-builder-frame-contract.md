# Builder brief — phase A4: land the raster frame contract

Read `docs/REVIEW-04-frame-contract.md` first; it supersedes `REVIEW-03` §B3 and changes the frame
file contract. Standing rules from `02-builder-m0.md` apply. You were right about both blockers:
the opening gate was a reviewer error, and the vector band budget was unachievable by design.

## Work

1. Apply **C1** (frame contract v3: ½-res 5-class PNG per step + `frame-index.json`, no per-band
   GeoJSON, no M0 outline), **C2** (gates incl. `V-A9` component-area filter and `V-A10`
   index/PNG agreement), **C3** (patch `ARCHITECTURE.md` §6.7 / §7.2 / §7.4 and
   `DATA-PIPELINE.md` §6.7 — mark edits `<!-- amended: REVIEW-04 -->`).
2. Remove the morphological opening everywhere; replace with the ≥9-cell component-area filter
   applied **before** statistics, geometry and rendering. Record components before/after and km²
   dropped.
3. Re-run **09 → 10 → 11 → 12 → 14 → 15**, commit at 09 green, 10–12 green, 14–15 green.
4. Report: per-frame PNG bytes, `frame-index.json` and `public/data/` totals, the component-filter
   audit, and the median/p95/clamp numbers computed on the filtered mask.

## Definition of done

- `public/data/` complete: frame PNGs + `frame-index.json` + summary + risk + series + admin +
  hydro + basemap + manifest + provenance + `validation-report.json` (`pass`, all gates named).
- Peak extent 4,000–12,000 km²; median peak depth 1.0–2.2 m; clamp ≤30 % of wet, ≤6 % of AOI;
  per-frame PNG ≤400 KB; animation tier ≤4.0 MB; `public/data/` ≤9.0 MB; stage 09 ≤600 s.
- No vector flood bands, no opening, no hand-edited JSON, no widened gate.

## If a gate fails

Stop and report observed vs expected with the command. Do not convert a failing measurement into a
relaxed threshold; that is the reviewer's job and it now requires a measured artifact.
