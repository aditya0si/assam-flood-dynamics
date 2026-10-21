Six files read (README, ARCHITECTURE §1–4/§7/§11/§12, verification ledger, flood-summary.json, district-risk.json, hand.py) plus targeted recomputation of the risk score from the committed file. Read-only; nothing executed against the build, so the `check-data 24/24` and `Playwright 10/10` figures in the brief remain inherited claims I did not re-verify.

REPORT — BAANH INDEPENDENT REVIEW (tool-budgeted variant)

1. CURRENT STATE, AS BUILT

Baanh is a static Vite/React/MapLibre explanatory scenario explorer with a real Python geospatial pipeline behind it. The strongest thing about it is not the map; it is that the honesty contract is executable. `scripts/check-honesty.mjs` has a self-test that injects `casualties`, `deaths`, `displaced`, `affected_persons`, `incident_id`, `agency_id`, `relief_camp`, `unqualified forecast`, `warning issued` and must fail on each (README.md:63-67), and `scripts/check-data.mjs` re-derives wet-cell counts and area from a real PNG decode rather than trusting metadata. That is rarer than it should be.

The science is honest about its own weakness. HAND is computed by exact EDT on a burned DEM at 90 m, EPSG:32646 (`pipeline/src/baanh_pipeline/hand.py:47-61`), negatives clamped, cells beyond `max_channel_distance_m` set to nodata, and stage 08 hard-fails when valid HAND share falls under a floor (hand.py:114-118). The peak is S07, 25 Aug, stage 3.70 m = mainstem 2.11 + backwater 1.59, area 10,010.6411 km², 1,238,659 wet cells, median depth 2.354 m, p95 3.7 m (`public/data/flood/flood-summary.json`, S07 entry). Shares: 12.80% of Assam (78,220.613 km²), 32.24% of the 31,050 km² flood-prone belt, 19.16% of AOI v2 (52,240.748 km²).

Where it is weak, measurably: the risk score is weaker than the README implies. The 20% depth term is a constant. Every one of the 33 districts has `p90_peak_depth_m` = 3.7 exactly, because the bathtub model clamps depth at the peak stage; so the depth term contributes an identical 18.5 points to every district and changes no rank. I reconstructed the formula from the committed file (100·[0.45·min(area/0.6,1) + 0.35·min(duration/90,1) + 0.20·min(3.7/4,1)]) and it reproduces all 33 scores to <0.02; deleting the depth term reproduces the identical top 5 and bottom 3. The effective ranking is area56% / duration 44% of the varying part. Separately, the score spread is only 39.598–71.944 and the class bands put 26 of 33 districts in `high` — one bucket holds 79% of the state. And `counts.no_data` is 0 while six districts have `valid_area_share` under 0.95, three of them badly so (Dima Hasao 0.466, Karbi Anglong East 0.558, Karbi Anglong West 0.580) — hill districts where HAND is undefined because there are no mapped channels. They receive numeric scores with no coverage caveat.

One documentation drift: `docs/ARCHITECTURE.md:6` still says "Application code is deliberately absent" while `src/` and `pipeline/` are populated; the spec is stale relative to the build.

Good portfolio: yes, unambiguously. Real DEM, real boundaries, real OSM rivers, a documented model with named limits, a versioned dataset (2026.10.0), SHA-256 manifest, budget gates, offline degradation, and a refusal to ship fabricated operational fields. Good for a disaster-management user: no. It has no live data, no gauge, no warning product, no population, no facility exposure, no route or shelter analysis, and by design (ARCHITECTURE.md:40-41) is not for an emergency responder. The README and ARCHITECTURE say this plainly; the risk is that a screenshot of S07 in a deck reads as "flood map" without the caveat travelling with it.

2. GAP ANALYSIS VS A REAL DISASTER-MANAGEMENT SYSTEM

District officer (Deputy Commissioner, one district): needs the *current* water level at their gauge(s) and a lead time in hours; which mauzas are cut off today; where relief camps are and their capacity; which roads are passable. Baanh supplies none of these: the hydrograph is synthetic, there is no live adapter, no camp dataset exists in any probed source, and passability needs a routable road network with a water overlay. What they can use is the cross-section and the inundation-depth field for explaining mechanism to a public meeting — teaching tool, not decision tool.

State EOC: needs a common operating picture across districts — one consistent picture at a common timestamp, a district-to-district comparison, the ability to move a shared scenario, and a live feed with latency and provenance. Baanh is a single synthetic composite with no ingest path and no multi-event capability (ARCHITECTURE.md:95, P2-04). The state EOC's actual first question is "what did the CWC forecast say for Dibrugarh at 06:00 today" and Baanh answers nothing to it.

