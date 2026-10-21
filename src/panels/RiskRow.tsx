import type { DistrictRiskEntry } from '../data/schemas';
import { formatArea, formatDays, formatDepthValue, formatPercent, formatScore } from '../data/format';
import { driverLabel, riskClassColor, riskClassLabel } from '../data/risk';
import styles from './panels.module.css';

interface RiskRowProps {
  district: DistrictRiskEntry;
  selected: boolean;
  onSelect: (districtId: string) => void;
}

const DRIVER_ORDER = ['area', 'duration', 'depth'] as const;

export function RiskRow({ district, selected, onSelect }: RiskRowProps) {
  const driverValues: Record<(typeof DRIVER_ORDER)[number], string> = {
    area: `${formatArea(district.peak_flooded_area_km2)} km²`,
    duration: `${formatDays(district.mean_duration_days)} d`,
    depth: `${formatDepthValue(district.p90_peak_depth_m)} m`,
  };
  const color = riskClassColor(district.risk_class);

  return (
    <button
      type="button"
      className={`${styles.riskRow} ${selected ? styles.riskRowSelected : ''}`}
      onClick={() => onSelect(district.district_id)}
      aria-pressed={selected}
      aria-label={`${district.name}, risk ${formatScore(district.risk_score)} of 100, ${riskClassLabel(
        district.risk_class,
      )}. Focus district on the map.`}
      data-district-id={district.district_id}
      data-rank={district.rank}
      data-score={formatScore(district.risk_score)}
    >
      <span className={styles.riskRank}>{district.rank}</span>
      <span className={styles.riskBody}>
        <span className={styles.riskTitleRow}>
          <span className={styles.riskName}>{district.name}</span>
          <span className={styles.riskScore}>{formatScore(district.risk_score)}</span>
        </span>
        <span className={styles.riskClassRow}>
          <span className={styles.riskClassDot} style={{ background: color }} aria-hidden="true" />
          <span>{riskClassLabel(district.risk_class)}</span>
          <span className={styles.riskAreaShare}>
            {formatPercent(district.area_share)} of district area
          </span>
          {district.valid_area_share < 1 ? (
            <span className={styles.riskCoverage} title="Share of district area with valid analysis cells">
              {formatPercent(district.valid_area_share)} coverage
            </span>
          ) : null}
        </span>
        <span className={styles.driverGrid}>
          {DRIVER_ORDER.map((driver) => (
            <span
              key={driver}
              className={styles.driver}
              data-driver={driver}
              data-listed={district.drivers.includes(driver) ? 'true' : 'false'}
            >
              <span className={styles.driverLabel}>{driverLabel(driver)}</span>
              <span className={styles.driverValue}>{driverValues[driver]}</span>
            </span>
          ))}
        </span>
      </span>
    </button>
  );
}
