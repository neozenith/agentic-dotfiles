# Contributing to frontend

Developer reference for working in this repository. End-user docs live in
[README.md](./README.md) — keep that file focused on the project's value
proposition.

## Tech stack

### Frontend (`frontend/`)
- **Vite** + **React 19** + **TypeScript** (strict family — incl.
  `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`)
- **Tailwind CSS v4** + **shadcn/ui**
- **Biome** — single tool for lint + format (`biome ci` enforces
  warnings-as-errors)
- **Vitest** with **>=90% coverage threshold**
- **Playwright** with the slug-taxonomy + coverage-matrix pattern
- **Bun** as runtime + package manager

### Backend (`backend/`)
- **FastAPI** + **uvicorn** with the `create_app()` factory pattern
- **Pydantic v2** request/response models
- **uv** for dependency + venv management
- **ruff** with strict rule selection (warnings-as-errors)
- **mypy** `--strict` over `server` AND `tests`
- **pytest** with `--cov-fail-under=90`; split into `tests/unit/` (pure logic)
  and `tests/api/` (TestClient integration)

## Getting started

```bash
make install         # uv sync (backend) + bun install (frontend)
make dev             # backend on 8200 + frontend on 5173 (human profile)
make agentic-dev     # backend on 8201 + frontend on 5174 (AI agent profile)
```

The two profiles let a human and an AI agent run dev servers in parallel
without colliding on either port.

## Make target catalogue

Run `make help` for the auto-discovered list. Common targets:

### Inner-loop (most-used)
| Target               | Purpose                                                  |
|----------------------|----------------------------------------------------------|
| `make dev`           | backend 8200 + frontend 5173 (human profile)             |
| `make agentic-dev`   | backend 8201 + frontend 5174 (AI agent profile)          |
| `make fix`           | autofix everything fixable (format + lint-fix, both halves) |
| `make ci`            | strict gate: format-check + lint + typecheck + test + test-e2e |

### Narrow inner-loops
| Target               | Purpose                                                  |
|----------------------|----------------------------------------------------------|
| `make test-py`       | backend pytest only                                      |
| `make test-ts`       | frontend vitest only                                     |
| `make typecheck-py`  | backend mypy only                                        |
| `make typecheck-ts`  | frontend tsc only                                        |
| `make test-e2e`      | Playwright e2e (auto-launches both halves via concurrently) |

