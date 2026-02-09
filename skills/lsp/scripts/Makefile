# Makefile for lsp_explorer scripts
# Run from repo root: make -C .claude/skills/lsp/scripts <target>

# Source files
SRC = lsp_explorer.py test_lsp_explorer.py

.PHONY: all test format lint typecheck check fix clean help smoke test-cov

# Default target
all: format lint typecheck test

# Run tests with pytest
test:
	uv run test_lsp_explorer.py

# Run tests with coverage
test-cov:
	uv run --with pytest-cov test_lsp_explorer.py --cov=lsp_explorer --cov-report=term-missing

# Format code with ruff
format:
	uv run ruff format $(SRC)

# Check formatting without modifying (for CI)
format-check:
	uv run ruff format --check $(SRC)

# Lint with ruff (line-length 120)
lint: format
	uv run ruff check --line-length 120 $(SRC)

# Lint and auto-fix
lint-fix: format
	uv run ruff check --fix --line-length 120 $(SRC)

# Type check with mypy
typecheck: fix
	uv run --with "lsprotocol>=2024.0.0" mypy lsp_explorer.py --ignore-missing-imports --strict

# Run all checks (CI-friendly)
check: format-check lint typecheck

# Run all auto-fixers (local development)
fix: format lint-fix

# Quick CLI smoke test
smoke:
	./lsp_explorer.sh --help

# Clean up cache and temp files
clean:
	rm -f *.pyc
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

# Show help
help:
	@echo "Available targets:"
	@echo "  all         - Run format, lint, typecheck, and test (default)"
	@echo "  test        - Run pytest tests"
	@echo "  test-cov    - Run tests with coverage report"
	@echo "  format      - Format code with ruff"
	@echo "  lint        - Lint code with ruff"
	@echo "  typecheck   - Type check with mypy"
	@echo "  check       - Run all checks (CI-friendly)"
	@echo "  fix         - Run all auto-fixers"
	@echo "  smoke       - Quick CLI smoke test"
	@echo "  clean       - Remove temp files and caches"
