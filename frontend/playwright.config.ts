import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright configuration for Fuzzbin frontend E2E tests.
 * 
 * Run with: npm run test:e2e
 * Run with UI: npm run test:e2e:ui
 */
export default defineConfig({
  testDir: './e2e',
  
  // Run tests in files in parallel
  fullyParallel: true,
  
  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,
  
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  
  // Opt out of parallel tests on CI for stability
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter to use
  reporter: process.env.CI 
    ? [['html', { outputFolder: 'playwright-report' }], ['github']]
    : [['html', { outputFolder: 'playwright-report' }], ['list']],
  
  // Shared settings for all projects
  use: {
    // Base URL to use in actions like `await page.goto('/')`
    baseURL: process.env.VITE_API_BASE_URL 
      ? 'http://localhost:5173' 
      : 'http://localhost:5173',

    // Collect trace when retrying the failed test
    trace: 'on-first-retry',
    
    // Capture screenshot on failure
    screenshot: 'only-on-failure',
    
    // Video recording (off by default, enable for debugging)
    video: 'off',
  },

  // Configure projects for major browsers
  projects: [
    // Setup project - handles authentication state
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
    },

    // Main test project - depends on setup (authenticated tests)
    {
      name: 'chromium',
      use: { 
        ...devices['Desktop Chrome'],
        // Use stored authentication state
        storageState: 'e2e/.auth/user.json',
      },
      dependencies: ['setup'],
      // Exclude unauthenticated and setup tests
      testIgnore: /.*\.(unauthenticated|setup)\.spec\.ts/,
    },

    // Unauthenticated tests (login page, etc.) - runs without auth state
    {
      name: 'chromium-unauthenticated',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /.*\.unauthenticated\.spec\.ts/,
    },
  ],

  // Run local dev server before starting the tests
  // In CI: workflow starts servers, so Playwright reuses them
  // Locally: Playwright starts servers (or reuses if already running)
  webServer: process.env.CI ? [] : [
    // Backend API server - uses isolated test directories to ensure clean state
    {
      command: 'rm -rf /tmp/fuzzbin-e2e && mkdir -p /tmp/fuzzbin-e2e/config /tmp/fuzzbin-e2e/library && cd .. && fuzzbin-api',
      url: 'http://localhost:8000/health',
      reuseExistingServer: true,
      timeout: 30 * 1000,
      env: {
        FUZZBIN_CONFIG_DIR: '/tmp/fuzzbin-e2e/config',
        FUZZBIN_LIBRARY_DIR: '/tmp/fuzzbin-e2e/library',
        FUZZBIN_API_JWT_SECRET: 'e2e-test-secret-key-do-not-use-in-production',
        FUZZBIN_API_AUTH_ENABLED: 'true',
      },
    },
    // Frontend dev server
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 30 * 1000,
    },
  ],

  // Timeout settings
  timeout: 30 * 1000, // 30 seconds per test
  expect: {
    timeout: 5 * 1000, // 5 seconds for assertions
  },
  
  // Output folder for test artifacts
  outputDir: 'test-results/',
})