### Docker (deploy-parity testing)
| Target                  | Purpose                                                              |
|-------------------------|----------------------------------------------------------------------|
| `make docker-build`     | build the backend image                                              |
| `make docker-up`        | start backend in Docker (detached, waits for healthcheck) on port 8210 |
| `make docker-down`      | stop and remove the Docker stack                                     |
| `make docker-logs`      | tail the docker compose logs                                         |
| `make test-api-docker`  | run pytest against the dockerized backend (BACKEND_BASE_URL=http://localhost:8210) |
| `make test-e2e-docker`  | Playwright with Vite frontend pointed at the dockerized backend       |

### Maintenance
| Target               | Purpose                                                  |
|----------------------|----------------------------------------------------------|
| `make port-debug`    | show which of the 5 dev/docker ports are in use          |
| `make port-clean`    | kill processes on all 5 dev/docker ports                 |
| `make clean`         | remove build artefacts, deps, test outputs              |

## Canonical inner-loop: `make fix ci`

Before committing, run **`make fix ci`**:

1. `make fix` — autoformats every file and applies all auto-fixable lint issues.
2. `make ci` — strict gate. Fails on warnings, format drift, type errors,
   broken builds, failing tests, or broken e2e routes.

If `fix` couldn't autofix something, `ci`'s `lint` step catches it.

## Strict policies

| Policy                          | Where enforced                                                                              |
|---------------------------------|---------------------------------------------------------------------------------------------|
| Warnings are errors (frontend)  | `biome ci .` (not `biome lint .`)                                                          |
| Warnings are errors (backend)   | `ruff check` over a broad rule selection + `ruff format --check`                            |
| TypeScript strict family        | `strict` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` + `noImplicitOverride` + `noPropertyAccessFromIndexSignature` |
| Python strict typing            | `mypy --strict` over `server` AND `tests`                                                   |
| Test coverage >= 90%            | Vitest `thresholds.lines/functions/branches/statements: 90`; pytest `--cov-fail-under=90`   |
| Unit / integration split (py)   | `tests/unit/` (pure logic) vs `tests/api/` (TestClient integration)                        |

## Project structure

```
frontend/
├── Makefile                       # top-level: delegates via `make -C backend|frontend`
├── docker-compose.yml             # backend service for deploy-parity testing
├── CLAUDE.md                      # agent memory: inner-loop, ports, Docker, anti-patterns
├── backend/
│   ├── Makefile                   # uv-driven leaf targets (incl. test-docker)
│   ├── Dockerfile                 # multi-stage: builder (uv) → slim runtime
│   ├── .dockerignore
│   ├── CLAUDE.md                  # backend-specific agent memory (no-mocks rule, etc.)
│   ├── pyproject.toml             # ruff, mypy, pytest config
│   ├── server/
│   │   ├── __main__.py            # argparse + uvicorn(factory=True)
│   │   ├── api/
│   │   │   ├── app.py             # create_app() factory
│   │   │   ├── routes.py
│   │   │   └── schemas.py         # Pydantic v2 models
│   │   └── core/                  # pure logic — NO FastAPI imports
│   └── tests/
│       ├── conftest.py            # env-var-aware `client` fixture (TestClient or httpx)
│       ├── unit/                  # pure-logic tests (>=90% coverage on `server.core`)
│       └── api/                   # integration tests via `client` fixture (both modes)
└── frontend/
    ├── Makefile                   # bun/biome/vitest/playwright leaf targets
    ├── CLAUDE.md                  # frontend-specific agent memory (e2e pattern, bun rule, etc.)
    ├── package.json               # `dev` + `agentic-dev` use `concurrently`
    ├── biome.json                 # warnings-as-errors via `biome ci`
    ├── vite.config.ts             # /api proxy, Vitest with coverage thresholds
    ├── playwright.config.ts       # webServer spawns BOTH halves (or frontend-only via env switch)
    ├── src/                       # React app
    └── e2e/
        ├── matrix.ts              # SECTIONS × VARIANTS axis arrays
        └── routes.spec.ts         # generated tests; .png/.log/.network.json artefacts
```

## Adding shadcn/ui components

```bash
bunx --bun --cwd frontend shadcn@latest add button card dialog
```

Components land in `frontend/src/components/ui/`. Don't hand-edit them — `shadcn add`
overwrites on update.

## E2e test pattern

The e2e suite uses a slug-taxonomy + coverage-matrix pattern. Every test
combination is declared in `frontend/e2e/matrix.ts`:

```ts
export const SECTIONS = [
  { id: 0, slug: "home", name: "Home", path: "/" },
] as const;
export const VARIANTS = [
  { id: 0, slug: "default", name: "Default" },
] as const;
```

Each generated test produces three paired artefacts keyed by a deterministic slug:

```
frontend/test-results/matrix/<slug>.png            # full-page screenshot
frontend/test-results/matrix/<slug>.log            # console + page errors (filtered)
frontend/test-results/matrix/<slug>.network.json   # request timings (Gantt-ready)
```

To add a route: append to `SECTIONS`. To grow a new axis: copy `VARIANTS`.

## Docker workflow (deploy-parity testing)

The backend ships with a multi-stage `Dockerfile` and a top-level `docker-compose.yml`.
Container listens on 8000; host port is `DOCKER_API_PORT` (default 8210), separate
from `make dev` (8200) and `make agentic-dev` (8201) so all three can run side by side.

```bash
make docker-build        # build the backend image
make docker-up           # start (detached, waits for /api/health)
make test-api-docker     # run tests/api/ against http://localhost:8210
make test-e2e-docker     # Playwright with the Vite frontend pointed at the container
make docker-down         # stop + remove
```

The `client` pytest fixture in `tests/api/conftest.py` is env-var-aware: when
`BACKEND_BASE_URL` is set (as `make test-api-docker` does), the SAME `tests/api/`
files run via `httpx.Client(base_url=...)` against the running container. Otherwise
they run in-process via `TestClient(create_app())`. **Same tests, two transports.**

## Agent memory files (`CLAUDE.md`)

Three `CLAUDE.md` files give a coding agent the durable maintenance + testing
context:

- `CLAUDE.md` (project root) — the inner-loop, ports, strict policies, Docker workflow, anti-patterns.
- `backend/CLAUDE.md` — Python conventions, `uv` rules, tests/unit ↔ tests/api split, **the no-mocks rule**.
- `frontend/CLAUDE.md` — bun conventions, Biome strictness, shadcn pattern, slug-taxonomy e2e pattern.

Treat them as living docs: when a new convention emerges (e.g. a per-file ruff
ignore, a new strict gate), update the relevant `CLAUDE.md` so the next agent
session inherits the lesson.
