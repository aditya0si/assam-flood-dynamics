import { useEffect, useState } from 'react';
import { DataContractError, loadDataset } from './data/loadData';
import type { Dataset, LoadFailure } from './data/types';
import { useTimelineStore } from './state/timelineStore';
import { TopBar } from './shell/TopBar';
import { StatusBar } from './shell/StatusBar';
import { ErrorBoundary } from './shell/ErrorBoundary';
import { MapCanvas } from './map/MapCanvas';
import { RightRail } from './shell/RightRail';
import { TimelineDock } from './timeline/TimelineDock';
import styles from './shell/shell.module.css';

type LoadPhase = 'loading' | 'ready' | 'error';

function AppShell() {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [phase, setPhase] = useState<LoadPhase>('loading');
  const [failure, setFailure] = useState<LoadFailure | null>(null);

  useEffect(() => {
    let alive = true;
    loadDataset()
      .then((loaded) => {
        if (!alive) return;
        useTimelineStore.getState().init(loaded.summary.steps.length, loaded.summary.peak_step);
        setDataset(loaded);
        setPhase('ready');
      })
      .catch((error: unknown) => {
        if (!alive) return;
        if (error instanceof DataContractError) {
          setFailure({ file: error.file, detail: error.detail });
        } else {
          setFailure({ file: 'dataset', detail: error instanceof Error ? error.message : String(error) });
        }
        setPhase('error');
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className={styles.app}>
      <nav className={styles.skipLinks} aria-label="Skip links">
        <a
          className={styles.skipLink}
          href="#scenario-timeline"
          onClick={(event) => {
            event.preventDefault();
            document.getElementById('scenario-timeline')?.focus();
          }}
        >
          Skip to scenario timeline
        </a>
        <a
          className={styles.skipLink}
          href="#analysis-rail"
          onClick={(event) => {
            event.preventDefault();
            document.getElementById('analysis-rail')?.focus();
          }}
        >
          Skip to analysis panels
        </a>
      </nav>

      <TopBar dataset={dataset} />

      <main className={styles.viewport} id="map-viewport">
        {phase === 'loading' ? (
          <div className={styles.loading} role="status" aria-live="polite">
            <div className={styles.loadingCard}>
              <span className={styles.loadingKicker}>Reading committed data</span>
              <span className={styles.loadingTitle}>Assam terrain, districts and the scenario timeline</span>
              <span className={styles.loadingBar} aria-hidden="true" />
              <p className={styles.loadingNote}>
                Local JSON and PNG frames only. No backend, no live feed, no forecast.
              </p>
            </div>
          </div>
        ) : null}

        {phase === 'error' && failure ? (
          <div className={styles.errorWrap} role="alert">
            <div className={styles.errorPanel}>
              <span className={styles.errorKicker}>Data contract error</span>
              <h1 className={styles.errorTitle}>The committed dataset did not validate</h1>
              <p className={styles.errorFile}>{failure.file}</p>
              <p className={styles.errorDetail}>{failure.detail}</p>
              <p className={styles.errorNote}>
                The app does not render partial geometry or fall back to invented values. Fix the
                named file in <code>public/data/</code> and reload.
              </p>
            </div>
          </div>
        ) : null}

        {phase === 'ready' && dataset ? (
          <>
            <div className={styles.mapArea}>
              <MapCanvas dataset={dataset} />
              <StatusBar />
            </div>
            <RightRail dataset={dataset} />
          </>
        ) : null}
      </main>

      <div className={styles.dockSlot}>
        {phase === 'ready' && dataset ? <TimelineDock dataset={dataset} /> : null}
      </div>
    </div>
  );
}

export function App() {
  return (
    <ErrorBoundary>
      <AppShell />
    </ErrorBoundary>
  );
}
