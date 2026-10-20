# Architect self-audit

**Scope of this audit:** the four specification documents only. No application code, pipeline
code, CSS, assets, or commits were produced. This is an honest hand-off audit, not a claim that
the product runs.

**Legend:** `done` = the requirement is specified in a named section with enough detail for a
builder; `done (P1)` = deliberately scoped to the parity milestone, not M0; `deferred (P2)` =
explicitly outside the first build with a reason. There are no unaddressed requirements.

| # | Requirement in `docs/briefs/01-architect.md` | Where satisfied | Status | Note |
|---:|---|---|---|---|
| 1 | Read `docs/reference-analysis.md` before designing; use its feature inventory and honesty rules | `ARCHITECTURE.md` header, §1, §3, §11; `DATA-PIPELINE.md` §2, §8 | done | Reference shell, data sources, and honesty rules are carried through, not paraphrased away. |
| 2 | Browser-based flood dynamics dashboard for Assam explaining monsoon → stage → backwater → inundation → risk | `ARCHITECTURE.md` §1 product statement; §2 demo script; `DATA-PIPELINE.md` §7 model | done | The five-link causal chain is the product spine and the M0 acceptance narrative. |
| 3 | Time-animated 3D terrain, risk zoning, scenario levels, synchronous analytics dock | `ARCHITECTURE.md` §3 P0-02…P0-06, §7; `DATA-PIPELINE.md` §7–§9 | done | 3D terrain, 12-step extent, risk zones/ranking, stage series, synced charts. |
| 4 | Everything static, GitHub Pages, no backend/database/auth/paid key/runtime AI | `ARCHITECTURE.md` §4, §9; `MILESTONES.md` “not in” lists | done | No runtime service; two probed tile hosts only. |
| 5 | Audience: engineer/recruiter judging in 60 seconds; depth visible | `ARCHITECTURE.md` §1 target user, §2 script, §11 provenance | done | 60-second script is beat-by-beat and maps to M0/M1 checks. |
| 6 | Buildable offline from repo with Node 24 + Vite | `ARCHITECTURE.md` §4, §9; `MILESTONES.md` M0 commands | done | One `npm ci` online, then offline build; all data committed; no remote fonts. |
| 7 | Data only from the five probed sources or committed pipeline output; no private API | `DATA-PIPELINE.md` §2 source table and source discipline; `ARCHITECTURE.md` §9 | done | UNOSAT is explicitly not ingested; no extra dataset is introduced. |
| 8 | Every derived layer labelled `derived`/`scenario`/`synthetic`; no invented agencies/incidents/casualties/displacement; no real-person data | `ARCHITECTURE.md` §11; `DATA-PIPELINE.md` §1, §6, §10 V13; `MILESTONES.md` A8/A13 | done | Schema has no such fields; `check-honesty.mjs` is an acceptance gate. |
| 9 | App renders meaningfully when tile servers are unreachable (styled fallback + committed overlays) | `ARCHITECTURE.md` §7.7 fallback matrix; §3 P0-09; `MILESTONES.md` A9 | done | Committed hillshade + vector overlays; four-state degradation table; Playwright abort test. |
| 10 | Product statement | `ARCHITECTURE.md` §1 | done | States model, not forecast; real vs synthetic split. |
| 11 | Target user | `ARCHITECTURE.md` §1 “Target user” | done | Primary skeptical technical reviewer; explicit non-user (emergency responder). |
| 12 | 60-second demo script, what viewer sees in order | `ARCHITECTURE.md` §2 | done | Timed table, 0–60 s, includes P1 marks and M0 scope. |
| 13 | Feature parity table: FireTrace → Baanh → P0/P1/P2 → why | `ARCHITECTURE.md` §3 | done | 24 rows; **P0 count 9**, P1 10, P2 5. |
| 14 | P0 is the vertical slice; P2 explicitly out of first build | `ARCHITECTURE.md` §3 note; `MILESTONES.md` M0/M1/M2 | done | M0 implements 8/9 P0; M1 closes P0-07 + P1; P2 listed as not built. |
| 15 | Tech stack with one-line rationale per dependency | `ARCHITECTURE.md` §4 dependency table | done | Vite, React, TS, MapLibre, Zustand, uPlot, zod + dev/test only; Python is offline-only. |
| 16 | Rejected alternatives: MapLibre vs Cesium vs three.js | `ARCHITECTURE.md` §4 rejected table | done | Each with a concrete reason (bundle, token, build cost). |
| 17 | Rejected alternatives: charting library | `ARCHITECTURE.md` §4 rejected table | done | uPlot vs Recharts/Chart.js/D3 full. |
| 18 | Rejected alternatives: state management | `ARCHITECTURE.md` §4 rejected table | done | Zustand vs Redux/Context/Jotai. |
| 19 | Rejected alternatives: styling | `ARCHITECTURE.md` §4 rejected table | done | CSS Modules/tokens vs Tailwind/styled-components/vanilla-extract. |
| 20 | File tree for finished repo, every source/data file, one-line purpose, grouped by concern | `ARCHITECTURE.md` §5 | done | Groups `app/shell`, `map`, `panels`, `charts`, `timeline`, `state`, `data`, `styles`, `tests`, `pipeline`; generated intermediates separated. |
| 21 | Timeline store contract | `ARCHITECTURE.md` §6.2 | done | State fields, actions, clamping, playback semantics, subscribers, reduced motion. |
| 22 | Layer registry contract | `ARCHITECTURE.md` §6.3 | done | `LayerSpec`, `LayerId`, paint order, class badge, lazy data path; panel never touches MapLibre ids. |
| 23 | Panel router contract | `ARCHITECTURE.md` §6.4 | done | Panel ids, open/close/focus, lazy P1 panels, no map unmount. |
| 24 | Camera controller contract | `ARCHITECTURE.md` §6.5 | done | Home, bounds, focus district/reach, modes, status callbacks, reduced motion. |
| 25 | What each component receives and emits | `ARCHITECTURE.md` §6.6 | done | Component/emits table; data-load contract §6.7. |
| 26 | Terrain source | `ARCHITECTURE.md` §7.1 | done | AWS Terrarium raster-dem, z12 render, z11 pipeline, Esri drape, hillshade, sky. |
| 27 | Layer ordering and paint order | `ARCHITECTURE.md` §7.2 | done | 18-row bottom→top table tied to registry `paintOrder`. |
| 28 | Flood extent animates between steps without re-tiling | `ARCHITECTURE.md` §7.4 | done | One GeoJSON source, two filtered fill layers, rAF opacity crossfade, no `setData`/source rebuild. |
| 29 | Risk polygons and hotspots drawn | `ARCHITECTURE.md` §7.3, §7.5 | done | Risk fill under flood, district line tint, hotspot circle semantics (not breaches). |
| 30 | Camera + lighting | `ARCHITECTURE.md` §7.6 | done | Oblique home, constrained orbit, static hillshade light, no fake sun model. |
| 31 | Performance budget: frame time, data size, load milestones, fallbacks | `ARCHITECTURE.md` §8 | done | Frame p95, long-frame cap, tier caps, load table, fallback matrix; budgets not measurements. |
| 32 | Deploy section (static host) | `ARCHITECTURE.md` §9 | done | GitHub Pages Actions, base `/baanh/`, caching, rollback, no secrets. |
| 33 | Accessibility baseline | `ARCHITECTURE.md` §10 | done | WCAG 2.2 AA target, slider semantics, live region, chart tables, map alternative, reduced motion, tests. |
| 34 | AOI definition (bbox + CRS + resolution) and why | `DATA-PIPELINE.md` §3 | done | `[89.55,23.95,96.15,28.15]`, EPSG:32646, 90 m, buffer/mask rationale, memory trade-off. |
| 35 | Exact pipeline stages with a runnable command per stage | `DATA-PIPELINE.md` §5 stages 01–15 | done | 15 fenced PowerShell commands, exact flags; stage 00 env in §4. |
| 36 | Input file, output file per stage | `DATA-PIPELINE.md` §5 per-stage blocks + §4.1 stage map | done | Each stage lists input/process/output/failure; outputs named. |
| 37 | JSON/GeoJSON schema of every output (names, types, units, labels) | `DATA-PIPELINE.md` §6.1–§6.17 | done | Manifest, provenance, scenario, districts, state, rivers, flood frames/summary, risk zones/ranking/hotspots, series/cross-sections, assets, gauges, validation, hillshade binary. |
| 38 | Inundation model: DEM mosaic from Terrarium | `DATA-PIPELINE.md` §7.2 | done | Decode formula, warp, void policy, sanity bounds. |
| 39 | River/drainage burn-in | `DATA-PIPELINE.md` §7.3 | done | Rasterisation widths, 5×5 min, 3 m burn, no fake monotonic pass, stated limitation. |
| 40 | Nearest-drainage elevation | `DATA-PIPELINE.md` §7.4 | done | SciPy EDT with `return_indices`, sampling 90 m, deterministic ties, distance units. |
| 41 | HAND | `DATA-PIPELINE.md` §7.5 | done | `max(0, dem_burned − nearest_channel_z)`, no smoothing, nodata rule. |
| 42 | Scenario water levels | `DATA-PIPELINE.md` §7.6, §8 | done | Uniform stage, mask, depth, no levee/infiltration, limitation stated. |
| 43 | Inundation masks | `DATA-PIPELINE.md` §7.6–§7.7 | done | Threshold + Assam mask + 8-connected component retention, min cells. |
| 44 | Polygonise | `DATA-PIPELINE.md` §7.8 | done | Per-band rasterio shapes, make_valid, winding, 5 decimals, geodesic area. |
| 45 | Simplify | `DATA-PIPELINE.md` §7.8 | done | 75 m in projected CRS, preserve topology, min ring 0.02 km². |
| 46 | Per-step output | `DATA-PIPELINE.md` §6.7–§6.8 | done | 12 steps, four bands, summary fields and units. |
| 47 | Assumed resolution, projection, nearest algorithm, no-reachable-channel handling | `DATA-PIPELINE.md` §3, §7.4, §7.9 | done | Explicit 90 m/EPSG:32646, EDT, 12 km limit, nodata, below-channel clamp, isolated components. |
| 48 | Scenario table: N timesteps, water level per step, rainfall/main-stem series | `DATA-PIPELINE.md` §8.1 | done | N=12, stage 0.5→6.0 m, synthetic rainfall 6→2 mm/day, anomaly 0.3→3.4 m. |
| 49 | State plainly which series are anchored vs synthetic | `DATA-PIPELINE.md` §8.2 | done | Only qualitative monsoon/lag/recession shape is anchored; all numbers synthetic. |
| 50 | Risk scoring formula over HAND, duration, district area share; output schema; no demographics | `DATA-PIPELINE.md` §9.1–§9.2, §6.10 | done | Cell score and district score formulas, weights, thresholds, drivers, coverage caveat; no population field. |
| 51 | Validation checks before data ships (geometry, monotonic area, Assam bounds, caps, no NaN) | `DATA-PIPELINE.md` §10 V01–V20 | done | 20 checks with pass/fail conditions; `publish` refuses on fail. |
| 52 | M0 vertical slice: exact files | `MILESTONES.md` M0 “exact files” | done | Root, src, public data, scripts, tests, and the M0 pipeline subset. |
| 53 | M0 exact command to run | `MILESTONES.md` M0 commands | done | `npm ci && npm run dev`; acceptance `npm run verify:m0`. |
| 54 | M0 acceptance check a reviewer can execute | `MILESTONES.md` M0-A1…A14 + manual check | done | Playwright, data, budget, honesty, fallback; manual four-clause test. |
| 55 | M1 parity with P0 + P1 feature table | `MILESTONES.md` M1 matrix | done | Every P0/P1 row mapped to an executable check. |
| 56 | M2 polish/optional | `MILESTONES.md` M2 | done | Candidates with preconditions; M2 may be skipped. |
| 57 | Each milestone has acceptance criteria as executable checks and explicit “not in” list | `MILESTONES.md` M0/M1/M2 | done | All three have command tables, checks, and not-in lists. |
| 58 | Self-audit table requirement → location → done/deferred reason | This document | done | No unaddressed requirement; caveats below. |
| 59 | Do not write application code, components, CSS, or pipeline scripts | Repository state | done | Only `docs/ARCHITECTURE.md`, `docs/DATA-PIPELINE.md`, `docs/MILESTONES.md`, `docs/ARCHITECT-SELF-AUDIT.md` created. |
| 60 | Do not `git commit`, push, or touch outside `docs/` | Repository state | done | No commits; no files outside `docs/` written. |
| 61 | Do not invent a dataset, gauge reading, or statistic; unknown values synthetic and labelled | `DATA-PIPELINE.md` §2, §8.2; `ARCHITECTURE.md` §11 | done | No numeric gauge/casualty/agency value exists; synthetic series are named and labelled. |
| 62 | Do not add dependencies that cannot be justified in one line | `ARCHITECTURE.md` §4 | done | Every runtime/dev dependency has a one-line role/rationale; Python deps are stage-specific. |
| 63 | Stop and report instead of guessing when a decision needs a paid key, backend, or missing data | `ARCHITECTURE.md` §1, §12; `DATA-PIPELINE.md` §2, §12; `MILESTONES.md` P2 | done | P2 features requiring unavailable data are deferred, not invented; no paid/backend path exists. |
| 64 | Definition of done: four docs exist, self-audit complete, file tree covers P0, every stage has a command, final print | This file; `ARCHITECTURE.md` §5; `DATA-PIPELINE.md` §5; final response | done | Final response prints stack, P0 count (9), and M0 command. |

