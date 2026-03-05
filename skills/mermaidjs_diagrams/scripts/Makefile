# Shared Makefile for all mermaidjs_diagrams skill scripts
# Run from repo root: make -C .claude/skills/mermaidjs_diagrams/scripts <target>

SCRIPTS = setup_diagrams mermaid_complexity
SRC = $(addsuffix .py,$(SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(SCRIPTS)))

# --no-project prevents uv from discovering the root pyproject.toml,
# which would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project

# Shared pytest args to isolate from root pyproject.toml config
PYTEST_ARGS = -v --rootdir . -o 'addopts='

.PHONY: all test test-cov format format-check \
        lint lint-fix typecheck \
        ci fix clean help smoke

# Default target
all: format lint typecheck test-cov

# Run all test suites via PEP-723 entry points
test:
	$(UV) test_setup_diagrams.py $(PYTEST_ARGS)
	$(UV) test_mermaid_complexity.py $(PYTEST_ARGS)

# Run tests with coverage
test-cov:
	$(UV) test_setup_diagrams.py $(PYTEST_ARGS) \
		--cov=setup_diagrams --cov-report=term-missing --cov-fail-under=90
	$(UV) test_mermaid_complexity.py $(PYTEST_ARGS) \
		--cov=mermaid_complexity --cov-report=term-missing --cov-fail-under=90

# Format code with ruff
format:
	$(UV) ruff format $(SRC)

# Check formatting without modifying (for CI)
format-check:
	$(UV) ruff format --check $(SRC)

# Lint with ruff
lint: format
	$(UV) ruff check --line-length 120 $(SRC)

# Lint and auto-fix
lint-fix: format
	$(UV) ruff check --fix --line-length 120 $(SRC)

# Type check with mypy (source files only)
typecheck: fix
	$(UV) mypy $(addsuffix .py,$(SCRIPTS)) --ignore-missing-imports --strict

# Run all checks with coverage enforcement (CI standard)
ci: format-check lint typecheck test-cov

# Run all auto-fixers (local development)
fix: format lint-fix

# Quick CLI smoke test (no .sh wrappers — invoke via uv run directly)
smoke:
	$(UV) setup_diagrams.py --help
	$(UV) mermaid_complexity.py --help

# Clean up cache and temp files
clean:
	rm -f *.pyc
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

# Show help
help:
	@echo "Available targets:"
	@echo "  all         - Run format, lint, typecheck, and test (default)"
	@echo "  test        - Run all pytest test suites"
	@echo "  test-cov    - Run tests with coverage report"
	@echo "  format      - Format code with ruff"
	@echo "  format-check- Check formatting without modifying"
	@echo "  lint        - Lint code with ruff"
	@echo "  lint-fix    - Lint and auto-fix issues"
	@echo "  typecheck   - Type check with mypy"
	@echo "  ci          - Run all checks with coverage enforcement"
	@echo "  fix         - Run all auto-fixers"
	@echo "  smoke       - Quick CLI smoke test (--help on each script)"
	@echo "  clean       - Remove temp files and caches"
