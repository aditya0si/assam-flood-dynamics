# Baanh — Data Pipeline

**Status:** implementation specification · **Version:** 1.0 · **Date:** 2026-10-21
**Audience:** the builder who implements `pipeline/` and anyone reviewing whether the map is
earned by the data.
**Related:** `docs/ARCHITECTURE.md` (render contracts, budgets), `docs/MILESTONES.md` (acceptance),
`docs/ARCHITECT-SELF-AUDIT.md` (requirement coverage).

The pipeline is **offline**. It fetches the probed public sources once, computes a 12-step
HAND-based inundation scenario, writes simplified GeoJSON/JSON into `public/data/`, validates
every output, and refuses to publish on failure. The browser never runs Python and never needs a
private API.

Nothing in this document is an operational forecast. The only real inputs are terrain,
administrative boundaries, mapped rivers, and (P1) OSM facilities. Rainfall, stage, and the
scenario threshold are **synthetic**; inundation and risk are **derived** from those inputs.
Every output carries that class.

---

## 1. Output contract at a glance

```text
public/data/
├─ manifest.json
├─ provenance.json
├─ scenario.json
├─ validation-report.json
├─ admin/assam-districts.geojson
├─ admin/assam-state.geojson
├─ hydro/assam-rivers.geojson
├─ flood/frame-index.json
├─ flood/frames/step-00.png … step-11.png
├─ flood/flood-summary.json
├─ risk/risk-zones.geojson
├─ risk/district-risk.json
├─ risk/hotspots.geojson                  (P1)
├─ series/monsoon-series.json
├─ series/cross-sections.json             (P1)
├─ series/rainfall.json                    (P1.3 ERA5 reanalysis)
├─ series/rainfall-forecast.json           (P1.3 current window, separate)
├─ exposure/district-exposure.json         (P1.5 WorldPop derived)
├─ basemap/assam-hillshade.webp
├─ assets/critical-facilities.geojson     (P1)
├─ gauges/virtual-gauges.geojson          (P1)
└─ validation/scorecard.json              (P1)
```

- Coordinates in every GeoJSON are **WGS84 / EPSG:4326**, longitude then latitude, 5 decimal
  places (~1 m), RFC 7946 winding.
- All analysis happens in **EPSG:32646** at **90 m** (§3).
- Area values are geodesic (WGS84 ellipsoid), in km², never planar degrees².
- Every feature has `"class"`; series carry `observed | reanalysis | scenario`. UI badges are
  `OBSERVED | REANALYSIS | DERIVED | SCENARIO` and every data surface carries a `data as of` age.
- No output contains a field for casualties, affected people, displacement, agency id, incident
  id, relief camp, or deployment ETA. Those fields do not exist in the schema and are banned by
  validation V13.

---

## 2. Sources, licences, and what is actually used

| Source | Exact endpoint | Used for | Licence / attribution | Runtime? |
|---|---|---|---|---|
| AWS Terrarium elevation tiles | `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png` | DEM mosaic, HAND, hillshade, 3D terrain | Mapzen/Amazon elevation tiles; attribution shown (“Elevation: AWS Terrarium / Mapzen”). Verify terms before public launch. | Yes (terrain), pipeline for DEM |
| Esri World Imagery | `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` | Satellite drape only; no analysis | Esri, Maxar, Earthstar Geographics and contributors; attribution required in the map | Yes (imagery), not pipeline |
| geoBoundaries | `https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/` | Assam ADM2 districts, dissolved state outline | CC BY 4.0 (geoBoundaries gbOpen); attribution shown | No; committed output |
| OSM Overpass | `https://overpass-api.de/api/interpreter` | River centrelines; P1 hospitals/clinics/schools | ODbL; “© OpenStreetMap contributors” shown | No; committed output |
| Natural Earth 10m rivers | Local/committed fallback copy of the Natural Earth 10m rivers GeoJSON (exact URL/path in `sources.json`) | River fallback if Overpass fails | Public domain | No; committed output |
| UNOSAT flood products | Portal reachable (per reference analysis) | **Not ingested in P0/P1.** Reserved for a future event-context cross-check. | UNOSAT terms; would be cited | No |
| ERA5 via Open-Meteo archive | `https://archive-api.open-meteo.com/v1/archive` | Daily precipitation JJAS 06-01 → 09-30 for 2015–2025, district areal means; off-season days omitted because the fetch is rate-limited, not because they are unavailable | Open-Meteo; ERA5 © ECMWF/C3S, CC BY 4.0 | No; committed output |
| Open-Meteo current window | `https://api.open-meteo.com/v1/forecast` | Current-window model guidance, stored separately | Open-Meteo, CC BY 4.0 | No; committed output |
| WorldPop 2020 | REST catalogue `https://www.worldpop.org/rest/data/pop/wpgp?iso3=IND`; published 1 km raster from `data.worldpop.org` | Static population aggregate to peak mask and districts | WorldPop, CC BY 4.0 | No; committed output |

Natural Earth is the documented fallback for the **rivers** source, not an additional layer or a
sixth dataset. The five probed layers remain terrain, satellite basemap, districts, rivers, and
event context; the first four are used, and UNOSAT is explicitly not used in the first build.

**Source discipline.** Only the documented sources above, or committed pipeline output, feed the
app. Phase 1b adds exactly two: ERA5 reanalysis rainfall (with a separate current-window file) and
WorldPop 2020 population for a derived exposure estimate. No discharge API, gauge API, building
footprint, or administrative unit beyond geoBoundaries ADM2 is added. If a source is unavailable,
the pipeline uses the documented fallback or fails; it does not substitute a plausible-looking
dataset.

**What is real vs synthetic.**

| Element | Class | Basis |
|---|---|---|
| Terrain/elevation | `source` | AWS Terrarium DEM, z11 |
| District boundaries and state outline | `source` | geoBoundaries ADM2, dissolved for state |
| Rivers | `source` | OSM Overpass, Natural Earth fallback |
| Hospitals/clinics/schools (P1) | `source` | OSM Overpass, completeness unverified |
| Rainfall series | `scenario` | Parameterised monsoon curve; no gauge record |
| ERA5 daily precipitation and district monsoon totals | `reanalysis` | ERA5 model reanalysis; never observed; JJAS 06-01..09-30 only (rate-limited fetch, not unavailable data) |
| Open-Meteo current window | `scenario` | Model current-window guidance; stored separately, not observed |
| Population exposure | `derived` | WorldPop 2020 × synthetic peak mask, zonal-summed as `pop × wet_fraction`; `potentially_exposed_residents`, `district_population`, `exposed_share_of_district`; totals clipped to AOI v2 as `population_within_aoi` |
| Main-stem stage anomaly | `scenario` | Parameterised; relative to a pre-monsoon baseline, not a gauge datum |
| Stage above local drainage | `scenario` | Model driver for HAND thresholds |
| Inundation extent/depth | `scenario` | Derived from DEM + channels + synthetic stage |
| Risk zones, district ranking, hotspots | `derived` | Formulas in §9, no demographics |
| Virtual gauges (P1) | `scenario` | Stations placed on mapped rivers; no agency, code, or datum |

No real 2022 (or other year) casualty, displacement, or incident figure is used. If one is ever
quoted, it must be cited in this file and labelled `reference` in the UI.

---

## 3. AOI, CRS, and resolution

<!-- amended: REVIEW-02 -->

### 3.1 Definition

`AOI_v2 = (inside Assam) ∩ (DEM ≤ 120 m)`. The 2 km edge buffer is kept for raster continuity
only; it is **not** part of the reported AOI v2 area and does not count as flood extent.

| Parameter | Value | Notes |
|---|---|---|
| AOI v2 core | `(inside Assam) ∩ (DEM ≤ 120 m)` | The valley-floor analysis domain. The review measured 52,358 km² at this grid; the committed mask measures 52,240.7 km² |
| AOI v2 edge buffer | `2 km` | Used so edge cells can see terrain/channels just outside the core; never added to area or flood metrics |
| Channel clip | `AOI v2 + 5 km` | Channel ways are clipped to this buffer; a way whose midpoint is outside it is excluded from both model and display |
| AOI bbox (WGS84) | `[89.55, 23.95, 96.15, 28.15]` | Assam plus a ~15–20 km regional buffer; includes edge terrain in Bhutan/Meghalaya/Arunachal/Bangladesh for continuity |
| Analysis CRS | `EPSG:32646` (WGS 84 / UTM zone 46N) | Metres; correct for distance transforms and raster algebra |
| Analysis resolution | `90 m × 90 m` | 1.3× the ~69 m native ground resolution of z11 Terrarium at 26°N |
| Output CRS | `EPSG:4326` | MapLibre/GeoJSON; areas computed geodesically |
| Assam mask | Dissolved union of filtered ADM2 polygons | Used for the Assam denominator and containment, not as the flood mask |
| Metric denominators | AOI v2, Assam `78,523 km²`, flood-prone area `31,050 km²` | Every peak-extent claim is reported against all three |
| No-data | `-9999` in GeoTIFF; `null`/absent in JSON | Never `0`, which is a valid elevation |

The flood-prone denominator is the Government of Assam, Water Resources Department statistic:
31.05 lakh hectares against a state area of 78.523 lakh hectares (39.6 %). It is a
**flood-prone-area statistic, not a single event’s observed extent**, and it is not ingested as a
layer; `provenance.json` records the source, retrieval date and that caveat.

At 90 m the AOI rectangle is roughly 42 million cells (≈168 MB per float32 raster). The distance
transform needs a few full-size arrays; the budget is ≤3 GB peak RSS and ≤1.5 GB disk for
intermediates. A 30 m grid would be ~9× the cells and is explicitly P2.

EPSG:32646 is chosen over Web Mercator because nearest-drainage distance and polygon area should
be in metres; the AOI’s western edge is ~0.45° outside the zone’s nominal 90°E boundary, where
UTM scale error is still negligible for a 90 m screening model. It is chosen over a bespoke
Albers projection to avoid an extra CRS definition that a reviewer cannot check at a glance.

### 3.2 Why this AOI

- The hill districts carry about 33 % of Assam; a uniform stage over the full state is not a
  meaningful floodplain model. AOI v2 keeps the valley floor and reports that limitation.
- The 2 km buffer matters: a valley-edge cell must be able to see a channel just outside the
  valley floor. The buffer is continuity, not counted area.
- The 5 km channel clip matters: it keeps river-mouth and edge geometry continuous without
  importing upstream foreign reaches (Bhutan, Tibet, Meghalaya).
- The bbox is deliberately rectangular. A river-corridor polygon would save cells but would make
  the AOI definition harder to audit and would clip tributaries.
- If AOI v2 excludes a district that is genuinely flood-prone, that must be stated in the run
  report; the 120 m threshold must not be stretched to manufacture coverage.

---

## 4. Environment and conventions

<!-- amended: REVIEW-02 -->

Python 3.11+ (64-bit). Commands are run from the repository root. The examples use PowerShell;
the POSIX equivalent differs only in activation. A virtual environment is recommended for a
clean machine but is **not required**; if the listed packages are already importable, skip the
venv steps. Do not treat 3.11 as a hard pin—any 3.11+ interpreter with the packages works.

```powershell
python -m venv .venv          # optional; skip if the environment already has the packages
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r pipeline/requirements.txt
python -m pip install -e pipeline
python -m baanh_pipeline.cli --help
```

`pipeline/requirements.txt` pins: `numpy`, `scipy`, `rasterio`, `shapely`, `pyproj`, `Pillow`,
`mercantile`, `requests`, `jsonschema`, `pytest`. No GDAL system install is required if the
binary wheels resolve; record the resolved versions in `provenance.json`.

Conventions for every stage:

- The fenced commands use PowerShell continuation (backtick). In bash/git-bash, remove the
  backticks and either keep each command on one line or replace them with `\`.
- The command exits `0` only on success and non-zero on any unhandled error.
- Writes are atomic (temp file + `os.replace`) so a failed stage cannot leave a half file.
- Each stage appends a fragment to `pipeline/work/provenance/<stage>.json` with source URLs,
  fetch timestamps, command, versions, and output paths.
- Raw responses are cached under `pipeline/cache/`; re-running a stage does not refetch unless
  `--refresh` is passed.
- All JSON is UTF-8, no BOM, `allow_nan=False`.

### 4.1 Stage map

| Stage | Command subcommand | Input | Output | Committed? |
|---|---|---|---|---|
| 00 | environment | — | optional virtualenv, installed package | No |
| 01 | `fetch-terrain` | AOI, sources config | raw Terrarium tiles, tile index | No (cache) |
| 02 | `fetch-boundaries` | AOI, sources config | raw geoBoundaries ADM2 | No (cache) |
| 03 | `fetch-rivers` | AOI, sources config | raw river GeoJSON + source record | No (cache) |
| 04 | `build-dem` | tiles | `dem-90m.tif`, `assam-hillshade.webp` | DEM no; hillshade yes |
| 05 | `build-admin` | ADM2 raw | districts base, state GeoJSON, centroids | State yes; base intermediate |
| 06 | `build-rivers` | raw river + DEM + state | AOI v2 masks, simplified rivers, channel lines | Rivers yes; masks/channels intermediate |
| 07 | `burn-rivers` | DEM, channels | burned DEM, channel mask | No |
| 08 | `compute-hand` | burned DEM, mask | HAND, distance, metadata | No |
| 09 | `build-inundation` | HAND, mask, scenario | per-step wet masks, flood frames, summary | Frames/summary yes; masks no |
| 10 | `build-risk` | masks, HAND, districts | risk zones, ranking, hotspots, districts GeoJSON | Yes |
| 11 | `build-series` | scenario, summary, transects | monsoon series, cross-sections | Yes |
| 12 | `build-assets` (P1) | OSM, stack, frames, districts | critical facilities | Yes |
| 13 | `build-gauges` (P1) | rivers, summary | virtual gauges | Yes |
| 14 | `validate` | all public data | validation report + exit code | Yes |
| 15 | `publish` | validated data | manifest, provenance | Yes |
| 16 | `build-validation` (P1) | Earth Search Sentinel-1 GRD, DEM, frames | `validation/scorecard.json` | Yes (scorecard only; no scene or mask) |
| 17 | `build-rainfall` (P1.3) | Open-Meteo archive + current window, district polygons | `series/rainfall.json`, `series/rainfall-forecast.json` | Yes |
| 18 | `build-exposure` (P1.5) | WorldPop 2020 raster, peak mask, districts | `exposure/district-exposure.json` | Yes |

M0 runs stages **01–11, 14, 15**. Stages 12–13 are optional P1 outputs; when omitted, the
manifest simply has no entry for them and the app hides those panels. Stage 16
(`build-validation`) is the Phase 1a Sentinel-1 scorecard and is run after stages 09–15; it
commits only the scorecard JSON, never a scene or mask. Phase 1b adds stages 17–18: ERA5
reanalysis rainfall (with a separate current-window file) and the WorldPop-derived exposure
estimate. Stages 04–11 are the minimum to produce the M0 data; stages 01–03 fetch its sources.

---

## 5. Stages: exact commands, inputs, outputs

Every command below is the contract the builder implements in `cli.py`. Flags are mandatory
unless marked `[optional]`. Paths are repository-relative.

### Stage 01 — fetch terrain

```powershell
python -m baanh_pipeline.cli fetch-terrain `
  --aoi pipeline/config/aoi.json `
  --sources pipeline/config/sources.json `
  --zoom 11 `
  --cache pipeline/cache/terrain