---

## Deferred by design (P2)

These are not gaps in the spec; they are explicitly outside the first build, usually because the
data does not exist in the probed sources. Each could be revisited only with a sourced dataset.

| Item | Where | Status | Reason |
|---|---|---|---|
| Evacuation corridors / relief camps | `ARCHITECTURE.md` P2-01 | deferred (P2) | No verified corridor or camp dataset; synthetic camps would imply operational guidance. |
| Resources table (boats, teams, ETA) | `ARCHITECTURE.md` P2-02 | deferred (P2) | No deployment, fleet, or ETA data; inventing it violates the honesty rules. |
| Drone/aircraft HUD and flight paths | `ARCHITECTURE.md` P2-03 | deferred (P2) | No flight or telemetry data; only camera behaviour survives at P1. |
| Multi-event historical comparison | `ARCHITECTURE.md` P2-04 | deferred (P2) | A second event needs verified extents/levels not in the probed sources. |
| 30 m analysis, exports, live adapter | `ARCHITECTURE.md` P2-05 | deferred (P2) | 30 m is ~9× the memory and not needed for the story; exports/live feeds add scope without evidence. |

**M0 scope note:** P0-07 (the full layer-control rail) is a P0 feature but deliberately ships in
M1. M0 has fixed layer visibility and a working fallback; it still tells the causal story. If the
review bar requires all nine P0 features in the first demo, move P0-07 into M0 and re-run the M0
checks; nothing else in the spec blocks that.

