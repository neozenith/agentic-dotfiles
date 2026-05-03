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
