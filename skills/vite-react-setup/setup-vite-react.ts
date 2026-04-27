#!/usr/bin/env bun

/**
 * Automated setup script for Vite + React + TypeScript + Tailwind v4 + shadcn/ui + Vitest + Biome.
 * Uses bun as the runtime and package manager.
 *
 * Usage:
 *   bun .claude/skills/vite-react-setup/setup-vite-react.ts              # Setup in current directory
 *   bun .claude/skills/vite-react-setup/setup-vite-react.ts frontend/    # Setup in subdirectory
 */

// @ts-ignore — `bun` is a runtime-provided module; types resolve at runtime
// even when bun-types isn't installed in the host project.
import { $ } from "bun";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmdirSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";

const targetDir = process.argv[2] ?? ".";
const isCurrentDir = targetDir === ".";
const displayName = isCurrentDir ? "current directory" : targetDir;

console.log(`Setting up Vite React app in ${displayName}...`);

const writeFile = (filePath: string, content: string): void => {
  console.log(`\nWriting ${filePath}`);
  writeFileSync(filePath, `${content.trim()}\n`);
};

// Step 1: Create Vite project
console.log("\nStep 1: Creating Vite project...");
if (isCurrentDir) {
  // Scaffold into tmp/vite-setup/, then move files into the project root.
  // (`bun create vite .` refuses to scaffold into a non-empty directory.)
  //
  // tmp/ is the project's standard scratch location: gitignored AND wiped by
  // `make clean`, so a partially-scaffolded directory left behind by a failed
  // run is invisible to git and trivially reclaimable.
  mkdirSync("tmp", { recursive: true });
  const tempDir = join("tmp", "vite-setup");
  await $`bun create vite@latest ${tempDir} --template react-ts`;

  for (const file of readdirSync(tempDir)) {
    renameSync(join(tempDir, file), file);
  }
  rmdirSync(tempDir);
  console.log("Moved files to current directory");
} else {
  await $`bun create vite@latest ${targetDir} --template react-ts`;
  process.chdir(targetDir);
}

// Step 2: Install base dependencies
console.log("\nStep 2: Installing base dependencies...");
await $`bun install`;

// Step 3: Install Tailwind CSS v4
console.log("\nStep 3: Installing Tailwind CSS v4...");
await $`bun add tailwindcss @tailwindcss/vite`;

// Step 4: Install shadcn/ui dependencies
console.log("\nStep 4: Installing shadcn/ui dependencies...");
await $`bun add -d @types/node`;
await $`bun add class-variance-authority clsx tailwind-merge`;

// Step 5: Install Vitest
console.log("\nStep 5: Installing Vitest...");
await $`bun add -d vitest @vitest/ui jsdom @testing-library/react @testing-library/jest-dom`;

// Step 6: Replace ESLint with Biome.
//
// The Vite react-ts template scaffolds with ESLint by convention, but the
// project rules pick exactly one tool — Biome — so we strip ESLint deps and
// install Biome in its place. Combining Biome with ESLint+Prettier is
// explicitly disallowed: their rule sets fight on the same files.
console.log("\nStep 6: Switching from ESLint to Biome...");
await $`bun remove @eslint/js eslint eslint-plugin-react-hooks eslint-plugin-react-refresh globals typescript-eslint`;
if (existsSync("eslint.config.js")) {
  unlinkSync("eslint.config.js");
  console.log("Removed eslint.config.js");
}
await $`bun add -d @biomejs/biome`;
await $`bunx --bun biome init`;

// Step 7: Configure Vite
console.log("\nStep 7: Configuring Vite...");
const viteConfig = `/// <reference types="vitest/config" />
import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// \`base\` controls the URL prefix Vite bakes into asset paths.
// - Local dev / non-Pages builds: "/"
// - GitHub Pages: actions/configure-pages exports the project sub-path
//   (e.g. "/repo-name/") and the workflow forwards it via PAGES_BASE_PATH.
const base = process.env.PAGES_BASE_PATH ?? "/"

export default defineConfig({
  base,
  plugins: [
    tailwindcss(),
    react(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', '.claude'],
  },
})`;
writeFile("vite.config.ts", viteConfig);

