import type { Dataset } from '../data/types';
import { formatDepthValue, formatPercent } from '../data/format';
import { ClassBadge, DataAge } from '../shell/DataBadge';
import styles from './panels.module.css';

interface MethodologyPanelProps {
  dataset: Dataset;
}

function formatMm(value: number): string {
  return `${Math.round(value).toLocaleString('en-IN')} mm`;
}

export function MethodologyPanel({ dataset }: MethodologyPanelProps) {
  const { scenario, districtRisk, series, summary, rainfall, exposure } = dataset;
  const model = scenario.model;
  const rainfallSeries = series.series.find((entry) => entry.id === 'rainfall');
  const stage = series.series.find((entry) => entry.id === 'stage_above_drainage');

  return (
    <div className={styles.panelBody}>
      <div className={styles.panelIntro}>
        <div className={styles.panelTitleRow}>
          <h2 className={styles.panelTitle} tabIndex={-1}>
            Methodology
          </h2>
          <ClassBadge className={summary.class} />
        </div>
        <p className={styles.panelLead}>
          A HAND screening model in plain language, the depth convention, and what is scenario,
          derived, reanalysis or observed.
        </p>
        <p className={styles.panelAgeLine}>
          <DataAge dataAsOf={summary.data_as_of} />
          <span> · ERA5</span>
          <DataAge dataAsOf={rainfall.data_as_of} compact />
          <span> · exposure</span>
          <DataAge dataAsOf={exposure.data_as_of} compact />
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
        <h3 className={styles.subTitle}>Class discipline</h3>
        <ul className={styles.classList}>
          <li>
            <ClassBadge className={summary.class} />
            <span>
              Inundation extent and depth: {summary.class}, derived from the DEM, mapped channels
              and the scenario stage curve. This is the timeline class and it stays SCENARIO even
              where ERA5 reanalysis informs the comparison.
            </span>
          </li>
          <li>
            <ClassBadge className={rainfallSeries?.class ?? series.class} />
            <span>
              Scenario rainfall: {rainfallSeries?.label ?? 'rainfall series'};{' '}
              {rainfallSeries?.source_note ?? rainfallSeries?.class}.
            </span>
          </li>
          <li>
            <ClassBadge className="reanalysis" />
            <span>
              ERA5 rainfall: class reanalysis, never observed. Daily totals 2015-2025 on a{' '}
              {rainfall.source.grid_resolution_deg}° grid ({rainfall.source.grid_resolution_km} km),
              area-weighted over the district polygons. 2022 JJAS and the 2015-2025 mean are
              published per district below. {rainfall.source.caveat}
            </span>
          </li>
          <li>
            <ClassBadge className={stage?.class ?? series.class} />
            <span>
              Stage above local drainage: {stage?.label ?? 'scenario stage'};{' '}
              {stage?.source_note ?? stage?.class}. Threshold{' '}
              {formatDepthValue(series.threshold.value)} m is a model parameter, not an official
              danger level.
            </span>
          </li>
          <li>
            <ClassBadge className={districtRisk.class} />
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
          <li>
            <ClassBadge className={exposure.class} />
            <span>
              Potentially exposed residents: {exposure.class}. WorldPop {exposure.source.vintage} at{' '}
              {exposure.source.resolution_m} m, aggregated to the S07 peak mask and to districts.
              The only resident field is <code>potentially_exposed_residents</code>. {exposure.method_sentence}{' '}
              {exposure.uncertainty_statement}
            </span>
          </li>
        </ul>
      </section>

      <section className={styles.methodCard} data-monsoon-table="true">
        <div className={styles.panelTitleRow}>
          <h3 className={styles.subTitle}>2022 monsoon vs 2015-2025 mean (ERA5)</h3>
          <span className={styles.badgePair}>
            <ClassBadge className="reanalysis" />
            <DataAge dataAsOf={rainfall.data_as_of} compact />
          </span>
        </div>
        <p>
          JJAS is June-September. All 33 district areal means are published; the AOI areal mean is{' '}
          {formatMm(rainfall.aoi_monsoon.monsoon_2022_mm)} in 2022 against a{' '}
          {formatMm(rainfall.aoi_monsoon.monsoon_2015_2025_mean_mm)} mean.
        </p>
        <div className={styles.monsoonTableWrap}>
          <table className={styles.validationTable}>
            <thead>
              <tr>
                <th scope="col">District</th>
                <th scope="col">2022 JJAS</th>
                <th scope="col">2015-2025 mean</th>
              </tr>
            </thead>
            <tbody>
              {rainfall.district_monsoon.map((district) => (
                <tr key={district.district_id} data-monsoon-district={district.district_id}>
                  <th scope="row">{district.name}</th>
                  <td>{formatMm(district.monsoon_2022_mm)}</td>
                  <td>{formatMm(district.monsoon_2015_2025_mean_mm)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
