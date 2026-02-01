const { test, expect } = require('@playwright/test');

// Lightweight E2E checks: login + page element smoke tests
test.beforeEach(async ({ page }) => {
  await page.goto('/accounts/login/');
  await page.fill('input[name=username]', 'playwright');
  await page.fill('input[name=password]', 'password');
  await Promise.all([
    page.waitForNavigation({ url: '**/' }),
    page.click('button[type=submit]'),
  ]);
});

test('dashboard shows retro elements', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.card-retro')).toBeVisible();
  await expect(page.locator('.btn-retro, .btn-retro-secondary')).toBeVisible();
});

test('comments page loads and contains comments list', async ({ page }) => {
  await page.goto('/spiders/comments/');
  await expect(page.locator('#comments-list')).toBeVisible();
  await expect(page.locator('.card-retro').first()).toBeVisible();

  // If "查看全文" exists, assert modal opens
  const moreBtn = page.locator('text=查看全文').first();
  if (await moreBtn.count() > 0) {
    await moreBtn.click();
    await expect(page.locator('.modal, .modal-dialog')).toBeVisible();
  }
});
