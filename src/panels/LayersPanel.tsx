import type { Dataset } from '../data/types';
import { LAYERS } from '../map/layerRegistry';
import { TERRAIN_EXAGGERATION } from '../map/mapConfig';
import { useLayerStore } from '../state/layerStore';
import { ClassBadge, DataAge } from '../shell/DataBadge';
import styles from './panels.module.css';

interface LayersPanelProps {
  dataset: Dataset;
}

export function LayersPanel({ dataset }: LayersPanelProps) {
  const visible = useLayerStore((state) => state.visible);
  const opacity = useLayerStore((state) => state.opacity);
  const baseMode = useLayerStore((state) => state.baseMode);
  const toggle = useLayerStore((state) => state.toggle);
  const setOpacity = useLayerStore((state) => state.setOpacity);
  const setBaseMode = useLayerStore((state) => state.setBaseMode);
  const reset = useLayerStore((state) => state.reset);

  const dataAsOf = (layerId: string): string => {
    if (layerId === 'flood') return dataset.summary.data_as_of;
    if (layerId === 'risk-zones' || layerId === 'hotspots' || layerId === 'districts') {
      return dataset.districtRisk.data_as_of;
    }
    return dataset.provenance.generated_at.slice(0, 10);
  };

  return (
    <div className={styles.panelBody}>
      <div className={styles.panelIntro}>
        <div className={styles.panelTitleRow}>
          <h2 className={styles.panelTitle} tabIndex={-1}>
            Layers
          </h2>
          <ClassBadge className="derived" />
        </div>
        <p className={styles.panelLead}>
          Toggle visibility, drag opacity, or swap the basemap. The map is not re-created; every
          control mutates the existing style layers.
        </p>
        <p className={styles.panelAgeLine}>
          <DataAge dataAsOf={dataset.manifest.generated_at.slice(0, 10)} />
          <span> · each layer row carries its own class badge and data age.</span>
        </p>
      </div>

      <div className={styles.baseModeBlock}>
        <span className={styles.fieldLabel}>Base mode</span>
        <div className={styles.segmented} role="group" aria-label="Basemap mode">
          <button
            type="button"
            className={`${styles.segment} ${baseMode === 'imagery' ? styles.segmentActive : ''}`}
            aria-pressed={baseMode === 'imagery'}
            onClick={() => setBaseMode('imagery')}
            data-base-mode="imagery"
          >
            Imagery
          </button>
          <button
            type="button"
            className={`${styles.segment} ${baseMode === 'hillshade' ? styles.segmentActive : ''}`}
            aria-pressed={baseMode === 'hillshade'}
            onClick={() => setBaseMode('hillshade')}
            data-base-mode="hillshade"
          >
            Hillshade
          </button>
        </div>
        <p className={styles.modeNote}>
          {baseMode === 'imagery'
            ? 'Esri World Imagery under the flood; hillshade stays as quiet relief.'
            : 'Imagery hidden; the committed relief and DEM hillshade carry the terrain.'}
        </p>
      </div>

      <div className={styles.layerList}>
        {LAYERS.map((layer) => {
          const isVisible = visible[layer.id];
          const value = opacity[layer.id];
          return (
            <section
              key={layer.id}
              className={`${styles.layerRow} ${isVisible ? '' : styles.layerRowOff}`}
              data-layer-id={layer.id}
              data-visible={isVisible ? 'true' : 'false'}
              data-opacity={value.toFixed(2)}
            >
              <div className={styles.layerHead}>
                <label className={styles.switch}>
                  <input
                    type="checkbox"
                    checked={isVisible}
                    onChange={() => toggle(layer.id)}
                    aria-label={`Show ${layer.label}`}
                  />
                  <span className={styles.switchTrack} aria-hidden="true">
                    <span className={styles.switchThumb} />
                  </span>
                </label>
                <span className={styles.layerName}>{layer.label}</span>
                <ClassBadge className={layer.class} />
              </div>
              <div className={styles.layerMeta}>
                <span>{layer.note}</span>
              </div>
              <div className={styles.layerAgeRow} data-layer-age={layer.id}>
                <DataAge dataAsOf={dataAsOf(layer.id)} compact />
              </div>
              <div className={styles.layerControls}>
                <label className={styles.opacityLabel} htmlFor={`opacity-${layer.id}`}>
                  Opacity
                </label>
                <input
                  id={`opacity-${layer.id}`}
                  className={styles.opacityRange}
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  value={Math.round(value * 100)}
                  onChange={(event) => setOpacity(layer.id, Number(event.target.value) / 100)}
                  aria-label={`${layer.label} opacity`}
                  aria-valuetext={`${Math.round(value * 100)} percent`}
                  data-opacity-for={layer.id}
                />
                <output className={styles.opacityValue} htmlFor={`opacity-${layer.id}`}>
                  {Math.round(value * 100)}%
                </output>
              </div>
            </section>
          );
        })}
      </div>

      <div className={styles.layerFoot}>
        <p>
          Dataset {dataset.manifest.dataset_version}. Hillshade opacity changes shading contrast;
          terrain vertical exaggeration is fixed at {TERRAIN_EXAGGERATION}× for readability, not a
          vertical-scale claim.
        </p>
        <button type="button" className={styles.resetButton} onClick={reset}>
          Reset layers
        </button>
      </div>
    </div>
  );
}
