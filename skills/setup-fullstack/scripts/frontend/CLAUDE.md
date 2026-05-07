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
- **Vitest** with coverage thresholds at 90% for lines / functions / branches / statements (scoped to `src/lib/**`; UI components are covered by Playwright e2e instead).

## Architecture

- `src/` — React app code.
  - `src/index.css` — design-token entry point. Holds `@import "tailwindcss"`, `@custom-variant dark`, the `@theme inline` mapping (Tailwind utilities → CSS vars), and the `:root` / `.dark` palettes. **Excluded from Biome** because Tailwind v4 at-rules (`@custom-variant`, `@theme inline`) aren't yet recognised by Biome's CSS parser.
  - `src/main.tsx` — React root mount with explicit null-check (no non-null assertion — Biome rejects it).
  - `src/App.tsx` — wraps the router in `<ThemeProvider>` so the theme is available everywhere.
  - `src/components/ThemeProvider.tsx` — context that reads `localStorage["ui-theme"]` (with system-pref fallback) and toggles `<html class="light">` / `<html class="dark">`. The class swap drives the CSS-var override; nothing in components branches on theme.
  - `src/components/ThemeToggle.tsx` — Sun/Moon icon button (lucide-react + shadcn `Button`) that flips the theme.
  - `src/components/Layout.tsx` — collapsible sidebar + header. Uses `buttonVariants(...)` to style `<Link>` elements (the shadcn Button's `asChild` prop isn't reliable across versions).
  - `src/components/ui/` — shadcn-generated components (`button.tsx`, `card.tsx`). **Do not hand-edit** — `shadcn add` overwrites them on update.
  - `src/lib/utils.ts` — `cn()` helper from shadcn (do NOT delete; everything in `src/components/ui/` imports it).
  - `src/lib/api.ts` — single fetch boundary; always uses relative `/api/...` paths so the Vite proxy (dev) and FastAPI static mount (Docker) both work.
  - `src/pages/` — route components (HomePage, ItemsPage, NotesPage). Each renders shadcn `Card`s populated from `lib/api.ts`.
- `e2e/` — Playwright tests. See "E2e pattern" below.
- `vite.config.ts` — also configures Vitest (`test:` block). Coverage thresholds + `setupFiles` live here.
- `playwright.config.ts` — webServer block spawns BOTH backend and frontend via `concurrently` by default. The `PLAYWRIGHT_FRONTEND_ONLY=1` env var switches to frontend-only (used by `make test-e2e-docker`, where the backend is in Docker).

## Theming: design tokens, not branching

The theme system is purely CSS-driven:

1. `index.css` defines color/radius variables (e.g. `--background`, `--card-foreground`) for both `:root` (light) and `.dark` (dark).
2. The `@theme inline` block tells Tailwind v4 to resolve utilities like `bg-background`, `text-card-foreground`, `border-border` from those variables.
3. `ThemeProvider` toggles `<html>`'s class. CSS cascade flips every component's colors instantly — no React re-render driven by theme.

Consequence: **components never read `useTheme()` to decide colors**. Use Tailwind's semantic utilities (`bg-card`, `text-muted-foreground`, etc.) and the right thing happens in both themes. `useTheme()` is only for showing the right toggle icon (Moon vs Sun).

To add a new colorable surface, add tokens to BOTH `:root` and `.dark` in `index.css`, then map them in `@theme inline`.

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
  { id: 0, slug: "home",  name: "Home",  path: "/" },
  { id: 1, slug: "items", name: "Items", path: "/items" },
  { id: 2, slug: "notes", name: "Notes", path: "/notes" },
] as const;

export const VARIANTS = [
  { id: 0, slug: "light", name: "Light", theme: "light" },
  { id: 1, slug: "dark",  name: "Dark",  theme: "dark"  },
] as const;
```

`MATRIX = SECTIONS.flatMap(s => VARIANTS.map(v => ...))` generates one Playwright
test per (section × variant) entry. Currently 3 × 2 = 6 generated tests. Each:

1. Uses `page.addInitScript` to seed `localStorage["ui-theme"]` BEFORE the page boots — so the ThemeProvider hydrates in the requested theme on first paint (no flash of wrong theme).
2. Navigates to `section.path`.
3. Waits for React mount + network settle.
4. Asserts `<html>` has the expected theme class (regression guard on the provider).
5. Asserts no (filtered) console errors.
6. Captures three artifacts to `test-results/matrix/`: `<slug>.png`, `<slug>.log`, `<slug>.network.json`.

To smoke-test a new route: append to `SECTIONS`. Done — every entry
automatically gets a generated test in BOTH themes.

To grow a new axis (locales, viewport sizes, auth states): copy the `VARIANTS`
shape and weave it into the `MATRIX` flatMap. The slug builder in `matrix.ts`
already pads ids to 2 digits, so 10+ entries per axis still sort lexicographically.

The console-error filter tolerates `[vite]` chatter, React DevTools nudge,
favicon misses, and `503`s for optional data. Anything else fails the test.

## API access from React code

- `vite.config.ts` proxies `/api/*` to the backend. The proxy target reads `API_PORT` from the environment, so the SAME proxy code routes `/api/*` to whichever port the launching `make` target supplied (8200 / 8201 / 8210).
- **Always use relative `/api/...` paths** in `fetch()` calls. Never hardcode `localhost:8200` or `127.0.0.1:8200`.
- All fetch goes through `src/lib/api.ts` — single boundary, single error-handling surface.
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
- Hardcoding colors (`bg-white`, `text-black`, `bg-gray-900`) — use semantic Tailwind tokens (`bg-background`, `text-foreground`, `bg-card`) so dark mode flips automatically.
- Branching on theme in component code (`if (theme === "dark") ...`) — let CSS variables do the work; reach for `useTheme()` only for the toggle icon.
- Using `Button asChild` — that prop isn't reliable across shadcn versions. Use `buttonVariants(...)` to style a `<Link>` or other element directly.
- Adding ESLint or Prettier — Biome is the single tool. Two formatters fight on the same files.
- Adding `npm install` to README/CONTRIBUTING — bun is the package manager. The skill explicitly removes the scaffold's ESLint deps and replaces them with Biome.
- `bun test` (without `run`) — invokes bun's built-in runner, not vitest. Use `bun run test`.
