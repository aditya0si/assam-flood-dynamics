# Review: Baanh / assam-flood-dynamics — independent panel report

Reviewer run: 2026-10-21. Read-only. Evidence: repository at `C:/Users/oliad/Desktop/baanh`, live URL probed with `curl` (root 200 (1,472 B), `data/manifest.json` 200 (11,828 B), `data/flood/frames/step-07.png` 200 (254,791 B) — byte-identical to the committed local file).

## 1. Current state, as built

What it genuinely is: a static Vite/React 19/MapLibre 5 SPA (`package.json:20-27`) that renders a 12-step, 136-day **synthetic** monsoon scenario (`public/data/scenario.json`, `threshold_stage_m: 2.0`, peak S07 stage 3.70 m) as HAND-threshold inundation over a 90 m analysis grid in EPSG:32646, displayed as 3,733×2,611 paletted PNG frames at 180 m/px (`frame-index.json:12-17`). Peak extent 10,010.64 km² = 32.2% of the 31,050 km² flood-prone denominator (`docs/M0-REPORT.md:58`). The pipeline is real GIS code — `pipeline/src/baanh_pipeline/` is ~9,170 lines including a 1,656-line validator; `hand.py:47-61` is an exact SciPy EDT on a 3 m channel-burned DEM, `inundation.py:78-140` implements the documented connectivity + ≥9-cell component filter, `risk.py:467-471` implements the published 0.45/0.35/0.20 district score.

Genuinely strong:
- **Honesty machinery is a real gate, not prose.** `scripts/check-honesty.mjs` bans casualty/agency/forecast fields; its self-test injects 9 banned strings and the gate fails on each (`M0-REPORT.md:88-100`). A reviewer falsified it independently (`docs/REVIEW-09`, `M0-REPORT.md:201`).
- **Executable acceptance**: `verify:m0` (`package.json:17`) chains build → data/budget/honesty gates → unit → Playwright; CI runs it on Linux green 10/10 (`M0-REPORT.md:186-193`).
- **Review trail** `REVIEW-02…14` documents reversals against the reviewer's own errors (e.g. `REVIEW-03`: "my thresholds were wrong, not the model") — rare and valuable.
- **Budget/offline discipline**: 4.63 MB of the 9 MB cap; tile-host fallback tested with both hosts aborted (`tests/e2e/fallback.spec.ts`).

Genuinely weak (all falsifiable from committed data):
1. **The recession is a byte-identical mirror of the rise.** S06 (15 Aug) and S08 (05 Sep) share stage 3.25 m and therefore identical masks: both 6,857.4231 km², 212,146 wet cells, 193,215 PNG bytes (`frame-index.json:122-151`). Same for S02/S11. There is no drainage, no hysteresis — physically wrong for a floodplain that ponds for weeks.
2. **The "onset" frame is not dry**: S00 already reports 1,833.9 km² (18.3% of peak) at 0.30 m stage (`frame-index.json:67`), driven by clamped-HAND-zero cells (peak clamped wet share 21.0%, `M0-REPORT.md:59-60`).
3. **The depth term is dead.** All 33 districts have `p90_peak_depth_m: 3.70` exactly (`risk/district-risk.json`, every row) — identical to peak stage. The 0.20×min(3.7/4,1)=18.5 points contribute equally to every score; ranking is effectively area+duration only.
4. **Duration mean inflates slivers.** Dima Hasao: 17.8 km² wet of 4,904 (area_share 0.0036), `valid_area_share` 0.466, yet ranks 12/33 "high" with mean_duration 114.7 d — above Dhubri with 194.0 km² wet (10.9% share). `mean_duration_days` is averaged over ever-wet cells only (`risk.py:434-440`), so a few channel-adjacent cells dominate.
5. **The topology filter, not the terrain, sets the margin**: at peak, 14,221 → 10,016 → 10,010.6 km² (`docs/PIPELINE-REPORT.md:22`) — connectivity alone removes ~30% of raw threshold area.
6. **M1 is mostly unshipped.** Actual panels are four (`src/shell/PanelRouter.tsx:36-39`: risk, provenance, methodology, layers); the layer registry has six layers including hotspots (`layerRegistry.ts:32-92`), but no Overview/Story/Cross-section/Gauge/Imagery panels that `MILESTONES.md` lists. 636 KB of committed P1 data (`critical-facilities.geojson` 574,243 B; `cross-sections.json` 58,222 B; `virtual-gauges.geojson` 3,430 B) is hashed, budgeted, validated — and never fetched (`loadData.ts` references only hotspots, line 128).

