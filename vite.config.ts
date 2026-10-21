import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

const reactStack = fileURLToPath(new URL('./node_modules/.vite-deps/react-stack.js', import.meta.url));
const mapLibreBundle = fileURLToPath(new URL('./node_modules/.vite-deps/maplibre-gl.js', import.meta.url));

// Only scripts/vite-run.mjs sets this. Plain `vite` never touches the vendored
// prebundle or the in-process esbuild shim.
const sandbox = process.env.BAANH_SANDBOX === '1';

export default defineConfig(({ command, isPreview }) => ({
  base: command === 'build' || isPreview ? '/baanh/' : '/',
  plugins: [react()],
  resolve: {
    alias:
      sandbox && command === 'serve' && !isPreview
        ? [
            { find: /^react-dom\/client$/, replacement: reactStack },
            { find: /^react-dom$/, replacement: reactStack },
            { find: /^react\/jsx-runtime$/, replacement: reactStack },
            { find: /^react\/jsx-dev-runtime$/, replacement: reactStack },
            { find: /^react$/, replacement: reactStack },
            { find: /^maplibre-gl$/, replacement: mapLibreBundle },
          ]
        : [],
  },
  // The sandbox prebundle (scripts/prebundle.mjs) replaces Vite's optimiser,
  // which cannot spawn its esbuild child under this workspace's sandbox.
  optimizeDeps: sandbox && command === 'serve' && !isPreview ? { disabled: 'dev' } : undefined,
  server: {
    port: 5173,
    strictPort: true,
    // Keep the dev payload small; the prebundled MapLibre module is large enough.
    sourcemap: false,
  },
  preview: {
    port: 4173,
    strictPort: true,
  },
  build: {
    target: 'es2022',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: {
          maplibre: ['maplibre-gl'],
          uplot: ['uplot'],
          react: ['react', 'react-dom', 'zustand'],
        },
      },
    },
  },
}));
