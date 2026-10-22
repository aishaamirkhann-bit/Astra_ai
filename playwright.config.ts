import { defineConfig, devices } from "@playwright/test";

const frontendPort = process.env.ASTRA_FRONTEND_PORT || "3000";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  // Tests share one seeded user/DB; serialize files to avoid wallet/budget races.
  workers: 1,
  retries: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://localhost:${frontendPort}`,
    // Auth state written by global-setup (one API login) — keeps the suite
    // well under the backend's sensitive-endpoint rate limit.
    storageState: "e2e/.auth/state.json",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