```

- **Input:** AOI bbox/CRS; Terrarium URL template; zoom 11.
- **Process:** compute the tile range covering the bbox, fetch in a bounded pool (≤6 concurrent),
  retry 3× with backoff, record tile failures. Do not silently accept missing tiles.
- **Output:** `pipeline/cache/terrain/{z}/{x}/{y}.png`; `pipeline/work/terrain-index.json`
  (`zoom`, `tile_count`, `missing_tiles`, `bbox_mercator`, `fetched_at`, per-tile bytes).
- **Failure:** >0.5% missing tiles → exit non-zero with the missing list. The DEM cannot be
  fabricated from neighbouring tiles.

### Stage 02 — fetch boundaries

```powershell
python -m baanh_pipeline.cli fetch-boundaries `
  --aoi pipeline/config/aoi.json `
  --sources pipeline/config/sources.json `
  --cache pipeline/cache/boundaries
```

- **Input:** geoBoundaries current ADM2 API URL; AOI.
- **Process:** download the API JSON, resolve the `gjDownloadURL`, download the GeoJSON, filter
  to Assam (`shapeISO` begins `IN-AS`, or the state name is Assam after normalisation), retain
  `shapeID`, `shapeName`, `shapeISO`, geometry. Do not merge renamed/new districts by hand.
- **Output:** `pipeline/cache/boundaries/geoboundaries-ind-adm2.json`,
  `pipeline/cache/boundaries/source-meta.json` (URL, `lastUpdated`, licence, feature count,
  Assam feature count, SHA-256).
- **Failure:** zero Assam features, or non-polygon geometry → exit non-zero.

### Stage 03 — fetch rivers

```powershell
python -m baanh_pipeline.cli fetch-rivers `
  --aoi pipeline/config/aoi.json `
  --sources pipeline/config/sources.json `
  --cache pipeline/cache/rivers `
  --overpass-timeout 180
```

- **Input:** Overpass interpreter URL; AOI bbox; Natural Earth 10m fallback path/URL.
- **Query:** `way["waterway"~"^(river|stream|canal|drain)$"](bbox); out geom;` with a 180 s
  timeout. Overpass is slow (~30 s observed); the timeout is not a reason to fail the build if
  the fallback is complete.
- **Process:** normalise `waterway`, keep `name`, `osm_id`; clip to AOI buffered 5 km; discard
  zero-length lines. If Overpass fails after 3 attempts, load Natural Earth 10m rivers and mark
  `source: "natural-earth"` on every feature.
- **Output:** `pipeline/cache/rivers/rivers-raw.geojson`,
  `pipeline/cache/rivers/rivers-source.json` (`source_used`, `attempts`, `feature_count`,
  `fetched_at`, `fallback_reason`).
- **Fallback limit:** if Natural Earth is also unavailable, exit non-zero. HAND without channels
  is meaningless; do not produce an empty-channel “flood”.

### Stage 04 — build DEM and fallback hillshade

```powershell
python -m baanh_pipeline.cli build-dem `
  --tiles pipeline/cache/terrain `
  --index pipeline/work/terrain-index.json `
  --aoi pipeline/config/aoi.json `
  --out-dem pipeline/work/dem-90m.tif `
  --out-hillshade public/data/basemap/assam-hillshade.webp `
  --hillshade-width 2000
```

- **Input:** cached Terrarium tiles; AOI; tile index.
- **Process:**
  1. Mosaic tiles in Web Mercator at z11, decode `elevation = R*256 + G + B/256 - 32768`.
  2. Warp to EPSG:32646 at 90 m with bilinear resampling; clip to the AOI rectangle.
  3. Fill small voids with `rasterio.fill.fillnodata` (max search 100 cells); if voids remain,
     mark them nodata and count them. No synthetic terrain interpolation beyond this.
  4. Compute a hillshade (315° azimuth, 45° altitude) and write an 8-bit grayscale WebP, width
     2000 px, quality 82, with the AOI Mercator corner coordinates recorded in provenance.
  5. Set `dem-90m.tif` nodata to `-9999`; compression `deflate`, tiled.
- **Output:** `pipeline/work/dem-90m.tif`; `public/data/basemap/assam-hillshade.webp` (≤1.5 MB);
  `pipeline/work/dem-meta.json` (size, min/max, void count, CRS, transform, hillshade bounds).
- **Validation:** min elevation plausibility −50 to 100 m for Assam; max 0–8,000 m. A DEM that
  is all zeros or has ocean values inside Assam is a failed fetch, not a model result.

### Stage 05 — build administrative layers

```powershell
python -m baanh_pipeline.cli build-admin `
  --raw pipeline/cache/boundaries/geoboundaries-ind-adm2.json `
  --aoi pipeline/config/aoi.json `
  --out-districts pipeline/work/districts-base.geojson `
  --out-state public/data/admin/assam-state.geojson `
  --out-centroids pipeline/work/district-centroids.json
```

- **Input:** filtered Assam ADM2 features.
- **Process:** reproject to EPSG:32646 for validity/area, `make_valid`, drop slivers <0.05 km²,
  compute geodesic area with `pyproj.Geod`, compute a representative point guaranteed inside the
  polygon (`shapely.representative_point`), simplify for display at 150 m tolerance, write WGS84.
  Dissolve all districts for the state outline, simplify at 200 m, compute state area.
- **Output:**
  - `pipeline/work/districts-base.geojson` — source geometry + `district_id`, `name`, `iso`,
    `area_km2`, `centroid_lon`, `centroid_lat`; no risk fields yet.
  - `public/data/admin/assam-state.geojson` — dissolved outline; `state_id` `IN-AS`.
  - `pipeline/work/district-centroids.json` — label points for DOM markers (not committed).
- **Validation:** every polygon valid; every centroid inside its polygon; no duplicate
  `district_id`; state union area within 1% of the sum of district areas (before simplification).

### Stage 06 — AOI v2, channel policy v2, display rivers

<!-- amended: REVIEW-02 -->

```powershell
python -m baanh_pipeline.cli build-rivers `
  --raw pipeline/cache/rivers/rivers-raw.geojson `
  --dem pipeline/work/dem-90m.tif `
  --state public/data/admin/assam-state.geojson `
  --aoi pipeline/config/aoi.json `
  --out public/data/hydro/assam-rivers.geojson `
  --out-channels pipeline/work/channel-lines.geojson
```

- **Input:** raw rivers; the 90 m DEM and dissolved state outline (to build AOI v2).
- **Process:** build `AOI_v2 = inside Assam ∩ DEM ≤ 120 m`, a 2 km edge mask and an AOI v2 + 5 km
  channel clip, and write them to `pipeline/work/`. Keep only `waterway=river`; drop `stream`,
  `canal`, `drain`, `ditch`. Clip to the 5 km buffer and require the way’s midpoint to be inside
  it. Drop clipped ways shorter than 2 km. The Brahmaputra main stem is `order 1`; all other
  rivers are `order 2`. Rasterise the candidate set with `all_touched=True` and 2-cell dilation
  for `order 1` only. If channel cells inside AOI v2 exceed 4.0 %, prune the shortest non-main
  ways until the share passes; record the pruned count and threshold. Display geometries simplify
  at 50 m and may be simplified further to meet the 1.0 MB cap, but the display set must never
  lose a way the model uses.
- **Output:** `public/data/hydro/assam-rivers.geojson` (display, ≤1.0 MB);
  `pipeline/work/channel-lines.geojson` (burn input); `pipeline/work/aoi-v2-*.tif` and
  `aoi-v2.json` (domain, buffer, clip and measured areas).
- **Validation:** at least one `order: 1` line; total channel length >500 km; every geometry
  valid; channel cells ≤4.0 % of AOI v2; zero model ways with midpoint outside AOI v2 + 5 km;
  every model way is `waterway=river`. If OSM returns only unnamed fragments, the fallback flag
  is recorded and shown in provenance.

### Stage 07 — burn channels into the DEM

<!-- amended: REVIEW-02 -->

```powershell
python -m baanh_pipeline.cli burn-rivers `
  --dem pipeline/work/dem-90m.tif `
  --channels pipeline/work/channel-lines.geojson `
  --out-dem pipeline/work/dem-burned.tif `
  --out-channels pipeline/work/channels-90m.tif `
  --burn-depth-m 3.0
```

- **Input:** 90 m DEM; the pruned river-only channel set.
- **Process:** rasterise channels at 90 m with `all_touched=True`; only the order-1 Brahmaputra
  main stem is dilated to 2 cells, every other river is 1 cell. For each channel cell sample the
  minimum DEM in a 5×5 window and subtract `burn_depth_m = 3.0`; write that value into
  `dem-burned.tif`; all other cells keep DEM. The burn is a **modelling device** to make the
  channel the local low point, not a surveyed incision depth. No monotonic downstream
  enforcement is attempted because OSM way direction is unreliable; this is a stated limitation.
- **Output:** `pipeline/work/dem-burned.tif`, `pipeline/work/channels-90m.tif` (uint8 0/1),
  `pipeline/work/burn-meta.json` (`channel_cells`, `channel_cells_aoi_v2`,
  `channel_cell_share_aoi_v2`, `burn_depth_m`, `dem_delta_min/max`).
- **Validation:** channel cells >0; channel cells inside AOI v2 ≤4.0 %; mean burned elevation <
  mean adjacent DEM by 1–6 m; no channel cell ends up above its pre-burn value.

### Stage 08 — nearest drainage, distance, HAND

```powershell
python -m baanh_pipeline.cli compute-hand `
  --dem-burned pipeline/work/dem-burned.tif `
  --channels pipeline/work/channels-90m.tif `
  --max-channel-distance-m 12000 `
  --out-hand pipeline/work/hand-90m.tif `
  --out-distance pipeline/work/channel-distance-90m.tif `
  --out-meta pipeline/work/hand-meta.json
```

- **Input:** burned DEM; channel mask.
- **Process:** exact Euclidean distance transform **on the channel mask**, 8-connected metric,
  with nearest-index output; sample the burned DEM at the nearest channel index; compute HAND;
  clamp negatives; apply the reachability limit; write float32 GeoTIFFs and metadata. Full
  algorithm in §7.
- **Output:** `hand-90m.tif` (m; `-9999` = no channel within 12 km), `channel-distance-90m.tif`
  (m), `hand-meta.json` (`valid_cells`, `nodata_cells`, `clamped_negative_cells`,
  `max_distance_m`, `p50_hand_m`, `p95_hand_m`, `channel_elevation_min/max`).
- **Validation:** HAND ≥0 everywhere valid; distance monotonic with mask distance; at least 80%
  of AOI v2 core cells valid HAND (warn below 85%); clamped negatives inside AOI v2 ≤6.0 %
  (V-A6); no NaN/Inf.

### Stage 09 — build the inundation sequence

<!-- amended: REVIEW-04 -->

```powershell
python -m baanh_pipeline.cli build-inundation `
  --dem pipeline/work/dem-burned.tif `
  --hand pipeline/work/hand-90m.tif `
  --distance pipeline/work/channel-distance-90m.tif `
  --channels pipeline/work/channels-90m.tif `
  --state public/data/admin/assam-state.geojson `
  --scenario pipeline/config/scenario.json `
  --frame-index public/data/flood/frame-index.json `
  --out-summary public/data/flood/flood-summary.json `
  --out-masks pipeline/work/inundation-masks `
  --out-frames-dir public/data/flood/frames
```

- **Input:** DEM/HAND/distance/channel mask; state outline; scenario steps; AOI v2 masks.
- **Process:** for each step, threshold HAND by `stage_m` inside AOI v2; apply the existing
  channel-proximity connectivity (a component must touch a channel cell or a cell within one
  cell of a channel); apply the **V-A9** component-area filter (drop 8-connected wet components
  smaller than 9 cells / 0.073 km²) — **no morphological opening anywhere**; derive the depth
  and its 5 classes from `depth = stage − max(HAND, 0)`; write the uint8 wet mask to
  `pipeline/work/inundation-masks/step-XX-wet.tif`; rasterise the class raster and write a
  half-resolution (≈180 m/px) paletted `step-XX.png` plus the step's `frame-index` entry. Do
  **not** polygonise bands, do **not** write per-band GeoJSON, do **not** build a float stack
  and do **not** write `inundation-stack.npz`. Full algorithm in §7.
- **Output:** `public/data/flood/frames/step-XX.png` (each ≤400 KB), `frame-index.json`
  (`bbox`, `width`, `height`, 5-class palette, per-step `file`/`area_km2`), `flood-summary.json`
  (with AOI v2 / Assam / flood-prone denominators, the V-A9 component audit and per-frame PNG
  bytes), `scenario.json` copy, and the uint8 mask cache (≤300 MB). There is no
  `flood-frames.geojson` and no per-step vector outline in M0.
- **Validation:** area non-decreasing on the rising limb (S00–S07), decreasing on recession
  (S08–S11), peak at S07; every frame present and valid; peak extent inside V-A4; V-A5 v4 is
  shape-based (median ≥0.7 m and ≤ peak stage − 0.5 m; p95 ≤ peak stage; p95 − median ≥0.6 m;
  clamped wet ≤30 %), computed on the area-filtered mask; every step carries `wet_cells` and
  the six `delay_deciles` (REVIEW-05 D2); clamped AOI ≤6 % (V-A6); V-A9 component counts,
  dropped area and `wet_cells` recorded and reproducible; V-A10 index/PNG agreement; wall time
  and artifacts inside V-A8; per-frame PNG ≤400 KB, animation tier ≤4.0 MB and `public/data/`
  ≤9.0 MB inside V09.

### Stage 10 — risk zones, district ranking, hotspots

<!-- amended: REVIEW-02 -->
<!-- amended: PHASE-0 -->

```powershell
python -m baanh_pipeline.cli build-risk `
  --masks pipeline/work/inundation-masks `
  --hand pipeline/work/hand-90m.tif `
  --distance pipeline/work/channel-distance-90m.tif `
  --channels pipeline/work/channels-90m.tif `
  --districts pipeline/work/districts-base.geojson `
  --scenario pipeline/config/scenario.json `
  --out-zones public/data/risk/risk-zones.geojson `
  --out-ranking public/data/risk/district-risk.json `
  --out-districts public/data/admin/assam-districts.geojson `
  --out-hotspots public/data/risk/hotspots.geojson
```

- **Input:** per-step uint8 wet masks; HAND/distance/channel mask; district polygons; scenario.
- **Process:** read each step’s mask, reconstruct depth as `stage_m - HAND` only where wet,
  accumulate duration and peak depth, classify risk zones, aggregate district metrics and score,
  join risk fields into the district GeoJSON, extract low-HAND distant pockets for hotspots. The
  Phase 0 pass also computes per-district peak depth context (`depth_over_1_5m_share`,
  `median_depth_m`) and `risk_class_area_share` over wet-at-peak area. Full formulas in §9. No
  float stack is read.
- **Output:** `risk-zones.geojson` (≤0.9 MB), `district-risk.json` (≤0.15 MB),
  `assam-districts.geojson` (≤1.2 MB), `hotspots.geojson` (≤0.10 MB).
