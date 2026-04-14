# Shared Makefile for all mermaidjs_diagrams skill scripts
# Run from repo root: make -C .claude/skills/mermaidjs_diagrams/scripts <target>

# Public scripts: referenced in SKILL.md, used during skill execution
SCRIPTS = mermaid_complexity

# Private scripts: maintenance helpers for the skill itself, NOT in SKILL.md
PRIVATE_SCRIPTS = _update_examples_readme

# TypeScript scripts (parity ports + new tools). Python remains the scientific
# baseline; TS versions use mermaid's canonical parsers for higher-fidelity
# structural extraction. See .claude/rules/typescript/ for conventions.
TS_SCRIPTS = mermaid_complexity find_mermaid_fences
TS_SRC = $(addsuffix .ts,$(TS_SCRIPTS)) $(addsuffix .test.ts,$(TS_SCRIPTS))

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
        ci fix clean help smoke debug \
        test-ts typecheck-ts smoke-ts install-ts parity

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
	$(UV) test_mermaid_complexity.py $(PYTEST_ARGS)
	$(UV) test__update_examples_readme.py $(PYTEST_ARGS)

# Run tests with coverage
test-cov:
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

# ── TypeScript targets ─────────────────────────────────────────────────────

# Install TS deps into this directory's node_modules
install-ts:
	bun install --cwd $(THIS_DIR)

# Typecheck TS scripts (strict mode, no emit). We invoke the local tsc binary
# directly rather than `bunx tsc`, because `bunx --cwd` has dependency-resolution
# quirks when the current directory and the cwd differ.
typecheck-ts:
	$(THIS_DIR)node_modules/.bin/tsc --project $(THIS_DIR)tsconfig.json --noEmit

# Run bun:test suites (pattern matches *.test.ts)
test-ts:
	bun test --cwd $(THIS_DIR)

# Smoke test: --help on each public TS script
smoke-ts:
	bun run $(THIS_DIR)mermaid_complexity.ts --help
	bun run $(THIS_DIR)find_mermaid_fences.ts --help

# Cross-language parity check: run Python and TS on the same fixtures, compare
# numeric metrics. Use this as a scientific regression gate when changing
# either implementation.
parity:
	@echo "=== Python baseline (regex parser) ==="
	@$(UV) mermaid_complexity.py $(EXAMPLES_DIR)/flowchart_fontawesome_icons.mmd --json --quiet | jq '.[0] | {nodes, edges, subgraphs, vcs: .visual_complexity_score, parser: "regex"}'
	@echo "=== TypeScript port (canonical parser) ==="
	@bun run $(THIS_DIR)mermaid_complexity.ts $(EXAMPLES_DIR)/flowchart_fontawesome_icons.mmd --json --quiet | jq '.[0] | {nodes, edges, subgraphs, vcs: .visual_complexity_score, parser: .parser_used, type: .diagram_type}'
	@echo ""
	@echo "=== Architecture-beta (where regex misses everything) ==="
	@echo "Python:"
	@$(UV) mermaid_complexity.py $(EXAMPLES_DIR)/architecture_beta_iconify_logos.mmd --json --quiet | jq '.[0] | {nodes, edges, subgraphs, vcs: .visual_complexity_score}'
	@echo "TypeScript:"
	@bun run $(THIS_DIR)mermaid_complexity.ts $(EXAMPLES_DIR)/architecture_beta_iconify_logos.mmd --json --quiet | jq '.[0] | {nodes, edges, subgraphs, vcs: .visual_complexity_score, parser: .parser_used}'

# Run all checks with coverage enforcement, then regenerate docs (CI standard)
ci: format-check lint typecheck test-cov typecheck-ts test-ts docs

# Run all auto-fixers (local development)
fix: format lint-fix

# Quick CLI smoke test (no .sh wrappers — invoke via uv run / bun run directly)
smoke: smoke-ts
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
	@echo ""
	@echo "TypeScript targets (parity ports + new tools):"
	@echo "  install-ts   - bun install in the scripts directory"
	@echo "  typecheck-ts - tsc --noEmit on all TS files"
	@echo "  test-ts      - bun:test suites"
	@echo "  smoke-ts     - --help on each TS script"
	@echo "  parity       - Compare Python vs TS output on the same fixture"
	@echo ""
	@echo "  clean       - Remove temp files and caches"
