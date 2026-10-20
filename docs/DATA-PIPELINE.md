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
├─ flood/flood-frames.geojson
├─ flood/flood-summary.json
├─ risk/risk-zones.geojson
├─ risk/district-risk.json
├─ risk/hotspots.geojson                  (P1)
├─ series/monsoon-series.json
├─ series/cross-sections.json             (P1)
├─ basemap/assam-hillshade.webp
├─ assets/critical-facilities.geojson     (P1)
└─ gauges/virtual-gauges.geojson          (P1)
```

- Coordinates in every GeoJSON are **WGS84 / EPSG:4326**, longitude then latitude, 5 decimal
  places (~1 m), RFC 7946 winding.
- All analysis happens in **EPSG:32646** at **90 m** (§3).
- Area values are geodesic (WGS84 ellipsoid), in km², never planar degrees².
- Every feature has `"class"` ∈ `source | reference | derived | scenario | synthetic`.
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

Natural Earth is the documented fallback for the **rivers** source, not an additional layer or a
sixth dataset. The five probed layers remain terrain, satellite basemap, districts, rivers, and
event context; the first four are used, and UNOSAT is explicitly not used in the first build.

**Source discipline.** Only the five probed sources above, or committed pipeline output, feed the
app. No rainfall API, discharge API, gauge API, population layer, building footprint, or
administrative unit beyond geoBoundaries ADM2 is added. If a source is unavailable, the pipeline
uses the documented fallback or fails; it does not substitute a plausible-looking dataset.

**What is real vs synthetic.**

| Element | Class | Basis |
|---|---|---|
| Terrain/elevation | `source` | AWS Terrarium DEM, z11 |
| District boundaries and state outline | `source` | geoBoundaries ADM2, dissolved for state |
| Rivers | `source` | OSM Overpass, Natural Earth fallback |
| Hospitals/clinics/schools (P1) | `source` | OSM Overpass, completeness unverified |
| Rainfall series | `synthetic` | Parameterised monsoon curve; no gauge record |
| Main-stem stage anomaly | `synthetic` | Parameterised; relative to a pre-monsoon baseline, not a gauge datum |
| Stage above local drainage | `scenario` | Model driver for HAND thresholds |
| Inundation extent/depth | `scenario` | Derived from DEM + channels + synthetic stage |
| Risk zones, district ranking, hotspots | `derived` | Formulas in §9, no demographics |
| Virtual gauges (P1) | `synthetic` | Stations placed on mapped rivers; no agency, code, or datum |

No real 2022 (or other year) casualty, displacement, or incident figure is used. If one is ever
quoted, it must be cited in this file and labelled `reference` in the UI.

---

## 3. AOI, CRS, and resolution

### 3.1 Definition

| Parameter | Value | Notes |
|---|---|---|
| AOI bbox (WGS84) | `[89.55, 23.95, 96.15, 28.15]` | Assam plus a ~15–20 km regional buffer; includes edge terrain in Bhutan/Meghalaya/Arunachal/Bangladesh for continuity |
| Analysis CRS | `EPSG:32646` (WGS 84 / UTM zone 46N) | Metres; correct for distance transforms and raster algebra |
| Analysis resolution | `90 m × 90 m` | 1.3× the ~69 m native ground resolution of z11 Terrarium at 26°N |
| Output CRS | `EPSG:4326` | MapLibre/GeoJSON; areas computed geodesically |
| Assam mask | Dissolved union of filtered ADM2 polygons | Applied to flood/risk outputs and district metrics |
| Output clip | Assam union (strict) for flood/risk metrics; channel raster includes a 2 km buffer | Keeps river-mouth geometry continuous without counting foreign cells |
| No-data | `-9999` in GeoTIFF; `null`/absent in JSON | Never `0`, which is a valid elevation |

At 90 m the AOI is roughly 42 million cells (≈168 MB per float32 raster). The distance transform
needs a few full-size arrays; the budget is ≤3 GB peak RSS and ≤1.5 GB disk for intermediates.
A 30 m grid would be ~9× the cells and is explicitly P2.

EPSG:32646 is chosen over Web Mercator because nearest-drainage distance and polygon area should
be in metres; the AOI’s western edge is ~0.45° outside the zone’s nominal 90°E boundary, where
UTM scale error is still negligible for a 90 m screening model. It is chosen over a bespoke
Albers projection to avoid an extra CRS definition that a reviewer cannot check at a glance.

### 3.2 Why this AOI

- It contains the whole Assam plain and the Brahmaputra main stem, so the causal story is not
  clipped at a district line.
- The buffer matters: a cell near the state edge must be able to see a channel just outside it.
- The mask matters: cells in Meghalaya or Bhutan are used for terrain/channel continuity but do
  not appear in district rankings or "Assam inundated area".
- The bbox is deliberately rectangular. A river-corridor polygon would save cells but would make
  the AOI definition harder to audit and would clip tributaries.

---

## 4. Environment and conventions

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
| 06 | `build-rivers` | river raw | simplified rivers, channel lines | Rivers yes; channels intermediate |
| 07 | `burn-rivers` | DEM, channels | burned DEM, channel mask | No |
| 08 | `compute-hand` | burned DEM, mask | HAND, distance, metadata | No |
| 09 | `build-inundation` | HAND, mask, scenario | flood frames, summary, depth stack | Frames/summary yes; stack no |
| 10 | `build-risk` | stack, HAND, districts | risk zones, ranking, hotspots, districts GeoJSON | Yes |
| 11 | `build-series` | scenario, summary, transects | monsoon series, cross-sections | Yes |
| 12 | `build-assets` (P1) | OSM, stack, frames, districts | critical facilities | Yes |
| 13 | `build-gauges` (P1) | rivers, summary | virtual gauges | Yes |
| 14 | `validate` | all public data | validation report + exit code | Yes |
| 15 | `publish` | validated data | manifest, provenance | Yes |

M0 runs stages **01–11, 14, 15**. Stages 12–13 are optional P1 outputs; when omitted, the
manifest simply has no entry for them and the app hides those panels. Stages 04–11 are the
minimum to produce the M0 data; stages 01–03 fetch its sources.

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

### Stage 06 — build river display layer and channel lines

```powershell
python -m baanh_pipeline.cli build-rivers `
  --raw pipeline/cache/rivers/rivers-raw.geojson `
  --aoi pipeline/config/aoi.json `
  --out public/data/hydro/assam-rivers.geojson `
  --out-channels pipeline/work/channel-lines.geojson
