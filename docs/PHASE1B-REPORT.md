# Phase 1b report — real forcing, labelled exposure, class badges

Status: code fixes implemented from `docs/REVIEW-20-phase1b.md` and
`docs/REVIEW-22-phase1b-completion.md`; **build-rainfall is blocked by Open-Meteo HTTP 429**.
No DEM swap and no OSM facilities.

**Build-rainfall status (REVIEW-22):** the rate-limited sweep cached **142 of 187
`(year, chunk)` pairs**. Every chunk for 2015–2022 is cached (8 × 17 = 136); 2023 has chunks
000, 032, 064, 096, 128 and 160 cached. Missing: 2023 chunks 192–512 (11), all 17 chunks of
2024 and all 17 chunks of 2025. A resumed run was refused with 429 at 2023:192. No
`series/rainfall.json` or `series/rainfall-forecast.json` was written, and no synthetic or
interpolated rainfall was substituted. Re-run `build-rainfall` when the quota resets; it will
resume from the cache.

## P1.3 — ERA5 reanalysis, never observed

- Archive endpoint: `https://archive-api.open-meteo.com/v1/archive`
- Model: `era5`; daily `precipitation_sum`; **JJAS only, 06-01..09-30 for each year
  2015–2025** (122 days × 11 years = 1,342 days).
- Rate-limit discipline: 32-point calls (locations × days weight ≈ 3,904), one cache file
  per `(year, chunk)` (`archive-{year}-{start_index:03d}.json`), at least 10 s between
  calls, `retries=6`. An HTTP 429 stops the stage cleanly with the cached-pair count; the
  next run resumes from cache. No full-year cache file is reused or mis-parsed.
- `query.window = "JJAS 06-01..09-30, 2015-2025"`, `query.off_season_included = false`,
  and the caveat: “Only the monsoon season is published; off-season days are omitted
  because the fetch is rate-limited, not because they are unavailable.”
- Documented grid: regular 0.25° (≈27.8 km) ERA5 cell-centre nodes covering the AOI bbox.
  District areal means are area-weighted intersections with the existing
  `public/data/admin/assam-districts.geojson` polygons.
- Every archive series carries `class: "reanalysis"`. The committed monsoon scenario series
  carry `class: "scenario"` and the timeline badge stays `SCENARIO`.
- 2022 JJAS (June–September) totals and the 2015–2025 mean are published per district in
  `data/series/rainfall.json`.
- An Open-Meteo current-window series is stored separately in
  `data/series/rainfall-forecast.json`, labelled `scenario` with
  `source_kind: "model_current_window"`; it is never mixed into the ERA5 archive.
- Provenance (endpoint, query, retrieval time, grid resolution, units) is in the rainfall
  `source` object and in `provenance.json`.

### District monsoon totals (mm, ERA5 reanalysis)

Filled from the committed file by the report generator below.

## P1.5 — potentially exposed residents (derived)

- Source: WorldPop 2020, 1 km Aggregated, India. REST catalogue
  `https://www.worldpop.org/rest/data/pop/wpgp?iso3=IND` was attempted; see the committed
  `rest_status` / fallback note. The published raster endpoint is on `data.worldpop.org`.
- Aggregation: district polygons (cell-centre containment), summing **masked** population
  (`pop × wet_fraction`) so district values reconcile to the S07 peak-mask value within
  1% (fractional 1 km coverage of the 90 m mask).
- Each district publishes `district_population` (raw zonal population),
  `potentially_exposed_residents` (masked zonal sum) and `exposed_share_of_district`.
- Totals are clipped to AOI v2 and published as `population_within_aoi` with
  `population_raster_scope: "AOI v2 polygon"`; the unclipped India-wide raster total is
  only `source.raster_total_unclipped` with `scope: "India"`.
- The only resident-count field is `potentially_exposed_residents`; `class: "derived"`.
- The method sentence, vintage, and uncertainty statement are published in
  `data/exposure/district-exposure.json` and rendered in the Risk and Methodology panels.
- This is a static population raster crossed with a synthetic flood mask, not an impact
  assessment. It does not estimate humanitarian impact, population movement, or loss of life.

## P1.6 — badges and ages

`OBSERVED · REANALYSIS · DERIVED · SCENARIO` badges and a `data as of … · N old` age appear on
the top bar, timeline, chart rows, rainfall context, map legend, layer rows, and all analysis
panels. The Validation tab exposes `OBSERVED` (Sentinel-1) and `DERIVED` (scorecard) with an age.
The timeline remains `SCENARIO`.

## Gates

`check-data` now enforces:

- three-way series class enum (`observed | reanalysis | scenario`);
- no `observed` label on an ERA5/reanalysis-derived series;
- `potentially_exposed_residents` as the only resident field in exposure, with no
  affected/displaced/casualty/death field;
- `data_as_of` on every published series and panel feed;
- new schemas for rainfall, current window, and exposure.

Pipeline `validate` adds V21 for the same rules and V22 for the four REVIEW-21 exposure value
gates. `pipeline/tests/test_phase1b.py` covers the class enum, the 122-day JJAS window, JJAS
arithmetic, ERA5-not-observed, exposure naming and the exposure value gates.

## District monsoon totals (blocked)

Not filled: `data/series/rainfall.json` does not exist because build-rainfall stopped on HTTP 429.
The district 2022 JJAS vs 2015–2025 JJAS means cannot be computed from the 142 cached pairs alone
(2023–2025 are incomplete), so no values are reported rather than interpolated ones.

## Exposed population totals

See `data/exposure/district-exposure.json` → `totals` and `peak_mask`. The generated file is the
authoritative record. Corrected values (REVIEW-21):

- Peak-mask potentially exposed residents: **5,807,467**.
- Sum of the 33 district masked values: **5,801,742** (0.099 % below the peak mask, inside the 1 %
  reconciliation gate).
- Population within AOI v2: **32,667,772** (`population_raster_scope: "AOI v2 polygon"`).
- Sum of raw district populations: **35,710,497**. This is the population total, not the exposed
  total; the old 35.7 M "exposed" figure was the unmasked district sum.
- Top five districts by exposed residents: Nagaon (690,431), Barpeta (412,221), Kamrup (381,099),
  Nalbari (354,022), Cachar (344,413).

## Caveat

ERA5 is a model-based reanalysis, not a gauge or satellite observation. It is biased in complex
terrain, and the 0.25° grid smooths orographic gradients. **Only JJAS is published; off-season
days are omitted because the Open-Meteo fetch is rate-limited, not because they are unavailable.**
The 2022 JJAS total and the 2015–2025 JJAS mean are computed from exactly that window.
Population exposure is a static WorldPop 2020 raster crossed with a synthetic flood mask; it is
not an impact assessment and carries no timing, warning, response, movement, or loss-of-life
information.