- **Validation:** all scores 0–100; every district appears once in the ranking; `rank` is a
  dense descending ranking; no population/asset-loss field; hotspots inside Assam; zone classes
  match the score thresholds; district weights sum to 1.0 and are the values the score actually
  multiplies; `depth_over_1_5m_share` is not constant; the four `risk_class_area_share` values
  sum to 1.0 ± 0.01.

### Stage 11 — monsoon series and cross-sections

<!-- amended: REVIEW-02 -->

```powershell
python -m baanh_pipeline.cli build-series `
  --scenario pipeline/config/scenario.json `
  --summary public/data/flood/flood-summary.json `
  --dem pipeline/work/dem-90m.tif `
  --channels pipeline/work/channels-90m.tif `
  --transects pipeline/config/transects.json `
  --out-series public/data/series/monsoon-series.json `
  --out-profiles public/data/series/cross-sections.json
```

- **Input:** scenario config; flood summary; DEM/channel mask; transect endpoints. (No depth
  stack: stage 11 recomputes water surface from nearest-channel elevation and stage.)
- **Process:** emit the chart-ready synthetic rainfall/stage series and the scenario threshold
  (cross-checked against `flood-summary.json`); sample each transect at 2 km spacing, record
  ground elevation, HAND, and water surface/depth for all 12 steps. Depth follows REVIEW-03 B2:
  `depth_m = max(0, stage_m − max(HAND, 0))`, so it never exceeds the stage; `water_surface_m` is
  `ground_m + depth_m` for the same clamped bathtub surface. Samples with nodata HAND become
  `ground_m: null` and are omitted from the profile; the count is reported.
- **Output:** `monsoon-series.json` (≤0.05 MB), `cross-sections.json` (≤0.20 MB).
- **Validation:** 12 points per series; values identical to summary at each step (tolerance 1e−6);
  every transect has ≥30 valid samples; no NaN.

### Stage 12 — critical-facility exposure (P1)

<!-- amended: REVIEW-02 -->

```powershell
python -m baanh_pipeline.cli build-assets `
  --aoi pipeline/config/aoi.json `
  --sources pipeline/config/sources.json `
  --masks pipeline/work/inundation-masks `
  --hand pipeline/work/hand-90m.tif `
  --frame-index public/data/flood/frame-index.json `
  --districts public/data/admin/assam-districts.geojson `
  --out public/data/assets/critical-facilities.geojson
```

- **Input:** OSM Overpass; per-step uint8 wet masks; HAND; frame index; districts.
- **Query:** `(node["amenity"~"^(hospital|clinic|school)$"](bbox);); out body;` with a 180 s
  timeout. Names are taken from OSM `name`; missing names stay `null` (never invented).
- **Process:** keep points inside Assam; spatial-join to district; sample each step’s wet mask
  and compute depth as `stage_m - HAND` where wet; record peak depth, first wet step, and an
  exposure band. No float stack is read.
  **Completeness is unknown**; the output says so and the UI must show it. No capacity, staff,
  or operational status is inferred. Names are organisational labels only; if an OSM name looks
  like a personal name, write `null` rather than publishing it.
- **Output:** `critical-facilities.geojson` (≤1.0 MB).
- **Failure:** Overpass unavailable → omit this optional layer and record a warning; M0/M1 still
  pass without assets. Do not fall back to a hand-built facility list.

### Stage 13 — virtual gauges (P1)

```powershell
python -m baanh_pipeline.cli build-gauges `
  --rivers public/data/hydro/assam-rivers.geojson `
  --summary public/data/flood/flood-summary.json `
  --out public/data/gauges/virtual-gauges.geojson
```

- **Input:** mapped rivers; flood summary.
- **Process:** select 6–8 river vertices distributed across the main stem and two tributaries;
  each gets a stage series equal to the scenario stage (possibly with a stated reach offset of
  0 m; no fake local variation). Mark every station `synthetic`; no agency, station code, or
  datum. `river_name` is copied from OSM or `null`.
- **Output:** `virtual-gauges.geojson` (≤0.10 MB).
- **Validation:** all points within 500 m of a mapped river; 12 stage values each; labels contain
  “synthetic” or the UI supplies the badge.

### Stage 14 — validate

```powershell
python -m baanh_pipeline.cli validate `
  --data public/data `
  --config pipeline/config `
  --report public/data/validation-report.json `
  --version 2026.10.0
```

Runs V01–V20 and V-A1–V-A10 (§10), writes the report atomically, prints a one-line summary, and exits non-zero
if any `fail` check exists. Warnings are allowed only where §10 says so.

### Stage 15 — publish manifest and provenance

```powershell
python -m baanh_pipeline.cli publish `
  --data public/data `
  --version 2026.10.0 `
  --manifest public/data/manifest.json `
  --provenance public/data/provenance.json
```

- **Input:** validated public data; per-stage provenance fragments.
- **Process:** compute SHA-256 and byte size for every file; assign `class`, `tier`
  (`critical|animation|optional|fallback`), and description; aggregate provenance entries;
  write manifest/provenance atomically. Refuse to publish if `validation-report.json` is missing
  or `status != "pass"`. Verify no file exceeds its cap.
- **Output:** `manifest.json`, `provenance.json`, and a final printed table of file sizes.
- **Validation:** manifest covers every data file except itself; every file has a hash; hashes
  match; `dataset_version` matches the CLI `--version`; `step_count` is 12.

### Stage 16 — Sentinel-1 validation scorecard (P1.1/P1.2)

```powershell
python -m baanh_pipeline.cli build-validation `
  --aoi pipeline/config/aoi.json `
  --sources pipeline/config/sources.json `
  --core-mask pipeline/work/aoi-v2-core-90m.tif `
  --dem pipeline/work/dem-90m.tif `
  --frame-index public/data/flood/frame-index.json `
  --frames public/data/flood/frames `
  --scenario pipeline/config/scenario.json `
  --out public/data/validation/scorecard.json `
  --cache pipeline/cache/s1
```

- **Input:** Earth Search STAC (`sentinel-1-grd`), AOI bbox, the AOI core mask (used only
  for scene selection and the diagnostic legacy area, never for the validity domain), the
  existing DEM (slope diagnostic), the committed PNG frames and frame-index, and the scenario
  peak step.
- **STAC search:** collection `sentinel-1-grd` at
  `https://earth-search.aws.element84.com/v1`, bbox from `config/aoi.json`, datetime
  `2022-06-01/2022-07-31`, instrument mode `IW`, product type `GRD`, VV asset required. The
  **earliest and latest usable acquisitions** are selected; within each date the slice with the
  largest AOI-core overlap is used. Scene binaries and masks are cached under
  `pipeline/cache/s1/` and are never committed.
- **Anonymous S3:** the stage sets `AWS_NO_SIGN_REQUEST=YES` and `AWS_REGION=us-west-2` before
  opening the `s3://` VV asset. The measurement COG reports `crs: None`; it carries WGS84 GCPs,
  so the stage transforms the GCPs into EPSG:32646 (zone from `proj:centroid`) and assigns that
  CRS before reprojection. On hosts where GDAL cannot complete the anonymous TLS request, a
  loopback range proxy around `requests` serves the same S3 bytes; the stage logs which path was
  used.
- **Decimation:** VV is read at `out_shape = (height // 9, width // 9)` with
  `Resampling.average` (native 10 m → ~90 m). It is never read at native resolution.
- **Calibration:** the STAC asset `schema-calibration-vv` is downloaded from the SAFE annotation
  (`annotation/calibration/calibration-iw-vv.xml`) and parsed per vector. Both scenes expose
  **27 vectors × 642 samples**; `A` is `sigmaNought`, interpolated over the decimated grid, and
  the scene is converted to **σ0 dB = 20·log10(DN / A)**. `method.calibration` publishes the
  source, vector count, samples per vector and `A_median` (595.42 for the 2022 scenes). Missing
  calibration is a stage error, never a silent fallback.
- **Water mask:** a **fixed −16 dB σ0** threshold, stated before scoring: it is a conservative
  C-band VV open-water threshold for monsoon conditions, in the low tail of the calibrated
  land/water distribution. The rationale is published in `method.threshold_rationale`; threshold
  choice, not the LUT, is the dominant residual uncertainty. Sensitivity is published at
  **−14 / −16 / −18 dB in σ0 space**, each row with observed area, TP/FP/FN area and
  IoU/precision/recall/F1. Components smaller than **5 analysis cells** (≈4 ha at 90 m) are
  dropped. Cells whose DEM slope exceeds **10°** are **not** removed from the shipped mask;
  the slope branch is evaluated and published as a diagnostic (REVIEW-19). The slope operator
  and unit are documented in `method.slope_filter` (§6.18).
- **Grid and validity domain (REVIEW-19):** masks reproject to **EPSG:32646, 90 m, aligned
  to the frame grid** with nearest resampling. A fractional coverage raster
  (`Resampling.average` of the valid source mask) is kept so partial cells are explicit.
  The validity domain is the **full SAR footprint** on the frame grid: `coverage >= 0.5`,
  intersected with the **regional AOI polygon** (`config/aoi.json` bbox, densified into
  EPSG:32646), then validity connected components smaller than 5 cells removed. The
  valley-floor **AOI core is not used** for validity. The old core clip retained only
  ~3,735 km² of a ~43,389 km² scene and ~97 % of the model's wet area, so it inflated IoU
  and recall; it is published only as
  `validity_attrition.legacy_aoi_core_clipped_area_km2`.
- **Validity attrition:** every scene publishes `validity_attrition` with km² after
  `raw_sar_valid → slope_filtered → aoi_clipped → component_filtered → final`, plus
  `with_slope_area_km2`, `without_slope_area_km2` and the shipped path. No step is silent.
- **Slope filter (REVIEW-19):** slope is computed from `pipeline/work/dem-90m.tif`
  (not a new DEM) as the **central-difference gradient**: `dz_dy, dz_dx =
  np.gradient(dem_m, 90, 90)`, `slope_deg = degrees(arctan(hypot(dz_dx, dz_dy)))`. The
  operator and unit **degrees** are published in `method.slope_filter`. The 10° filter is
  **evaluated and reported**, not applied to the final domain: across this SAR scene it
  removes ~25,850 km² of hill terrain and cannot be shown not to remove valley-floor
  cells. Both `with_slope` and `without_slope` validity areas are published per scene.
- **Mask provenance:** the validity mask is built from SAR VV validity, the AOI polygon,
  terrain and geometry **only**. It must never reference the flood frames, the HAND wet
  mask or any district/risk artifact. `method.mask_provenance` records the allowed and
  prohibited inputs and asserts `model_conditioned = false`. The model is applied only
  after the validity domain is fixed.
- **Coverage rule:** if a selected scene cannot be fetched, or the valid observed share of
  its SAR footprint is below **90 %**, the stage exits non-zero with the exact error. It
  does not substitute another date and does not lower the bar. A single Sentinel-1 GRD
  slice covers ~97.8 % of its own GCP-corner scene on this AOI (the old ~7 % figure was the
  AOI-core intersection, not the scene); `scene_area_km2`,
  `validity_area_km2` and `validity_fraction_of_scene` are published per scene.
- **Scoring:** the committed PNG frames are decoded with frame-index placement (paletted class
  >0 = wet) and compared with the observed mask at every step. The stage reports the
  best-matching step (IoU) and the scenario peak S07 (IoU, precision, recall, F1, area bias) at
  the fixed −16 dB threshold. Sensitivity at −14/−16/−18 dB is scored against the same S07 model
  on the same **full-footprint** validity domain, so the rows are directly comparable.
  Metrics are **area-weighted**, not cell counts, so the published TP/FP/FN km² satisfy
  `TP + FP = modelled_in_validity_km2` and `TP + FN = observed_area_km2` within 0.5 km²
  per threshold. Observed area, `modelled_in_validity_km2` and area bias use the same
  domain; `validity_area_km2` is published per scene so every ratio denominator is
  visible.
- **Stop/report:** the calibration LUT summary, fixed σ0 threshold and rationale, per-threshold
  sensitivity, observed water area/fraction, scene/validity area and ratio, validity
  attrition, with/without slope areas, modelled area inside validity, best-match step/IoU
  and peak metrics are written to `validation/scorecard.json`. A bad IoU is the finding;
  it is not improved to fit.
- **Output:** `public/data/validation/scorecard.json` (≤128 KB) only. No scene, mask or cache
  file is committed.

---


## 6. Output schemas

Common GeoJSON envelope:

```json
{
  "type": "FeatureCollection",
  "name": "…",
  "schema_version": "1.0.0",
  "dataset_version": "2026.10.0",
  "class": "scenario",
  "features": []
}
```

Feature-level `class` is required and must be one of the five values. `label` is a human string
suitable for a map popup or legend; it must not over-claim (e.g. “Scenario inundation”, not
“Observed flood”).

### 6.1 `manifest.json`

| Field | Type | Unit / values | Notes |
|---|---|---|---|
| `schema_version` | string | semver | `1.0.0` |
| `dataset_version` | string | `YYYY.MM.N` | Passed to `publish`; loader cache-busts |
| `app_min_version` | string | semver | App refuses a dataset requiring a newer app |
| `scenario_id` | string | id | `assam-monsoon-composite-v1` |
| `generated_at` | string | ISO 8601 UTC | Informational, not part of hashes |
| `crs` | string | `EPSG:4326` | All GeoJSON |
| `analysis_crs` | string | `EPSG:32646` | Provenance |
| `bbox` | number[4] | degrees | AOI |
| `step_count` | integer | 12 | Must equal scenario |
| `load_tiers` | object | arrays of paths | `critical`, `animation`, `optional`, `fallback` |
| `files` | array | see below | One entry per committed data file |
| `attribution` | array | see below | Shown in UI |

`files[]`: one entry per committed data file **except `manifest.json` itself** (it cannot contain
its own hash). The validation report is included.

| Field | Type | Notes |
|---|---|---|
| `path` | string | relative to `public/`, e.g. `data/flood/frame-index.json` |
| `bytes` | integer | exact size |
| `sha256` | string | lowercase hex |
| `class` | enum | five-class label |
| `tier` | enum | `critical`, `animation`, `optional`, `fallback` |
| `description` | string | one line, UI/provenance |

`attribution[]`: `{ "name": string, "url": string, "licence": string }`.

