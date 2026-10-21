# Review 21 — Phase 1b exposure: the mask is computed, then not used

The tree from the interrupted Phase 1b run is uncommitted and `check-data` fails because
`data/series/rainfall.json` and `data/series/rainfall-forecast.json` were never written (the ERA5
stage died on an Open-Meteo rate limit before the transport error). The reviewer is re-running
`build-rainfall` to complete that piece. Everything below is about `data/exposure/district-exposure.json`,
which **was** written and is wrong in two ways.

## Defect 1 — district exposure ignores the flood mask

`pipeline/src/baanh_pipeline/exposure.py`, `_district_population()`:

```python
values = pop[district_raster == index]
count = int(round(float(values.sum())))
```

That sums **all** population inside each district polygon. The wet mask is only ever applied to the
AOI-wide figure in `_peak_population()`. Measured consequences:

| Quantity | Published | Should be |
|---|---|---|
| `peak_mask.potentially_exposed_residents` (masked) | **5,807,467** | correct — this is the honest number |
| `totals.potentially_exposed_residents` (sum of districts) | **35,710,497** | ≈ the masked total, not 6× it |
| Assam population (2020 estimate) | ~35 M | a value equal to the whole state is self-evidently wrong |

A district table that reports 35.7 M "potentially exposed" residents in a state of ~35 M people,
while the peak mask is 10,033 km² (12.8 % of Assam), is the kind of number that discredits every
other number on the page.

**Fix:** build `masked = pop * wet_fraction` once (already computed inside `_peak_population`), then
zonal-sum `masked` per district. Return `wet_fraction` from `_peak_population` or expose a helper so
both code paths use the same array. District values must sum to the peak-mask value within 1 %.

## Defect 2 — the raster totals are India, not Assam

`totals.population_raster_total = 1,409,367,663` and `worldpop_cell_count = 12,106,108`.

That is the **whole-India** WorldPop raster summed over its full extent. A field named
`population_raster_total` sitting beside Assam districts will be read as Assam's population.

**Fix:** clip the raster to the AOI before taking totals, and rename to make the scope explicit:
`population_within_aoi`. Add `population_raster_scope: "AOI v2 polygon"`. If a full-raster figure is
still wanted, publish it under `source.raster_total_unclipped` with an explicit `scope: "India"`.

## Gates that would have caught both

Add to `check-data` (and the pipeline's own `validate`):

1. `abs(sum(districts) - peak_mask.potentially_exposed_residents) / peak_mask... <= 0.01`
2. `20000000 <= totals.population_within_aoi <= 45000000` (Assam's plausible range)
3. every district `potentially_exposed_residents <= its own district population` — a district cannot
   expose more people than live in it (requires publishing `district_population` per row, which is
   also useful context);
4. `peak_mask.potentially_exposed_residents < totals.population_within_aoi` — a strict subset.

## Delivery

- Fix `exposure.py`, re-run stage 18, publish the corrected file.
- `district_population` and `exposed_share_of_district` per row, both `class: derived`.
- All gates green, unit tests, pipeline pytest, build, commit, push, CI.
- Report: the corrected totals, the top five districts by exposed residents, and the sum-vs-peak check.
