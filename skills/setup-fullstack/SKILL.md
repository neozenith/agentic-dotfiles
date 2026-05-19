---
name: setup-fullstack
description: Automated setup for a fullstack web app — Python (FastAPI + uv) backend + React/Vite/TypeScript/Tailwind/shadcn/Biome/Vitest/Playwright frontend, sibling `backend/` and `frontend/` directories under a top-level Makefile that delegates per-language targets (`format-ts`/`format-py`, `lint-ts`/`lint-py`, `typecheck-ts`/`typecheck-py`, `test-ts`/`test-py`) and rolls them up into `format`, `lint`, `typecheck`, `test`, with `make fix ci` as the canonical inner-loop. Use when scaffolding a new fullstack web application with a Python API backend and a React frontend, initializing the standard `backend/` + `frontend/` project layout, or asking for "Python + React fullstack".
user-invocable: true
metadata:
  version: "0.1.0"
  short-description: Scaffold a FastAPI + Vite/React fullstack app
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
- **Cloud-agnostic object-storage layer** — `StorageBackend` Protocol with three real implementations (memory / local-filesystem / S3-compatible). MinIO covers local S3, AWS S3 covers the same code path against the real cloud.
- **Postgres-backup-to-object-storage feature** — `pg_dump -Fc` periodic + on-shutdown, `pg_restore` on cold start when the DB is empty. Off-by-default; opt in via `STORAGE_BACKEND` env var. Designed for ephemeral DB sidecars (e.g. Cloud Run scale-to-zero) where data must survive cold starts.

## Usage

**Default behavior: scaffold into the current working directory of the session that invoked the skill.** Do not ask the user to confirm the target — the working tree is recoverable via `git reset --hard` if the directory is under version control (or by deleting added files/dirs otherwise). Only deviate from CWD when the user explicitly names a target directory in their prompt.

The script must run under `bun` — it uses `Bun.$` (typed tagged-template shell) and top-level await. **Prerequisites:** `bun`, `uv`, and `make` must be available on `PATH`; the script performs a preflight check and exits with a clear message if any are missing.

```bash
# Canonical — scaffold into the current working directory with the default variation
bun .claude/skills/setup-fullstack/scripts/setup-fullstack.ts

# Use a specific runtime variation (database + storage + backup preset)
bun .claude/skills/setup-fullstack/scripts/setup-fullstack.ts sqlite-persisted

# List all available variations
bun .claude/skills/setup-fullstack/scripts/setup-fullstack.ts list-variations

# Help
bun .claude/skills/setup-fullstack/scripts/setup-fullstack.ts --help
```

**Variation** is an optional first positional argument selecting a runtime preset (database backend + storage backend + backup overlay). The chosen preset's env-var bundle is written to `.env` so `make docker-up` / `make ci` pick it up by default. Omit it to use the default variation (`sqlite-memory`). Run `list-variations` to see every option.

**`--no-fix`** skips the `make fix` autofix pass; **`--no-verify`** skips the typecheck + tests verification step. Both flags are escape hatches for iterating quickly — re-run without them before committing.

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
│   │   │   ├── app.py             # create_app() factory + backup lifespan wiring
│   │   │   ├── admin.py           # /api/admin/backup{,/status} + /api/admin/restore
│   │   │   ├── app_state.py       # BackupContext attached to app.state
│   │   │   ├── routes.py          # /api/health, /api/echo, /api/items, /api/notes
│   │   │   └── schemas.py         # Pydantic v2 models
│   │   ├── core/__init__.py       # pure logic, NO FastAPI imports
│   │   ├── storage/               # StorageBackend Protocol + memory/local/s3 impls
│   │   └── backup/                # pg_dump/pg_restore + scheduler + cold-start restore
│   └── tests/
│       ├── conftest.py            # TestClient fixture
│       ├── unit/                  # pure-logic + storage-contract tests
│       └── api/                   # TestClient integration + backup-roundtrip (skip-if-no-stack)
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

Identical in spirit to `vite-react-setup`'s pattern, but the webServer block in `playwright.config.ts` spawns BOTH halves via `concurrently` so the e2e suite exercises the real backend, not a mock. Each test produces three artifacts: a `.png` screenshot, a `.log` of console/page errors, and a `.network.json` with per-request timings.

See `resources/DESIGN-RATIONALE.md` for the matrix shape, artifact format, and how to extend axes.

## Persistence + backup matrix

The scaffold ships a cloud-agnostic `StorageBackend` Protocol (memory / local / S3-compatible) and an optional Postgres backup feature (off by default; opt in via `STORAGE_BACKEND`). The entire matrix — database × storage × backup overlay — is selectable at runtime with no scaffold-time choice required.

See `resources/PERSISTENCE-MATRIX.md` for the full axis tables, compose-overlay combinations, and configuration knobs.

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

## Design rationale

For the reasoning behind toolchain and architecture choices (Makefile structure, `concurrently`, `uvicorn(factory=True)`, `server.core` isolation, port split, Pydantic v2, `hatchling`, etc.) see `resources/DESIGN-RATIONALE.md`.