### 6.2 `provenance.json`

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-10-21T00:00:00Z",
  "entries": [
    {
      "id": "terrain",
      "dataset": "AWS Terrarium DEM mosaic",
      "class": "source",
      "source_name": "AWS Terrain Tiles (Terrarium)",
      "source_url": "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
      "licence": "Mapzen/Amazon elevation tiles; verify terms",
      "fetched_at": "2026-10-21T00:00:00Z",
      "pipeline": [
        { "stage": "01", "command": "python -m baanh_pipeline.cli fetch-terrain …", "version": "1.0.0" },
        { "stage": "04", "command": "python -m baanh_pipeline.cli build-dem …", "version": "1.0.0" }
      ],
      "output_paths": ["data/basemap/assam-hillshade.webp"],
      "notes": "Bilinear warp to 90 m EPSG:32646; hillshade 315°/45°."
    }
  ]
}
```

Required entries: terrain, boundaries, rivers, flood frames, risk, series, hillshade,
validation (Sentinel-1 scorecard), and (if present) assets, gauges, UNOSAT note. `notes` must
state assumptions that affect the layer.

### 6.3 `scenario.json`

```json
{
  "schema_version": "1.0.0",
  "scenario_id": "assam-monsoon-composite-v1",
  "name": "Composite monsoon scenario (synthetic)",
  "class": "synthetic",
  "not_a_forecast": true,
  "year_label": null,
  "step_count": 12,
  "total_days": 136,
  "peak_step": 7,
  "threshold_stage_m": 1.5,
  "grid": {
    "crs": "EPSG:32646",
    "resolution_m": 90,
    "bbox": [89.55, 23.95, 96.15, 28.15],
    "nodata": -9999
  },
  "steps": [
    { "step": 0, "label": "01 Jun", "day_offset": 0, "phase": "onset" }
  ],
  "model": {
    "name": "HAND-threshold scenario",
    "version": "hand-v2",
    "burn_depth_m": 3.0,
    "max_channel_distance_m": 12000,
    "connectivity": { "enabled": true, "max_channel_distance_m": 90 },
    "component_filter": {
      "method": "component_area_filter",
      "min_cells": 9,
      "min_area_km2": 0.073,
      "opening": "none",
      "applied_before_statistics": true
    },
    "depth_bands_m": [0.0, 0.5, 1.5, 3.0, null],
    "frame_resolution_scale": 2
  },
  "assumptions": ["…"],
  "limitations": ["…"]
}
```

`steps[]` fields: `step` integer 0–11; `label` string (`DD Mon`, no year); `day_offset` integer
0–136; `phase` enum `onset|rising|peak|receding`. `depth_bands_m` has five edges; the last band is
open-ended (`null`).

`assumptions` must include: AOI v2 (inside Assam, DEM ≤120 m) and its 2 km edge buffer;
`waterway=river` only; uniform stage over mapped channels; flat water surface per step;
HAND threshold with channel-proximity connectivity and the ≥9-cell component-area filter (no
opening); half-resolution 5-class PNG frames; no calibration; synthetic hydrograph. `limitations`
must include: no hydrodynamic routing; no levee failure; mapped channels incomplete; 90 m grid;
no population/asset-loss estimate.

### 6.4 `admin/assam-districts.geojson`

Feature properties:

| Field | Type | Unit | Notes |
|---|---|---|---|
| `district_id` | string | — | geoBoundaries `shapeID` |
| `name` | string | — | `shapeName` |
| `iso` | string | — | `shapeISO` |
| `area_km2` | number | km² | Geodesic, source polygon |
| `centroid_lon` | number | degrees | Representative point |
| `centroid_lat` | number | degrees | Representative point |
| `risk_score` | number \| null | 0–100 | Derived; null if no valid cells |
| `risk_class` | enum \| null | `low\|moderate\|high\|very_high` | Derived |
| `rank` | integer \| null | 1..N | Derived, dense descending score |
| `valid_area_share` | number | 0–1 | Share of district with valid HAND |
| `class` | string | — | `source` |
| `derived_fields` | string[] | — | `["risk_score","risk_class","rank"]` |
| `label` | string | — | e.g. “District boundary (source); risk attributes (derived)” |

### 6.5 `admin/assam-state.geojson`

| Field | Type | Unit | Notes |
|---|---|---|---|
| `state_id` | string | — | `IN-AS` |
| `name` | string | — | `Assam` |
| `area_km2` | number | km² | Geodesic |
| `district_count` | integer | — | Features dissolved |
| `class` | string | — | `source` |
| `label` | string | — | “Assam outline, dissolved from ADM2 (source)” |

Geometry: `Polygon` or `MultiPolygon`, simplified at 200 m.

### 6.6 `hydro/assam-rivers.geojson`

| Field | Type | Unit | Notes |
|---|---|---|---|
| `river_id` | string | — | `osm:way/123` or `ne:<id>` |
| `name` | string \| null | — | OSM/NE name; null allowed |
| `waterway` | enum | — | `river` only in the model; the enum keeps legacy values for display compatibility |
| `order` | integer | 1–2 | 1 = Brahmaputra main stem (2-cell dilation), 2 = other river (1 cell) |
| `source` | enum | — | `osm\|natural-earth` |
| `source_id` | string | — | Native id |
| `class` | string | — | `source` |
| `label` | string | — | “River centreline (OSM/ODbL)” |

### 6.7 `flood/frame-index.json` and `flood/frames/step-XX.png`

<!-- amended: REVIEW-04 -->

M0 ships raster frames, not per-band GeoJSON. `frame-index.json` is loaded once and is enough
for the app to place every PNG without knowing the projection:

```json
{
  "schema_version": "1.0.0",
  "dataset_version": "2026.10.0",
  "scenario_id": "assam-monsoon-composite-v1",
  "class": "scenario",
  "bbox": [89.55, 23.95, 96.15, 28.15],
  "width": 3733,
  "height": 2611,
  "crs": "EPSG:4326",
  "source_crs": "EPSG:32646",
  "source_resolution_m": 90,
  "frame_resolution_m": 180,
  "frame_scale": 2,
  "classes": [
    { "id": 0, "label": "dry", "color": "#000000", "alpha": 0, "min_m": null, "max_m": 0.0 },
    { "id": 1, "label": "0.0-0.5", "color": "#9ecae1", "alpha": 235, "min_m": 0.0, "max_m": 0.5 },
    { "id": 2, "label": "0.5-1.5", "color": "#4292c6", "alpha": 235, "min_m": 0.5, "max_m": 1.5 },
    { "id": 3, "label": "1.5-3.0", "color": "#08519c", "alpha": 240, "min_m": 1.5, "max_m": 3.0 },
    { "id": 4, "label": "3.0+", "color": "#03135e", "alpha": 245, "min_m": 3.0, "max_m": null }
  ],
  "steps": [
    { "id": 0, "label": "01 Jun", "stage_m": 0.3, "file": "frames/step-00.png",
      "area_km2": 0.0, "png_bytes": 0, "png_wet_cells": 0, "png_area_km2": 0.0 }
  ]
}
```

| Field | Type | Unit | Notes |
|---|---|---|---|
| `bbox` | number[4] | ° | `[west, south, east, north]`, WGS84, the footprint of every PNG |
| `width`, `height` | integer | px | Half the analysis raster dimensions; each pixel is ≈180 m |
| `classes` | object[5] | — | `id` 0 (transparent/dry) plus the four wet depth classes; `color` is baked into the PNG and read by the legend |
| `steps[].file` | string | — | Relative to `flood/`: `frames/step-XX.png` |
| `steps[].area_km2` | number | km² | Area-filtered wet area at the step; must match the PNG wet cells × cell area within 1 % (V-A10) |

`step-XX.png` is a paletted 5-class PNG at **half the analysis resolution** (≈180 m/px):
class 0 is fully transparent, classes 1–4 are the depth bands. The PNG is optimised with
`optimize=True` and a palette + `tRNS` chunk, and is gated **raw** at 400 KB per frame. No
per-band GeoJSON and no per-step vector outline are produced in M0; a peak-extent outline is
allowed only as P1 with its own cap. `flood-summary.json` keeps the per-step area/district
shares and, from REVIEW-05 D2, also publishes `wet_cells` plus the six `delay_deciles` (§6.8).

### 6.8 `flood/flood-summary.json`

<!-- amended: REVIEW-02 -->

```json
{
  "schema_version": "1.0.0",
  "scenario_id": "assam-monsoon-composite-v1",
  "class": "scenario",
  "peak_step": 7,
  "series_class": {
    "rainfall": "synthetic",
    "mainstem_stage": "synthetic",
    "backwater": "synthetic",
    "inundated_area": "scenario"
  },
  "steps": [
    {
      "step": 7,
      "step_label": "25 Aug",
      "day_offset": 85,
      "phase": "peak",
      "rainfall_mm_day": 10,
      "mainstem_stage_m": 2.11,
      "backwater_m": 1.59,
      "stage_m": 3.70,
      "above_threshold": true,
      "inundated_area_km2": 0.0,
      "wet_cells": 0,
      "new_inundation_km2": 0.0,
      "receded_area_km2": 0.0,
      "median_depth_m": 0.0,
      "p95_depth_m": 0.0,
      "delay_deciles": {
        "p10": 0.0,
        "p25": 0.0,
        "p50": 0.0,
        "p75": 0.0,
        "p90": 0.0,
        "p95": 0.0
      },
      "max_depth_m": 0.0,
      "mean_depth_m": 0.0,
      "clamped_wet_share": 0.0,
      "clamped_aoi_share": 0.0,
      "component_filter": {
        "method": "component_area_filter",
        "min_cells": 9,
        "min_area_km2": 0.073,
        "opening": "none",
        "connectivity": true,
        "connectivity_max_distance_m": 90.0,
        "raw_components": 0,
        "connectivity_components": 0,
        "components_before": 0,
        "components_after": 0,
        "dropped_components": 0,
        "area_before_km2": 0.0,
        "dropped_area_km2": 0.0,
        "raw_area_km2": 0.0
      },
      "frame_file": "frames/step-07.png",
      "frame_png_bytes": 0,
      "frame_width": 3733,
      "frame_height": 2611,
      "png_wet_cells": 0,
      "png_area_km2": 0.0,
      "affected_district_count": 0,
      "valid_cell_share": 0.0
    }
  ],
  "totals": {
    "max_area_km2": 0.0,
    "peak_stage_m": 3.70,
    "scenario_days": 136,
    "districts_any_inundation": 0,
    "median_depth_at_peak_m": 0.0,
    "p95_depth_at_peak_m": 0.0,
    "clamped_wet_share_at_peak": 0.0,
    "clamped_aoi_share": 0.0,
    "max_depth_at_peak_m": 0.0,
    "aoi_v2_area_km2": 52240.7,
    "assam_area_km2": 78220.6,
    "flood_prone_area_km2": 31050.0,
    "peak_extent_share_of_aoi_v2": 0.0,
    "peak_extent_share_of_assam": 0.0,
    "peak_extent_share_of_flood_prone_area": 0.0,
    "plausibility_band": {
      "min_km2": 4000.0,
      "max_km2": 12000.0,
      "max_share_of_flood_prone_area": 0.40,
      "note": "V-A4 band chosen by the reviewer from REVIEW-02; not a calibrated observation."
    }
  }
}
```

Field semantics:

- `rainfall_mm_day`: synthetic areal rainfall index for the step, mm/day.
- `mainstem_stage_m`: synthetic stage anomaly relative to a pre-monsoon baseline, metres.
  **Not** a gauge reading or a level above mean sea level.
- `backwater_m`: synthetic additive allowance for tributary/backwater stacking, metres.
- `stage_m`: scenario water level above local drainage, metres; the value applied to HAND.
  It is defined exactly as `stage_m = mainstem_stage_m + backwater_m` (validated by V11); the
  additive form is a declared simplification, not a hydrodynamic backwater solution.
- `above_threshold`: `stage_m >= scenario.threshold_stage_m` (2.0). A model flag, not an official warning.
- `inundated_area_km2`: union of wet cells inside AOI v2 at the step, after the V-A9
  component-area filter.
- `wet_cells`: count of wet analysis cells (90 m) in the same area-filtered mask. It is an
  artifact, not a derived estimate; V-A9 checks it against the committed wet mask.
- `new_inundation_km2`: cells wet at `t` and dry at `t−1` (0 at t=0).
- `receded_area_km2`: cells dry at `t` and wet at `t−1` (0 at t=0).
- `median_depth_m`, `p95_depth_m`, `max_depth_m`, `mean_depth_m`: over wet cells at the step;
  mean is area-weighted. Depth is `stage_m − max(HAND, 0)` (REVIEW-03 B2), so every value is
  ≤ the step stage. The median and p95 are the V-A5 statistics on the area-filtered mask
  (including channel cells).
- `delay_deciles`: REVIEW-05 D2. The 10th, 25th, 50th, 75th, 90th and 95th percentile of depth
  over wet cells, keyed `p10`…`p95`. `p50` equals `median_depth_m` and `p95` equals
  `p95_depth_m`; the six values are published independently and no consumer may average them
  into one number. They are the shape evidence behind the V-A5 spread rule: a distribution
  piled up against the bathtub bound is visible in `p75`–`p95`, not in the median alone.
- `clamped_wet_share`: share of the step's wet area whose burned ground lies below its nearest
  channel elevation (HAND clamped to 0). V-A5 caps the peak-step value at 30 %.
- `clamped_aoi_share`: share of valid AOI v2 cells that are clamped; V-A6 caps it at 6 %.
- `component_filter`: V-A9 record. `raw_components` is the 8-connected count of the HAND
  threshold mask; `connectivity_components` is the count after the channel-proximity test (when
  enabled); `components_before`/`components_after` bound the ≥9-cell area filter, and
  `dropped_area_km2` is the area removed. `opening` must be `none`. The values are recomputed
  from the wet masks by V-A9, not trusted from the JSON.
- `frame_file`, `frame_png_bytes`, `frame_width`, `frame_height`, `png_wet_cells`,
  `png_area_km2`: measured PNG artifact and its wet-cell area; V-A10 checks the PNG, the
  frame-index entry and `inundated_area_km2` agree within 1 %.
- `affected_district_count`: districts with >1 km² wet.
- `valid_cell_share`: share of AOI v2 core cells with valid HAND. A coverage caveat.
- `share_of_aoi_v2`, `share_of_assam`, `share_of_flood_prone_area`: the same step area against
  the three denominators; the peak shares are repeated in `totals`.
- All numbers are `null` if undefined for a step, never `NaN`.

### 6.9 `risk/risk-zones.geojson`

| Field | Type | Unit | Notes |
|---|---|---|---|
| `zone_id` | string | — | `RZ-0001`, deterministic sort by class then centroid |
| `risk_class` | enum | — | `low\|moderate\|high\|very_high` |
| `risk_score` | number | 0–100 | Area-weighted mean cell score in the polygon |
| `mean_hand_m` | number | m | Mean HAND of cells |
| `mean_duration_days` | number | days | Mean wet duration |
| `peak_depth_m` | number | m | Maximum depth in the polygon over all steps |
| `area_km2` | number | km² | Geodesic |
| `class` | string | — | `derived` |
| `model_version` | string | — | `hand-v2` |
| `label` | string | — | e.g. “Derived risk zone · high” |

Geometry: `Polygon`/`MultiPolygon`, simplified 100 m, min 0.05 km². Only cells wet in at least
one step are classified, so the layer is **scenario-conditional risk**, not all-time flood risk.
Because 12k 90 m components cannot fit the fixed 0.9 MB raw cap, stage 10 vectorises a
block-majority grid: the smallest factor in `risk.zone.vector_block_factors` whose output fits the
cap is used, with a block retained when at least `risk.zone.vector_min_wet_fraction` of its 90 m
cells are wet. `risk_score`, `mean_hand_m`, `mean_duration_days`, `peak_depth_m` are still
computed from the 90 m cells under each zone. In A5 the chosen grid is 1,080 m (factor 12) at a
45% wet threshold; the 100 m simplification and 0.05 km² floor are unchanged. This is a
cartographic generalisation required by the size cap, not a change to the risk formula.

### 6.10 `risk/district-risk.json`

<!-- amended: PHASE-0 -->

```json
{
  "schema_version": "1.0.0",
  "scenario_id": "assam-monsoon-composite-v1",
  "class": "derived",
  "generated_at": "2026-10-21T00:00:00Z",
  "weights_version": "area-duration-v1",
  "weights": { "area_share": 0.5625, "duration": 0.4375 },
  "reference_values": {
    "area_share_saturation": 0.60,
    "duration_saturation_days": 90
  },
  "severity": {
    "formula": "severity_index = 100 * (p - min(p)) / (max(p) - min(p)), p = z(depth_over_1_5m_share) * z(median_depth_m) * z(mean_duration_days)",
    "z_statistic": "population z-score across the scoreable districts: (x - mean) / std(ddof=0)",
    "inputs": ["depth_over_1_5m_share", "median_depth_m", "mean_duration_days"],
    "normalisation": { "method": "min-max over the district products", "min": 0.0, "max": 0.0, "n_districts": 33 },
    "z_population": {
      "depth_over_1_5m_share": { "mean": 0.0, "std": 0.0 },
      "median_depth_m": { "mean": 0.0, "std": 0.0 },
      "mean_duration_days": { "mean": 0.0, "std": 0.0 }
    }
  },
  "risk_class_area_share": {
    "low": 0.0,
    "moderate": 0.0,
    "high": 0.0,
    "very_high": 0.0
  },
  "districts": [
    {
      "rank": 1,
      "district_id": "IN-AS-…",
      "name": "…",
      "area_km2": 0.0,
      "peak_flooded_area_km2": 0.0,
      "area_share": 0.0,
      "mean_duration_days": 0.0,
      "p90_peak_depth_m": 0.0,
      "depth_over_1_5m_share": 0.0,
      "median_depth_m": 0.0,
      "risk_score": 0.0,
      "risk_class": "very_high",
      "severity_index": 0.0,
      "severity_rank": 1,
      "drivers": ["area", "duration"],
      "valid_area_share": 0.0,
      "class": "derived"
    }
  ],
  "counts": { "total": 0, "very_high": 0, "high": 0, "moderate": 0, "low": 0, "no_data": 0 }
}
```

- `weights_version` names the applied weight set. `weights` contains exactly the two scored
  drivers and sums to 1.0. The depth weight is absent: bathtub peak depth saturates at the stage,
  so it is reported as context and never multiplied into the score.
- `risk_class_area_share` is the **area share of the four per-cell risk classes over all analysis
  cells wet at the peak step (S07) with valid HAND inside AOI v2**. The denominator is peak wet
  area, not district polygon area and not all wet cells from every step; the four values therefore
  sum to 1.0. This is the explicit denominator the panel review asked for.
- `depth_over_1_5m_share` is the count share of the district's cells wet at peak whose bathtub
  depth is strictly greater than 1.5 m. `median_depth_m` is the plain median depth over the same
  wet cells. Both are reported context bars in the Risk panel; neither is scored.
- `p90_peak_depth_m` remains published for continuity, but it is 3.7 m for every district at the
  peak step because the bathtub surface is capped by the 3.7 m stage.
- `drivers` is a deterministic array of the top two weighted contributions, labels `area`,
  `duration`. No demographic field exists.
- `valid_area_share` is the share of the district's raster cells with valid HAND. The UI shows a
  `coverage …%` badge and the row annotation `Scored on the AOI-covered share only` when it is
  below 0.75.
- `severity_index` (0–100) and `severity_rank` are the separate P1.7 profile. They are never
  added to `risk_score`; `risk_score` and `rank` remain the extent-led score and rank. The exact
  formula and every constant are in §9.5 and in the top-level `severity` object, so the index is
  reproducible from the committed JSON without a hidden constant.
- The district GeoJSON joins `severity_index` and `severity_rank` alongside `risk_score`,
  `risk_class` and `rank`. The Risk panel labels `risk_score` as **Extent score** and shows both
  ranks on every row.

### 6.11 `risk/hotspots.geojson` (P1)

Point features:

| Field | Type | Unit | Notes |
|---|---|---|---|
| `hotspot_id` | string | — | `HS-01` |
| `rank` | integer | — | By area descending |
| `reason` | enum | — | `low_hand_backwater_pocket` |
| `area_km2` | number | km² | Pocket area |
| `hand_mean_m` | number | m | Mean HAND in pocket |
| `distance_to_channel_m` | number | m | Minimum distance to a channel |
| `first_step` | integer | 0–11 | First step wet |
| `peak_depth_m` | number | m | Max depth |
| `centroid_lon` | number | degrees | Point |
| `centroid_lat` | number | degrees | Point |
| `district_id` | string \| null | — | Spatial join |
| `class` | string | — | `derived` |
| `label` | string | — | “Derived inundation hotspot · low-HAND pocket (not a breach)” |

### 6.12 `series/monsoon-series.json`

```json
{
  "schema_version": "1.0.0",
  "scenario_id": "assam-monsoon-composite-v1",
  "class": "synthetic",
  "series": [
    {
      "id": "rainfall",
      "label": "Rainfall (synthetic)",
      "unit": "mm/day",
      "class": "synthetic",
      "source_note": "Parameterised monsoon curve; no gauge record.",
      "points": [{ "step": 0, "day": 0, "value": 6 }]
    },
    {
      "id": "stage_above_drainage",
      "label": "Stage above local drainage (scenario)",
      "unit": "m",
      "class": "scenario",
      "source_note": "Synthetic stage applied to the HAND threshold; not a gauge reading.",
      "points": [{ "step": 0, "day": 0, "value": 0.5 }]
    }
  ],
  "threshold": {
    "id": "scenario_threshold",
    "label": "Scenario threshold",
    "value": 1.5,
    "unit": "m",
    "class": "scenario",
    "note": "Model parameter, not an official danger level."
  }
}
```

Values must equal `flood-summary.json` at each step (V11). `day` is `day_offset`.

### 6.13 `series/cross-sections.json` (P1)

```json
{
  "schema_version": "1.0.0",
  "scenario_id": "assam-monsoon-composite-v1",
  "class": "derived",
  "transects": [
    {
      "transect_id": "T1",
      "label": "Valley transect T1 (west)",
      "start": [90.10, 26.20],
      "end": [91.40, 26.30],
      "length_km": 0.0,
      "sample_count": 0,
      "samples": [
        {
          "distance_km": 0.0,
          "lon": 90.10,
          "lat": 26.20,
          "ground_m": 0.0,
          "hand_m": 0.0,
          "water_surface_m": [0.0],
          "depth_m": [0.0]
        }
      ],
      "class": "derived",
      "label_note": "DEM + HAND profile; not a surveyed section."
    }
  ]
}
```

`water_surface_m` and `depth_m` are arrays of 12 values indexed by step. `sample_count` counts
valid samples. No NaN; invalid samples are omitted and counted in provenance.

### 6.14 `assets/critical-facilities.geojson` (P1)

| Field | Type | Unit | Notes |
|---|---|---|---|
| `osm_id` | string | — | `node/123` |
| `facility` | enum | — | `hospital\|clinic\|school` |
| `name` | string \| null | — | OSM `name`; never invented |
| `district_id` | string \| null | — | Spatial join |
| `lon` | number | degrees | Point |
| `lat` | number | degrees | Point |
| `peak_depth_m` | number \| null | m | Scenario peak at point |
| `first_step` | integer \| null | 0–11 | First wet step |
| `exposure_class` | enum | — | `none\|minor\|moderate\|major` (thresholds §9.4) |
| `class` | string | — | `source` |
| `derived_fields` | string[] | — | `["peak_depth_m","first_step","exposure_class"]` |
| `completeness` | string | — | `incomplete-osm` |
| `label` | string | — | “OSM facility (source); exposure derived from scenario” |

### 6.15 `gauges/virtual-gauges.geojson` (P1)

| Field | Type | Unit | Notes |
|---|---|---|---|
| `gauge_id` | string | — | `VG-01`…`VG-08` |
| `label` | string | — | “Virtual gauge VG-01 (synthetic)” |
| `river_name` | string \| null | — | From OSM |
| `river_id` | string | — | From rivers layer |
| `lon` | number | degrees | Point on/near river |
| `lat` | number | degrees | Point on/near river |
| `stage_series_m` | number[12] | m | Scenario stage |
| `peak_step` | integer | 0–11 | 7 |
| `class` | string | — | `synthetic` |
| `note` | string | — | “No agency, station code, datum, or measurement.” |

### 6.16 `validation-report.json`

<!-- amended: REVIEW-02 -->

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-10-21T00:00:00Z",
  "dataset_version": "2026.10.0",
  "status": "pass",
  "checks": [
    {
      "id": "V05",
      "name": "Rising-limb area monotonicity",
      "status": "pass",
      "expected": "non-decreasing S00–S07",
      "actual": "…",
      "detail": "steps 0–7"
    },
    {
      "id": "V-A5",
      "name": "Peak depth",
      "status": "pass",
      "expected": "peak-step median ≥0.7 m and ≤ peak stage − 0.5 m; p95 ≤ peak stage; p95 − median ≥0.6 m; clamped wet ≤30%; every step has wet_cells and ordered delay_deciles",
      "actual": "…",
      "detail": "…"
    }
  ],
  "counts": { "files": 29, "steps": 12, "features": 0, "gates": 30, "failures": 0, "warnings": 0 }
}
```

