#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEFAULT_DATA = path.join(ROOT, 'public', 'data');
const DEFAULT_DIST = path.join(ROOT, 'dist');

const TEXT_EXTENSIONS = new Set([
  '.json',
  '.geojson',
  '.js',
  '.mjs',
  '.css',
  '.html',
  '.htm',
  '.svg',
  '.xml',
  '.txt',
  '.csv',
  '.md',
  '.map',
]);

const BANNED = [
  { id: 'casualties', pattern: /\bcasualties\b/gi },
  { id: 'deaths', pattern: /\bdeaths\b/gi },
  { id: 'displaced', pattern: /\bdisplaced\b/gi },
  { id: 'affected_persons', pattern: /\baffected_persons\b/gi },
  { id: 'incident_id', pattern: /\bincident_id\b/gi },
  { id: 'agency_id', pattern: /\bagency_id\b/gi },
  { id: 'relief_camp', pattern: /\brelief_camp\b/gi },
  { id: 'warning issued', pattern: /\bwarning\s+issued\b/gi },
];

const FORECAST = /\bforecast\b/gi;
const DISCLAIMER = /not\s+a\s+forecast/i;

function parseArgs(argv) {
  const options = {
    data: DEFAULT_DATA,
    dist: DEFAULT_DIST,
    selfTest: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--self-test') options.selfTest = true;
    else if (arg === '--data') options.data = path.resolve(argv[++index] ?? '');
    else if (arg === '--dist') options.dist = path.resolve(argv[++index] ?? '');
    else if (arg === '--help' || arg === '-h') {
      console.log(
        'usage: node scripts/check-honesty.mjs [--data <dir>] [--dist <dir>] [--self-test]\n' +
          '  Scans committed JSON/text data and built output for banned claims/fields.\n' +
          '  --self-test copies the data, injects banned strings, and asserts the gate rejects them.',
      );
      process.exit(0);
    } else {
      console.error(`check-honesty: unknown argument ${arg}`);
      process.exit(2);
    }
  }
  return options;
}

function walkTextFiles(root) {
  if (!fs.existsSync(root)) return [];
  const files = [];
  const visit = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const absolute = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        visit(absolute);
      } else if (TEXT_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
        files.push(absolute);
      }
    }
  };
  visit(root);
  return files.sort();
}

function locationFor(text, index) {
  const before = text.slice(0, index);
  const line = before.split('\n').length;
  const column = index - before.lastIndexOf('\n');
  return { line, column };
}

/**
 * A bare "forecast" is allowed only inside an explicit negation, e.g.
 * "NOT A FORECAST", "not_a_forecast", "no forecast is implied". Positive
 * phrases ("operational forecast") fail. The negation must be in the same
 * clause, so a later positive sentence is not rescued by an earlier disclaimer.
 */
function forecastIsQualified(text, index) {
  const before = text.slice(0, index);
  const notKey = /not_a_$/i.test(before);
  if (notKey) return true;

  const clauseStart = Math.max(
    text.lastIndexOf('.', index - 1),
    text.lastIndexOf('!', index - 1),
    text.lastIndexOf('?', index - 1),
    text.lastIndexOf(';', index - 1),
    text.lastIndexOf('\n', index - 1),
  );
  const window = text.slice(Math.max(clauseStart + 1, index - 180), index);
  return /\b(not|never|no|without|banned|forbidden|avoid|avoids|deny|denies|exclude|excludes)\b/i.test(
    window,
  );
}

function scanText(text, file, root, violations) {
  for (const rule of BANNED) {
    rule.pattern.lastIndex = 0;
    for (const match of text.matchAll(rule.pattern)) {
      const { line, column } = locationFor(text, match.index ?? 0);
      violations.push({
        file: path.relative(root, file),
        line,
        column,
        rule: rule.id,
        context: text
          .slice(Math.max(0, (match.index ?? 0) - 45), (match.index ?? 0) + match[0].length + 45)
          .replace(/\s+/g, ' ')
          .trim(),
      });
    }
  }

  FORECAST.lastIndex = 0;
  for (const match of text.matchAll(FORECAST)) {
    const index = match.index ?? 0;
    if (forecastIsQualified(text, index)) continue;
    const { line, column } = locationFor(text, index);
    violations.push({
      file: path.relative(root, file),
      line,
      column,
      rule: 'unqualified forecast',
      context: text
        .slice(Math.max(0, index - 45), index + match[0].length + 45)
        .replace(/\s+/g, ' ')
        .trim(),
    });
  }
}

