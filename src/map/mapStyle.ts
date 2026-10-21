import type {
  LayerSpecification,
  Map as MapLibreMap,
  StyleSpecification,
} from 'maplibre-gl';
import type { Dataset } from '../data/types';
import { dataUrl } from '../data/loadData';
import { MAP_ATTRIBUTION } from '../data/attribution';
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
  IMAGERY_LAYER_ID,
  IMAGERY_SOURCE_ID,
  RIVERS_LAYER_ID,
  RIVERS_SOURCE_ID,
  STATE_LAYER_ID,
  STATE_SOURCE_ID,
  TERRAIN_EXAGGERATION,
  TERRAIN_HILLSHADE_LAYER_ID,
  TERRAIN_HILLSHADE_SOURCE_ID,
  TERRAIN_SOURCE_ID,
  TERRARIUM_TILES,
  bboxCoordinates,
} from './mapConfig';

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
        'hillshade-exaggeration': 0.34,
        'hillshade-illumination-direction': 315,
        'hillshade-illumination-altitude': 45,
        'hillshade-shadow-color': '#04121a',
        'hillshade-highlight-color': '#e9f2f5',
        'hillshade-accent-color': '#68818c',
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
        'raster-resampling': 'linear',
      },
    },
    {
      id: RIVERS_LAYER_ID,
      type: 'line',
      source: RIVERS_SOURCE_ID,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#7cc7e8',
        'line-width': ['match', ['get', 'order'], 1, 1.8, 2, 1.05, 0.6],
        'line-opacity': 0.82,
      },
    },
    {
      id: DISTRICT_LAYER_ID,
      type: 'line',
      source: DISTRICTS_SOURCE_ID,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#9db4bf',
        'line-width': 0.7,
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
