import type { HTMLAttributes } from 'react';
import { badgeClassFor, badgeFor, dataAge, dataAsOfText } from '../data/labels';
import styles from './dataBadge.module.css';

interface ClassBadgeProps {
  className: string;
  label?: string;
}

/** One of the four P1.6 labels: OBSERVED, REANALYSIS, DERIVED, SCENARIO. */
export function ClassBadge({ className: dataClass, label }: ClassBadgeProps) {
  const tone = badgeClassFor(dataClass);
  return (
    <span className={`${styles.badge} ${styles[tone]}`} data-class-badge={tone}>
      {label ?? badgeFor(dataClass)}
    </span>
  );
}

interface DataAgeProps extends HTMLAttributes<HTMLSpanElement> {
  dataAsOf: string;
  compact?: boolean;
}

/** Visible "data as of ... · N old" age for a data surface. */
export function DataAge({ dataAsOf, compact = false, ...rest }: DataAgeProps) {
  return (
    <span
      {...rest}
      className={`${styles.age} ${compact ? styles.ageCompact : ''} ${rest.className ?? ''}`.trim()}
      data-data-as-of={dataAsOf.slice(0, 10)}
      data-age={dataAge(dataAsOf)}
      title={`data as of ${dataAsOf.slice(0, 10)} (${dataAge(dataAsOf)})`}
    >
      {dataAsOfText(dataAsOf)}
    </span>
  );
}
