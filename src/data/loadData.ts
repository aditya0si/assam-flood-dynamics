import type { ZodType } from 'zod';
import {
  districtRiskSchema,
  featureCollectionSchema,
  floodSummarySchema,
  frameIndexSchema,
  hotspotFeatureCollectionSchema,
  manifestSchema,
  monsoonSeriesSchema,
  provenanceSchema,
  riskZoneFeatureCollectionSchema,
  scenarioSchema,
  scorecardSchema,
  type DistrictRisk,
  type FeatureCollection,
  type FloodSummary,
  type FrameIndex,
  type HotspotCollection,
  type Manifest,
  type MonsoonSeries,
  type Provenance,
  type RiskZoneCollection,
  type Scenario,
  type Scorecard,
} from './schemas';
import type { Dataset } from './types';

const DATA_ROOT = 'data/';

export class DataContractError extends Error {
  readonly file: string;
  readonly detail: string;

  constructor(file: string, detail: string) {
    super(`${file}: ${detail}`);
    this.name = 'DataContractError';
    this.file = file;
    this.detail = detail;
  }
}

/**
 * Resolve a committed data path against Vite's BASE_URL, never against an
 * absolute '/data/...' path. Works for both the dev server ('/') and the
 * GitHub Pages project build ('/assam-flood-dynamics/').
 */
export function dataUrl(path: string): string {
  const clean = path.replace(/^\/+/, '');
  return new URL(`${import.meta.env.BASE_URL}${DATA_ROOT}${clean}`, window.location.href).href;
}

