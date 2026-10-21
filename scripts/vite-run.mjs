import childProcess from 'node:child_process';
import { register, syncBuiltinESMExports } from 'node:module';

/**
 * This Windows workspace runs under a file/process sandbox that rejects
 * child_process spawns with piped stdio. Vite's Windows realpath workaround
 * shells out to `net use`; it is a best-effort optimisation, not a correctness
 * need, so the call is short-circuited here. Vite itself is then loaded with
 * the runner config loader so no other tool process is required.
 *
 * The root `esbuild` package is vendor/esbuild-inprocess, which runs the
 * compiler as WebAssembly in this process. See that package for the reason.
 */
const originalExec = childProcess.exec;
childProcess.exec = function sandboxSafeExec(command, options, callback) {
  const text = typeof command === 'string' ? command.trim() : '';
  if (text === 'net use') {
    const done = typeof options === 'function' ? options : callback;
    if (typeof done === 'function') {
      queueMicrotask(() => done(new Error('net use skipped in the sandboxed build')));
    }
    return undefined;
  }
  return originalExec.call(this, command, options, callback);
};
syncBuiltinESMExports();
register(new URL('./esbuild-loader.mjs', import.meta.url));

process.argv = [process.argv[0], 'vite', ...process.argv.slice(2), '--configLoader', 'runner'];
await import('../node_modules/vite/bin/vite.js');
