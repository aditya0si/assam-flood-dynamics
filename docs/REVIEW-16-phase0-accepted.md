# Review 16 — Phase 0 accepted, with one nit and one design finding

Commit `987cf96` (CI `39634316782` **success** 7 m 9 s on Linux; Pages deploy `39634316684` success).
Reviewer-verified against committed data and the live URL, not against the report.

## Verified

| Item | Evidence |
|---|---|
| Weights honest | `risk/district-risk.json` → `weights {area_share: 0.5625, duration: 0.4375}`, `weights_version: area-duration-v1`, sums to 1.0; `reference_values` no longer mentions depth |
| Ranking preserved | top 5 unchanged in order: **Sivasagar 66.805 · Majuli 54.195 · Hojai 53.773 · Nalbari 51.168 · Nagaon 49.618** — a dropped constant term cannot reorder, and it didn't |
| Depth context discriminates | `depth_over_1_5m_share`: **33 distinct** values, range 0.470–0.882; `median_depth_m`: 30 distinct, 1.307–3.700 m |
| Coverage caveat | 4 districts below 0.75: **Dima Hasao 0.466**, Karbi Anglong West 0.580, Karbi Anglong East 0.558, Tinsukia 0.744; live row reads `44.1 · coverage 46.6% · Moderate · 0.4% of district area · Scored on the AOI-covered share only` |
| Class shares | `risk_class_area_share` = low 0.2766 · moderate 0.1931 · high 0.2047 · very_high 0.3256, sum **1.000000** |
| Live UI | formula now reads `Score = 56.3% area share + 43.8% duration. Area saturates at 60.0%; duration at 90 days`; depth labelled `reported, not scored`; Sivasagar shows `#1 · 66.8` |
| Gates | `check-data` **27/27**, unit **14/14**, budget PASS, honesty PASS, zero console errors |

This also closes the "79 % in one class" question for good: the largest class is **32.6 %** of wet-at-peak
area by the documented denominator.

## Nit (carry into the next phase, not worth a round trip)

`risk_class_area_share` is in the JSON but its **denominator is only in the docs**. Add a sibling
`risk_class_area_share_denominator` string (`"cells wet at peak S07 with valid HAND inside AOI v2"`)
so the artifact is self-describing. Acceptance: `check-data` asserts the field exists and is non-empty.

## Design finding (this one matters for Phase 1)

The score is dominated by **area share**, so a district whose small covered fringe is almost entirely
deeply flooded ranks low. Dima Hasao: `depth_over_1_5m_share 0.882`, `median_depth 3.7 m`,
`duration 114.7 d` — the most severe per-wet-cell profile in the file — yet it scores **44.1 (moderate)**
because only 0.4 % of its area is wet.

That is not a bug; it is a *severity vs extent* conflation. For disaster management both matter and
they answer different questions: extent drives shelter/relief scale, severity drives life-safety and
evacuation urgency. Phase 1 should publish **two labelled ranks** (extent-led and severity-led) or a
2-axis view, rather than one number that silently trades one for the other.

Add to `07-plan.md` Phase 1 as **P1.7**: expose per-district `severity_index` (depth>1.5 m share ×
median depth × duration, normalised) beside the existing extent-led score, with both labelled; no
single composite until a documented weighting exists. Acceptance: the Risk panel shows both and
Dima Hasao ranks high on severity while low on extent.
