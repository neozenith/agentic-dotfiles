# Project Memory

Fullstack web app: Python (FastAPI) backend + React (Vite) frontend, sibling
`backend/` and `frontend/` directories under a top-level Makefile.

For language-specific details, see `backend/CLAUDE.md` and `frontend/CLAUDE.md`.

## Critical: the inner-loop is `make fix ci`

Before considering ANY task done, run:

```bash
make fix ci
```

- `make fix` — autofix all formatters and lint findings (both halves).
- `make ci` — strict gate: format-check + lint + typecheck + test + test-e2e.

If `make ci` fails, the work is not done. Fix the issues, then re-run.

## Project layout

```
.
├── Makefile               # top-level orchestrator; delegates via `make -C backend|frontend`
├── docker-compose.yml     # backend service for deploy-parity testing
├── backend/               # FastAPI + uvicorn + uv + ruff + mypy + pytest
│   ├── Dockerfile         # multi-stage: builder (uv) → slim runtime
│   ├── server/api/        # wire layer (FastAPI + Pydantic schemas)
│   └── server/core/       # pure logic — NO FastAPI imports
└── frontend/              # Vite + React + TS + Tailwind + shadcn + Biome + Vitest + Playwright
    ├── src/               # React app
    └── e2e/               # Playwright slug-taxonomy + coverage-matrix tests
```

## Ports

| Profile | Make target          | Backend | Frontend |
|---------|----------------------|---------|----------|
| Human   | `make dev`           | 8200    | 5173     |
| Agent   | `make agentic-dev`   | 8201    | 5174     |
| Docker  | `make docker-up`     | 8210    | (n/a)    |

When running as a coding agent, ALWAYS use `make agentic-dev` (5174 + 8201)
so a human can keep `make dev` (5173 + 8200) running in parallel without
collision. Both backend AND frontend ports split — not just the frontend.

## Strict policies (these gate `make ci`)

- **Warnings are errors** — frontend uses `biome ci` (not `biome lint`); backend uses `ruff check` + `ruff format --check`.
- **TypeScript strict family** — `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noPropertyAccessFromIndexSignature`.
- **Python `mypy --strict`** over `server` AND `tests`.
- **Test coverage ≥ 90%** — Vitest thresholds (lines/functions/branches/statements); pytest `--cov-fail-under=90`.
- **No mocks in Python tests** — use real dependencies, real test instances, real `TestClient` or `httpx.Client`. See `backend/CLAUDE.md` for the rule's full text.
- **Backend tests split** — `tests/unit/` (pure logic, coverage-load-bearing) vs `tests/api/` (HTTP integration via env-var-aware `client` fixture).

## Docker workflow

The backend ships with a multi-stage Dockerfile. Compose orchestrates a single
backend service for deploy-parity testing.

| Make target          | What it does                                                  |
|----------------------|---------------------------------------------------------------|
| `make docker-build`  | Build the backend image (`docker compose build`)              |
| `make docker-up`     | Start detached, wait for healthcheck (`docker compose up -d --wait`) |
| `make docker-down`   | Stop + remove containers + volumes                            |
| `make docker-logs`   | Tail logs                                                     |
| `make test-api-docker` | Run pytest against the dockerized backend (port 8210)       |
| `make test-e2e-docker` | Run Playwright with the Vite frontend pointed at port 8210  |

The `client` pytest fixture is env-var-aware: when `BACKEND_BASE_URL` is set
(as `make test-api-docker` does), the SAME test files in `tests/api/` run via
`httpx.Client(base_url=...)` against the running container. Otherwise they run
in-process via `TestClient(create_app())`. Same tests, two transports.

## Where new things go

- **New API route** → `backend/server/api/routes.py` + Pydantic models in `backend/server/api/schemas.py`. Real logic in `backend/server/core/`.
- **New domain logic** → `backend/server/core/` (NO FastAPI imports allowed). This is the surface the ≥90% coverage gate targets.
- **New shadcn component** → `bunx --bun --cwd frontend shadcn@latest add <name>`. Lands in `frontend/src/components/ui/`. Don't hand-edit.
- **New e2e route smoke** → append to `frontend/e2e/matrix.ts` `SECTIONS`. Done.
- **New backend dep** → `uv --directory backend add <pkg>`. Never `pip install`.
- **New frontend dep** → `bun add <pkg>` from `frontend/`. Never `npm install` / `yarn add` / `pnpm add`.

## Anti-patterns to avoid

- `cd backend && ...` in shell commands — use `uv --directory backend ...` or `make -C backend ...`. (See user's global `CLAUDE.md` rule.)
- Suppressing a Biome warning with `// biome-ignore` — fix the code, or scope an override in `frontend/biome.json`. The warning exists for a reason.
- Suppressing a ruff warning with `# noqa` — fix the code, or add a per-file-ignore in `backend/pyproject.toml`.
- Bypassing `--cov-fail-under=90` or Vitest thresholds — write the test instead.
- `useState<any>(...)` — never use `any`. Use `unknown` and narrow with a type guard.
- `document.getElementById("root")!` (non-null assertion) — Biome rejects it. Use an explicit null-check + throw.
- Mocking in Python tests (`unittest.mock`, `pytest-mock`, `@patch`) — see `backend/CLAUDE.md`. Mocks are forbidden, no exceptions.
- Adding a frontend test runner OTHER than Vitest — Vitest is the single test runner; bun's built-in `bun test` is NOT used (it runs `*.test.ts` in bun's dialect, not vitest's).

## Dev server collision avoidance

If `make dev` errors with "address already in use", run `make port-debug` to see
which of the 4 dev ports (5173, 5174, 8200, 8201) are occupied, then
`make port-clean` to free them. Both targets exist precisely so this never
becomes a 5-minute debugging tangent.
