# Review 22 — Phase 1b completion: ERA5 rate limit, `batch_size` NameError, exposure mask

The Phase 1b run died twice: first a dsh transport error, then a hard `HTTP 429` from Open-Meteo.
The tree is uncommitted and `check-data` fails because `data/series/rainfall.json` and
`data/series/rainfall-forecast.json` do not exist.

## Measured failure

```
baanh_pipeline.http.FetchError: fetch failed for https://archive-api.open-meteo.com/v1/archive?... after 8 attempt(s):
HTTP 429 after 0.2s: '{"reason":"Hourly API request limit exceeded. Please try again in the next hour."}'
```

Cause: `_fetch_archive()` requests **32 points for the first 192 points, then 128 points per call**,
each over the full 4,017-day range (2015-01-01 → 2025-12-31). Open-Meteo weights a call by
`locations × days`, so a single 128-point call is ~514 k weight. Six calls succeeded (files
`archive-batch-000/032/064/096/128/160.json` are cached and **must be reused**), then the hourly cap
hit. Re-running as-is will burn the cap again.

There is also a **latent `NameError`**: line 128 of `rainfall.py` references `batch_size`, which is
not defined in `_fetch_archive()` — the stage would fail after all fetches completed, wasting the
whole quota.

## Required changes to `pipeline/src/baanh_pipeline/rainfall.py`

1. **Fetch monsoon windows only.** For each year 2015…2025, request `06-01 … 09-30` (122 days) instead
   of the full year. Weight per call drops from `32 × 4017` to `32 × 122` (~3,900), and the whole
   sweep becomes ~690 k total instead of ~2 M.
2. **32-point chunks throughout.** Drop the 128-point path entirely.
3. **Cache per `(year, chunk)`**: `archive-{year}-{start_index:03d}.json`. Cached full-year batch files
   from the failed run **cannot** be reused for a 122-day window — delete or ignore them; do not
   mis-parse them (the parser's `expected_days` check will catch it, which is correct).
4. **Fix `batch_size`** — compute it from the chunk length actually used.
5. **Concatenate the per-year windows** into one continuous JJAS series per point, in date order, and
   assert no duplicate or missing dates across years.
6. **Publish the scope honestly** in `query`: `window: "JJAS 06-01..09-30, 2015-2025"`,
   `off_season_included: false`, plus a `caveat` sentence: *"Only the monsoon season is published;
   off-season days are omitted because the fetch is rate-limited, not because they are unavailable."*
   The 2022 JJAS total and the 2015–2025 JJAS mean must both be computed from exactly this window.
7. **Rate-limit discipline:** ≥10 s between calls, `retries=6`, and on `429` **stop the stage cleanly**
   with a message naming how many `(year, chunk)` pairs are cached, so the next run resumes instead of
   restarting.

## Required changes to `pipeline/src/baanh_pipeline/exposure.py` (see `REVIEW-21`)

- Zonal-sum the **masked** population (`pop × wet_fraction`) per district, not raw `pop`.
- Clip the population raster to the AOI before publishing totals; rename to `population_within_aoi`
  and state the scope. Never publish India-wide sums next to Assam districts.
- Publish `district_population` and `exposed_share_of_district` per row.
- Gates: `sum(districts) ≈ peak_mask` within 1 %; `population_within_aoi ∈ [20M, 45M]`;
  each district's exposed ≤ its own population; peak mask < AOI total.

## Delivery

Run `build-rainfall` (resume-friendly), `build-exposure`, then `build-validation` if the scorecard's
`data_as_of` needs refreshing. All gates green (`check-data`, budget, honesty + self-test, unit,
pipeline pytest), build, commit, push, CI green. Report the district JJAS totals for 2022 vs the
2015–2025 mean, the corrected exposure totals, the cached-batch count, and the commit SHAs.

**If the hourly limit is hit again: stop, report which `(year, chunk)` pairs are cached, and do not
substitute synthetic or interpolated rainfall for real ERA5 values.** A missing file is recoverable;
a fabricated one is not.
