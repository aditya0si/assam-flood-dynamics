export type TileStatus = 'loading' | 'live' | 'degraded' | 'offline';
export type TileHealthLevel = 'live' | 'degraded' | 'offline';
export type HealthTone = 'ok' | 'warn' | 'bad' | 'loading';

export interface TileHealthSnapshot {
  dem: TileStatus;
  imagery: TileStatus;
}

export interface TileHealthCopy {
  level: TileHealthLevel;
  text: string;
  tone: HealthTone;
}

/** Consecutive failures before a source with no success is called offline. */
export const OFFLINE_AFTER_ERRORS = 3;
/** A source that never resolves is degraded after one window, offline after two. */
export const OFFLINE_AFTER_TIMEOUTS = 2;

export interface SourceHealthStats {
  successes: number;
  errors: number;
  consecutiveErrors: number;
  pending: number;
  lastOutcome: 'none' | 'success' | 'error';
  timeoutRounds: number;
}

export function newSourceStats(): SourceHealthStats {
  return {
    successes: 0,
    errors: 0,
    consecutiveErrors: 0,
    pending: 0,
    lastOutcome: 'none',
    timeoutRounds: 0,
  };
}

/**
 * Source health from request outcomes only.
 *
 * - loading: no success, no error and no elapsed window yet.
 * - live: at least one tile resolved and the last three outcomes were not failures.
 * - degraded: some requests failed (or are still pending past a window) but the
 *   source has not earned an offline claim.
 * - offline: three failures with no success, or two full windows without a
 *   single resolved tile.
 *
 * A source with a success can never be reported offline; a later success always
 * recovers the source.
 */
export function deriveSourceStatus(stats: SourceHealthStats): TileStatus {
  if (stats.successes > 0) {
    return stats.lastOutcome === 'error' && stats.consecutiveErrors >= OFFLINE_AFTER_ERRORS
      ? 'degraded'
      : 'live';
  }
  if (stats.errors >= OFFLINE_AFTER_ERRORS) return 'offline';
  if (stats.timeoutRounds >= OFFLINE_AFTER_TIMEOUTS) return 'offline';
  if (stats.errors > 0 || stats.timeoutRounds > 0) return 'degraded';
  return 'loading';
}

export function deriveOverallHealth(snapshot: TileHealthSnapshot): TileHealthLevel {
  const statuses: TileStatus[] = [snapshot.dem, snapshot.imagery];
  if (statuses.every((status) => status === 'offline')) return 'offline';
  if (statuses.includes('offline') || statuses.includes('degraded')) return 'degraded';
  // Loading is not live: never claim a tile host is live before it resolves.
  if (statuses.every((status) => status === 'live')) return 'live';
  return 'degraded';
}

/**
 * The single copy for both the map chip and the status bar. Both indicators call
 * this, so they cannot contradict each other.
 */
export function tileHealthCopy(snapshot: TileHealthSnapshot): TileHealthCopy {
  const level = deriveOverallHealth(snapshot);
  if (level === 'offline') {
    return { level, text: 'Tile hosts offline · committed relief', tone: 'bad' };
  }
  if (snapshot.imagery === 'offline') {
    return {
      level,
      text:
        snapshot.dem === 'live'
          ? 'Imagery offline · hillshade terrain'
          : 'Imagery offline · terrain pending',
      tone: 'warn',
    };
  }
  if (snapshot.dem === 'offline') {
    return {
      level,
      text:
        snapshot.imagery === 'live'
          ? '3D terrain offline · flat imagery'
          : '3D terrain offline · imagery pending',
      tone: 'warn',
    };
  }
  if (level === 'live') {
    return { level, text: 'Terrain and imagery live', tone: 'ok' };
  }
  if (snapshot.dem === 'loading' && snapshot.imagery === 'loading') {
    return { level, text: 'Connecting to tile hosts', tone: 'loading' };
  }
  if (snapshot.dem === 'live' && snapshot.imagery === 'loading') {
    return { level, text: 'Terrain live · imagery loading', tone: 'loading' };
  }
  if (snapshot.imagery === 'live' && snapshot.dem === 'loading') {
    return { level, text: 'Imagery live · terrain loading', tone: 'loading' };
  }
  return { level, text: 'Tile hosts degraded · overlays intact', tone: 'warn' };
}

export const INITIAL_TILE_HEALTH: TileHealthSnapshot = { dem: 'loading', imagery: 'loading' };