Portfolio vs real user: as a portfolio artifact this is strong — shipped, tested, honest, with a review trail. For a real disaster-management user it has **zero operational value today**: synthetic forcing, no defences (the dominant Assam flood mechanism is embankment *breach*, which a HAND bathtub cannot represent), no exposure, no live feed, mirrored recession, 180 m display. Its value is as a disciplined shell and data contract onto which real data can be bolted.

## 2. Gap analysis against a real disaster-management system

**District duty officer (DDRAM/EOC)** needs: now-cast at *their* reach (gauge vs CWC danger level, minutes old), village/ward-scale affected population, road/bridge cut status, shelter status, 6–12 h lead time, print/SMS output, low-bandwidth/offline. Baanh has: a state-scale composite scenario on a 10–16-day clock, ADM2 only, no roads, no shelters, no now-cast, no export (print is optional M2, `MILESTONES.md:406`).

**State EOC (ASDMA)** needs: multi-district situation updated 6-hourly, IMD/CWC/NDRF feeds, trend vs yesterday, confidence bands, resource view, audit log. Baanh: one immutable `dataset_version 2026.10.0`, no update concept, no roles, deliberately no backend.

**NDMA analyst** needs: return-period maps (1-in-2/10/50/100 y), defence-aware hydraulics, exposure and vulnerability (population, crop, GDP), hindcast validation against real events, ensemble uncertainty, transboundary inflow context (Brahmaputra enters from Tibet/Arunachal; upstream forcing is unmodelled), sediment/geomorphology of the braided system. Baanh: one synthetic scenario, terrain-only risk, no validation against any observation, no uncertainty quantification.

**Data gaps** (all currently absent, not merely unbuilt): rainfall, stage, discharge, bathymetry, embankments, population, roads, shelters, SAR truth, land use. **UX gaps**: no permalink (P1-09 unimplemented), no user-facing chart data export (the table at `ChartGrid.tsx:132` is `sr-only`), no mobile sheet, no Assamese/Bengali, no "model run id" surfaced to the user beyond the dataset version.

## 3. Real data integration plan

Everything below is free unless noted; nothing listed requires a paid key. "Not available" means no open dataset exists at usable resolution for Assam.

