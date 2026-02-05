# Makefile for introspect_sessions scripts
# Run from repo root: make -C .claude/skills/introspect/scripts <target>

.PHONY: all test format lint typecheck check clean help

# Default target
all: format lint typecheck test

# Run tests with pytest
test:
	uv run pytest test_introspect_sessions.py -v

# Run tests with coverage
test-cov:
	uv run --with pytest-cov pytest test_introspect_sessions.py -v --cov=introspect_sessions --cov-report=term-missing

# Format code with ruff
format:
	uv run ruff format introspect_sessions.py test_introspect_sessions.py

# Check formatting without modifying (for CI)
format-check:
	uv run ruff format --check introspect_sessions.py test_introspect_sessions.py

# Lint with ruff (line-length 120 for SQL strings and long docstrings)
lint: format
	uv run ruff check --line-length 120 introspect_sessions.py test_introspect_sessions.py

# Lint and auto-fix
lint-fix: format
	uv run ruff check --fix --line-length 120 introspect_sessions.py test_introspect_sessions.py

# Type check with mypy
typecheck: fix
	uv run mypy introspect_sessions.py --ignore-missing-imports --strict

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
