import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the Companion-X dashboard regression smoke
 * (bd-w0gr, regression pin for bd-115z + bd-n368).
 *
 * The smoke assumes the API and Next dashboard are ALREADY running on
 * :8000 / :3000 (the unified-server local dev posture; matches
 * `lib/proxy.ts` default when API_URL is unset). Spawning them here
 * would drag in Strands + Bedrock/Ollama credentials that aren't in
 * the test environment. Run `npm run dev` (and the API) in another
 * shell before invoking `npx playwright test`.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
