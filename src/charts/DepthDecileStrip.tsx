import type { SummaryStep } from '../data/schemas';
import { formatDepthValue, formatStepCode } from '../data/format';
import styles from '../timeline/timeline.module.css';

interface DepthDecileStripProps {
  step: SummaryStep;
}

const DECILE_KEYS = ['p10', 'p25', 'p50', 'p75', 'p90', 'p95'] as const;

export function DepthDecileStrip({ step }: DepthDecileStripProps) {
  const values = DECILE_KEYS.map((key) => step.delay_deciles[key]);
  const maxValue = Math.max(...values, 1);

  return (
    <figure
      className={styles.decileFigure}
      aria-label={`Depth deciles at ${formatStepCode(step.step)}: ${values
        .map((value) => `${formatDepthValue(value)} metres`)
        .join(', ')}`}
    >
      <figcaption className={styles.decileCaption}>
        <span>Depth deciles over wet cells</span>
        <span className={styles.chartMuted}>
          {formatStepCode(step.step)} · {step.step_label} · {step.wet_cells.toLocaleString('en-US')} wet cells
        </span>
      </figcaption>
      <div className={styles.decileStrip}>
        {DECILE_KEYS.map((key, index) => {
          const value = values[index];
          return (
            <span
              key={key}
              className={styles.decileCell}
              data-decile={key}
              data-value={formatDepthValue(value)}
              title={`${key.toUpperCase()} ${formatDepthValue(value)} m`}
            >
              <span className={styles.decileBarWrap} aria-hidden="true">
                <span
                  className={styles.decileBar}
                  style={{ height: `${Math.max(3, (value / maxValue) * 100)}%` }}
                />
              </span>
              <span className={styles.decileKey}>{key.toUpperCase()}</span>
              <span className={styles.decileValue}>{formatDepthValue(value)}</span>
            </span>
          );
        })}
      </div>
      <p className={styles.decileNote}>
        Bathtub depth percentiles from <code>flood-summary.json</code>; six ordered values, not a
        distribution average.
      </p>
    </figure>
  );
}
