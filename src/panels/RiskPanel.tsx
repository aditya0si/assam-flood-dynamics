import type { DistrictRisk, Exposure } from '../data/schemas';
import { formatPercent } from '../data/format';
import { rankedDistricts } from '../data/risk';
import { useSelectionStore } from '../state/selectionStore';
import { ClassBadge, DataAge } from '../shell/DataBadge';
import { RiskRow } from './RiskRow';
import styles from './panels.module.css';

interface RiskPanelProps {
  risk: DistrictRisk;
  exposure: Exposure;
}

function formatResidents(value: number): string {
  return value.toLocaleString('en-IN');
}

export function RiskPanel({ risk, exposure }: RiskPanelProps) {
  const selectedDistrictId = useSelectionStore((state) => state.selectedDistrictId);
  const selectDistrict = useSelectionStore((state) => state.selectDistrict);
  const districts = rankedDistricts(risk);
  const exposureTop = [...exposure.districts]
    .sort((left, right) => right.potentially_exposed_residents - left.potentially_exposed_residents)
    .slice(0, 5);
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
          <span className={styles.badgePair}>
            <ClassBadge className={risk.class} />
            <ClassBadge className={exposure.class} />
          </span>
        </div>
        <p className={styles.panelLead}>
          {districts.length} districts ordered by the extent score. Each row shows both the
          extent rank and the separate severity rank; click a row to focus the district.
        </p>
        <p className={styles.panelAgeLine}>
          <DataAge dataAsOf={risk.data_as_of} />
          <span> · exposure:</span>
          <DataAge dataAsOf={exposure.data_as_of} />
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

      <section className={styles.methodCard} data-exposure-card="true">
        <div className={styles.panelTitleRow}>
          <h3 className={styles.subTitle}>Potentially exposed residents</h3>
          <span className={styles.badgePair}>
            <ClassBadge className="derived" />
            <DataAge dataAsOf={exposure.data_as_of} compact />
          </span>
        </div>
        <p className={styles.exposureTotal}>
          {formatResidents(exposure.totals.potentially_exposed_residents)}{' '}
          <span>district total · {formatResidents(exposure.totals.peak_mask_potentially_exposed_residents)} in the peak mask</span>
        </p>
        <ul className={styles.exposureList}>
          {exposureTop.map((district) => (
            <li key={district.district_id}>
              <span>{district.name}</span>
              <strong>{formatResidents(district.potentially_exposed_residents)}</strong>
            </li>
          ))}
        </ul>
        <p className={styles.exposureMethod}>{exposure.method_sentence}</p>
        <p className={styles.exposureCaveat}>{exposure.uncertainty_statement}</p>
        <p className={styles.exposureCaveat}>{exposure.caveat}</p>
      </section>

      <p className={styles.panelFoot}>
        Extent is scenario-conditional terrain exposure, not expected loss. Severity is a
        per-wet-cell profile, not a second loss estimate. Exposure is the derived
        potentially_exposed_residents estimate only; no impact, movement or loss field exists in
        the committed data.
      </p>
    </div>
  );
}
