# Makefile for introspect_sessions scripts
# Run from repo root: make -C .claude/skills/introspect/scripts <target>

# Source files
SRC = introspect_sessions.py test_introspect_sessions.py

# --no-project prevents uv from discovering the root pyproject.toml,
# which would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project

# Shared pytest args to isolate from root pyproject.toml config
PYTEST_ARGS = -v --rootdir . -o 'addopts='

.PHONY: all test test-cov format format-check lint lint-fix typecheck check fix smoke clean help debug

debug:
	@echo "Makefile dir (PWD):  $(PWD)"
	@echo "Shell dir (\$\$PWD):  $$(pwd)"

# Default target
all: format lint typecheck test

# Run tests via PEP-723 entry point (deps declared in test file)
test:
	$(UV) test_introspect_sessions.py $(PYTEST_ARGS)

# Run tests with coverage — invokes pytest directly so coverage starts before imports
test-cov:
	$(UV) test_introspect_sessions.py $(PYTEST_ARGS) \
		--cov=introspect_sessions --cov-report=term-missing --cov-fail-under=90

# Format code with ruff
format:
	$(UV) ruff format $(SRC)

# Check formatting without modifying (for CI)
format-check:
	$(UV) ruff format --check $(SRC)

# Lint with ruff (line-length 120 for SQL strings and long docstrings)
lint: format
	$(UV) ruff check --line-length 120 $(SRC)

# Lint and auto-fix
lint-fix: format
	$(UV) ruff check --fix --line-length 120 $(SRC)

# Type check with mypy
typecheck: fix
	$(UV) mypy introspect_sessions.py --ignore-missing-imports --strict

# Run all checks (format-check + lint + typecheck) - suitable for CI
check: format-check lint typecheck

# Run all auto-fixers (format + lint-fix) - for local development
fix: format lint-fix

# Run a quick smoke test of the CLI
smoke:
	./introspect_sessions.sh --help
	./introspect_sessions.sh cache status || true

# Clean up cache and temp files
clean:
	rm -f *.pyc
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -f .coverage

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
	@echo "  smoke       - Quick CLI smoke test"
	@echo "  clean       - Remove temp files and caches"
	@echo ""
	@echo "Usage from repo root:"
	@echo "  make -C .claude/skills/introspect/scripts test"
	@echo "  make -C .claude/skills/introspect/scripts all"