// Step 8: Patch tsconfig.json AND tsconfig.app.json with path aliases.
//
// We patch via string replacement rather than JSON.parse because the Vite
// react-ts template ships tsconfig.app.json with `/* … */` comments (JSONC),
// which JSON.parse rejects. String replacement also preserves the template's
// original formatting and inline comments — useful when humans diff the file.
//
// `baseUrl` is deliberately omitted — it is deprecated in TypeScript 6+ and
// `paths` resolves relative to each tsconfig file's location.
console.log("\nStep 8: Configuring TypeScript...");

const patchTsconfig = (filePath: string): void => {
  if (!existsSync(filePath)) return;
  let content = readFileSync(filePath, "utf8");

  // Drop any existing baseUrl line (deprecated in TS 6+).
  content = content.replace(/^\s*"baseUrl"\s*:\s*"[^"]*"\s*,?\s*\n/m, "");

  // Replace any existing paths block, or insert one after `"compilerOptions": {`.
  const pathsLine = '    "paths": { "@/*": ["./src/*"] }';
  if (/"paths"\s*:\s*\{[^}]*\}/.test(content)) {
    content = content.replace(/"paths"\s*:\s*\{[^}]*\}/, pathsLine.trim());
  } else {
    content = content.replace(
      /("compilerOptions"\s*:\s*\{)/,
      `$1\n${pathsLine},`,
    );
  }

  writeFileSync(filePath, content);
  console.log(`\nPatched ${filePath}`);
};

patchTsconfig("tsconfig.json");
patchTsconfig("tsconfig.app.json");

// Step 9: Configure Tailwind CSS
console.log("\nStep 9: Configuring Tailwind CSS...");
writeFile("src/index.css", '@import "tailwindcss";');

// Step 10: Vite environment types
console.log("\nStep 10: Creating Vite environment types...");
writeFile("src/vite-env.d.ts", '/// <reference types="vite/client" />');

// Step 11: Patch biome.json — exclude common build/test/scratch dirs and
// enable Tailwind directive parsing so `@apply`, `@theme`, etc. don't trip
// the CSS parser. Biome's init writes a JSONC-style file with tabs.
console.log("\nStep 11: Configuring Biome...");
if (existsSync("biome.json")) {
  let bio = readFileSync("biome.json", "utf8");
  // Replace the default `includes` array with one that excludes our outputs.
  bio = bio.replace(
    /"includes":\s*\[[^\]]*\]/,
    `"includes": [
		"**",
		"!!**/.claude",
		"!!**/dist",
		"!!**/coverage",
		"!!**/e2e-screenshots",
		"!!**/playwright-report",
		"!!**/test-results",
		"!!**/tmp"
	]`,
  );
  // Insert `css` block with tailwindDirectives if not already present.
  if (!/"css"\s*:/.test(bio)) {
    bio = bio.replace(
      /("javascript"\s*:\s*\{[^}]*\}\s*,?)/,
      `$1
	"css": {
		"parser": {
			"cssModules": true,
			"tailwindDirectives": true
		}
	},`,
    );
  }
  writeFileSync("biome.json", bio);
  console.log("Patched biome.json");
}

// Step 12: Install Playwright for end-to-end testing.
console.log("\nStep 12: Installing Playwright...");
await $`bun add -d @playwright/test`;
await $`bunx --bun playwright install --with-deps chromium`;

