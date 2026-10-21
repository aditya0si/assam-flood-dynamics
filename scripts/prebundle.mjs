import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';

/**
 * Dev-only prebundle for the sandbox. Vite's dependency optimiser normally calls
 * esbuild's binary; this workspace forbids that child process. The committed
 * esbuild-wasm shim can compile, but its browser build has no filesystem, so a
 * tiny resolver plugin feeds it the packages. The resulting ESM modules are
 * aliased in vite.config.ts only for `serve`. Production uses Vite normally.
 *
 * React is bundled once so React and ReactDOM share a single hook dispatcher.
 */
if (typeof globalThis.self === 'undefined') globalThis.self = globalThis;
if (typeof globalThis.location === 'undefined') {
  globalThis.location = { href: `file://${process.cwd().replace(/\\/g, '/')}/` };
}

const root = process.cwd();
const require = createRequire(path.join(root, 'package.json'));
const browser = require('esbuild-wasm/lib/browser.js');
const wasmModule = await WebAssembly.compile(await readFile(require.resolve('esbuild-wasm/esbuild.wasm')));
await browser.initialize({ wasmModule, worker: false });

const outDir = path.join(root, 'node_modules', '.vite-deps');
const normalizePath = (value) => (/^\/[A-Za-z]:[\\/]/.test(value) ? value.slice(1) : value);

const isIdentifier = (name) => name !== 'default' && name !== '__esModule' && /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(name);

const diskPlugin = {
  name: 'sandbox-disk',
  setup(build) {
    build.onResolve({ filter: /.*/ }, (args) => {
      if (args.kind === 'entry-point') {
        return { path: require.resolve(args.path), namespace: 'sandbox-disk' };
      }
      const importer = args.importer && path.isAbsolute(normalizePath(args.importer))
        ? normalizePath(args.importer)
        : path.join(root, 'index.js');
      try {
        const importerRequire = createRequire(importer);
        return { path: importerRequire.resolve(args.path), namespace: 'sandbox-disk' };
      } catch {
        return null;
      }
    });

    build.onLoad({ filter: /.*/, namespace: 'sandbox-disk' }, async (args) => {
      const filePath = normalizePath(args.path);
      const extension = path.extname(filePath).toLowerCase();
      const loader = extension === '.json' ? 'json' : extension === '.ts' || extension === '.tsx' ? 'ts' : 'js';
      return { contents: await readFile(filePath, 'utf8'), loader };
    });
  },
};

async function bundleToFile(file, modules) {
  const names = new Set();
  for (const specifier of modules) {
    for (const name of Object.keys(require(specifier) ?? {})) {
      if (isIdentifier(name)) names.add(name);
    }
  }
  const imports = modules.map((specifier, index) => `import m${index} from ${JSON.stringify(specifier)};`).join('\n');
  const spread = modules.map((_, index) => `...m${index}`).join(', ');
  const exportNames = [...names].join(', ');
  const contents = `${imports}\nconst { ${exportNames} } = { ${spread} };\nexport { ${exportNames} };\nexport default m0;\n`;

  const result = await browser.build({
    absWorkingDir: '/',
    stdin: {
      contents,
      resolveDir: root,
      sourcefile: `prebundle-${file}`,
      loader: 'js',
    },
    bundle: true,
    write: false,
    format: 'esm',
    platform: 'browser',
    target: ['es2022'],
    define: { 'process.env.NODE_ENV': '"development"' },
    logLevel: 'silent',
    plugins: [diskPlugin],
  });
  const output = result.outputFiles?.[0];
  if (!output) throw new Error(`prebundle produced no output for ${file}`);
  await writeFile(path.join(outDir, file), output.text, 'utf8');
  return names.size;
}

await mkdir(outDir, { recursive: true });

const reactEntries = ['react', 'react-dom', 'react-dom/client', 'react/jsx-runtime', 'react/jsx-dev-runtime'];
const reactExports = await bundleToFile(
  'react-stack.js',
  reactEntries,
);
const mapLibreExports = await bundleToFile('maplibre-gl.js', ['maplibre-gl']);

console.log(
  `prebundled ${reactEntries.length} React entries (${reactExports} exports) and MapLibre (${mapLibreExports} exports) for the sandboxed dev server`,
);
