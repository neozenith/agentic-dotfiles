---
name: setup-fullstack
description: Automated setup for a fullstack web app — Python (FastAPI + uv) backend + React/Vite/TypeScript/Tailwind/shadcn/Biome/Vitest/Playwright frontend, sibling `backend/` and `frontend/` directories under a top-level Makefile that delegates per-language targets (`format-ts`/`format-py`, `lint-ts`/`lint-py`, `typecheck-ts`/`typecheck-py`, `test-ts`/`test-py`) and rolls them up into `format`, `lint`, `typecheck`, `test`, with `make fix ci` as the canonical inner-loop. Use when scaffolding a new fullstack web application with a Python API backend and a React frontend, initializing the standard `backend/` + `frontend/` project layout, or asking for "Python + React fullstack".
user-invocable: true
---

# Setup Fullstack

Automatically scaffolds a complete fullstack web application — a Python FastAPI backend served alongside a React/Vite frontend — under a top-level Makefile that orchestrates both halves.

This skill is the fullstack extension of `vite-react-setup`. The frontend half is a whole copy of that skill's output (Vite + React 19 + TypeScript + Tailwind v4 + shadcn/ui + Biome + Vitest + Playwright + Bun); the backend half adds FastAPI + uvicorn + uv + ruff + mypy + pytest. The two halves talk over Vite's `/api` dev proxy.

## What you get

- **Top-level Makefile** with per-language rollup targets and the canonical `make fix ci` inner-loop
- **`backend/`** subproject — FastAPI app factory + pure-logic core, ruff (warnings-are-errors), mypy strict, pytest with ≥90% coverage gate, `tests/unit/` vs `tests/api/` split
- **`frontend/`** subproject — Vite + React 19 + TypeScript strict family (incl. `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`) + Tailwind v4 + shadcn/ui + Biome (warnings-as-errors via `biome ci`) + Vitest with ≥90% coverage threshold + Playwright e2e
- **Concurrently**-driven dev — backend + frontend launch from a single `package.json` script with prefixed/colored logs
- **Dual port profiles** — human (`make dev` → 5173 + 8200) and agent (`make agentic-dev` → 5174 + 8201) so a coding agent and a human can run dev stacks simultaneously without colliding
- **Slug-taxonomy + coverage-matrix e2e** — Playwright spec generates one test per route × variant, asserts no browser console errors, takes screenshots, captures network event timings (start offsets + durations) into `.network.json` for Gantt analysis
- **GitHub Actions CI** — `bun install --frozen-lockfile` + `uv sync --frozen` + `make ci` + Playwright browser cache + e2e artifact upload on failure

## Usage

**Default behavior: scaffold into the current working directory of the session that invoked the skill.** Do not ask the user to confirm the target — the working tree is recoverable via `git reset --hard` (or by deleting the subdir, if one was given). Only deviate from CWD when the user explicitly names a target directory in their prompt.

```bash
# Default — scaffold into the current working directory (no argument required)
bun .claude/skills/setup-fullstack/setup-fullstack.ts

# Only when the user explicitly asks for a named subdirectory
bun .claude/skills/setup-fullstack/setup-fullstack.ts my-fullstack-app
```

The script must run under `bun` — it uses `Bun.$` (typed tagged-template shell) and top-level await.

## Project layout produced

```
project-root/
├── Makefile                       # top-level: delegates via `make -C backend|frontend`
├── README.md                      # users: value prop, how to consume
├── CONTRIBUTING.md                # devs: Make targets, ports, e2e pattern
├── .gitignore
├── .github/workflows/build.yml    # bun + uv + make ci
├── backend/
│   ├── Makefile                   # uv-driven: install/dev/format/lint/typecheck/test
│   ├── pyproject.toml             # ruff strict, mypy strict, pytest ≥90% coverage
│   ├── server/
│   │   ├── __main__.py            # argparse + uvicorn(factory=True)
│   │   ├── api/
│   │   │   ├── app.py             # create_app() factory
│   │   │   ├── routes.py          # /api/health, /api/echo
│   │   │   └── schemas.py         # Pydantic v2 models
│   │   └── core/__init__.py       # pure logic, NO FastAPI imports
│   └── tests/
│       ├── conftest.py            # TestClient fixture
│       ├── unit/                  # pure-logic tests (the coverage-load-bearing tier)
│       └── api/                   # TestClient integration tests
└── frontend/
    ├── Makefile                   # bun/biome/vitest/playwright targets
    ├── package.json               # `dev` and `agentic-dev` use `concurrently`
    ├── biome.json                 # strict (`biome ci`)
    ├── vite.config.ts             # /api proxy, Vitest with ≥90% coverage
    ├── playwright.config.ts       # webServer spawns BOTH halves via concurrently
    ├── src/                       # React app shell
    └── e2e/
        ├── matrix.ts              # SECTIONS × VARIANTS axis arrays
        └── routes.spec.ts         # generated tests; .png/.log/.network.json artifacts
```

## Canonical inner-loop: `make fix ci`

The full quality DAG is encoded in the top-level Makefile:

| Top-level target | What it runs                                                                                              |
|------------------|-----------------------------------------------------------------------------------------------------------|
| `make fix`       | `format` then `lint-fix` — both halves, both languages, all auto-fixable findings.                        |
| `make ci`        | `format-check` + `lint` + `typecheck` + `test` + `test-e2e` — strict gate, both halves, no warnings allowed. |

Per-language rollup targets exist for narrow inner-loops: `make test-py` (just backend), `make lint-ts` (just frontend lint), etc. Top-level targets fan out to both halves; per-language targets `make -C` into one subdir.

