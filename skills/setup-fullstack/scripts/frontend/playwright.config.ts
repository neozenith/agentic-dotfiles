import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PLAYWRIGHT_PORT ?? 5174);
const API_PORT = process.env.PLAYWRIGHT_API_PORT ?? "8201";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`;

// When PLAYWRIGHT_FRONTEND_ONLY=1, the webServer block spawns ONLY the Vite
// frontend — used by `make test-e2e-docker`, where the backend is already
// running in a Docker container at PLAYWRIGHT_API_PORT. The Vite proxy reads
// API_PORT from its environment, so /api/* routes to the dockerized backend.
//
// Default behaviour: spawn BOTH backend (uvicorn) and frontend (Vite) via
// `concurrently` (the agentic-dev script).
const FRONTEND_ONLY = process.env.PLAYWRIGHT_FRONTEND_ONLY === "1";

const webServerCommand = FRONTEND_ONLY
  ? `API_PORT=${API_PORT} bun run dev:frontend-only -- --port ${PORT} --strictPort`
  : `API_PORT=${API_PORT} DEV_PORT=${PORT} bun run agentic-dev`;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "default", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: webServerCommand,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
