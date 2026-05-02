---
name: vite-react-setup
description: Automated setup for Vite + React + TypeScript + Tailwind CSS v4 + shadcn/ui + Vitest + Playwright + Biome projects, using bun as the runtime and package manager. Includes GitHub Actions workflow with build, e2e, and Pages deploy. Use when setting up new React projects, creating Vite apps, initializing React TypeScript projects, or setting up modern React development environments.
---

# Vite React Setup

Automatically scaffolds a complete modern React development environment with:

- **Build**: Vite + React 19 + TypeScript
- **Styling**: Tailwind CSS v4 with `@tailwindcss/vite` plugin
- **UI primitives**: shadcn/ui, pre-configured with `components.json`
- **Lint + format**: Biome (single tool, replaces ESLint + Prettier)
- **Audit**: `bun audit` wired into the lint chain
- **Unit tests**: Vitest + jsdom + Testing Library, scoped to `src/**`
- **E2e tests**: Playwright with the **slug-taxonomy + coverage-matrix** pattern (see below)
- **Path aliases**: `@/*` declared in both `tsconfig.json` and `tsconfig.app.json`
- **CI/CD**: GitHub Actions workflow with build → audit → biome ci → unit → e2e → Pages deploy
- **Docs split**: `README.md` for users, `CONTRIBUTING.md` for developers (see below)
- **Scratch**: `tmp/vite-setup/` during scaffold (gitignored; reclaimable via `make clean`)

## Usage

```bash
# Setup in current directory
bun .claude/skills/vite-react-setup/setup-vite-react.ts

# Setup in a subdirectory
bun .claude/skills/vite-react-setup/setup-vite-react.ts frontend/
```

The script must run under `bun` — it uses `Bun.$` (typed tagged-template shell) and top-level await. Unlike the legacy `.js` version, it's not designed to fall back to node.

## What gets configured