| Dataset | Provider / URL | Licence | Res. / cadence | Variables | Pipeline entry |
|---|---|---|---|---|---|
| Rain (gauge) | IMD gridded rainfall, mausam.imd.gov.in / dataportal.imd.gov.in | Free w/ registration (Govt of India) | 0.25° (~25 km), daily | mm/day | Areal forcing per sub-catchment; replaces synthetic rainfall series |
| Rain (satellite) | GPM IMERG V07 Final, NASA PPS/GES DISC | Free w/ Earthdata | 0.1° (~10 km), 30-min | mm/hr | Gap-filled forcing; real rainfall chart with provenance |
| River stage/discharge | CWC flood-forecast portal (cwc.gov.in/ffs); India-WRIS (india-wris.gov.in) | Free w/ registration; no official bulk API — report/scrape ingest, rate-limited | Station point, 15-min–daily | stage m, Q cumec | Rating-curve calibration, hindcast validation, future live adapter |
| DEM | Copernicus DEM GLO-30 (ESA) and/or FABDEM v2 (Univ. Bristol) | Free with attribution | 30 m, static | elevation | Stage 04 mosaic at 30 m → HAND; replaces/augments z11 Terrarium (~69 m) |
| Bathymetry | CWC/WRD cross-section surveys | **Not open** — request; terms unknown | surveyed sections | channel depth | Required for S3/S4 hydraulics; until then, declared synthetic sections |
| SAR flood extent | Sentinel-1 GRD via ASF DAAC / Google Earth Engine | Free (Copernicus) | 10 m, ~6-day revisit | water mask | Event masks for calibration/validation (CSI/IoU); also UNOSAT products (free, event-triggered, episodic — unknown for future Assam events); JRC Global Flood Database (250 m MODIS, 2000-18) too coarse/cloud-prone |
| Admin | geoBoundaries gbOpen ADM2 (in use); Census 2011 sub-district/ward + LGD codes | CC BY 4.0 / free | polygon | codes, names | Village-level exposure joins |
| Population | WorldPop unconstrained 100 m; Meta HRSL 30 m | Free, CC BY | 100 m / 30 m, yearly | count | Per-cell exposure join; Census 2011 ward counts as anchor |
| Roads / critical infra | OSM via Overpass bbox or Geofabrik India extract (no official state split) | ODbL | vector | bridges, NH/SH, hospitals | Exposure of lifelines; completeness caveat already modelled (`DATA-PIPELINE.md` stage 12) |
| Embankments | OSM `man_made=embankment`/`waterway=levee` (sparse); Assam WRD embankment GIS (**not downloadable — request, terms unknown**); Global Dike Database (Kc & Mistral 2022, published, availability verify) | ODbL / govt-request / published | vector | alignment, crest | Overlay now; breach module (S5) later |
| Land use | ESA WorldCover 10 m; Dynamic World 10 m | Free, CC BY 4.0 | 10 m, 2020/21 + near-RT | classes | Manning n / SCS CN per cell |
| Soil | SoilGrids 250 m (ISRIC) | Free | 250 m | texture, bulk density | Rainfall-runoff parameters |

Not available for Assam at usable resolution: **channel bathymetry** (none public), **complete embankment geometry** (no open dataset; OSM is unreliable here), **ward-level exposure/capacity tables** (shelter capacity sits with ASDMA/district DRM — unknown licence). One inconsistency to fix while touching provenance: `DATA-PIPELINE.md:115` cites Assam as 78,523 km² but `flood-summary.json` publishes `assam_area_km2: 78220.6`.

## 4. Simulation upgrade path

Staged hybrid, cheapest first. Each stage keeps the static Pages deploy.

**S1 — Gauge-driven, spatially variable stage (HAND retained).** Replace the single uniform stage with per-reach stages from CWC gauges (Pandu, Neamatighat, Goalpara, Dibrugarh, plus Barak at Badarpur) via fitted rating curves (fit log-log Q~h on gauged points, require R²≥0.90 on the gauged range; publish fit residuals). Buys: longitudinal water-surface slope, reach timing, observed anchoring. Costs: station ingest, datum harmonisation (each gauge has its own datum — the hardest part). Validation: hindcast 2022/2023; stage RMSE ≤0.5 m at ≥2 gauges, peak timing error ≤2 days. Effort: weeks.

**S2 — Rainfall-runoff at sub-catchment scale.** MERIT Hydro flow accumulation → ~100–500 sub-catchments; HEC-HMS or Gr4j per catchment, forced by IMERG+IMD, parameters from SoilGrids+WorldCover; Muskingum routing to confluences. Buys: the hydrograph becomes a *result*, enabling lead time. Costs: parameter equifinality, monsoon calibration effort. Validation: NSE ≥0.6, KGE ≥0.5 at ≥2 CWC discharge stations on 2022; daily timestep. Effort: 2–3 months.

**S3 — 1D hydrodynamic main stem + major tributaries.** HEC-RAS unsteady or LISFLOOD-FP 1D along ~700 km main stem, ~1,000–3,000 cross-sections (CWC surveys on request; else synthetic from DEM + declared width assumptions), lateral inflows from S2, dt 5–15 min. Buys: backwater, confluence stacking, rating at sections. Validation: multi-gauge stage hydrographs, RMSE ≤0.3 m; sensitivity run on the bathymetry assumption. Effort: 3–6 months.

