# Shared Makefile for all mermaidjs_diagrams skill scripts
# Run from repo root: make -C .claude/skills/mermaidjs_diagrams/scripts <target>

# Public scripts: referenced in SKILL.md, used during skill execution
SCRIPTS = setup_diagrams mermaid_complexity

# Private scripts: maintenance helpers for the skill itself, NOT in SKILL.md
PRIVATE_SCRIPTS = _update_examples_readme

SRC = $(addsuffix .py,$(SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(SCRIPTS))) \
      $(addsuffix .py,$(PRIVATE_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PRIVATE_SCRIPTS)))

THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
EXAMPLES_DIR := $(abspath $(THIS_DIR)../resources/examples)
EXAMPLES_README := $(EXAMPLES_DIR)/README.md

# --no-project prevents uv from discovering the root pyproject.toml,
# which would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project

# Shared pytest args to isolate from root pyproject.toml config
PYTEST_ARGS = -v --rootdir . -o 'addopts='

.PHONY: all test test-cov format format-check \
        lint lint-fix typecheck docs \
        ci fix clean help smoke debug

debug:
	echo $(MAKEFILE_LIST)
	echo $(lastword $(MAKEFILE_LIST))
	echo $(abspath $(lastword $(MAKEFILE_LIST)))
	echo $(THIS_DIR)
	echo $(EXAMPLES_DIR)
	echo $(EXAMPLES_README)

# Default target
all: format lint typecheck test-cov

# Run all test suites via PEP-723 entry points
test:
	$(UV) test_setup_diagrams.py $(PYTEST_ARGS)
	$(UV) test_mermaid_complexity.py $(PYTEST_ARGS)
	$(UV) test__update_examples_readme.py $(PYTEST_ARGS)

# Run tests with coverage
test-cov:
	$(UV) test_setup_diagrams.py $(PYTEST_ARGS) \
		--cov=setup_diagrams --cov-report=term-missing --cov-fail-under=90
	$(UV) test_mermaid_complexity.py $(PYTEST_ARGS) \
		--cov=mermaid_complexity --cov-report=term-missing --cov-fail-under=90
	$(UV) test__update_examples_readme.py $(PYTEST_ARGS) \
		--cov=_update_examples_readme --cov-report=term-missing --cov-fail-under=90

# Format code with ruff
format: $(SRC)
	$(UV) ruff format $(SRC)

# Check formatting without modifying (for CI)
format-check: $(SRC)
	$(UV) ruff format --check $(SRC)

# Lint with ruff
lint: format $(SRC)
	$(UV) ruff check --line-length 120 $(SRC)

# Lint and auto-fix
lint-fix: format $(SRC)
	$(UV) ruff check --fix --line-length 120 $(SRC)

# Type check with mypy (source files only, public + private)
typecheck: fix $(addsuffix .py,$(SCRIPTS) $(PRIVATE_SCRIPTS))
	$(UV) mypy $(addsuffix .py,$(SCRIPTS) $(PRIVATE_SCRIPTS)) --ignore-missing-imports --strict

# Regenerate examples README from .mmd + .png pairs
docs:
	$(UV) _update_examples_readme.py
	uvx --from md-toc md_toc --in-place github --header-levels 4 $(EXAMPLES_README)

# Run all checks with coverage enforcement, then regenerate docs (CI standard)
ci: format-check lint typecheck test-cov docs

# Run all auto-fixers (local development)
fix: format lint-fix

# Quick CLI smoke test (no .sh wrappers — invoke via uv run directly)
smoke:
	$(UV) setup_diagrams.py --help
	$(UV) mermaid_complexity.py --help
	$(UV) _update_examples_readme.py --help

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
	@echo "  docs        - Regenerate examples README from .mmd + .png pairs"
	@echo "  ci          - Run all checks + docs (CI standard)"
	@echo "  fix         - Run all auto-fixers"
	@echo "  smoke       - Quick CLI smoke test (--help on each script)"
	@echo "  clean       - Remove temp files and caches"
