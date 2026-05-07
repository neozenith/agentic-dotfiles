SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# Ports — exported so child Makefiles + processes inherit them.
# Both backend AND frontend ports split across human/agent profiles so two
# concurrent dev sessions never collide. Docker uses a third pair so the
# container can run alongside `make dev` / `make agentic-dev`.
export API_PORT          ?= 8200
export AGENTIC_API_PORT  ?= 8201
export DEV_PORT          ?= 5173
export AGENTIC_DEV_PORT  ?= 5174
export DOCKER_API_PORT   ?= 8210

# DATABASE_BACKEND selects which overlay compose file to layer on top of the
# base docker-compose.yml. Override via `make DATABASE_BACKEND=postgres docker-up`
# (or any other docker-* target). Recursive expansion (`=`, not `:=`) so the
# variable is re-evaluated on every use — picks up command-line overrides.
DATABASE_BACKEND ?= sqlite

# BACKUP_BACKEND optionally layers an overlay for the postgres backup feature:
#   none     — default; backup feature stays OFF
#   local    — filesystem-backed StorageBackend (volume-mounted)
#   minio    — local S3-compatible service + bucket-init sidecar
#
# AWS S3 mode wants BACKUP_BACKEND=none and the host shell to export
# STORAGE_BACKEND=s3 + STORAGE_BUCKET + S3_REGION + AWS_* — the base compose
# threads those through to the backend container via env passthrough.
BACKUP_BACKEND ?= none

COMPOSE_FILES_BASE = -f docker-compose.yml -f docker-compose.$(DATABASE_BACKEND).yml
ifeq ($(BACKUP_BACKEND),minio)
  COMPOSE_FILES = $(COMPOSE_FILES_BASE) -f docker-compose.minio.yml
else ifeq ($(BACKUP_BACKEND),local)
  COMPOSE_FILES = $(COMPOSE_FILES_BASE) -f docker-compose.local-storage.yml
else
  COMPOSE_FILES = $(COMPOSE_FILES_BASE)
endif

.PHONY: help install dev agentic-dev \
        format format-ts format-py format-check format-check-ts format-check-py \
        lint lint-ts lint-py lint-fix lint-fix-ts lint-fix-py \
        typecheck typecheck-ts typecheck-py \
        test test-ts test-py test-e2e \
        fix ci ci-docker clean port-debug port-clean \
        docker-build docker-up docker-dev docker-down docker-logs docker-restart docker-status \
        docker-up-sqlite docker-up-postgres docker-up-postgres-minio docker-up-postgres-local minio-logs \
        test-api-docker test-e2e-docker test-backup-roundtrip

help: ## Show this help
	@grep -E '^[a-zA-Z][a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Installation
# =============================================================================

install: ## Install all deps for both subprojects (uv sync + bun install)
	$(MAKE) -C backend install
	$(MAKE) -C frontend install

# =============================================================================
# Dev (concurrently spawns backend + frontend in a single process tree)
# =============================================================================

dev: ## Run backend (8200) + frontend (5173) — HUMAN profile
	$(MAKE) -C frontend dev

agentic-dev: ## Run backend (8201) + frontend (5174) — AGENT profile (parallel-safe)
	$(MAKE) -C frontend agentic-dev

# =============================================================================
# Format
# =============================================================================

format: format-ts format-py ## Auto-format both halves
format-ts: ## Auto-format frontend (Biome)
	$(MAKE) -C frontend format
format-py: ## Auto-format backend (ruff format)
	$(MAKE) -C backend format

format-check: format-check-ts format-check-py ## Format-check both halves (no writes)
format-check-ts: ## Format-check frontend (Biome)
	$(MAKE) -C frontend format-check
format-check-py: ## Format-check backend (ruff format --check)
	$(MAKE) -C backend format-check

# =============================================================================
# Lint (warnings-are-errors)
# =============================================================================