`checks` must contain every ID in `V01–V20` and `V-A1–V-A10` (30 gates); a missing ID is a
failure, not a skip. `status` is `pass` only if every check is `pass` or an allowed `warn`. A
`fail` makes `publish` refuse.

### 6.17 `basemap/assam-hillshade.webp`

Binary, not JSON. Contract: 8-bit grayscale WebP, width 2000 px, height derived from the AOI
aspect ratio, quality 82, ≤1.5 MB. It is **not** georeferenced in the file; the app positions it
with the AOI Mercator corners from `manifest.json` (`bbox`) and `provenance.json`. It contains no
labels, no water, no flood extent—only relief—so it cannot be mistaken for an observation.

---

### 6.18 `validation/scorecard.json` (P1)

The schema required by REVIEW-17 P1.2, corrected by REVIEW-18 and REVIEW-19. The scorecard is
`derived`, not `source`: it compares a scenario extent shape with real Sentinel-1 acquisitions
and is not an event hindcast. Numbers below are the committed 2022-07-31 scene after the
REVIEW-19 full-footprint correction.

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-10-21T20:15:46Z",
  "method": {
    "collection": "sentinel-1-grd",
    "threshold_method": "fixed_sigma0",
    "threshold_db": -16.0,
    "threshold_rationale": "Fixed -16 dB sigma0 threshold for C-band VV open water in monsoon conditions: …",
    "sensitivity_db": [-14.0, -16.0, -18.0],
    "calibration": {
      "source": "Sentinel-1 SAFE annotation/calibration/calibration-iw-vv.xml (STAC asset schema-calibration-vv; anonymous S3)",
      "vectors": 27,
      "samples_per_vector": 642,
      "A_median": 595.42265
    },
    "slope_mask_deg": 10.0,
    "slope_filter": {
      "operator": "central-difference gradient of the 90 m DEM: dz_dy, dz_dx = np.gradient(dem_m, 90, 90); slope_deg = degrees(arctan(hypot(dz_dx, dz_dy)))",
      "unit": "degrees",
      "threshold_deg": 10.0,
      "applied_to_validity": false,
      "with_slope_area_km2": 33134.4027,
      "without_slope_area_km2": 84841.9364,
      "removed_by_slope_km2": 51707.5336,
      "reason": "The 10 degree filter removes hill terrain across this SAR scene; because it also removes valley-floor cells, REVIEW-19 allows dropping it. Both branches are published; the final domain uses without_slope."
    },
    "validity_definition": "SAR VV valid samples (finite calibrated sigma0) reprojected to the 90 m frame grid with average coverage >= 0.5, intersected with the regional AOI polygon, then validity connected components smaller than 5 cells removed. The valley-floor AOI-core clip and the 10 degree slope filter are NOT applied to the final domain; both are published as diagnostics in validity_attrition.",
    "mask_stack_version": "review19-full-footprint-v2",
    "scene_area_method": "Quadrilateral through the four corner GCPs transformed to EPSG:32646; not the bbox area. 2022-07-31 gives 43,391 km2 (reviewer 43,389 km2).",
    "mask_provenance": {
      "allowed_inputs": ["sentinel1_vv_sigma0_validity", "aoi_polygon", "dem_slope", "grid_geometry"],
      "prohibited_inputs": ["flood_frames", "hand_wet_mask", "district_risk_artifacts"],
      "model_conditioned": false,
      "note": "The validity domain is fixed before any flood frame is read. The model is applied only after the domain is fixed."
    },
    "min_component_cells": 5,
    "resampling": "average→nearest",
    "crs": "EPSG:32646",
    "resolution_m": 90
  },
  "scenes": [
    {
      "scene_id": "S1A_IW_GRDH_1SDV_20220731T233912_20220731T233937_044351_054B00",
      "datetime": "2022-07-31T23:39:24.699506Z",
      "platform": "sentinel-1a",
      "relative_orbit": 4,
      "threshold_db": -16.0,
      "threshold_rationale": "Fixed -16 dB sigma0 threshold for C-band VV open water in monsoon conditions: …",
      "scene_area_km2": 43391.2866,
      "validity_area_km2": 42419.6064,
      "validity_fraction_of_scene": 0.977607,
      "with_slope_validity_area_km2": 16566.2113,
      "without_slope_validity_area_km2": 42419.6064,
      "validity_attrition": {
        "raw_sar_valid": {"area_km2": 42419.6064, "removed_km2": 0.0, "applied_to_final": true, "reason": "Full SAR VV validity on the 90 m frame grid: finite calibrated sigma0, average coverage >= 0.5. No AOI-core clip."},
        "slope_filtered": {"area_km2": 16566.2113, "removed_km2": 25853.395, "applied_to_final": false, "reason": "Diagnostic branch: DEM slope <= 10 degrees. Not applied to the shipped domain; the published final domain is the without_slope branch."},
        "aoi_clipped": {"area_km2": 42419.6064, "removed_km2": 0.0, "applied_to_final": true, "legacy_aoi_core_area_km2": 3743.0227, "legacy_aoi_core_removed_km2": 38676.5837, "reason": "Regional AOI bbox (89.55-96.15 E, 23.95-28.15 N), densified to EPSG:32646. The valley-floor AOI core is not used."},
        "component_filtered": {"area_km2": 42419.6064, "removed_km2": 0.0, "applied_to_final": true, "reason": "Validity connected components smaller than 5 cells removed."},
        "final": {"area_km2": 42419.6064, "removed_km2": 0.0, "applied_to_final": true, "reason": "Shipped validity domain = raw_sar_valid -> aoi_clipped -> component_filtered; slope branch not applied."},
        "shipped_path": ["raw_sar_valid", "aoi_clipped", "component_filtered", "final"],
        "with_slope_area_km2": 16566.2113,
        "without_slope_area_km2": 42419.6064,
        "legacy_aoi_core_clipped_area_km2": 3743.0227,
        "note": "The former AOI-core clip is published only as a diagnostic. It is not part of the shipped validity domain."
      },
      "slope_filter": {
        "operator": "central-difference gradient of the 90 m DEM: dz_dy, dz_dx = np.gradient(dem_m, 90, 90); slope_deg = degrees(arctan(hypot(dz_dx, dz_dy)))",
        "unit": "degrees",
        "threshold_deg": 10.0,
        "applied_to_validity": false,
        "with_slope_area_km2": 16566.2113,
        "without_slope_area_km2": 42419.6064,
        "removed_by_slope_km2": 25853.395,
        "reason": "The 10 degree filter removes hill terrain across this SAR scene; because it also removes valley-floor cells, REVIEW-19 allows dropping it."
      },
      "mask_provenance": {
        "allowed_inputs": ["sentinel1_vv_sigma0_validity", "aoi_polygon", "dem_slope", "grid_geometry"],
        "prohibited_inputs": ["flood_frames", "hand_wet_mask", "district_risk_artifacts"],
        "model_conditioned": false,
        "note": "The validity domain is fixed before any flood frame is read. The model is applied only after the domain is fixed."
      },
      "modelled_in_validity_km2": 553.5251,
      "observed_area_km2": 490.1876,
      "observed_water_fraction_of_aoi": 0.011556,
      "observed_water_fraction_of_validity": 0.011556,
      "best_match_step": 7,
      "best_match_iou": 0.099464,
      "peak_step": {
        "step": 7,
        "modelled_area_km2": 553.5251,
        "iou": 0.099464,
        "precision": 0.17058,
        "recall": 0.19262,
        "f1": 0.180931,
        "area_bias_pct": 12.9211
      },
      "sensitivity": [
        {
          "threshold_db": -16.0,
          "observed_area_km2": 490.1876,
          "observed_water_fraction_of_validity": 0.011556,
          "true_positive_km2": 94.4201,
          "false_positive_km2": 459.105,
          "false_negative_km2": 395.7675,
          "iou": 0.099464,
          "precision": 0.17058,
          "recall": 0.19262,
          "f1": 0.180931
        }
      ]
    }
  ],
  "summary": {
    "mean_iou_over_scenes": 0.093433,
    "mean_precision": 0.154183,
    "mean_recall": 0.192766,
    "mean_validity_area_km2": 42420.9682,
    "mean_validity_fraction_of_scene": 0.977611,
    "worst_scene": "S1A_IW_GRDH_1SDV_20220601T233908_20220601T233933_043476_0530F2",
    "caveats": ["This is an extent-shape comparison against real Sentinel-1 acquisitions, not an event hindcast.", "σ0 calibration applied from the SAFE calibration LUT. …", "Validity is the full Sentinel-1 footprint on the frame grid (coverage ≥0.5, regional AOI only), not the valley-floor AOI core. …"]
  }
}
```

- `method.calibration` records the `schema-calibration-vv` source, `vectors` (27),
  `samples_per_vector` (642) and `A_median` (595.42); `check-data` requires all four.
- `scene_area_km2` is the ground area of the scene quadrilateral from its four corner GCPs
  transformed to EPSG:32646. It is **not** the STAC bbox area. `validity_fraction_of_scene =
  validity_area_km2 / scene_area_km2`; both are required.
- `validity_area_km2` is the **full-footprint** comparison domain: SAR VV validity on the
  90 m frame grid (`coverage ≥0.5`) ∩ regional AOI polygon, validity components <5 cells
  removed. It is **not** the valley-floor AOI core. `modelled_in_validity_km2` is the S07
  model area measured inside that same domain; together they make every ratio denominator
  visible.
- `validity_attrition` publishes km² after `raw_sar_valid → slope_filtered → aoi_clipped →
  component_filtered → final`, with `removed_km2`, `applied_to_final`, a reason per step,
  `with_slope_area_km2`, `without_slope_area_km2`, and the legacy AOI-core area as a
  diagnostic. `final.area_km2` must equal `validity_area_km2`.
- `slope_filter.operator` is the central-difference gradient of the 90 m DEM; `unit` is
  `degrees`; the 10° threshold is evaluated but `applied_to_validity = false`. Both
  `with_slope_area_km2` and `without_slope_area_km2` are published per scene.
- `mask_provenance` lists the allowed inputs (SAR validity, AOI polygon, DEM slope, grid
  geometry) and prohibits the flood frames, HAND wet mask and district/risk artifacts.
  `model_conditioned` is `false`; the model is read only after the domain is fixed.
- `observed_area_km2` is the fixed −16 dB σ0 water area over the validity domain.
  `observed_water_fraction_of_validity` is `observed_area_km2 / validity_area_km2` (the
  older `observed_water_fraction_of_aoi` key is kept equal for compatibility).
- `best_match_step` and `best_match_iou` are the best of the 12 committed frames. `peak_step`
  is always S07 and carries the full precision/recall/F1/area-bias row.
- `sensitivity` is an array of exactly three rows, one per fixed σ0 threshold
  (−14/−16/−18 dB). Each row publishes `observed_area_km2`, its validity fraction, TP/FP/FN
  area, IoU, precision, recall and F1, all scored against the same S07 model and domain.
  Metrics are area-weighted, so **TP + FP = modelled_in_validity_km2** and **TP + FN =
  observed_area_km2** within 0.5 km² per threshold; `check-data` enforces both.
  The −16 dB row equals the `peak_step` metrics.
- `summary.mean_iou_over_scenes` is the mean of the per-scene best-match IoU. `mean_precision`
  and `mean_recall` are the mean of the per-scene **S07** precision/recall at −16 dB.
  `mean_validity_area_km2` and `mean_validity_fraction_of_scene` summarise the corrected
  footprint. `worst_scene` is the scene with the lowest best-match IoU.
- The three caveat sentences are required and checked by `check-data`; no caveat may claim
  calibration was unavailable. A low IoU is the finding and ships unchanged.

## 7. Inundation model specification

This is the exact model a builder must implement. It is a **HAND-threshold screening model**, not
a hydrodynamic simulation. Every simplification is stated; do not fill the gaps with invented
physics.

### 7.1 Constants

<!-- amended: REVIEW-02 -->

| Constant | Value | Meaning |
|---|---|---|
| `RES_M` | 90 | Analysis cell size, metres |
| `CRS` | EPSG:32646 | Analysis projection |
| `BURN_DEPTH_M` | 3.0 | Channel lowering, metres |
| `MAX_CHANNEL_DISTANCE_M` | 12000 | Beyond this, HAND is undefined |
| `MIN_COMPONENT_CELLS` | 9 | ≈0.073 km² at 90 m; component-area filter floor |
| `DEPTH_BANDS_M` | `[0, 0.5, 1.5, 3.0, null]` | Four wet classes plus transparent/dry |
| `CONNECTIVITY` | 8-connected | Component must touch a channel cell or one cell from it |
| `FRAME_SCALE` | 2 | PNG at half the analysis resolution (≈180 m/px) |
| `PEAK_STEP` | 7 | 25 Aug |
| `ALERT_STAGE_M` | 2.0 | Scenario flag threshold |

### 7.2 Step A — DEM mosaic

1. Decode each z11 Terrarium PNG as `z = R*256 + G + B/256 - 32768` (metres).
2. Mosaic in its native Web Mercator grid, then warp to EPSG:32646 at 90 m with bilinear
   resampling. Record the affine transform and nodata.
3. Fill only small voids (≤100-cell search). A large void is a fetch failure; fail.
4. Clip to the AOI rectangle. Keep a boolean `inside_assam` mask from the dissolved state
   polygon; it is used at output time, not to alter the DEM.

### 7.3 Step B — channel policy and burn-in

<!-- amended: REVIEW-02 -->

**Channel policy v2 (A2), applied in stage 06 before any burn:**

1. Keep only `waterway=river`. Drop `stream`, `canal`, `drain`, `ditch`.
2. Clip to `AOI_v2` buffered by 5 km. A way whose midpoint is outside that buffer is excluded
   from both the burn and the display layer — no upstream foreign reaches.
3. Drop ways shorter than 2 km after clipping.
4. Keep the Brahmaputra main stem as `order 1`; 2-cell dilation applies to it only. All other
   channels are 1 cell, no dilation.
5. **Hard gate:** channel cells inside AOI v2 ≤4.0 %. If exceeded, prune the shortest non-main
   ways until it passes; record how many were pruned and the length threshold in
   `pipeline/work/aoi-v2.json` and `provenance.json`.
6. The display layer (`hydro/assam-rivers.geojson`) shows the same kept set as the model. It may
   be simplified further to meet the 1.0 MB cap; it must never show a river the model does not
   use or omit one it does.

**Burn-in (stage 07):**

1. Rasterise the pruned `channel-lines.geojson` at 90 m, `all_touched=True`, with the main stem
   (`order 1`) dilated to 2 cells and all other channels 1 cell. This is `channel_mask`.
2. For each channel cell, `z_burn = min(DEM[5×5 neighbourhood]) - 3.0`.
3. Write `z_burn` only at channel cells into `dem-burned.tif`; all other cells keep DEM.
4. Do **not** enforce a downstream monotonic elevation. OSM way direction is not reliable, and a
   false monotonic pass would create a fake longitudinal profile. The consequence—occasional
   local channel highs—is limited by the 5×5 minimum and is listed as a limitation.

Why burn at all: a DEM at 90 m often puts the photographed ground surface above the water
surface in a narrow channel; without lowering, the nearest “drainage” would be higher than the
floodplain and HAND would be systematically negative. A 3 m burn is a declared modelling device,
not a surveyed channel depth. The river-only policy makes HAND coarser between major channels;
that is a stated limitation, not a reason to keep streams in the model.

### 7.4 Step C — nearest-drainage assignment

The question is: for every land cell, which channel cell is nearest, and how far is it?

1. Build the boolean mask `channel_mask` over the full AOI. Channels may lie in the AOI v2 + 5 km
   clip so valley-edge cells are not artificially cut off; flood counts remain restricted to the
   AOI v2 core.
2. Compute the exact Euclidean distance transform with nearest indices:

   ```text
   distance_m, (iy, ix) = scipy.ndimage.distance_transform_edt(
       ~channel_mask,
       sampling=(90.0, 90.0),
       return_indices=True
   )
   ```

   `(iy, ix)` is the nearest channel cell for every cell; ties are resolved deterministically by
   SciPy’s implementation (row-major scan order). This is O(N) and does not require flow routing.
3. `nearest_channel_z = dem_burned[iy, ix]` (the burned elevation at the channel).
4. `distance_m` is the Euclidean grid distance, not a flow-path length. It is used for hotspots
   and the reachability limit, not as a hydrological travel distance.

### 7.5 Step D — HAND

```text
raw_hand = dem_burned - nearest_channel_z
hand = max(0, raw_hand)
```

- Negative `raw_hand` means the cell is below its nearest channel (depression, levee backslope,
  or burn artefact). Clamp to 0 and count it; if clamped cells exceed 2% of valid cells, emit a
  warning in `hand-meta.json` and validation.
- If `distance_m > 12000`, set `hand = -9999` (nodata). There is no “reachable channel” within the
  model’s search limit; do not invent one from a neighbouring basin.
- If `nearest_channel_z` is nodata, set HAND nodata and count it.
- Do not smooth HAND. Smoothing would create plausible-looking detail that the 90 m DEM does not
  support.

`HAND` means “height above the nearest mapped drainage”, not “height above the nearest flowing
water at this moment”. On hills far from mapped streams it can be large; that is correct for this
model.

### 7.6 Step E — scenario water level and mask

<!-- amended: REVIEW-02 -->

For each step `s` with stage `stage_s` (metres above local drainage):

```text
wet_raw = valid_hand AND inside_AOI_v2 AND (hand <= stage_s)
depth_raw = stage_s - max(hand, 0)
```

<!-- amended: REVIEW-03 B2 -->

`depth = stage − max(HAND, 0)` is the bathtub convention, so `depth ≤ stage` for every wet cell.
A cell below the burnt channel datum reports the full stage (HAND 0). This is deliberately
**conservative-shallow**: without levee or bathymetry data the model cannot assign a deeper
surface to that cell. State the bias in the methodology note and the run report; do not present
the clamped depth as a measured water depth.

`inside_AOI_v2` is the core mask (inside Assam, DEM ≤120 m), not the 2 km edge buffer and not the
full Assam polygon. The 2 km buffer is used only so edge channels/terrain remain continuous.

- The stage is applied uniformly to every channel cell. This is the key simplification: a real
  river has a water-surface slope and tributary backwater is unsteady. The model represents
  backwater only through the terrain relationship—low-HAND cells far from the main stem fill
  when the stage exceeds their local drainage height. The UI must not claim a routed backwater
  simulation.
- No levees, embankments, roads, or flood defences are subtracted. There is no verified levee
  dataset in the probed sources, and inventing one would create false protection.
- No infiltration, evaporation, pumping, or antecedent moisture. The mask is a static threshold
  per step.

### 7.7 Step F — connectivity

A raw threshold produces isolated wet specks in depressions that have no hydraulic path to a
channel. Remove them:

1. Label `wet_raw` with 8-connectivity (`scipy.ndimage.label`).
2. A component is retained if it contains at least one channel cell, or a cell whose
   `distance_m <= 90` (one cell from a channel).
3. `wet_connected = retained components`; the V-A9 ≥9-cell filter below is the only
   component-size floor (there is no separate 3-cell floor).
4. `depth = depth_raw` where the final wet mask is true, else 0.

This is a topological connectivity check, not a flow simulation. It can still retain a cell that
would be separated by a levee; that is covered by the no-levee limitation. It can drop a genuine
backwater pocket that is disconnected at 90 m; the count of dropped components is recorded and
reported, and the limitation is stated.

**V-A9 component-area filter (REVIEW-04 C2)** runs immediately after connectivity and before
statistics, rendering and mask output:

1. Label the connectivity-filtered wet mask with 8-connectivity.
2. Drop every connected component smaller than **9 cells** (≈0.073 km² at 90 m).
3. Record, per step, `raw_components` (threshold-mask components), `connectivity_components`,
   `components_before`/`components_after` around the area filter, `dropped_components` and
   `dropped_area_km2`. `opening` is recorded as `none`.
4. Only the resulting mask is counted for area, used for depth statistics, written as the wet
   mask and rendered into the PNG. **Morphological opening is forbidden**; there is no binary
   opening anywhere in stage 09.

The filter removes DEM/edge specks, not real islands. No band reduction, coarse simplification
or quiet polygon drop is used to meet the frame cap.

### 7.8 Step G — depth classes and raster frames

<!-- amended: REVIEW-04 -->

For each step:

1. Convert `depth` to a uint8 class raster: 0 = dry/transparent, 1 = `0.0–0.5 m`,
   2 = `0.5–1.5 m`, 3 = `1.5–3.0 m`, 4 = `3.0+ m`.
2. Downsample by 2 in each axis (half the analysis resolution, ≈180 m/px). The committed frame
   is exactly `width // 2` × `height // 2` pixels; the last odd row/column is dropped and the
   frame-index `bbox` is the cropped footprint. No polygonisation, no simplification and no
   ring-area floor are applied.
