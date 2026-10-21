import type { ZodType } from 'zod';
import {
  featureCollectionSchema,
  floodSummarySchema,
  frameIndexSchema,
  manifestSchema,
  scenarioSchema,
  type FeatureCollection,
  type FloodSummary,
  type FrameIndex,
  type Manifest,
  type Scenario,
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
 * GitHub Pages project build ('/baanh/').
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

  const [scenario, summary, frameIndex, districts, state, rivers] = await Promise.all([
    getJson(scenarioSchema, 'scenario.json'),
    getJson(floodSummarySchema, 'flood/flood-summary.json'),
    getJson(frameIndexSchema, 'flood/frame-index.json'),
    getJson(featureCollectionSchema, 'admin/assam-districts.geojson'),
    getJson(featureCollectionSchema, 'admin/assam-state.geojson'),
    getJson(featureCollectionSchema, 'hydro/assam-rivers.geojson'),
  ]);

  assertSameDataset('flood/frame-index.json', frameIndex.dataset_version, manifest.dataset_version);

  if (scenario.scenario_id !== manifest.scenario_id || summary.scenario_id !== manifest.scenario_id) {
    throw new DataContractError('manifest.json', 'scenario_id does not match the committed scenario and summary');
  }
  if (frameIndex.scenario_id !== manifest.scenario_id) {
    throw new DataContractError('flood/frame-index.json', 'scenario_id does not match the manifest');
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

  return { manifest, scenario, summary, frameIndex, districts, state, rivers };
}

export type { FeatureCollection, FloodSummary, FrameIndex, Manifest, Scenario };
