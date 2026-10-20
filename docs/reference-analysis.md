# Reference analysis — what we are reproducing, and for what

Source: `@claudeai` (2026-10-16) quoting `@DilumSanjaya` (2026-10-08) —
"Played around with an idea for a wildfire analysis tool … Made with Opus 5.5".
Video: 115 s, 3456×1990, 23 sampled frames analysed.

**Codebase: not public.** The author's 100 repos contain no wildfire-analysis project
(`dilums/wildfire` is a 2023 unrelated JS repo) and the t.co resolves only to his own post.
Nothing is forked; the product is specified from the video.

## The reference product: "FireTrace — Wildfire Dynamics Analysis"

Shell: top bar (logo, incident name + region, date range, Layers / Analyze / Share, avatar) ·
centre 3D terrain viewport · right analysis rail · bottom timeline dock.

| Region | Contents |
|---|---|
| Viewport | Oblique 3D satellite imagery draped on a DEM with hillshade and 3D trees; fire perimeter outlines; burn scar (dNBR) fills; hotspot dots; spread-probability layer; contour/progression lines; drone flight paths with sensor footprints; thermal PiP feed; aircraft follow-cam with HUD (altitude / speed / heading); 2D analytical overlay mode; thermal + grayscale base modes |
| Right rail | Layers (Active Fire, Fire Perimeter, Burn Scar dNBR, Fire Spread Probability, Evacuation Zones, Terrain & Imagery → Satellite / Hillshade / Labels + opacity) · Incident Overview (name, agency id, start, size, containment) · Weather & Fire Behavior (temp, humidity, wind) · Drone Fleet with telemetry · Resources table (D-425…, Water Tender, Engine 2, status, ETA) |
| Bottom dock | Timeline (play/pause/step, date scrubber across days) · three synced charts: Fire Area (acres), Rate of Spread (chains/hr), Elevation/Temperature profile · Key Events list / Detections table (time, confidence, coords, sensor) |

Interaction observed: camera orbit/zoom, timeline scrub drives overlays and all three charts,
panel switches between Layers / Drone Fleet / Resources, PiP opens and closes, fullscreen
drone view dismissed with ESC.

## Our product: "Baanh — Assam Flood Dynamics"

Same shell, different physics. Working title `baanh` (Assamese: বান, flood); repo
`baanh` with descriptor "Assam Flood Dynamics Analysis".

| FireTrace | Baanh equivalent |
|---|---|
| Fire perimeter / burn scar | Flood extent per timestep (scenario water levels) |
| Hotspots | Breach / inundation hotspots (embankment breach points, drainage chokepoints) |
| Fire spread probability | Flood-risk zone (DEM-derived, district-distributed) |
| Evacuation zones | Evacuation corridors + relief-camp locations |
| Weather & fire behaviour | Monsoon rainfall, Brahmaputra discharge/level vs danger level, tributary backwater |
| Drone fleet + thermal PiP | Satellite pass scope (imagery PiP with flood mask) + gauge/sensor fleet (CWC-style stations with level telemetry) |
| Resources table | Relief-camp / asset deployment table (boats, teams, camps, status, ETA) |
| Fire area / rate of spread charts | Inundated area (km²) / water-level rise rate (m/day) / rainfall (mm) |
| Elevation profile | Cross-section of the Brahmaputra valley (elevation vs inundation depth) |
| Key events | Flood chronology (breach, peak, recede) |

"What we are demonstrating" (the user's stated goal): **how an Assam flood happens** —
monsoon rainfall → rising Brahmaputra and tributaries → backwater into the floodplain →
inundation of low-lying districts → high-risk areas. The app must make that causal chain
legible, not just paint water on a map.

## Verified data sources (probed from this machine, 2026-10-21)

| Layer | Source | Status |
|---|---|---|
| Terrain / DEM | AWS Terrarium tiles `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png` | 200, PNG |
| Satellite basemap | Esri World Imagery `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` | 200, JPEG |
| District boundaries | geoBoundaries `https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/` | 200, JSON (filter to Assam) |
| Rivers | OSM Overpass `https://overpass-api.de/api/status`; fallback Natural Earth 10m rivers GeoJSON | 200 (Overpass slow, ~30 s) |
| Event context | UNOSAT flood products (portal reachable) | 200 |

No paid map key is used. Everything the app renders must come from these or from the
committed offline pipeline output.

## Honesty rules (non-negotiable)

1. The inundation model is **DEM-derived scenario modelling**, not an operational forecast.
   Every derived layer is labelled `derived`, `scenario`, or `synthetic` in the UI.
2. A provenance panel lists source → processing step → output file for every dataset.
3. Rainfall/discharge series that are not from a cited gauge are marked synthetic and the
   shape of the curve is explained (monsoon onset, peak, recede).
4. No invented agency identifiers, incident numbers, or death/affected-person statistics.
   If a real 2022 figure is used, it is cited in the docs and shown as `reference`.
5. The mechanism (why the valley floods) is stated in-app, in prose, with the model's
   assumptions listed next to it.

## Constraints for the build

- Static site: no backend, no database, no auth, no paid API key. Deployable to GitHub Pages.
- Offline-first data: all heavy geodata precomputed into `public/data/`, app works if tile
  servers are down (basemap excepted, with a styled fallback).
- Data budget: first meaningful paint under ~8 MB of committed GeoJSON/JSON; simplify geometry.
- Browser: Chromium 120+, WebGL2. 60 fps pan/orbit on a mid-range GPU; degrade gracefully.
