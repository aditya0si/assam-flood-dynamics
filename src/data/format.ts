import type { SummaryStep } from './schemas';

/** Locale-stable area label. No thousands separator, so the peak reads as committed. */
export function formatArea(km2: number): string {
  return km2.toFixed(1);
}

/** Trim floating-point noise while keeping at least one decimal. */
export function formatStage(metres: number): string {
  const rounded = Math.round(metres * 100) / 100;
  return Number.isInteger(rounded) ? rounded.toFixed(1) : String(rounded);
}

export function formatPercent(share: number): string {
  return `${(share * 100).toFixed(1)}%`;
}

export function formatStepCode(step: number): string {
  return `S${String(step).padStart(2, '0')}`;
}

export function formatStepNumber(step: number, stepCount: number): string {
  return `Step ${step + 1} of ${stepCount}`;
}

export function formatPhase(phase: string): string {
  if (phase.length === 0) return phase;
  return `${phase.charAt(0).toUpperCase()}${phase.slice(1)}`;
}

export function formatDepthBand(minM: number | null, maxM: number | null): string {
  if (minM === null && maxM === null) return 'depth class';
  if (maxM === null) return `${formatStage(minM ?? 0)}+ m`;
  if (minM === null) return `≤ ${formatStage(maxM)} m`;
  return `${formatStage(minM)}–${formatStage(maxM)} m`;
}

export function formatShareValue(share: number): string {
  return formatPercent(share);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function stepAriaText(step: SummaryStep, index: number, stepCount: number): string {
  return `${formatStepNumber(index, stepCount)}, ${step.step_label}, ${step.phase}, scenario stage ${formatStage(
    step.stage_m,
  )} metres, ${formatArea(step.inundated_area_km2)} square kilometres inundated`;
}