3. Write the class raster as an optimised paletted PNG (`P` mode, 5-entry palette, index 0
   transparent via `tRNS`). The palette is the same list published in `frame-index.json`.
4. Write the step's `frame-index` entry with `id`, `label`, `stage_m`, relative `file`,
   `area_km2` and the measured PNG bytes/wet cells. Measure each PNG raw; refuse a frame above
   400 KB. Write `frame-index.json` once after all steps.
5. V-A10 then checks, from the committed artifacts, that the index bbox and half-resolution
   reproduce every PNG extent within 1 pixel and that each step's `area_km2` matches the PNG
   wet cells × cell area within 1 %. The `public/data/` total is capped at 9.0 MB (V09).
6. No per-band GeoJSON, no per-step vector outline, no two-class fallback and no `setData`
   GeoJSON source are produced in M0.

### 7.9 Step H — no reachable channel, edge cases

| Case | Handling | Visible consequence |
|---|---|---|
| No channel within 12 km | HAND nodata; never wet; counted in `hand-meta.json` | Cell absent from flood/risk; `valid_area_share` caveat |
| No channel at all in AOI | Pipeline fails V04/V17; no output | No fake flood |
| Cell below nearest channel | HAND clamped to 0; counted; warning above 2%, hard gate 6% (V-A6) | Cell floods at the first stage ≥0 |
| Channel elevation above cell but distance valid | Same clamp; local depression | Stated limitation |
| Isolated wet component | Dropped by connectivity or the ≥9-cell area filter; count and dropped area reported | Avoids speckle |
| Cell outside AOI v2 | Computed for continuity but excluded from output and metrics | No hill-district flood area; stated caveat |
| Stage above maximum HAND | Depth clipped at stage; no extrapolation | Max depth reported honestly |
| Recession step leaves a disconnected puddle | Connectivity applies per step; puddle may drop | Area can fall faster than a hydrodynamic model |

