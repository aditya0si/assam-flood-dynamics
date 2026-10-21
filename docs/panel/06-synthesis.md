# Panel synthesis — Baanh / assam-flood-dynamics, disaster-management review

Compiled by Hermes from four independent model reviews plus a reviewer-run source-verification pass.
Date: 2026-10-21. Repository state: `cf1a835` + review docs; live
`https://aditya0si.github.io/assam-flood-dynamics/`.

## 1. Method

| Panelist | Route | Status | Report |
|---|---|---|---|
| **gpt-6-sol** (chatgpt sol 6, high reasoning) | `openai-codex`, full repo brief | complete | `04-gpt-6-sol.md` |
| **mimo-v2.6-flash** (high) | `opencode-go`, full repo brief | complete | `02-mimo-v2.6-flash.md` |
| **glm-5.3-flash** (high) | `opencode-go`, full repo brief | complete | `03-glm-5.3-flash.md` |
| **minimax-m3.1-flash** (high) | `opencode-go`, bounded brief after a first run exhausted its tool budget | **complete** (19.7 KB) | `01-minimax-m3.1-flash.md` · claims audited in `08-claims-verified.md` |

Deviations, stated plainly:

- **`glm-5.3-flash` is on the Go subscription, not the free Zen tier.** The free Zen models return
  `403 — "free tier can only be used from within OpenCode"` to any non-OpenCode client, and the
  OpenCode CLI on this machine is unauthenticated (`Invalid credential`). Same model family, same
  version; the only difference is which quota pays.
- **`minimax` first run hit its 30-tool-call budget** exploring the repo and produced no report; the
  bounded re-run succeeded and contributed the only *internal* defect findings of the panel — one
  confirmed (inert depth term), one not reproducible (79 % class width), one partial (46.6 % minimum
  AOI coverage). See `08-claims-verified.md`.
- Two of the four briefs pointed at the whole repository, which is why two panelists spent their
  budget on file reads. The bounded brief (§`00c`) is the better template for next time.

## 2. What all three completed reviews agree on

1. **It is a scenario explorer, not a flood information system.** Every panelist independently
   says the product's honesty posture is its strength and its operational emptiness is its limit:
   no observed forcing, no calibrated event, no defence data, no update cycle, no decision authority.
2. **HAND is the right baseline and the wrong destination.** It is defensible as a 90 m screening
   layer; it cannot produce arrival times, velocities, defence effects, or lead time.
3. **Validation must come from Sentinel-1, not from plausibility gates.** All three name held-out
   SAR wet/dry masks with IoU/precision/recall as the first real test. (My probe confirms the data
   is free and reachable: five S1 scenes over Assam for 10–30 Jun 2022, no auth.)
4. **The risk ranking needs an exposure denominator.** Terrain risk without population, roads,
   facilities and cropland is not a disaster-management product. WorldPop/OSM are the cheap path.
5. **Embankments are the decisive missing dataset.** Without crest lines, condition and failure
   modes, "prevention" cannot be modelled honestly — it can only be illustrated. All three treat
   this as a blocker rather than a feature.
6. **Nothing here may become an operational warning surface.** Merge into the existing
   `NOT A FORECAST` posture: Baanh may show what a scenario implies; an authority issues warnings.
7. **The review trail itself is an asset.** mimo put it best: "the REVIEW-02…14 discipline must
   survive contact with institutions — document reversals, never tune a gate to fit a result."

## 3. Where they disagree, and how I adjudicate

| Question | gpt-6-sol | mimo | glm | Adjudication |
|---|---|---|---|---|
| Ambition level | Staged, gated, authority-dependent; refuses to promise | Same spine, adds soil + LGD codes for village joins | Most implementation-forward; names specific libraries and a 50–100 member ensemble | Start from sol's staging, take mimo's **SoilGrids** (verified 200) and **LGD codes**, and defer glm's ensemble until a single-event hindcast exists |
| Stage/discharge data | Treats CWC hydrological data as **classified** under the 2018 policy; requires written release | Free with registration, scrape with rate limits | Uses CWC bulletins with an "approach/archive" caveat | **sol is right and this is the single most important legal finding.** Plan must assume restricted until a written release exists; public bulletins are not a licence |
| DEM upgrade | Copernicus GLO-30, after datum/survey checks | GLO-30 **or FABDEM v2** | FABDEM preferred for HAND stability | Both are free where reachable; **neither `fabdem.org` nor the Bristol data host answered from this machine**, so GLO-30 (Data Space, 200 on catalogue probe) is the primary and FABDEM a later swap |
| 1D/2D hydraulics | HEC-RAS, with explicit calibration gates and candidate thresholds | Same, plus Manning/SCS from land cover and soil | Kinematic/diffusive main-stem routing first, then ensemble | Adopt sol's acceptance metrics as *targets* (stage MAE ≤0.3 m, peak-time ≤6 h, IoU ≥0.65) and mimo's parameter sources; glm's routing step is a reasonable pre-1D experiment |
| Pipeline entry for rainfall | New forcing stage, keep native grid | Per-subcatchment areal means via HydroSHEDS | Merge IMD + IMERG, resample to catchments | Agree: catchment areal means; never interpolate to 90 m and imply measurement |