// Step 13: Write Playwright config — dev server runs on agentic port (5174)
// so a human running `make dev` on 5173 can keep working in parallel.
console.log("\nStep 13: Writing Playwright config...");
const playwrightConfig = `import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PLAYWRIGHT_PORT ?? 5174);
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? \`http://localhost:\${PORT}\`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  outputDir: "test-results",
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "default", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: \`bun run dev -- --port \${PORT} --strictPort\`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});`;
writeFile("playwright.config.ts", playwrightConfig);

// Step 14: Write the e2e starter spec — slug taxonomy + coverage matrix
// pattern (see docs in the file for how to expand axes when filters are
// added to the app).
console.log("\nStep 14: Writing e2e starter spec...");
mkdirSync("e2e", { recursive: true });
const e2eSpec = `import { mkdirSync, writeFileSync } from "node:fs";
import { type Page, expect, test } from "@playwright/test";
import type { Request as PlaywrightRequest } from "@playwright/test";

/**
 * Universal Routes E2E Test Suite
 *
 * Site-map smoke test: every route declared in SECTIONS gets a generated
 * permutation test that:
 *   1. Navigates to the path
 *   2. Waits for React to mount + the network to settle
 *   3. Asserts zero browser console errors
 *   4. Takes a full-page screenshot
 *   5. Writes paired .log + .network.json artifacts keyed by the slug
 *
 * Slug format:
 *   E{id}_{ENGINE}-S{id}_{SECTION}.png
 *
 * To add a route to the smoke suite: append an entry to SECTIONS. Done.
 * To grow new axes (time ranges, viewport sizes, locales) when the app
 * gains filters, copy the ENGINES/SECTIONS shape and weave them into the
 * permutation loop at the bottom of this file.
 */

const ENGINES = { default: { id: 1, name: "default" } } as const;
type EngineKey = keyof typeof ENGINES;
type Engine = (typeof ENGINES)[EngineKey];

const getEngine = (): Engine => {
  const projectName = test.info().project.name as EngineKey;
  return ENGINES[projectName] ?? ENGINES.default;
};

const SECTIONS = [
  { id: 0, slug: "home", name: "Home", path: "/" },
] as const;
type Section = (typeof SECTIONS)[number];

interface CoverageEntry { section: Section }
const COVERAGE_MATRIX: CoverageEntry[] = SECTIONS.map((section) => ({ section }));

const pad = (n: number): string => String(n).padStart(2, "0");
const screenshotSlug = (engine: Engine, section: Section): string =>
  \`E\${pad(engine.id)}_\${engine.name.toUpperCase()}-S\${pad(section.id)}_\${section.slug.toUpperCase()}\`;

interface NetworkTiming {
  url: string;
  method: string;
  status: number | null;
  start_offset_ms: number;
  duration_ms: number;
  resource_type: string;
}

interface TestCollector {
  writeLog: (slug: string) => void;
  assertNoErrors: () => void;
}

const collectTestIO = (page: Page): TestCollector => {
  const testStart = Date.now();
  const lines: string[] = [];
  const errors: string[] = [];

  page.on("pageerror", (err) => {
    lines.push(\`[PAGE_ERROR] \${err.message}\`);
    errors.push(err.message);
  });
  page.on("console", (msg) => {
    const level = msg.type().toUpperCase().padEnd(7);
    lines.push(\`[\${level}] \${msg.text()}\`);
    if (msg.type() === "error") errors.push(msg.text());
  });

  const network: NetworkTiming[] = [];
  const pending = new Map<PlaywrightRequest, number>();

  page.on("request", (req) => { pending.set(req, Date.now()); });
  page.on("requestfinished", async (req) => {
    const start = pending.get(req);
    if (start === undefined) return;
    pending.delete(req);
    const res = await req.response();
    network.push({
      url: req.url(), method: req.method(),
      status: res ? res.status() : null,
      start_offset_ms: start - testStart,
      duration_ms: Date.now() - start,
      resource_type: req.resourceType(),
    });
  });
  page.on("requestfailed", (req) => {
    const start = pending.get(req);
    if (start === undefined) return;
    pending.delete(req);
    network.push({
      url: req.url(), method: req.method(), status: null,
      start_offset_ms: start - testStart,
      duration_ms: Date.now() - start,
      resource_type: req.resourceType(),
    });
  });

  return {
    writeLog(slug: string): void {
      const dir = "e2e-screenshots";
      mkdirSync(dir, { recursive: true });
      writeFileSync(\`\${dir}/\${slug}.log\`, \`\${lines.join("\\n")}\\n\`, "utf-8");
      const wallClockEnd = network.reduce(
        (max, n) => Math.max(max, n.start_offset_ms + n.duration_ms), 0,
      );
      const summary = {
        test_start_ms: testStart,
        wall_clock_duration_ms: wallClockEnd,
        total_requests: network.length,
        total_duration_ms: network.reduce((s, n) => s + n.duration_ms, 0),
        all_requests: [...network].sort((a, b) => a.start_offset_ms - b.start_offset_ms),
      };
      writeFileSync(\`\${dir}/\${slug}.network.json\`,
        \`\${JSON.stringify(summary, null, 2)}\\n\`, "utf-8");
    },
    assertNoErrors(): void {
      const real = errors.filter((e) =>
        !e.includes("act(") && !e.includes("favicon") && !e.includes("[vite]"));
      expect(real, \`Browser console errors:\\n\${real.join("\\n")}\`).toHaveLength(0);
    },
  };
};

const waitForPageLoad = async (page: Page): Promise<void> => {
  await page.waitForFunction(
    () => (document.getElementById("root")?.children.length ?? 0) > 0,
    { timeout: 15_000 },
  );
  await page.waitForLoadState("networkidle", { timeout: 3_000 }).catch(() => {});
};

for (const entry of COVERAGE_MATRIX) {
  test.describe(\`\${entry.section.name} route\`, () => {
    const testLabel = \`S\${pad(entry.section.id)}_\${entry.section.slug}: \${entry.section.path}\`;
    test(testLabel, async ({ page }) => {
      const engine = getEngine();
      const slug = screenshotSlug(engine, entry.section);
      const io = collectTestIO(page);
      await page.goto(entry.section.path);
      await waitForPageLoad(page);
      await page.screenshot({ path: \`e2e-screenshots/\${slug}.png\`, fullPage: true });
      io.writeLog(slug);
      io.assertNoErrors();
    });
  });
}
`;
writeFile("e2e/routes.spec.ts", e2eSpec);

