import type { Dataset } from '../data/types';
import { SYNTHETIC_SERIES_NOTE } from '../data/attribution';
import { formatArea, formatPercent, formatPhase, formatStage, formatStepCode, stepAriaText } from '../data/format';
import { badgeFor } from '../data/labels';
import { useTimelineStore } from '../state/timelineStore';
import { ChartGrid } from '../charts/ChartGrid';
import { PlaybackControls } from './PlaybackControls';
import { TimelineScrubber } from './TimelineScrubber';
import { usePlayback } from './usePlayback';
import styles from './timeline.module.css';

interface TimelineDockProps {
  dataset: Dataset;
}

interface MetricProps {
  label: string;
  value: string;
  unit?: string;
  detail?: string;
}

function Metric({ label, value, unit, detail }: MetricProps) {
  return (
    <div className={styles.metric}>
      <span className={styles.metricLabel}>{label}</span>
      <span className={styles.metricValue}>
        {value}
        {unit ? <span className={styles.metricUnit}>{unit}</span> : null}
      </span>
      {detail ? <span className={styles.metricDetail}>{detail}</span> : null}
    </div>
  );
}

export function TimelineDock({ dataset }: TimelineDockProps) {
  usePlayback();
  const step = useTimelineStore((state) => state.step);
  const stepCount = dataset.summary.steps.length;
  const current = dataset.summary.steps[step] ?? dataset.summary.steps[0];

  return (
    <section
      id="scenario-timeline"
      className={styles.dock}
      aria-label="Scenario timeline"
      tabIndex={0}
      data-timeline="true"
    >
      <div className={styles.dockMain}>
        <div className={styles.dockHeader}>
          <PlaybackControls />

          <div className={styles.identity}>
            <span className={styles.stepCode}>{formatStepCode(step)}</span>
            <div className={styles.identityText}>
              <h2 className={styles.stepLabel}>{current.step_label}</h2>
              <span className={styles.stepMeta}>
                {formatPhase(current.phase)} · day {current.day_offset} of the scenario
              </span>
            </div>
          </div>

          <span className={styles.classBadge}>{badgeFor(dataset.summary.class)}</span>
        </div>

        <div className={styles.metrics}>
          <Metric label="Scenario stage" value={formatStage(current.stage_m)} unit="m" />
          <Metric label="Inundated area" value={formatArea(current.inundated_area_km2)} unit="km²" />
          <Metric label="Share of Assam" value={formatPercent(current.share_of_assam)} />
          <Metric label="Share of flood-prone area" value={formatPercent(current.share_of_flood_prone_area)} />
        </div>

        <TimelineScrubber summary={dataset.summary} />
      </div>

      <div className={styles.chartPane}>
        <div className={styles.chartPaneHead}>
          <span className={styles.paneKicker}>Timeline analytics</span>
          <span className={styles.syntheticBadge}>{badgeFor(dataset.summary.series_class.rainfall)}</span>
        </div>
        <ChartGrid summary={dataset.summary} series={dataset.series} />
        <p className={styles.seriesNote}>{SYNTHETIC_SERIES_NOTE} · area is scenario-derived.</p>
      </div>

      <p className={styles.srOnly} aria-live="polite" aria-atomic="true">
        {stepAriaText(current, step, stepCount)}
      </p>
    </section>
  );
}