```

- **Input:** raw rivers.
- **Process:** clip to AOI + 5 km; drop lines shorter than 500 m; assign `order` (1 = Brahmaputra
  main stem by name/length heuristic, 2 = named tributaries, 3 = other rivers, 4 = streams,
  5 = canals/drains); simplify display geometries at 50 m; keep a denser channel version for
  rasterisation (no simplification below 90 m).
- **Output:** `public/data/hydro/assam-rivers.geojson` (display), ≤1.0 MB;
  `pipeline/work/channel-lines.geojson` (burn input).
- **Validation:** at least one `order: 1` line; total channel length > 500 km; every geometry
  valid. If OSM returns only unnamed fragments, the fallback flag is recorded and shown in
  provenance.

### Stage 07 — burn channels into the DEM

```powershell
python -m baanh_pipeline.cli burn-rivers `
  --dem pipeline/work/dem-90m.tif `
  --channels pipeline/work/channel-lines.geojson `
  --out-dem pipeline/work/dem-burned.tif `
  --out-channels pipeline/work/channels-90m.tif `
  --burn-depth-m 3.0
```

- **Input:** 90 m DEM; channel lines.
- **Process:** rasterise channels at 90 m with `all_touched=True` (main stem width 2 cells,
  others 1 cell); for each channel cell sample the minimum DEM in a 5×5 window and subtract
  `burn_depth_m = 3.0`; write that value into `dem-burned.tif`; all other cells keep DEM.
  The burn is a **modelling device** to make the channel the local low point, not a surveyed
  incision depth. No monotonic downstream enforcement is attempted because OSM way direction is
  unreliable; this is a stated limitation.
- **Output:** `pipeline/work/dem-burned.tif`, `pipeline/work/channels-90m.tif` (uint8 0/1),
  `pipeline/work/burn-meta.json` (`channel_cells`, `burn_depth_m`, `dem_delta_min/max`).
- **Validation:** channel cells >0; mean burned elevation < mean adjacent DEM by 1–6 m; no
  channel cell ends up above its pre-burn value.

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
- **Validation:** HAND ≥0 everywhere valid; distance monotonic with mask distance; at least 85%
  of Assam-masked cells valid; no NaN/Inf.

### Stage 09 — build the inundation sequence

```powershell
python -m baanh_pipeline.cli build-inundation `
  --dem pipeline/work/dem-burned.tif `
  --hand pipeline/work/hand-90m.tif `
  --distance pipeline/work/channel-distance-90m.tif `
  --channels pipeline/work/channels-90m.tif `
  --state public/data/admin/assam-state.geojson `
  --scenario pipeline/config/scenario.json `
  --out-frames public/data/flood/flood-frames.geojson `
  --out-summary public/data/flood/flood-summary.json `
  --out-stack pipeline/work/inundation-stack.npz
