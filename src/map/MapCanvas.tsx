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
import { badgeFor } from '../data/labels';
import { formatDepthBand, formatStage, formatStepNumber } from '../data/format';
import { dataUrl } from '../data/loadData';
import { createFloodController, type FloodController } from './flood';
import {
  FLOOD_CURRENT_SOURCE_ID,
  FLOOD_OUTGOING_SOURCE_ID,
  HOME_BEARING,
  HOME_PITCH,
  MAX_BOUNDS,
  MAX_PITCH,
  MAX_ZOOM,
  MIN_ZOOM,
  bboxCenter,
} from './mapConfig';
import { buildMapStyle, setTerrain } from './mapStyle';
import { createTileHealthTracker, type TileHealthSnapshot, type TileHealthTracker } from './tileHealth';
import styles from './map.module.css';

interface MapCanvasProps {
  dataset: Dataset;
  onHealthChange?: (snapshot: TileHealthSnapshot) => void;
}

export function MapCanvas({ dataset, onHealthChange }: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const floodRef = useRef<FloodController | null>(null);
  const onHealthRef = useRef(onHealthChange);
  const [webglError, setWebglError] = useState(false);
  const [frameError, setFrameError] = useState(false);
  const [health, setHealth] = useState<TileHealthSnapshot>({ dem: 'loading', imagery: 'loading' });

  useEffect(() => {
    onHealthRef.current = onHealthChange;
  }, [onHealthChange]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let map: MapLibreMap;
    try {
      map = new maplibregl.Map({
        container,
        style: buildMapStyle(dataset),
        center: bboxCenter(dataset.manifest.bbox),
        zoom: 6,
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
      [dataset.manifest.bbox[0], dataset.manifest.bbox[1]],
      [dataset.manifest.bbox[2], dataset.manifest.bbox[3]],
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

    let healthTracker: TileHealthTracker | null = null;
    healthTracker = createTileHealthTracker(map, (snapshot) => {
      setHealth(snapshot);
      onHealthRef.current?.(snapshot);
    });

    map.on('load', () => {
      setTerrain(map, true);
      const camera = map.cameraForBounds(bounds, { padding: 36 });
      if (camera?.center && typeof camera.zoom === 'number') {
        map.jumpTo({
          center: camera.center,
          zoom: camera.zoom,
          pitch: HOME_PITCH,
          bearing: HOME_BEARING,
        });
      } else {
        map.jumpTo({ center: bboxCenter(dataset.manifest.bbox), zoom: 6, pitch: HOME_PITCH, bearing: HOME_BEARING });
      }
      updateAriaLabel(useTimelineStore.getState().step);

      const controller = createFloodController(map, dataset.frameIndex, {
        onFrameError: () => setFrameError(true),
      });
      floodRef.current = controller;
      const initialStep = useTimelineStore.getState().step;
      void controller.start(initialStep).then((ready) => {
        useTimelineStore.getState().setFramesReady(ready);
      });
    });

    const unsubscribe = useTimelineStore.subscribe((state, previous) => {
      if (state.step === previous.step) return;
      floodRef.current?.goToStep(state.step);
      updateAriaLabel(state.step);
    });

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(container);

    return () => {
      unsubscribe();
      resizeObserver.disconnect();
      healthTracker?.destroy();
      floodRef.current?.destroy();
      floodRef.current = null;
      map.off('error', onMapError);
      map.remove();
      mapRef.current = null;
    };
  }, [dataset]);

  const depthClasses = dataset.frameIndex.classes.filter((entry) => entry.id !== 0);
  const frameWidth = dataset.frameIndex.width;
  const frameHeight = dataset.frameIndex.height;
  const frameResolution = dataset.frameIndex.frame_resolution_m;

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

      {health.dem === 'offline' || health.imagery === 'offline' ? (
        <div className={styles.degradedChip} role="status">
          {health.dem === 'offline' && health.imagery === 'offline'
            ? 'Offline basemap · committed relief'
            : health.imagery === 'offline'
              ? 'Imagery offline · hillshade terrain'
              : '3D terrain offline · flat satellite'}
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
