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

  return (
    <div className={styles.panelBody}>
      <div className={styles.panelIntro}>
        <div className={styles.panelTitleRow}>
          <h2 className={styles.panelTitle} tabIndex={-1}>
            District risk ranking
          </h2>
          <span className={styles.classBadge}>{badgeFor(risk.class)}</span>
        </div>
        <p className={styles.panelLead}>
          {districts.length} districts ordered by scenario-conditional terrain risk. Click a row to
          focus the district on the map.
        </p>
        <p className={styles.formulaNote}>
          Score = {formatPercent(risk.weights.area_share)} area share +{' '}
          {formatPercent(risk.weights.duration)} duration + {formatPercent(risk.weights.depth)} peak
          depth. Area saturates at {formatPercent(risk.reference_values.area_share_saturation)}; duration
          at {risk.reference_values.duration_saturation_days} days; depth at{' '}
          {risk.reference_values.depth_reference_m} m.
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

      <ol className={styles.riskList} aria-label="Districts sorted by descending risk score">
        {districts.map((district) => (
          <li key={district.district_id}>
            <RiskRow
              district={district}
              selected={selectedDistrictId === district.district_id}
              onSelect={(districtId) =>
                selectDistrict(selectedDistrictId === districtId ? null : districtId)
              }
            />
          </li>
        ))}
      </ol>

      <p className={styles.panelFoot}>
        Risk is scenario-conditional terrain exposure, not expected loss. No population, asset or
        casualty field exists in the committed data.
      </p>
    </div>
  );
}