function scan({ data, dist }) {
  const violations = [];
  if (!fs.existsSync(data)) {
    return { violations, error: `data directory does not exist: ${data}` };
  }
  if (!fs.existsSync(dist)) {
    return { violations, error: `dist directory does not exist: ${dist} (run npm run build)` };
  }

  for (const file of walkTextFiles(data)) {
    scanText(fs.readFileSync(file, 'utf8'), file, data, violations);
  }
  let disclaimerVisible = false;
  for (const file of walkTextFiles(dist)) {
    const text = fs.readFileSync(file, 'utf8');
    if (DISCLAIMER.test(text)) disclaimerVisible = true;
    scanText(text, file, dist, violations);
  }
  if (!disclaimerVisible) {
    violations.push({
      file: path.relative(dist, path.join(dist, 'index.html')),
      line: 0,
      column: 0,
      rule: 'required disclaimer',
      context: 'built output does not contain "NOT A FORECAST"',
    });
  }
  return { violations, error: null };
}

function printViolations(violations, label) {
  console.log(`${label}: ${violations.length} violation(s)`);
  for (const violation of violations.slice(0, 40)) {
    console.log(
      `  ${violation.file}:${violation.line}:${violation.column}  [${violation.rule}]  ${violation.context}`,
    );
  }
  if (violations.length > 40) console.log(`  ... ${violations.length - 40} more`);
}

function runClean(options) {
  console.log('check-honesty: banned fields/claims in public/data and dist');
  console.log(`  data: ${path.relative(ROOT, options.data) || options.data}`);
  console.log(`  dist: ${path.relative(ROOT, options.dist) || options.dist}`);
  const { violations, error } = scan(options);
  if (error) {
    console.error(`check-honesty: FAIL: ${error}`);
    return 1;
  }
  if (violations.length > 0) {
    printViolations(violations, 'check-honesty');
    console.error('check-honesty: FAIL');
    return 1;
  }
  console.log('  banned fields/claims: 0');
  console.log('  required "NOT A FORECAST" present in built output');
  console.log('check-honesty: PASS');
  return 0;
}

function inject(pathName, text) {
  fs.writeFileSync(pathName, text, 'utf8');
}

function expectedRules() {
  return [
    'casualties',
    'deaths',
    'displaced',
    'affected_persons',
    'incident_id',
    'agency_id',
    'relief_camp',
    'warning issued',
    'unqualified forecast',
  ];
}

function runSelfTest(options) {
  console.log('check-honesty self-test: injected-string proof');
  const clean = scan(options);
  if (clean.error) {
    console.error(`  FAIL: ${clean.error}`);
    return 1;
  }
  if (clean.violations.length > 0) {
    printViolations(clean.violations, '  clean copy');
    console.error('  FAIL: the committed tree is not clean before injection');
    return 1;
  }
  console.log('  clean copy: PASS (0 violations)');

  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'baanh-honesty-'));
  try {
    const data = path.join(temp, 'data');
    const dist = path.join(temp, 'dist');
    fs.cpSync(options.data, data, { recursive: true });
    fs.mkdirSync(dist, { recursive: true });
    fs.writeFileSync(
      path.join(dist, 'index.html'),
      '<!doctype html><title>gate fixture</title><p>NOT A FORECAST</p>\n',
      'utf8',
    );

    const target = path.join(data, 'scenario.json');
    const injected = fs.readFileSync(target, 'utf8').replace(
      '"not_a_forecast": true,',
      '"not_a_forecast": true,\n  "injected": "casualties deaths displaced affected_persons incident_id agency_id relief_camp operational forecast warning issued",',
    );
    inject(target, injected);

    const dirty = scan({ data, dist });
    const found = new Set(dirty.violations.map((violation) => violation.rule));
    const missing = expectedRules().filter((rule) => !found.has(rule));
    if (missing.length > 0) {
      printViolations(dirty.violations, '  injected copy');
      console.error(`  FAIL: injected gate missed: ${missing.join(', ')}`);
      return 1;
    }
    console.log(`  injected copy: FAIL as intended (${dirty.violations.length} violations)`);
    for (const rule of expectedRules()) {
      const hit = dirty.violations.find((violation) => violation.rule === rule);
      console.log(`    detected [${rule}] at ${hit.file}:${hit.line}`);
    }
    console.log('check-honesty self-test: PASS (real gate rejects each banned string)');
    return 0;
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
}

const options = parseArgs(process.argv.slice(2));
const exitCode = options.selfTest ? runSelfTest(options) : runClean(options);
process.exit(exitCode);
