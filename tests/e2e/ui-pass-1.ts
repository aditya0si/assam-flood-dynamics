import { expect, test } from '@playwright/test';
import { DEPTH_PRESENTATION } from '../../src/map/depthPalette';
import { openApp, openPanel } from './helpers';

// Share one cold WebGL mount, not browser state between tests. Each assertion
// remains a named report step; all other M0 tests retain isolated pages.
test('UI pass 1 — survey instrument acceptance', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openApp(page);
  await test.step('map owns the screen and rails work by keyboard', async () => {
    const rail = page.locator('#analysis-rail');
    const dock = page.locator('#scenario-timeline');
    const mapHeightRatio = () => page.locator('.maplibregl-map').evaluate(
      (el) => el.getBoundingClientRect().height / innerHeight,
    );
    await expect(rail).toHaveAttribute('data-rail-size', 'default');
    await expect(dock).toHaveAttribute('data-rail-size', 'default');
    await expect.poll(mapHeightRatio).toBeGreaterThanOrEqual(0.60);
    expect((await rail.boundingBox())!.width).toBe(380);
    await page.getByRole('button', { name: 'Expand analysis width', exact: true }).click();
    expect((await rail.boundingBox())!.width).toBe(520);
    await page.getByRole('button', { name: 'Hide analysis', exact: true }).focus();
    await page.keyboard.press('Enter');
    await expect(rail).toHaveAttribute('data-rail-size', 'collapsed');
    expect((await rail.boundingBox())!.width).toBe(44);
    await page.getByRole('button', { name: 'Hide analytics', exact: true }).focus();
    await page.keyboard.press('Space');
    await expect(dock).toHaveAttribute('data-rail-size', 'collapsed');
    await expect.poll(mapHeightRatio).toBeGreaterThanOrEqual(0.75);
    await expect(page.getByText('NOT A FORECAST')).toHaveCount(1);
    await page.getByRole('button', { name: 'Show analysis', exact: true }).click();
    await expect(page.getByRole('tab', { name: 'Risk', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Show analytics', exact: true }).click();
    await expect(rail).toHaveAttribute('data-rail-size', 'default');
    await expect(dock).toHaveAttribute('data-rail-size', 'default');
  });

  await test.step('five ranked district rows fit the visible scroll area', async () => {
    const panel = page.locator('#panel-risk');
    const rows = panel.locator('button[data-district-id]');
    for (let index = 0; index < 5; index++) {
      const row = rows.nth(index);
      await expect(row).toContainText(`#${index + 1}`);
      await expect(row).toContainText((await row.getAttribute('data-score'))!);
      const bounds = await row.boundingBox();
      const area = await panel.boundingBox();
      expect(bounds!.y).toBeGreaterThanOrEqual(area!.y);
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(area!.y + area!.height);
    }
  });

  await test.step('legend swatches equal the shared map palette', async () => {
    const legend = page.locator('[aria-label="Scenario flood depth classes"]');
    await legend.locator('summary').click();
    const swatches = legend.locator('li > span:first-child');
    const expected = Object.values(DEPTH_PRESENTATION).map(({ color }) => {
      const channels = [1, 3, 5].map((offset) => Number.parseInt(color.slice(offset, offset + 2), 16));
      return `rgb(${channels.join(', ')})`;
    });
    await expect(swatches).toHaveCount(expected.length);
    for (const swatch of await swatches.all()) await expect(swatch).toBeVisible();
    const colors = await swatches.evaluateAll((nodes) => nodes.map(
      (el) => getComputedStyle(el).backgroundColor,
    ));
    expect(colors).toEqual(expected);
    await legend.locator('summary').click();
  });

  await test.step('extent-score formula wraps without clipping', async () => {
    const formula = page.locator('[data-extent-formula]');
    await formula.scrollIntoViewIfNeeded();
    expect(await formula.evaluate((node) => node.scrollWidth <= node.clientWidth + 2)).toBe(true);
  });

  await test.step('exactly one warning persists through every analysis tab', async () => {
    for (const panel of ['Risk', 'Validation', 'Provenance', 'Methodology', 'Layers'] as const) {
      await openPanel(page, panel);
      await expect(page.getByText('NOT A FORECAST')).toHaveCount(1);
      await expect(page.getByText('NOT A FORECAST')).toBeVisible();
      // Count text-bearing elements, not ancestors that inherit textContent.
      expect(await page.evaluate(() => [...document.querySelectorAll('*')].filter((node) =>
        [...node.childNodes].some((child) => child.nodeType === Node.TEXT_NODE && child.textContent?.includes('NOT A FORECAST')),
      ).length)).toBe(1);
    }
  });

  await test.step('S00 charts explain the onset state', async () => {
    await expect(page.getByRole('region', { name: 'Timeline analytics', exact: true })).toContainText('Onset — no accumulated change yet.');
  });
});
