import { useEffect, useRef, useState } from 'react';
import maplibregl, {
  AttributionControl,
  LngLatBounds,
  Map as MapLibreMap,
  NavigationControl,
  ScaleControl,
  type ErrorEvent as MapLibreErrorEvent,
} from 'maplibre-gl';
import type { Dataset } from '../data/types';
import { useTimelineStore } from '../state/timelineStore';
import { useTileHealthStore } from '../state/tileHealthStore';
import { badgeFor } from '../data/labels';
import { formatDepthBand, formatStage, formatStepNumber } from '../data/format';
import { dataUrl } from '../data/loadData';
import { createFloodController, type FloodController } from './flood';
import {
  AOI_CORE_BOUNDS,
  BACKGROUND_LAYER_ID,
  FLOOD_CURRENT_SOURCE_ID,
  FLOOD_OUTGOING_SOURCE_ID,
  HOME_BEARING,
  HOME_PITCH,
  HOME_ZOOM,
  MAX_BOUNDS,
  MAX_PITCH,
  MAX_ZOOM,
  MIN_ZOOM,
  bboxCenter,
} from './mapConfig';
import { buildMapStyle, setTerrain } from './mapStyle';
import { createTileHealthTracker, type TileHealthTracker } from './tileHealth';
import { tileHealthCopy } from './tileHealthState';
import styles from './map.module.css';

interface MapCanvasProps {
  dataset: Dataset;
}

