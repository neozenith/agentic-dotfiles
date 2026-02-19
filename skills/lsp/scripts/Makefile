# Makefile for lsp_explorer scripts
# Run from repo root: make -C .claude/skills/lsp/scripts <target>

# Source files
SRC = lsp_explorer.py test_lsp_explorer.py

# --no-project prevents uv from discovering the root pyproject.toml,
# which would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project

# Shared pytest args to isolate from root pyproject.toml config
PYTEST_ARGS = -v --rootdir . -o 'addopts='

.PHONY: all test test-cov format format-check lint lint-fix typecheck check fix clean help smoke debug

# Default target
all: format lint typecheck test

# Run tests via PEP-723 entry point (deps declared in test file)
test:
	$(UV) test_lsp_explorer.py $(PYTEST_ARGS)

# Run tests with coverage — via same PEP-723 entry point
test-cov:
	$(UV) test_lsp_explorer.py $(PYTEST_ARGS) \
		--cov=lsp_explorer --cov-report=term-missing --cov-fail-under=90

# Format code with ruff
format:
	$(UV) ruff format $(SRC)

# Check formatting without modifying (for CI)
format-check:
	$(UV) ruff format --check $(SRC)

# Lint with ruff (line-length 120)
lint: format
	$(UV) ruff check --line-length 120 $(SRC)

# Lint and auto-fix
lint-fix: format
	$(UV) ruff check --fix --line-length 120 $(SRC)

# Type check with mypy
typecheck: fix
	$(UV) mypy lsp_explorer.py --ignore-missing-imports --strict

# Run all checks (CI-friendly)
check: format-check lint typecheck test-cov

# Run all auto-fixers (local development)
fix: format lint-fix

# Quick CLI smoke test
smoke:
	./lsp_explorer.sh --help

# Debug: show resolved uv/pytest config
debug:
	@echo "UV = $(UV)"
	@echo "PYTEST_ARGS = $(PYTEST_ARGS)"
	$(UV) python -c "import sys; print('Python:', sys.executable)"

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
	@echo "  format-check- Check formatting without modifying"
	@echo "  lint        - Lint code with ruff"
	@echo "  lint-fix    - Lint and auto-fix issues"
	@echo "  typecheck   - Type check with mypy"
	@echo "  check       - Run all checks (CI-friendly)"
	@echo "  fix         - Run all auto-fixers"
	@echo "  smoke       - Quick CLI smoke test"
	@echo "  debug       - Show resolved uv/pytest config"
	@echo "  clean       - Remove temp files and caches"