```

- **Input:** DEM/HAND/distance/channel mask; state mask; scenario steps.
- **Process:** for each step, threshold HAND by `stage_m`, apply Assam mask and connectivity,
  derive depth bands, polygonise, validate/simplify, compute summary. Full algorithm in §7.
- **Output:** `flood-frames.geojson` (≤6.5 MB), `flood-summary.json`, and the intermediate
  `inundation-stack.npz` with `depth[step, y, x]` float32 and `wet[step, y, x]` bool.
- **Validation:** area non-decreasing on the rising limb (S00–S07, 0.5% tolerance), decreasing on
  recession (S08–S11), peak at S07; every polygon valid; no feature outside the AOI.

### Stage 10 — risk zones, district ranking, hotspots

```powershell
python -m baanh_pipeline.cli build-risk `
  --stack pipeline/work/inundation-stack.npz `
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

- **Input:** per-step depth stack; HAND/distance/channel mask; district polygons; scenario.
- **Process:** compute per-cell duration and peak depth; classify risk zones; aggregate district
  metrics and score; join risk fields into the district GeoJSON; extract low-HAND distant
  pockets for hotspots. Full formulas in §9.
- **Output:** `risk-zones.geojson` (≤0.9 MB), `district-risk.json` (≤0.15 MB),
  `assam-districts.geojson` (≤1.2 MB), `hotspots.geojson` (≤0.10 MB).
- **Validation:** all scores 0–100; every district appears once in the ranking; `rank` is a
  dense descending ranking; no population/asset-loss field; hotspots inside Assam; zone classes
  match the score thresholds.

### Stage 11 — monsoon series and cross-sections

```powershell
python -m baanh_pipeline.cli build-series `
  --scenario pipeline/config/scenario.json `
  --summary public/data/flood/flood-summary.json `
  --stack pipeline/work/inundation-stack.npz `
  --dem pipeline/work/dem-90m.tif `
  --channels pipeline/work/channels-90m.tif `
  --transects pipeline/config/transects.json `
  --out-series public/data/series/monsoon-series.json `
  --out-profiles public/data/series/cross-sections.json
```

- **Input:** scenario config; flood summary; depth stack; DEM/channel mask; transect endpoints.
- **Process:** emit the chart-ready synthetic rainfall/stage series and the scenario threshold
  (cross-checked against `flood-summary.json`); sample each transect at 2 km spacing, record
  ground elevation, HAND, and water surface/depth for all 12 steps. Water surface at a sample =
  nearest channel elevation + scenario stage. Samples with nodata HAND become `ground_m: null`
  and are omitted from the profile; the count is reported.
- **Output:** `monsoon-series.json` (≤0.05 MB), `cross-sections.json` (≤0.20 MB).
- **Validation:** 12 points per series; values identical to summary at each step (tolerance 1e−6);
  every transect has ≥30 valid samples; no NaN.

### Stage 12 — critical-facility exposure (P1)

```powershell
python -m baanh_pipeline.cli build-assets `
  --aoi pipeline/config/aoi.json `
  --sources pipeline/config/sources.json `
  --stack pipeline/work/inundation-stack.npz `
  --frames public/data/flood/flood-frames.geojson `
  --districts public/data/admin/assam-districts.geojson `
  --out public/data/assets/critical-facilities.geojson
```

- **Input:** OSM Overpass; flood frames; districts.
- **Query:** `(node["amenity"~"^(hospital|clinic|school)$"](bbox);); out body;` with a 180 s
  timeout. Names are taken from OSM `name`; missing names stay `null` (never invented).
- **Process:** keep points inside Assam; spatial-join to district; sample the depth stack at the
  point location for each step; record peak depth, first wet step, and an exposure band.
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

Runs V01–V20 (§10), writes the report atomically, prints a one-line summary, and exits non-zero
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
| `path` | string | relative to `public/`, e.g. `data/flood/flood-frames.geojson` |
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