NDMA analyst: needs calibrated hydraulics, multi-event benchmarking, and defensible error bars — "what was our IoU against the June 2022 SAR extent, and what is the error band for 2030 planning?". Baanh has no observed event to validate against and no error characterisation at all. Its only external check is a plausibility band of 4,000–12,000 km² that `flood-summary.json` itself labels "chosen by the reviewer from REVIEW-02; it is not a calibrated observation". A band chosen after seeing the result cannot validate the result.

Common structural gap: every number is a scenario-conditional terrain exposure. Nothing is an observation, and nothing carries an uncertainty estimate.

3. REAL DATA INTEGRATION PLAN

Every row below is either (a) in the verification ledger's §1 working keyless list, or (b) explicitly marked unprobed-by-ledger. Licence text is stated conservatively from provider terms, not from a probe.

- Rainfall, satellite: GPM IMERG, NASA GES DISC, https://disc.gsfc.nasa.gov/ — free, Earthdata account required. 0.1° / 30-min. Cadence: near-real-time product latency hours. Vars: precipitation rate, total. Entry: new stage replacing `build-series` rainfall input; keep `build-series` for the synthetic series as a parallel, separately-labelled product.
- Rainfall, gauge/reanalysis: Open-Meteo archive (ERA5) + forecast, https://archive-api.open-meteo.com/v1/archive and https://api.open-meteo.com/v1/forecast — free, keyless, non-commercial tier, attribution required. ~9-25 km, hourly/daily. Entry: same as above, as an OBSERVED/REANALYSIS class series beside SYNTHETIC.
- River discharge (model): GloFAS via Open-Meteo Flood API, https://flood-api.open-meteo.com/v1/flood — free, keyless; m³/s, 30 past + 7 forecast days. Entry: 1D routing stage. CAUTION (ledger §3): lat/lon snapping gave median 0.1 m³/s at Majuli main stem, 0.8 at Guwahati, 8.8 at Dhubri, 104.2 in Upper Assam — these are tributaries/headwaters. Discharge must be selected by upstream area or GloFAS river ID, never by point proximity.
- River stage (authoritative): India-WRIS https://indiawris.gov.in/wris/ and CWC FFS https://ffs.india-water.gov.in/ — probed200; account/registration for bulk products; terms vary by product. Vars: AWLR/RL stage, daily mean/max. Entry: rating-curve + validation stage.
- SAR extent (the one real validation lever): Sentinel-1 GRD via Element 84 Earth Search STAC, POST https://earth-search.aws.element84.com/v1/search — free, no auth, keyless. 10 m, 12-day revisit (6-day with two-constellation in practice; treat as ~12). Ledger §4 already returned 5 scenes for bbox [92.0,25.5,95.5,27.5] over 2022-06-10/30, so the June 2022 Assam event is reachable today. Entry: `build-obs-extent` (new) → held-out validation harness.
- Long-term surface water: JRC Global Surface Water https://global-surface-water.appspot.com/ — free, 30 m, monthly 1984-2021. Entry: static water-occurrence layer. It stops in 2021, so it cannot validate 2022 or later; do not present it as current.
- DEM: already AWS Terrarium via `fetch-terrain`/`build-dem`. Alternative 30 m ASTER/SRTM not needed at 90 m analysis resolution.
- Bathymetry: UNKNOWN / effectively unavailable. No probed source carries Brahmaputra or Barak bathymetry; commercial and survey-office products are restricted. Consequence: no true conveyance modelling, no bathymetric dredging effect.
- Embankments / bunds: OSM via Geofabrik extract, https://download.geofabrik.de/asia/india.html — free, ODbL, keyless, whole-state, and replaces flaky Overpass (ledger §2: 502 on one probe). Vars: `embankment`, `waterway=river`, `levee`, bund lines. Crest levels, heights and condition: UNKNOWN / restricted — no public structured inventory was found in any probed source. This is the single biggest blocker for prevention features.
- Population: WorldPop REST https://www.worldpop.org/rest/data/pop/wpgp?iso3=IND — free, keyless, ~100 m, annual rasters, ODbL. Entry: exposure stage joining the peak mask.
- Roads and facilities: OSM via Geofabrik (free, ODbL, keyless) — highway geometry, hospitals, schools, clinics, shelters (as POI presence, not capacity). Entry: `build-assets`.
- Land cover: ESA WorldCover10 m — free, non-commercial-permissive, but NOT probed by the ledger; verify before relying on it. Entry: land-use-change scenario stage.
- Catchment/runoff attributes: HydroSHEDS/HydroATLAS https://www.hydrosheds.org/products/hydroatlas — probed 200; free for non-commercial research, commercial needs a licence. Vars: upstream area, Strahler order, basin slope — these are also the correct way to disambiguate GloFAS reaches. Entry: routing stage (upstream area for reach selection).
- Event extents and humanitarian products: UNOSAT https://unosat.org/products/ and Copernicus EMS Rapid Mapping https://rapidmapping.emergency.copernicus.eu/ — probed 200; activation-based, not continuous; product-level terms apply.
- State bulletins: ASDMA https://asdma.assam.gov.in/ — probed 200; machine-readable licence unknown, bulletins are human-readable.

