# Frontend Memory

Vite + React 19 + TypeScript + Tailwind v4 + shadcn/ui + Biome + Vitest + Playwright. See project-root `CLAUDE.md` for cross-cutting context.

## Running things

- **NEVER** use `npm` / `npx` / `yarn` / `pnpm`. Always `bun` / `bunx --bun` / `bun add`.
- `bun create vite` and `bun install` only — do not introduce a second package manager.
- From project root: `make -C frontend dev` or `make dev` (which invokes the concurrently script and spawns the backend too).
- `bun run dev` runs concurrently — both backend (uvicorn) AND frontend (Vite). Use `bun run dev:frontend-only` to skip the backend (e.g., when the backend is dockerized).

## Strict gates

- **Biome** with `biome ci` — warnings are errors, format drift fails. The same command runs in CI, so there is no "passes locally / fails in CI" surprise.
- **TypeScript strict family** — `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noPropertyAccessFromIndexSignature`.
- **Vitest** with coverage thresholds at 90% for lines / functions / branches / statements.

## Architecture

- `src/` — React app code.
  - `src/lib/utils.ts` — `cn()` helper from shadcn (do NOT delete; everything in `src/components/ui/` imports it).
  - `src/components/ui/` — shadcn-generated components. **Do not hand-edit** — `shadcn add` overwrites them on update.
  - `src/main.tsx` — React root mount with explicit null-check (no non-null assertion — Biome rejects it).
- `e2e/` — Playwright tests. See "E2e pattern" below.
- `vite.config.ts` — also configures Vitest (`test:` block). Coverage thresholds + `setupFiles` live here.
- `playwright.config.ts` — webServer block spawns BOTH backend and frontend via `concurrently` by default. The `PLAYWRIGHT_FRONTEND_ONLY=1` env var switches to frontend-only (used by `make test-e2e-docker`, where the backend is in Docker).

## Adding a UI component (shadcn)

```bash
bunx --bun --cwd frontend shadcn@latest add button card dialog
```

Components land in `src/components/ui/`. If a Biome rule trips on shadcn-generated
code, scope a path override in `biome.json`:

```json
"overrides": [
  {
    "includes": ["src/components/ui/**"],
    "linter": { "rules": { "...": "off" } }
  }
]
```

Do NOT hand-edit the generated files; the next `shadcn add` overwrites them.

## E2e pattern: slug-taxonomy + coverage-matrix

`e2e/matrix.ts` declares two axis arrays:

```ts
export const SECTIONS = [
  { id: 0, slug: "home", name: "Home", path: "/" },
] as const;
export const VARIANTS = [
  { id: 0, slug: "default", name: "Default" },
] as const;
```

`MATRIX = SECTIONS.flatMap(s => VARIANTS.map(v => ...))` generates one Playwright
test per (section × variant) entry. Each generated test:

1. Navigates to `section.path`.
2. Waits for React mount + network settle.
3. Asserts no (filtered) console errors.
4. Captures three artifacts to `test-results/matrix/`: `<slug>.png`, `<slug>.log`, `<slug>.network.json`.

To smoke-test a new route: append to `SECTIONS`. Done — every entry
automatically gets a generated test.

To grow a new axis (locales, viewport sizes, auth states): copy the `VARIANTS`
shape and weave it into the `MATRIX` flatMap. The slug builder in `matrix.ts`
already pads ids to 2 digits, so 10+ entries per axis still sort lexicographically.

The console-error filter tolerates `[vite]` chatter, React DevTools nudge,
favicon misses, and `503`s for optional data. Anything else fails the test.

## API access from React code

- `vite.config.ts` proxies `/api/*` to the backend. The proxy target reads `API_PORT` from the environment, so the SAME proxy code routes `/api/*` to whichever port the launching `make` target supplied (8200 / 8201 / 8210).
- **Always use relative `/api/...` paths** in `fetch()` calls. Never hardcode `localhost:8200` or `127.0.0.1:8200`.
- During docker testing (`make test-e2e-docker`), `API_PORT=8210` is set and the Vite proxy routes to the dockerized backend automatically.

## Path aliases

`@/*` resolves to `./src/*`. Both `tsconfig.json` AND `tsconfig.app.json` declare it (Vite's react-ts template uses TypeScript project references, so the alias has to live in both files for tooling to pick it up consistently).

```ts
// ✅ CORRECT
import { cn } from "@/lib/utils";

// ❌ AVOID — relative imports past one directory
import { cn } from "../../../lib/utils";
```

## Running tests

- `bun run test` (or `make test-ts`) — Vitest unit tests with coverage thresholds.
- `bun run test:ui` — Vitest UI dashboard (interactive).
- `bun run test:e2e` (or `make test-e2e`) — Playwright; webServer block spawns both halves.
- `make test-e2e-docker` — Playwright with `PLAYWRIGHT_FRONTEND_ONLY=1` and `API_PORT=8210`; expects the backend to already be running in Docker.

**Use `bun run test`, NOT `bun test`.** The latter invokes Bun's built-in
test runner, which finds zero `*.test.ts` files in vitest's dialect and
silently passes. We want vitest's runner — `bun run test` is the canonical form.

## Anti-patterns

- `useState<any>(...)` — never use `any`. Use `unknown` and narrow with a type guard.
- `document.getElementById("root")!` (non-null assertion) — Biome rejects it. Use an explicit null-check + throw. See `src/main.tsx` for the canonical form.
- Importing past one directory (`../../../`) — use the `@/*` alias.
- Hand-editing `src/components/ui/*` — use `bunx --bun shadcn@latest add` to regenerate.
- Adding ESLint or Prettier — Biome is the single tool. Two formatters fight on the same files.
- Adding `npm install` to README/CONTRIBUTING — bun is the package manager. The skill explicitly removes the scaffold's ESLint deps and replaces them with Biome.
- `bun test` (without `run`) — invokes bun's built-in runner, not vitest. Use `bun run test`.