Required entries: terrain, boundaries, rivers, flood frames, risk, series, hillshade, and
(if present) assets, gauges, UNOSAT note. `notes` must state assumptions that affect the layer.

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
  "threshold_stage_m": 4.0,
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
    "version": "hand-v1",
    "burn_depth_m": 3.0,
    "max_channel_distance_m": 12000,
    "connectivity": "8-connected; component must touch a channel cell",
    "min_polygon_area_km2": 0.02,
    "simplify_tolerance_m": 75,
    "depth_bands_m": [0.0, 0.5, 1.5, 3.0, null]
  },
  "assumptions": ["…"],
  "limitations": ["…"]
}
```

`steps[]` fields: `step` integer 0–11; `label` string (`DD Mon`, no year); `day_offset` integer
0–136; `phase` enum `onset|rising|peak|receding`. `depth_bands_m` has five edges; the last band is
open-ended (`null`).

`assumptions` must include: uniform stage over mapped channels; flat water surface per step;
HAND threshold with connectivity; no calibration; synthetic hydrograph. `limitations` must
include: no hydrodynamic routing; no levee failure; mapped channels incomplete; 90 m grid; no
population/asset-loss estimate.

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
| `waterway` | enum | — | `river\|stream\|canal\|drain` |
| `order` | integer | 1–5 | 1 = main stem, 5 = drain |
| `source` | enum | — | `osm\|natural-earth` |
| `source_id` | string | — | Native id |
| `class` | string | — | `source` |
| `label` | string | — | “River centreline (OSM/ODbL)” |

### 6.7 `flood/flood-frames.geojson`

One `FeatureCollection`; features are polygons for **each depth band at each step**. Within a
step the bands are non-overlapping and their union is the inundated extent. Across steps,
features overlap (each step is a full snapshot); the app filters by `step`.

| Field | Type | Unit | Notes |
|---|---|---|---|
| `step` | integer | 0–11 | Timeline key |
| `step_label` | string | — | `DD Mon` |
| `phase` | enum | — | `onset\|rising\|peak\|receding` |
| `depth_band` | enum | — | `0.0-0.5`, `0.5-1.5`, `1.5-3.0`, `3.0+` |
| `depth_m_lo` | number | m | Inclusive lower edge |
| `depth_m_hi` | number \| null | m | Exclusive upper edge; `null` for `3.0+` |
| `band_area_km2` | number | km² | Area of this polygon |
| `step_area_km2` | number | km² | Total inundated area at this step (repeated) |
| `class` | string | — | `scenario` |
| `model_version` | string | — | `hand-v1` |
| `label` | string | — | e.g. “Scenario inundation · 25 Aug · 1.5–3.0 m” |

Geometry: `Polygon`/`MultiPolygon`, EPSG:4326, simplified 75 m, min ring 0.02 km², 5 decimals.
No feature may straddle two `step` values.

### 6.8 `flood/flood-summary.json`

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
      "mainstem_stage_m": 3.4,
      "backwater_m": 2.6,
      "stage_m": 6.0,
      "above_threshold": true,
      "inundated_area_km2": 0.0,
      "new_inundation_km2": 0.0,
      "receded_area_km2": 0.0,
      "max_depth_m": 0.0,
      "mean_depth_m": 0.0,
      "affected_district_count": 0,
      "valid_cell_share": 0.0
    }
  ],
  "totals": {
    "max_area_km2": 0.0,
    "peak_stage_m": 6.0,
    "scenario_days": 136,
    "districts_any_inundation": 0
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
- `above_threshold`: `stage_m >= scenario.threshold_stage_m` (4.0). A model flag, not an official warning.
- `inundated_area_km2`: union of wet cells inside Assam at the step.
- `new_inundation_km2`: cells wet at `t` and dry at `t−1` (0 at t=0).
- `receded_area_km2`: cells dry at `t` and wet at `t−1` (0 at t=0).
- `max_depth_m`, `mean_depth_m`: over wet cells at the step; mean is area-weighted.
- `affected_district_count`: districts with >1 km² wet.
- `valid_cell_share`: share of Assam-masked cells with valid HAND. A global coverage caveat.
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
| `model_version` | string | — | `hand-v1` |
| `label` | string | — | e.g. “Derived risk zone · high” |

Geometry: `Polygon`/`MultiPolygon`, simplified 100 m, min 0.05 km². Only cells wet in at least
one step are classified, so the layer is **scenario-conditional risk**, not all-time flood risk.

### 6.10 `risk/district-risk.json`

```json
{
  "schema_version": "1.0.0",
  "scenario_id": "assam-monsoon-composite-v1",
  "class": "derived",
  "generated_at": "2026-10-21T00:00:00Z",
  "weights": { "area_share": 0.45, "duration": 0.35, "depth": 0.20 },
  "reference_values": {
    "area_share_saturation": 0.60,
    "duration_saturation_days": 90,
    "depth_reference_m": 4.0
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
      "risk_score": 0.0,
      "risk_class": "very_high",
      "drivers": ["area", "duration"],
      "valid_area_share": 0.0,
      "class": "derived"
    }
  ],
  "counts": { "total": 0, "very_high": 0, "high": 0, "moderate": 0, "low": 0, "no_data": 0 }
}
```

`drivers` is a deterministic array of the top two weighted contributions, labels `area`,
`duration`, `depth`. No demographic field exists.

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
    "value": 4.0,
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
      "expected": "non-decreasing, tolerance 0.5%",
      "actual": "…",
      "detail": "steps 0–7"
    }
  ],
  "counts": { "files": 16, "steps": 12, "features": 0, "failures": 0, "warnings": 0 }
}
```

