import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

// Backend interpreter: override with ASTRA_BACKEND_PYTHON; otherwise prefer the
// project venv, falling back to the ambient python (CI provides its own).
function backendPython(): string {
  if (process.env.ASTRA_BACKEND_PYTHON) return process.env.ASTRA_BACKEND_PYTHON;
  if (process.platform === "win32") {
    for (const candidate of [".venv/Scripts/python.exe", "../.venv/Scripts/python.exe", "../../.venv312/Scripts/python.exe"]) {
      if (fs.existsSync(path.join(__dirname, "astra-backend", candidate))) {
        return candidate.replace(/\//g, path.sep);
      }
    }
  }
  return process.platform === "win32" ? "python" : "python3";
}

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  // Tests share one seeded user/DB; serialize files to avoid wallet/budget races.
  workers: 1,
  retries: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3000",
    // Auth state written by global-setup (one API login) — keeps the suite
    // well under the backend's sensitive-endpoint rate limit.
    storageState: "e2e/.auth/state.json",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${backendPython()}" -m uvicorn app.main:app --port 8000`,
      cwd: "./astra-backend",
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 120_000,
      // E2E uses the development OTP bypass and must never contact a real
      // email provider configured in astra-backend/.env.
      env: {
        ...process.env,
        APP_ENV: "development",
        OTP_DEBUG_LOG: "true",
        RESEND_API_KEY: "",
        SMTP_HOST: "",
        SMTP_USERNAME: "",
        SMTP_USER: "",
        SMTP_PASSWORD: "",
      },
    },
    {
      // Invoke Next directly so Playwright owns the actual server process on
      // Windows too; npm.cmd can leave its child alive after the suite ends.
      command: "node ./node_modules/next/dist/bin/next dev",
      url: "http://localhost:3000/login",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
