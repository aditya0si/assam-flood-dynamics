/**
 * Redirect Vite's `import esbuild from 'esbuild'` to the committed in-process
 * WebAssembly shim. Needed because this Windows workspace sandbox forbids the
 * child_process pipe that the normal esbuild package starts for its compiler.
 * This is a loader for the local build only; it does not affect bundle output.
 */
export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'esbuild') {
    return {
      url: new URL('../vendor/esbuild-inprocess/index.mjs', import.meta.url).href,
      shortCircuit: true,
    };
  }
  return nextResolve(specifier, context);
}
