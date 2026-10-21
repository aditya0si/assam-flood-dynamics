# Independent review panel — Baanh (bounded variant)

You are one of four independent reviewers contributing to one synthesis. This variant is
**tool-budgeted**: you have limited turns, so do not explore the whole repository.

## Budget

- Read **at most 6 files**, then write your report.
- Do **not** run long greps or recursive listings.
- Target ≤1800 words. Depth of judgement matters more than breadth of reading.

## Read these first (in order, stop when you have enough)

1. `README.md`
2. `docs/ARCHITECTURE.md` (sections 3, 4, 7, 11)
3. `docs/panel/05-verification-ledger.md` — sources the reviewer actually probed; treat anything
   outside it as unverified
4. `public/data/flood/flood-summary.json` (top-level totals + the S07 entry)
5. `public/data/risk/district-risk.json` (weights + top three districts)
6. One of: `pipeline/src/baanh_pipeline/hand.py` or `src/map/flood.ts`

## The artifact in one paragraph

Static Vite/React/MapLibre scenario explorer for Assam floods. A Python pipeline derives flood
extent from a DEM-based **HAND screening model** (height above nearest drainage, 90 m, EPSG:32646),
applied at 12 synthetic monsoon stages peaking at 3.70 m, producing 10,010.6 km² of modelled
inundation (12.8 % of Assam, 32.2 % of the flood-prone belt), a 33-district risk ranking
(Sivasagar 71.9 top; 45 % area + 35 % duration + 20 % depth), raster depth frames, provenance and
methodology panels, an explicit "NOT A FORECAST" posture, and executable gates
(`check-data` 24/24, budget, honesty, Playwright 10/10 in CI). Live:
`https://aditya0si.github.io/assam-flood-dynamics/`.

## Your report — exactly these seven sections, ≤1800 words

1. **Current state, as built** — what it genuinely is; strong vs weak; separate "good portfolio"
   from "good for a disaster-management user".
2. **Gap analysis vs a real disaster-management system** — district officer / state EOC / NDMA
   analyst; what each needs that this lacks.
3. **Real data integration plan** — per dataset: provider, URL, licence, resolution, cadence,
   variables, pipeline entry. Cover rainfall (gauge + satellite), river stage/discharge, DEM,
   bathymetry, SAR extent, population, roads/facilities, embankments, land cover. Mark clearly what
   is free, what needs an account, and what is **restricted or unavailable** for Assam.
4. **Simulation upgrade path** — from HAND screening to rainfall-runoff, rating curves, 1D and
   1D/2D routing, breach modelling, ensembles; what each buys, costs, and how it is validated
   (metrics, held-out events, numeric targets).
5. **Prevention and mitigation features** — embankment/bund scenarios, dredging, retention, land
   use, drainage, early-warning thresholds and lead time, evacuation routing and shelter capacity,
   what-if comparison — each tied to obtainable data.
6. **Prioritised roadmap** — 8–10 items with impact (H/M/L), effort (S/M/L), data dependency, risk,
   and a one-line acceptance test; each step must leave the product shippable.
7. **Non-negotiables** — honesty, ethics, and failure modes to guard against.

## Rules

- **Read-only:** no edits, no state-changing git commands.
- Cite repository paths; quote real numbers.
- Do not invent datasets, providers or statistics. Write **unknown** where you do not know.
- A recommendation without a data source or an acceptance test is not a recommendation.
- Assume a reviewer will try to falsify every claim.
