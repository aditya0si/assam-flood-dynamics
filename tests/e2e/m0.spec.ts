import { expect, test } from '@playwright/test';
import { decodePng, countDifferentPixels } from '../../scripts/lib/png.mjs';
import {
  POLL_TIMEOUT,
  collectErrors,
  focusTimeline,
  gotoStep,
  hideMapOverlays,
  mapCanvasScreenshot,
  openApp,
  openPanel,
  percentage,
  probeValue,
  setFloodVisible,
  setLayerVisible,
  settleHillshadeBasemap,
  waitForSettledFrame,
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
    expect(await probeValue(page, 'styleLoaded')).toBe(true);
    expect(await probeValue(page, 'renderSeq')).toBeGreaterThan(0);
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
            centroidLon: district.centroidLon,
            centroidLat: district.centroidLat,
          }
        : null;
    });
    expect(top?.name).toBe('Sivasagar');
    expect(top?.score).toBe(66.8);
    expect(top?.riskClass).toBe('very_high');
    expect(top?.rank).toBe(1);
    expect(top?.areaShare).toBeGreaterThan(0.4);
    expect(top?.durationDays).toBeGreaterThan(60);

    // B5: the default camera is the top-ranked district's committed centroid,
    // at district scale and the review's 42 degree pitch.
    const camera = await probeValue(page, 'camera');
    expect(camera, 'window.__baanh.camera must expose the live camera').not.toBeNull();
    expect(camera!.center[0]).toBeCloseTo(top!.centroidLon!, 2);
    expect(camera!.center[1]).toBeCloseTo(top!.centroidLat!, 2);
    expect(camera!.zoom).toBeCloseTo(9.5, 1);
    expect(camera!.pitch).toBeCloseTo(42, 1);

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
    await expect
      .poll(() => probeValue(page, 'isPlaying'), { timeout: POLL_TIMEOUT })
      .toBe(false);
    const pausedAt = await probeValue(page, 'step');
    await page.waitForTimeout(700);
    expect(await probeValue(page, 'step')).toBe(pausedAt);

    await page.keyboard.press('ArrowRight');
    await expect.poll(() => probeValue(page, 'step'), { timeout: POLL_TIMEOUT }).toBe(pausedAt! + 1);
    await page.keyboard.press('ArrowLeft');
    await expect.poll(() => probeValue(page, 'step'), { timeout: POLL_TIMEOUT }).toBe(pausedAt);

    await page.keyboard.press('End');
    await expect.poll(() => probeValue(page, 'step'), { timeout: POLL_TIMEOUT }).toBe(11);
    await page.keyboard.press('Home');
    await expect.poll(() => probeValue(page, 'step'), { timeout: POLL_TIMEOUT }).toBe(0);

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

  test('the flood surface paints monotonically more of the map at S00, S04 and S07', async ({
    page,
  }) => {
    // B6: six canvas captures plus decode are the cost here, not navigation.
    // Give the test its own budget instead of sharing the 75 s default.
    test.setTimeout(180_000);
    const errors = collectErrors(page);
    await openApp(page);
    // B7: measure over the committed hillshade raster, never streaming imagery.
    await settleHillshadeBasemap(page);

    // B6: one page for all three states. Step buttons select a frame directly,
    // so the test never re-navigates and never decodes the intermediate frames
    // that Home + repeated ArrowRight used to pull in.
    const timelineSteps = page.getByRole('group', { name: 'Timeline steps' });
    const selectStep = async (step: number) => {
      if ((await probeValue(page, 'step')) === step) return;
      await timelineSteps.locator(`[data-step="${step}"]`).click();
      await expect.poll(() => probeValue(page, 'step'), { timeout: POLL_TIMEOUT }).toBe(step);
      await expect
        .poll(() => probeValue(page, 'frameFile'), { timeout: POLL_TIMEOUT })
        .toContain(`step-${String(step).padStart(2, '0')}.png`);
    };

    // Painted share = the pixels the flood raster changes at that step, measured
    // against the same map with the flood hidden. This is a per-step share, not
    // a S00-vs-S04 delta, so the thin early margins cannot make the test fail.
    const measured: Array<{ step: number; different: number; pixels: number; share: number }> = [];
    for (const step of [0, 4, 7]) {
      await selectStep(step);
      await setFloodVisible(page, true);
      // One settle for the frame crossfade; no second seek before the capture.
      await page.waitForTimeout(300);
      await hideMapOverlays(page);
      await waitForSettledFrame(page);
      const floodOn = decodePng(await mapCanvasScreenshot(page));

      await setFloodVisible(page, false);
      await page.waitForTimeout(300);
      await hideMapOverlays(page);
      await waitForSettledFrame(page);
      const floodOff = decodePng(await mapCanvasScreenshot(page));

      expect(floodOn.width).toBe(floodOff.width);
      expect(floodOn.height).toBe(floodOff.height);
      const pixels = floodOn.width * floodOn.height;
      const different = countDifferentPixels(floodOn, floodOff, 10);
      measured.push({ step, different, pixels, share: different / pixels });
    }
    await setFloodVisible(page, true);

    const [s00, s04, s07] = measured;
    const summary = measured
      .map((entry) => `S${String(entry.step).padStart(2, '0')} ${percentage(entry.different, entry.pixels)}`)
      .join(' < ');
    console.log(`M0-A6 painted share on the map box: ${summary}`);

    expect(
      s00.share,
      `baseline not settled: S00 share ${percentage(s00.different, s00.pixels)} exceeds 20% ` +
        `(measured ${summary})`,
    ).toBeLessThanOrEqual(0.2);

    expect(s04.share, `painted share must grow S00 -> S04 (measured ${summary})`).toBeGreaterThan(
      s00.share,
    );
    expect(s07.share, `painted share must grow S04 -> S07 (measured ${summary})`).toBeGreaterThan(
      s04.share,
    );
    expect(
      s07.share - s00.share,
      `S07 - S00 painted share must be >= 3 percentage points (measured ${summary})`,
    ).toBeGreaterThanOrEqual(0.03);

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });

  test('risk ranking and keyboard focus path: Enter selects first row, Escape returns to tab', async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openApp(page);

    const rows = page.getByRole('button', { name: /extent score [\d.]+ of 100/i });
    await expect(rows).toHaveCount(33);
    await expect(rows.first()).toContainText('Sivasagar');
    await expect(rows.first()).toContainText('66.8');
    await expect(rows.first()).toContainText('Very high');
    await expect(rows.first().locator('[data-depth-share]')).toBeVisible();
    await expect(rows.first()).toContainText('Severity inputs');
    await expect(rows.first()).toHaveAttribute('data-rank', '1');
    await expect(rows.first()).toHaveAttribute('data-severity-rank', /^\d+$/);

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
    await expect
      .poll(() => probeValue(page, 'selectedDistrictId'), { timeout: POLL_TIMEOUT })
      .toBe(top);
    await expect(rows.first()).toHaveAttribute('aria-pressed', 'true');

    await page.keyboard.press('Escape');
    await expect(page.locator(':focus')).toHaveId('panel-tab-risk');

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });

  test('validation tab renders the Sentinel-1 scorecard and both district ranks', async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openApp(page);

    await openPanel(page, 'Validation');
    const panel = page.locator('[data-validation-panel="true"]');
    await expect(panel).toBeVisible();
    await expect(panel.locator('[data-validation-scene]')).toHaveCount(2);
    await expect(panel.getByText(/not an event hindcast/i).first()).toBeVisible();
    await expect(panel.getByText(/σ0 calibration applied from the SAFE calibration LUT/i).first()).toBeVisible();

    await openPanel(page, 'Risk');
    const first = page.getByRole('button', { name: /extent score [\d.]+ of 100/i }).first();
    await expect(first).toHaveAttribute('data-rank', '1');
    await expect(first).toHaveAttribute('data-severity-rank', /^\d+$/);
    await expect(first).toContainText('extent');
    await expect(first).toContainText('severity');

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });

  test('coverage badge and row annotation appear for the lowest-coverage district', async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openApp(page);

    const rows = page.getByRole('button', { name: /extent score [\d.]+ of 100/i });
    await expect(rows).toHaveCount(33);
    const coverages = await rows.evaluateAll((nodes) =>
      nodes.map((node) => Number(node.getAttribute('data-coverage'))),
    );
    const lowest = Math.min(...coverages);
    expect(lowest, 'expected a district below the 75% coverage threshold').toBeLessThan(0.75);
    const lowestRow = rows.nth(coverages.indexOf(lowest));
    const badge = lowestRow.locator('[data-coverage-badge="true"]');
    await expect(badge).toHaveCount(1);
    await expect(badge).toContainText(/coverage \d+\.\d%/i);
    await expect(badge).toBeVisible();
    const note = lowestRow.locator('[data-coverage-note="true"]');
    await expect(note).toHaveCount(1);
    await expect(note).toHaveText('Scored on the AOI-covered share only');

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });

  test('layer controls mutate the live store; opacity clamps at the ends', async ({ page }) => {
    const errors = collectErrors(page);
    await openApp(page);
    await openPanel(page, 'Layers');

    const flood = page.getByLabel('Show Scenario flood extent');
    const floodVisible = async () =>
      (await probeValue(page, 'layers'))?.visible.includes('flood') ?? false;
    await expect.poll(floodVisible, { timeout: POLL_TIMEOUT }).toBe(true);

    // Keyboard path: the switch input must be focusable and Space must toggle it.
    await flood.focus();
    await expect(flood).toBeFocused();
    await page.keyboard.press('Space');
    await expect.poll(floodVisible, { timeout: POLL_TIMEOUT }).toBe(false);
    await page.keyboard.press('Space');
    await expect.poll(floodVisible, { timeout: POLL_TIMEOUT }).toBe(true);

    // B7: the input is intentionally 1x1 and invisible, so force the checked
    // state and assert the live store, not the hidden element's property.
    await flood.setChecked(false, { force: true });
    await expect.poll(floodVisible, { timeout: POLL_TIMEOUT }).toBe(false);
    await flood.setChecked(true, { force: true });
    await expect.poll(floodVisible, { timeout: POLL_TIMEOUT }).toBe(true);

    const opacity = page.locator('[data-opacity-for="flood"]');
    await opacity.focus();
    await page.keyboard.press('Home');
    await expect
      .poll(async () => (await probeValue(page, 'layers'))?.opacity.flood, { timeout: POLL_TIMEOUT })
      .toBe(0);
    for (let index = 0; index < 20; index += 1) await page.keyboard.press('ArrowRight');
    await expect
      .poll(async () => (await probeValue(page, 'layers'))?.opacity.flood, { timeout: POLL_TIMEOUT })
      .toBeCloseTo(0.2, 5);
    await page.keyboard.press('End');
    await expect
      .poll(async () => (await probeValue(page, 'layers'))?.opacity.flood, { timeout: POLL_TIMEOUT })
      .toBe(1);

    await page.getByRole('button', { name: 'Hillshade', exact: true }).click();
    await expect
      .poll(async () => (await probeValue(page, 'layers'))?.baseMode, { timeout: POLL_TIMEOUT })
      .toBe('hillshade');
    await page.getByRole('button', { name: 'Imagery', exact: true }).click();
    await expect
      .poll(async () => (await probeValue(page, 'layers'))?.baseMode, { timeout: POLL_TIMEOUT })
      .toBe('imagery');

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
      await expect
        .poll(() => probeValue(page, 'isPlaying'), { timeout: POLL_TIMEOUT })
        .toBe(false);
      expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
    });
  });
});

