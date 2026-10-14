import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? 'https://d2zs9nk4uc2dbx.cloudfront.net';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,          // run serially — each query hits a live backend
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,                    // single worker — live backend rate limits
  reporter: [
    ['html', { open: 'never', outputFolder: 'e2e-report' }],
    ['json', { outputFile: 'e2e-report/results.json' }],
    ['list'],
  ],
  timeout: 90_000,               // 90s per test — backend turns can take 30s+
  expect: { timeout: 60_000 },   // 60s for assertions — streaming takes time

  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'on',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