// Step 15: Write GitHub Actions workflow — build + lint + test + e2e + Pages deploy.
// Action versions are pinned to current majors as of 2026-04. Bump in
// routine maintenance; minor/patch updates are safe automatic.
console.log("\nStep 15: Writing GitHub Actions workflow...");
mkdirSync(".github/workflows", { recursive: true });
const workflow = `name: Build

on:
  push:
    branches: [main]
    tags: ["v*"]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: build-\${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    name: Build, lint, test
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: write

    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Setup Bun
        uses: oven-sh/setup-bun@v2
        with:
          bun-version: latest

      - name: Install dependencies
        run: bun install --frozen-lockfile

      - name: Audit dependencies
        run: bun audit --audit-level=high

      - name: Lint & format check
        run: bunx --bun biome ci .

      - name: Type check & build
        run: bun run build

      - name: Run unit tests
        run: bun run test --run --passWithNoTests

      - name: Cache Playwright browsers
        uses: actions/cache@v5
        with:
          path: ~/.cache/ms-playwright
          key: playwright-\${{ runner.os }}-\${{ hashFiles('bun.lock') }}
          restore-keys: |
            playwright-\${{ runner.os }}-

      - name: Install Playwright browsers
        run: bunx --bun playwright install --with-deps chromium

      - name: Run e2e tests
        run: bun run test:e2e

      - name: Upload e2e artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v7
        with:
          name: e2e-failures-\${{ github.run_id }}-\${{ github.sha }}
          path: |
            e2e-screenshots/
            playwright-report/
            test-results/
          if-no-files-found: ignore
          retention-days: 14

      - name: Upload dist artifact
        uses: actions/upload-artifact@v7
        with:
          name: site-dist-\${{ github.run_id }}-\${{ github.sha }}
          path: dist/
          if-no-files-found: error
          retention-days: 30

      - name: Upload release asset
        if: startsWith(github.ref, 'refs/tags/v')
        env:
          GH_TOKEN: \${{ secrets.GITHUB_TOKEN }}
        run: |
          ARCHIVE="site-\${GITHUB_REF_NAME}.zip"
          (cd dist && zip -r "../\${ARCHIVE}" .)
          gh release upload "\${GITHUB_REF_NAME}" "\${ARCHIVE}" --clobber

  deploy-pages:
    name: Deploy to GitHub Pages
    needs: build
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: \${{ steps.deployment.outputs.page_url }}

    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Setup Bun
        uses: oven-sh/setup-bun@v2
        with:
          bun-version: latest

      - name: Install dependencies
        run: bun install --frozen-lockfile

      - name: Configure Pages
        id: pages
        uses: actions/configure-pages@v6

      - name: Build with Pages base path
        run: bun run build
        env:
          PAGES_BASE_PATH: \${{ steps.pages.outputs.base_path }}

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v5
        with:
          path: dist

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v5
`;
writeFile(".github/workflows/build.yml", workflow);