function describeError(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

async function getJson<T>(schema: ZodType<T>, path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(dataUrl(path), {
      headers: { Accept: 'application/json' },
    });
  } catch (error) {
    throw new DataContractError(path, `network error (${describeError(error)})`);
  }

  if (!response.ok) {
    throw new DataContractError(path, `HTTP ${response.status} ${response.statusText}`);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch (error) {
    throw new DataContractError(path, `invalid JSON (${describeError(error)})`);
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    const issue = parsed.error.issues[0];
    const location = issue && issue.path.length > 0 ? issue.path.join('.') : '(root)';
    throw new DataContractError(path, `${location}: ${issue?.message ?? 'schema validation failed'}`);
  }
  return parsed.data;
}

function assertSameDataset(label: string, value: string, expected: string): void {
  if (value !== expected) {
    throw new DataContractError(label, `dataset_version "${value}" does not match manifest "${expected}"`);
  }
}

function assertSteps(label: string, steps: Array<{ step: number }>, expectedCount: number, prefix: string): void {
  if (steps.length !== expectedCount) {
    throw new DataContractError(label, `expected ${expectedCount} ${prefix}, found ${steps.length}`);
  }
  for (let index = 0; index < steps.length; index += 1) {
    if (steps[index].step !== index) {
      throw new DataContractError(label, `step ${index} is missing or out of order (found ${steps[index].step})`);
    }
  }
}

export async function loadDataset(): Promise<Dataset> {
  const manifest: Manifest = await getJson(manifestSchema, 'manifest.json');

  const [
    scenario,
    summary,
    frameIndex,
    districts,
    state,
    rivers,
    provenance,
    districtRisk,
    series,
    riskZones,
    hotspots,
    scorecard,
  ] = await Promise.all([
    getJson(scenarioSchema, 'scenario.json'),
    getJson(floodSummarySchema, 'flood/flood-summary.json'),
    getJson(frameIndexSchema, 'flood/frame-index.json'),
    getJson(featureCollectionSchema, 'admin/assam-districts.geojson'),
    getJson(featureCollectionSchema, 'admin/assam-state.geojson'),
    getJson(featureCollectionSchema, 'hydro/assam-rivers.geojson'),
    getJson(provenanceSchema, 'provenance.json'),
    getJson(districtRiskSchema, 'risk/district-risk.json'),
    getJson(monsoonSeriesSchema, 'series/monsoon-series.json'),
    getJson(riskZoneFeatureCollectionSchema, 'risk/risk-zones.geojson'),
    getJson(hotspotFeatureCollectionSchema, 'risk/hotspots.geojson'),
    getJson(scorecardSchema, 'validation/scorecard.json'),
  ]);

  assertSameDataset('flood/frame-index.json', frameIndex.dataset_version, manifest.dataset_version);
  assertSameDataset('provenance.json', provenance.dataset_version, manifest.dataset_version);
  assertSameDataset('series/monsoon-series.json', series.dataset_version, manifest.dataset_version);
  assertSameDataset('risk/risk-zones.geojson', riskZones.dataset_version, manifest.dataset_version);
  assertSameDataset('risk/hotspots.geojson', hotspots.dataset_version, manifest.dataset_version);

  if (scenario.scenario_id !== manifest.scenario_id || summary.scenario_id !== manifest.scenario_id) {
    throw new DataContractError('manifest.json', 'scenario_id does not match the committed scenario and summary');
  }
  if (frameIndex.scenario_id !== manifest.scenario_id) {
    throw new DataContractError('flood/frame-index.json', 'scenario_id does not match the manifest');
  }
  if (districtRisk.scenario_id !== manifest.scenario_id || series.scenario_id !== manifest.scenario_id) {
    throw new DataContractError('manifest.json', 'scenario_id does not match the committed risk and series files');
  }

  if (districtRisk.districts.length !== districtRisk.counts.total) {
    throw new DataContractError(
      'risk/district-risk.json',
      `counts.total ${districtRisk.counts.total} does not match ${districtRisk.districts.length} districts`,
    );
  }
  const ranks = new Set<number>();
  const severityRanks = new Set<number>();
  for (const district of districtRisk.districts) {
    if (!Number.isFinite(district.risk_score)) {
      throw new DataContractError('risk/district-risk.json', `${district.name} has a non-finite risk_score`);
    }
    if (!Number.isFinite(district.severity_index)) {
      throw new DataContractError('risk/district-risk.json', `${district.name} has a non-finite severity_index`);
    }
    if (ranks.has(district.rank)) {
      throw new DataContractError('risk/district-risk.json', `rank ${district.rank} is duplicated`);
    }
    ranks.add(district.rank);
    if (severityRanks.has(district.severity_rank)) {
      throw new DataContractError(
        'risk/district-risk.json',
        `severity_rank ${district.severity_rank} is duplicated`,
      );
    }
    severityRanks.add(district.severity_rank);
  }
  if (scorecard.summary.caveats.length === 0) {
    throw new DataContractError('validation/scorecard.json', 'caveats are empty');
  }
  if (!scorecard.summary.caveats.some((caveat) => /not an event hindcast/i.test(caveat))) {
    throw new DataContractError(
      'validation/scorecard.json',
      'the required "not an event hindcast" caveat is missing',
    );
  }
  if (scorecard.summary.caveats.some((caveat) => /calibration was unavailable/i.test(caveat))) {
    throw new DataContractError(
      'validation/scorecard.json',
      'a caveat claims calibration was unavailable, but the SAFE LUT is applied',
    );
  }
  for (const entry of provenance.entries) {
    if (entry.class === 'source' && entry.pipeline.length === 0) {
      throw new DataContractError('provenance.json', `${entry.id} has no processing stage`);
    }
  }

  assertSteps('scenario.json', scenario.steps, manifest.step_count, 'scenario steps');
  assertSteps('flood/flood-summary.json', summary.steps, manifest.step_count, 'summary steps');
  assertSteps('flood/frame-index.json', frameIndex.steps.map((step) => ({ step: step.id })), manifest.step_count, 'frame steps');

  if (summary.peak_step < 0 || summary.peak_step >= summary.steps.length) {
    throw new DataContractError('flood/flood-summary.json', `peak_step ${summary.peak_step} is outside the step range`);
  }

  summary.steps.forEach((step, index) => {
    const frame = frameIndex.steps[index];
    if (step.frame_file !== frame.file) {
      throw new DataContractError(
        'flood/flood-summary.json',
        `step ${index} frame_file "${step.frame_file}" does not match frame-index "${frame.file}"`,
      );
    }
    if (step.step_label !== frame.label) {
      throw new DataContractError(
        'flood/frame-index.json',
        `step ${index} label "${frame.label}" does not match summary "${step.step_label}"`,
      );
    }
  });

  return {
    manifest,
    scenario,
    summary,
    frameIndex,
    districts,
    state,
    rivers,
    provenance,
    districtRisk,
    series,
    riskZones,
    hotspots,
    scorecard,
  };
}

export type {
  DistrictRisk,
  FeatureCollection,
  FloodSummary,
  FrameIndex,
  HotspotCollection,
  Manifest,
  MonsoonSeries,
  Provenance,
  RiskZoneCollection,
  Scenario,
  Scorecard,
};
