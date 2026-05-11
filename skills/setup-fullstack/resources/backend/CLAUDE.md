# Backend Memory

FastAPI + uvicorn + uv server. See project-root `CLAUDE.md` for cross-cutting context (`make fix ci`, ports, strict policies).

## Running things

- **NEVER** invoke `python` / `pip` directly. Always `uv run ...` or `uv add ...`.
- From project root: `uv --directory backend run python -m server` or `make -C backend dev`.
- `python -m server --reload` invokes `server/__main__.py`, which calls `uvicorn.run(..., factory=True)` — `create_app()` is built fresh per worker.

## Architecture

The backend has two tiers, distinguished by who owns the code. See
`../CONTEXT.md` for the canonical definitions of these terms.

### Framework-managed code

Parts the scaffold ships with and forks generally inherit unchanged.

- `server/api/` — FastAPI wire layer (routes, schemas, app factory).
  - `app.py` — `create_app()` factory. Tests build isolated app instances per fixture.
  - `routes.py` — endpoint handlers. Translate Pydantic ↔ core function calls only; NO business logic here.
  - `schemas.py` — Pydantic v2 request/response models. The schemas ARE the contract.
- `server/storage/` — cloud-agnostic object-storage adapters (`memory`, `local`,
  `s3`) behind the `StorageBackend` Protocol.
- `server/storage/backup/` — Postgres `pg_dump`/`pg_restore` against a
  `StorageBackend`. Owns the periodic-backup scheduler and cold-start restore
  wired into the FastAPI lifespan. The `latest.dump` pointer convention lives
  exclusively in `server/storage/backup/pointer.py`; no other module knows the
  filename.
- `server/db.py`, `server/models.py`, `server/config.py` — DB engine, SQLAlchemy
  `Base`, env-driven config.

### User-contributed code

Where your fork's domain logic lives.

- `server/core/` — pure functions, **NO FastAPI imports allowed**. Deterministic,
  exhaustively unit-testable. The ≥90% coverage gate targets this surface.
  The scaffold ships an `echo()` placeholder; replace it with whatever your fork
  actually does. Name modules after the domain (e.g. `quote_calculator.py`,
  `order_intake.py`), not the technical role.

The `core` rule is load-bearing: deterministic, easy to test exhaustively,
testable without spinning up an HTTP server. Framework glue (FastAPI
middleware, DI, request parsing) lives in `api/`, where TestClient integration
tests cover it.

## Tests

- `tests/unit/` — tests for `server.core`. Pure functions, deterministic, fast.
- `tests/api/` — HTTP integration tests via the `client` fixture.
- `tests/conftest.py` — the `client` fixture branches on `BACKEND_BASE_URL`:
  - **unset** → `TestClient(create_app())` (in-process, default).
  - **set** → `httpx.Client(base_url=BACKEND_BASE_URL)` (against a running server, e.g. dockerized).
  - SAME test files run in both modes — no test code duplication.

### NO MOCKS, NO PATCHES, NO EXCEPTIONS

This is non-negotiable in this project.

```python
# ❌ FORBIDDEN — no mocks, no patches, no MagicMock, no @patch
from unittest.mock import Mock, MagicMock, patch
from pytest_mock import mocker
```

Test real code or don't test it. Use real `TestClient`, real `httpx.Client`,
real `tmp_path` for filesystem fixtures. If a test needs an external service,
use a real test instance via dependency injection — never a mock.

The full text of this rule lives in `.claude/rules/python/tests.md`. The
short version: mocks test your assumptions about an interface, not your
code; they hide bugs when the real implementation drifts; high coverage with
mocks is meaningless coverage.

## Strict gates

- `mypy --strict` — type every parameter and return value. `from __future__ import annotations` is in every file (allows forward references without quotes).
- `ruff` selects `E, W, F, I, B, C4, UP, RUF, SIM, ARG, N, S, PT`. Warnings = errors. Fix at the source; do not `# noqa` unless there's a documented per-file-ignore in `pyproject.toml`.
- `pytest --cov-fail-under=90` — total coverage on `server/` must stay ≥ 90%. The unit/api split keeps the denominator focused on real logic.

## Docker

- `Dockerfile` — multi-stage: builder uses uv to create a venv (`uv sync --frozen --no-dev --no-install-project`); runtime copies the venv + source and runs `python -m server` directly. No uv at runtime.
- Container listens on 8000; host port is `DOCKER_API_PORT` (default 8210).
- Healthcheck: `GET /api/health` via `urllib.request` (no `curl` in the slim image).
- `docker compose up -d --wait` blocks until the healthcheck passes.

## Adding a route — the recipe

1. Add Pydantic models to `server/api/schemas.py`.
2. Add the handler to `server/api/routes.py` — keep it thin, delegate to `server.core`.
3. Add real domain logic to `server/core/` (user-contributed surface).
4. Write a unit test in `tests/unit/test_<module>.py` for the core function.
5. Write an integration test in `tests/api/test_<endpoint>.py` using the `client` fixture.
6. Run `make test-py` — must pass with ≥ 90% coverage.

## When tests fail with `BACKEND_BASE_URL` set

That means the dockerized backend isn't reachable. Check:

- `make docker-status` — is the container running?
- `make docker-logs` — what's the container saying?
- `curl http://localhost:8210/api/health` — does the health endpoint respond?

Tests don't `pytest.skip` if `BACKEND_BASE_URL` is set but the server is
unreachable — they fail with a connection error, which is correct behavior.
Skipping would hide infrastructure failures.

## Imports

All imports go at the top of the file. No conditional / nested imports.
`from __future__ import annotations` is the only allowed top-level "import"
that has runtime effect (it disables eager type-hint evaluation).
