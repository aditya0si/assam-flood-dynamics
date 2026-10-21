import type {
  ExpressionSpecification,
  LayerSpecification,
  Map as MapLibreMap,
  StyleSpecification,
} from 'maplibre-gl';
import type { Dataset } from '../data/types';
import { dataUrl } from '../data/loadData';
import { MAP_ATTRIBUTION } from '../data/attribution';
import { RISK_CLASS_COLORS } from '../data/risk';
import { fallbackHillshadeSource } from './fallbackRaster';
import {
  BACKGROUND_LAYER_ID,
  DISTRICT_LAYER_ID,
  DISTRICTS_SOURCE_ID,
  ESRI_IMAGERY_TILES,
  FALLBACK_LAYER_ID,
  FALLBACK_SOURCE_ID,
  FLOOD_CURRENT_LAYER_ID,
  FLOOD_CURRENT_SOURCE_ID,
  FLOOD_OPACITY,
  FLOOD_OUTGOING_LAYER_ID,
  FLOOD_OUTGOING_SOURCE_ID,
  HILLSHADE_ACCENT,
  HILLSHADE_HIGHLIGHT,
  HILLSHADE_SHADOW,
  HOTSPOTS_LAYER_ID,
  HOTSPOTS_SOURCE_ID,
  IMAGERY_LAYER_ID,
  IMAGERY_SOURCE_ID,
  RIVER_COLOR,
  RIVERS_LAYER_ID,
  RIVERS_SOURCE_ID,
  RISK_ZONES_SOURCE_ID,
  RISK_ZONE_FILL_LAYER_ID,
  RISK_ZONE_LINE_LAYER_ID,
  STATE_LAYER_ID,
  STATE_SOURCE_ID,
  TERRAIN_EXAGGERATION,
  TERRAIN_HILLSHADE_LAYER_ID,
  TERRAIN_HILLSHADE_SOURCE_ID,
  TERRAIN_SOURCE_ID,
  TERRARIUM_TILES,
  bboxCoordinates,
} from './mapConfig';

const RISK_COLOR_EXPRESSION = [
  'match',
  ['get', 'risk_class'],
  'low',
  RISK_CLASS_COLORS.low,
  'moderate',
  RISK_CLASS_COLORS.moderate,
  'high',
  RISK_CLASS_COLORS.high,
  'very_high',
  RISK_CLASS_COLORS.very_high,
  '#93a8b1',
] as unknown as ExpressionSpecification;

const DISTRICT_RISK_TINT = [
  'match',
  ['get', 'risk_class'],
  'low',
  RISK_CLASS_COLORS.low,
  'moderate',
  RISK_CLASS_COLORS.moderate,
  'high',
  RISK_CLASS_COLORS.high,
  'very_high',
  RISK_CLASS_COLORS.very_high,
  '#c8d6db',
] as unknown as ExpressionSpecification;

