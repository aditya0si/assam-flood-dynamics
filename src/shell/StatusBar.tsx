import type { TileHealthSnapshot } from '../map/tileHealth';
import styles from './shell.module.css';

interface StatusBarProps {
  health: TileHealthSnapshot;
}

function statusCopy(health: TileHealthSnapshot): { text: string; tone: 'ok' | 'warn' | 'bad' | 'loading' } {
  if (health.dem === 'offline' && health.imagery === 'offline') {
    return { text: 'Offline basemap · committed relief', tone: 'bad' };
  }
  if (health.imagery === 'offline') {
    return { text: 'Imagery offline · hillshade terrain', tone: 'warn' };
  }
  if (health.dem === 'offline') {
    return { text: '3D terrain offline · flat satellite', tone: 'warn' };
  }
  if (health.dem === 'ok' && health.imagery === 'ok') {
    return { text: 'Terrain and imagery live', tone: 'ok' };
  }
  if (health.dem === 'degraded' || health.imagery === 'degraded') {
    return { text: 'Tile hosts degraded · overlays intact', tone: 'warn' };
  }
  return { text: 'Connecting to tile hosts', tone: 'loading' };
}

export function StatusBar({ health }: StatusBarProps) {
  const status = statusCopy(health);
  return (
    <div className={styles.statusBar} role="status" aria-live="polite">
      <span className={`${styles.statusDot} ${styles[`status-${status.tone}`]}`} aria-hidden="true" />
      <span>{status.text}</span>
    </div>
  );
}
