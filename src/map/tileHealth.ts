import type { ErrorEvent as MapLibreErrorEvent, Map as MapLibreMap, MapSourceDataEvent } from 'maplibre-gl';
import {
  IMAGERY_LAYER_ID,
  IMAGERY_SOURCE_ID,
  TERRAIN_HILLSHADE_SOURCE_ID,
  TERRAIN_SOURCE_ID,
  TILE_HEALTH_TIMEOUT_MS,
} from './mapConfig';

export type TileStatus = 'loading' | 'ok' | 'degraded' | 'offline';

export interface TileHealthSnapshot {
  dem: TileStatus;
  imagery: TileStatus;
}

type HealthListener = (snapshot: TileHealthSnapshot) => void;

export interface TileHealthTracker {
  destroy: () => void;
}

/**
 * Keeps the fallback matrix honest: if a tile host produces no successful tile
 * within the timeout, or produces repeated errors, the matching layer is degraded
 * and the committed relief remains visible underneath.
 */
export function createTileHealthTracker(map: MapLibreMap, onChange: HealthListener): TileHealthTracker {
  let dem: TileStatus = 'loading';
  let imagery: TileStatus = 'loading';
  let demSucceeded = false;
  let imagerySucceeded = false;
  let demErrors = 0;
  let imageryErrors = 0;
  let destroyed = false;
  let lastKey = '';

  const emit = () => {
    const key = `${dem}:${imagery}`;
    if (key === lastKey) return;
    lastKey = key;
    onChange({ dem, imagery });
  };

  const applyOfflineFallbacks = () => {
    if (!map.isStyleLoaded()) return;
    if (imagery === 'offline') {
      if (map.getLayer(IMAGERY_LAYER_ID)) map.setLayoutProperty(IMAGERY_LAYER_ID, 'visibility', 'none');
    }
    if (dem === 'offline') {
      map.setTerrain(null);
      map.setMaxPitch(24);
      const targetPitch = imagery === 'offline' ? 0 : Math.min(map.getPitch(), 20);
      map.jumpTo({ pitch: targetPitch });
    }
  };

  const settle = (source: 'dem' | 'imagery', status: TileStatus) => {
    if (source === 'dem') dem = status;
    else imagery = status;
    emit();
    applyOfflineFallbacks();
  };

  const isDemSource = (sourceId?: string): boolean =>
    sourceId === TERRAIN_SOURCE_ID || sourceId === TERRAIN_HILLSHADE_SOURCE_ID;

  const onSourceData = (event: MapSourceDataEvent) => {
    if (destroyed) return;
    if (isDemSource(event.sourceId) && event.tile && !demSucceeded) {
      demSucceeded = true;
      settle('dem', 'ok');
    }
    if (event.sourceId === IMAGERY_SOURCE_ID && event.tile && !imagerySucceeded) {
      imagerySucceeded = true;
      settle('imagery', 'ok');
    }
  };

  const onError = (event: MapLibreErrorEvent) => {
    if (destroyed) return;
    const sourceEvent = event as MapLibreErrorEvent & { sourceId?: string; preventDefault?: () => void };
    if (!isDemSource(sourceEvent.sourceId) && sourceEvent.sourceId !== IMAGERY_SOURCE_ID) return;
    sourceEvent.preventDefault?.();
    if (isDemSource(sourceEvent.sourceId)) {
      demErrors += 1;
      if (!demSucceeded && demErrors >= 3) settle('dem', 'offline');
    } else {
      imageryErrors += 1;
      if (!imagerySucceeded && imageryErrors >= 3) settle('imagery', 'offline');
    }
  };

  map.on('sourcedata', onSourceData);
  map.on('error', onError);

  const timer = window.setTimeout(() => {
    if (destroyed) return;
    if (!demSucceeded) settle('dem', 'offline');
    if (!imagerySucceeded) settle('imagery', 'offline');
  }, TILE_HEALTH_TIMEOUT_MS);

  emit();

  return {
    destroy: () => {
      destroyed = true;
      window.clearTimeout(timer);
      map.off('sourcedata', onSourceData);
      map.off('error', onError);
    },
  };
}