---

## Honest caveats (not unaddressed requirements)

1. **This is a specification, not a running product.** The M0 command cannot execute until the
   builder creates `package.json`, the app, the data and the pipeline. Stack versions and
   performance budgets are targets, not measurements.
2. **The pipeline CLI is an interface contract.** `cli.py` subcommands, flags, and schemas are
   specified precisely, but no pipeline code exists yet. A builder must implement them and may
   discover rasterio/SciPy edge cases; the validation gates are the guardrail.
3. **Source terms need a pre-launch check.** AWS Terrarium and Esri World Imagery are publicly
   reachable and key-free as probed, but their terms/attribution must be reviewed before a public
   launch. The docs require attribution; they do not provide legal clearance.
4. **OSM completeness is unknown.** River and facility layers can be incomplete. This is stated
   in the model limitations and the P1 facility schema; the app must keep the caveat visible.
5. **The Assam ADM2 count is not hard-coded.** The pipeline filters what geoBoundaries returns
   and validates uniqueness/coverage. This avoids inventing a district count or silently fixing
   renamed units.
6. **UNOSAT is not used.** It is a probed context source, but the first build does not ingest an
   event extent. `provenance.json` notes this; a future P2 cross-check would need a citation.
7. **No calibration.** The 6.0 m peak stage, 4.0 m threshold, rainfall values, and risk weights
   are declared model parameters. They are not fitted to a gauge or satellite extent, and the
   docs say so repeatedly. This is a deliberate honesty trade-off, not an oversight.
