/**
 * The same base-path rule as vite.config.ts. Playwright runs against the
 * production preview, so it defaults to the GitHub Pages project path and
 * honours BAANH_BASE when the reviewer points the build somewhere else.
 */
export function normalizeBase(value: string): string {
  const trimmed = value.trim();
  if (!trimmed || trimmed === '/') return '/';
  return `/${trimmed.replace(/^\/+|\/+$/g, '')}/`;
}

export const APP_BASE_PATH = normalizeBase(process.env.BAANH_BASE ?? '/assam-flood-dynamics/');
