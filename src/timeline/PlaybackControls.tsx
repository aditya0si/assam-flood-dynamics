import { useTimelineStore, type Speed } from '../state/timelineStore';
import styles from './timeline.module.css';

function PrevIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M13.5 4.5 7 10l6.5 5.5V4.5Z" fill="currentColor" />
      <rect x="4" y="4.5" width="2" height="11" rx="1" fill="currentColor" />
    </svg>
  );
}

function NextIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M6.5 4.5 13 10l-6.5 5.5V4.5Z" fill="currentColor" />
      <rect x="14" y="4.5" width="2" height="11" rx="1" fill="currentColor" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M6.5 4.3 15 10l-8.5 5.7V4.3Z" fill="currentColor" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <rect x="5" y="4" width="3.4" height="12" rx="1" fill="currentColor" />
      <rect x="11.6" y="4" width="3.4" height="12" rx="1" fill="currentColor" />
    </svg>
  );
}

const SPEEDS: Speed[] = [0.5, 1, 2];

function speedLabel(speed: Speed): string {
  return `${speed}×`;
}

export function PlaybackControls() {
  const step = useTimelineStore((state) => state.step);
  const stepCount = useTimelineStore((state) => state.stepCount);
  const playing = useTimelineStore((state) => state.playing);
  const speed = useTimelineStore((state) => state.speed);
  const framesReady = useTimelineStore((state) => state.framesReady);
  const setStep = useTimelineStore((state) => state.setStep);
  const stepBy = useTimelineStore((state) => state.stepBy);
  const toggle = useTimelineStore((state) => state.toggle);
  const setSpeed = useTimelineStore((state) => state.setSpeed);

  const atStart = step <= 0;
  const atEnd = stepCount === 0 || step >= stepCount - 1;

  return (
    <div className={styles.transport} aria-label="Playback controls">
      <button
        type="button"
        className={styles.iconButton}
        onClick={() => stepBy(-1)}
        disabled={atStart}
        aria-label="Previous scenario step"
        aria-keyshortcuts="ArrowLeft"
        title="Previous step (ArrowLeft)"
      >
        <PrevIcon />
      </button>
      <button
        type="button"
        className={`${styles.iconButton} ${styles.playButton}`}
        onClick={toggle}
        disabled={!framesReady}
        aria-label={playing ? 'Pause scenario playback' : 'Play scenario playback'}
        aria-keyshortcuts="Space"
        title={framesReady ? 'Play/pause (Space)' : 'Loading flood frames'}
      >
        {playing ? <PauseIcon /> : <PlayIcon />}
      </button>
      <button
        type="button"
        className={styles.iconButton}
        onClick={() => stepBy(1)}
        disabled={atEnd}
        aria-label="Next scenario step"
        aria-keyshortcuts="ArrowRight"
        title="Next step (ArrowRight)"
      >
        <NextIcon />
      </button>

      <div className={styles.speedGroup} role="group" aria-label="Playback speed">
        {SPEEDS.map((value) => (
          <button
            key={value}
            type="button"
            className={`${styles.speedButton} ${speed === value ? styles.speedActive : ''}`}
            onClick={() => setSpeed(value)}
            aria-pressed={speed === value}
            aria-label={`Playback speed ${speedLabel(value)}`}
          >
            {speedLabel(value)}
          </button>
        ))}
      </div>
      <button
        type="button"
        className={styles.stepButton}
        onClick={() => setStep(0, 'user')}
        aria-label="Jump to first scenario step"
        aria-keyshortcuts="Home"
      >
        First
      </button>
    </div>
  );
}
