# Review 19 — Phase 1a: validity footprint is 9 % of the scene, and it inflates the score

Commit `97e8cf7`, CI `39665108432` success. The σ0 calibration fix is accepted:
`method.calibration = {A_median 595.42265, vectors 27, samples_per_vector 642}`, threshold fixed at
−16 dB with a −14/−16/−18 dB band, caveats corrected, `TP/FP/FN` now published per threshold.
That work is good and stays.

**But the comparison is being made on a sliver, and that sliver is model-correlated.**

## Measured, same scene (`…20220731T233912…054B00`), reviewer implementation

| Quantity | Reviewer | Scorecard |
|---|---|---|
| Scene ground area (from GCP corners) | **43,389 km²** | not published |
| Validity on the frame grid | **41,193.0 km² (94.9 % of scene)** | **3,735.09 km² (8.6 %)** |
| Observed water @ −16 dB σ0 | **467.1 km²** | 240.05 km² |
| Model wet inside validity | **568.2 km²** | 551.87 km² |
| TP | **79.2 km²** | 94.05 km² |
| IoU vs S07 | **0.0827** | 0.1348 |
| Precision (TP/model) | **0.1392** | 0.1704 |
| Recall (TP/observed) | **0.1694** | 0.3918 |

Two facts cannot both be innocent:

1. Validity is **8.6 %** of the scene even though 94.9 % of the scene lands inside the frame grid, so
   something is deleting ~90 % of a 43,389 km² footprint.
2. The model's wet area inside that 3,735 km² sliver is **551.9 km²** — 97 % of the 568.2 km² it has
   inside the *whole* 41,193 km² scene. A validity mask that retains almost exactly the model's wet
   area, and only 9 % of the scene, is not a footprint; it is a selection correlated with the thing
   being tested. It inflates IoU (**+63 %**) and recall (**2.3×**) relative to the full-scene numbers.

## What to do

1. **Instrument the mask stack.** Publish a per-scene `validity_attrition` object with the area (km²)
   after each step, in order: `raw_sar_valid → slope_filtered → aoi_clipped → component_filtered →
   final`. No step may be silent. This alone identifies which filter is eating the footprint.
2. **Prohibit model-conditioned selection.** The validity mask must be built from SAR validity, the
   AOI polygon, terrain and geometry **only**. No mask may reference the flood frames, the HAND wet
   mask, or any district/risk artifact. State this in the module docstring.
3. **Threshold the slope filter in explicit units** and document it: `slope > 10°` computed from the
   DEM with a stated operator and unit, or drop the slope filter if it cannot be shown not to remove
   valley floor. Report both `with_slope` and `without_slope` validity areas.
4. **Recompute on the full footprint** and publish the resulting numbers. If the honest IoU is 0.08
   rather than 0.13, that is what ships.
5. **Add `check-data` assertions:**
   - `validity_area_km2 >= 20000` for this AOI (a scene covering 43,389 km² cannot validate on 3,735),
     **unless** `validity_attrition` documents which filter removed the rest and why;
   - `scene_area_km2` is published and `validity_area_km2 / scene_area_km2` is recorded;
   - `TP + FP === modelled_in_validity_km2` and `TP + FN === observed_area_km2` within 0.5 km², per
     threshold — the arithmetic identity that would have caught this immediately.
6. **Reconcile against the reviewer's numbers** in the report: validity ≈ 41,000 km², observed
   ≈ 467 km² at −16 dB, IoU ≈ 0.083 for this scene. Explain any residual difference by mechanism, not
   by tolerance.

## Acceptance

- Validity within 10 % of 41,193 km² for this scene, or an attrition table that justifies the gap.
- `TP+FP` and `TP+FN` identities hold per threshold.
- Published IoU/precision/recall recomputed on the full footprint.
- All existing gates stay green; CI green on Linux; the Validation tab shows the corrected numbers.