What is restricted or unavailable for Assam, plainly: discharge time series at the resolution a district officer needs (many CWC products restricted or registration-gated); rating curves for many gauges (UNKNOWN whether published); embankment crest level and condition (UNKNOWN, likely restricted); bathymetry (effectively unavailable); shelter capacity, relief-camp occupancy, evacuation-route authority (no structured public source). Do not plan around these.

4. SIMULATION UPGRADE PATH

Stage A — rainfall-runoff (from synthetic series to a driven hydrograph): SCS-CN or GR4J per sub-basin from HydroATLAS attributes plus IMD/GPM rainfall. Buys a non-arbitrary timing and a defensible rainfall-to-stage lag. Costs: S/M. Validates against CWC/ASDMA stage at two or more gauges, target RMSE ≤ 0.30 m over the synthetic horizon and ≤ 0.50 m for the June 2022 held-out period — target, not measurement.

Stage B — rating curves: stage↔discharge per gauge from observed pairs. Buys the ability to report discharge and to compare like with like across products. Costs S. Fails closed if fewer than two gauges yield a usable curve; the product then keeps reporting stage only.

Stage C — 1D routing (Muskingum or diffusive-wave) along the main stem and tributaries, using GloFAS/HydroATLAS reach selection and terrain channel profiles. Buys backwater, attenuation, and travel time — the causal chain the current product asserts but does not compute. Costs L (HEC-RAS is free but heavy to automate; LISFLOOD-FP is open source and is the realistic choice). Validation: gauge stage RMSE ≤ 0.30 m at ≥2 gauges on the June 2022 window.

Stage D — 1D/2D coupled (LISFLOOD-FP or TREX on the AOI). Buys depth-field realism: wetting front, velocity, and non-uniform depth, which fixes the constant-3.7 m p90 that currently makes the depth term inert. Costs L. Validation: IoU ≥ 0.55 and F1 ≥ 0.75 against the Sentinel-1 June 2022 mask (ledger §4 gives 5 usable scenes). Numeric targets must be set before the run, in the repo, or they will be fitted to the result.

Stage E — embankment breach: only after a verified crest-level inventory exists; until then it can be a parameterised, clearly-hypothetical mechanism. Buys the answer a district officer actually asks ("what if the bund at 94.2 E overtops?"). Costs M, blocked on data.

Stage F — ensembles: ≥50 members with perturbed rainfall hyetograph and stage. Buys a defensible range instead of a single number, which is what "risk" means operationally. Costs M. Target: ≥80% of members within ±20% of the median peak area; report the band, never the median alone.

Validation discipline: fix the June 2022 SAR scenes as held-out before any tuning; keep the 2022 event out of calibration; report IoU/precision/recall per scene with the scene IDs.

5. PREVENTION AND MITIGATION FEATURES

Each is tied to data that exists or does not.
- Embankment/bund scenarios: mechanism can ship now as a toggleable per-segment crest elevation with a HYPOTHETICAL class badge; real crest data is restricted/unknown. Ships the interaction without claiming real bunds.
- Dredging: no bathymetry, so ship as a conveyance-sensitivity slider in the 1D model (e.g. ±10% conveyance), labelled a sensitivity, not a bathymetric edit.
- Retention/pond storage: DEM (have, 90 m) + land cover + OSM waterbody polygons are sufficient. Realistic, low risk.
- Land-use change: two land-cover epochs; only after WorldCover or an equivalent is probed.
- Drainage: urban drainage network data is unavailable; do not build this.
- Early-warning thresholds and lead time: needs CWC FFS, which is a forecast product. Shipping it inside Baanh converts the product's identity, creates automation/licence questions on FFS data terms, and collides with the honesty gate. Recommendation: keep thresholds scenario-conditional as today, and if lead time is ever added, isolate it in a separate module with its own licence review.
- Evacuation routing: road network from Geofabrik is available; shelter POIs are available as presence only; capacity is restricted. Ship "road accessibility under the modelled depth" — a network graph where edges below threshold are cut — explicitly not an evacuation plan.
- What-if comparison: cheapest, highest-value, needs no new data. The pipeline already produces per-step area; a second scenario branch produces a delta table. This is the feature that most directly serves a district officer.

6. PRIORITISED ROADMAP

