SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

API_PORT         ?= 8200
AGENTIC_API_PORT ?= 8201

.PHONY: install dev agentic-dev format format-check lint lint-fix typecheck test test-cov clean

# uv sync materialises the venv from uv.lock; the conditional handles the
# fresh-checkout case where there's no lockfile yet (first install creates it).
install:
	uv sync 2>/dev/null || uv sync

dev:
	uv run python -m server --port $(API_PORT) --reload

agentic-dev:
	uv run python -m server --port $(AGENTIC_API_PORT) --reload

format:
	uv run ruff format server tests

format-check:
	uv run ruff format --check server tests

# warnings-are-errors: ruff check + ruff format --check both must pass.
lint:
	uv run ruff check server tests
	uv run ruff format --check server tests

lint-fix:
	uv run ruff check --fix server tests

typecheck:
	uv run mypy server tests

test:
	uv run pytest

test-cov:
	uv run pytest --cov-report=html

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage dist build
