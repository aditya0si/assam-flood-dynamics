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
      aria-label={`${district.name}, extent score ${formatScore(district.risk_score)} of 100 rank ${
        district.rank
      }, severity index ${formatScore(district.severity_index)} rank ${district.severity_rank}. Focus district on the map.`}
      data-district-id={district.district_id}
      data-rank={district.rank}
      data-severity-rank={district.severity_rank}
      data-severity-index={formatScore(district.severity_index)}
      data-score={formatScore(district.risk_score)}
      data-coverage={district.valid_area_share}
    >
      <span className={styles.riskRanks}>
        <span className={styles.riskRank} title="Extent rank">
          #{district.rank}
          <em>extent</em>
        </span>
        <span className={styles.riskRankSeverity} title="Severity rank">
          #{district.severity_rank}
          <em>severity</em>
        </span>
      </span>
      <span className={styles.riskBody}>
        <span className={styles.riskTitleRow}>
          <span className={styles.riskName}>{district.name}</span>
          <span className={styles.riskScoreGroup}>
            <span className={styles.riskScoreLabel}>Extent score</span>
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
          aria-label={`Severity inputs for ${district.name}, separate from the extent score`}
          data-depth-share={district.depth_over_1_5m_share}
          data-median-depth={district.median_depth_m}
        >
          <span className={styles.depthContextLabel}>Severity inputs · not in extent score</span>
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
          <span className={styles.contextMetric}>
            <span className={styles.contextMetricLabel}>Severity index</span>
            <span className={styles.contextTrack} aria-hidden="true">
              <span
                className={styles.contextFill}
                style={{ width: `${district.severity_index}%` }}
              />
            </span>
            <span className={styles.contextValue}>
              {formatScore(district.severity_index)} · #{district.severity_rank}
            </span>
          </span>
        </span>
      </span>
    </button>
  );
}
