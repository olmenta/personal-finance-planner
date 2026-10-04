import { readFileSync } from "node:fs";
import path from "node:path";
import { defineConfig, devices } from "@playwright/test";
import { E2E_TODAY } from "./e2e/support/constants";

/* End-to-end suite: its own API (port 8100) on the Neon "e2e" branch and its
   own Next dev server (port 3100, build dir .next-e2e), so it never touches
   your dev servers on 8000/3000 or your dev data. "Today" is pinned on both
   sides (FIXED_TODAY + page.clock) so months and paid/pending are stable. */

const API_PORT = 8100;
const WEB_PORT = 3100;
const backendDir = path.resolve(__dirname, "../backend");

/** Reads E2E_* from backend/.env (gitignored); CI can set them as env vars. */
function backendEnv(key: string): string {
  if (process.env[key]) return process.env[key];
  let file = "";
  try {
    file = readFileSync(path.join(backendDir, ".env"), "utf8");
  } catch {
    // no backend/.env: fall through to the error below
  }
  const line = file.split("\n").find((l) => l.startsWith(`${key}=`));
  const value = line?.slice(key.length + 1).trim().replace(/^"(.*)"$/, "$1");
  if (!value) throw new Error(`${key} is not set (backend/.env or environment)`);
  return value;
}

export default defineConfig({
  testDir: "./e2e",
  // One shared database: spec files run one at a time, each from a reset.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"], ["html", { open: "never" }]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    locale: "es-ES",
    timezoneId: "Europe/Madrid",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } }],
  webServer: [
    {
      command: `uv run uvicorn app.main:app --port ${API_PORT}`,
      cwd: backendDir,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        DATABASE_URL: backendEnv("E2E_DATABASE_URL"),
        MIGRATIONS_DATABASE_URL: backendEnv("E2E_MIGRATIONS_DATABASE_URL"),
        FIXED_TODAY: E2E_TODAY,
        // No telemetry and no live LLM calls from test runs.
        SENTRY_DSN: "",
        ANTHROPIC_API_KEY: "",
      },
    },
    {
      command: `npx next dev --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 180_000,
      env: {
        BACKEND_URL: `http://127.0.0.1:${API_PORT}`,
        NEXT_DIST_DIR: ".next-e2e",
        NEXT_PUBLIC_SENTRY_DSN: "",
        SENTRY_DSN: "",
      },
    },
  ],
});