`status` is `pass` only if every check is `pass` or an allowed `warn`. A `fail` makes `publish`
refuse.

### 6.17 `basemap/assam-hillshade.webp`

Binary, not JSON. Contract: 8-bit grayscale WebP, width 2000 px, height derived from the AOI
aspect ratio, quality 82, ≤1.5 MB. It is **not** georeferenced in the file; the app positions it
with the AOI Mercator corners from `manifest.json` (`bbox`) and `provenance.json`. It contains no
labels, no water, no flood extent—only relief—so it cannot be mistaken for an observation.

---

## 7. Inundation model specification

This is the exact model a builder must implement. It is a **HAND-threshold screening model**, not
a hydrodynamic simulation. Every simplification is stated; do not fill the gaps with invented
physics.

### 7.1 Constants

| Constant | Value | Meaning |
|---|---|---|
| `RES_M` | 90 | Analysis cell size, metres |
| `CRS` | EPSG:32646 | Analysis projection |
| `BURN_DEPTH_M` | 3.0 | Channel lowering, metres |
| `MAX_CHANNEL_DISTANCE_M` | 12000 | Beyond this, HAND is undefined |
| `MIN_POLYGON_AREA_KM2` | 0.02 | Drop smaller flood rings |
| `SIMPLIFY_TOLERANCE_M` | 75 | Flood polygon simplification |
| `MIN_COMPONENT_CELLS` | 3 | ~0.024 km² at 90 m |
| `DEPTH_BANDS_M` | `[0, 0.5, 1.5, 3.0, null]` | Four classes |
| `CONNECTIVITY` | 8-connected | Component must touch a channel cell |
| `PEAK_STEP` | 7 | 25 Aug |
| `ALERT_STAGE_M` | 4.0 | Scenario flag threshold |

### 7.2 Step A — DEM mosaic

1. Decode each z11 Terrarium PNG as `z = R*256 + G + B/256 - 32768` (metres).
2. Mosaic in its native Web Mercator grid, then warp to EPSG:32646 at 90 m with bilinear
   resampling. Record the affine transform and nodata.
3. Fill only small voids (≤100-cell search). A large void is a fetch failure; fail.
4. Clip to the AOI rectangle. Keep a boolean `inside_assam` mask from the dissolved state
   polygon; it is used at output time, not to alter the DEM.

### 7.3 Step B — channel burn-in

1. Rasterise `channel-lines.geojson` at 90 m, `all_touched=True`, with the main stem (`order 1`)
   dilated to 2 cells and all other channels 1 cell. This is `channel_mask`.
2. For each channel cell, `z_burn = min(DEM[5×5 neighbourhood]) - 3.0`.
3. Write `z_burn` only at channel cells into `dem-burned.tif`; all other cells keep DEM.
4. Do **not** enforce a downstream monotonic elevation. OSM way direction is not reliable, and a
   false monotonic pass would create a fake longitudinal profile. The consequence—occasional
   local channel highs—is limited by the 5×5 minimum and is listed as a limitation.

Why burn at all: a DEM at 90 m often puts the photographed ground surface above the water
surface in a narrow channel; without lowering, the nearest “drainage” would be higher than the
floodplain and HAND would be systematically negative. A 3 m burn is a declared modelling device,
not a surveyed channel depth.

### 7.4 Step C — nearest-drainage assignment

The question is: for every land cell, which channel cell is nearest, and how far is it?

1. Build the boolean mask `channel_mask` over the full AOI. Include channels in the 2 km buffer
   outside Assam so edge cells are not artificially cut off.
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

For each step `s` with stage `stage_s` (metres above local drainage):

```text
wet_raw = valid_hand AND inside_assam AND (hand <= stage_s)
depth_raw = max(0, stage_s - hand)
```

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
3. Drop components with fewer than `MIN_COMPONENT_CELLS` (3) cells.
4. `wet = retained components`; `depth = depth_raw` where wet, else 0.

This is a topological connectivity check, not a flow simulation. It can still retain a cell that
would be separated by a levee; that is covered by the no-levee limitation. It can drop a genuine
backwater pocket that is disconnected at 90 m; the count of dropped components is recorded and
reported, and the limitation is stated.

### 7.8 Step G — depth bands and polygonisation

For each step:

1. Convert `depth` to a uint8 band raster: 1 = `0.0–0.5 m`, 2 = `0.5–1.5 m`, 3 = `1.5–3.0 m`,
   4 = `3.0+ m`; 0 = dry.
2. Polygonise each band separately with `rasterio.features.shapes(band, mask=band>0,
   transform=transform)`. This guarantees bands do not overlap within a step.
