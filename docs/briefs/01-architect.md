# Architect brief — Baanh (Assam Flood Dynamics Analysis)

You are the **architect** for a new single-page web product. Your deliverable is the
specification set that a separate builder will implement, not application code.
Read `docs/reference-analysis.md` first: it contains the verified feature inventory of the
reference product (FireTrace) and the verified data sources, plus the honesty rules.

## Mission

Design a browser-based **flood dynamics analysis dashboard for Assam, India** that explains
how a Brahmaputra floodplain flood develops: monsoon rainfall → rising main stem and tributaries
→ backwater into low-lying land → inundation spread over time → which districts and assets are
at risk. Time-animated 3D terrain, risk zoning, scenario water levels, and a synchronous
analytics dock. Everything static, deployable to GitHub Pages, no backend, no paid keys.

Audience: an engineer or recruiter opening a link and judging in 60 seconds whether this is a
real system or a mock. Depth must be visible: real geography, a stated model, provenance.

## Hard constraints

- Stack you choose must be buildable **offline from this repo** with Node 24 + Vite. No
  backend, no database, no auth, no paid tile keys, no runtime AI calls.
- Data: only the five probed sources in `docs/reference-analysis.md`, or output committed by
  the offline Python pipeline into `public/data/`. Nothing fetched from a private API.
- Honesty rules in `docs/reference-analysis.md` are binding: every derived layer is labelled
  `derived` / `scenario` / `synthetic`; no invented agency names, incident ids, casualty or
  displacement statistics; no real-person data.
- The app must render something meaningful when tile servers are unreachable (styled fallback
  canvas + committed overlays).

## Deliverables (write only these files)

1. `docs/ARCHITECTURE.md`
   - Product statement, target user, the 60-second demo script (what the viewer sees, in order).
   - **Feature parity table**: FireTrace feature → Baanh equivalent → priority `P0/P1/P2` →
     why. P0 is the vertical slice; P2 is explicitly out of the first build.
   - **Tech stack** with one-line rationale per dependency, and the rejected alternatives
     (say why MapLibre-vs-Cesium-vs-three.js, charting lib, state management, styling).
   - **File tree** for the finished repo: every source file and every data file with a one-line
     purpose. Group by concern (`app/`, `map/`, `panels/`, `charts/`, `data/`, `pipeline/`).
   - Component/state contract: the timeline store, the layer registry, the panel router, the
     camera controller; what each component receives and emits.
   - Rendering plan: terrain source, layer ordering and paint order, how the flood extent animates
     between steps without re-tiling, how risk polygons and hotspots are drawn, camera + lighting.
   - Performance budget: frame time, data size, load milestones, fallbacks.
   - Deploy section (static host) and an accessibility baseline.
2. `docs/DATA-PIPELINE.md`
   - AOI definition (bbox + CRS + resolution) and why.
   - Exact pipeline stages with **runnable command per stage**, input file, output file, and the
     JSON/GeoJSON **schema of every output** (property names, types, units, labels).
   - The **inundation model spec** in enough detail that a builder can implement it without
     invention: DEM mosaic from terrarium tiles → river/drainage burn-in → nearest-drainage
     elevation → HAND (height above nearest drainage) → scenario water levels →
     inundation masks → polygonise → simplify → per-step output. State the assumed resolution,
     the projection, the algorithm for nearest-drainage assignment, and how to handle cells with
     no reachable channel.
   - Scenario table: N timesteps across a monsoon event, water level per step in metres above
     local drainage, and the rainfall / main-stem-level series that drives the display — say
     plainly which series are anchored to documented values and which are synthetic.
   - Risk scoring: exact formula over HAND, inundation duration, and district area share; output
     schema for district ranking. No invented demographics.
   - Validation section: the checks that must pass before data ships (geometry validity, monotonic
     area growth where expected, bounds inside Assam, file size caps, no NaN).
3. `docs/MILESTONES.md`
   - `M0` vertical slice: the smallest build that already tells the causal story (name the exact
     files, the exact command to run it, and the acceptance check a reviewer can execute).
   - `M1` parity with the P0+P1 feature table. `M2` polish/optional.
   - Each milestone: acceptance criteria as executable checks, and an explicit "not in this
     milestone" list.
4. `docs/ARCHITECT-SELF-AUDIT.md`
   - Table: every requirement in this brief → where in your docs it is satisfied (file + section)
     → `done` / `deferred` with reason. An honest audit, not a marketing one.

## Do not

- Do not write application code, components, CSS, or pipeline scripts. Docs only.
- Do not `git commit`, push, or touch anything outside `docs/`.
- Do not invent a dataset, a gauge reading, or a statistic. If a value is unknown, define it as
  a labelled synthetic series and say so in the schema.
- Do not add dependencies you cannot justify in one line.

## Stop and report instead of guessing when

A decision would need a paid key, a backend, or data that does not exist in the probed sources.

## Definition of done

All four documents exist, the self-audit table has no unaddressed requirement, the file tree
covers every P0 feature, and `docs/DATA-PIPELINE.md` names a command for every stage. End your
run by printing: the chosen stack in one line, the P0 feature count, and the exact command a
reviewer runs to start M0.
