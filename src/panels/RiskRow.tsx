import type { DistrictRiskEntry } from '../data/schemas';
import { formatArea, formatDays, formatDepthValue, formatPercent, formatScore } from '../data/format';
import { driverLabel, riskClassColor, riskClassLabel } from '../data/risk';
import styles from './panels.module.css';

interface RiskRowProps {
  district: DistrictRiskEntry;
  selected: boolean;
  depthShareMax: number;
  medianDepthMax: number;
  onSelect: (districtId: string) => void;
}

const SCORED_DRIVERS = ['area', 'duration'] as const;
const COVERAGE_BADGE_THRESHOLD = 0.75;

export function RiskRow({
  district,
  selected,
  depthShareMax,
  medianDepthMax,
  onSelect,
}: RiskRowProps) {
  const driverValues: Record<(typeof SCORED_DRIVERS)[number], string> = {
    area: `${formatArea(district.peak_flooded_area_km2)} km²`,
    duration: `${formatDays(district.mean_duration_days)} d`,
  };
  const color = riskClassColor(district.risk_class);
  // P0.3: below 75% valid coverage the score is computed on a minority of the
  // district and must say so next to the score and on the row.
  const lowCoverage = district.valid_area_share < COVERAGE_BADGE_THRESHOLD;
  const depthShareWidth = Math.min(100, (district.depth_over_1_5m_share / depthShareMax) * 100);
  const medianDepthWidth = Math.min(100, (district.median_depth_m / medianDepthMax) * 100);

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
      data-coverage={district.valid_area_share}
    >
      <span className={styles.riskRank}>{district.rank}</span>
      <span className={styles.riskBody}>
        <span className={styles.riskTitleRow}>
          <span className={styles.riskName}>{district.name}</span>
          <span className={styles.riskScoreGroup}>
            <span className={styles.riskScore}>{formatScore(district.risk_score)}</span>
            {lowCoverage ? (
              <span
                className={styles.riskCoverageBadge}
                data-coverage-badge="true"
                title="Share of district area with valid analysis cells"
              >
                coverage {formatPercent(district.valid_area_share)}
              </span>
            ) : null}
          </span>
        </span>
        <span className={styles.riskClassRow}>
          <span className={styles.riskClassDot} style={{ background: color }} aria-hidden="true" />
          <span>{riskClassLabel(district.risk_class)}</span>
          <span className={styles.riskAreaShare}>
            {formatPercent(district.area_share)} of district area
          </span>
          {lowCoverage ? (
            <span className={styles.riskCoverageNote} data-coverage-note="true">
              Scored on the AOI-covered share only
            </span>
          ) : null}
        </span>
        <span className={styles.driverGrid}>
          {SCORED_DRIVERS.map((driver) => (
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
        <span
          className={styles.depthContext}
          aria-label={`Depth context for ${district.name}, reported but not scored`}
          data-depth-share={district.depth_over_1_5m_share}
          data-median-depth={district.median_depth_m}
        >
          <span className={styles.depthContextLabel}>Depth context · reported, not scored</span>
          <span className={styles.contextMetric}>
            <span className={styles.contextMetricLabel}>Depth &gt;1.5 m</span>
            <span className={styles.contextTrack} aria-hidden="true">
              <span className={styles.contextFill} style={{ width: `${depthShareWidth}%` }} />
            </span>
            <span className={styles.contextValue}>
              {formatPercent(district.depth_over_1_5m_share)}
            </span>
          </span>
          <span className={styles.contextMetric}>
            <span className={styles.contextMetricLabel}>Median depth</span>
            <span className={styles.contextTrack} aria-hidden="true">
              <span className={styles.contextFill} style={{ width: `${medianDepthWidth}%` }} />
            </span>
            <span className={styles.contextValue}>{formatDepthValue(district.median_depth_m)} m</span>
          </span>
        </span>
      </span>
    </button>
  );
}
