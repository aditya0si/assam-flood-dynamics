import { useEffect } from 'react';
import { useTimelineStore } from '../state/timelineStore';
import { prefersReducedMotion } from '../lib/motion';

const STEP_INTERVAL_MS = 1200;

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName.toLowerCase();
  return tag === 'input' || tag === 'textarea' || tag === 'select' || tag === 'button' || tag === 'a';
}

/**
 * One rAF clock for playback. The map subscribes to the store transiently;
 * this hook never causes a map re-render.
 */
export function usePlayback(): void {
  useEffect(() => {
    let animationFrame = 0;
    let lastTimestamp = 0;
    let accumulator = 0;

    const stopClock = () => {
      if (animationFrame !== 0) {
        cancelAnimationFrame(animationFrame);
        animationFrame = 0;
      }
      lastTimestamp = 0;
      accumulator = 0;
    };

    const tick = (timestamp: number) => {
      const state = useTimelineStore.getState();
      if (!state.playing) {
        stopClock();
        return;
      }
      if (document.hidden) {
        state.pause();
        stopClock();
        return;
      }

      if (lastTimestamp === 0) lastTimestamp = timestamp;
      accumulator += timestamp - lastTimestamp;
      lastTimestamp = timestamp;

      const interval = STEP_INTERVAL_MS / state.speed;
      while (accumulator >= interval) {
        accumulator -= interval;
        const before = useTimelineStore.getState().step;
        useTimelineStore.getState().stepBy(1);
        const after = useTimelineStore.getState().step;
        if (after === before) {
          useTimelineStore.getState().pause();
          stopClock();
          return;
        }
        if (after >= useTimelineStore.getState().stepCount - 1) {
          useTimelineStore.getState().pause();
          stopClock();
          return;
        }
      }

      animationFrame = requestAnimationFrame(tick);
    };

    const startClock = () => {
      stopClock();
      const state = useTimelineStore.getState();
      if (prefersReducedMotion()) {
        state.stepBy(1);
        state.pause();
        return;
      }
      animationFrame = requestAnimationFrame(tick);
    };

    const unsubscribe = useTimelineStore.subscribe((state, previous) => {
      if (state.playing && !previous.playing) startClock();
      else if (!state.playing && previous.playing) stopClock();
    });

    const onVisibilityChange = () => {
      if (document.hidden) useTimelineStore.getState().pause();
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      if (isEditableTarget(event.target)) return;

      const state = useTimelineStore.getState();
      if (state.stepCount <= 0) return;

      switch (event.key) {
        case ' ':
        case 'Spacebar':
          event.preventDefault();
          state.toggle();
          break;
        case 'ArrowLeft':
          event.preventDefault();
          state.stepBy(-1);
          break;
        case 'ArrowRight':
          event.preventDefault();
          state.stepBy(1);
          break;
        case 'Home':
          event.preventDefault();
          state.setStep(0, 'user');
          break;
        case 'End':
          event.preventDefault();
          state.setStep(state.stepCount - 1, 'user');
          break;
        case 'PageUp':
          event.preventDefault();
          state.stepBy(3);
          break;
        case 'PageDown':
          event.preventDefault();
          state.stepBy(-3);
          break;
        default:
          break;
      }
    };

    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('keydown', onKeyDown);

    return () => {
      stopClock();
      unsubscribe();
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, []);
}
