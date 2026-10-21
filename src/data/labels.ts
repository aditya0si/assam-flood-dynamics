const BADGES: Record<string, string> = {
  source: 'SOURCE',
  derived: 'DERIVED',
  scenario: 'SCENARIO',
  synthetic: 'SYNTHETIC',
  reference: 'REFERENCE',
};

export function badgeFor(className: string): string {
  return BADGES[className] ?? className.toUpperCase();
}

export function badgeTone(className: string): 'scenario' | 'synthetic' | 'source' | 'derived' | 'reference' {
  if (className === 'scenario') return 'scenario';
  if (className === 'synthetic') return 'synthetic';
  if (className === 'derived') return 'derived';
  if (className === 'reference') return 'reference';
  return 'source';
}

export function phaseLabel(phase: string): string {
  if (phase.length === 0) return phase;
  return `${phase.charAt(0).toUpperCase()}${phase.slice(1)}`;
}

export const HONESTY_CHIP = 'NOT A FORECAST';
