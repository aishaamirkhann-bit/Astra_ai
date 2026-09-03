import fs from "node:fs";
import path from "node:path";
import { request, type FullConfig } from "@playwright/test";

const STATE_PATH = path.join(__dirname, ".auth", "state.json");

/**
 * Logs in ONCE through the real API and persists the auth state (httpOnly
 * cookie + astra_user localStorage) so individual tests start authenticated.
 * Keeps the suite far below the backend's login rate limit (8/60s).
 */
export default async function globalSetup(config: FullConfig) {
  const backend = "http://localhost:8000";
  const context = await request.newContext({ baseURL: backend });
  try {
    const login = await context.post("/api/v1/auth/login", {
      data: { email: "aisha@astra.ai", password: "demo1234" },
    });
    if (!login.ok()) throw new Error(`global-setup login failed: ${login.status()} ${await login.text()}`);
    const { otp_token } = (await login.json()) as { otp_token: string };

    const verify = await context.post("/api/v1/auth/verify-otp", {
      data: { otp_token, code: "123456" },
    });
    if (!verify.ok()) throw new Error(`global-setup verify-otp failed: ${verify.status()} ${await verify.text()}`);
    const { user } = (await verify.json()) as { user: unknown };

    const { cookies } = await context.storageState();
    const state = {
      cookies,
      origins: [
        {
          origin: config.projects[0]?.use.baseURL ?? "http://localhost:3000",
          localStorage: [{ name: "astra_user", value: JSON.stringify(user) }],
        },
      ],
    };
    fs.mkdirSync(path.dirname(STATE_PATH), { recursive: true });
    fs.writeFileSync(STATE_PATH, JSON.stringify(state));
  } finally {
    await context.dispose();
  }
}
