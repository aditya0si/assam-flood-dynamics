import type {
  ErrorEvent as MapLibreErrorEvent,
  Map as MapLibreMap,
  MapSourceDataEvent,
} from 'maplibre-gl';
import {
  BACKGROUND_LAYER_ID,
  IMAGERY_SOURCE_ID,
  MAX_PITCH,
  TERRAIN_EXAGGERATION,
  TERRAIN_HILLSHADE_SOURCE_ID,
  TERRAIN_SOURCE_ID,
  TILE_HEALTH_TIMEOUT_MS,
} from './mapConfig';
import {
  deriveSourceStatus,
  newSourceStats,
  type SourceHealthStats,
  type TileHealthSnapshot,
} from './tileHealthState';

export type {
  HealthTone,
  TileHealthCopy,
  TileHealthLevel,
  TileHealthSnapshot,
  TileStatus,
} from './tileHealthState';

type HealthListener = (snapshot: TileHealthSnapshot) => void;

export interface TileHealthTracker {
  destroy: () => void;
}

interface TrackerState {
  dem: SourceHealthStats;
  imagery: SourceHealthStats;
}

function isDemSource(sourceId?: string): boolean {
  return sourceId === TERRAIN_SOURCE_ID;
}

function isTrackedSource(sourceId?: string): boolean {
  return (
    isDemSource(sourceId) ||
    sourceId === TERRAIN_HILLSHADE_SOURCE_ID ||
    sourceId === IMAGERY_SOURCE_ID
  );
}

/**
 * Keeps the health matrix honest: every status is an aggregate of real tile
 * outcomes. Offline is never a timer-only verdict while a later success can
 * still arrive, and the imagery layer is left mounted so a recovering host can
 * be observed and recovered.
 */
export function createTileHealthTracker(map: MapLibreMap, onChange: HealthListener): TileHealthTracker {
  const state: TrackerState = { dem: newSourceStats(), imagery: newSourceStats() };
  let destroyed = false;
  let lastKey = '';
  let terrainDisabled = false;

  const statsFor = (sourceId?: string): SourceHealthStats | null => {
    if (isDemSource(sourceId)) return state.dem;
    if (sourceId === IMAGERY_SOURCE_ID) return state.imagery;
    return null;
  };

  const snapshot = (): TileHealthSnapshot => ({
    dem: deriveSourceStatus(state.dem),
    imagery: deriveSourceStatus(state.imagery),
  });

  const emit = (force = false) => {
    const next = snapshot();
    const key = `${next.dem}:${next.imagery}`;
    if (!force && key === lastKey) return;
    lastKey = key;
    onChange(next);
  };

  const applyFallbacks = () => {
    if (!map.getLayer(BACKGROUND_LAYER_ID)) return;
    const dem = deriveSourceStatus(state.dem);

    if (dem === 'offline') {
      map.setTerrain(null);
      map.setMaxPitch(24);
      map.jumpTo({ pitch: Math.min(map.getPitch(), 20) });
      terrainDisabled = true;
      return;
    }

    if (dem === 'live' && terrainDisabled) {
      map.setMaxPitch(MAX_PITCH);
      map.setTerrain({ source: TERRAIN_SOURCE_ID, exaggeration: TERRAIN_EXAGGERATION });
      terrainDisabled = false;
    }
  };

  const settle = () => {
    emit();
    applyFallbacks();
  };

  const onSourceLoading = (event: MapSourceDataEvent) => {
    if (destroyed) return;
    const stats = statsFor(event.sourceId);
    if (!stats || !event.tile) return;
    stats.pending += 1;
  };

  const onSourceData = (event: MapSourceDataEvent) => {
    if (destroyed) return;
    const stats = statsFor(event.sourceId);
    if (!stats || !event.tile) return;
    // Any tile that reaches sourcedata resolved successfully.
    stats.pending = Math.max(0, stats.pending - 1);
    stats.successes += 1;
    stats.consecutiveErrors = 0;
    stats.lastOutcome = 'success';
    settle();
  };

  const onSourceAbort = (event: MapSourceDataEvent) => {
    if (destroyed) return;
    const stats = statsFor(event.sourceId);
    if (!stats || !event.tile) return;
    stats.pending = Math.max(0, stats.pending - 1);
  };

  const onError = (event: MapLibreErrorEvent) => {
    if (destroyed) return;
    const sourceEvent = event as MapLibreErrorEvent & { sourceId?: string; preventDefault?: () => void };
    if (!isTrackedSource(sourceEvent.sourceId)) return;
    sourceEvent.preventDefault?.();
    const stats = statsFor(sourceEvent.sourceId);
    if (!stats) return;
    stats.pending = Math.max(0, stats.pending - 1);
    stats.errors += 1;
    stats.consecutiveErrors += 1;
    stats.lastOutcome = 'error';
    settle();
  };

  map.on('sourcedataloading', onSourceLoading);
  map.on('sourcedata', onSourceData);
  map.on('sourcedataabort', onSourceAbort);
  map.on('error', onError);

  // One 6 s window is not enough to call a still-pending host offline; a second
  // window without a single resolved tile is.
  const timer = window.setInterval(() => {
    if (destroyed) return;
    state.dem.timeoutRounds += 1;
    state.imagery.timeoutRounds += 1;
    settle();
  }, TILE_HEALTH_TIMEOUT_MS);

  emit(true);

  return {
    destroy: () => {
      destroyed = true;
      window.clearInterval(timer);
      map.off('sourcedataloading', onSourceLoading);
      map.off('sourcedata', onSourceData);
      map.off('sourcedataabort', onSourceAbort);
      map.off('error', onError);
    },
  };
}
