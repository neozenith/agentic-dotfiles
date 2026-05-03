SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# Ports — exported so child Makefiles + processes inherit them.
# Both backend AND frontend ports split across human/agent profiles so two
# concurrent dev sessions never collide.
export API_PORT          ?= 8200
export AGENTIC_API_PORT  ?= 8201
export DEV_PORT          ?= 5173
export AGENTIC_DEV_PORT  ?= 5174

.PHONY: help install dev agentic-dev \
        format format-ts format-py format-check format-check-ts format-check-py \
        lint lint-ts lint-py lint-fix lint-fix-ts lint-fix-py \
        typecheck typecheck-ts typecheck-py \
        test test-ts test-py test-e2e \
        fix ci clean port-debug port-clean

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
# Port management
# =============================================================================

port-debug: ## Show which dev ports are in use
	@for port in $(API_PORT) $(AGENTIC_API_PORT) $(DEV_PORT) $(AGENTIC_DEV_PORT); do \
		pid=$$(lsof -ti:$$port 2>/dev/null || true); \
		if [ -n "$$pid" ]; then echo "  port $$port: in use by PID $$pid"; \
		else echo "  port $$port: free"; fi; \
	done

port-clean: ## Kill processes on all 4 dev ports
	@for port in $(API_PORT) $(AGENTIC_API_PORT) $(DEV_PORT) $(AGENTIC_DEV_PORT); do \
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
