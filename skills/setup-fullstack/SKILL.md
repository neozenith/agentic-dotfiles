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
- **Cloud-agnostic object-storage layer** — `StorageBackend` Protocol with three real implementations (memory / local-filesystem / S3-compatible). MinIO covers local S3, AWS S3 covers the same code path against the real cloud.
- **Postgres-backup-to-object-storage feature** — `pg_dump -Fc` periodic + on-shutdown, `pg_restore` on cold start when the DB is empty. Off-by-default; opt in via `STORAGE_BACKEND` env var. Designed for ephemeral DB sidecars (e.g. Cloud Run scale-to-zero) where data must survive cold starts.

## Usage

**Default behavior: scaffold into the current working directory of the session that invoked the skill.** Do not ask the user to confirm the target — the working tree is recoverable via `git reset --hard` (or by deleting the subdir, if one was given). Only deviate from CWD when the user explicitly names a target directory in their prompt.

```bash
# Default — scaffold into the current working directory (no argument required)
bun .claude/skills/setup-fullstack/scripts/setup-fullstack.ts

# Only when the user explicitly asks for a named subdirectory
bun .claude/skills/setup-fullstack/scripts/setup-fullstack.ts my-fullstack-app
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

## Persistence + backup matrix

The scaffold ships with a cloud-agnostic object-storage layer plus an optional
Postgres backup feature. The matrix is **selectable at runtime** via env vars
and Make vars — no scaffold-time choice required. Same code, all options.

### Storage backend axis (env: `STORAGE_BACKEND`)

| Value      | What it stores                                | When to use                                        |
|------------|-----------------------------------------------|----------------------------------------------------|
| *(unset)*  | nothing — backup feature is OFF               | Default. Local dev when you don't care about backup. |
| `memory`   | dict in-process                               | Unit tests; quick smoke checks. Lost on restart.    |
| `local`    | files under a directory                       | Local dev with persistence; cheap CI tier.         |
| `s3`       | AWS S3 / MinIO / any S3-API service           | Production + integration tests via MinIO.          |

`s3` covers both AWS and MinIO: same backend class, switched via `S3_ENDPOINT_URL`
(`http://minio:9000` for local MinIO, omit for AWS) plus `S3_ADDRESSING_STYLE=path`
for MinIO. Adding GCS / Azure later is a single new file implementing the same
`StorageBackend` Protocol — no factory, env, or test changes beyond one entry.

### Database backend axis (Make var: `DATABASE_BACKEND`)

| Value      | Compose overlay                  | DSN shape                                    |
|------------|----------------------------------|----------------------------------------------|
| `sqlite`   | `docker-compose.sqlite.yml`      | `sqlite+aiosqlite:///...`                    |
| `postgres` | `docker-compose.postgres.yml`    | `postgresql+asyncpg://...`                   |

### Backup feature axis (Make var: `BACKUP_BACKEND`)

| Value   | Compose overlay              | Effect                                          |
|---------|------------------------------|-------------------------------------------------|
| `none`  | (no overlay)                 | Default. Backup feature inert.                  |
| `minio` | `docker-compose.minio.yml`   | Adds MinIO + bucket-init sidecar; backend wired |

### How the matrix combines

```bash
# Plain SQLite, no backup (default — fastest local dev)
make docker-up

# Postgres, no backup (testing the postgres data path)
DATABASE_BACKEND=postgres make docker-up

# Postgres + MinIO + scheduler enabled (full backup roundtrip locally)
make docker-up-postgres-minio

# Postgres + AWS S3 (real cloud backups; no MinIO)
DATABASE_BACKEND=postgres \
STORAGE_BACKEND=s3 STORAGE_BUCKET=<your-bucket> \
S3_REGION=<region> \
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
make docker-up

# End-to-end backup/restore integration test (boots stack, runs, tears down)
make test-backup-roundtrip
```

### Test matrix

The unit tests (`tests/unit/test_storage_contract.py`) parametrize the same
8-assertion contract across `memory` and `local` backends — both real
implementations of the protocol. The S3 backend honors the same contract; it's
exercised by the dockerized `test-backup-roundtrip` integration test against
MinIO. Adding a new backend means adding ONE line to the parametrize map.

### Configuration knobs

| Env var                    | Default      | Notes                                              |
|----------------------------|--------------|----------------------------------------------------|
| `STORAGE_BACKEND`          | (unset)      | `s3` / `local` / `memory` / `""` (disabled)        |
| `STORAGE_BUCKET`           | —            | Required when `STORAGE_BACKEND=s3`                 |
| `STORAGE_LOCAL_PATH`       | tempfile     | Optional path for `local`; falls back via mkdtemp  |
| `S3_ENDPOINT_URL`          | (AWS native) | Set for MinIO / S3-compatible non-AWS              |
| `S3_REGION`                | `us-east-1`  | MinIO ignores it; AWS requires it                  |
| `S3_ADDRESSING_STYLE`      | `auto`       | `path` for MinIO; `auto` works for AWS             |
| `BACKUP_INTERVAL_SECONDS`  | `900`        | 15-minute periodic dump cadence                    |
| `BACKUP_KEY_PREFIX`        | `backups/`   | Object-key prefix; `latest.dump` is the cold-start pointer |
| `BACKUP_ENABLED`           | (auto)       | Force-disable with `0`/`false`/`no`/`off`          |

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
