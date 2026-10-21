# Verification ledger — data sources and model routes actually probed

Reviewer: Hermes · machine: Windows 11, this host · date: **2026-10-21** · method: direct HTTP
probes from this machine, then a real query where the endpoint survived. Every row is something I
executed, not something a panel model asserted.

## 1. Working, keyless (usable today by the pipeline)

| Source | URL probed | Result | Note |
|---|---|---|---|
| Open-Meteo Flood API (GloFAS discharge) | `https://flood-api.open-meteo.com/v1/flood?latitude=26.75&longitude=94.2&daily=river_discharge` | **200 application/json** | returns `river_discharge` in m³/s, 30 past + 7 forecast days |
| Open-Meteo forecast (rainfall) | `https://api.open-meteo.com/v1/forecast?...&hourly=precipitation` | **200** | free, no key |
| Open-Meteo archive (ERA5 rainfall) | `https://archive-api.open-meteo.com/v1/archive?...` | **200** | free historical series |
| Sentinel-1 STAC (Element 84 Earth Search) | `POST https://earth-search.aws.element84.com/v1/search` | **200**, 5 scenes | see §3 |
| JRC Global Surface Water | `https://global-surface-water.appspot.com/` | 200 | 30 m monthly history 1984–2021 |
| HydroSHEDS / HydroATLAS | `https://www.hydrosheds.org/products/hydroatlas` | 200 | catchment attributes for runoff work |
| WorldPop REST | `https://www.worldpop.org/rest/data/pop/wpgp?iso3=IND` | 200 application/json | ~100 m population |
| Copernicus Data Space catalogue | `https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$top=1` | 200 | search works; download needs an account |
| India-WRIS | `https://indiawris.gov.in/wris/` | 200 | CWC/state water data portal (terms vary by product) |
| CWC flood forecasting | `https://ffs.india-water.gov.in/` | 200 | official FFS portal |
| ASDMA | `https://asdma.assam.gov.in/` | 200 | state disaster-management bulletins |
| UNOSAT flood products | `https://unosat.org/products/` | 200 | event flood extents, humanitarian use |
| Copernicus EMS Rapid Mapping | `https://rapidmapping.emergency.copernicus.eu/` | 200 | activation-based, not continuous |
| NRSC Bhoonidhi | `https://bhoonidhi.nrsc.gov.in/bhoonidhi/index.html` | 200 | CartoDEM / Indian EO ordering |
| IRI Data Library | `https://iridl.ldeo.columbia.edu/` | 200 | IMD grid mirror candidate |
| Geofabrik India extract | `https://download.geofabrik.de/asia/india.html` | 200 | OSM bulk, better than Overpass for a full-state build |
| NASA GES DISC | `https://disc.gsfc.nasa.gov/` | 200 | GPM IMERG (Earthdata login) |

## 2. Negative findings (do not put these in a plan without an alternative)

| Claim / endpoint | Probe result | Consequence |
|---|---|---|
| OpenCode **Zen free** models through Hermes (`glm-5.3-flash-free`, provider `opencode`) | **HTTP 403** — "free tier can only be used from within OpenCode" | Free Zen models are unusable as a Hermes panel member |
| OpenCode CLI own auth (`opencode run -m opencode/glm-5.3-flash-free`) | `Invalid credential` | Not authenticated here; would need `opencode auth login` |
| `floodforecast.india-ris.org` (proposed by one panel model) | **DNS does not resolve** (`getaddrinfo failed`) | Claim unverified; the working official alternative is `ffs.india-water.gov.in` |
| `https://cds.climate.copernicus.eu/api/v2` | **404** | CDS API v2 endpoint has moved; GloFAS via CDS needs a current account anyway |
| `https://data.bris.ac.uk/dataset/25wfy0f9ukoge2gs7a5mqpq2j7` (FABDEM) | connection reset | Portal is `fabdem.org`; direct data host needs the current download route |
| Overpass API | **502** on one probe (200 on a later one) | Flaky: needs retry + Geofabrik extract fallback |

## 3. GloFAS is real but coordinate-fragile — measured

Snapping a lat/lon to the nearest GloFAS river cell does **not** reliably land on the Brahmaputra.
Median discharge from 8-day windows at five Assam coordinates:

| Point | Median discharge |
|---|---|
| Majuli / main stem (26.95 N, 94.10 E) | **0.1 m³/s** |
| Dhubri, state exit (26.40 N, 90.05 E) | 8.8 m³/s |
| Upper Assam (27.05 N, 94.60 E) | 104.2 m³/s |
| Jorhat area (26.75 N, 94.20 E) | 11.5 m³/s |
| Guwahati reach (26.20 N, 91.70 E) | 0.8 m³/s |

A Brahmaputra main stem at peak carries tens of thousands of m³/s, so these are **tributary or
headwater cells**. Any plan that says "use GloFAS for the Brahmaputra" must first select the reach
by upstream area / GloFAS river ID, or anchor on CWC gauge stages instead. This is exactly the
kind of plausible-sounding claim that would have shipped a wrong number.

## 4. Sentinel-1 calibration data is genuinely free and available

`POST https://earth-search.aws.element84.com/v1/search`, bbox `[92.0, 25.5, 95.5, 27.5]`,
`2022-06-10/2022-06-30`, collection `sentinel-1-grd`, **no auth**: 5 scenes returned, e.g.
`S1A_IW_GRDH_1SDV_20220628T115736…` and `…20220623T114928…`. That is enough to build a held-out
wet/dry mask for the June 2022 Assam flood and to score any model output against it (IoU / precision /
recall), which is the first honest validation step the current product lacks.

## 5. Consolidation note

None of the panel models had access to these probes. Where a report names a source that is not in
§1, treat it as **unverified** until it appears here or is probed the same way.