8. **M0 is eight of nine P0.** P0-07 (layer controls) is M1. M0 still tells the causal story;
   the split is explicit in `ARCHITECTURE.md` §3 and `MILESTONES.md` M0. If a reviewer requires
   all P0 at the first demo, move P0-07 into M0 and re-run the M0 checks.
9. **P1 asset exposure is not P0.** The mission’s “assets at risk” is answered at M1 with OSM
   facilities and a completeness caveat; P0 answers “districts at risk”. No facility capacity or
   operational status is invented.
10. **No screenshot or trace evidence.** The performance and a11y numbers are budgets and test
    plans; M1 requires a recorded trace and axe run. The audit does not pretend those exist.

## Final consistency check

- P0 features: **9** (P0-01 … P0-09).
- P1 features: 10; P2 rows: 5, all explicitly not built.
- Scenario: **12 steps**, peak S07, 136 days, peak stage **6.0 m**, threshold 4.0 m.
- AOI: `[89.55, 23.95, 96.15, 28.15]`, EPSG:32646, **90 m**.
- M0 command: `npm ci && npm run dev`; acceptance: `npm run verify:m0`.
- M0 file list is a subset of the architecture file tree; M1 additions are disjoint and listed.
- Every pipeline output in `DATA-PIPELINE.md` §6 has a producing stage in §5 and a validation
  check in §10.
- Every P0/P1 feature has a component/file in `ARCHITECTURE.md` §5 and an acceptance check in
  `MILESTONES.md` M1.
- No document claims that a synthetic series is observed, that the model is a forecast, or that
  an agency/incident/casualty figure exists.
