# Makefile for plan_manager scripts
# Run from repo root: make -C .claude/skills/plans/scripts <target>

# Source files
SCRIPTS = plan_manager
SRC = $(addsuffix .py,$(SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(SCRIPTS))) conftest.py

# --no-project prevents uv from discovering the root pyproject.toml,
# which would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project

# Shared pytest args to isolate from root pyproject.toml config
PYTEST_ARGS = -v --rootdir . -o 'addopts='

.PHONY: all test test-cov format format-check \
        lint lint-fix typecheck \
        check fix clean help smoke ci

# Default target
all: format lint typecheck test-cov

# Run tests via PEP-723 entry point (deps declared in test file)
test:
	$(UV) test_plan_manager.py $(PYTEST_ARGS)

# Run tests with coverage — via same PEP-723 entry point
test-cov:
	$(UV) test_plan_manager.py $(PYTEST_ARGS) \
		--cov=plan_manager --cov-report=term-missing --cov-fail-under=90

# Format code with ruff
format: $(SRC)
	$(UV) ruff format $(SRC)

# Check formatting without modifying (for CI)
format-check: $(SRC)
	$(UV) ruff format --check $(SRC)

# Lint with ruff (line-length 120 for SQL strings and long docstrings)
lint: format $(SRC)
	$(UV) ruff check --line-length 120 $(SRC)

# Lint and auto-fix
lint-fix: format $(SRC)
	$(UV) ruff check --fix --line-length 120 $(SRC)

# Type check with mypy
typecheck: fix plan_manager.py
	$(UV) mypy plan_manager.py --ignore-missing-imports --strict

# Run all checks (CI-friendly)
ci: format-check lint typecheck test-cov

# Run all auto-fixers (local development)
fix: format lint-fix

# Quick CLI smoke test
smoke:
	./plan_manager.sh --help

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
	@echo "  ci          - Run all checks (CI-friendly)"
	@echo "  fix         - Run all auto-fixers"
	@echo "  smoke       - Quick CLI smoke test"
	@echo "  clean       - Remove temp files and caches"
