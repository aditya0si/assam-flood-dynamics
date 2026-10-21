import { useEffect, useRef, useState } from 'react';
import maplibregl, {
  AttributionControl,
  LngLatBounds,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  Popup,
  ScaleControl,
  type ErrorEvent as MapLibreErrorEvent,
  type MapMouseEvent,
} from 'maplibre-gl';
import type { Dataset } from '../data/types';
import type { HotspotProperties } from '../data/schemas';
import { useTimelineStore } from '../state/timelineStore';
import { useTileHealthStore } from '../state/tileHealthStore';
import { useLayerStore } from '../state/layerStore';
import { usePanelStore } from '../state/panelStore';
import { useSelectionStore } from '../state/selectionStore';
import { badgeFor } from '../data/labels';
import { formatArea, formatDepthValue, formatScore, formatStage, formatStepNumber } from '../data/format';
import { hotspotDisplayName, hotspotReasonLabel, topDistrict } from '../data/risk';
import { dataUrl } from '../data/loadData';
import { prefersReducedMotion } from '../lib/motion';
import { createFloodController, type FloodController } from './flood';
import {
  AOI_CORE_BOUNDS,
  BACKGROUND_LAYER_ID,
  DISTRICT_LABEL_LIMIT,
  DISTRICT_LABEL_MIN_ZOOM,
  FLOOD_CURRENT_SOURCE_ID,
  FLOOD_OUTGOING_SOURCE_ID,
  HERO_ZOOM,
  HOME_BEARING,
  HOME_PITCH,
  HOTSPOTS_LAYER_ID,
  MAX_BOUNDS,
  MAX_PITCH,
  MAX_ZOOM,
  MIN_ZOOM,
  bboxCenter,
} from './mapConfig';
import { applyLayerPaint, buildMapStyle, setTerrain } from './mapStyle';
import { LAYER_IDS } from './layerRegistry';
import { createTileHealthTracker, type TileHealthTracker } from './tileHealth';
import { tileHealthCopy } from './tileHealthState';
import { depthPresentationColor } from './depthPalette';
import styles from './map.module.css';

interface MapCanvasProps {
  dataset: Dataset;
}

interface DistrictFeatureProperties {
  district_id: string;
  name: string;
  rank: number;
  risk_score: number;
  risk_class: string;
  centroid_lon: number;
  centroid_lat: number;
}

function buildHotspotPopup(
  hotspot: HotspotProperties,
  districtName: string | null,
  districtRiskScore: number | null,
): HTMLElement {
  const card = document.createElement('div');
  card.className = styles.hotspotCard;

  const kicker = document.createElement('span');
  kicker.className = styles.hotspotKicker;
  kicker.textContent = `Derived hotspot ${hotspot.hotspot_id} · rank ${hotspot.rank} of 20`;

  const title = document.createElement('strong');
  title.className = styles.hotspotTitle;
  title.textContent = hotspotDisplayName(hotspot, districtName);

  const score = document.createElement('span');
  score.className = styles.hotspotScore;
  score.textContent =
    districtRiskScore === null
      ? `Rank ${hotspot.rank} of 20`
      : `Rank ${hotspot.rank} of 20 · district risk ${formatScore(districtRiskScore)}`;
  score.dataset.hotspotRank = String(hotspot.rank);
  score.dataset.districtRisk = districtRiskScore === null ? '' : String(districtRiskScore);

  const meta = document.createElement('span');
  meta.className = styles.hotspotMeta;
  meta.textContent = `${formatArea(hotspot.area_km2)} km² · HAND ${formatDepthValue(
    hotspot.hand_mean_m,
  )} m · ${(hotspot.distance_to_channel_m / 1000).toFixed(1)} km from a channel`;

  const reason = document.createElement('span');
  reason.className = styles.hotspotReason;
  reason.textContent = `${hotspotReasonLabel(hotspot.reason)} · peak depth ${formatDepthValue(
    hotspot.peak_depth_m,
  )} m`;

  const caveat = document.createElement('span');
  caveat.className = styles.hotspotCaveat;
  caveat.textContent = 'Backwater pocket, not an embankment breach.';

  card.append(kicker, title, score, meta, reason, caveat);
  return card;
}

