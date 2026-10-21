# Independent review panel — Baanh / assam-flood-dynamics

You are one of four independent reviewers, each a different model, contributing to a single
synthesis. Do not assume the others' opinions; give your own, with evidence.

## The artifact

Repository: `C:/Users/oliad/Desktop/baanh` (public: `github.com/aditya0si/assam-flood-dynamics`)
Live: `https://aditya0si.github.io/assam-flood-dynamics/`

Read at least: `README.md`, `docs/ARCHITECTURE.md`, `docs/DATA-PIPELINE.md`,
`docs/MILESTONES.md`, `docs/M0-REPORT.md`, `docs/REVIEW-01…14` (skim for what was rejected and
why), `pipeline/` (stage modules), `src/` (map, panels, timeline, charts, state), and the data
contracts in `public/data/{manifest.json,flood/flood-summary.json,flood/frame-index.json,risk/*}`.

What it is today, in one line: a static Vite/React/MapLibre scenario explorer that derives flood
extent from a DEM-based HAND screening model over Assam, with 12 synthetic monsoon steps, a district
risk ranking, provenance/methodology panels, and an explicit "NOT A FORECAST" posture.

## What we want from you

Produce a markdown report, **≤2500 words**, with exactly these sections:

1. **Current state, as built** — what it genuinely is (cite paths/numbers), what is strong, what is
   weak. Distinguish "good for a portfolio" from "good for a real disaster-management user".
2. **Gap analysis against a real disaster-management system** — capabilities, data, model, ops,
   user roles, UX. What would a district duty officer, a state emergency operations centre, or an
   NDMA analyst need that this does not have?
3. **Real data integration plan** — for each dataset: name, provider, URL, licence, spatial
   resolution, temporal cadence, the variables it contributes, and how it would enter the pipeline.
   Cover at minimum: rainfall (gauge + satellite), river stage/discharge, DEM/bathymetry, SAR flood
   extent for calibration, administrative boundaries, population, roads/critical infrastructure,
   embankments/levees, land use. Say plainly which are free and which are not, and which are not
   available for Assam at usable resolution.
4. **Simulation upgrade path** — from HAND screening to what, concretely: rainfall-runoff,
   rating curves, 1D/2D hydrodynamic routing, breach modelling, ensembles and uncertainty, or a
   staged hybrid. For each stage say what it buys, what it costs, and how it would be validated
   (metrics, reference events, data needed). Be specific about numeric expectations (resolution,
   timestep, calibration targets).
5. **Prevention and mitigation features** — what the product would need to *show prevention*:
   embankment/bund scenarios, dredging, retention areas, land-use change, drainage, early-warning
   thresholds and lead time, evacuation routing and shelter capacity, what-if comparison, and
   who acts on it. Keep each feature tied to data that can actually be obtained.
6. **Prioritised roadmap** — 10–12 items, each with: impact (H/M/L), effort (S/M/L), data
   dependency, risk, and a one-line acceptance test. Order them so each step leaves the product
   shippable.
7. **Non-negotiables** — honesty, ethics, and failure modes to guard against when this stops being
   a portfolio piece and starts being used for real decisions.

## Rules

- **Read-only.** Do not edit, create, or delete any file. Do not run git commands that mutate state.
  You may read files, grep, and run read-only shell commands.
- Cite repository paths (and line numbers where it matters) and quote real numbers from the data.
- Do not invent datasets, providers, statistics, or capabilities. If you do not know, write
  **unknown**.
- Prefer concrete, checkable statements over adjectives. A recommendation without a data source or
  an acceptance test is not a recommendation.
- Assume a reviewer will try to falsify every claim you make.
