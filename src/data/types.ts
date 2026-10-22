import type {
  DistrictRisk,
  Exposure,
  FeatureCollection,
  FloodSummary,
  FrameIndex,
  HotspotCollection,
  Manifest,
  MonsoonSeries,
  Provenance,
  Rainfall,
  RainfallForecast,
  RiskZoneCollection,
  Scenario,
  Scorecard,
  SummaryStep,
} from './schemas';

export interface Dataset {
  manifest: Manifest;
  scenario: Scenario;
  summary: FloodSummary;
  frameIndex: FrameIndex;
  districts: FeatureCollection;
  state: FeatureCollection;
  rivers: FeatureCollection;
  provenance: Provenance;
  districtRisk: DistrictRisk;
  series: MonsoonSeries;
  rainfall: Rainfall;
  rainfallForecast: RainfallForecast;
  exposure: Exposure;
  riskZones: RiskZoneCollection;
  hotspots: HotspotCollection;
  scorecard: Scorecard;
}

export interface DataSetMeta {
  datasetVersion: string;
  scenarioId: string;
  stepCount: number;
}

export type LoadPhase = 'idle' | 'loading' | 'ready' | 'error';

export interface LoadFailure {
  file: string;
  detail: string;
}

export function currentSummaryStep(summary: FloodSummary, step: number): SummaryStep {
  const clamped = Math.max(0, Math.min(step, summary.steps.length - 1));
  return summary.steps[clamped];
}