3. Transform coordinates to EPSG:4326. `shapely.make_valid`; if still invalid, fail that feature
   (do not silently drop it) and report.
4. Simplify with `shapely.simplify(tolerance=75 / 111320 degrees, preserve_topology=True)`
   (≈75 m at the equator; at 26°N the longitude tolerance is scaled by `1/cos(26°)` so the
   ground tolerance remains ~75 m). Builder note: do the simplification in EPSG:32646 and then
   transform to WGS84; this is the preferred implementation and avoids the latitude correction.
5. Drop rings/parts smaller than 0.02 km² (geodesic). Keep holes only if ≥0.02 km²; fill smaller
   holes.
6. Quantise coordinates to 5 decimals; remove consecutive duplicates; enforce RFC 7946 exterior
   counter-clockwise / interior clockwise winding.
7. Compute `band_area_km2` geodesically; `step_area_km2` is the sum of bands.
8. Emit one feature per band per step with the properties in §6.7.

### 7.9 Step H — no reachable channel, edge cases

| Case | Handling | Visible consequence |
|---|---|---|
| No channel within 12 km | HAND nodata; never wet; counted in `hand-meta.json` | Cell absent from flood/risk; `valid_area_share` caveat |
| No channel at all in AOI | Pipeline fails V04/V17; no output | No fake flood |
| Cell below nearest channel | HAND clamped to 0; counted; warning if >2% | Cell floods at the first stage ≥0 |
| Channel elevation above cell but distance valid | Same clamp; local depression | Stated limitation |
| Isolated wet component | Dropped by connectivity; count reported | Avoids speckle |
| Cell outside Assam | Computed for continuity but excluded from output and metrics | No foreign districts in ranking |
| Stage above maximum HAND | Depth clipped at stage; no extrapolation | Max depth reported honestly |
| Recession step leaves a disconnected puddle | Connectivity applies per step; puddle may drop | Area can fall faster than a hydrodynamic model |

No cell is ever assigned a HAND from a different basin by hand. If the nearest channel is across
a ridge, the Euclidean method will still use it; that is a known limitation of non-routed HAND
and is stated in-app. A flow-accumulation/routing refinement is P2.

---

## 8. Scenario table and synthetic anchoring

### 8.1 The 12 steps

`N = 12`; peak at S07; total 136 days. Dates are **composite labels without a year** to avoid
implying a specific observed event.

| Step | Label | Day | Phase | Rainfall (mm/day, synthetic) | Main-stem anomaly (m, synthetic) | Backwater allowance (m, synthetic) | Stage above drainage (m, scenario) | Above threshold |
|---:|---|---:|---|---:|---:|---:|---:|---|
| S00 | 01 Jun | 0 | onset | 6 | 0.3 | 0.2 | 0.5 | no |
| S01 | 15 Jun | 14 | rising | 12 | 0.7 | 0.3 | 1.0 | no |
| S02 | 01 Jul | 30 | rising | 17 | 1.2 | 0.5 | 1.7 | no |
| S03 | 15 Jul | 44 | rising | 21 | 1.8 | 0.7 | 2.5 | no |
| S04 | 25 Jul | 54 | rising | 24 | 2.4 | 1.0 | 3.4 | no |
| S05 | 05 Aug | 65 | rising | 20 | 2.9 | 1.4 | 4.3 | yes |
| S06 | 15 Aug | 75 | rising | 14 | 3.2 | 2.0 | 5.2 | yes |
| S07 | 25 Aug | 85 | peak | 10 | 3.4 | 2.6 | 6.0 | yes |
| S08 | 05 Sep | 96 | receding | 7 | 3.2 | 2.0 | 5.2 | yes |
| S09 | 15 Sep | 106 | receding | 5 | 2.7 | 1.4 | 4.1 | yes |
| S10 | 30 Sep | 121 | receding | 3 | 1.9 | 1.0 | 2.9 | no |
| S11 | 15 Oct | 136 | receding | 2 | 1.0 | 0.6 | 1.6 | no |

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
- Every stage-above-drainage value and the 4.0 m scenario threshold.
- The step dates (composite month/day labels, no year).

**Derived (computed, not observed):**
- Inundation extent, depth bands, areas, risk zones, district scores, hotspots.

**Real (source data):**
- Terrain, district boundaries, state outline, rivers, and (P1) facility locations.

The scenario is deliberately not calibrated to a gauge. A reviewer must be able to see that the
hydrograph is a shape, not a claim. The in-app copy says: “Synthetic monsoon scenario; not a
forecast, not a gauge record, not an evacuation instruction.”

### 8.3 Why these values

