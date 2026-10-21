import { expect, type Page } from '@playwright/test';
import { APP_BASE_PATH } from './basePath';

export type TileSourceStatus = 'loading' | 'live' | 'degraded' | 'offline';

export interface Probe {
  step: number;
  stepCount: number;
  stepLabel: string;
  phase: string;
  areaKm2: number;
  frameFile: string;
  ready: boolean;
  isPlaying: boolean;
  /** Painted map frames since mount; advances on every MapLibre 'render'. */
  renderSeq: number;
  /** True once the style document and required layers/sources are installed. */
  styleLoaded: boolean;
  /** Request one painted frame; no camera, layer or source change. */
  requestRender: () => void;
  tileHealth: 'live' | 'degraded' | 'offline';
  tileSources: { dem: TileSourceStatus; imagery: TileSourceStatus };
  tileHealthHistory: string[];
  camera: {
    center: [number, number];
    zoom: number;
    pitch: number;
  } | null;
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
    centroidLon: number | null;
    centroidLat: number | null;
  } | null;
}

declare global {
  interface Window {
    __baanh?: Probe;
  }
}

export type AppErrors = string[];

/** Per-assertion budget for host-bound state transitions (B7). */
export const POLL_TIMEOUT = 30_000;

/**
 * B8 capture budget. The settle predicate no longer observes tile health, so it
 * gets its own generous ceiling instead of borrowing the host-transition budget.
 */
export const SETTLE_TIMEOUT = 60_000;

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
  await page.goto(APP_BASE_PATH, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#scenario-timeline')).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => Boolean(window.__baanh)), { timeout: 30_000 })
    .toBe(true);
  await expect
    .poll(() => probeValue(page, 'frameFile'), { timeout: 30_000 })
    .toMatch(/frames\/step-00\.png$/);
  await expect.poll(() => probeValue(page, 'ready'), { timeout: POLL_TIMEOUT }).toBe(true);
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
  await expect.poll(() => probeValue(page, 'step'), { timeout: POLL_TIMEOUT }).toBe(step);
  const frame = `step-${String(step).padStart(2, '0')}.png`;
  await expect.poll(() => probeValue(page, 'frameFile'), { timeout: POLL_TIMEOUT }).toContain(frame);
}

export async function openPanel(page: Page, name: 'Risk' | 'Provenance' | 'Methodology' | 'Layers'): Promise<void> {
  const tab = page.getByRole('tab', { name, exact: true });
  await tab.click();
  await expect
    .poll(() => probeValue(page, 'panel'), { timeout: POLL_TIMEOUT })
    .toBe(name.toLowerCase());
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

export async function showMapOverlays(page: Page): Promise<void> {
  await page.evaluate(() => {
    for (const selector of [
      '#analysis-rail',
      '[aria-label="Scenario flood depth classes"]',
      '#map-viewport [role="status"]',
    ]) {
      for (const element of document.querySelectorAll<HTMLElement>(selector)) {
        element.style.visibility = '';
      }
    }
  });
}

/**
 * Toggle a Layers switch through its real control. B6 renders the input as a
 * 1x1, opacity-0 element, so it is deliberately not actionable; force the
 * checked state and verify the live store instead of the hidden input.
 */
export async function setLayerVisible(
  page: Page,
  layerId: string,
  label: string,
  visible: boolean,
): Promise<void> {
  await showMapOverlays(page);
  const input = page.getByLabel(label);
  const currentlyVisible = (await probeValue(page, 'layers'))?.visible.includes(layerId) ?? false;
  if (currentlyVisible !== visible) await input.setChecked(visible, { force: true });
  await expect
    .poll(async () => (await probeValue(page, 'layers'))?.visible.includes(layerId), {
      timeout: POLL_TIMEOUT,
    })
    .toBe(visible);
}

/** Toggle the flood layer through the real Layers control, then leave the rail visible. */
export async function setFloodVisible(page: Page, visible: boolean): Promise<void> {
  await setLayerVisible(page, 'flood', 'Show Scenario flood extent', visible);
}

/**
 * B8: request two explicit map repaints. The probe's requestRender() calls
 * map.triggerRepaint() only, so it schedules a painted frame without marking
 * sources dirty, moving the camera or changing layer state. A rAF between
 * requests keeps them from being coalesced.
 */
async function requestRenderFrames(page: Page): Promise<void> {
  for (let index = 0; index < 2; index += 1) {
    await page.evaluate(() => {
      window.__baanh?.requestRender();
    });
    await page.evaluate(
      () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())),
    );
  }
}

/**
 * B8 capture precondition, for A6 and R6 only: the style document is loaded and
 * the map has painted at least two more frames. No dependence on tile network
 * state, so it behaves the same on headless Linux CI as on a live machine.
 */
export async function waitForSettledFrame(page: Page, timeout = SETTLE_TIMEOUT): Promise<void> {
  await expect.poll(() => probeValue(page, 'styleLoaded'), { timeout }).toBe(true);
  const startSeq = (await probeValue(page, 'renderSeq')) ?? 0;
  await requestRenderFrames(page);
  await page.waitForFunction(
    (target) =>
      window.__baanh?.styleLoaded === true && (window.__baanh?.renderSeq ?? 0) >= target,
    startSeq + 2,
    { timeout, polling: 'raf' },
  );
}

/**
 * B7/B8: settle A6/R6 on the committed hillshade raster. Imagery tiles stream in
 * asynchronously and contaminate a flood-on/flood-off pixel diff, so switch to
 * the committed base, then wait for the deterministic style/render predicate.
 */
export async function settleHillshadeBasemap(page: Page): Promise<void> {
  await openPanel(page, 'Layers');
  await page.getByRole('button', { name: 'Hillshade', exact: true }).click();
  await expect
    .poll(async () => (await probeValue(page, 'layers'))?.baseMode, { timeout: POLL_TIMEOUT })
    .toBe('hillshade');
  await waitForSettledFrame(page);
}

export async function mapCanvasScreenshot(page: Page): Promise<Buffer> {
  const canvas = page.locator('#map-viewport canvas').first();
  await expect(canvas).toBeVisible();
  return canvas.screenshot({ animations: 'disabled' });
}

export function percentage(part: number, total: number): string {
  return `${((part / total) * 100).toFixed(2)}%`;
}