**S4 — 2D floodplain routing.** LISFLOOD-FP local-inertial or HEC-RAS 2D at 30 m over the Brahmaputra corridor (AOI v2 is 52,241 km² ≈ 58M cells at 30 m — restrict 2D to ~20–30 km river buffers; keep 90 m elsewhere). Buys: real routing, ponding/drainage (kills the mirror recession), beel storage, timing. Costs: hours–days of CPU per event, calibration. Validation: CSI ≥0.4 / area bias ≤20% against Sentinel-1 peak extents of ≥2 events (e.g. June 2022, April 2024 — both publicly imaged by Sentinel-1; exact scenes to be listed when fetched). Effort: 6+ months.

**S5 — Embankment/breach module** (blocked on the levee dataset in §3): parametrised breach location/width/closure time in S3/S4; hindcast a documented breach event. Buys: the actual Assam failure mode. **S6 — Ensembles/uncertainty**: 20–50 members over rainfall, rating curves, roughness; publish P(wet) and P(depth>1 m) with Brier score and reliability diagrams against SAR; costs 20–50× runtime.

**Interim hybrid (recommended immediately):** keep HAND but (a) force it with observed gauge stages per reach (S1), (b) compute HAND against flow-conditioned channels (AGREE reconditioning from MERIT Hydro flow accumulation) instead of Euclidean nearest-drain, (c) add a drainage-delay rule (a cell stays wet N days after stage drops below its HAND) with N tuned on SAR ponding observations. Validation: 2022 hindcast CSI against one Sentinel-1 scene. Cost: pipeline-stage work only.

## 5. Prevention and mitigation features

Each feature tied to data that can actually be obtained, and to an actor:

- **Embankment risk view**: WRD alignment (request) + OSM levees; which settlements/roads lie within 2 km behind each reach; who acts: WRD embankment divisions, district DRM. Acceptance: every levee segment carries a source tag; "model does not simulate defence" banner mandatory until S5.
- **Breach what-if** (needs S5): pick reach + breach width; render the diff raster vs baseline; who acts: EOC pre-positioning (NDRF/SDPRF).
- **Retention/beel storage**: delineate beels from DEM (HAND<1 m, area>5 km²) + WorldCover wetlands; storage scenario quantified only once S3/S4 exists; who acts: WRD floodplain-management policy.
- **Land-use / roughness change**: WorldCover reclass → Manning n in the 2D model; levee-vs-restoration comparison; who acts: district planners.
- **Early-warning thresholds**: CWC publishes official escalation/danger levels per gauge (free, cwc.gov.in) — the product computes *exceedance countdown* from S2/S3 lead time. Who issues warnings: CWC/IMD/NDMA/ASDMA only. Acceptance: thresholds match CWC published values exactly; ≥24 h model lead time demonstrated on 2022/2023 hydrographs.
- **Evacuation routing / shelters**: road graph from OSM (free) routes to DEM-derived high ground; shelter *capacity* is not open data (ASDMA/district lists; licence unknown) — do not publish routes to shelters until capacity is sourced.
- **Dredging scenarios**: only honest as sensitivity of channel geometry in S3/S4 (bathymetry not free); label as sensitivity, never as prediction.
- **What-if comparison UI**: commit two scenario folders; side-by-side toggle with a diff raster; acceptance: both scenarios labelled, diff sums to a checkable number.
- **Drainage improvement**: only city-scale (Guwahati municipal network — data not open, unknown); not feasible at state scale.

## 6. Prioritised roadmap

Each step leaves the static product shippable.

