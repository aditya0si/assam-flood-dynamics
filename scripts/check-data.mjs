#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { decodePng, countOpaquePixels } from './lib/png.mjs';
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
} from '../src/data/schemas.ts';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DATA = path.join(ROOT, 'public', 'data');
const FAILURES = [];
const CHECKS = [];
const cache = new Map();

function readJson(relative) {
  if (cache.has(relative)) return cache.get(relative);
  const absolute = path.join(DATA, relative);
  const raw = fs.readFileSync(absolute, 'utf8');
  const value = JSON.parse(raw);
  cache.set(relative, value);
  return value;
}

function fail(message) {
  FAILURES.push(message);
  throw new Error(message);
}

function assert(condition, message) {
  if (!condition) fail(message);
}

function close(actual, expected, tolerance, label) {
  assert(Number.isFinite(actual), `${label}: not a finite number (${actual})`);
  assert(
    Math.abs(actual - expected) <= tolerance,
    `${label}: expected ${expected} +/- ${tolerance}, got ${actual}`,
  );
}

function check(name, fn) {
  const started = Date.now();
  try {
    fn();
    CHECKS.push({ name, ok: true });
    console.log(`  PASS  ${name} (${Date.now() - started} ms)`);
  } catch (error) {
    CHECKS.push({ name, ok: false });
    console.log(`  FAIL  ${name}: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function walkFiles(dir, suffix = '') {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const absolute = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walkFiles(absolute, suffix));
    else if (!suffix || entry.name.endsWith(suffix)) out.push(absolute);
  }
  return out.sort();
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function getCoordinates(geometry) {
  if (!geometry || !geometry.type) fail('feature has no geometry');
  const coords = geometry.coordinates;
  if (!Array.isArray(coords)) fail(`geometry ${geometry.type} has no coordinates`);
  const points = [];
  const visit = (node) => {
    if (node.length === 2 && typeof node[0] === 'number' && typeof node[1] === 'number') {
      points.push(node);
      return;
    }
    for (const child of node) visit(child);
  };
  visit(coords);
  assert(points.length > 0, `geometry ${geometry.type} has no finite coordinate pairs`);
  return points;
}

function validateFeatureCollection(relative, options = {}) {
  const parsed = featureCollectionSchema.safeParse(readJson(relative));
  assert(parsed.success, `${relative}: ${parsed.error?.issues[0]?.message ?? 'schema failed'}`);
  const collection = parsed.data;
  assert(collection.features.length > 0, `${relative}: no features`);
  if (options.count !== undefined) {
    assert(
      collection.features.length === options.count,
      `${relative}: expected ${options.count} features, found ${collection.features.length}`,
    );
  }
  const allowedClasses = new Set(['source', 'derived', 'scenario', 'synthetic', 'reference']);
  const ids = new Set();
  for (const [index, feature] of collection.features.entries()) {
    assert(feature.geometry && feature.geometry.type, `${relative}: feature ${index} has no geometry`);
    assert(Array.isArray(feature.geometry.coordinates), `${relative}: feature ${index} has no coordinates`);
    const properties = feature.properties ?? {};
    assert(
      allowedClasses.has(properties.class),
      `${relative}: feature ${index} has invalid class ${JSON.stringify(properties.class)}`,
    );
    if (options.requireLabel !== false) {
      assert(
        typeof properties.label === 'string' && properties.label.length > 0,
        `${relative}: feature ${index} has no label`,
      );
    }
    if (options.idKey) {
      const id = properties[options.idKey];
      assert(typeof id === 'string' && id.length > 0, `${relative}: feature ${index} has no ${options.idKey}`);
      assert(!ids.has(id), `${relative}: duplicate ${options.idKey} ${id}`);
      ids.add(id);
    }
    if (options.coordinates !== false) {
      for (const [lon, lat] of getCoordinates(feature.geometry)) {
        assert(Number.isFinite(lon) && Number.isFinite(lat), `${relative}: non-finite coordinate`);
        assert(lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90, `${relative}: swapped lon/lat`);
        assert(
          lon >= AOI[0] - 0.02 && lon <= AOI[2] + 0.02 && lat >= AOI[1] - 0.02 && lat <= AOI[3] + 0.02,
          `${relative}: coordinate ${lon},${lat} outside AOI`,
        );
      }
    }
  }
  return collection;
}

const manifest = readJson('manifest.json');
const scenario = readJson('scenario.json');
const summary = readJson('flood/flood-summary.json');
const frameIndex = readJson('flood/frame-index.json');
const risk = readJson('risk/district-risk.json');
const series = readJson('series/monsoon-series.json');
const provenance = readJson('provenance.json');
const report = readJson('validation-report.json');
const AOI = frameIndex.bbox;

console.log('check-data: committed JSON schemas, manifest integrity and A-series invariants');
console.log(`  root: ${path.relative(ROOT, DATA)}`);

check('manifest schema and dataset identity', () => {
  const parsed = manifestSchema.safeParse(manifest);
  assert(parsed.success, parsed.error?.issues[0]?.message ?? 'manifest schema failed');
  assert(manifest.schema_version === '1.0.0', `unexpected schema_version ${manifest.schema_version}`);
  assert(manifest.step_count === 12, `expected 12 steps, found ${manifest.step_count}`);
  assert(manifest.dataset_version === '2026.10.0', `unexpected dataset_version ${manifest.dataset_version}`);
  assert(
    manifest.scenario_id === scenario.scenario_id && scenario.scenario_id === summary.scenario_id,
    'scenario_id mismatch between manifest, scenario and summary',
  );
});

check('every JSON file parses, including strict finite numbers', () => {
  const jsonFiles = walkFiles(DATA).filter((file) => file.endsWith('.json') || file.endsWith('.geojson'));
  assert(jsonFiles.length >= 15, `expected at least 15 JSON files, found ${jsonFiles.length}`);
  for (const file of jsonFiles) {
    const relative = path.relative(DATA, file).replaceAll('\\', '/');
    const text = fs.readFileSync(file, 'utf8');
    try {
      JSON.parse(text);
    } catch (error) {
      fail(`${relative}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
});

check('core JSON schemas (scenario, summary, frame index, risk, series, provenance)', () => {
  const pairs = [
    ['scenario.json', scenarioSchema, scenario],
    ['flood/flood-summary.json', floodSummarySchema, summary],
    ['flood/frame-index.json', frameIndexSchema, frameIndex],
    ['risk/district-risk.json', districtRiskSchema, risk],
    ['series/monsoon-series.json', monsoonSeriesSchema, series],
    ['provenance.json', provenanceSchema, provenance],
  ];
  for (const [name, schema, value] of pairs) {
    const parsed = schema.safeParse(value);
    assert(parsed.success, `${name}: ${parsed.error?.issues[0]?.message ?? 'schema failed'}`);
  }
});

check('risk-zone and hotspot schemas', () => {
  for (const [name, schema] of [
    ['risk/risk-zones.geojson', riskZoneFeatureCollectionSchema],
    ['risk/hotspots.geojson', hotspotFeatureCollectionSchema],
  ]) {
    const parsed = schema.safeParse(readJson(name));
    assert(parsed.success, `${name}: ${parsed.error?.issues[0]?.message ?? 'schema failed'}`);
  }
});

check('validation report exists, is pass, and carries V-A1..V-A10', () => {
  assert(report.status === 'pass', `validation report status is ${report.status}`);
  assert(report.counts?.failures === 0, 'validation report records failures');
  assert(report.dataset_version === manifest.dataset_version, 'report dataset_version mismatch');
  assert(Array.isArray(report.checks) && report.checks.length >= 31, 'report has fewer than 31 gates');
  const byId = new Map();
  for (const gate of report.checks) {
    assert(gate.status === 'pass', `${gate.id} ${gate.name}: status ${gate.status}`);
    byId.set(gate.id, gate);
  }
  for (let index = 1; index <= 10; index += 1) {
    const id = `V-A${index}`;
    assert(byId.has(id), `missing ${id} in validation report`);
  }
  for (const id of ['V01', 'V07', 'V10', 'V13', 'V20']) {
    assert(byId.has(id), `missing ${id} in validation report`);
  }
});

check('manifest integrity: every committed file listed once, size and sha256 match', () => {
  const actual = walkFiles(DATA)
    .filter((file) => path.basename(file) !== 'manifest.json')
    .map((file) => `data/${path.relative(DATA, file).replaceAll('\\', '/')}`);
  const listed = manifest.files.map((entry) => entry.path);
  assert(manifest.files.length === listed.length, 'duplicate manifest entry names');
  assert(new Set(listed).size === listed.length, 'duplicate manifest paths');
  for (const relative of actual) {
    assert(listed.includes(relative), `unlisted committed file ${relative}`);
  }
  for (const entry of manifest.files) {
    const relative = entry.path.replace(/^data\//, '');
    const absolute = path.join(DATA, relative);
    assert(fs.existsSync(absolute), `manifest lists missing file ${entry.path}`);
    const bytes = fs.statSync(absolute).size;
    assert(bytes === entry.bytes, `${entry.path}: expected ${entry.bytes} bytes, got ${bytes}`);
    assert(sha256(absolute) === entry.sha256, `${entry.path}: sha256 mismatch`);
  }
  assert(actual.length === manifest.files.length, `manifest lists ${manifest.files.length} of ${actual.length} files`);
});

check('GeoJSON layers: geometry, class/label, coordinates and unique ids', () => {
  validateFeatureCollection('admin/assam-districts.geojson', {
    idKey: 'district_id',
    count: 33,
  });
  validateFeatureCollection('admin/assam-state.geojson', { idKey: 'state_id', count: 1 });
  validateFeatureCollection('hydro/assam-rivers.geojson', { idKey: 'river_id', count: 860 });
  validateFeatureCollection('risk/risk-zones.geojson', { idKey: 'zone_id', count: 1747 });
  validateFeatureCollection('risk/hotspots.geojson', { idKey: 'hotspot_id', count: 20 });
  validateFeatureCollection('assets/critical-facilities.geojson', { idKey: 'osm_id', count: 1183 });
  validateFeatureCollection('gauges/virtual-gauges.geojson', { idKey: 'gauge_id', count: 8 });
});

check('district join: ranking and boundary layers agree', () => {
  const districts = validateFeatureCollection('admin/assam-districts.geojson', {
    idKey: 'district_id',
    count: 33,
  });
  const boundaryIds = new Set(districts.features.map((feature) => feature.properties.district_id));
  const riskIds = new Set(risk.districts.map((district) => district.district_id));
  for (const id of boundaryIds) assert(riskIds.has(id), `district ${id} has no risk row`);
  for (const id of riskIds) assert(boundaryIds.has(id), `risk row ${id} has no boundary`);
});

check('risk ranking: 33 dense ranks, finite scores 0-100, counts agree', () => {
  assert(risk.districts.length === 33, `expected 33 districts, found ${risk.districts.length}`);
  assert(risk.counts.total === 33, `counts.total is ${risk.counts.total}`);
  const ranks = risk.districts.map((district) => district.rank).sort((a, b) => a - b);
  for (let index = 0; index < ranks.length; index += 1) {
    assert(ranks[index] === index + 1, `rank ${index + 1} missing or duplicated`);
  }
  for (const district of risk.districts) {
    assert(Number.isFinite(district.risk_score), `${district.name}: non-finite risk score`);
    assert(district.risk_score >= 0 && district.risk_score <= 100, `${district.name}: score outside 0-100`);
    assert(district.area_share >= 0 && district.area_share <= 1, `${district.name}: invalid area_share`);
    assert(district.valid_area_share >= 0 && district.valid_area_share <= 1, `${district.name}: invalid coverage`);
  }
  const top = [...risk.districts].sort((a, b) => a.rank - b.rank)[0];
  assert(top.name === 'Sivasagar', `top district is ${top.name}, expected Sivasagar`);
  close(top.risk_score, 66.805, 1e-9, 'top district score');
});

check('P0.1 risk weights: two drivers sum to 1.0 and are the applied weights', () => {
  assert(
    typeof risk.weights_version === 'string' && risk.weights_version.length > 0,
    'weights_version is missing',
  );
  assert(!('depth' in risk.weights), 'risk.weights must not contain a depth driver');
  close(risk.weights.area_share, 0.5625, 1e-12, 'area weight');
  close(risk.weights.duration, 0.4375, 1e-12, 'duration weight');
  close(risk.weights.area_share + risk.weights.duration, 1.0, 1e-12, 'weights sum');

  const references = risk.reference_values;
  for (const district of risk.districts) {
    const areaTerm = Math.min(district.area_share / references.area_share_saturation, 1);
    const durationTerm = Math.min(
      district.mean_duration_days / references.duration_saturation_days,
      1,
    );
    const expected = 100 * (risk.weights.area_share * areaTerm + risk.weights.duration * durationTerm);
    close(district.risk_score, expected, 1e-3, `${district.name} applied score`);
  }
});

check('P0.2 depth context varies across the 33 districts', () => {
  const shares = risk.districts.map((district) => district.depth_over_1_5m_share);
  const distinct = new Set(shares.map((value) => value.toFixed(6)));
  assert(distinct.size > 1, `depth_over_1_5m_share is constant at ${shares[0]}`);
  for (const district of risk.districts) {
    assert(
      Number.isFinite(district.depth_over_1_5m_share) &&
        district.depth_over_1_5m_share >= 0 &&
        district.depth_over_1_5m_share <= 1,
      `${district.name}: invalid depth_over_1_5m_share`,
    );
    assert(
      Number.isFinite(district.median_depth_m) && district.median_depth_m >= 0,
      `${district.name}: invalid median_depth_m`,
    );
  }
});

check('P0.4 risk class area shares over wet-at-peak cells sum to 1.0', () => {
  const shares = risk.risk_class_area_share;
  let sum = 0;
  for (const key of ['low', 'moderate', 'high', 'very_high']) {
    assert(Number.isFinite(shares[key]) && shares[key] >= 0 && shares[key] <= 1, `invalid ${key} share`);
    sum += shares[key];
  }
  close(sum, 1.0, 0.01, 'risk class area share sum');
});

check('V-A1 AOI v2 area inside the 45,000-56,000 km2 band', () => {
  const area = manifest.aoi_v2.area_km2;
  assert(area >= 45000 && area <= 56000, `AOI v2 area ${area} is outside the band`);
});

check('V-A2 channel policy: <=4.0% of AOI v2', () => {
  const share = manifest.aoi_v2.channel_cell_share_of_aoi_v2;
  assert(Number.isFinite(share) && share > 0 && share <= 0.04, `channel share ${share} exceeds 4%`);
});

check('V-A3 stage series: strict rise S00-S07, strict fall S08-S11, peak S07', () => {
  const steps = summary.steps;
  assert(steps.length === 12, `expected 12 steps, found ${steps.length}`);
  for (let index = 1; index <= 7; index += 1) {
    assert(steps[index].stage_m > steps[index - 1].stage_m, `stage does not rise at S${index}`);
  }
  for (let index = 9; index < steps.length; index += 1) {
    assert(steps[index].stage_m < steps[index - 1].stage_m, `stage does not fall at S${index}`);
  }
  assert(summary.peak_step === 7, `peak_step is ${summary.peak_step}`);
  close(steps[7].stage_m, 3.7, 1e-9, 'peak stage');
  close(series.threshold.value, 2.0, 1e-9, 'scenario threshold');
  for (const step of steps) {
    close(step.stage_m, step.mainstem_stage_m + step.backwater_m, 1e-6, `S${step.step} stage arithmetic`);
  }
});

check('V-A4 peak extent: 4,000-12,000 km2 and <=40% of flood-prone area', () => {
  const peak = summary.steps[summary.peak_step];
  assert(peak.inundated_area_km2 >= 4000 && peak.inundated_area_km2 <= 12000, 'peak extent outside band');
  close(frameIndex.steps[summary.peak_step].area_km2, peak.inundated_area_km2, 0.01, 'frame-index peak area');
  const share = peak.inundated_area_km2 / manifest.aoi_v2.flood_prone_area_km2;
  assert(share <= 0.4, `peak extent share ${share} exceeds 40%`);
  close(peak.share_of_flood_prone_area, share, 0.0005, 'peak share of flood-prone area');
});

check('V-A5 peak depth shape and ordered deciles for every step', () => {
  const peak = summary.steps[summary.peak_step];
  assert(peak.median_depth_m >= 0.7, `peak median ${peak.median_depth_m} is below 0.7 m`);
  assert(peak.median_depth_m <= peak.stage_m - 0.5, 'peak median exceeds stage - 0.5 m');
  assert(peak.p95_depth_m <= peak.stage_m + 1e-9, 'p95 above peak stage');
  assert(peak.p95_depth_m - peak.median_depth_m >= 0.6, 'p95 - median below 0.6 m');
  assert(peak.clamped_wet_share <= 0.3, `clamped wet share ${peak.clamped_wet_share} exceeds 30%`);
  for (const step of summary.steps) {
    const d = step.delay_deciles;
    const values = [d.p10, d.p25, d.p50, d.p75, d.p90, d.p95];
    for (let index = 0; index < values.length; index += 1) {
      assert(Number.isFinite(values[index]), `S${step.step} decile ${index} is not finite`);
      if (index > 0) assert(values[index] >= values[index - 1], `S${step.step} deciles are not ordered`);
    }
    close(d.p50, step.median_depth_m, 1e-6, `S${step.step} p50 == median`);
    close(d.p95, step.p95_depth_m, 1e-6, `S${step.step} p95 == p95`);
    assert(step.clamped_wet_share <= 0.3, `S${step.step} clamped wet share exceeds 30%`);
    assert(step.clamped_aoi_share <= 0.06, `S${step.step} clamped AOI share exceeds 6%`);
  }
});

check('V-A6 clamped negative HAND stays <=6.0% of AOI v2', () => {
  const max = Math.max(...summary.steps.map((step) => step.clamped_aoi_share));
  assert(max <= 0.06, `clamped AOI share ${max} exceeds 6%`);
  close(max, 0.053168, 1e-6, 'clamped AOI share');
});

check('V-A7 hydrograph shape: rising/recession and peak at S07', () => {
  const areas = summary.steps.map((step) => step.inundated_area_km2);
  for (let index = 1; index <= 7; index += 1) {
    assert(areas[index] >= areas[index - 1], `area decreases on the rising limb at S${index}`);
  }
  for (let index = 9; index < areas.length; index += 1) {
    assert(areas[index] <= areas[index - 1], `area increases on the recession at S${index}`);
  }
  const maxIndex = areas.indexOf(Math.max(...areas));
  assert(maxIndex === 7, `area maximum is S${maxIndex}, expected S07`);
});

check('V-A9 component-area filter declared before statistics and counted per step', () => {
  const model = scenario.model.component_filter;
  assert(model.method === 'component_area_filter', `unexpected component method ${model.method}`);
  assert(model.min_cells >= 9, `min_cells ${model.min_cells} is below 9`);
  assert(model.opening === 'none', `morphological opening is ${model.opening}`);
  assert(model.applied_before_statistics === true, 'filter is not declared before statistics');
  const audit = summary.component_filter_audit;
  assert(audit.min_cells >= 9, `summary min_cells ${audit.min_cells} is below 9`);
  for (const step of summary.steps) {
    const filter = step.component_filter;
    assert(filter.min_cells >= 9, `S${step.step} min_cells is below 9`);
    assert(filter.opening === 'none', `S${step.step} applies opening`);
    assert(filter.components_before - filter.components_after === filter.dropped_components, `S${step.step} component counts disagree`);
    assert(filter.dropped_area_km2 >= 0 && Number.isFinite(filter.dropped_area_km2), `S${step.step} dropped area invalid`);
  }
});

check('V-A10 frame-index/PNG agreement: dimensions, wet cells, area within 1%', () => {
  assert(frameIndex.width === 3733 && frameIndex.height === 2611, 'unexpected frame dimensions');
  assert(frameIndex.steps.length === 12, `expected 12 frames, found ${frameIndex.steps.length}`);
  const cellKm2 = (frameIndex.frame_resolution_m * frameIndex.frame_resolution_m) / 1_000_000;
  for (const [index, frame] of frameIndex.steps.entries()) {
    const summaryStep = summary.steps[index];
    const absolute = path.join(DATA, 'flood', frame.file);
    const bytes = fs.statSync(absolute).size;
    assert(bytes === frame.png_bytes, `${frame.file}: expected ${frame.png_bytes} bytes, got ${bytes}`);
    assert(summaryStep.frame_png_bytes === bytes, `${frame.file}: summary png bytes mismatch`);
    const decoded = decodePng(fs.readFileSync(absolute));
    assert(decoded.width === frameIndex.width && decoded.height === frameIndex.height, `${frame.file}: dimensions disagree`);
    const wet = countOpaquePixels(decoded);
    assert(wet === frame.png_wet_cells, `${frame.file}: expected ${frame.png_wet_cells} wet pixels, got ${wet}`);
    assert(wet === summaryStep.png_wet_cells, `${frame.file}: summary wet cells mismatch`);
    const area = wet * cellKm2;
    const delta = Math.abs(area - frame.png_area_km2) / frame.png_area_km2;
    assert(delta <= 0.01, `${frame.file}: decoded area ${area.toFixed(3)} differs by ${(delta * 100).toFixed(2)}%`);
    close(summaryStep.png_area_km2, frame.png_area_km2, 0.01, `${frame.file} summary/index area`);
  }
});

check('step contract: labels, days, phases and frame files agree', () => {
  assert(scenario.steps.length === 12, 'scenario has the wrong step count');
  for (let index = 0; index < 12; index += 1) {
    const s = scenario.steps[index];
    const f = summary.steps[index];
    const frame = frameIndex.steps[index];
    assert(s.step === index && f.step === index && frame.id === index, `step ${index} is out of order`);
    assert(s.label === f.step_label && s.label === frame.label, `step ${index} labels disagree`);
    assert(s.day_offset === f.day_offset, `step ${index} day offsets disagree`);
    assert(s.phase === f.phase, `step ${index} phases disagree`);
    assert(f.frame_file === frame.file, `step ${index} frame files disagree`);
    assert(s.stage_m === f.stage_m, `step ${index} stages disagree`);
  }
});

check('shares and totals are arithmetically consistent', () => {
  const aoi = manifest.aoi_v2.area_km2;
  const assam = manifest.aoi_v2.assam_area_km2;
  const floodProne = manifest.aoi_v2.flood_prone_area_km2;
  for (const step of summary.steps) {
    close(step.share_of_aoi_v2, step.inundated_area_km2 / aoi, 0.0005, `S${step.step} AOI share`);
    close(step.share_of_assam, step.inundated_area_km2 / assam, 0.0005, `S${step.step} Assam share`);
    close(step.share_of_flood_prone_area, step.inundated_area_km2 / floodProne, 0.0005, `S${step.step} flood-prone share`);
  }
  close(summary.totals.max_area_km2, summary.steps[7].inundated_area_km2, 1e-6, 'max area total');
  close(summary.totals.peak_stage_m, 3.7, 1e-9, 'peak stage total');
  close(summary.totals.median_depth_at_peak_m, summary.steps[7].median_depth_m, 1e-6, 'peak median total');
});

check('monsoon series matches the summary at every step', () => {
  const byId = new Map(series.series.map((entry) => [entry.id, entry]));
  for (const id of ['rainfall', 'mainstem_stage', 'backwater', 'stage_above_drainage']) {
    assert(byId.has(id), `missing series ${id}`);
  }
  const field = {
    rainfall: 'rainfall_mm_day',
    mainstem_stage: 'mainstem_stage_m',
    backwater: 'backwater_m',
    stage_above_drainage: 'stage_m',
  };
  for (const [id, key] of Object.entries(field)) {
    const entry = byId.get(id);
    assert(entry.points.length === 12, `${id}: expected 12 points`);
    for (const point of entry.points) {
      close(point.value, summary.steps[point.step][key], 1e-6, `${id} S${point.step}`);
    }
  }
});

check('provenance covers terrain, districts, rivers, flood and risk', () => {
  const byId = new Map(provenance.entries.map((entry) => [entry.id, entry]));
  for (const id of ['terrain', 'boundaries', 'rivers', 'flood', 'risk']) {
    const entry = byId.get(id);
    assert(entry, `missing provenance entry ${id}`);
    assert(entry.source_name.length > 0, `${id}: no source`);
    assert(entry.licence.length > 0, `${id}: no licence`);
    assert(entry.pipeline.length > 0, `${id}: no pipeline stage`);
    assert(entry.output_paths.length > 0, `${id}: no output file`);
    for (const output of entry.output_paths) {
      const relative = output.replace(/^public\//, '').replace(/^data\//, '');
      assert(fs.existsSync(path.join(DATA, relative)), `${id}: output ${output} does not exist`);
    }
  }
  const classes = new Set(['source', 'derived', 'scenario', 'synthetic', 'reference']);
  for (const entry of provenance.entries) {
    assert(classes.has(entry.class), `${entry.id}: invalid class ${entry.class}`);
  }
});

check('cross-sections and virtual gauges are internally complete', () => {
  const cross = readJson('series/cross-sections.json');
  assert(cross.schema_version === '1.0.0', 'cross-sections schema_version');
  assert(cross.scenario_id === manifest.scenario_id, 'cross-sections scenario_id');
  assert(Array.isArray(cross.transects) && cross.transects.length === 3, 'expected 3 transects');
  for (const transect of cross.transects) {
    assert(transect.samples.length === transect.sample_count, `${transect.transect_id}: sample_count mismatch`);
    for (const sample of transect.samples) {
      assert(Number.isFinite(sample.ground_m) && Number.isFinite(sample.hand_m), `${transect.transect_id}: non-finite profile`);
      assert(sample.water_surface_m.length === 12 && sample.depth_m.length === 12, `${transect.transect_id}: series length`);
      for (const value of [...sample.water_surface_m, ...sample.depth_m]) {
        assert(Number.isFinite(value), `${transect.transect_id}: non-finite water value`);
      }
    }
  }

  const gauges = readJson('gauges/virtual-gauges.geojson');
  assert(gauges.features.length === 8, `expected 8 virtual gauges, found ${gauges.features.length}`);
  for (const feature of gauges.features) {
    const props = feature.properties;
    assert(props.stage_series_m.length === 12, `${props.gauge_id}: stage series length`);
    assert(props.peak_step === 7, `${props.gauge_id}: peak_step`);
    assert(props.class === 'synthetic', `${props.gauge_id}: class must be synthetic`);
    assert(props.note.includes('No agency'), `${props.gauge_id}: missing no-agency note`);
  }
});

check('no forbidden field names inside committed data', () => {
  const forbidden = [
    'casualties',
    'deaths',
    'displaced',
    'affected_persons',
    'incident_id',
    'agency_id',
    'relief_camp',
    'warning_issued',
  ];
  const visit = (value, file, trail) => {
    if (Array.isArray(value)) {
      value.forEach((child, index) => visit(child, file, `${trail}[${index}]`));
      return;
    }
    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      assert(!forbidden.includes(key.toLowerCase()), `${file}: forbidden field ${trail}.${key}`);
      visit(child, file, `${trail}.${key}`);
    }
  };
  for (const file of walkFiles(DATA).filter((name) => name.endsWith('.json') || name.endsWith('.geojson'))) {
    visit(JSON.parse(fs.readFileSync(file, 'utf8')), path.relative(DATA, file), '$');
  }
});

const failed = CHECKS.filter((entry) => !entry.ok);
console.log('');
console.log(
  `check-data: ${CHECKS.length - failed.length}/${CHECKS.length} gates passed; ${FAILURES.length} failure(s)`,
);
if (failed.length > 0) {
  for (const failure of FAILURES) console.error(`  - ${failure}`);
  process.exit(1);
}
console.log('check-data: PASS');
