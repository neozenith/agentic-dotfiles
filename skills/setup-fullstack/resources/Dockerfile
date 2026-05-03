# Multi-stage Dockerfile bundling the React frontend (built by Vite) +
# the FastAPI backend into a single image.
#
# Build context = project root (so we can COPY both backend/ and frontend/).
#
# Stage 1 (frontend-builder): bun install + vite build → /work/dist
# Stage 2 (backend-builder):  uv sync (no-dev, no-install-project) → /work/.venv
# Stage 3 (runtime):          slim Python; copies venv + server source + built SPA.
#
# At runtime FastAPI mounts /app/static (the built SPA) at "/" so a single
# origin serves both the API (under /api/*) and the SPA (everything else).

# === Stage 1: frontend-builder ===
FROM oven/bun:1 AS frontend-builder
WORKDIR /work

# Lockfile + manifest first for layer caching across source changes.
COPY frontend/package.json frontend/bun.lock* ./
RUN bun install --frozen-lockfile

# Source after — invalidates only this layer when components change.
COPY frontend/ ./
RUN bun run build
# Output: /work/dist/

# === Stage 2: backend-builder ===
FROM python:3.12-slim AS backend-builder

# Pin uv via the official static-binary image (no apt, no curl chain).
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /work

# Lockfile + manifest first for layer caching.
COPY backend/pyproject.toml backend/uv.lock ./

# Install non-dev deps into /work/.venv. `--no-install-project` skips
# building the local `server` package — we COPY it fresh into the runtime
# stage and rely on PYTHONPATH for imports.
RUN uv sync --frozen --no-dev --no-install-project

# === Stage 3: runtime ===
FROM python:3.12-slim AS runtime
WORKDIR /app

# Copy the built artefacts: backend venv, backend source, and the built SPA.
COPY --from=backend-builder /work/.venv /app/.venv
COPY backend/server /app/server
COPY --from=frontend-builder /work/dist /app/static

# PATH activates the venv; PYTHONPATH lets `python -m server` find the source
# without having installed it as a wheel. STATIC_DIR tells create_app where
# the SPA lives. DATABASE_URL points at a per-container SQLite file in a
# directory we mkdir below (volume-mountable for persistence).
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    STATIC_DIR=/app/static \
    DATABASE_URL=sqlite:////app/data/app.db \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /app/data

EXPOSE 8000

# uvicorn(factory=True): create_app() is built fresh per worker.
CMD ["python", "-m", "server", "--host", "0.0.0.0", "--port", "8000"]
