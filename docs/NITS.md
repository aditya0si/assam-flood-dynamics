# Nit register

Small, known defects that are **not** fixed in Phase 1a. Each is open until a later review
closes it; none blocks the build or the validation scorecard.

| id | found in | description | blocks | status |
|---|---|---|---|---|
| N-01 | `public/data/risk/district-risk.json` | `risk_class_area_share` has no machine-readable denominator in the JSON (`risk_class_area_share_denominator`). The denominator (area of cells wet at peak S07 with valid HAND) is documented only in prose in `DATA-PIPELINE.md` and the schema description. | Nothing; the four shares still sum to 1.0 and are checked. A consumer cannot recover the denominator from the artifact alone. | open |
| N-02 | Risk rail / app shell | The bottom-right attribution clips at narrow rail widths. The map attribution is positioned under the rail and loses its right-hand text when the rail is at its narrowest. | Nothing functional; a review/reporting legibility defect. | open |
| N-03 | Risk panel | The panel does not state that district scores are AOI-relative; only rows below 75 % coverage carry the `coverage …%` badge and the `Scored on the AOI-covered share only` annotation. | Nothing; a reader can mistake the score for an all-district score. | open |

Statuses are all `open`. Nits are not fixed in this phase.
