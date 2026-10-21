import type { DistrictRisk, DistrictRiskEntry, HotspotProperties } from './schemas';

export type RiskClass = 'low' | 'moderate' | 'high' | 'very_high';

export const RISK_CLASS_LABELS: Record<RiskClass, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  very_high: 'Very high',
};

export const RISK_CLASS_ORDER: RiskClass[] = ['low', 'moderate', 'high', 'very_high'];

/** Ordered light-teal -> amber -> coral -> magenta; text repeats the class. */
export const RISK_CLASS_COLORS: Record<RiskClass, string> = {
  low: '#79c9ae',
  moderate: '#e8b65a',
  high: '#e07a63',
  very_high: '#d95f9b',
};

export function isRiskClass(value: string): value is RiskClass {
  return value === 'low' || value === 'moderate' || value === 'high' || value === 'very_high';
}

export function riskClassLabel(value: string): string {
  return isRiskClass(value) ? RISK_CLASS_LABELS[value] : value.replace(/_/g, ' ');
}

export function riskClassColor(value: string): string {
  return isRiskClass(value) ? RISK_CLASS_COLORS[value] : '#93a8b1';
}

export function rankedDistricts(risk: DistrictRisk): DistrictRiskEntry[] {
  return [...risk.districts].sort((left, right) => {
    if (left.rank !== right.rank) return left.rank - right.rank;
    return right.risk_score - left.risk_score;
  });
}

export function topDistrict(risk: DistrictRisk): DistrictRiskEntry | null {
  return rankedDistricts(risk)[0] ?? null;
}

export function driverLabel(driver: string): string {
  if (driver === 'area') return 'Inundated area';
  if (driver === 'duration') return 'Duration';
  if (driver === 'depth') return 'Peak depth';
  return driver;
}

export function hotspotDisplayName(hotspot: HotspotProperties, districtName: string | null): string {
  const place = districtName ? `${districtName} · ` : '';
  return `${place}${hotspot.hotspot_id} low-HAND pocket`;
}

export function hotspotReasonLabel(reason: string): string {
  return reason.replace(/_/g, ' ');
}
