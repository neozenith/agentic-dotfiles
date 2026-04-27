# Vite React Setup Skill

Automated setup script for creating a production-ready Vite + React + TypeScript project with modern tooling, using **bun** as the runtime and package manager.

## What it includes

- **Vite** — next-generation frontend tooling
- **React 19** with **TypeScript**
- **Tailwind CSS v4** — utility-first CSS framework via the new Vite plugin (no `tailwind.config.js`)
- **shadcn/ui** — re-usable component library
- **Biome** — single tool for lint + format + import organization (replaces ESLint + Prettier)
- **Vitest** — fast unit testing framework, scoped to `src/**`
- **Playwright** — end-to-end testing with the **slug-taxonomy + coverage-matrix** pattern (see "E2e pattern" below)
- **bun audit** — dependency security check, wired into the lint chain
- **GitHub Actions** — build + audit + biome ci + unit + e2e + Pages deploy, with current major action versions
- Path aliases (`@/*` → `./src/*`) configured in both `tsconfig.json` and `tsconfig.app.json`

## Usage

### From command line

```bash
# Set up in the current directory
bun .claude/skills/vite-react-setup/setup-vite-react.ts

# Set up in a named subdirectory
bun .claude/skills/vite-react-setup/setup-vite-react.ts my-project-name
```

### From Claude Code

Ask Claude to "set up a new Vite React project" and provide the project name (or omit for the current directory).

## What the script does

1. Scaffolds a Vite + React + TypeScript project (`bun create vite@latest`).
   - When the target is the current directory, the scaffold is created in
     `tmp/vite-setup/` first and then files are moved into the project root,
     because `bun create vite .` refuses to scaffold into a non-empty
     directory. `tmp/` is conventionally gitignored and wiped by `make clean`.
2. Installs all base dependencies (`bun install`, `bun add`, `bun add -d`).
3. Configures Tailwind CSS v4 with the Vite plugin (`@import "tailwindcss"` in `src/index.css`).
4. Strips the scaffold's ESLint deps and `eslint.config.js`, then installs Biome and runs `biome init`.
5. Patches `biome.json` to exclude build/test/scratch dirs and enable Tailwind directive parsing.
6. Patches **both** `tsconfig.json` and `tsconfig.app.json` with the `@/*` path alias (no deprecated `baseUrl`).
7. Configures Vite (`vite.config.ts`) — Tailwind plugin, React plugin, `@/*` alias, Vitest scoped to `src/**`, and a `base` path that honors `PAGES_BASE_PATH` for GitHub Pages deploys.
8. Installs Playwright + chromium, writes `playwright.config.ts` (dev server on agentic port 5174 for parallel-safe runs), and writes a starter `e2e/routes.spec.ts` using the slug-taxonomy pattern.
9. Writes `.github/workflows/build.yml` with the latest action versions (checkout@v6, cache@v5, upload-artifact@v7, setup-bun@v2, configure-pages@v6, upload-pages-artifact@v5, deploy-pages@v5). Two jobs: `build` (always) and `deploy-pages` (push to main only).
10. Sets up shadcn/ui with default configuration (`bunx --bun shadcn@latest init -d`).
11. Adds `test` / `test:ui` / `test:e2e` scripts to `package.json` plus biome `lint` / `format` / `check` scripts.
12. Runs `bun run build` AND `bun run test:e2e` to verify everything compiles and the home route loads.

## E2e pattern: slug taxonomy + coverage matrix

Mirrors `claude-code-sessions/frontend/e2e/filters.spec.ts`:

- **Axes** are `const` arrays of `{ id, slug, ... }` records. `id` is numeric (padded to 2 digits) for lexicographic artifact sorting; `slug` is a URL-safe lowercase identifier.
- The starter spec ships with `ENGINES` (single `default`) and `SECTIONS` (the site map). Add new axes (time ranges, viewport sizes, locales) when needed.
- **`COVERAGE_MATRIX`** declares permutations to test. Nested for-loops generate one `test()` per matrix entry.
- **`collectTestIO(page)`** captures console output, page errors, and network timing. Each test produces paired artifacts keyed by slug:
  - `e2e-screenshots/<slug>.png` — full-page screenshot
  - `e2e-screenshots/<slug>.log` — console + page-error stream
  - `e2e-screenshots/<slug>.network.json` — start-offset-sorted timing summary, ready for Gantt visualization
- The slug builder produces names like `E01_DEFAULT-S00_HOME` so all artifacts for a route sort together.

To add a route: append `{ id, slug, name, path }` to `SECTIONS`. Done. Every entry automatically gets navigate → wait → assert no console errors → screenshot.

## After setup

```bash
bun run dev          # Start development server
bun run build        # Build for production
bun run test         # Vitest unit tests (do NOT use `bun test`)
bun run test:e2e     # Playwright e2e tests
bun run lint         # Biome lint check
bun run format       # Biome format --write
bun run check        # Biome check --write (lint + format + organize imports)
```

Add shadcn/ui components:

```bash
bunx --bun shadcn@latest add button card
```

### One-time GitHub Pages setup

In repo **Settings → Pages**, set **Source: GitHub Actions**. The workflow's `deploy-pages` job will register the `github-pages` environment automatically on the first push to `main`. Live URL appears in the deploy job's run summary.

## Why these specific choices

- **`bun create vite` over `npm create vite`** — keeps the project on a single package manager from scaffold onwards; no orphan `package-lock.json`.
- **`bunx --bun`** — forces shadcn's CLI / Biome / Playwright / tsc to execute on bun's runtime instead of node, and ensures lockfile detection picks up `bun.lock`.
- **Paths in both tsconfigs** — Vite's react-ts template uses TypeScript project references. The root `tsconfig.json` only configures references; `tsconfig.app.json` is the leaf the build actually consults. Having `@/*` in only one of them is a common silent failure (build fails with "Cannot find module '@/lib/utils'").
- **No `baseUrl`** — deprecated in TypeScript 6+ (TS5101). Modern `paths` resolves relative to each tsconfig's location.
- **Vitest `include` scoped to `src/**`** — without this, Vitest discovers `.claude/skills/**/*.test.ts` files (often written for `bun:test`) and crashes the runner.
- **Biome over ESLint + Prettier** — the project rule is "pick ONE — do not combine Biome with ESLint/Prettier." Their rule sets fight on the same files. Biome is the modern choice (single binary, ~10-100x faster, both lint and format).
- **Playwright on the agentic port (5174)** — so a human running `make dev` on 5173 can keep working while `make test-e2e` runs in parallel.
- **`actions/deploy-pages` over `gh-pages` branch** — modern Pages is artifact-based, not branch-based. No deploy branch to maintain or accidentally diff against.
- **`bun audit --audit-level=high` in lint** — fails the build on new high+ severity vulnerabilities at PR time, not deploy time.

## Requirements

- bun 1.2+ (for the text lockfile, `bun create vite`, `Bun.$`, and `bun audit`)
- Node 20+ optional fallback (the `.ts` script requires bun's runtime; only the legacy `.js` version supports node)

## Notes

- Action versions in the generated workflow are pinned to current majors as of 2026-04. Bump in routine maintenance.
- The script verifies both the build AND the e2e smoke test before completing — a green setup means a deployable scaffold.
