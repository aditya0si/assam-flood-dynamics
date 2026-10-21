export const TERRAIN_SOURCE_ID = 'aws-terrarium-dem';
export const TERRAIN_HILLSHADE_SOURCE_ID = 'aws-terrarium-hillshade';
export const IMAGERY_SOURCE_ID = 'esri-world-imagery';
export const FALLBACK_SOURCE_ID = 'committed-hillshade';
export const FLOOD_CURRENT_SOURCE_ID = 'flood-raster-current';
export const FLOOD_OUTGOING_SOURCE_ID = 'flood-raster-outgoing';
export const DISTRICTS_SOURCE_ID = 'assam-districts';
export const STATE_SOURCE_ID = 'assam-state';
export const RIVERS_SOURCE_ID = 'assam-rivers';
export const RISK_ZONES_SOURCE_ID = 'risk-zones';
export const HOTSPOTS_SOURCE_ID = 'inundation-hotspots';

export const BACKGROUND_LAYER_ID = 'background';
export const FALLBACK_LAYER_ID = 'fallback-relief';
export const IMAGERY_LAYER_ID = 'satellite';
export const TERRAIN_HILLSHADE_LAYER_ID = 'terrain-hillshade';
export const FLOOD_OUTGOING_LAYER_ID = 'flood-raster-outgoing-layer';
export const FLOOD_CURRENT_LAYER_ID = 'flood-raster-current-layer';
export const RISK_ZONE_FILL_LAYER_ID = 'risk-zones-fill';
export const RISK_ZONE_LINE_LAYER_ID = 'risk-zones-line';
export const RIVERS_LAYER_ID = 'rivers';
export const DISTRICT_LAYER_ID = 'district-line';
export const STATE_LAYER_ID = 'state-outline';
export const HOTSPOTS_LAYER_ID = 'hotspots';

export const TERRARIUM_TILES = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
export const ESRI_IMAGERY_TILES =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

export const TERRAIN_EXAGGERATION = 1.4;
export const HOME_PITCH = 42;
export const HOME_BEARING = -12;
export const HOME_ZOOM = 7.2;
/**
 * Subject frame for the Brahmaputra flood-prone belt (the AOI v2 core), not the
 * state bbox. Derivation: the committed peak frame (step-07) has its wet pixels
 * concentrated in this belt; this box is the 5th–95th percentile of those
 * pixels in the main valley, with the Barak-valley tail excluded. No data file
 * was changed to produce it.
 */
export const AOI_CORE_BOUNDS: [number, number, number, number] = [90.15, 25.95, 95.0, 27.55];
export const MAX_BOUNDS: [[number, number], [number, number]] = [
  [88.9, 23.3],
  [96.8, 28.8],
];
export const MIN_ZOOM = 5.5;
export const MAX_ZOOM = 13;
export const MAX_PITCH = 75;

export const FLOOD_OPACITY = 0.88;
export const CROSSFADE_MS = 220;
export const TILE_HEALTH_TIMEOUT_MS = 6000;

/**
 * B4 camera fit. The peak frame is scanned at runtime to find the dominant wet
 * core; the map then fits that extent (not the wider flood-prone belt) with an
 * 8% total margin and the review's 42 degree pitch. Presentation only: no
 * frame, class or value is regenerated.
 */
export const PEAK_FIT_PADDING_RATIO = 0.04;
export const PEAK_EXTENT_SCAN_MAX_WIDTH = 1200;
export const PEAK_EXTENT_ALPHA_FLOOR = 8;
export const PEAK_EXTENT_ROW_DENSITY_FLOOR = 0.1;
export const PEAK_EXTENT_TRIM = 0.05;

/**
 * Palette separation (REVIEW-07 B2 + REVIEW-09 B4):
 * - Depth classes are recoloured at runtime to cyan -> teal -> indigo -> violet.
 * - Rivers are warm sand, not cyan, so a mapped channel can never be confused with water.
 * - Hillshade is lower-contrast and desaturated so it does not compete at valley scale.
 */
export const RIVER_COLOR = '#cbb58a';
export const HILLSHADE_SHADOW = '#051412';
export const HILLSHADE_HIGHLIGHT = '#b9c7c8';
export const HILLSHADE_ACCENT = '#3b4d50';
export const DISTRICT_LABEL_MIN_ZOOM = 6;
export const DISTRICT_LABEL_LIMIT = 10;

export function bboxCoordinates(
  bbox: [number, number, number, number],
): [[number, number], [number, number], [number, number], [number, number]] {
  const [west, south, east, north] = bbox;
  return [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ];
}

export function bboxCenter(bbox: [number, number, number, number]): [number, number] {
  const [west, south, east, north] = bbox;
  return [(west + east) / 2, (south + north) / 2];
}
