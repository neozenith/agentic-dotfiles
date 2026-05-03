# Multi-stage Dockerfile for the FastAPI backend.
#
# Stage 1 (builder): use uv to materialise a venv with all runtime deps.
# Stage 2 (runtime): copy ONLY the venv + source — no uv, no build tools.
#
# Build context is the backend/ directory. From the project root:
#   docker compose build
# or, equivalently:
#   docker build -t myapp-backend backend/

FROM python:3.12-slim AS builder

# Pin uv via the official static-binary image (no apt, no curl chain).
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency manifests FIRST so this layer caches across source changes.
COPY pyproject.toml uv.lock ./

# Install ALL non-dev dependencies into /app/.venv. `--no-install-project`
# skips building the local `server` package itself — we copy it in fresh
# below, and use PYTHONPATH at runtime instead. This avoids needing a
# README.md just to satisfy hatchling's metadata reader during the build.
RUN uv sync --frozen --no-dev --no-install-project

COPY server ./server

# ---

FROM python:3.12-slim AS runtime
WORKDIR /app

# Copy the built venv + source from builder. No uv in the runtime image.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/server ./server

# Activate the venv (PATH only — no shell activation script needed).
# PYTHONPATH lets `python -m server` import the local package without
# having installed it as a wheel.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# uvicorn with factory=True; create_app() is built fresh per worker.
CMD ["python", "-m", "server", "--host", "0.0.0.0", "--port", "8000"]