// Step 16: Update package.json scripts.
console.log("\nStep 16: Updating package.json scripts...");
type PackageJson = { scripts?: Record<string, string>; [k: string]: unknown };
const packageJson: PackageJson = JSON.parse(readFileSync("package.json", "utf8"));
// Quality scripts:
//   - `lint`         strict read-only check. Uses `biome ci` (not `biome lint`)
//                    so warnings AND info-level findings fail — same behavior
//                    as the generated GitHub Actions workflow. Enforces the
//                    strict no-warnings policy.
//   - `lint-fix`     apply lint auto-fixes only, leave formatting alone.
//                    Includes --unsafe so `useNodejsImportProtocol` etc. get
//                    rewritten.
//   - `format`       autofix formatting only (whitespace, indentation).
//   - `format-check` read-only format check; fails if any file would be
//                    reformatted.
//
// Note: there's no `fix` script here. The Makefile's `fix` target is a meta-
// target that depends on `format` + `lint-fix`, composing the autofix chain
// at the Make level rather than via a redundant package.json wrapper.
packageJson.scripts = {
  ...packageJson.scripts,
  lint: "biome ci .",
  "lint-fix": "biome lint --write --unsafe .",
  format: "biome format --write .",
  "format-check": "biome format .",
  test: "vitest",
  "test:ui": "vitest --ui",
  "test:e2e": "playwright test",
};
writeFile("package.json", JSON.stringify(packageJson, null, 2));