export function MapCanvas({ dataset }: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const floodRef = useRef<FloodController | null>(null);
  const visibleFrameRef = useRef('');
  const readyRef = useRef(false);
  const [webglError, setWebglError] = useState(false);
  const [frameError, setFrameError] = useState(false);
  const health = useTileHealthStore((state) => state.snapshot);
  const healthLevel = useTileHealthStore((state) => state.level);
  const status = tileHealthCopy(health);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Reset the single shared health record for this map instance.
    useTileHealthStore.getState().reset();
    readyRef.current = false;
    visibleFrameRef.current = '';
    container.setAttribute('data-ready', 'false');
    container.setAttribute('data-step', String(useTimelineStore.getState().step));
    container.setAttribute('data-frame-file', '');

    // The probe is a live view of the store, not a snapshot that can drift.
    const probe = Object.freeze({
      get step(): number {
        return useTimelineStore.getState().step;
      },
      get frameFile(): string {
        return visibleFrameRef.current;
      },
      get isPlaying(): boolean {
        return useTimelineStore.getState().playing;
      },
      get tileHealth(): 'live' | 'degraded' | 'offline' {
        return useTileHealthStore.getState().level;
      },
    });
    Object.defineProperty(window, '__baanh', {
      value: probe,
      writable: false,
      configurable: true,
      enumerable: true,
    });

    let map: MapLibreMap;
    try {
      map = new maplibregl.Map({
        container,
        style: buildMapStyle(dataset),
        center: bboxCenter(AOI_CORE_BOUNDS),
        zoom: HOME_ZOOM,
        pitch: HOME_PITCH,
        bearing: HOME_BEARING,
        maxBounds: new LngLatBounds([MAX_BOUNDS[0][0], MAX_BOUNDS[0][1]], [MAX_BOUNDS[1][0], MAX_BOUNDS[1][1]]),
        minZoom: MIN_ZOOM,
        maxZoom: MAX_ZOOM,
        maxPitch: MAX_PITCH,
        renderWorldCopies: false,
        dragRotate: true,
        touchPitch: true,
        canvasContextAttributes: { antialias: true },
        attributionControl: false,
      });
    } catch {
      setWebglError(true);
      return;
    }

    mapRef.current = map;
    map.addControl(new NavigationControl({ visualizePitch: true, showCompass: true }), 'top-right');
    map.addControl(new ScaleControl({ unit: 'metric', maxWidth: 96 }), 'bottom-right');
    map.addControl(new AttributionControl({ compact: true }), 'bottom-right');

    const bounds = new LngLatBounds(
      [AOI_CORE_BOUNDS[0], AOI_CORE_BOUNDS[1]],
      [AOI_CORE_BOUNDS[2], AOI_CORE_BOUNDS[3]],
    );

    const updateAriaLabel = (step: number) => {
      const summary = dataset.summary.steps[step];
      if (!summary || !container) return;
      container.setAttribute(
        'aria-label',
        `Oblique terrain map of Assam; scenario flood extent at ${formatStepNumber(
          step,
          dataset.summary.steps.length,
        )}, ${summary.step_label}, scenario stage ${formatStage(summary.stage_m)} metres.`,
      );
    };

    const onMapError = (event: MapLibreErrorEvent) => {
      const sourceEvent = event as MapLibreErrorEvent & { sourceId?: string; preventDefault?: () => void };
      if (sourceEvent.sourceId === FLOOD_CURRENT_SOURCE_ID || sourceEvent.sourceId === FLOOD_OUTGOING_SOURCE_ID) {
        sourceEvent.preventDefault?.();
        setFrameError(true);
      }
    };
    map.on('error', onMapError);

    const healthTracker: TileHealthTracker = createTileHealthTracker(map, (snapshot) => {
      useTileHealthStore.getState().setSnapshot(snapshot);
    });

    const markReady = () => {
      if (readyRef.current) return;
      readyRef.current = true;
      container.setAttribute('data-ready', 'true');
    };

    let sceneStarted = false;
    let readyFallback = 0;

    // style.load / styledata mean the style document is installed; they do not
    // wait for remote tiles (map 'load' does, and that is what froze playback).
    const startScene = () => {
      if (sceneStarted || mapRef.current !== map) return;
      // The layer exists once the style document is parsed; unlike map 'load'
      // this does not wait for remote tiles to settle.
      if (!map.getLayer(BACKGROUND_LAYER_ID) || !map.getSource(FLOOD_CURRENT_SOURCE_ID)) return;
      sceneStarted = true;
      map.off('styledata', startScene);
      map.off('style.load', startScene);

      setTerrain(map, true);
      const camera = map.cameraForBounds(bounds, {
        padding: 28,
        pitch: HOME_PITCH,
        bearing: HOME_BEARING,
      });
      if (camera?.center && typeof camera.zoom === 'number') {
        map.jumpTo({
          center: camera.center,
          zoom: camera.zoom,
          pitch: HOME_PITCH,
          bearing: HOME_BEARING,
        });
      } else {
        map.jumpTo({
          center: bboxCenter(AOI_CORE_BOUNDS),
          zoom: HOME_ZOOM,
          pitch: HOME_PITCH,
          bearing: HOME_BEARING,
        });
      }
      updateAriaLabel(useTimelineStore.getState().step);

      const controller = createFloodController(map, dataset.frameIndex, {
        onFrameError: () => setFrameError(true),
        onFrameApplied: (_step, file) => {
          visibleFrameRef.current = file;
          container.setAttribute('data-frame-file', file);
          markReady();
        },
      });
      floodRef.current = controller;

      // The transport depends on the local PNG renderer, never on remote tiles.
      // A failed frame is reported in the UI but must not disable Play forever.
      useTimelineStore.getState().setFramesReady(true);

      const initialStep = useTimelineStore.getState().step;
      void controller.start(initialStep).then(() => {
        map.triggerRepaint();
      });
      // If the first local frame cannot decode, the style and terrain are still
      // a ready map; do not leave data-ready false forever.
      readyFallback = window.setTimeout(markReady, 2000);
    };

    map.on('styledata', startScene);
    map.on('style.load', startScene);
    // In case both events were already delivered before this listener.
    startScene();

    const unsubscribe = useTimelineStore.subscribe((state, previous) => {
      if (state.step === previous.step) return;
      container.setAttribute('data-step', String(state.step));
      floodRef.current?.goToStep(state.step);
      updateAriaLabel(state.step);
    });

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(container);

    return () => {
      window.clearTimeout(readyFallback);
      unsubscribe();
      resizeObserver.disconnect();
      healthTracker.destroy();
      floodRef.current?.destroy();
      floodRef.current = null;
      map.off('styledata', startScene);
      map.off('style.load', startScene);
      map.off('error', onMapError);
      map.remove();
      mapRef.current = null;
      if (window.__baanh) Reflect.deleteProperty(window, '__baanh');
    };
  }, [dataset]);

  const depthClasses = dataset.frameIndex.classes.filter((entry) => entry.id !== 0);
  const frameWidth = dataset.frameIndex.width;
  const frameHeight = dataset.frameIndex.height;
  const frameResolution = dataset.frameIndex.frame_resolution_m;
  const showHealthChip =
    healthLevel !== 'live' && !(health.dem === 'loading' && health.imagery === 'loading');

  return (
    <div className={styles.mapWrap}>
      {webglError ? (
        <div className={styles.webglFallback}>
          <img
            className={styles.webglImage}
            src={dataUrl('basemap/assam-hillshade.webp')}
            alt="Committed hillshade relief of Assam"
          />
          <p role="alert" className={styles.webglMessage}>
            WebGL2 is required for the 3D terrain view. The committed hillshade relief and every
            timeline readout remain available.
          </p>
        </div>
      ) : (
        <div
          ref={containerRef}
          className={styles.canvas}
          role="img"
          aria-label="Oblique terrain map of Assam; scenario flood extent"
          data-tile-health={healthLevel}
        />
      )}

      <div className={styles.legend} aria-label="Scenario flood depth classes">
        <div className={styles.legendHead}>
          <span>Scenario depth</span>
          <span className={styles.legendBadge}>{badgeFor(dataset.frameIndex.class)}</span>
        </div>
        <ul className={styles.legendList}>
          {depthClasses.map((entry) => (
            <li key={entry.id} className={styles.legendItem}>
              <span
                className={styles.swatch}
                style={{ backgroundColor: entry.color, opacity: Math.max(0.55, entry.alpha / 255) }}
              />
              <span>{formatDepthBand(entry.min_m, entry.max_m)}</span>
            </li>
          ))}
        </ul>
        <p className={styles.legendMeta}>
          {frameWidth} × {frameHeight} px · {formatStage(frameResolution)} m/px · classes from
          frame-index.json
        </p>
      </div>

      {showHealthChip ? (
        <div
          className={`${styles.degradedChip} ${styles[`health-${status.tone}`]}`}
          role="status"
          data-health-text={status.text}
        >
          {status.text}
        </div>
      ) : null}

      {frameError ? (
        <div className={styles.frameWarning} role="status">
          A flood frame could not be decoded; the timeline readouts are still data-backed.
        </div>
      ) : null}
    </div>
  );
}