export function buildMapStyle(dataset: Dataset): StyleSpecification {
  const frameBbox = dataset.frameIndex.bbox;
  const frameCoordinates = bboxCoordinates(frameBbox);
  const firstFrame = dataUrl(`flood/${dataset.frameIndex.steps[0].file}`);

  const layers: LayerSpecification[] = [
    {
      id: BACKGROUND_LAYER_ID,
      type: 'background',
      paint: { 'background-color': '#071014' },
    },
    {
      id: FALLBACK_LAYER_ID,
      type: 'raster',
      source: FALLBACK_SOURCE_ID,
      paint: {
        'raster-opacity': 1,
        'raster-fade-duration': 0,
      },
    },
    {
      id: IMAGERY_LAYER_ID,
      type: 'raster',
      source: IMAGERY_SOURCE_ID,
      paint: {
        'raster-opacity': 1,
        'raster-fade-duration': 180,
      },
    },
    {
      id: TERRAIN_HILLSHADE_LAYER_ID,
      type: 'hillshade',
      source: TERRAIN_HILLSHADE_SOURCE_ID,
      paint: {
        // Deliberately quiet: relief contextualises the flood, it does not compete.
        'hillshade-exaggeration': 0.22,
        'hillshade-illumination-direction': 315,
        'hillshade-illumination-altitude': 45,
        'hillshade-shadow-color': HILLSHADE_SHADOW,
        'hillshade-highlight-color': HILLSHADE_HIGHLIGHT,
        'hillshade-accent-color': HILLSHADE_ACCENT,
      },
    },
    {
      id: RISK_ZONE_FILL_LAYER_ID,
      type: 'fill',
      source: RISK_ZONES_SOURCE_ID,
      paint: {
        'fill-color': RISK_COLOR_EXPRESSION,
        'fill-opacity': 0.34,
        'fill-antialias': false,
      },
    },
    {
      id: RISK_ZONE_LINE_LAYER_ID,
      type: 'line',
      source: RISK_ZONES_SOURCE_ID,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': RISK_COLOR_EXPRESSION,
        'line-width': 0.55,
        'line-opacity': 0.82,
      },
    },
    {
      id: FLOOD_OUTGOING_LAYER_ID,
      type: 'raster',
      source: FLOOD_OUTGOING_SOURCE_ID,
      paint: {
        'raster-opacity': 0,
        'raster-opacity-transition': { duration: 0 },
        'raster-fade-duration': 0,
        'raster-saturation': 0.38,
        'raster-contrast': 0.14,
        'raster-resampling': 'linear',
      },
    },
    {
      id: FLOOD_CURRENT_LAYER_ID,
      type: 'raster',
      source: FLOOD_CURRENT_SOURCE_ID,
      paint: {
        'raster-opacity': FLOOD_OPACITY,
        'raster-opacity-transition': { duration: 0 },
        'raster-fade-duration': 0,
        'raster-saturation': 0.38,
        'raster-contrast': 0.14,
        'raster-resampling': 'linear',
      },
    },
    {
      id: RIVERS_LAYER_ID,
      type: 'line',
      source: RIVERS_SOURCE_ID,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': RIVER_COLOR,
        'line-width': ['match', ['get', 'order'], 1, 1.9, 2, 1.1, 0.65],
        'line-opacity': 0.78,
        'line-blur': 0.2,
      },
    },
    {
      id: DISTRICT_LAYER_ID,
      type: 'line',
      source: DISTRICTS_SOURCE_ID,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': DISTRICT_RISK_TINT,
        'line-width': 0.72,
        'line-opacity': 0.72,
      },
    },
    {
      id: STATE_LAYER_ID,
      type: 'line',
      source: STATE_SOURCE_ID,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#e2edf1',
        'line-width': 1.35,
        'line-opacity': 0.72,
      },
    },
    {
      id: HOTSPOTS_LAYER_ID,
      type: 'circle',
      source: HOTSPOTS_SOURCE_ID,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'area_km2'], 18, 3.8, 81, 9],
        'circle-color': '#f0a93f',
        'circle-opacity': 1,
        'circle-stroke-color': '#1a1207',
        'circle-stroke-width': 1.2,
        'circle-pitch-alignment': 'map',
      },
    },
  ];

  return {
    version: 8,
    name: 'Baanh scenario terrain',
    sources: {
      [TERRAIN_SOURCE_ID]: {
        type: 'raster-dem',
        tiles: [TERRARIUM_TILES],
        tileSize: 256,
        maxzoom: 12,
        encoding: 'terrarium',
        attribution: 'Elevation: AWS Terrarium / Mapzen',
      },
      [TERRAIN_HILLSHADE_SOURCE_ID]: {
        type: 'raster-dem',
        tiles: [TERRARIUM_TILES],
        tileSize: 256,
        maxzoom: 12,
        encoding: 'terrarium',
      },
      [IMAGERY_SOURCE_ID]: {
        type: 'raster',
        tiles: [ESRI_IMAGERY_TILES],
        tileSize: 256,
        maxzoom: 17,
        attribution: 'Imagery: Esri, Maxar, Earthstar Geographics',
      },
      [FALLBACK_SOURCE_ID]: fallbackHillshadeSource(dataset.manifest.bbox),
      [FLOOD_CURRENT_SOURCE_ID]: {
        type: 'image',
        url: firstFrame,
        coordinates: frameCoordinates,
      },
      [FLOOD_OUTGOING_SOURCE_ID]: {
        type: 'image',
        url: firstFrame,
        coordinates: frameCoordinates,
      },
      [RISK_ZONES_SOURCE_ID]: {
        type: 'geojson',
        data: dataset.riskZones,
        attribution: 'Risk zones: derived from committed scenario',
      },
      [HOTSPOTS_SOURCE_ID]: {
        type: 'geojson',
        data: dataset.hotspots,
        attribution: 'Hotspots: derived, not breaches',
      },
      [DISTRICTS_SOURCE_ID]: {
        type: 'geojson',
        data: dataset.districts,
        attribution: MAP_ATTRIBUTION,
      },
      [STATE_SOURCE_ID]: {
        type: 'geojson',
        data: dataset.state,
      },
      [RIVERS_SOURCE_ID]: {
        type: 'geojson',
        data: dataset.rivers,
      },
    },
    sky: {
      'sky-color': '#071014',
      'horizon-color': '#17303a',
      'fog-color': '#0b171d',
      'fog-ground-blend': 0.72,
      'horizon-fog-blend': 0.65,
      'sky-horizon-blend': 0.8,
    },
    layers,
  };
}