The stage rises from 0.5 m to 6.0 m, a plausible order of magnitude for a large floodplain
screening exercise, but **the number is a model parameter, not a measured flood level**. It was
chosen to produce a legible sequence from first inundation to a broad peak without flooding the
entire AOI. The rainfall peak at S04 and stage peak at S07 create a visible lag. The recession is
slower than the rise (51 days from peak to S11 vs 85 days from S00 to peak), matching the
qualitative behaviour of a large valley draining after the monsoon.

The stage is the exact sum of the two synthetic columns:
`stage_m = mainstem_stage_m + backwater_m`. The split is a narrative device for the causal chain
(a main-stem rise plus a tributary/backwater allowance), not a solved backwater term. The model
applies the summed stage uniformly to every mapped channel. A reviewer must not read the split as
two independent physical estimates.

If the builder changes any value, they must update the scenario table, the config, the summary,
the series, and the validation expectations together. No component may hard-code 6.0 or step 7;
they come from `scenario.json`/`flood-summary.json`.

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

Polygonise the classified raster, simplify at 100 m, drop polygons < 0.05 km². A polygon’s
`risk_score` is the area-weighted mean cell score; its class is the class of that mean, and
because polygonisation is per class the mean stays inside the class band. If a merged polygon
would cross a class boundary, keep the classes separate (do not merge across classes).

### 9.2 District aggregation → ranking

For district `d`:

```text
area_share = min(peak_flooded_area_km2 / district_area_km2, 1.0)
A = min(area_share / 0.60, 1)
D = min(mean_duration_days / 90, 1)
H = min(p90_peak_depth_m / 4.0, 1)

risk_score = 100 × (0.45×A + 0.35×D + 0.20×H)
```

- `peak_flooded_area_km2` is the maximum wet area within the district over the 12 steps.
- `district_area_km2` is the geodesic source-polygon area, not the raster cell count.
- `mean_duration_days` is area-weighted over cells ever wet; dry cells are excluded from the
  mean (otherwise large dry districts would look safer than they are).
- `p90_peak_depth_m` is the area-weighted 90th percentile of depth at the peak step (S07).
- `valid_area_share` is the share of the district’s raster cells with valid HAND; it is a
  coverage caveat, **not** part of the score.

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
`counts.no_data` so the total is still auditable. `drivers` is the two largest of `0.45A`,
`0.35D`, `0.20H`; ties break in the order area, duration, depth.

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

---

## 10. Validation — checks that must pass before data ships

`validate` runs every check, records expected/actual, and exits non-zero on `fail`. `publish`
refuses if `status != "pass"`.

| ID | Check | Pass condition | Fail / warn |
|---|---|---|---|
| V01 | Schema validity | Every committed JSON/GeoJSON parses and matches its §6 schema | fail |
| V02 | Geometry validity | No `null`/empty geometry; `shapely.is_valid` true after `make_valid`; no self-intersection | fail |
| V03 | Bounds | Every coordinate inside AOI + 0.01°; no swapped lon/lat | fail |
| V04 | Assam containment | Districts/state intersect Assam; flood/risk/hotspot centroids inside the buffered state | fail |
| V05 | Rising-limb monotonicity | `area[S00..S07]` non-decreasing, tolerance 0.5% | fail |
| V06 | Recession | `area[S08..S11]` non-increasing; peak step = 7 | fail |
| V07 | Finite numbers | No `NaN`, `Infinity`, `-Infinity` anywhere; JSON `allow_nan=False` | fail |
| V08 | Classes and labels | Every feature `class` in the five-value enum; badges/labels present; no layer missing a class | fail |
| V09 | File caps | Every file ≤ its §11 cap; total ≤14 MB | fail |
| V10 | Manifest integrity | Every file except `manifest.json` is listed once; SHA-256 and byte size match; no orphan data file | fail |
| V11 | Series and stage consistency | `monsoon-series` points equal `flood-summary` at every step (1e−6); threshold = 4.0; `stage_m = mainstem_stage_m + backwater_m` at every step | fail |
| V12 | District join | Every ranking district exists in districts GeoJSON exactly once; `rank` dense; score 0–100 | fail |
| V13 | Forbidden fields/claims | No `casualties`, `deaths`, `displaced`, `affected_persons`, `incident_id`, `agency_id`, `relief_camp`, `eta`, `warning_issued`; no positive `operational forecast`/`official forecast`/`flood forecast`. A bare `forecast` passes only inside the required negation `not a forecast` / `never a forecast` or the boolean key `not_a_forecast`. | fail |
| V14 | Step count | Exactly 12 steps; labels/days/phases match `scenario.json`; every step has at least one feature | fail |
| V15 | Coordinate hygiene | 5 decimals; no consecutive duplicates; RFC 7946 winding; no ring <0.02 km² (flood) | fail |
| V16 | Risk range | All scores 0–100; zone classes match thresholds; ranking classes match thresholds | fail |
| V17 | Channel coverage | ≥85% of Assam-masked cells valid HAND; no-channel cells reported; clamped negatives ≤2% | warn if 80–85%; fail <80% |
| V18 | Fallback asset | `assam-hillshade.webp` exists, ≤1.5 MB, decodes, width 2000 | fail |
| V19 | First-paint budget | Critical-tier bytes ≤3.5 MB raw; total animation tier ≤7.6 MB raw | fail |
| V20 | Provenance completeness | Every committed dataset has a provenance entry with source/licence/stage/output; UNOSAT absence noted | fail |