test.describe('R6 map dominance', () => {
  test.use({ viewport: { width: 1920, height: 869 } });

  test('hero camera frames S07 at >=10% of the map viewport, which is 62-68% of viewport height', async ({
    page,
  }) => {
    test.setTimeout(180_000);
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

    // Assert the camera, not just the pixels: top-ranked district centroid,
    // district scale, 42 degree pitch.
    const camera = await probeValue(page, 'camera');
    const top = await page.evaluate(() => window.__baanh?.districtTop ?? null);
    expect(top?.name).toBe('Sivasagar');
    expect(camera, 'window.__baanh.camera must expose the live camera').not.toBeNull();
    expect(camera!.center[0]).toBeCloseTo(top!.centroidLon!, 2);
    expect(camera!.center[1]).toBeCloseTo(top!.centroidLat!, 2);
    expect(camera!.zoom).toBeCloseTo(9.5, 1);
    expect(camera!.pitch).toBeCloseTo(42, 1);

    await gotoStep(page, 7);
    // B7: the same committed hillshade baseline as A6; no streaming imagery.
    await settleHillshadeBasemap(page);

    // Flood-only contribution: hide the other hazard overlays so the diff is
    // produced by the flood raster, exactly as REVIEW-08 measured it.
    for (const [id, label] of [
      ['risk-zones', 'Show Risk zones'],
      ['hotspots', 'Show Inundation hotspots'],
    ] as const) {
      await setLayerVisible(page, id, label, false);
    }
    await page.waitForTimeout(600);

    await hideMapOverlays(page);
    await page.waitForTimeout(500);
    await waitForSettledFrame(page);
    const floodOn = decodePng(await mapCanvasScreenshot(page));

    await setFloodVisible(page, false);
    await page.waitForTimeout(300);
    await hideMapOverlays(page);
    await page.waitForTimeout(500);
    await waitForSettledFrame(page);
    const floodOff = decodePng(await mapCanvasScreenshot(page));

    expect(floodOn.width).toBe(Math.round(mapBox!.width));
    expect(floodOn.height).toBe(Math.round(mapBox!.height));
    const different = countDifferentPixels(floodOn, floodOff, 10);
    // VIEWPORT-RELATIVE, as REVIEW-11 requires: denominator is the map element's
    // box, never the full 1920x869 page screenshot. 10% is calibrated hero
    // framing, not a physical constant.
    const mapPixels = mapBox!.width * mapBox!.height;
    const contribution = different / mapPixels;
    console.log(
      `R6 hero camera ${JSON.stringify(camera)}; S07 flood-only contribution: ` +
        `${different} px = ${percentage(different, mapPixels)} of the ` +
        `${mapBox!.width.toFixed(0)}x${mapBox!.height.toFixed(0)} map viewport`,
    );
    expect(
      contribution,
      `S07 flood must cover at least 10% of the map viewport at the hero camera ` +
        `(measured ${percentage(different, mapPixels)}, camera ${JSON.stringify(camera)})`,
    ).toBeGreaterThanOrEqual(0.1);

    expect(errors, `unexpected browser errors:\n${errors.join('\n')}`).toEqual([]);
  });
});
