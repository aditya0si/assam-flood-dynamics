import { expect, test } from '@playwright/test';
import { POLL_TIMEOUT, collectErrors, focusTimeline, gotoStep, openApp, probeValue } from './helpers';

test.describe('M0 blocked-tile fallback', () => {
  test('loads with both tile hosts blocked: health offline, overlays intact, playback works', async ({
    page,
  }) => {
    const blocked = { dem: 0, imagery: 0 };
    // B6: regex routes, not `**/arcgisonline.com/**`. That glob compiles to a
    // pattern that needs a slash immediately before the host name, so it never
    // matched `server.arcgisonline.com`: B5 blocked only the DEM host, imagery
    // succeeded, and `degraded` was the correct aggregate state. Both tile hosts
    // must fail before an offline verdict is honest.
    await page.route(/elevation-tiles-prod/, (route) => {
      blocked.dem += 1;
      return route.abort();
    });
    await page.route(/arcgisonline\.com/, (route) => {
      blocked.imagery += 1;
      return route.abort();
    });

    const errors = collectErrors(page);
    const startedAt = Date.now();
    await openApp(page);
    const loadMs = Date.now() - startedAt;
    console.log(
      `[fallback] app load took ${loadMs}ms (logged, not asserted); ` +
        `the offline state gets its own ${POLL_TIMEOUT}ms budget`,
    );

    // B5/B7: both hosts have confirmed errors. The sequence must pass through
    // degraded and then settle offline. This is a per-assertion budget, not a
    // deadline inherited from navigation cost.
    await expect
      .poll(
        async () => {
          const overall = await probeValue(page, 'tileHealth');
          const sources = await probeValue(page, 'tileSources');
          console.log(
            `[fallback] t+${Date.now() - startedAt}ms overall=${overall ?? '?'} ` +
              `dem=${sources?.dem ?? '?'} imagery=${sources?.imagery ?? '?'} ` +
              `blocked(dem=${blocked.dem}, imagery=${blocked.imagery})`,
          );
          return overall;
        },
        { timeout: POLL_TIMEOUT, intervals: [200, 400, 800] },
      )
      .toBe('offline');
    const offlineAt = Date.now() - startedAt;
    console.log(
      `[fallback] offline at t+${offlineAt}ms (load ${loadMs}ms); blocked requests ` +
        `dem=${blocked.dem}, imagery=${blocked.imagery}`,
    );
    expect(blocked.dem, 'the DEM host must have been requested and blocked').toBeGreaterThan(0);
    expect(blocked.imagery, 'the imagery host must have been requested and blocked').toBeGreaterThan(
      0,
    );

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
    await expect
      .poll(() => probeValue(page, 'isPlaying'), { timeout: POLL_TIMEOUT })
      .toBe(false);

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });
});
