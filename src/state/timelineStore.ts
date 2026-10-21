import { create } from 'zustand';

export type Speed = 0.5 | 1 | 2;
export type StepSource = 'user' | 'playback' | 'url' | 'init';

/** One visible step per interval at 1x. Reduced motion shortens the crossfade, not the clock. */
export const PLAYBACK_STEP_MS = 1200;

interface TimelineState {
  step: number;
  playing: boolean;
  speed: Speed;
  stepCount: number;
  peakStep: number;
  framesReady: boolean;
  /** Milliseconds accumulated since the last visible step. */
  accumulatorMs: number;
  init: (stepCount: number, peakStep: number) => void;
  setStep: (step: number, source?: StepSource) => void;
  stepBy: (delta: number) => void;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  setSpeed: (speed: Speed) => void;
  setFramesReady: (ready: boolean) => void;
  /**
   * Advance the clock by `deltaMs`. The rAF loop only feeds time; the store owns
   * the decision to advance and to stop at the last step, which keeps playback
   * testable without a browser or a map.
   */
  tick: (deltaMs: number, intervalMs?: number) => void;
}

export const useTimelineStore = create<TimelineState>((set, get) => ({
  step: 0,
  playing: false,
  speed: 1,
  stepCount: 0,
  peakStep: 0,
  framesReady: false,
  accumulatorMs: 0,

  init: (stepCount, peakStep) =>
    set({
      step: 0,
      playing: false,
      stepCount,
      peakStep,
      framesReady: false,
      accumulatorMs: 0,
    }),

  setStep: (step, _source = 'user') => {
    const { stepCount, step: current } = get();
    if (stepCount <= 0) return;
    const next = Math.max(0, Math.min(Math.trunc(step), stepCount - 1));
    if (next === current) return;
    set({ step: next, accumulatorMs: 0 });
  },

  stepBy: (delta) => {
    const { step, stepCount } = get();
    if (stepCount <= 0) return;
    const next = Math.max(0, Math.min(step + Math.trunc(delta), stepCount - 1));
    if (next === step) return;
    set({ step: next, accumulatorMs: 0 });
  },

  play: () => {
    const { playing, step, stepCount, framesReady } = get();
    if (playing || stepCount <= 0 || !framesReady) return;
    // Restarting from the last step rewinds first, so the whole scenario plays.
    if (step >= stepCount - 1) set({ step: 0, playing: true, accumulatorMs: 0 });
    else set({ playing: true, accumulatorMs: 0 });
  },

  pause: () => {
    if (!get().playing) return;
    set({ playing: false, accumulatorMs: 0 });
  },

  toggle: () => {
    if (get().playing) get().pause();
    else get().play();
  },

  setSpeed: (speed) => {
    if (speed !== 0.5 && speed !== 1 && speed !== 2) return;
    set({ speed });
  },

  setFramesReady: (ready) => set({ framesReady: ready }),

  tick: (deltaMs, intervalMs) => {
    const { playing, step, stepCount, speed, accumulatorMs } = get();
    if (!playing || stepCount <= 0 || !Number.isFinite(deltaMs) || deltaMs <= 0) return;

    const interval =
      intervalMs !== undefined && Number.isFinite(intervalMs) && intervalMs > 0
        ? intervalMs
        : PLAYBACK_STEP_MS / speed;
    const accumulated = accumulatorMs + deltaMs;

    // At most one step per tick: a stalled frame moves the scenario forward by
    // one frame, never skips several crossfades at once.
    if (accumulated < interval) {
      set({ accumulatorMs: accumulated });
      return;
    }

    if (step >= stepCount - 1) {
      set({ playing: false, accumulatorMs: 0 });
      return;
    }

    const next = step + 1;
    // Drop any excess time after a visible step so a throttled frame cannot
    // cause a burst of several steps on the next frames.
    if (next >= stepCount - 1) {
      set({ step: next, playing: false, accumulatorMs: 0 });
    } else {
      set({ step: next, accumulatorMs: 0 });
    }
  },
}));