## Strict policies

| Policy                          | Where enforced                                                                              |
|---------------------------------|---------------------------------------------------------------------------------------------|
| Warnings are errors (frontend)  | `biome ci .` (not `biome lint .`) — fails on warnings, info, format drift                   |
| Warnings are errors (backend)   | `ruff check` with `select = ["E", "W", "F", "I", "B", "C4", "UP", "RUF", "SIM", "ARG", "N", "S", "PT"]` and `ruff format --check` |
| TypeScript strict family        | `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noPropertyAccessFromIndexSignature` |
| Python strict typing            | `mypy --strict` over `server` and `tests`                                                   |
| Test coverage ≥ 90%             | Vitest `thresholds.lines/functions/branches/statements: 90`; pytest `--cov-fail-under=90`   |
| Unit / integration split (py)   | `tests/unit/` (pure-logic, coverage-load-bearing) vs `tests/api/` (TestClient integration)  |

## Ports

| Profile      | Make target          | Backend (uvicorn) | Frontend (Vite) |
|--------------|----------------------|-------------------|-----------------|
| Human        | `make dev`           | `8200`            | `5173`          |
| Agent        | `make agentic-dev`   | `8201`            | `5174`          |

**Both ports split** — not just the frontend. A shared backend at `8200` would mean the human and the agent compete for the same uvicorn process; reload semantics and dev DB state would race. Splitting both lets two concurrent dev sessions iterate independently.

The frontend's Vite proxy reads `API_PORT` from the environment, so the same proxy code routes `/api/*` to whichever port the launching `make` target supplied.

## E2e pattern: slug-taxonomy + coverage-matrix

Identical in spirit to `vite-react-setup`'s pattern, but the webServer block in `playwright.config.ts` spawns BOTH halves via `concurrently` so the e2e suite exercises the real backend, not a mock.

```ts
// e2e/matrix.ts
export const SECTIONS = ["home"] as const;
export const VARIANTS = ["default"] as const;
export const MATRIX = SECTIONS.flatMap((s) =>
  VARIANTS.map((v) => ({ id: `${s}__${v}`, path: `/${s === "home" ? "" : s}` })),
);
```

Each generated test produces three paired artifacts keyed by a deterministic slug:

```
test-results/matrix/<slug>.png            # full-page screenshot
test-results/matrix/<slug>.log            # console + page errors (filtered)
test-results/matrix/<slug>.network.json   # request timings (start_offset_ms, duration_ms)
```

Console-error filter: tolerates `[vite]` chatter, React DevTools nudge, favicon misses, and `503`s for optional data; everything else fails the test.

To add a route: append to `SECTIONS`. To grow a new axis (locales, viewport sizes, auth states): copy the `SECTIONS`/`VARIANTS` shape and weave it into the `MATRIX` flatMap.

## Documentation split: README.md + CONTRIBUTING.md

Same rule as `vite-react-setup`: `README.md` is the user-facing landing page (project overview, value proposition, how to consume); `CONTRIBUTING.md` is the developer-facing on-ramp (Make targets, ports, e2e pattern, dev/build/test workflow). They MUST NOT overlap.

Preservation rules:

| Existing file              | Action                                                                              |
|----------------------------|-------------------------------------------------------------------------------------|
| `README.md` exists         | **Preserve** verbatim. The Vite scaffold's generic README is discarded.             |
| `README.md` missing        | Write a minimal user-facing template that names the project and describes consumption. NEVER write developer/Make/test docs here. |
| `CONTRIBUTING.md` exists   | **Preserve** verbatim — the user has likely already curated it.                     |
| `CONTRIBUTING.md` missing  | Generate a fresh CONTRIBUTING.md covering the tech stack, Make catalogue, `make fix ci`, port allocation, and e2e pattern. |

## After Setup

```bash
# Inner-loop (do this before committing):
make fix ci          # autofix everything, then strict gate

# Dev:
make dev             # backend on 8200 + frontend on 5173 (human profile)
make agentic-dev     # backend on 8201 + frontend on 5174 (agent profile)

# Per-half iteration:
make test-py         # backend pytest only
make test-ts         # frontend vitest only
make typecheck-py    # mypy only
make typecheck-ts    # tsc only
make test-e2e        # Playwright (auto-launches both halves via concurrently)

# Discover everything:
make help
```

## Why these specific choices

- **Top-level + per-language sub-Makefiles (not single flat Makefile)** — each subproject is independently usable for tight inner-loops; the top-level is pure orchestration. Avoids a 200-line monolith and keeps blast radius small when adding new targets.
- **`concurrently` in package.json (not `make -j`)** — `concurrently -k` (kill-others) gives prefixed/colored logs and a single Ctrl-C tears down both processes cleanly. `make -j` with two long-running processes interleaves output and orphans children on interrupt.
- **`uvicorn(factory=True)` with `create_app()`** — tests can build isolated `FastAPI` instances per fixture without sharing module-level state.
- **`server.core` with no FastAPI imports** — the boundary that the ≥90% coverage gate is meant to load on. Pure functions are easy to test exhaustively; framework glue isn't.
- **`tests/unit` vs `tests/api` split** — lets the coverage gate apply primarily to deterministic logic while API tests verify wiring without inflating the denominator.
- **Both backend AND frontend ports split across human/agent profiles** — see *Ports* above.
- **Pydantic v2 + `response_model` everywhere** — schemas ARE the contract; OpenAPI generation is free; mypy `pydantic.mypy` plugin gives strict static checking on top.
- **`hatchling` build backend** — modern, simple, default for pyproject-only Python packages. No `setup.py`.
