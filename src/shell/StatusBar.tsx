import { tileHealthCopy } from '../map/tileHealthState';
import { useTileHealthStore } from '../state/tileHealthStore';
import styles from './shell.module.css';

export function StatusBar() {
  const health = useTileHealthStore((state) => state.snapshot);
  const status = tileHealthCopy(health);

  return (
    <div className={styles.statusBar} role="status" aria-live="polite">
      <span className={`${styles.statusDot} ${styles[`status-${status.tone}`]}`} aria-hidden="true" />
      <span>{status.text}</span>
    </div>
  );
}
