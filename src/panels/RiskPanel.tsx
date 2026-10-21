import type { DistrictRisk } from '../data/schemas';
import { badgeFor } from '../data/labels';
import { formatPercent } from '../data/format';
import { rankedDistricts } from '../data/risk';
import { useSelectionStore } from '../state/selectionStore';
import { RiskRow } from './RiskRow';
import styles from './panels.module.css';

interface RiskPanelProps {
  risk: DistrictRisk;
}

export function RiskPanel({ risk }: RiskPanelProps) {
  const selectedDistrictId = useSelectionStore((state) => state.selectedDistrictId);
  const selectDistrict = useSelectionStore((state) => state.selectDistrict);
  const districts = rankedDistricts(risk);
  // Context bars are relative to the strongest district for each metric, so
  // they never imply a scoring reference value.
  const depthShareMax = Math.max(...districts.map((district) => district.depth_over_1_5m_share), 1e-9);
  const medianDepthMax = Math.max(...districts.map((district) => district.median_depth_m), 1e-9);

  return (
    <div className={styles.panelBody}>
      <div className={styles.panelIntro}>
        <div className={styles.panelTitleRow}>
          <h2 className={styles.panelTitle} tabIndex={-1}>
            District extent and severity
          </h2>
          <span className={styles.classBadge}>{badgeFor(risk.class)}</span>
        </div>
        <p className={styles.panelLead}>
          {districts.length} districts ordered by the extent score. Each row shows both the
          extent rank and the separate severity rank; click a row to focus the district.
        </p>
        <p className={styles.formulaNote}>
          <strong>Extent score</strong> = {formatPercent(risk.weights.area_share)} area share +{' '}
          {formatPercent(risk.weights.duration)} duration. Area saturates at{' '}
          {formatPercent(risk.reference_values.area_share_saturation)}; duration at{' '}
          {risk.reference_values.duration_saturation_days} days. <strong>Severity index</strong>{' '}
          = 100 × min–max of the product of district z-scores for depth &gt;1.5 m share, median
          depth and mean duration. Extent rank orders the extent score; severity rank orders the
          index. The two are never combined. Weights {risk.weights_version}.
        </p>
      </div>

      <div className={styles.riskLegend} aria-label="Risk classes">
        <span>
          <i className={styles.legendDot} style={{ background: '#79c9ae' }} /> Low
        </span>
        <span>
          <i className={styles.legendDot} style={{ background: '#e8b65a' }} /> Moderate
        </span>
        <span>
          <i className={styles.legendDot} style={{ background: '#e07a63' }} /> High
        </span>
        <span>
          <i className={styles.legendDot} style={{ background: '#d95f9b' }} /> Very high
        </span>
      </div>

      <ol className={styles.riskList} aria-label="Districts sorted by descending extent score">
        {districts.map((district) => (
          <li key={district.district_id}>
            <RiskRow
              district={district}
              selected={selectedDistrictId === district.district_id}
              depthShareMax={depthShareMax}
              medianDepthMax={medianDepthMax}
              onSelect={(districtId) =>
                selectDistrict(selectedDistrictId === districtId ? null : districtId)
              }
            />
          </li>
        ))}
      </ol>

      <p className={styles.panelFoot}>
        Extent is scenario-conditional terrain exposure, not expected loss. Severity is a
        per-wet-cell profile, not a second loss estimate. No population, asset or casualty field
        exists in the committed data.
      </p>
    </div>
  );
}
