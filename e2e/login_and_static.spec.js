const { test, expect } = require('@playwright/test');

// Simple E2E checks:
// - /login should redirect to /accounts/login/ and show the login form
// - /static/css/retro.css should be accessible with Content-Type text/css
// - protected pages should redirect to login when not authenticated

test('login redirect and login page elements', async ({ page }) => {
  await page.goto('/login');
  await expect(page).toHaveURL(/\/accounts\/login\//);
  await expect(page.locator('#username')).toBeVisible();
  await expect(page.locator('#password')).toBeVisible();
  await expect(page.locator('#captcha-img')).toBeVisible();
});

test('static retro.css is served with text/css', async ({ request }) => {
  const response = await request.get('/static/css/retro.css');
  expect(response.status()).toBe(200);
  const ct = response.headers()['content-type'] || '';
  expect(ct).toContain('text/css');
});

test('protected routes redirect to login', async ({ page }) => {
  const protectedPaths = [
    '/basic-table-query',
    '/user-management',
    '/accounts/operation-logs',
  ];

  for (const p of protectedPaths) {
    await page.goto(p);
    await expect(page).toHaveURL(/\/accounts\/login\//);
  }
});
