# Plan — from scenario explorer to disaster-management simulation

Derived from `06-synthesis.md` (three completed model reviews + reviewer verification). Every task
below is small enough to finish and verify, and every phase leaves the product shippable.

**Rule that governs the whole plan:** no phase may depend on a dataset that has not been probed from
this machine and recorded in `05-verification-ledger.md`. Restricted data is a *procurement* task,
not an engineering task.

---

## Phase 1 — Real data, same model (the product stops being unvalidated)

**Goal:** the existing HAND model gets scored against observed water, and the synthetic rainfall
series is replaced by observed rainfall. Effort: 2–3 weeks.

| # | Task | Files / surface | Acceptance test |
|---|---|---|---|
| 1.1 | **Sentinel-1 event catalogue.** STAC search `earth-search.aws.element84.com` for `sentinel-1-grd`, bbox 92.0/25.5/95.5/27.5, Jun–Jul 2022; download 3 scenes; derive water masks (VV threshold + permanent-water subtraction) | `pipeline/calibration/s1.py`, artefacts in `pipeline/calibration/2022-06/` (not shipped) | ≥3 scenes downloaded, masks reprojected to the 90 m EPSG:32646 grid, each with acquisition timestamp |
| 1.2 | **Validation scorecard.** Score the current HAND frames against the closest S1 mask: IoU, precision, recall, and area bias; write JSON | `public/data/validation/scorecard.json` via new pipeline stage | `check-data` validates the schema; the numbers reproduce from the committed inputs |
| 1.3 | **Observed rainfall.** Open-Meteo archive (ERA5) + forecast, catchment areal means over HydroSHEDS sub-basins | new `pipeline/src/baanh_pipeline/forcing.py`, `public/data/series/rainfall-observed.json` | every value carries source + timestamp; native grid resolution stated, never resampled to 90 m and called measured |
| 1.4 | **DEM upgrade path.** Copernicus GLO-30 (account) as the target; keep Terrarium as fallback; re-derive HAND | `pipeline` stage 01/04 | HAND distribution shift documented; pipeline still ≤10 min; both DEMs versioned in provenance |
| 1.5 | **Exposure layer.** WorldPop 100 m + OSM hospitals/schools/roads joined to the peak mask | `public/data/exposure/*.json` | counts labelled *potentially exposed residents*, never "affected"; aggregation back to source cells reproduces the total |
| 1.7 | **Severity beside extent.** Per-district `severity_index` (depth>1.5 m share × median depth × duration, normalised) published alongside the extent-led score; both labelled, no composite | Risk panel shows both ranks; Dima Hasao ranks high on severity, low on extent (measured: 0.882 depth share, 3.7 m median, 114.7 d, yet 44.1 on extent) |
| 1.6 | **UI: OBSERVED vs SCENARIO vs DERIVED.** New class badge, per-layer data-age, and a Validation panel that shows the scorecard with its misses | `src/panels/ValidationPanel.tsx` | Playwright: badge present on every data surface, age visible, scorecard renders numbers from JSON |

**Exit criterion:** a reviewer can open the app, read "HAND screening scored IoU 0.xx against
Sentinel-1 on 28 Jun 2022", and see the rainfall series marked observed.

---

## Phase 2 — Hydrology (the model starts explaining the flood, not just the terrain)

**Goal:** stage comes from water balance and routing, not from a hand-set curve. Effort: 3–5 weeks.
**Depends on:** Phase 1. D-1's status below decides how much is possible.