1. Held-out SAR validation harness (Sentinel-1, June 2022). Impact H, effort M, dep: keyless STAC. Risk: the model may score poorly — that is the point, and the number must be published. Acceptance: `npm run validate:sar` prints IoU/precision/recall per scene ID and CI fails below IoU 0.55; README quotes the measured number.
2. Fix the risk score: depth dispersion, and an insufficient-coverage class. Impact H, effort S, dep: none. Acceptance: `district-risk.json` shows `counts.no_data` ≥ 6 for the six districts with `valid_area_share` < 0.95, and either distinct p90 depths for ≥10 districts or the depth weight set to 0 with a documented reason; `check-data` still passes24/24 and the UI shows the coverage caveat.
3. Migrate OSM ingest from Overpass to Geofabrik. Impact M, effort S, dep: keyless. Acceptance: river and facility builds succeed with zero Overpass calls and the committed river file is byte-identical or the diff is explained.
4. Population exposure (WorldPop 100 m). Impact M, effort S, dep: keyless. Acceptance: district table adds a scenario-conditional population-exposed column with a ±25% grid caveat; the honesty self-test still rejects all 9 injected strings.
5. What-if comparison (baseline vs branch, area/depth delta table). Impact M, effort S, dep: none. Acceptance: user can load a second scenario and the table shows Δarea and Δdepth per district; CI e2e covers the flow.
6. Asset exposure from OSM (hospitals, schools, clinics) with an explicit completeness caveat. Impact M, effort S, dep: Geofabrik. Acceptance: panel lists facilities with peak depth and states "OSM incomplete"; no count presented as a total.
7. Road accessibility graph under modelled depth. Impact M, effort M, dep: OSM. Acceptance: at S07 the map cuts edges below the depth threshold and shows a per-district count of cut links, labelled scenario-conditional.
8. Real-event observation layer (Sentinel-1 SAR extent) as a distinct OBSERVATION class, never mixed into the synthetic animation. Impact H, effort L, dep: STAC + radiometric processing (terrain correction, speckle, threshold). Acceptance: a separate toggle labelled OBSERVATION with the scene date and product id; the honesty gate rejects any merge of OBSERVATION and SCENARIO frames.
9. Rating curves and 1D routing (Stage B+C). Impact H, effort L, dep: CWC/ASDMA stage, GloFAS reach selection, HydroATLAS. Risk: gauge availability may not clear the two-gauge floor. Acceptance: routing runs only if ≥2 gauges yield a curve; otherwise it stays off with a stated reason; gauge RMSE reported in the build output.
10. Documentation honesty refresh. Impact M, effort S, dep: none. Acceptance: a CI grep fails if `docs/ARCHITECTURE.md` retains "Application code is deliberately absent" or any doc asserts a status contradicted by the tree.

Each step above leaves the site shippable: none removes a shipped capability, and steps 1–3 only add evidence.

7. NON-NEGOTIABLES

- Every synthetic number keeps a SYNTHETIC/SCENARIO/DERIVED badge at the point of use, not only in the README. Enforce in the UI, not just in JSON.
- Never let a scenario-conditional population figure drift into impact semantics. "Population exposed under scenario S07" is defensible; "people affected" is not. The honesty gate's banned strings are the floor, not the ceiling — extend it when a new field lands.
- Observations, reanalysis and synthetic series never share a layer, a legend, or a colour ramp. The moment a SAR extent and a modelled extent can be read as the same object, the product becomes a forecasting tool by accident.
- The GloFAS reach-selection trap must be encoded, not remembered: no discharge figure without reach ID / upstream area, and a CI test that fails if a GloFAS value is attached to a coordinate-selected cell. The0.1 m³/s at Majuli main stem is exactly the error a reviewer will look for.
- Never present the 4,000–12,000 km² plausibility band as validation. It was chosen post hoc by a reviewer, and `flood-summary.json` says so; keep that caveat next to the band in the UI.
- Offline degradation is a safety property, not a nicety: when both tile hosts fail, the committed relief and local frames must still render with the `NOT A FORECAST` badge, and an empty map must never be shown (it reads as "no flood here"). The blocked-tile Playwright spec is the guard.
- No person-level data, ever. If relief-camp or shelter data is ever obtained, aggregate at district and publish a coverage statement.
- Keep the refusal to ship fields it cannot source. A field that would be empty is worse than an absent field, because it advertises capability.

Bottom line: Baanh is a well-disciplined, honestly-labelled teaching artefact with a real pipeline, and its most serious internal defect — an inert depth term, a single 79 %-wide risk class, and unscored low-coverage hill districts — is fixable in a day with no new data. It becomes a credible operational prototype only after item 1 (SAR held-out validation) and item 9 (rating curves + 1D routing) land, and it becomes an operational tool only when live gauge data, embankment crest data and shelter capacity are obtainable — which, on present probing, they are not.

session_id: 20261021_203325_5543f9
EXIT=0