export function setTerrain(map: MapLibreMap, enabled: boolean): void {
  if (enabled) {
    map.setTerrain({ source: TERRAIN_SOURCE_ID, exaggeration: TERRAIN_EXAGGERATION });
  } else {
    map.setTerrain(null);
  }
}

/**
 * Shared layer-state application (used by MapCanvas at scene start and on every
 * layer-store change). Kept next to the style so paint property names cannot
 * drift from the layer definitions.
 */
export function applyLayerPaint(
  map: MapLibreMap,
  state: {
    visible: Record<string, boolean>;
    opacity: Record<string, number>;
    baseMode: 'imagery' | 'hillshade';
  },
): void {
  if (!map.getLayer(BACKGROUND_LAYER_ID)) return;

  const setVisibility = (layerId: string, visible: boolean) => {
    if (!map.getLayer(layerId)) return;
    map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
  };

  setVisibility(FLOOD_OUTGOING_LAYER_ID, state.visible.flood);
  setVisibility(FLOOD_CURRENT_LAYER_ID, state.visible.flood);
  setVisibility(RISK_ZONE_FILL_LAYER_ID, state.visible['risk-zones']);
  setVisibility(RISK_ZONE_LINE_LAYER_ID, state.visible['risk-zones']);
  setVisibility(RIVERS_LAYER_ID, state.visible.rivers);
  setVisibility(DISTRICT_LAYER_ID, state.visible.districts);
  setVisibility(TERRAIN_HILLSHADE_LAYER_ID, state.visible.hillshade);
  setVisibility(HOTSPOTS_LAYER_ID, state.visible.hotspots);
  setVisibility(IMAGERY_LAYER_ID, state.baseMode === 'imagery');

  if (map.getLayer(RISK_ZONE_FILL_LAYER_ID)) {
    map.setPaintProperty(RISK_ZONE_FILL_LAYER_ID, 'fill-opacity', state.opacity['risk-zones']);
  }
  if (map.getLayer(RISK_ZONE_LINE_LAYER_ID)) {
    map.setPaintProperty(
      RISK_ZONE_LINE_LAYER_ID,
      'line-opacity',
      Math.min(1, 0.45 + state.opacity['risk-zones']),
    );
  }
  if (map.getLayer(RIVERS_LAYER_ID)) {
    map.setPaintProperty(RIVERS_LAYER_ID, 'line-opacity', state.opacity.rivers);
  }
  if (map.getLayer(DISTRICT_LAYER_ID)) {
    map.setPaintProperty(DISTRICT_LAYER_ID, 'line-opacity', state.opacity.districts);
  }
  if (map.getLayer(HOTSPOTS_LAYER_ID)) {
    map.setPaintProperty(HOTSPOTS_LAYER_ID, 'circle-opacity', state.opacity.hotspots);
  }
  if (map.getLayer(FALLBACK_LAYER_ID)) {
    map.setPaintProperty(FALLBACK_LAYER_ID, 'raster-opacity', state.baseMode === 'hillshade' ? 0.92 : 1);
  }
  if (map.getLayer(TERRAIN_HILLSHADE_LAYER_ID)) {
    const opacity = state.opacity.hillshade;
    map.setPaintProperty(TERRAIN_HILLSHADE_LAYER_ID, 'hillshade-exaggeration', 0.1 + opacity * 0.65);
    // MapLibre's hillshade layer has no dedicated opacity property. Alpha in
    // the three shading colours is the opacity control that actually changes
    // rendered pixels, while keeping one layer (no map re-init).
    map.setPaintProperty(
      TERRAIN_HILLSHADE_LAYER_ID,
      'hillshade-shadow-color',
      rgba(HILLSHADE_SHADOW, 0.82 * opacity),
    );
    map.setPaintProperty(
      TERRAIN_HILLSHADE_LAYER_ID,
      'hillshade-highlight-color',
      rgba(HILLSHADE_HIGHLIGHT, 0.52 * opacity),
    );
  }
  if (map.getLayer(IMAGERY_LAYER_ID)) {
    map.setPaintProperty(IMAGERY_LAYER_ID, 'raster-opacity', state.baseMode === 'imagery' ? 1 : 0);
  }
}

function rgba(hex: string, alpha: number): string {
  const value = hex.replace('#', '');
  const red = parseInt(value.slice(0, 2), 16);
  const green = parseInt(value.slice(2, 4), 16);
  const blue = parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${Math.min(1, Math.max(0, alpha))})`;
}
