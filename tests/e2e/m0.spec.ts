import { expect, test } from '@playwright/test';
import { decodePng, countDifferentPixels } from '../../scripts/lib/png.mjs';
import {
  collectErrors,
  focusTimeline,
  gotoStep,
  hideMapOverlays,
  mapCanvasScreenshot,
  openApp,
  openPanel,
  percentage,
  probeValue,
} from './helpers';

test.describe('M0 acceptance', () => {
  test('loads, mounts the WebGL map and exposes live __baanh hooks', async ({ page }) => {
    const errors = collectErrors(page);
    await openApp(page);

    expect(await probeValue(page, 'step')).toBe(0);
    expect(await probeValue(page, 'stepCount')).toBe(12);
    expect(await probeValue(page, 'stepLabel')).toBe('01 Jun');
    expect(await probeValue(page, 'phase')).toBe('onset');
    expect(await probeValue(page, 'frameFile')).toMatch(/frames\/step-00\.png$/);
    expect(await probeValue(page, 'panel')).toBe('risk');
    expect((await probeValue(page, 'layers'))?.visible).toEqual(
      expect.arrayContaining(['flood', 'risk-zones', 'rivers', 'districts', 'hillshade', 'hotspots']),
    );

    const top = await page.evaluate(() => {
      const district = window.__baanh?.districtTop;
      return district
        ? {
            name: district.name,
            score: district.score,
            riskClass: district.riskClass,
            rank: district.rank,
            areaShare: district.areaShare,
            durationDays: district.durationDays,
          }
        : null;
    });
    expect(top?.name).toBe('Sivasagar');
    expect(top?.score).toBe(71.9);
    expect(top?.riskClass).toBe('very_high');
    expect(top?.rank).toBe(1);
    expect(top?.areaShare).toBeGreaterThan(0.4);
    expect(top?.durationDays).toBeGreaterThan(60);

    await expect(page.getByText('NOT A FORECAST').first()).toBeVisible();
    await expect(page.getByText('SCENARIO').first()).toBeVisible();
    await expect(page.locator('#map-viewport canvas')).toHaveCount(1);
    await expect(page.locator('#map-viewport [role="status"]').first()).toContainText(
      /live|degraded|offline|tile|terrain|imagery|connecting/i,
    );

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });

  test('keyboard path: skip link reaches timeline, Space plays, arrows step, Home/End jump', async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openApp(page);

    await page.keyboard.press('Tab');
    await expect(page.locator(':focus')).toHaveText('Skip to scenario timeline');
    await page.keyboard.press('Enter');
    await expect(page.locator(':focus')).toHaveId('scenario-timeline');

    await page.keyboard.press('Space');
    await expect.poll(() => probeValue(page, 'isPlaying'), { timeout: 5_000 }).toBe(true);
    await expect.poll(() => probeValue(page, 'step'), { timeout: 6_000 }).toBeGreaterThan(0);

    await page.keyboard.press('Space');
    await expect.poll(() => probeValue(page, 'isPlaying')).toBe(false);
    const pausedAt = await probeValue(page, 'step');
    await page.waitForTimeout(700);
    expect(await probeValue(page, 'step')).toBe(pausedAt);

    await page.keyboard.press('ArrowRight');
    await expect.poll(() => probeValue(page, 'step')).toBe(pausedAt! + 1);
    await page.keyboard.press('ArrowLeft');
    await expect.poll(() => probeValue(page, 'step')).toBe(pausedAt);

    await page.keyboard.press('End');
    await expect.poll(() => probeValue(page, 'step')).toBe(11);
    await page.keyboard.press('Home');
    await expect.poll(() => probeValue(page, 'step')).toBe(0);

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });

  test('scrubbing to S07 updates the map frame, area readout and all three chart values', async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openApp(page);
    await gotoStep(page, 7);

    expect(await probeValue(page, 'step')).toBe(7);
    expect(await probeValue(page, 'stepLabel')).toBe('25 Aug');
    expect(await probeValue(page, 'phase')).toBe('peak');
    expect(await probeValue(page, 'frameFile')).toMatch(/frames\/step-07\.png$/);
    expect(await probeValue(page, 'areaKm2')).toBeCloseTo(10010.6411, 3);

    await expect(page.getByText('10010.6').first()).toBeVisible();
    await expect(page.getByText('25 Aug').first()).toBeVisible();
    const charts = page.getByLabel('Three synced scenario charts');
    await expect(charts).toContainText('Inundated area');
    await expect(charts).toContainText('Scenario stage above local drainage');
    await expect(charts).toContainText('Rainfall (synthetic)');
    await expect(charts).toContainText('10010.6');
    await expect(charts).toContainText('3.7');
    await expect(charts).toContainText('10');

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });

  test('the flood surface visibly changes between S00, S04 and S07', async ({ page }) => {
    const errors = collectErrors(page);
    await openApp(page);
    await hideMapOverlays(page);

    await gotoStep(page, 0);
    await page.waitForTimeout(900);
    const s00 = decodePng(await mapCanvasScreenshot(page));

    await gotoStep(page, 4);
    await page.waitForTimeout(900);
    const s04 = decodePng(await mapCanvasScreenshot(page));

    await gotoStep(page, 7);
    await page.waitForTimeout(900);
    const s07 = decodePng(await mapCanvasScreenshot(page));

    const mapPixels = s00.width * s00.height;
    const diff04 = countDifferentPixels(s00, s04, 10) / mapPixels;
    const diff07 = countDifferentPixels(s00, s07, 10) / mapPixels;
    console.log(
      `M0-A6 canvas diff: S00->S04 ${percentage(diff04 * mapPixels, mapPixels)}, ` +
        `S00->S07 ${percentage(diff07 * mapPixels, mapPixels)} of the map`,
    );
    expect(diff04, 'S00 and S04 must not render the same flood surface').toBeGreaterThan(0.01);
    expect(diff07, 'S00 and S07 must not render the same flood surface').toBeGreaterThan(0.02);
    expect(diff07).toBeGreaterThan(diff04);

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });

  test('risk ranking and keyboard focus path: Enter selects first row, Escape returns to tab', async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openApp(page);

    const rows = page.getByRole('button', { name: /risk [\d.]+ of 100/i });
    await expect(rows).toHaveCount(33);
    await expect(rows.first()).toContainText('Sivasagar');
    await expect(rows.first()).toContainText('71.9');
    await expect(rows.first()).toContainText('Very high');

    // Second skip link -> rail -> active Risk tab -> first risk row.
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus')).toHaveText('Skip to analysis panels');
    await page.keyboard.press('Enter');
    await expect(page.locator(':focus')).toHaveId('analysis-rail');
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus')).toHaveId('panel-tab-risk');
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus')).toHaveAttribute('data-rank', '1');

    await page.keyboard.press('Enter');
    const top = await page.evaluate(() => window.__baanh?.districtTop?.districtId ?? null);
    await expect.poll(() => probeValue(page, 'selectedDistrictId')).toBe(top);
    await expect(rows.first()).toHaveAttribute('aria-pressed', 'true');

    await page.keyboard.press('Escape');
    await expect(page.locator(':focus')).toHaveId('panel-tab-risk');

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });

  test('layer controls mutate the live store; opacity clamps at the ends', async ({ page }) => {
    const errors = collectErrors(page);
    await openApp(page);
    await openPanel(page, 'Layers');

    const flood = page.getByRole('checkbox', { name: 'Show Scenario flood extent' });
    await expect(flood).toBeChecked();
    await flood.uncheck();
    await expect.poll(() => probeValue(page, 'layers')).toEqual(
      expect.objectContaining({ visible: expect.not.arrayContaining(['flood']) }),
    );
    await flood.check();

    const opacity = page.locator('[data-opacity-for="flood"]');
    await opacity.focus();
    await page.keyboard.press('Home');
    await expect.poll(async () => (await probeValue(page, 'layers'))?.opacity.flood).toBe(0);
    for (let index = 0; index < 20; index += 1) await page.keyboard.press('ArrowRight');
    await expect.poll(async () => (await probeValue(page, 'layers'))?.opacity.flood).toBeCloseTo(
      0.2,
      5,
    );
    await page.keyboard.press('End');
    await expect.poll(async () => (await probeValue(page, 'layers'))?.opacity.flood).toBe(1);

    await page.getByRole('button', { name: 'Hillshade', exact: true }).click();
    await expect.poll(async () => (await probeValue(page, 'layers'))?.baseMode).toBe('hillshade');
    await page.getByRole('button', { name: 'Imagery', exact: true }).click();
    await expect.poll(async () => (await probeValue(page, 'layers'))?.baseMode).toBe('imagery');

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });

  test('provenance shows source -> stage -> file and the required disclaimer', async ({ page }) => {
    const errors = collectErrors(page);
    await openApp(page);
    await openPanel(page, 'Provenance');

    await expect(page.getByText('NOT A FORECAST').first()).toBeVisible();
    for (const id of ['terrain', 'boundaries', 'rivers', 'flood', 'risk']) {
      const card = page.locator(`[data-prov-entry="${id}"]`);
      await expect(card).toHaveCount(1);
      await expect(card).toContainText('Source');
      await expect(card).toContainText('Stage');
      await expect(card.locator('code').first()).toContainText('data/');
    }
    await expect(page.getByText('Model assumptions').first()).toBeVisible();

    await openPanel(page, 'Methodology');
    await expect(page.getByText('HAND screening').first()).toBeVisible();
    await expect(page.getByText('conservative-shallow').first()).toBeVisible();
    await expect(page.getByText('What is not modelled').first()).toBeVisible();

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });
});