lint: lint-ts lint-py ## Strict lint both halves (warnings = errors)
lint-ts: ## Strict lint frontend (biome ci)
	$(MAKE) -C frontend lint
lint-py: ## Strict lint backend (ruff check + ruff format --check)
	$(MAKE) -C backend lint

lint-fix: lint-fix-ts lint-fix-py ## Auto-fix lint findings on both halves
lint-fix-ts: ## Auto-fix frontend lint (biome check --write --unsafe)
	$(MAKE) -C frontend lint-fix
lint-fix-py: ## Auto-fix backend lint (ruff check --fix)
	$(MAKE) -C backend lint-fix

# =============================================================================
# Typecheck (strict)
# =============================================================================

typecheck: typecheck-ts typecheck-py ## Strict typecheck both halves
typecheck-ts: ## Frontend typecheck (tsc -b --noEmit)
	$(MAKE) -C frontend typecheck
typecheck-py: ## Backend typecheck (mypy --strict)
	$(MAKE) -C backend typecheck

# =============================================================================
# Test (>=90% coverage)
# =============================================================================

test: test-ts test-py ## Run unit tests on both halves with >=90% coverage gate
test-ts: ## Frontend unit tests (vitest --coverage)
	$(MAKE) -C frontend test
test-py: ## Backend unit + api tests (pytest --cov)
	$(MAKE) -C backend test

test-e2e: ## Playwright e2e (auto-launches both halves via concurrently)
	$(MAKE) -C frontend test-e2e

# =============================================================================
# Composite — the canonical inner-loop is `make fix ci`
# =============================================================================

fix: format lint-fix ## Auto-fix everything fixable (format + lint-fix, both halves)

ci: format-check lint typecheck test test-e2e ## Strict gate (format-check + lint + typecheck + test + e2e)

# =============================================================================
# Docker (deploy-parity testing — image bundles SPA + FastAPI; DB choice
# layered on top via DATABASE_BACKEND={sqlite,postgres})
# =============================================================================

docker-build: ## Build the bundled (frontend + backend) Docker image
	docker compose $(COMPOSE_FILES) build

docker-up: ## Start DETACHED with $(DATABASE_BACKEND) backend, wait for /api/health, print URL
	docker compose $(COMPOSE_FILES) up -d --wait
	@echo ""
	@echo "  ┌──────────────────────────────────────────────────────────┐"
	@echo "  │  App ready at: http://localhost:$(DOCKER_API_PORT)                       │"
	@echo "  │    Backend:     $(DATABASE_BACKEND)                                       │"
	@echo "  │    SPA:         http://localhost:$(DOCKER_API_PORT)/                      │"
	@echo "  │    API health:  http://localhost:$(DOCKER_API_PORT)/api/health            │"
	@echo "  │    OpenAPI:     http://localhost:$(DOCKER_API_PORT)/docs                  │"
	@echo "  │  Stop with: make docker-down                              │"
	@echo "  └──────────────────────────────────────────────────────────┘"
	@echo ""

docker-dev: ## Start in the FOREGROUND with $(DATABASE_BACKEND) backend (Ctrl+C to stop)
	@echo ""
	@echo "  Starting Docker stack in foreground (DATABASE_BACKEND=$(DATABASE_BACKEND))..."
	@echo "  Once healthy: http://localhost:$(DOCKER_API_PORT)"
	@echo "  Press Ctrl+C to stop."
	@echo ""
	docker compose $(COMPOSE_FILES) up

docker-up-sqlite: ## Convenience: docker-up with DATABASE_BACKEND=sqlite (the default)
	$(MAKE) DATABASE_BACKEND=sqlite docker-up

docker-up-postgres: ## Convenience: docker-up with DATABASE_BACKEND=postgres
	$(MAKE) DATABASE_BACKEND=postgres docker-up

