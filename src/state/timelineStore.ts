import { create } from 'zustand';

export type Speed = 0.5 | 1 | 2;
export type StepSource = 'user' | 'playback' | 'url' | 'init';

interface TimelineState {
  step: number;
  playing: boolean;
  speed: Speed;
  stepCount: number;
  peakStep: number;
  framesReady: boolean;
  init: (stepCount: number, peakStep: number) => void;
  setStep: (step: number, source?: StepSource) => void;
  stepBy: (delta: number) => void;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  setSpeed: (speed: Speed) => void;
  setFramesReady: (ready: boolean) => void;
}

export const useTimelineStore = create<TimelineState>((set, get) => ({
  step: 0,
  playing: false,
  speed: 1,
  stepCount: 0,
  peakStep: 0,
  framesReady: false,

  init: (stepCount, peakStep) =>
    set({
      step: 0,
      playing: false,
      stepCount,
      peakStep,
      framesReady: false,
    }),

  setStep: (step, _source = 'user') => {
    const { stepCount, step: current } = get();
    if (stepCount <= 0) return;
    const next = Math.max(0, Math.min(Math.trunc(step), stepCount - 1));
    if (next === current) return;
    set({ step: next });
  },

  stepBy: (delta) => {
    const { step, stepCount } = get();
    if (stepCount <= 0) return;
    const next = Math.max(0, Math.min(step + Math.trunc(delta), stepCount - 1));
    if (next === step) return;
    set({ step: next });
  },

  play: () => {
    const { playing, step, stepCount, framesReady } = get();
    if (playing || stepCount <= 0 || !framesReady) return;
    if (step >= stepCount - 1) set({ step: 0, playing: true });
    else set({ playing: true });
  },

  pause: () => {
    if (!get().playing) return;
    set({ playing: false });
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
}));