// Step 17: Write the Makefile — single command-and-control surface.
//
// The DAG is the program: `fix` is a meta-target with no recipe, just deps
// `install format lint-fix`. `ci` is the strict gate. The canonical
// inner-loop is `make fix ci` — fix all autofixable issues, then verify
// against the strict CI gate.
//
// Two dev profiles run on different ports so a human running `make dev` (5173)
// can develop in parallel with an AI agent running `make agentic-dev` (5174).
console.log("\nStep 17: Writing Makefile...");
const makefile = `.PHONY: help install dev agentic-dev build preview clean
.PHONY: audit format format-check lint lint-fix fix typecheck
.PHONY: test test-watch test-ui test-e2e test-e2e-ui ci
.PHONY: port-debug port-clean agentic-port-clean

# =============================================================================
# Port Configuration
# =============================================================================
# Human developer port (default Vite port).
DEV_PORT ?= 5173

# AI agent port (use for \`agentic-dev\` so it can run in parallel with \`dev\`).
AGENTIC_DEV_PORT ?= 5174

help: ## Show this help
\t@grep -E '^[a-zA-Z0-9_-]+:.*?## .*\$$' \$(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\\033[36m%-22s\\033[0m %s\\n", \$$1, \$$2}'

# =============================================================================
# Installation
# =============================================================================
# Sentinel-file pattern: \`bun install\` only runs when package.json or bun.lock
# is newer than node_modules/.bun_deps. Every other target chains through
# \`install\` for cheap idempotence.

install: node_modules/.bun_deps ## Install dependencies (bun install, idempotent)

node_modules/.bun_deps: package.json bun.lock
\tbun install
\t@touch \$@

# =============================================================================
# Human Developer Targets (default port 5173)
# =============================================================================

dev: install ## Run Vite dev server for human developers (port 5173)
\t@echo "==============================================================================="
\t@echo "| Starting Vite dev server (HUMAN profile)...                                 |"
\t@echo "|                                                                             |"
\t@echo "| http://localhost:\$(DEV_PORT)                                                       |"
\t@echo "|                                                                             |"
\t@echo "| For AI agent development: make agentic-dev (port \$(AGENTIC_DEV_PORT))                       |"
\t@echo "==============================================================================="
\tbun run dev -- --port \$(DEV_PORT) --strictPort

# =============================================================================
# AI Agent Development Targets (port 5174)
# =============================================================================

agentic-dev: install ## Run Vite dev server for AI agent development (port 5174)
\t@echo "==============================================================================="
\t@echo "| Starting Vite dev server (AGENTIC CODING profile)...                        |"
\t@echo "|                                                                             |"
\t@echo "| http://localhost:\$(AGENTIC_DEV_PORT)                                                       |"
\t@echo "|                                                                             |"
\t@echo "| For human development: make dev (port \$(DEV_PORT))                                  |"
\t@echo "==============================================================================="
\tbun run dev -- --port \$(AGENTIC_DEV_PORT) --strictPort

# =============================================================================
# Build & Preview
# =============================================================================

build: install ## Production build (tsc -b && vite build) -> dist/
\tbun run build

preview: install ## Preview the built bundle locally
\tbun run preview

# =============================================================================
# Code Quality
# =============================================================================
# Single tool for both lint and format: Biome. \`lint\` is read-only (strict —
# fails on warnings/info too); \`format\` modifies whitespace only; \`fix\` is the
# "make my code clean" meta-target — applies all auto-fixable lint and format
# issues including unsafe ones, by composing format + lint-fix.

audit: install ## Audit dependencies for known vulnerabilities (high+ severity)
\tbun audit --audit-level=high

format: install ## Auto-format code (Biome format --write — modifies files)
\tbun run format

format-check: install ## Format check only — fails if any file would be reformatted (no writes)
\tbun run format-check

lint: install audit ## Strict check: Biome ci + audit (fails on warnings/info — matches CI)
\tbun run lint

lint-fix: install ## Auto-fix lint findings only — leaves formatting alone (Biome lint --write --unsafe)
\tbun run lint-fix

fix: install format lint-fix ## Auto-fix all fixable lint + format issues (composes format + lint-fix)

typecheck: install ## TypeScript type check (tsc -b, no emit — leaf tsconfigs set noEmit:true)
\tbunx --bun tsc -b

test: install ## Run Vitest unit tests once (passes if no test files yet)
\tbun run test --run --passWithNoTests

test-ui: install ## Run Vitest with the @vitest/ui dashboard
\tbun run test:ui

test-e2e: install ## Run Playwright e2e tests (auto-starts dev server on agentic port)
\tbun run test:e2e

test-e2e-ui: install ## Run Playwright in interactive UI mode
\tbun run test:e2e -- --ui

# Canonical inner-loop: \`make fix ci\` — autofix everything, then run the
# strict gate. \`audit\` and \`format-check\` listed explicitly even though
# \`lint\` covers them transitively, so removing \`lint\`'s deps later doesn't
# silently weaken CI. Make's dep dedup ensures each target runs at most once.
ci: audit build format-check typecheck lint test test-e2e ## Run all CI checks (strict gate)

# =============================================================================
# Port Management
# =============================================================================
# \`port-clean\` and \`agentic-port-clean\` are deliberately split so the human
# and the agent can each clean up their own port without disturbing the other.

port-debug: ## Show which dev ports are in use
\t@pid=\$$(lsof -ti:\$(DEV_PORT) 2>&1); [ -n "\$$pid" ] && echo "Port \$(DEV_PORT) (human)   in use by PID \$$pid" || echo "Port \$(DEV_PORT) (human)   free."
\t@pid=\$$(lsof -ti:\$(AGENTIC_DEV_PORT) 2>&1); [ -n "\$$pid" ] && echo "Port \$(AGENTIC_DEV_PORT) (agentic) in use by PID \$$pid" || echo "Port \$(AGENTIC_DEV_PORT) (agentic) free."

port-clean: ## Kill processes on the human dev port only
\t@pid=\$$(lsof -ti:\$(DEV_PORT) 2>&1); [ -n "\$$pid" ] && kill -9 \$$pid && echo "Killed PID \$$pid on port \$(DEV_PORT)" || echo "Port \$(DEV_PORT) free."

agentic-port-clean: ## Kill processes on the agentic dev port only
\t@pid=\$$(lsof -ti:\$(AGENTIC_DEV_PORT) 2>&1); [ -n "\$$pid" ] && kill -9 \$$pid && echo "Killed PID \$$pid on port \$(AGENTIC_DEV_PORT)" || echo "Port \$(AGENTIC_DEV_PORT) free."

# =============================================================================
# Cleanup
# =============================================================================

clean: ## Clean up build artifacts, test outputs, deps, and tmp/
\trm -rf dist
\trm -rf coverage
\trm -rf e2e-screenshots
\trm -rf playwright-report
\trm -rf test-results
\trm -rf node_modules
\trm -rf tmp
`;
writeFile("Makefile", makefile);

