import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

/**
 * The Windows workspace sandbox forbids child_process spawns with piped stdio.
 * The normal esbuild package starts its Go compiler as a child process. This
 * shim loads the same compiler as WebAssembly in this process instead, using
 * esbuild-wasm's browser API (which exposes the identical build/transform API).
 *
 * It is installed as the root `esbuild` package via a file dependency, so Vite's
 * own `import esbuild from 'esbuild'` is satisfied without patching node_modules.
 */
if (typeof globalThis.self === 'undefined') {
  globalThis.self = globalThis;
}
if (typeof globalThis.location === 'undefined') {
  globalThis.location = { href: `file://${process.cwd().replace(/\\/g, '/')}/` };
}

const require = createRequire(import.meta.url);
const browser = require('esbuild-wasm/lib/browser.js');
const wasmPath = require.resolve('esbuild-wasm/esbuild.wasm');
const wasmModule = await WebAssembly.compile(await readFile(wasmPath));
await browser.initialize({ wasmModule, worker: false });

export const build = browser.build;
export const transform = browser.transform;
export const formatMessages = browser.formatMessages;
export const analyzeMetafile = browser.analyzeMetafile;
export const initialize = browser.initialize;
export const stop = browser.stop;
export const version = browser.version;

export default browser;
