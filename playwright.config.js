const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: 'e2e',
  timeout: 30 * 1000,
  expect: { timeout: 5000 },
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8000',
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
  },
  webServer: {
    // Start Django, run migrations and ensure a test user exists.
    // Note: this uses the default Django settings to create a persistent sqlite DB for E2E.
    command: 'DJANGO_SETTINGS_MODULE=spider_management.settings bash -lc "python manage.py migrate --noinput && python - <<PY\nfrom django.contrib.auth import get_user_model\nUser = get_user_model()\nif not User.objects.filter(username=\"playwright\").exists():\n    User.objects.create_superuser(\"playwright\", \"playwright@example.com\", \"password\")\nPY\n && python manage.py runserver 0.0.0.0:8000"',
    port: 8000,
    timeout: 120 * 1000,
    reuseExistingServer: false,
  },
});
