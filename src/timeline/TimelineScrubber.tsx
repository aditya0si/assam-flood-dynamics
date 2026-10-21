import type { CSSProperties } from 'react';
import type { FloodSummary } from '../data/schemas';
import { formatStepCode, stepAriaText } from '../data/format';
import { useTimelineStore } from '../state/timelineStore';
import styles from './timeline.module.css';

interface TimelineScrubberProps {
  summary: FloodSummary;
}

export function TimelineScrubber({ summary }: TimelineScrubberProps) {
  const step = useTimelineStore((state) => state.step);
  const setStep = useTimelineStore((state) => state.setStep);
  const stepCount = summary.steps.length;
  const current = summary.steps[step] ?? summary.steps[0];
  const lastIndex = Math.max(0, stepCount - 1);
  const progress = lastIndex === 0 ? 0 : (step / lastIndex) * 100;
  const first = summary.steps[0];
  const last = summary.steps[stepCount - 1];

  return (
    <div className={styles.scrubberWrap}>
      <input
        className={styles.range}
        type="range"
        min={0}
        max={lastIndex}
        step={1}
        value={step}
        onChange={(event) => setStep(Number(event.target.value), 'user')}
        aria-label="Scenario step"
        aria-valuetext={stepAriaText(current, step, stepCount)}
        aria-keyshortcuts="ArrowLeft ArrowRight Home End"
        style={{ '--progress': `${progress}%` } as CSSProperties}
      />
      <div className={styles.rangeEnds} aria-hidden="true">
        <span>{first.step_label}</span>
        <span>{last.step_label}</span>
      </div>
      <div className={styles.ticks} role="group" aria-label="Timeline steps">
        {summary.steps.map((entry, index) => (
          <button
            key={entry.step}
            type="button"
            className={`${styles.tick} ${index === step ? styles.tickActive : ''}`}
            data-step={index}
            data-phase={entry.phase}
            onClick={() => setStep(index, 'user')}
            aria-current={index === step ? 'step' : undefined}
            aria-label={`${formatStepCode(index)} ${entry.step_label}, ${entry.phase}`}
            title={`${formatStepCode(index)} · ${entry.step_label} · ${entry.phase}`}
          >
            <span className={styles.tickMark} aria-hidden="true" />
            <span className={styles.tickLabel}>{formatStepCode(index)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
