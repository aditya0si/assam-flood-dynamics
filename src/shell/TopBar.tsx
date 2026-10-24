import type { Dataset } from '../data/types';
import { HONESTY_CHIP } from '../data/labels';
import { formatPhase, formatStepCode } from '../data/format';
import { useTimelineStore } from '../state/timelineStore';
import { ClassBadge, DataAge } from './DataBadge';
import styles from './shell.module.css';

interface TopBarProps {
  dataset: Dataset | null;
}

function FloodMark() {
  return (
    <svg className={styles.mark} viewBox="0 0 64 64" aria-hidden="true">
      <path
        d="M10 38c6-7 11-7 17 0s11 7 17 0 7-5 10-2"
        fill="none"
        stroke="#7cc7e8"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path
        d="M10 49c6-7 11-7 17 0s11 7 17 0 7-5 10-2"
        fill="none"
        stroke="#3d82a3"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <path d="M32 9v22M21 31h22" stroke="#c2d3da" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function TopBar({ dataset }: TopBarProps) {
  const step = useTimelineStore((state) => state.step);
  const stepCount = useTimelineStore((state) => state.stepCount);
  const current = dataset?.summary.steps[step];
  const scenarioClass = dataset?.summary.class ?? 'scenario';

  return (
    <header className={styles.topbar}>
      <div className={styles.brand}>
        <FloodMark />
        <div className={styles.brandText}>
          <h1 className={styles.brandName}>Baanh</h1>
          <span className={styles.brandSub}>Assam Flood Dynamics</span>
        </div>
      </div>

      <div className={styles.scenarioTitle}>
        <span className={styles.scenarioKicker}>Composite monsoon scenario</span>
        <span className={styles.scenarioName}>
          {dataset?.scenario.name ?? 'HAND-threshold terrain scenario'}
        </span>
      </div>

      <div className={styles.topMeta}>
        <span className={styles.notForecast} title="Explanatory synthetic scenario, not an operational product">
          {HONESTY_CHIP}
        </span>
        <ClassBadge className={scenarioClass} />
        {dataset ? (
          <>
            <span className={styles.datasetVersion}>data {dataset.manifest.dataset_version}</span>
            <DataAge className={styles.datasetVersion} dataAsOf={dataset.summary.data_as_of} compact />
          </>
        ) : null}
      </div>

      <div className={styles.stepReadout} aria-live="off">
        {dataset && current ? (
          <>
            <span className={styles.stepCode}>{formatStepCode(step)}</span>
            <span className={styles.stepLabel}>{current.step_label}</span>
            <span className={styles.stepPhase}>{formatPhase(current.phase)}</span>
            <span className={styles.stepPosition}>
              {step + 1}/{stepCount}
            </span>
          </>
        ) : (
          <span className={styles.stepPosition}>loading data</span>
        )}
      </div>
    </header>
  );
}