No cell is ever assigned a HAND from a different basin by hand. If the nearest channel is across
a ridge, the Euclidean method will still use it; that is a known limitation of non-routed HAND
and is stated in-app. A flow-accumulation/routing refinement is P2.

---

## 8. Scenario table and synthetic anchoring

<!-- amended: REVIEW-02 -->

### 8.1 The 12 steps

`N = 12`; peak at S07; total 136 days. Dates are **composite labels without a year** to avoid
implying a specific observed event. Stages are the phase-A curve rescaled by ×1.48 (REVIEW-03 B1);
the peak is 3.70 m, selected by the phase-A3 measured calibration inside V-A4/V-A5. The
main-stem and backwater columns are scaled with the same factor and the backwater value absorbs
the 2-decimal reconciliation so `stage_m = mainstem_stage_m + backwater_m` still holds exactly.
All three columns remain **synthetic scenario parameters**.

| Step | Label | Day | Phase | Rainfall (mm/day, synthetic) | Main-stem anomaly (m, synthetic) | Backwater allowance (m, synthetic) | Stage above drainage (m, scenario) | Above 2.0 m |
|---:|---|---:|---|---:|---:|---:|---:|---|
| S00 | 01 Jun | 0 | onset | 6 | 0.19 | 0.11 | 0.30 | no |
| S01 | 15 Jun | 14 | rising | 12 | 0.44 | 0.16 | 0.60 | no |
| S02 | 01 Jul | 30 | rising | 17 | 0.75 | 0.30 | 1.05 | no |
| S03 | 15 Jul | 44 | rising | 21 | 1.12 | 0.43 | 1.55 | no |
| S04 | 25 Jul | 54 | rising | 24 | 1.49 | 0.66 | 2.15 | yes |
| S05 | 05 Aug | 65 | rising | 20 | 1.80 | 0.85 | 2.65 | yes |
| S06 | 15 Aug | 75 | rising | 14 | 1.99 | 1.26 | 3.25 | yes |
| S07 | 25 Aug | 85 | peak | 10 | 2.11 | 1.59 | **3.70** | yes |
| S08 | 05 Sep | 96 | receding | 7 | 1.99 | 1.26 | 3.25 | yes |
| S09 | 15 Sep | 106 | receding | 5 | 1.68 | 0.82 | 2.50 | yes |
| S10 | 30 Sep | 121 | receding | 3 | 1.18 | 0.62 | 1.80 | no |
| S11 | 15 Oct | 136 | receding | 2 | 0.62 | 0.43 | 1.05 | no |

### 8.2 What is anchored, what is invented

**Anchored (qualitative, documented climatology only):**
- The Assam monsoon is seasonal: onset around June, peak rainfall in July–August, recession
  through September–October.
- The Brahmaputra main stem peaks **after** catchment rainfall, so the stage curve lags the
  rainfall curve.
- Low-lying floodplain and tributary-mouth areas are the first to inundate and the last to drain.

These are stated as the shape of the curve, not as measured values. No numeric rainfall,
discharge, gauge level, return period, or event statistic is quoted from a source.

**Synthetic (declared, not observed):**
- Every rainfall value in the table.
- Every main-stem anomaly value.
- Every backwater-allowance value.
- Every stage-above-drainage value and the 2.0 m scenario threshold.
- The step dates (composite month/day labels, no year).

**Derived (computed, not observed):**
- Inundation extent, depth bands, areas, risk zones, district scores, hotspots.

**Real (source data):**
- Terrain, district boundaries, state outline, rivers, and (P1) facility locations.

The scenario is deliberately not calibrated to a gauge. A reviewer must be able to see that the
hydrograph is a shape, not a claim. The in-app copy says: “Synthetic monsoon scenario; not a
forecast, not a gauge record, not an evacuation instruction.”

### 8.3 Why these values

The stage rises from 0.30 m to **3.70 m**, the phase-A curve rescaled by ×1.48 (REVIEW-03 B1).
The number is a **model parameter, not a measured flood level**: it is the peak stage selected by
the phase-A3 measured calibration on the A2 channel set, inside the V-A4 extent band. The rainfall
peak at S04 and stage peak at S07 preserve the visible lag. The recession is slower than the rise
(51 days from peak to S11 vs 85 days from S00 to peak), matching the qualitative behaviour of a
large valley draining after the monsoon.

The stage is the exact sum of the two synthetic columns:
`stage_m = mainstem_stage_m + backwater_m`. The split is a narrative device for the causal chain
(a main-stem rise plus a tributary/backwater allowance), not a solved backwater term. The model
applies the summed stage uniformly to every mapped channel. A reviewer must not read the split as
two independent physical estimates.

The 3.70 m peak is the **measured calibration choice**, not an observation. The V-A4 band
(4,000–12,000 km²) and the ≤40 %-of-flood-prone ceiling were chosen by the REVIEW-02 reviewer; the
V-A5 depth band and clamped-share gates were revised by REVIEW-03 B3. They are recorded in
`provenance.json` and the run report as plausibility and calibration choices.

If the builder changes any value, they must update the scenario table, the config, the summary,
the series, and the validation expectations together. No component may hard-code 3.70 or step 7;
they come from `scenario.json`/`flood-summary.json`, and V-A3 compares the peak against
`pipeline/inundation/calibrated_peak_stage_m`.

### 8.4 Duration weights

Step labels are not uniformly spaced. For per-cell duration:

```text
w_k = (day[k+1] - day[k-1]) / 2      for interior k
w_0 = (day[1] - day[0]) / 2
w_11 = (day[11] - day[10]) / 2
duration_days = sum(w_k for k where depth[k] > 0.1 m)
```

The weights sum to 136 days. This avoids over-counting the 10-day steps relative to the 16-day
steps. `mean_duration_days` is area-weighted over cells that are wet in at least one step.

---

## 9. Risk scoring

Two related but distinct metrics are published. They answer different questions and must not be
conflated in the UI.

### 9.1 Per-cell hazard → risk zones

<!-- amended: PHASE-0 -->

Only cells wet in at least one step are classified. For a cell:

```text
H = min(HAND_m, 6.0) / 6.0
D = min(duration_days, 136) / 136
cell_risk = 100 × (0.60 × (1 - H) + 0.40 × D)
```

- `HAND_m` is from the 90 m raster; `duration_days` uses §8.4.
- A cell at HAND 0 that is wet for the full scenario scores 100.
- A cell at HAND 6 m wet for one 10-day step scores ≈ 2.9.
- The score is clipped to `[0, 100]`.

Class thresholds:

| Class | Score |
|---|---|
| `very_high` | ≥ 70 |
| `high` | 55 – <70 |
| `moderate` | 40 – <55 |
| `low` | < 40 |

<!-- amended: PHASE-0 -->

The same per-cell classes are summarised in `district-risk.json` as
`risk_class_area_share`. Its denominator is the **area of all analysis cells wet at the peak step
(S07) with valid HAND**, not the district polygon area and not the union of every step. The four
shares (`low`, `moderate`, `high`, `very_high`) cover that denominator and sum to 1.0. This
publishes the denominator the panel review found missing; it is not a district score.

Polygonise the classified raster, simplify at 100 m, drop polygons < 0.05 km². A polygon’s
`risk_score` is the area-weighted mean cell score; its class is the class of that mean, and
because polygonisation is per class the mean stays inside the class band. If a merged polygon
would cross a class boundary, keep the classes separate (do not merge across classes).
The 0.9 MB raw cap is binding: stage 10 vectorises a block-majority grid
(`risk.zone.vector_block_factors`, `risk.zone.vector_min_wet_fraction`) to reduce the boundary
coordinate count while keeping the 90 m cell statistics; the chosen grid and the resulting zone
coverage are reported in `docs/PIPELINE-REPORT.md`.

### 9.2 District aggregation → ranking

<!-- amended: PHASE-0 -->

For district `d`:

```text
area_share = min(peak_flooded_area_km2 / district_area_km2, 1.0)
A = min(area_share / 0.60, 1)
D = min(mean_duration_days / 90, 1)

risk_score = 100 × (0.5625×A + 0.4375×D)
```

- `peak_flooded_area_km2` is the maximum wet area within the district over the 12 steps.
- `district_area_km2` is the geodesic source-polygon area, not the raster cell count.
- `mean_duration_days` is area-weighted over cells ever wet; dry cells are excluded from the
  mean (otherwise large dry districts would look safer than they are).
- `p90_peak_depth_m` is the area-weighted 90th percentile of depth at the peak step (S07). It is
  **reported but not scored**: in the bathtub convention the peak depth is capped by the 3.7 m
  scenario stage, so every district records the same value. The two scored weights are the
  previous 45% and 35% weights re-normalised over their 80% live total (`0.45 / 0.80 = 0.5625`,
  `0.35 / 0.80 = 0.4375`); `weights_version` is `area-duration-v1`.
- `depth_over_1_5m_share` is the count share of the district’s cells wet at peak with depth
  strictly greater than 1.5 m; `median_depth_m` is the plain median depth over those wet cells.
  Both are reported context, not score inputs.
- `valid_area_share` is the share of the district’s raster cells with valid HAND; it is a
  coverage caveat, **not** part of the score. The Risk panel shows a `coverage …%` badge and the
  row annotation `Scored on the AOI-covered share only` when it is below 0.75.

Why different weights from §9.1: the cell score is a terrain-hazard index (HAND dominates); the
district score is an aggregate exposure index where the share of district area actually wet is
the most legible driver. Both are documented, neither uses population.

Class thresholds:

| Class | Score |
|---|---|
| `very_high` | ≥ 60 |
| `high` | 45 – <60 |
| `moderate` | 30 – <45 |
| `low` | < 30 |

Ranking: sort by `risk_score` descending, then `name` ascending for ties. `rank` is dense
(1..N); districts with no valid cells or zero peak area get `risk_score: null`, `rank: null`,
`risk_class: null`, and are omitted from the ranked positions. They are counted in
`counts.no_data` so the total is still auditable. `drivers` is the two largest of `0.5625A`,
`0.4375D`; ties break in the order area, duration. Removing the constant depth term shifts every
score but cannot reorder the ranking; the Phase 0 regeneration preserved the order and the class
thresholds above.

No demographics, population, buildings, roads, crop value, or casualty data enters the formula.
The output is explicitly “scenario-conditional terrain risk”, not expected loss.

### 9.3 Hotspots (P1)

A hotspot is a **derived low-HAND backwater pocket**, not a breach:

1. Take the peak-step wet mask.
2. Keep cells with `HAND ≤ 2.0 m` and `distance_to_channel ≥ 1500 m`.
3. Label 8-connected components; keep components ≥2.0 km².
4. Keep components first wet at step ≤6 (they fill before the peak, i.e. they are backwater
   pockets rather than the last fringe).
5. One point per component at the point of maximum distance-to-channel; compute mean HAND,
   minimum distance, peak depth, first step, district.
6. Rank by area descending, maximum 20.

The `reason` value is always `low_hand_backwater_pocket`. The UI calls them “inundation
hotspots”; it must not call them embankment breaches. There is no embankment dataset.

### 9.4 Facility exposure bands (P1)

For each OSM facility point, sample `depth[step]` at its cell:

| Band | Peak depth |
|---|---|
| `none` | < 0.1 m or never wet |
| `minor` | 0.1 – <1.0 m |
| `moderate` | 1.0 – <3.0 m |
| `major` | ≥ 3.0 m |

This is a **scenario depth exposure**, not damage, loss, or operational status.

### 9.5 Severity index beside extent (P1.7)

<!-- amended: REVIEW-17 -->

`risk_score` is an **extent-led** score: area share dominates and duration is the second
driver. It answers "how much of the district is wet", not "how bad is the water where it is
wet". P1.7 publishes a second, explicitly separate profile for the latter.

For district `d`, with `x1 = depth_over_1_5m_share`, `x2 = median_depth_m`,
`x3 = mean_duration_days`:

```text
μk = mean(xk) over the scoreable districts
σk = population standard deviation of xk (ddof = 0)
zk = (xk − μk) / σk        (zk = 0 if σk = 0)
p  = z1 × z2 × z3
severity_index = 100 × (p − min(p)) / (max(p) − min(p))
```

- The mean and population standard deviation are computed over the districts that have all
  three inputs. Every constant (`μk`, `σk`, `min(p)`, `max(p)`, the number of districts) is
  published in the top-level `severity` object of `district-risk.json`; nothing is hidden.
- The min–max mapping is applied to the **product** `p`, not to each z-score separately. A
  district exactly at the population mean on any input has `p = 0`; the index is therefore not
  a claim that all three inputs are independently "good".
- `severity_rank` is dense (1..N) descending by `severity_index`, ties broken by district name
  ascending. `rank` remains the dense extent-score rank. Both are shown, never combined.
- Class labels (`risk_class`) are still the extent-score classes. The severity profile has no
  class; it has an index and a rank.
- Measured example: Dima Hasao has `depth_over_1_5m_share 0.882086`, `median_depth_m 3.7`,
  `mean_duration_days 114.6664`, `area_share 0.003634`; it ranks **1/33 on severity** but
  **12/33 on the extent score** (and 33/33 on area share). The acceptance sentence in
  REVIEW-17 says "bottom half on extent"; the committed extent score puts it just above the
  median because duration is 43.75 % of that score. This is reported as a finding, not tuned
  away: the severity formula is exactly the one above, and the extent score was not changed.
- No demographic, population, asset-loss, agency or incident field enters either profile.

---

## 10. Validation — checks that must pass before data ships

<!-- amended: REVIEW-02 -->

`validate` runs every check, records expected/actual, and exits non-zero on `fail`. `publish`
refuses if `status != "pass"`. The report lists every gate by ID in
`REQUIRED_GATE_IDS`; a missing ID is itself a failure.

