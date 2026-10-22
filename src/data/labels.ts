const BADGES: Record<string, string> = {
  observed: 'OBSERVED',
  reanalysis: 'REANALYSIS',
  derived: 'DERIVED',
  scenario: 'SCENARIO',
  // Legacy data classes still present in source files.  They are presented as
  // one of the four P1.6 badges rather than inventing a fifth label.
  synthetic: 'SCENARIO',
  source: 'DERIVED',
  reference: 'DERIVED',
};

export type DataClass = 'observed' | 'reanalysis' | 'derived' | 'scenario';

export function badgeClassFor(className: string): DataClass {
  if (className === 'observed' || className === 'reanalysis' || className === 'derived') {
    return className;
  }
  if (className === 'source' || className === 'reference') return 'derived';
  return 'scenario';
}

export function badgeFor(className: string): string {
  return BADGES[className] ?? BADGES[badgeClassFor(className)] ?? className.toUpperCase();
}

export function badgeTone(className: string): DataClass {
  return badgeClassFor(className);
}

export function phaseLabel(phase: string): string {
  if (phase.length === 0) return phase;
  return `${phase.charAt(0).toUpperCase()}${phase.slice(1)}`;
}

/** Parse a published data_as_of date without assuming a timezone suffix. */
export function parseDataAsOf(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}/.test(value)) return null;
  const date = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * P1.6: a visible age for every data surface.  Ages are relative to the current
 * clock, so the same committed file reads "10 months old" in October 2026 and
 * "11 months old" a month later.  Tests assert the date and the unit, not an
 * exact number.
 */
export function dataAge(value: string, now: Date = new Date()): string {
  const date = parseDataAsOf(value);
  if (!date) return 'age unknown';
  const days = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 86_400_000));
  if (days < 31) return `${days} day${days === 1 ? '' : 's'} old`;
  const months = Math.floor(days / 30.4375);
  if (months < 24) return `${months} month${months === 1 ? '' : 's'} old`;
  const years = Math.floor(days / 365.25);
  return `${years} year${years === 1 ? '' : 's'} old`;
}

export function dataAsOfText(value: string): string {
  return `data as of ${value.slice(0, 10)} · ${dataAge(value)}`;
}

export const HONESTY_CHIP = 'NOT A FORECAST';