test.describe('accessibility baseline', () => {
  test.describe('prefers-reduced-motion', () => {
    test.use({ reducedMotion: 'reduce' });

    test('playback lengthens rather than freezing', async ({ page }) => {
      const errors = collectErrors(page);
      await openApp(page);
      await focusTimeline(page);
      await page.keyboard.press('Space');
      await expect.poll(() => probeValue(page, 'isPlaying'), { timeout: 5_000 }).toBe(true);
      await expect.poll(() => probeValue(page, 'step'), { timeout: 8_000 }).toBeGreaterThan(0);
      await page.keyboard.press('Space');
      await expect.poll(() => probeValue(page, 'isPlaying')).toBe(false);
      expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
    });
  });
});

test.describe('R6 map dominance', () => {
  test.use({ viewport: { width: 1920, height: 869 } });

  test('map is 62-68% of viewport height and the S07 flood covers >=6% of the screenshot', async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openApp(page);

    const mapBox = await page.locator('#map-viewport').boundingBox();
    expect(mapBox).not.toBeNull();
    const heightShare = mapBox!.height / 869;
    console.log(`R6 map height: ${mapBox!.height.toFixed(1)}px = ${(heightShare * 100).toFixed(2)}vh`);
    expect(heightShare, 'map must occupy at least 62% of a 900px-class viewport').toBeGreaterThanOrEqual(
      0.62,
    );
    expect(heightShare, 'map must not exceed 68% of a 900px-class viewport').toBeLessThanOrEqual(0.68);

    await gotoStep(page, 7);
    await openPanel(page, 'Layers');

    // Flood-only contribution: hide the other hazard overlays so the diff is
    // produced by the flood raster, exactly as REVIEW-08 measured it.
    for (const label of ['Show Risk zones', 'Show Inundation hotspots']) {
      const checkbox = page.getByRole('checkbox', { name: label });
      if (await checkbox.isChecked()) await checkbox.uncheck();
    }
    await page.waitForTimeout(600);

    await hideMapOverlays(page);
    await page.waitForTimeout(500);
    const floodOn = decodePng(await mapCanvasScreenshot(page));

    await page.locator('#analysis-rail').evaluate((element) => {
      (element as HTMLElement).style.visibility = 'visible';
    });
    await page.getByRole('checkbox', { name: 'Show Scenario flood extent' }).uncheck();
    await hideMapOverlays(page);
    await page.waitForTimeout(500);
    const floodOff = decodePng(await mapCanvasScreenshot(page));

    expect(floodOn.width).toBe(1920);
    const different = countDifferentPixels(floodOn, floodOff, 10);
    const screenshotPixels = 1920 * 869;
    const contribution = different / screenshotPixels;
    console.log(
      `R6 flood-only contribution at S07: ${different} px = ${percentage(different, screenshotPixels)} ` +
        `of the 1920x869 screenshot (map ${floodOn.width}x${floodOn.height})`,
    );
    expect(
      contribution,
      'S07 flood must contribute at least 6% of a 1920x869 screenshot',
    ).toBeGreaterThanOrEqual(0.06);

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });
});
