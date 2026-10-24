import { expect, test } from '@playwright/test';
import { DEPTH_PRESENTATION } from '../../src/map/depthPalette';
import { openApp, openPanel } from './helpers';

test.describe('UI pass 1 — survey instrument', () => {
  test('map owns the screen and rails work by keyboard', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openApp(page);
    const rail = page.locator('#analysis-rail');
    expect((await rail.boundingBox())!.width).toBe(380);
    await page.getByRole('button', { name: 'Expand analysis width', exact: true }).click();
    expect((await rail.boundingBox())!.width).toBe(520);
    expect((await page.locator('.maplibregl-map').boundingBox())!.height).toBeGreaterThanOrEqual(540);
    await page.getByRole('button', { name: 'Hide analysis', exact: true }).focus();
    await page.keyboard.press('Enter');
    await expect(rail).toHaveAttribute('data-rail-size', 'collapsed');
    expect((await rail.boundingBox())!.width).toBe(44);
    await page.getByRole('button', { name: 'Hide analytics', exact: true }).focus();
    await page.keyboard.press('Space');
    expect((await page.locator('.maplibregl-map').boundingBox())!.height).toBeGreaterThanOrEqual(675);
    await page.getByRole('button', { name: 'Show analysis', exact: true }).click();
    await expect(page.getByRole('tab', { name: 'Risk', exact: true })).toBeVisible();
  });

  test('five ranked district rows fit the visible scroll area', async ({ page }) => {
    await openApp(page);
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

  test('legend swatches equal the shared map palette', async ({ page }) => {
    await openApp(page);
    const legend = page.locator('[aria-label="Scenario flood depth classes"]');
    await legend.locator('summary').click();
    const colors = await legend.locator('li > span:first-child').evaluateAll((nodes) => nodes.map((node) => {
      const rgb = getComputedStyle(node).backgroundColor.match(/\d+/g)!;
      return '#' + rgb.slice(0, 3).map((value) => Number(value).toString(16).padStart(2, '0')).join('');
    }));
    expect(colors).toEqual(Object.values(DEPTH_PRESENTATION).map((entry) => entry.color));
  });

  test('extent-score formula wraps without clipping', async ({ page }) => {
    await openApp(page);
    const formula = page.locator('[data-extent-formula]');
    await formula.scrollIntoViewIfNeeded();
    expect(await formula.evaluate((node) => node.scrollWidth <= node.clientWidth + 2)).toBe(true);
  });

  test('exactly one warning persists through every analysis tab', async ({ page }) => {
    await openApp(page);
    for (const panel of ['Risk', 'Validation', 'Provenance', 'Methodology', 'Layers'] as const) {
      await openPanel(page, panel);
      await expect(page.getByText('NOT A FORECAST', { exact: true })).toHaveCount(1);
      await expect(page.getByText('NOT A FORECAST', { exact: true })).toBeVisible();
      // Count text-bearing elements, not ancestors that inherit textContent.
      expect(await page.evaluate(() => [...document.querySelectorAll('*')].filter((node) =>
        [...node.childNodes].some((child) => child.nodeType === Node.TEXT_NODE && child.textContent?.includes('NOT A FORECAST')),
      ).length)).toBe(1);
    }
  });

  test('S00 charts explain the onset state', async ({ page }) => {
    await openApp(page);
    await expect(page.getByRole('region', { name: 'Timeline analytics', exact: true })).toContainText('Onset — no accumulated change yet.');
  });
});
