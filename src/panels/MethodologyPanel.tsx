import type { Dataset } from '../data/types';
import { badgeFor } from '../data/labels';
import { formatDepthValue, formatPercent } from '../data/format';
import styles from './panels.module.css';

interface MethodologyPanelProps {
  dataset: Dataset;
}

export function MethodologyPanel({ dataset }: MethodologyPanelProps) {
  const { scenario, districtRisk, series, summary } = dataset;
  const model = scenario.model;
  const rainfall = series.series.find((entry) => entry.id === 'rainfall');
  const stage = series.series.find((entry) => entry.id === 'stage_above_drainage');

  return (
    <div className={styles.panelBody}>
      <div className={styles.panelIntro}>
        <div className={styles.panelTitleRow}>
          <h2 className={styles.panelTitle} tabIndex={-1}>
            Methodology
          </h2>
          <span className={styles.classBadge}>{badgeFor(summary.class)}</span>
        </div>
        <p className={styles.panelLead}>
          A HAND screening model in plain language, the depth convention, and what is synthetic
          versus derived.
        </p>
      </div>

      <section className={styles.methodCard}>
        <h3 className={styles.subTitle}>HAND screening</h3>
        <p>
          HAND means <strong>height above nearest drainage</strong>. For each 90 m analysis cell it
          records how far the ground sits above the nearest mapped river channel. A single scenario
          stage is then applied to every mapped channel: any cell whose HAND is lower than that stage
          becomes wet. This is a terrain screening test, not a solved hydrodynamic model.
        </p>
        <dl className={styles.definitionList}>
          <div>
            <dt>Model</dt>
            <dd>
              {model.name} <code>{model.version}</code>
            </dd>
          </div>
          <div>
            <dt>Depth formula</dt>
            <dd>
              <code>{model.depth_formula}</code>
            </dd>
          </div>
          <div>
            <dt>Channel burn</dt>
            <dd>{formatDepthValue(model.burn_depth_m)} m below the mapped channel datum</dd>
          </div>
          <div>
            <dt>Component filter</dt>
            <dd>
              {model.component_filter.method}; wet components below{' '}
              {model.component_filter.min_cells} cells ({formatDepthValue(model.component_filter.min_area_km2)} km²)
              are dropped. {model.component_filter.opening === 'none' ? 'No morphological opening.' : null}
            </dd>
          </div>
        </dl>
      </section>

      <section className={`${styles.methodCard} ${styles.biasCard}`}>
        <h3 className={styles.subTitle}>Bathtub depth convention</h3>
        <p>
          <strong>Bathtub convention:</strong> <code>{model.depth_formula}</code>. The result is{' '}
          <strong>conservative-shallow</strong>: a cell below the burnt channel datum reports the full
          stage, because no levee or bathymetry data exists to give it a deeper surface. That bias is
          intentional and is not corrected by an unobserved depth field.
        </p>
        <p className={styles.quote}>{model.depth_bias}</p>
        <p>
          At the peak step the bathtub surface is capped by the scenario stage (3.7 m), so
          <code> p90_peak_depth_m</code> is the same for every district. Peak depth therefore
          enters the separate severity index (depth &gt;1.5 m share and median depth) but not the
          extent score; the two ranks are labelled separately.
        </p>
      </section>

      <section className={styles.methodCard}>
        <h3 className={styles.subTitle}>Synthetic vs derived</h3>
        <ul className={styles.classList}>
          <li>
            <span className={styles.classBadge}>{badgeFor(summary.class)}</span>
            <span>
              Inundation extent and depth: {summary.class}, derived from the DEM, mapped channels and
              the synthetic stage curve.
            </span>
          </li>
          <li>
            <span className={styles.classBadge}>{badgeFor(rainfall?.class ?? series.class)}</span>
            <span>
              Rainfall: {rainfall?.label ?? 'rainfall series'}; {rainfall?.source_note ?? rainfall?.class}.
            </span>
          </li>
          <li>
            <span className={styles.classBadge}>{badgeFor(stage?.class ?? series.class)}</span>
            <span>
              Stage above local drainage: {stage?.label ?? 'scenario stage'};{' '}
              {stage?.source_note ?? stage?.class}. Threshold{' '}
              {formatDepthValue(series.threshold.value)} m is a model parameter, not an official
              danger level.
            </span>
          </li>
          <li>
            <span className={styles.classBadge}>{badgeFor(districtRisk.class)}</span>
            <span>
              Extent score and district ranking: {districtRisk.class}, weighted{' '}
              {formatPercent(districtRisk.weights.area_share)} area share and{' '}
              {formatPercent(districtRisk.weights.duration)} duration (two drivers, weights{' '}
              {districtRisk.weights_version}). The severity index is a separate 0–100 profile of
              depth &gt;1.5 m share × median depth × duration, min–max normalised; it is never
              added to the extent score. Districts below 75% valid coverage carry a coverage
              badge.
            </span>
          </li>
        </ul>
      </section>

      <section className={styles.methodCard}>
        <h3 className={styles.subTitle}>What is not modelled</h3>
        <ul className={styles.assumptionList}>
          {scenario.limitations.slice(0, 5).map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
