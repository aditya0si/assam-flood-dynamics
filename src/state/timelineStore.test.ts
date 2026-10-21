import test from 'node:test';
import assert from 'node:assert/strict';
import { PLAYBACK_STEP_MS, useTimelineStore } from './timelineStore.ts';

const store = useTimelineStore;

function reset(): void {
  store.setState({
    step: 0,
    playing: false,
    speed: 1,
    stepCount: 0,
    peakStep: 0,
    framesReady: false,
    accumulatorMs: 0,
  });
}

function readyAtStart(stepCount = 12): void {
  reset();
  store.getState().init(stepCount, Math.min(7, stepCount - 1));
  store.getState().setFramesReady(true);
}

test('store playback advances from 0 to 11 one step at a time and stops at the end', () => {
  readyAtStart();

  store.getState().play();
  assert.equal(store.getState().playing, true);

  const visited: number[] = [];
  for (let tick = 0; tick < 11; tick += 1) {
    store.getState().tick(PLAYBACK_STEP_MS);
    visited.push(store.getState().step);
  }

  assert.deepEqual(visited, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]);
  assert.equal(store.getState().playing, false);
  assert.equal(store.getState().step, 11);

  // The clock must not wrap or advance past the last step.
  store.getState().tick(PLAYBACK_STEP_MS);
  assert.equal(store.getState().step, 11);
  assert.equal(store.getState().playing, false);
});

test('pause holds the current step', () => {
  readyAtStart();
  store.getState().play();
  store.getState().tick(PLAYBACK_STEP_MS);
  store.getState().tick(PLAYBACK_STEP_MS);
  assert.equal(store.getState().step, 2);

  store.getState().pause();
  assert.equal(store.getState().playing, false);

  for (let tick = 0; tick < 5; tick += 1) store.getState().tick(PLAYBACK_STEP_MS);
  assert.equal(store.getState().step, 2);
});

test('next and previous move exactly one step and clamp at the ends', () => {
  readyAtStart();
  store.getState().setStep(5, 'user');
  store.getState().stepBy(1);
  assert.equal(store.getState().step, 6);
  store.getState().stepBy(-1);
  assert.equal(store.getState().step, 5);

  store.getState().setStep(0, 'user');
  store.getState().stepBy(-1);
  assert.equal(store.getState().step, 0);

  store.getState().setStep(11, 'user');
  store.getState().stepBy(1);
  assert.equal(store.getState().step, 11);
});

test('play on the last step restarts from 0', () => {
  readyAtStart();
  store.getState().setStep(11, 'user');
  store.getState().play();
  assert.equal(store.getState().step, 0);
  assert.equal(store.getState().playing, true);
  store.getState().tick(PLAYBACK_STEP_MS);
  assert.equal(store.getState().step, 1);
});

test('does not start until the local frame source is ready', () => {
  reset();
  store.getState().init(12, 7);
  store.getState().play();
  assert.equal(store.getState().playing, false);
  store.getState().setFramesReady(true);
  store.getState().play();
  assert.equal(store.getState().playing, true);
});

test('a long tick advances one visible step without skipping', () => {
  readyAtStart();
  store.getState().play();
  store.getState().tick(PLAYBACK_STEP_MS * 3);
  assert.equal(store.getState().step, 1);
  assert.equal(store.getState().playing, true);
});
