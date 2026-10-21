import { useEffect } from 'react';
import { useTimelineStore } from '../state/timelineStore';

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName.toLowerCase();
  return tag === 'input' || tag === 'textarea' || tag === 'select' || tag === 'button' || tag === 'a';
}

/**
 * One rAF clock for playback. Timing lives here; the store owns the actual
 * advance/stop decision. Reduced motion is handled by the map crossfade
 * (instant opacity), never by freezing the transport.
 */
export function usePlayback(): void {
  useEffect(() => {
    let animationFrame = 0;
    let lastTimestamp = 0;

    const stopClock = () => {
      if (animationFrame !== 0) {
        cancelAnimationFrame(animationFrame);
        animationFrame = 0;
      }
      lastTimestamp = 0;
    };

    const tick = (timestamp: number) => {
      animationFrame = 0;
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

      const delta = lastTimestamp === 0 ? 0 : Math.max(0, timestamp - lastTimestamp);
      lastTimestamp = timestamp;
      state.tick(delta);

      if (!useTimelineStore.getState().playing) {
        stopClock();
        return;
      }
      animationFrame = requestAnimationFrame(tick);
    };

    const startClock = () => {
      stopClock();
      animationFrame = requestAnimationFrame(tick);
    };

    // Zustand v5 calls listeners with (state, previousState).
    const unsubscribe = useTimelineStore.subscribe((state, previous) => {
      if (state.playing && !previous.playing) startClock();
      else if (!state.playing && previous.playing) stopClock();
    });

    // A remount (StrictMode, HMR) must not strand a playing transport.
    if (useTimelineStore.getState().playing) startClock();

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
