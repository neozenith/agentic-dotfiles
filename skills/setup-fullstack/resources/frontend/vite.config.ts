/// <reference types="vitest/config" />
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const apiPort = process.env.API_PORT ?? "8200";
const devPort = Number(process.env.DEV_PORT ?? 5173);
const base = process.env.PAGES_BASE_PATH ?? "/";

export default defineConfig({
  base,
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: devPort,
    strictPort: true,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", "dist", "e2e", ".claude"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      // Coverage focuses on src/lib/** — the deterministic, unit-testable
      // surface. UI components and pages are covered by the Playwright e2e
      // suite (slug-taxonomy + coverage-matrix), not Vitest.
      // src/lib/api.ts is excluded because testing it at the unit level
      // would require mocking fetch (against the project's no-mocks ethos);
      // the Playwright e2e exercises it end-to-end against the real backend.
      include: ["src/lib/**/*.{ts,tsx}"],
      exclude: ["src/lib/**/*.test.{ts,tsx}", "src/lib/api.ts"],
      thresholds: {
        lines: 90,
        functions: 90,
        branches: 90,
        statements: 90,
      },
    },
  },
});