export function MapCanvas({ dataset }: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const floodRef = useRef<FloodController | null>(null);
  const visibleFrameRef = useRef('');
  const readyRef = useRef(false);
  // B8: deterministic settle hooks. renderSeq counts painted map frames;
  // styleLoaded is set once the style document and required layers exist, so
  // neither depends on remote tile network state.
  const renderSeqRef = useRef(0);
  const styleLoadedRef = useRef(false);
  const [webglError, setWebglError] = useState(false);
  const [frameError, setFrameError] = useState(false);
  const health = useTileHealthStore((state) => state.snapshot);
  const healthLevel = useTileHealthStore((state) => state.level);
  const floodVisible = useLayerStore((state) => state.visible.flood);
  const status = tileHealthCopy(health);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const districts = dataset.districts.features as Array<{
      properties: DistrictFeatureProperties;
      geometry: unknown;
    }>;
    const districtById = new Map(
      districts.map((feature) => [feature.properties.district_id, feature.properties]),
    );

    const top = topDistrict(dataset.districtRisk);
    const topFeature = top ? districtById.get(top.district_id) : undefined;
    // B5: hero reach is the top-ranked district's committed centroid. The map
    // opens at district scale there instead of fitting the whole thin belt.
    const heroCenter: [number, number] = topFeature
      ? [topFeature.centroid_lon, topFeature.centroid_lat]
      : bboxCenter(AOI_CORE_BOUNDS);
    const topDistrictProbe = top
      ? Object.freeze({
          name: top.name,
          // The hook carries the display score the rail shows (71.9) plus the
          // committed value (71.944) so either assertion is possible.
          score: Number(formatScore(top.risk_score)),
          riskScore: top.risk_score,
          scoreLabel: formatScore(top.risk_score),
          riskClass: top.risk_class,
          rank: top.rank,
          districtId: top.district_id,
          areaShare: top.area_share,
          durationDays: top.mean_duration_days,
          peakDepthM: top.p90_peak_depth_m,
          centroidLon: topFeature?.centroid_lon ?? null,
          centroidLat: topFeature?.centroid_lat ?? null,
          toString: () => top.name,
        })
      : null;

    // Reset the single shared health record for this map instance.
    useTileHealthStore.getState().reset();
    readyRef.current = false;
    visibleFrameRef.current = '';
    renderSeqRef.current = 0;
    styleLoadedRef.current = false;
    container.setAttribute('data-ready', 'false');
    container.setAttribute('data-step', String(useTimelineStore.getState().step));
    container.setAttribute('data-frame-file', '');

    // The probe is a live view of the stores, not a snapshot that can drift.
    const probe = Object.freeze({
      get step(): number {
        return useTimelineStore.getState().step;
      },
      get stepCount(): number {
        return dataset.summary.steps.length;
      },
      get stepLabel(): string {
        return dataset.summary.steps[useTimelineStore.getState().step]?.step_label ?? '';
      },
      get phase(): string {
        return dataset.summary.steps[useTimelineStore.getState().step]?.phase ?? '';
      },
      get areaKm2(): number {
        return dataset.summary.steps[useTimelineStore.getState().step]?.inundated_area_km2 ?? 0;
      },
      get frameFile(): string {
        return visibleFrameRef.current;
      },
      get ready(): boolean {
        return readyRef.current;
      },
      get styleLoaded(): boolean {
        return styleLoadedRef.current;
      },
      get renderSeq(): number {
        return renderSeqRef.current;
      },
      get isPlaying(): boolean {
        return useTimelineStore.getState().playing;
      },
      get tileHealth(): 'live' | 'degraded' | 'offline' {
        return useTileHealthStore.getState().level;
      },
      get tileSources() {
        const snapshot = useTileHealthStore.getState().snapshot;
        return { dem: snapshot.dem, imagery: snapshot.imagery };
      },
      get panel(): string {
        return usePanelStore.getState().activePanel;
      },
      get selectedDistrictId(): string | null {
        return useSelectionStore.getState().selectedDistrictId;
      },
      get layers() {
        const state = useLayerStore.getState();
        return {
          visible: LAYER_IDS.filter((id) => state.visible[id]),
          opacity: { ...state.opacity },
          baseMode: state.baseMode,
        };
      },
      get districtTop() {
        return topDistrictProbe;
      },
      get camera() {
        const current = mapRef.current;
        if (!current) return null;
        const center = current.getCenter();
        return {
          center: [center.lng, center.lat] as [number, number],
          zoom: current.getZoom(),
          pitch: current.getPitch(),
        };
      },
      get tileHealthHistory(): string[] {
        return [...useTileHealthStore.getState().history];
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
        center: heroCenter,
        zoom: HERO_ZOOM,
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
    // B8: one increment per painted map frame. The E2E settle helper waits for
    // this counter to advance; it never waits on tile load state.
    const onRender = () => {
      renderSeqRef.current += 1;
    };
    map.on('render', onRender);
    // R6: the rail overlays the right edge, so map controls live top-left.
    map.addControl(new NavigationControl({ visualizePitch: true, showCompass: true }), 'top-left');
    map.addControl(new ScaleControl({ unit: 'metric', maxWidth: 96 }), 'bottom-right');
    map.addControl(new AttributionControl({ compact: true }), 'bottom-right');

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

    const riskById = new Map(
      dataset.districtRisk.districts.map((district) => [district.district_id, district]),
    );
    const labelFeatures = [...districts]
      .filter((feature) => {
        const rank = Number(feature.properties.rank);
        return Number.isFinite(rank) && rank >= 1 && rank <= DISTRICT_LABEL_LIMIT;
      })
      .sort((left, right) => left.properties.rank - right.properties.rank);

    const labelMarkers: Marker[] = [];
    const updateLabelVisibility = () => {
      const layerVisible = useLayerStore.getState().visible.districts;
      const visible = layerVisible && map.getZoom() >= DISTRICT_LABEL_MIN_ZOOM;
      for (const marker of labelMarkers) {
        const element = marker.getElement();
        element.style.display = visible ? '' : 'none';
        element.setAttribute('aria-hidden', visible ? 'false' : 'true');
      }
    };

    const createDistrictLabels = () => {
      if (labelMarkers.length > 0) return;
      for (const feature of labelFeatures) {
        const properties = feature.properties;
        const element = document.createElement('div');
        element.className = styles.districtLabel;
        element.dataset.districtId = properties.district_id;

        const name = document.createElement('span');
        name.className = styles.districtLabelName;
        name.textContent = properties.name;

        const score = document.createElement('span');
        score.className = styles.districtLabelScore;
        score.textContent = `#${properties.rank} · ${formatScore(properties.risk_score)}`;
        score.dataset.rank = String(properties.rank);
        score.dataset.score = formatScore(properties.risk_score);

        element.append(name, score);
        element.title = `${properties.name} · district risk score ${formatScore(
          properties.risk_score,
        )} of 100 · rank ${properties.rank} in the Risk panel`;
        element.setAttribute(
          'aria-label',
          `${properties.name}, district risk score ${formatScore(
            properties.risk_score,
          )} of 100, rank ${properties.rank} in the Risk panel`,
        );
        const marker = new Marker({ element, anchor: 'center' })
          .setLngLat([properties.centroid_lon, properties.centroid_lat])
          .addTo(map);
        labelMarkers.push(marker);
      }
      updateLabelVisibility();
    };

    let hotspotPopup: Popup | null = null;
    const onHotspotClick = (event: MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
      const feature = event.features?.[0];
      if (!feature) return;
      const hotspot = feature.properties as unknown as HotspotProperties;
      const district = districtById.get(hotspot.district_id);
      const risk = riskById.get(hotspot.district_id);
      const element = buildHotspotPopup(
        hotspot,
        district?.name ?? null,
        risk?.risk_score ?? null,
      );
      hotspotPopup?.remove();
      hotspotPopup = new Popup({
        closeButton: true,
        closeOnClick: true,
        offset: 12,
        maxWidth: '310px',
        className: styles.hotspotPopup,
      })
        .setLngLat([hotspot.centroid_lon, hotspot.centroid_lat])
        .setDOMContent(element)
        .addTo(map);
    };
    const onHotspotEnter = () => {
      map.getCanvas().style.cursor = 'pointer';
    };
    const onHotspotLeave = () => {
      map.getCanvas().style.cursor = '';
    };

    const applyLayers = () => {
      applyLayerPaint(map, useLayerStore.getState());
      updateLabelVisibility();
      if (!useLayerStore.getState().visible.hotspots) hotspotPopup?.remove();
      floodRef.current?.refreshOpacity();
    };
    const unsubscribeLayers = useLayerStore.subscribe(applyLayers);

    const focusDistrict = (districtId: string | null) => {
      if (!districtId) return;
      const district = districtById.get(districtId);
      if (!district) return;
      const camera = {
        center: [district.centroid_lon, district.centroid_lat] as [number, number],
        zoom: Math.max(map.getZoom(), 8.1),
        pitch: HOME_PITCH,
        bearing: HOME_BEARING,
      };
      if (prefersReducedMotion()) {
        map.jumpTo(camera);
      } else {
        map.flyTo({ ...camera, duration: 900, essential: true });
      }
    };
    const unsubscribeSelection = useSelectionStore.subscribe((state, previous) => {
      if (state.selectedDistrictId !== previous.selectedDistrictId) {
        focusDistrict(state.selectedDistrictId);
      }
    });

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
      styleLoadedRef.current = true;
      map.off('styledata', startScene);
      map.off('style.load', startScene);

      setTerrain(map, true);
      updateAriaLabel(useTimelineStore.getState().step);

      applyLayers();
      createDistrictLabels();
      map.on('click', HOTSPOTS_LAYER_ID, onHotspotClick);
      map.on('mouseenter', HOTSPOTS_LAYER_ID, onHotspotEnter);
      map.on('mouseleave', HOTSPOTS_LAYER_ID, onHotspotLeave);

      const controller = createFloodController(map, dataset.frameIndex, {
        onFrameError: () => setFrameError(true),
        onFrameApplied: (_step, file) => {
          visibleFrameRef.current = file;
          container.setAttribute('data-frame-file', file);
          markReady();
        },
        getOpacity: () => useLayerStore.getState().opacity.flood,
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

    map.on('zoom', updateLabelVisibility);

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
      unsubscribeLayers();
      unsubscribeSelection();
      resizeObserver.disconnect();
      healthTracker.destroy();
      floodRef.current?.destroy();
      floodRef.current = null;
      map.off('styledata', startScene);
      map.off('style.load', startScene);
      map.off('render', onRender);
      map.off('zoom', updateLabelVisibility);
      map.off('click', HOTSPOTS_LAYER_ID, onHotspotClick);
      map.off('mouseenter', HOTSPOTS_LAYER_ID, onHotspotEnter);
      map.off('mouseleave', HOTSPOTS_LAYER_ID, onHotspotLeave);
      map.off('error', onMapError);
      hotspotPopup?.remove();
      for (const marker of labelMarkers) marker.remove();
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
        <ul className={styles.legendList} data-flood-visible={floodVisible ? 'true' : 'false'}>
          {depthClasses.map((entry) => (
            <li key={entry.id} className={styles.legendItem}>
              <span
                className={styles.swatch}
                style={{
                  backgroundColor: depthPresentationColor(entry.id, entry.color),
                  opacity: floodVisible ? Math.max(0.55, entry.alpha / 255) : 0.35,
                }}
              />
              <span>{`${entry.label} m`}</span>
            </li>
          ))}
        </ul>
        <p className={styles.legendMeta}>
          {floodVisible
            ? `${frameWidth} × ${frameHeight} px · ${formatStage(frameResolution)} m/px · classes from frame-index.json`
            : 'Flood extent hidden in Layers; depth classes still from frame-index.json.'}
        </p>
        <p className={styles.markerKey}>
          District markers: <strong>#1 · 71.9</strong> = rank · district risk score 0–100; rank
          matches the Risk panel.
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
