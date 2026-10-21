import {
  DISTRICT_LAYER_ID,
  FLOOD_CURRENT_LAYER_ID,
  FLOOD_OPACITY,
  FLOOD_OUTGOING_LAYER_ID,
  HOTSPOTS_LAYER_ID,
  RIVERS_LAYER_ID,
  RISK_ZONE_FILL_LAYER_ID,
  RISK_ZONE_LINE_LAYER_ID,
  TERRAIN_HILLSHADE_LAYER_ID,
} from './mapConfig';

export type LayerId = 'flood' | 'risk-zones' | 'rivers' | 'districts' | 'hillshade' | 'hotspots';

export type BaseMode = 'imagery' | 'hillshade';

export interface LayerSpec {
  id: LayerId;
  label: string;
  group: 'Hazard' | 'Context' | 'Base';
  kind: 'raster' | 'fill' | 'line' | 'circle' | 'hillshade';
  styleLayerIds: string[];
  defaultVisible: boolean;
  defaultOpacity: number;
  class: string;
  dataPath: string;
  note: string;
}

export const LAYERS: LayerSpec[] = [
  {
    id: 'flood',
    label: 'Scenario flood extent',
    group: 'Hazard',
    kind: 'raster',
    styleLayerIds: [FLOOD_OUTGOING_LAYER_ID, FLOOD_CURRENT_LAYER_ID],
    defaultVisible: true,
    defaultOpacity: FLOOD_OPACITY,
    class: 'scenario',
    dataPath: 'data/flood/frames/',
    note: 'HAND-threshold depth bands, one PNG per step.',
  },
  {
    id: 'risk-zones',
    label: 'Risk zones',
    group: 'Hazard',
    kind: 'fill',
    styleLayerIds: [RISK_ZONE_FILL_LAYER_ID, RISK_ZONE_LINE_LAYER_ID],
    defaultVisible: true,
    defaultOpacity: 0.34,
    class: 'derived',
    dataPath: 'data/risk/risk-zones.geojson',
    note: 'HAND × scenario-duration classes. Drawn beneath the flood.',
  },
  {
    id: 'rivers',
    label: 'Rivers',
    group: 'Context',
    kind: 'line',
    styleLayerIds: [RIVERS_LAYER_ID],
    defaultVisible: true,
    defaultOpacity: 0.78,
    class: 'source',
    dataPath: 'data/hydro/assam-rivers.geojson',
    note: 'Mapped OSM river centrelines; sand-toned so they never read as flood.',
  },
  {
    id: 'districts',
    label: 'District boundaries',
    group: 'Context',
    kind: 'line',
    styleLayerIds: [DISTRICT_LAYER_ID],
    defaultVisible: true,
    defaultOpacity: 0.72,
    class: 'source',
    dataPath: 'data/admin/assam-districts.geojson',
    note: 'geoBoundaries ADM2 outlines with derived risk-class tint.',
  },
  {
    id: 'hillshade',
    label: 'Terrain hillshade',
    group: 'Base',
    kind: 'hillshade',
    styleLayerIds: [TERRAIN_HILLSHADE_LAYER_ID],
    defaultVisible: true,
    defaultOpacity: 0.28,
    class: 'source',
    dataPath: 'data/basemap/assam-hillshade.webp',
    note: 'Terrarium DEM relief, 315°/45°. Vertical exaggeration is readability only.',
  },
  {
    id: 'hotspots',
    label: 'Inundation hotspots',
    group: 'Hazard',
    kind: 'circle',
    styleLayerIds: [HOTSPOTS_LAYER_ID],
    defaultVisible: true,
    defaultOpacity: 1,
    class: 'derived',
    dataPath: 'data/risk/hotspots.geojson',
    note: 'Low-HAND backwater pockets. These are not embankment breaches.',
  },
];

export const LAYER_BY_ID: Record<LayerId, LayerSpec> = Object.fromEntries(
  LAYERS.map((layer) => [layer.id, layer]),
) as Record<LayerId, LayerSpec>;

export const LAYER_IDS: LayerId[] = LAYERS.map((layer) => layer.id);

export function clampOpacity(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}
