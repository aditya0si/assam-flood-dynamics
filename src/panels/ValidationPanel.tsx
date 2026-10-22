import type { Scorecard } from '../data/schemas';
import { formatArea, formatPercent, formatScore, formatStepCode } from '../data/format';
import { ClassBadge, DataAge } from '../shell/DataBadge';
import styles from './panels.module.css';

interface ValidationPanelProps {
  scorecard: Scorecard;
}

function formatUtc(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.toISOString().slice(0, 10)} UTC`;
}

export function ValidationPanel({ scorecard }: ValidationPanelProps) {
  const { method, scenes, summary } = scorecard;
  return (
    <div className={styles.panelBody} data-validation-panel="true">
      <div className={styles.panelIntro}>
        <div className={styles.panelTitleRow}>
          <h2 className={styles.panelTitle} tabIndex={-1}>
            Sentinel-1 validation
          </h2>
          <span className={styles.badgePair}>
            <ClassBadge className="observed" />
            <ClassBadge className="derived" />
          </span>
        </div>
        <p className={styles.panelLead}>
          Two real Sentinel-1 GRD acquisitions, scored against the committed scenario frames.
          This is an extent-shape comparison, not an event hindcast.
        </p>
        <p className={styles.panelAgeLine}>
          <DataAge dataAsOf={scorecard.data_as_of} />
          <span> · SAR acquisition dates are the observed data; the scorecard is derived.</span>
        </p>
        <p className={styles.formulaNote}>
          {method.collection} · VV decimated with {method.resampling} · σ0 calibration from
          SAFE LUT (A median {formatScore(method.calibration.A_median)}) · fixed{' '}
          {formatScore(method.threshold_db)} dB threshold · sensitivity{' '}
          {method.sensitivity_db.join(' / ')} dB · {method.crs} at{' '}
          {method.resolution_m} m. Validity is the full SAR footprint, not the AOI-core
          sliver; the {method.slope_mask_deg}° slope filter is a per-scene diagnostic and
          is not applied to the final domain.
        </p>
      </div>

      <div className={styles.validationSummary} data-validation-summary="true">
        <span>
          Mean IoU <strong>{formatScore(summary.mean_iou_over_scenes)}</strong>
        </span>
        <span>
          Precision <strong>{formatScore(summary.mean_precision)}</strong>
        </span>
        <span>
          Recall <strong>{formatScore(summary.mean_recall)}</strong>
        </span>
        <span className={styles.validationWorst}>
          Worst {summary.worst_scene}
        </span>
      </div>

      {scenes.map((scene) => (
        <section
          key={scene.scene_id}
          className={styles.methodCard}
          data-validation-scene={scene.scene_id}
        >
          <h3 className={styles.subTitle}>{scene.scene_id}</h3>
          <p className={styles.panelAgeLine}>
            <ClassBadge className="observed" />
            <DataAge dataAsOf={scene.datetime.slice(0, 10)} />
            <span className={styles.validationMeta}>
              {' '}· {formatUtc(scene.datetime)} · {scene.platform} · relative orbit{' '}
              {scene.relative_orbit} · σ0 {formatScore(scene.threshold_db)} dB
            </span>
          </p>
          <dl className={styles.validationGrid}>
            <div>
              <dt>Observed water</dt>
              <dd>
                <ClassBadge className="observed" /> {formatArea(scene.observed_area_km2)} km²
              </dd>
            </div>
            <div>
              <dt>Observed fraction</dt>
              <dd>
                {formatPercent(scene.observed_water_fraction_of_validity)} of{' '}
                {formatArea(scene.validity_area_km2)} km² validity
              </dd>
            </div>
            <div>
              <dt>Validity footprint</dt>
              <dd>
                {formatArea(scene.validity_area_km2)} km² of{' '}
                {formatArea(scene.scene_area_km2)} km² scene (
                {formatPercent(scene.validity_fraction_of_scene)})
              </dd>
            </div>
            <div>
              <dt>Slope diagnostic</dt>
              <dd>
                {formatArea(scene.with_slope_validity_area_km2)} km² with slope ≤{' '}
                {scene.slope_filter.threshold_deg}° ·{' '}
                {formatArea(scene.without_slope_validity_area_km2)} km² without
              </dd>
            </div>
            <div>
              <dt>Best match</dt>
              <dd>
                {formatStepCode(scene.best_match_step)} · IoU {formatScore(scene.best_match_iou)}
              </dd>
            </div>
            <div>
              <dt>Peak {formatStepCode(scene.peak_step.step)}</dt>
              <dd>
                {formatArea(scene.peak_step.modelled_area_km2)} km² modelled of{' '}
                {formatArea(scene.validity_area_km2)} km² validity · IoU{' '}
                {formatScore(scene.peak_step.iou)}
              </dd>
            </div>
            <div>
              <dt>Peak precision / recall</dt>
              <dd>
                {formatScore(scene.peak_step.precision)} / {formatScore(scene.peak_step.recall)} ·
                F1 {formatScore(scene.peak_step.f1)}
              </dd>
            </div>
            <div>
              <dt>Area bias</dt>
              <dd>
                {scene.peak_step.area_bias_pct >= 0 ? '+' : ''}
                {formatScore(scene.peak_step.area_bias_pct)}%
              </dd>
            </div>
          </dl>
          <table className={styles.validationTable}>
            <caption>Sensitivity at peak {formatStepCode(scene.peak_step.step)}</caption>
            <thead>
              <tr>
                <th scope="col">Mask</th>
                <th scope="col">IoU</th>
                <th scope="col">Precision</th>
                <th scope="col">Recall</th>
              </tr>
            </thead>
            <tbody>
              {scene.sensitivity.map((entry) => (
                <tr key={entry.threshold_db}>
                  <th scope="row">σ0 ≤ {formatScore(entry.threshold_db)} dB</th>
                  <td>{formatScore(entry.iou)}</td>
                  <td>{formatScore(entry.precision)}</td>
                  <td>{formatScore(entry.recall)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}

      <section className={styles.methodCard}>
        <h3 className={styles.subTitle}>Caveats</h3>
        <ul className={styles.assumptionList}>
          {summary.caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      </section>

      <p className={styles.panelFoot}>
        The scenario has no date correspondence: the best-matching step and the scenario peak
        S07 are both reported. A low IoU is the finding and is not improved to fit.
      </p>
    </div>
  );
}