docker-up-postgres-minio: ## Postgres + MinIO stack — full local backup/restore round-trip
	$(MAKE) DATABASE_BACKEND=postgres BACKUP_BACKEND=minio docker-up
	@echo ""
	@echo "  MinIO console:   http://localhost:9001 (minioadmin / minioadmin)"
	@echo "  MinIO S3 API:    http://localhost:9000"
	@echo "  Bucket:          app-backups"
	@echo ""

docker-up-postgres-local: ## Postgres + filesystem-backed LocalStorage backup
	$(MAKE) DATABASE_BACKEND=postgres BACKUP_BACKEND=local docker-up
	@echo ""
	@echo "  Backup target:   filesystem (named volume local-storage-data)"
	@echo "  In-container:    /app/data/storage/"
	@echo ""

minio-logs: ## Tail just the minio + minio-init container logs
	docker compose $(COMPOSE_FILES) logs -f minio minio-init

docker-down: ## Stop and remove the Docker stack (incl. volumes)
	docker compose $(COMPOSE_FILES) down -v --remove-orphans

docker-logs: ## Tail the docker compose logs
	docker compose $(COMPOSE_FILES) logs -f

docker-restart: docker-down docker-up ## Restart the docker stack with the current $(DATABASE_BACKEND)

docker-status: ## Show docker compose ps
	docker compose $(COMPOSE_FILES) ps

test-api-docker: docker-up ## Run pytest against the dockerized backend (port $(DOCKER_API_PORT))
	BACKEND_BASE_URL=http://localhost:$(DOCKER_API_PORT) $(MAKE) -C backend test-docker

test-e2e-docker: docker-up ## Run Playwright with the Vite frontend pointed at the dockerized backend
	PLAYWRIGHT_API_PORT=$(DOCKER_API_PORT) PLAYWRIGHT_FRONTEND_ONLY=1 $(MAKE) -C frontend test-e2e

test-backup-roundtrip: ## Postgres+MinIO backup/restore integration test (boots stack, runs test, tears down)
	@trap "$(MAKE) DATABASE_BACKEND=postgres BACKUP_BACKEND=minio docker-down >/dev/null 2>&1 || true" EXIT INT TERM; \
		$(MAKE) DATABASE_BACKEND=postgres BACKUP_BACKEND=minio docker-up && \
		BACKEND_BASE_URL=http://localhost:$(DOCKER_API_PORT) \
		  $(MAKE) -C backend test-backup-roundtrip

ci-docker: docker-build ## Strict gate vs the dockerized backend (api + e2e); cleans up on exit
	@trap "$(MAKE) docker-down >/dev/null 2>&1 || true" EXIT INT TERM; \
		$(MAKE) test-api-docker && \
		$(MAKE) test-e2e-docker && \
		echo "" && \
		echo "  ci-docker: PASS (DATABASE_BACKEND=$(DATABASE_BACKEND))" && \
		echo ""

# =============================================================================
# Port management
# =============================================================================

port-debug: ## Show which dev/docker ports are in use
	@for port in $(API_PORT) $(AGENTIC_API_PORT) $(DEV_PORT) $(AGENTIC_DEV_PORT) $(DOCKER_API_PORT); do \
		pid=$$(lsof -ti:$$port 2>/dev/null || true); \
		if [ -n "$$pid" ]; then echo "  port $$port: in use by PID $$pid"; \
		else echo "  port $$port: free"; fi; \
	done

port-clean: ## Kill processes on all 5 dev/docker ports
	@for port in $(API_PORT) $(AGENTIC_API_PORT) $(DEV_PORT) $(AGENTIC_DEV_PORT) $(DOCKER_API_PORT); do \
		pid=$$(lsof -ti:$$port 2>/dev/null || true); \
		if [ -n "$$pid" ]; then kill -9 $$pid && echo "  killed PID $$pid on port $$port"; fi; \
	done

# =============================================================================
# Cleanup
# =============================================================================

clean: ## Remove build artefacts, deps, test outputs from both halves
	$(MAKE) -C backend clean
	$(MAKE) -C frontend clean
	rm -rf tmp
