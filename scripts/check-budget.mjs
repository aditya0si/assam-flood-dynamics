#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DATA = path.join(ROOT, 'public', 'data');
const DIST = path.join(ROOT, 'dist');
const MiB = 1024 * 1024;
const KiB = 1024;

const CAPS = {
  frame: 400 * KiB, // REVIEW-08 B3: every committed flood frame
  critical: 3.5 * MiB,
  animation: 4.0 * MiB,
  optional: 3.0 * MiB,
  total: 9.0 * MiB,
};

const failures = [];

function assert(condition, message) {
  if (!condition) failures.push(message);
}

function format(bytes) {
  if (bytes < MiB) return `${(bytes / KiB).toFixed(1)} KB`;
  return `${(bytes / MiB).toFixed(2)} MB`;
}

function readJson(relative) {
  return JSON.parse(fs.readFileSync(path.join(DATA, relative), 'utf8'));
}

function sumPaths(paths) {
  let total = 0;
  for (const entry of paths) {
    const absolute = path.join(DATA, entry.replace(/^data\//, ''));
    assert(fs.existsSync(absolute), `manifest tier lists missing file ${entry}`);
    if (fs.existsSync(absolute)) total += fs.statSync(absolute).size;
  }
  return total;
}

console.log('check-budget: committed data caps (400 KB/frame, 4 MB animation, 9 MB total)');
console.log(`  root: ${path.relative(ROOT, DATA)}`);

const manifest = readJson('manifest.json');
const tiers = manifest.load_tiers;
const critical = sumPaths(tiers.critical);
const animation = sumPaths(tiers.animation);
const optional = sumPaths([...(tiers.optional ?? []), ...(tiers.fallback ?? [])]);
const frameIndex = readJson('flood/frame-index.json');

console.log(`  critical tier:  ${format(critical)} / ${format(CAPS.critical)}`);
assert(critical <= CAPS.critical, `critical tier ${format(critical)} exceeds ${format(CAPS.critical)}`);

console.log(`  animation tier: ${format(animation)} / ${format(CAPS.animation)}`);
assert(animation <= CAPS.animation, `animation tier ${format(animation)} exceeds ${format(CAPS.animation)}`);

console.log(`  optional+fallback: ${format(optional)} / ${format(CAPS.optional)}`);
assert(optional <= CAPS.optional, `optional+fallback ${format(optional)} exceeds ${format(CAPS.optional)}`);

let total = 0;
const walk = (dir) => {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const absolute = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(absolute);
    else total += fs.statSync(absolute).size;
  }
};
walk(DATA);
console.log(`  public/data total: ${format(total)} / ${format(CAPS.total)}`);
assert(total <= CAPS.total, `public/data total ${format(total)} exceeds ${format(CAPS.total)}`);

let largestFrame = 0;
for (const frame of frameIndex.steps) {
  const absolute = path.join(DATA, 'flood', frame.file);
  assert(fs.existsSync(absolute), `missing frame ${frame.file}`);
  if (!fs.existsSync(absolute)) continue;
  const bytes = fs.statSync(absolute).size;
  largestFrame = Math.max(largestFrame, bytes);
  console.log(`  ${frame.file}: ${format(bytes)} / ${format(CAPS.frame)}`);
  assert(bytes <= CAPS.frame, `${frame.file} is ${format(bytes)}, over the 400 KB frame cap`);
  assert(bytes === frame.png_bytes, `${frame.file} size ${bytes} does not match frame-index ${frame.png_bytes}`);
}
console.log(`  largest frame: ${format(largestFrame)} / ${format(CAPS.frame)}`);

if (fs.existsSync(DIST)) {
  const assets = fs
    .readdirSync(path.join(DIST, 'assets'), { withFileTypes: true })
    .filter((entry) => entry.isFile() && /\.(js|css)$/.test(entry.name))
    .map((entry) => {
      const absolute = path.join(DIST, 'assets', entry.name);
      return { name: entry.name, bytes: fs.statSync(absolute).size };
    });
  let distBytes = 0;
  for (const asset of assets) distBytes += asset.bytes;
  console.log(`  dist assets: ${assets.length} JS/CSS files, ${format(distBytes)} raw`);
} else {
  console.log('  dist/ absent: run npm run build before check-budget for built-asset sizes');
}

console.log('');
if (failures.length > 0) {
  for (const failure of failures) console.error(`  - ${failure}`);
  console.error(`check-budget: FAIL (${failures.length} cap violation(s))`);
  process.exit(1);
}
console.log(`check-budget: PASS (total ${format(total)}, animation ${format(animation)}, max frame ${format(largestFrame)})`);
