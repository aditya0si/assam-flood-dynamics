import test from 'node:test';
import assert from 'node:assert/strict';
import {
  deriveOverallHealth,
  deriveSourceStatus,
  tileHealthCopy,
  type SourceHealthStats,
} from './tileHealthState.ts';

function stats(overrides: Partial<SourceHealthStats> = {}): SourceHealthStats {
  return {
    successes: 0,
    errors: 0,
    consecutiveErrors: 0,
    pending: 0,
    lastOutcome: 'none',
    timeoutRounds: 0,
    offlineConfirmed: false,
    ...overrides,
  };
}

test('never claims live before a tile resolves', () => {
  assert.equal(deriveSourceStatus(stats()), 'loading');
  assert.equal(deriveSourceStatus(stats({ pending: 1 })), 'loading');
  assert.equal(deriveOverallHealth({ dem: 'loading', imagery: 'loading' }), 'degraded');
  assert.equal(tileHealthCopy({ dem: 'loading', imagery: 'loading' }).text, 'Connecting to tile hosts');
});

test('only reaches live when both sources have a resolved tile', () => {
  assert.equal(deriveOverallHealth({ dem: 'live', imagery: 'loading' }), 'degraded');
  assert.equal(deriveOverallHealth({ dem: 'live', imagery: 'live' }), 'live');
  assert.equal(tileHealthCopy({ dem: 'live', imagery: 'live' }).text, 'Terrain and imagery live');
});

test('does not call a source offline while a request is pending in the first window', () => {
  assert.equal(deriveSourceStatus(stats({ pending: 1, timeoutRounds: 1 })), 'degraded');
  assert.equal(deriveSourceStatus(stats({ timeoutRounds: 2 })), 'offline');
});

test('confirmed both-host errors are degraded first, then offline', () => {
  const failed = { errors: 1, lastOutcome: 'error' as const };
  assert.equal(deriveSourceStatus(stats(failed)), 'degraded');
  assert.equal(deriveSourceStatus(stats({ ...failed, offlineConfirmed: true })), 'offline');
  assert.equal(
    deriveSourceStatus(stats({ ...failed, successes: 1, offlineConfirmed: true })),
    'live',
  );
});

test('never calls a source offline after a success', () => {
  const recovered = stats({ successes: 4, errors: 2, consecutiveErrors: 2, lastOutcome: 'error' });
  assert.notEqual(deriveSourceStatus(recovered), 'offline');
  assert.equal(deriveSourceStatus({ ...recovered, consecutiveErrors: 3 }), 'degraded');
  assert.equal(
    deriveSourceStatus({ ...recovered, successes: 5, consecutiveErrors: 0, lastOutcome: 'success' }),
    'live',
  );
});

test('shared copy agrees when imagery is offline and terrain is live', () => {
  const snapshot = { dem: 'live' as const, imagery: 'offline' as const };
  assert.equal(deriveOverallHealth(snapshot), 'degraded');
  assert.deepEqual(tileHealthCopy(snapshot), {
    level: 'degraded',
    text: 'Imagery offline · hillshade terrain',
    tone: 'warn',
  });
});

test('does not claim imagery relief is live while the DEM is still pending', () => {
  const snapshot = { dem: 'loading' as const, imagery: 'offline' as const };
  assert.equal(tileHealthCopy(snapshot).text, 'Imagery offline · terrain pending');
  assert.equal(
    tileHealthCopy({ dem: 'offline', imagery: 'loading' }).text,
    '3D terrain offline · imagery pending',
  );
});

test('reports both hosts offline only when neither has a success', () => {
  const snapshot = { dem: 'offline' as const, imagery: 'offline' as const };
  assert.equal(deriveOverallHealth(snapshot), 'offline');
  assert.equal(tileHealthCopy(snapshot).text, 'Tile hosts offline · committed relief');
});