## 4. Source verification (reviewer-run; the panel had no access to this)

**Survived probing and usable now:** Open-Meteo Flood/GloFAS (200, m³/s), Open-Meteo forecast +
ERA5 archive (200), Sentinel-1 STAC Earth Search (200, 5 Assam scenes Jun 2022), JRC Global Surface
Water, HydroATLAS, WorldPop REST, SoilGrids portal, ASF DAAC, Copernicus Data Space catalogue,
Copernicus EMS Rapid Mapping, Geofabrik India, GES DISC, India-WRIS, CWC FFS, ASDMA, UNOSAT,
geoBoundaries ADM2, NRSC Bhoonidhi, IRI Data Library, Dynamic World.

**Proposed by a panelist but failed here (treat as unverified):**

| Claim | Probe |
|---|---|
| `floodforecast.india-ris.org` (glm) | DNS does not resolve |
| `dataportal.imd.gov.in` (mimo) | DNS does not resolve |
| `fabdem.org`, Bristol data host (mimo, glm) | DNS / connection reset |
| Global Dike Database article URL (mimo) | 404 (wrong article ID) |
| ISRIC WCS endpoint (implied by SoilGrids) | connection failed |
| Copernicus CDS `api/v2` (glm) | 404 — API moved |

**Measured trap — GloFAS coordinate snapping.** A lat/lon query returns the nearest GloFAS *river
cell*, not the Brahmaputra. At five Assam coordinates the medians were 0.1, 8.8, 104.2, 11.5 and
0.8 m³/s — tributary/headwater cells, orders of magnitude below the main stem. Any "use GloFAS for
the Brahmaputra" plan must select the reach by upstream area or anchor on gauges.

## 5. The gap, in one table

| Capability | Today | A district officer needs | A state EOC needs | NDMA analyst needs |
|---|---|---|---|---|
| Forcing | synthetic 12-step stage | observed rain + named gauge with datum | cross-district feeds, latency, health | archived events, model versions |
| Model | HAND threshold | reach-specific stage, defence effects | uncertainty, ensembles | validation by event and lead time |
| Exposure | district terrain score | villages, roads, shelters, accessible routes | cross-district resource picture | loss statistics, comparable events |
| Action | none | thresholds, evacuation routes, closures | escalation/approval record | intervention comparison |
| Provenance | strong (source→stage→file) | same + data age per layer | feed-health monitoring | audit trail, reproducible runs |

## 6. Compiled plan

See `07-plan.md` for the full phase plan with acceptance tests. In one line each:

- **Phase 1 — Real data, same model (2–3 weeks).** Sentinel-1 event masks + Open-Meteo/ERA5 rainfall
  + GLO-30 DEM swap + WorldPop/OSM exposure. Ship an **IoU/precision/recall scorecard** for the
  existing HAND model on June 2022. The product stops being unvalidated.
- **Phase 2 — Hydrology (3–5 weeks).** Catchment areal rainfall → rating curves → 1D main-stem
  routing on a gauged reach; rainfall–runoff where the data permits. Target held-out stage MAE
  ≤0.3 m, peak timing ≤6 h. Refuse to publish a "forecast" until this passes.
- **Phase 3 — Prevention what-if (3–4 weeks).** Embankment crest scenarios (only where an authorised
  crest dataset exists), retention/dredging toggles, land-cover change; every intervention compared
  against a frozen baseline with the same metrics and uncertainty band.
- **Phase 4 — Decision surface (4+ weeks).** Thresholds with measured lead times, evacuation routing
  on a verified network, shelter capacity, shadow-mode drills with an agency. Governance first.

## 7. Non-negotiables (merged, deduplicated)

1. Separate synthetic, derived, modelled and observed in every label, export and legend, with a
   **data-age timestamp** per layer.
2. Never convert an internal plausibility band into a skill claim; publish misses and false alarms,
   not just peaks.
3. Do not publish or redistribute restricted CWC/NRSC/CWC-bulletin material because it is viewable.
4. Preserve native resolution, vertical datum, acquisition time, licence and source version.
5. Show missing and stale sensors rather than interpolating them away.
6. No warning, evacuation instruction or "safe route" label without an accountable authority and an
   audit trail.
7. Keep the review discipline: when a gate is wrong, withdraw it in writing with the measurement
   that disproved it — the pattern already used in `docs/REVIEW-02…13`.
