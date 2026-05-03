# Backend

FastAPI service that powers the application API.

See the top-level `CONTRIBUTING.md` for the full developer workflow (Make targets,
ports, test layout). Tight inner-loops from this directory:

```bash
make install     # uv sync
make dev         # uvicorn with reload (default port 8200)
make test        # pytest with coverage gate (>=90%)
make typecheck   # mypy --strict
make lint        # ruff check (warnings = errors)
```

For deploy-parity testing, use the top-level Docker workflow:

```bash
make docker-build       # build the backend image (multi-stage, uv-driven)
make docker-up          # start detached on port 8210, wait for /api/health
make test-api-docker    # run tests/api/ against the dockerized backend (httpx)
make docker-down        # tear down
```

Agent-specific guidance — including the **no-mocks** testing rule — lives in
`CLAUDE.md` next to this file.