| # | Task | Acceptance test |
|---|---|---|
| 2.0 | **Data-access decision.** Request written release for CWC gauge stage/discharge (sol's finding: Brahmaputra–Meghna data is generally classified). Until granted, use Open-Meteo GloFAS **with reach selection by upstream area**, never nearest-cell | A written licence/refusal on file; `provenance.json` names the permitted use |
| 2.1 | **Rating curves.** Stage–discharge per reach from permitted gauges or published FFS tables | curves stored with datum + version; a test rejects mismatched datums |
| 2.2 | **Rainfall–runoff** for 2–3 gauged sub-catchments (GR4J/HBV class), hourly forcing | volume bias ±20 %, peak timing ≤6 h on one event, held out on a second |
| 2.3 | **1D routing** on the main stem (kinematic/diffusive wave, then HEC-RAS if a survey exists) | held-out stage MAE ≤0.3 m, peak-time error ≤6 h |
| 2.4 | **Uncertainty band** from ensemble rainfall/roughness (start at 20 members, not 100) | UI shows p10/p50/p90 extent, and where members disagree |
| 2.5 | **Forecast language gate** in CI: no string containing "forecast" without a qualifying label | `check-honesty` extended; a deliberate violation fails the build |

**Exit criterion:** one historical Assam event is hindcast end-to-end and scored against both the
gauge and the S1 mask, with the misses published.

---

## Phase 3 — Prevention and mitigation (the "what if we had…" surface)

**Goal:** interventions become comparable experiments, not illustrations. Effort: 3–4 weeks.

| # | Task | Acceptance test |
|---|---|---|
| 3.0 | **Embankment data procurement.** Request WRD scheme records (alignment, crest, condition). If refused, build the feature with **declared hypothetical crests** in a separate "hypothetical" namespace | either an authorised dataset in provenance, or every hypothetical crest visibly labelled |
| 3.1 | **Scenario editor.** Raise/lower crest, add a breach (location, width, time), open/close a sluice, add retention storage | editing a scenario never mutates the baseline; both persist in the URL/session |
| 3.2 | **Comparison view.** Frozen baseline vs intervention: depth delta, duration delta, exposed population delta, with the uncertainty band | delta reproducible from stored inputs; "no change" is a valid, displayed result |
| 3.3 | **Breach module** with explicit parameters and a stated trigger range | a test asserts the model refuses to run a breach with missing crest elevation rather than inventing one |
| 3.4 | **Dredging / land-use experiments** gated behind repeated-survey or scenario labels | each carries its own data-source line and confidence |

**Exit criterion:** a reviewer can ask "what does +1 m of crest on this reach buy?" and get a number
with an uncertainty band, or an explicit "cannot be estimated with the data held".

---

## Phase 4 — Decision surface (only with an accountable partner)

**Goal:** the product becomes usable in a drill. Effort: 4+ weeks, mostly non-engineering.

| # | Task | Acceptance test |
|---|---|---|
| 4.1 | Thresholds mapped to **observed** levels with measured historical lead time | each threshold shows hits, misses and false alarms from past events |
| 4.2 | Evacuation routing on a verified network with shelter capacity; unverified edges labelled **unknown**, never "safe" | a drill walkthrough with a district officer, logged |
| 4.3 | Feed-health monitor: per-source age, error rate, last-success | stale feed visibly degrades the UI rather than silently interpolating |
| 4.4 | Audit trail: model version, inputs hash, who saw what when | run reproducible from the audit record |
| 4.5 | Shadow-mode drills with rollback, stale-feed and manual-override tests | signed drill record before any public "operational" badge |

**Exit criterion:** an agency signs a drill, not a launch.

---

## Sequencing and effort

| Phase | Duration | Ships | Depends on |
|---|---|---|---|
| 1 | 2–3 wk | validated HAND + observed rainfall + exposure + validation panel | S1 (free), Open-Meteo (free), WorldPop (free), GLO-30 (account) |
| 2 | 3–5 wk | routed stage + ensemble band + forecast-language gate | Phase 1; CWC release *or* GloFAS reach selection |
| 3 | 3–4 wk | intervention comparison + breach module | WRD crest data *or* hypothetical namespace |
| 4 | 4+ wk | thresholds, routing, drills | partner + governance |

## First 10 working days (concrete)

1. `pipeline/calibration/s1.py` + three June 2022 masks on the analysis grid.
2. Scorecard JSON + `ValidationPanel` + CI schema check — this is the single highest-value change:
   it converts "plausible" into "measured".
3. Observed rainfall series from Open-Meteo archive, catchment-aggregated, with provenance.
4. Write the data-access register: every dataset, licence, retrieval date, permitted use, and the
   three that need a letter (CWC gauge series, WRD embankments, NRSC products).
5. Add the `OBSERVED` badge and per-layer data-age to the UI.
6. Deploy; update `M0-REPORT` with the scorecard numbers — including a bad IoU if that is the truth.

## What not to do

- Do not put a 2D hydrodynamic solver in the browser. Route and solve offline; the app displays results.
- Do not call GloFAS "Brahmaputra discharge" without reach selection — measured: 0.1–104 m³/s at
  Assam coordinates, which is tributary flow.
- Do not scrape CWC/NRSC products into public artifacts, however visible they are in a browser.
- Do not build the "prevention" UI before crest data, or it becomes an animation of an opinion.
- Do not add a second event until the first one is scored.