1. **Break the mirror recession + state the dry baseline** (drainage-delay rule; UI caption for the S00 1,834 km² channel/clamped baseline). Impact H, Effort S, Data: none (derived), Risk: all committed numbers change → re-run pipeline, update gates. Test: S08 area strictly < S06; `verify:m0` green.
2. **Fix the dead depth term and the Dima Hasao artifact** (depth percentile above 0.5 m; duration contribution capped by area share). Impact M, Effort S, Data: none, Risk: ranking churn. Test: no district with area_share<0.02 in the top 15; depth term varies across districts.
3. **Resolve dead payload**: render or remove the three unfetched P1 files (636 KB). Impact L, Effort S, Risk: budget recalculation. Test: check-data proves every committed file is fetched or explicitly documented as unfetched.
4. **Real rainfall scenario** (IMERG+IMD series committed alongside the synthetic one, both labelled). Impact H, Effort M, Data: IMERG/IMD (free, accounts), Risk: licence/attribution drift. Test: chart shows real mm/day with a provenance entry; synthetic still selectable; honesty gate passes.
5. **CWC gauge hindcast ingest (S1)**. Impact H, Effort M, Data: CWC/India-WRIS, Risk: scrape fragility, datum harmonisation. Test: stage RMSE ≤0.5 m at ≥2 gauges on 2022; station ids in provenance.
6. **30 m DEM (GLO-30/FABDEM) HAND on the valley corridor**. Impact H, Effort M, Data: free, Risk: 9× cells (docs already flag memory, `DATA-PIPELINE.md:125`) → corridor-only. Test: peak extent stays in the V-A4 band; peak delta documented; RSS ≤6 GB.
7. **Sentinel-1 validation harness**. Impact H, Effort M, Data: free (ASF/GEE), Risk: SAR over-vegetation under-detection. Test: automated CSI/IoU report for ≥1 event, committed under `docs/`.
8. **Exposure layer** (WorldPop + OSM roads/bridges/hospitals on peak mask). Impact H, Effort M, Data: free, Risk: ODbL obligations. Test: exposure table renders; honesty gate extended to ban "affected persons" phrasing; per-cell population sums to a checkable total.
9. **Embankment dataset acquisition + overlay** (WRD request; OSM fallback). Impact H, Effort M, Data: request, timeline unknown, Risk: never arrives → ship OSM-only with completeness banner. Test: per-feature source tags; banner present in all views.
10. **Rainfall-runoff sub-catchments (S2)**. Impact H, Effort L, Data: IMERG/IMD/SoilGrids/WorldCover, Risk: equifinality. Test: NSE ≥0.6 at ≥2 CWC stations, 2022; configs committed.
11. **2D corridor hindcast (S4)**. Impact H, Effort L, Data: S2 inflows + section assumptions, Risk: bathymetry uncertainty. Test: CSI ≥0.4 vs Sentinel-1 peak extent, area bias ≤20%, sensitivity run in the report.
12. **Uncertainty product** (P(wet) map replaces the binary mask for the calibrated scenario). Impact M, Effort M, Data: from 10–11, Risk: misread as certainty. Test: reliability diagram vs SAR; UI shows probability legend.

## 7. Non-negotiables

- **Keep the honesty gate and extend it.** Never add "affected", "warning", "safe", "danger level" (except verbatim CWC-published values) without agency-owned data. Prove the extended gate fails on injected data, as `check-honesty.mjs --self-test` does today.
- **Jurisdiction**: warnings are issued only by CWC/IMD/NDMA/ASDMA. Any early-warning feature must name the issuing authority and label itself decision-support, not a warning.
- **The district ranking must not be shipped as a priority list**: the Dima Hasao case (17.8 km² wet, 0.36% share, rank 12 "high") shows how a clean-looking rank misprioritises. Ship it only with area-share, `valid_area_share`, and the scenario-conditional caveat adjacent.
- **No physical claims from artifacts**: until drainage is modelled, `mean_duration_days` is a property of a symmetric scenario, not ponding time; S00's 1,833.9 km² is a channel/clamped baseline, not onset flooding.
- **Licences before operations**: `provenance.json` itself says Esri terms "verify before public launch" — an operational deployment should move to a free-licence basemap or hold a licence; ODbL applies to derived river data; CC BY attribution obligations for WorldCover/WorldPop/geoBoundaries must render in-product.
- **Fix the 78,523 vs 78,220.6 km² denominator mismatch** between `DATA-PIPELINE.md:115` and `flood-summary.json`.
- **Operational failure modes**: keep the dataset-version cache-bust and the tile fallback; add a "data as-of" timestamp and refuse operational display of data older than its cadence.
- **No individual-level data; exposure ≠ vulnerability.** If population enters, the UI must resist equity-blind prioritisation and state OSM/WorldPop completeness limits.
- **The REVIEW-02…14 discipline must survive contact with institutions**: document reversals, never tune a gate to fit a result — that trail is the project's most valuable asset.

session_id: 20261021_201634_eb8c85
  [tool] ◉_◉ contemplating...
EXIT=0