Additional assertions inside stages:

- `build-dem`: elevation range sanity (−50 to 8,000 m); no ocean zeros inside Assam.
- `build-admin`: centroid inside polygon; state area within 1% of the district sum.
- `build-rivers`: at least one main-stem line; channel length >500 km.
- `build-inundation`: peak area >0; peak area <30% of Assam (sanity bound, not a scientific
  claim); `new_inundation` and `receded` non-negative.
- `build-risk`: districts with zero valid cells do not receive a score; hotspot count ≤20.
- `publish`: refuses on a dirty/partial data directory or missing report.

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

### 11.1 Caps

| File | Cap |
|---|---|
| `flood/flood-frames.geojson` | 6.5 MB |
| `admin/assam-districts.geojson` | 1.2 MB |
| `admin/assam-state.geojson` | 0.15 MB |
| `hydro/assam-rivers.geojson` | 1.0 MB |
| `risk/risk-zones.geojson` | 0.9 MB |
| `risk/district-risk.json` | 0.15 MB |
| `risk/hotspots.geojson` | 0.10 MB |
| `series/monsoon-series.json` | 0.05 MB |
| `series/cross-sections.json` | 0.20 MB |
| `basemap/assam-hillshade.webp` | 1.5 MB |
| `assets/critical-facilities.geojson` | 1.0 MB |
| `gauges/virtual-gauges.geojson` | 0.10 MB |
| manifest + provenance + scenario + validation | 0.25 MB combined |
| **Total committed data** | **14 MB** |

Tiers: critical (manifest, scenario, provenance, districts, state, rivers, district-risk,
monsoon-series, validation) ≤3.5 MB raw; animation (flood frames, summary, risk zones) ≤7.6 MB
raw; optional/fallback (hillshade, cross-sections, hotspots, assets, gauges) ≤3.0 MB raw.

If the flood cap is exceeded, reduce depth bands (four → three) before coarsening the grid or
simplifying below 75 m. The model resolution is the last thing to degrade.

### 11.2 Expected runtime

| Stage | Wall time (reference laptop) | Peak RSS |
|---|---|---|
| fetch terrain (z11, ~900 tiles) | 2–6 min | <500 MB |
| fetch boundaries/rivers | 1–3 min (Overpass can be 30 s+) | <300 MB |
| DEM/hillshade | 1–2 min | 1.5 GB |
| HAND | 2–4 min | 3 GB |
| Inundation (12 steps) | 4–8 min | 3 GB |
| Risk/series | 2–4 min | 2 GB |
| Validate/publish | <1 min | <300 MB |

Disk for cache + work: ≤1.5 GB. The pipeline is single-machine and not parallelised beyond tile
fetching; clarity over speed.

### 11.3 Determinism

- Given the same cached inputs, the numeric outputs are deterministic: SciPy EDT is
  deterministic, rasterio polygonisation is deterministic, and geometries are sorted by
  `(step, depth_band, area desc, centroid)` before writing.
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

1. **Not a forecast.** The scenario is synthetic; the model is a terrain screening tool.
2. **No hydrodynamic routing.** Uniform stage over mapped channels; no unsteady flow, no
   backwater solver, no sediment.
3. **No defences.** Levees, embankments, roads, and flood walls are absent; the model may
   overstate inundation behind protection.
4. **Incomplete channels.** HAND uses mapped rivers; first-order streams are missing, so HAND is
   conservative on hills and coarse near small tributaries.
5. **90 m grid.** Smaller channels, culverts, and local depressions are not resolved.
6. **Euclidean nearest drainage.** A channel across a ridge can be selected; no flow-path
   distance.
7. **No calibration.** Stage values are not fitted to a gauge or a satellite extent.
8. **Scenario-conditional risk.** Risk zones and district scores describe this scenario, not
   all-time flood risk or expected loss.
9. **No demographics or assets in the score.** P1 facility exposure is a depth join, not damage.
10. **OSM completeness.** Facility and river completeness is uneven; the UI says so.

If a reviewer asks for an operational forecast, the answer is that this product is not one and
the data to make one is not among the probed sources. Do not add a plausible-looking feed.