1. **Vite + React + TypeScript scaffold** via `bun create vite@latest`
2. **Tailwind v4** via `@tailwindcss/vite` plus `@import "tailwindcss"` in `src/index.css`
3. **shadcn/ui** initialized with `bunx --bun shadcn@latest init -d`
4. **Path aliases** patched into both `tsconfig.json` and `tsconfig.app.json` (no deprecated `baseUrl`)
5. **Vitest** scoped to `src/**/*.{test,spec}.{ts,tsx}`, excluding `.claude/`
6. **Biome** replaces ESLint (the scaffold's ESLint deps are removed and `eslint.config.js` is deleted); `biome.json` excludes build/test/scratch dirs and enables Tailwind directive parsing
7. **Playwright** with chromium installed; `playwright.config.ts` runs the dev server on the agentic port (5174) so it can run in parallel with `make dev`
8. **E2e starter spec** (`e2e/routes.spec.ts`) using the slug-taxonomy pattern (see "E2e pattern" below)
9. **GitHub Actions workflow** (`.github/workflows/build.yml`) with current major action versions (checkout@v6, cache@v5, upload-artifact@v7, setup-bun@v2, configure-pages@v6, upload-pages-artifact@v5, deploy-pages@v5)
10. **package.json scripts**: `dev`, `build`, `preview`, `lint` (= `biome ci .` for strict no-warnings policy), `lint-fix`, `format`, `format-check`, `test`, `test:ui`, `test:e2e`
11. **Makefile**: encodes the project's quality DAG. Includes split human/agent dev ports (5173/5174), strict CI gate, and the canonical `make fix ci` inner-loop
12. **README.md preservation + CONTRIBUTING.md generation** (see "Documentation split" below)

### Canonical inner-loop: `make fix ci`

After laying down code, run **`make fix ci`**:

1. **`make fix`** — meta-target with no recipe, just deps `install format lint-fix`. Autoformats every file then applies all auto-fixable lint issues. The DAG is the program; each leaf is independently runnable.
2. **`make ci`** — strict gate: `audit build format-check typecheck lint test test-e2e`. `audit` and `format-check` listed explicitly even though `lint` covers them transitively, so future trimming of `lint`'s deps doesn't silently weaken CI. Make's dep dedup ensures each runs at most once.

If `fix` couldn't autofix something, `ci`'s `lint` step catches it. Clean signal, every time. Both human developers and AI agents should treat `make fix ci` as the standard "I'm done with this code" signal before committing.

### Strict no-warnings policy

The `lint` script uses `biome ci .` rather than `biome lint .`. `biome lint` only fails on errors; `biome ci` fails on warnings AND info-level findings AND format drift. The same command runs in the generated CI workflow, so there's no "passes locally but fails in CI" surprise. Future projects that don't want this strictness can swap to `biome lint .` — but the default is strict because warnings that linger turn into "yellow noise" no one reads.

## Documentation split: README.md + CONTRIBUTING.md

The scaffold treats `README.md` and `CONTRIBUTING.md` as two **non-overlapping** audiences:

| File              | Audience       | Contains                                                                                          |
|-------------------|----------------|---------------------------------------------------------------------------------------------------|
| `README.md`       | **Users**      | Project overview, value proposition, install/consume instructions for end users of the project.   |
| `CONTRIBUTING.md` | **Developers** | How to run dev server, build, test; Make targets; tech stack; tooling decisions; how to add UI components; CI gate; port allocation. |

**Why separate them?** README is the landing page — anyone evaluating whether to adopt this project reads it. CONTRIBUTING is the on-ramp for people who'll modify the code. Mixing them forces users to scroll past dev internals and forces contributors to hunt through marketing copy. Most modern open-source projects (React, Vite, shadcn/ui themselves) follow this split.

### Preservation rules

The Vite scaffold writes its own generic `README.md` (a "React + TypeScript + Vite" template). The setup script must NOT clobber an existing project README, because that README typically contains the project's reason-to-exist that nobody else can recover.

| Existing file              | Action                                                                                          |
|----------------------------|-------------------------------------------------------------------------------------------------|
| `README.md` exists         | **Preserve** verbatim. The scaffolded Vite template README is discarded.                        |
| `README.md` missing        | Write a minimal user-facing template that names the project (from `package.json`) and explains how to consume it. NEVER write developer/Make/test docs here. |
| `CONTRIBUTING.md` exists   | **Preserve** verbatim — the user has likely already curated it.                                 |
| `CONTRIBUTING.md` missing  | Generate a fresh CONTRIBUTING.md covering: tech stack, getting started, Make target catalogue, `make fix ci` inner-loop, project structure, port allocation, e2e test pattern, GitHub Pages setup. |

### What CONTRIBUTING.md MUST contain

Everything that the "After Setup" section below describes — but as durable, in-repo developer documentation rather than transient skill output. Specifically:

- **Tech stack list** with version anchors (so a future contributor knows what's installed before reading code)
- **Getting started**: `bun install`, `make dev`, `make agentic-dev`, what each port is for
- **Make target catalogue**: discovered via `make help`, but also enumerated explicitly so the docs render cleanly on GitHub
- **The canonical inner-loop**: `make fix ci` — when to run it, what it gates, why warnings count
- **Strict no-warnings policy** explanation
- **Project layout** (annotated tree of `src/`, `e2e/`, `.github/workflows/`)
- **How to add shadcn components** — `bunx --bun shadcn@latest add <name>`
- **E2e test pattern**: link to / inline-quote the slug-taxonomy + coverage-matrix doc
- **GitHub Pages setup**: the one-time Settings → Pages → Source: GitHub Actions step

### What CONTRIBUTING.md MUST NOT contain

- The project's value proposition (that's README's job)
- "Why this project exists" / problem statement
- User-facing usage examples (CLI invocations to consume the project, not develop it)
- Anything that would also belong in a customer-facing landing page

## E2e pattern: slug taxonomy + coverage matrix

Mirrors the pattern in `claude-code-sessions/frontend/e2e/filters.spec.ts`. Every route in the site map is declared as `{ id, slug, name, path }`:

```ts
const SECTIONS = [
  { id: 0, slug: "home", name: "Home", path: "/" },
] as const;
```

A `COVERAGE_MATRIX` declares which permutations to test, and nested for-loops at the bottom of the spec generate one Playwright `test()` per entry. Each test produces three paired artifacts keyed by a deterministic slug:

```
e2e-screenshots/E01_DEFAULT-S00_HOME.png         # full-page screenshot
e2e-screenshots/E01_DEFAULT-S00_HOME.log         # console + page errors
e2e-screenshots/E01_DEFAULT-S00_HOME.network.json  # request timing for Gantt viz
```

To add a route to the smoke suite: append `{ id, slug, name, path }` to `SECTIONS`. To grow new axes (time ranges, viewport sizes, locales) when filters appear: copy the `ENGINES`/`SECTIONS` shape and weave them into the permutation loop. The `id` field pads to two digits so 10+ entries still sort correctly.

## After Setup

```bash
bun run dev          # Start development server (port 5173)
bun run build        # Build for production
bun run test         # Vitest unit tests (delegates to vitest, not bun test)
bun run test:e2e     # Playwright e2e tests
bun run lint         # Biome lint check
bun run format       # Biome format --write
bun run check        # Biome check --write (lint + format + organize imports)

# Add shadcn components
bunx --bun shadcn@latest add button card
```

**One-time GitHub Pages setup**: in repo Settings → Pages, set **Source: GitHub Actions**. The workflow's `deploy-pages` job will register the `github-pages` environment automatically on the first push to `main`.

**Important**: use `bun run test`, not `bun test`. The latter invokes bun's built-in test runner instead of Vitest.
