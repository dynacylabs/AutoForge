import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  globalSetup: './tests/global-setup.ts',
  globalTeardown: './tests/global-teardown.ts',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // Must stay 1: every test hits one shared, stateful backend (project
  // state, filament library, job history) with no per-worker isolation, so
  // two spec files running concurrently in separate workers can corrupt
  // each other's state (e.g. a slider mutation from one file's job landing
  // mid-assertion in another file's "defaults" test).
  workers: 1,
  reporter: 'html',
  use: {
    baseURL: process.env.WEBUI_TEST_BASE_URL || 'http://127.0.0.1:8000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
