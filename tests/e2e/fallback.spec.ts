import { expect, test } from '@playwright/test';
import { collectErrors, focusTimeline, gotoStep, openApp, probeValue } from './helpers';

test.describe('M0 blocked-tile fallback', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/elevation-tiles-prod/**', (route) => route.abort());
    await page.route('**/arcgisonline.com/**', (route) => route.abort());
  });

  test('loads with both tile hosts blocked: health offline, overlays intact, playback works', async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const startedAt = Date.now();
    await openApp(page);

    // B5: both hosts have confirmed errors. The sequence must pass through
    // degraded and then settle offline within 8 s of navigation.
    const remaining = 8_000 - (Date.now() - startedAt);
    expect(remaining, 'app load must leave room for the 8 s offline budget').toBeGreaterThan(0);
    await expect
      .poll(() => probeValue(page, 'tileHealth'), {
        timeout: remaining,
        intervals: [200, 400, 800],
      })
      .toBe('offline');
    expect(
      Date.now() - startedAt,
      'the both-hosts-blocked path must reach offline within 8 s',
    ).toBeLessThanOrEqual(8_000);

    const history = await probeValue(page, 'tileHealthHistory');
    const degradedIndex = history?.indexOf('degraded') ?? -1;
    const offlineIndex = history?.lastIndexOf('offline') ?? -1;
    expect(degradedIndex, 'degraded must be observed before offline').toBeGreaterThanOrEqual(0);
    expect(offlineIndex, 'offline must follow degraded in the health history').toBeGreaterThan(
      degradedIndex,
    );
    expect(history?.at(-1), 'offline must be the settled state').toBe('offline');

    await expect(page.getByText('Tile hosts offline · committed relief').first()).toBeVisible();
    await expect(page.locator('#map-viewport canvas')).toHaveCount(1);
    expect(await probeValue(page, 'ready')).toBe(true);
    expect((await probeValue(page, 'layers'))?.visible).toEqual(
      expect.arrayContaining(['flood', 'risk-zones', 'rivers', 'districts', 'hillshade', 'hotspots']),
    );

    await gotoStep(page, 7);
    expect(await probeValue(page, 'step')).toBe(7);
    expect(await probeValue(page, 'frameFile')).toMatch(/frames\/step-07\.png$/);
    expect(await probeValue(page, 'areaKm2')).toBeCloseTo(10010.6411, 3);
    await expect(page.getByText('10010.6').first()).toBeVisible();

    // The transport never depends on a remote tile host.
    await focusTimeline(page);
    await page.keyboard.press('Space');
    await expect.poll(() => probeValue(page, 'isPlaying'), { timeout: 5_000 }).toBe(true);
    await expect.poll(() => probeValue(page, 'step'), { timeout: 6_000 }).toBeGreaterThan(7);
    await page.keyboard.press('Space');
    await expect.poll(() => probeValue(page, 'isPlaying')).toBe(false);

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });
});
