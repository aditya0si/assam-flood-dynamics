import type { Dataset } from '../data/types';
import { useState } from 'react';
import { formatArea, formatPercent, formatPhase, formatStage, formatStepCode, stepAriaText } from '../data/format';
import { useTimelineStore } from '../state/timelineStore';
import { ClassBadge, DataAge } from '../shell/DataBadge';
import { ChartGrid } from '../charts/ChartGrid';
import { DepthDecileStrip } from '../charts/DepthDecileStrip';
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
  const [expanded, setExpanded] = useState(true);
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
      data-expanded={expanded}
      data-rail-size={expanded ? 'default' : 'collapsed'}
    >
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

          <div className={styles.timelineTrack}><TimelineScrubber summary={dataset.summary} /></div>
          <button type="button" className={styles.collapseButton} aria-expanded={expanded}
            aria-controls="timeline-analytics" onClick={() => setExpanded((value) => !value)}>
            {expanded ? 'Hide analytics' : 'Show analytics'} <span aria-hidden="true">{expanded ? '⌄' : '⌃'}</span>
          </button>
        </div>
      <div id="timeline-analytics" role="region" aria-label="Timeline analytics" className={styles.analytics} hidden={!expanded}>
      <div className={styles.dockMain}>
        <div className={styles.chartPaneHead}>
          <span className={styles.paneKicker}>Scenario snapshot</span>
          <span className={styles.chartPaneBadges}>
            <ClassBadge className={dataset.summary.class} />
            <DataAge dataAsOf={dataset.summary.data_as_of} compact />
          </span>
        </div>
        {step === 0 ? <p className={styles.onset} role="status">Onset — no accumulated change yet.</p> : null}
        <div className={styles.metrics}>
          <Metric label="Scenario stage" value={formatStage(current.stage_m)} unit="m" />
          <Metric label="Inundated area" value={formatArea(current.inundated_area_km2)} unit="km²" />
          <Metric label="Share of Assam" value={formatPercent(current.share_of_assam)} />
          <Metric label="Flood-prone share" value={formatPercent(current.share_of_flood_prone_area)} />
        </div>

        <div className={styles.decileSlot}>
          <DepthDecileStrip step={current} />
        </div>


      </div>

      <div className={styles.chartPane}>

        <ChartGrid
          summary={dataset.summary}
          series={dataset.series}
          rainfall={dataset.rainfall}
          forecast={dataset.rainfallForecast}
        />
      </div>
      </div>

      <p className={styles.srOnly} aria-live="polite" aria-atomic="true">
        {stepAriaText(current, step, stepCount)}
      </p>
    </section>
  );
}
