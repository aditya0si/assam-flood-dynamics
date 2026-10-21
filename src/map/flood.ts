import type { ImageSource, Map as MapLibreMap } from 'maplibre-gl';
import type { FrameIndex } from '../data/schemas';
import { dataUrl } from '../data/loadData';
import { prefersReducedMotion } from '../lib/motion';
import {
  CROSSFADE_MS,
  FLOOD_CURRENT_LAYER_ID,
  FLOOD_CURRENT_SOURCE_ID,
  FLOOD_OPACITY,
  FLOOD_OUTGOING_LAYER_ID,
  FLOOD_OUTGOING_SOURCE_ID,
} from './mapConfig';

interface FloodHooks {
  onFrameError?: (step: number) => void;
  /** Fires when a frame has actually been handed to both image sources. */
  onFrameApplied?: (step: number, file: string) => void;
}

export interface FloodController {
  start: (initialStep: number) => Promise<boolean>;
  goToStep: (step: number) => void;
  destroy: () => void;
}

/**
 * Two image sources, one working frame each. A step change updates the image
 * source URLs and animates raster-opacity only: no source remove/add, no
 * re-tiling, no GeoJSON parse. Each URL is preloaded as an Image first so the
 * browser cache usually has the PNG before MapLibre swaps it in.
 */
export function createFloodController(
  map: MapLibreMap,
  frameIndex: FrameIndex,
  hooks: FloodHooks = {},
): FloodController {
  const images = new Map<number, HTMLImageElement>();
  const pending = new Map<number, Promise<HTMLImageElement>>();
  let displayedStep = -1;
  let displayedUrl: string | null = null;
  let requestId = 0;
  let animationFrame = 0;
  let destroyed = false;

  const frameCount = frameIndex.steps.length;

  const frameUrl = (step: number): string => dataUrl(`flood/${frameIndex.steps[step].file}`);

  const loadFrame = (step: number): Promise<HTMLImageElement> => {
    const cached = images.get(step);
    if (cached && cached.complete && cached.naturalWidth > 0) return Promise.resolve(cached);

    const inFlight = pending.get(step);
    if (inFlight) return inFlight;

    const frame = frameIndex.steps[step];
    const promise = new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.decoding = 'async';
      image.onload = () => {
        pending.delete(step);
        images.set(step, image);
        resolve(image);
      };
      image.onerror = () => {
        pending.delete(step);
        reject(new Error(`Unable to decode flood frame ${frame.file}`));
      };
      image.src = frameUrl(step);
    });
    pending.set(step, promise);
    return promise;
  };

  const prefetch = (step: number): void => {
    if (step < 0 || step >= frameCount || images.has(step) || pending.has(step)) return;
    void loadFrame(step).catch(() => undefined);
  };

  const setRasterOpacity = (layerId: string, opacity: number): void => {
    if (!map.getLayer(layerId)) return;
    map.setPaintProperty(layerId, 'raster-opacity', opacity);
  };

  const stopAnimation = (): void => {
    if (animationFrame !== 0) {
      cancelAnimationFrame(animationFrame);
      animationFrame = 0;
    }
  };

  const applyOpacity = (): void => {
    setRasterOpacity(FLOOD_OUTGOING_LAYER_ID, 0);
    setRasterOpacity(FLOOD_CURRENT_LAYER_ID, FLOOD_OPACITY);
  };

  const crossfade = (): void => {
    stopAnimation();
    if (prefersReducedMotion()) {
      applyOpacity();
      return;
    }

    setRasterOpacity(FLOOD_OUTGOING_LAYER_ID, FLOOD_OPACITY);
    setRasterOpacity(FLOOD_CURRENT_LAYER_ID, 0);
    const startedAt = performance.now();

    const frame = (now: number) => {
      if (destroyed) return;
      const progress = Math.min(1, (now - startedAt) / CROSSFADE_MS);
      setRasterOpacity(FLOOD_OUTGOING_LAYER_ID, FLOOD_OPACITY * (1 - progress));
      setRasterOpacity(FLOOD_CURRENT_LAYER_ID, FLOOD_OPACITY * progress);
      if (progress < 1) {
        animationFrame = requestAnimationFrame(frame);
      } else {
        animationFrame = 0;
        setRasterOpacity(FLOOD_OUTGOING_LAYER_ID, 0);
        setRasterOpacity(FLOOD_CURRENT_LAYER_ID, FLOOD_OPACITY);
      }
    };
    animationFrame = requestAnimationFrame(frame);
  };

  const prune = (step: number): void => {
    const keep = new Set([step - 1, step, step + 1]);
    for (const key of Array.from(images.keys())) {
      if (!keep.has(key)) images.delete(key);
    }
  };

  const updateImageSources = (outgoingUrl: string, currentUrl: string): boolean => {
    const outgoing = map.getSource<ImageSource>(FLOOD_OUTGOING_SOURCE_ID);
    const current = map.getSource<ImageSource>(FLOOD_CURRENT_SOURCE_ID);
    if (!outgoing || !current) return false;
    outgoing.updateImage({ url: outgoingUrl });
    current.updateImage({ url: currentUrl });
    return true;
  };

  const applyStep = async (step: number, animate: boolean, id: number): Promise<boolean> => {
    const clamped = Math.max(0, Math.min(step, frameCount - 1));
    if (clamped === displayedStep && displayedUrl) return true;

    try {
      await loadFrame(clamped);
    } catch {
      if (id === requestId) hooks.onFrameError?.(clamped);
      return false;
    }
    if (destroyed || id !== requestId) return false;

    const nextUrl = frameUrl(clamped);
    const outgoingUrl = displayedUrl ?? nextUrl;
    if (!updateImageSources(outgoingUrl, nextUrl)) {
      if (id === requestId) hooks.onFrameError?.(clamped);
      return false;
    }

    displayedUrl = nextUrl;
    displayedStep = clamped;
    hooks.onFrameApplied?.(clamped, frameIndex.steps[clamped].file);

    if (animate) crossfade();
    else applyOpacity();

    prefetch(clamped + 1);
    prune(clamped);
    return true;
  };

  const goToStep = (step: number): void => {
    const id = ++requestId;
    void applyStep(step, true, id);
  };

  return {
    start: async (initialStep: number) => {
      const id = ++requestId;
      const applied = await applyStep(initialStep, false, id);
      prefetch(initialStep + 1);
      return applied;
    },
    goToStep,
    destroy: () => {
      destroyed = true;
      requestId += 1;
      stopAnimation();
      images.clear();
      pending.clear();
      displayedUrl = null;
    },
  };
}