// Step 18: Initialize shadcn/ui (with defaults). bunx forces the bun runtime.
console.log("\nStep 18: Initializing shadcn/ui...");
await $`bunx --bun shadcn@latest init -d`;

// Step 19: Format generated files with Biome (shadcn writes its own style).
console.log("\nStep 19: Running Biome check on generated files...");
await $`bunx --bun biome check --write --unsafe . || true`;

// Step 20: Verify build
console.log("\nStep 20: Testing build...");
await $`bun run build`;

// Step 21: Verify e2e (smoke test the home route).
console.log("\nStep 21: Running e2e smoke test...");
await $`bun run test:e2e`;

console.log("\nSetup complete.");
console.log("\nCanonical inner-loop:");
if (!isCurrentDir) {
  console.log(`  cd ${targetDir}`);
}
console.log("  make fix ci          # Autofix everything, then run the strict gate");
console.log("\nOther make targets:");
console.log("  make dev             # Vite dev server, port 5173 (human profile)");
console.log("  make agentic-dev     # Vite dev server, port 5174 (AI agent profile)");
console.log("  make build           # Production build → dist/");
console.log("  make test            # Vitest unit tests");
console.log("  make test-e2e        # Playwright e2e tests");
console.log("  make help            # Auto-discovered list of every target");
console.log("\nNote: use `bun run test`, NOT `bun test` — the latter invokes");
console.log("bun's built-in test runner instead of Vitest.");
console.log("\nAdd shadcn components:");
console.log("  bunx --bun shadcn@latest add button card");
console.log("\nGitHub Pages: in repo Settings → Pages, set Source: GitHub Actions.");
console.log("Pushes to main will deploy automatically via .github/workflows/build.yml.");
