export const TERRAIN_SOURCE_ID = 'aws-terrarium-dem';
export const TERRAIN_HILLSHADE_SOURCE_ID = 'aws-terrarium-hillshade';
export const IMAGERY_SOURCE_ID = 'esri-world-imagery';
export const FALLBACK_SOURCE_ID = 'committed-hillshade';
export const FLOOD_CURRENT_SOURCE_ID = 'flood-raster-current';
export const FLOOD_OUTGOING_SOURCE_ID = 'flood-raster-outgoing';
export const DISTRICTS_SOURCE_ID = 'assam-districts';
export const STATE_SOURCE_ID = 'assam-state';
export const RIVERS_SOURCE_ID = 'assam-rivers';

export const BACKGROUND_LAYER_ID = 'background';
export const FALLBACK_LAYER_ID = 'fallback-relief';
export const IMAGERY_LAYER_ID = 'satellite';
export const TERRAIN_HILLSHADE_LAYER_ID = 'terrain-hillshade';
export const FLOOD_OUTGOING_LAYER_ID = 'flood-raster-outgoing-layer';
export const FLOOD_CURRENT_LAYER_ID = 'flood-raster-current-layer';
export const RIVERS_LAYER_ID = 'rivers';
export const DISTRICT_LAYER_ID = 'district-line';
export const STATE_LAYER_ID = 'state-outline';

export const TERRARIUM_TILES = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
export const ESRI_IMAGERY_TILES =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

export const TERRAIN_EXAGGERATION = 1.4;
export const HOME_PITCH = 55;
export const HOME_BEARING = -15;
export const MAX_BOUNDS: [[number, number], [number, number]] = [
  [88.9, 23.3],
  [96.8, 28.8],
];
export const MIN_ZOOM = 5.5;
export const MAX_ZOOM = 13;
export const MAX_PITCH = 75;

export const FLOOD_OPACITY = 0.62;
export const CROSSFADE_MS = 220;
export const TILE_HEALTH_TIMEOUT_MS = 6000;

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