| ID | Check | Pass condition | Fail / warn |
|---|---|---|---|
| V01 | Schema validity | Every committed JSON/GeoJSON parses and matches its §6 schema | fail |
| V02 | Geometry validity | No `null`/empty geometry; `shapely.is_valid` true after `make_valid`; no self-intersection | fail |
| V03 | Bounds | Every coordinate inside AOI + 0.01°; no swapped lon/lat | fail |
| V04 | Assam containment | Districts/state intersect Assam; risk/hotspot centroids inside the buffered state | fail |
| V05 | Rising-limb monotonicity | `area[S00..S07]` non-decreasing, tolerance 0.5% | fail |
| V06 | Recession | `area[S08..S11]` non-increasing; peak step = 7 | fail |
| V07 | Finite numbers | No `NaN`, `Infinity`, `-Infinity` anywhere; JSON `allow_nan=False` | fail |
| V08 | Classes and labels | Every feature `class` in the five-value enum; badges/labels present; no layer missing a class | fail |
| V09 | File caps | Every frame PNG ≤400 KB raw; JSON gzip caps respected; `public/data/` total ≤9.0 MB | fail |
| V10 | Manifest integrity | Every file except `manifest.json` is listed once; SHA-256 and byte size match; no orphan data file | fail |
| V11 | Series and stage consistency | `monsoon-series` points equal `flood-summary` at every step (1e−6); threshold = 2.0; `stage_m = mainstem_stage_m + backwater_m` at every step | fail |
| V12 | District join | Every ranking district exists in districts GeoJSON exactly once; `rank` and `severity_rank` dense; score 0–100; joined risk and severity fields match | fail |
| V13 | Forbidden fields/claims | No `casualties`, `deaths`, `displaced`, `affected_persons`, `incident_id`, `agency_id`, `relief_camp`, `eta`, `warning_issued`; no positive `operational forecast`/`official forecast`/`flood forecast`. A bare `forecast` passes only inside the required negation `not a forecast` / `never a forecast` or the boolean key `not_a_forecast`. | fail |
| V14 | Step count | Exactly 12 steps; labels/days/phases match `scenario.json`; every step has one frame PNG and one `frame-index` entry | fail |
| V15 | Coordinate hygiene | 5 decimals; no consecutive duplicates; RFC 7946 winding (vector layers) | fail |
| V16 | Risk range | All scores 0–100; zone classes match thresholds; ranking classes match thresholds | fail |
| V17 | Channel coverage | ≥85% of AOI v2 core cells valid HAND; no-channel cells reported; clamped negatives ≤6.0% | warn if 80–85% valid or clamped 2–6%; fail <80% valid or >6% |
| V18 | Fallback asset | `assam-hillshade.webp` exists, ≤1.5 MB, decodes, width 2000 | fail |
| V19 | First-paint budget | Critical-tier bytes ≤3.5 MB raw; animation tier (12 PNGs + frame-index + summary + risk-zones) ≤4.0 MB raw; optional/fallback ≤3.0 MB | fail |
| V20 | Provenance completeness | Every committed dataset has a provenance entry with source/licence/stage/output; UNOSAT absence noted; flood-prone and Sentinel-1 validation sources recorded | fail |
| V-A1 | AOI v2 area | AOI v2 core area between 45,000 and 56,000 km²; mask area agrees with metadata | fail |
| V-A2 | Channel policy | Channel cells ≤4.0% of AOI v2; zero model ways with midpoint outside AOI v2 + 5 km; every model way is `waterway=river` | fail |
| V-A3 | Stage series v3 | Strictly increases S00→S07, strictly decreases S08→S11, peak = 3.70 m at S07, threshold 2.0 m | fail |
| V-A4 | Peak extent plausibility | Peak extent between 4,000 and 12,000 km² and ≤40% of the 31,050 km² flood-prone area (reviewer-selected band, not a calibrated observation) | fail |
| V-A5 | Peak depth | REVIEW-05 D1 v4: peak-step median ≥0.7 m and ≤ peak stage − 0.5 m; p95 ≤ peak stage; p95 − median ≥0.6 m; clamped share of wet area ≤30% (`depth = stage − max(HAND, 0)`), computed on the area-filtered mask; every step carries `wet_cells` and six ordered `delay_deciles` whose p50/p95 equal the step median/p95 (D2) | fail |
| V-A6 | Clamped HAND | Clamped negative HAND cells inside AOI v2 ≤6.0% | fail |
| V-A7 | Hydrograph shape | Every rising-limb step non-decreasing; recession non-increasing; peak at S07 | fail |
| V-A8 | Stage 09 performance | Stage 09 wall time ≤10 min; no `inundation-stack.npz` above 300 MB; every stage-09 artifact ≤300 MB | fail |
| V-A9 | Component-area filter | ≥9-cell component-area filter applied before statistics, masks and rendering; **no morphological opening**; raw/connectivity/before/after counts and dropped area recorded for every step and reproduced from the wet masks | fail |
| V-A10 | Frame-index/PNG agreement | `frame-index.json` bbox and half-resolution reproduce every PNG extent within 1 pixel; each step's `area_km2` matches the PNG wet cells × cell area within 1% | fail |

Additional assertions inside stages:

- `build-dem`: elevation range sanity (−50 to 8,000 m); no ocean zeros inside Assam.
- `build-admin`: centroid inside polygon; state area within 1% of the district sum.
- `build-rivers`: at least one main-stem line; channel length >500 km; channel cells ≤4.0% of
  AOI v2; no model way with midpoint outside AOI v2 + 5 km.
- `build-inundation`: rising-limb and recession areas exact non-decreasing/non-increasing; peak
  at S07; peak extent inside V-A4; peak depth inside V-A5; per-step masks and PNGs written; no
  float stack, no `inundation-stack.npz` and no per-band GeoJSON.
- `build-risk`: districts with zero valid cells do not receive a score; hotspot count ≤20;
  published district weights sum to 1.0 and are the values applied to every score;
  `depth_over_1_5m_share` has more than one distinct value; `risk_class_area_share` sums to 1.0.
- `publish`: refuses on a dirty/partial data directory or missing report.

<!-- amended: PHASE-0 -->

`node scripts/check-data.mjs` repeats the three Phase 0 assertions against the committed file:
the published `weights` sum to 1.0 and reproduce every `risk_score`; the 33
`depth_over_1_5m_share` values are not constant; and the four `risk_class_area_share` values sum
to 1.0 ± 0.01.

<!-- amended: REVIEW-17 -->

`check-data` also gates the two Phase 1a artifacts:

- `validation/scorecard.json` exists and matches the schema; `collection` is
  `sentinel-1-grd`, `threshold_method` is `fixed_sigma0`, `threshold_db` is −16,
  `sensitivity_db` is `[-14,-16,-18]`, `slope_mask_deg` is 10, `min_component_cells` is 5,
  resampling is `average→nearest`, CRS is `EPSG:32646`, resolution is 90 m; exactly two scenes
  are present.
- `method.calibration` is present with a finite, non-null `A_median`, 27 vectors and 642
  samples per vector; the source names `schema-calibration-vv`.
- `method.slope_filter` publishes the gradient operator, `unit = "degrees"`, threshold 10,
  `applied_to_validity = false`, and both with/without slope areas. `method.mask_provenance`
  lists the allowed inputs, prohibits `flood_frames`, `hand_wet_mask` and
  `district_risk_artifacts`, and asserts `model_conditioned = false`.
- each scene publishes `scene_area_km2`, `validity_area_km2`,
  `validity_fraction_of_scene` (checked against the ratio), `with_slope_validity_area_km2`,
  `without_slope_validity_area_km2`, and a `validity_attrition` ledger whose `final.area_km2`
  equals `validity_area_km2`. `validity_area_km2 >= 20000` is required unless the attrition
  ledger documents a filter that removed the rest.
- each scene has exactly three sensitivity rows with σ0 thresholds `[-14,-16,-18]`, observed
  area and all metrics; `validity_area_km2` and `modelled_in_validity_km2` are finite;
  every `iou`/`precision`/`recall`/`f1` is in `[0,1]`; `observed_area_km2 > 0`;
  per threshold `TP + FP = modelled_in_validity_km2` and `TP + FN = observed_area_km2` within
  0.5 km²; precision and recall are consistent with those areas; `peak_step.step` equals the
  scenario peak; `worst_scene` names a listed scene; the caveats are non-empty, contain "not an
  event hindcast", and **no caveat contains "calibration was unavailable"**.
- every district has a finite `severity_index` in `[0,100]` and a positive `severity_rank`, as
  well as the existing extent `rank`; severity has more than five distinct values; both ranks
  are dense; the published z-score means/stds, product min/max and the min–max formula
  reproduce every `severity_index`.
- the Dima Hasao measured profile is asserted (0.882086, 3.7 m, 114.6664 d) and its severity
  rank is required to be in the top third. The extent rank is printed, not asserted: the
  committed extent score ranks it 12/33, so the "bottom half on extent" wording in REVIEW-17 is
  not met by the extent score, while its area-share rank is 33/33. This is a reported finding.

`validation-report.json` itself is validated (status, checks array, counts) and is committed so
the provenance panel can show the last run. Warnings are displayed in the panel; they are not
silent.

CI (`.github/workflows/pages.yml` may run the data checks without re-running the full pipeline):

```powershell
python -m baanh_pipeline.cli validate --data public/data --config pipeline/config --report public/data/validation-report.json --version 2026.10.0
node scripts/check-data.mjs
node scripts/check-budget.mjs
npm run verify:m0
```

The pipeline itself is not run in CI: it needs tile/Overpass network access and several GB of
temporary disk. The committed outputs and their hashes are the artifact; a data change must be
produced locally and committed with a fresh manifest.

---

## 11. Size caps, runtime, and reproducibility

<!-- amended: REVIEW-02 -->

### 11.1 Caps

<!-- amended: REVIEW-04 -->

| File | Cap |
|---|---|
| `flood/frames/step-XX.png` (each) | 400 KB raw |
| `flood/frame-index.json` | 64 KB raw / 32 KB gzip |
| `flood/flood-summary.json` | 64 KB gzip |
| `admin/assam-districts.geojson` | 1.2 MB |
| `admin/assam-state.geojson` | 0.15 MB |
| `hydro/assam-rivers.geojson` | 1.0 MB |
| `risk/risk-zones.geojson` | 0.9 MB raw / 256 KB gzip |
| `risk/district-risk.json` | 0.15 MB |
| `risk/hotspots.geojson` | 0.10 MB |
| `series/monsoon-series.json` | 0.05 MB |
| `series/cross-sections.json` | 0.20 MB |
| `basemap/assam-hillshade.webp` | 1.5 MB |
| `assets/critical-facilities.geojson` | 1.0 MB |
| `gauges/virtual-gauges.geojson` | 0.10 MB |
| `validation/scorecard.json` | 128 KB raw / 16 KB gzip |
| manifest + provenance + scenario + validation | 0.25 MB combined |
| **Total committed data** | **9 MB** |

Tiers: critical (manifest, scenario, provenance, districts, state, rivers, district-risk,
monsoon-series, validation, scorecard) ≤3.5 MB raw; animation (12 PNGs, frame-index, summary,
risk zones) ≤4.0 MB raw, with JSON gated on gzip and PNG gated raw; optional/fallback (hillshade,
cross-sections, hotspots, assets, gauges) ≤3.0 MB raw.

<!-- amended: REVIEW-04 -->

PNG frames are already compressed; the 400 KB per-frame cap is raw. JSON payloads
(`frame-index.json`, `flood-summary.json`, `risk-zones.geojson`) are also gated on gzip. There is
no two-class fallback: at half resolution every measured frame is far below 400 KB. Do not reduce
the depth-class count silently, coarsen further, or drop genuine flood components merely to make
the byte count look good. Do not hand-edit the committed JSON. The stage-09 per-step uint8 mask
cache is capped at 300 MB; the old float `.npz` stack and the vector frame files are not part of
the accepted path.

### 11.2 Expected runtime

| Stage | Wall time (reference laptop) | Peak RSS |
|---|---|---|
| fetch terrain (z11, ~900 tiles) | 2–6 min | <500 MB |
| fetch boundaries/rivers | 1–3 min (Overpass can be 30 s+) | <300 MB |
| DEM/hillshade | 1–2 min | 1.5 GB |
| HAND | 2–4 min | 3 GB |
| Inundation (12 steps) | ≤10 min (V-A8) | 3 GB |
| Risk/series | 2–4 min | 2 GB |
| Validate/publish | <1 min | <300 MB |

Disk for cache + work: ≤1.5 GB. The pipeline is single-machine and not parallelised beyond tile
fetching; clarity over speed.

### 11.3 Determinism

- Given the same cached inputs, the numeric outputs are deterministic: SciPy EDT and
  `ndimage.label` are deterministic, Paletted PNG encoding is deterministic for a fixed Pillow
  build, and frames are written in step order. <!-- amended: REVIEW-04 -->
- `generated_at` timestamps and `fetched_at` differ between runs; they are excluded from
  geometric comparisons. Validate compares numbers, not timestamps.
- Raw source SHA-256 hashes are recorded in provenance. Re-running with a changed source will
  change the outputs and the manifest; that is expected and must be reviewed.
- `publish` writes files in a fixed order and uses `sort_keys` where the schema does not require
  order, so diffs are reviewable.

### 11.4 Licensing and attribution checklist

- Map shows “Elevation: AWS Terrarium / Mapzen”, “Imagery © Esri, Maxar, Earthstar Geographics”,
  “Boundaries: geoBoundaries (CC BY 4.0)”, “Rivers: © OpenStreetMap contributors (ODbL)” or
  “Natural Earth” when the fallback is used.
- `provenance.json` records the exact licence string and URL for each source.
- Esri World Imagery is a basemap, not an event observation. The UI says so in the imagery panel.
- No source is described as an official Assam government or CWC feed. No agency logo is used.

---

## 12. Limitations (must be repeated in-app)

<!-- amended: REVIEW-02 -->

1. **Not a forecast.** The scenario is synthetic; the model is a terrain screening tool.
2. **No hydrodynamic routing.** Uniform stage over mapped channels; no unsteady flow, no
   backwater solver, no sediment.
3. **No defences.** Levees, embankments, roads, and flood walls are absent; the model may
   overstate inundation behind protection.
4. **Incomplete channels.** HAND uses `waterway=river` only; streams and drains are deliberately
   excluded, so HAND is coarser between major rivers and the flood band can be narrower than a
   full-channel model would suggest. This is a stated policy, not a hidden smoothing.
5. **90 m grid.** Smaller channels, culverts, and local depressions are not resolved.
6. **Euclidean nearest drainage.** A channel across a ridge can be selected; no flow-path
   distance. Negative HAND (cell below its nearest channel) is clamped and counted; V-A6 caps it
   at 6.0% of AOI v2, and V-A5 caps the peak-step clamped share of wet area at 30%.
7. **No calibration.** Stage values are not fitted to a gauge or a satellite extent. The
   4,000–12,000 km² peak band and 31,050 km² flood-prone denominator are plausibility references,
   not observations of this scenario.
8. **Valley-floor AOI.** AOI v2 excludes hill districts above 120 m; flood metrics do not cover
   them. If a genuinely flood-prone district is excluded, that is a coverage caveat, not a reason
   to raise the threshold.
9. **Scenario-conditional risk.** Risk zones and district scores describe this scenario, not
   all-time flood risk or expected loss.
10. **No demographics or assets in the score.** P1 facility exposure is a depth join, not damage.
11. **OSM completeness.** Facility and river completeness is uneven; the UI says so.

If a reviewer asks for an operational forecast, the answer is that this product is not one and
the data to make one is not among the probed sources. Do not add a plausible-looking feed.
