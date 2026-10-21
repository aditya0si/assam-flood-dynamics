import { expect, type Page } from '@playwright/test';

export interface Probe {
  step: number;
  stepCount: number;
  stepLabel: string;
  phase: string;
  areaKm2: number;
  frameFile: string;
  ready: boolean;
  isPlaying: boolean;
  tileHealth: 'live' | 'degraded' | 'offline';
  panel: string;
  selectedDistrictId: string | null;
  layers: {
    visible: string[];
    opacity: Record<string, number>;
    baseMode: 'imagery' | 'hillshade';
  };
  districtTop: {
    name: string;
    score: number;
    riskScore: number;
    riskClass: string;
    rank: number;
    districtId: string;
    areaShare: number;
    durationDays: number;
    peakDepthM: number;
  } | null;
}

declare global {
  interface Window {
    __baanh?: Probe;
  }
}

export type AppErrors = string[];

export function collectErrors(page: Page): AppErrors {
  const errors: string[] = [];
  page.on('pageerror', (error) => {
    errors.push(`pageerror: ${error.message}`);
  });
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    const text = message.text();
    if (isExpectedNetworkError(text)) return;
    errors.push(`console: ${text}`);
  });
  return errors;
}

function isExpectedNetworkError(text: string): boolean {
  if (/Failed to load resource/i.test(text)) return true;
  if (/failed to load/i.test(text)) return true;
  if (/net::ERR_/i.test(text)) return true;
  if (/failed to fetch|aborterror|networkerror|load failed/i.test(text)) return true;
  if (/(?:could not|unable to) (?:load|fetch|decode)/i.test(text)) return true;
  return /(?:tile|raster|image|source)[^.]{0,80}(?:failed|error|abort)/i.test(text);
}

export async function probeValue<K extends keyof Probe>(
  page: Page,
  key: K,
): Promise<Probe[K] | undefined> {
  return page.evaluate((requested) => {
    const probe = window.__baanh;
    return probe ? (probe[requested as keyof Probe] as Probe[K]) : undefined;
  }, key);
}

export async function openApp(page: Page): Promise<void> {
  await page.goto('/baanh/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#scenario-timeline')).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => Boolean(window.__baanh)), { timeout: 30_000 })
    .toBe(true);
  await expect
    .poll(() => probeValue(page, 'frameFile'), { timeout: 30_000 })
    .toMatch(/frames\/step-00\.png$/);
  await expect.poll(() => probeValue(page, 'ready'), { timeout: 10_000 }).toBe(true);
}

export async function focusTimeline(page: Page): Promise<void> {
  await page.locator('#scenario-timeline').focus();
}

export async function gotoStep(page: Page, step: number): Promise<void> {
  await focusTimeline(page);
  await page.keyboard.press('Home');
  for (let index = 0; index < step; index += 1) {
    await page.keyboard.press('ArrowRight');
  }
  await expect.poll(() => probeValue(page, 'step')).toBe(step);
  const frame = `step-${String(step).padStart(2, '0')}.png`;
  await expect.poll(() => probeValue(page, 'frameFile'), { timeout: 15_000 }).toContain(frame);
}

export async function openPanel(page: Page, name: 'Risk' | 'Provenance' | 'Methodology' | 'Layers'): Promise<void> {
  const tab = page.getByRole('tab', { name, exact: true });
  await tab.click();
  await expect.poll(() => probeValue(page, 'panel')).toBe(name.toLowerCase());
}

export async function hideMapOverlays(page: Page): Promise<void> {
  await page.evaluate(() => {
    for (const selector of [
      '#analysis-rail',
      '[aria-label="Scenario flood depth classes"]',
      '#map-viewport [role="status"]',
    ]) {
      for (const element of document.querySelectorAll<HTMLElement>(selector)) {
        element.style.visibility = 'hidden';
      }
    }
  });
}

export async function mapCanvasScreenshot(page: Page): Promise<Buffer> {
  const canvas = page.locator('#map-viewport canvas').first();
  await expect(canvas).toBeVisible();
  return canvas.screenshot({ animations: 'disabled' });
}

export function percentage(part: number, total: number): string {
  return `${((part / total) * 100).toFixed(2)}%`;
}
