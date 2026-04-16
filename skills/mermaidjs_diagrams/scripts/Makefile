# Shared Makefile for all mermaidjs_diagrams skill scripts
# Run from repo root: make -C .claude/skills/mermaidjs_diagrams/scripts <target>

# ── Python source ──────────────────────────────────────────────────────────

# Public scripts: referenced in SKILL.md, used during skill execution
PY_SCRIPTS = mermaid_complexity

# Private scripts: maintenance helpers for the skill itself, NOT in SKILL.md
PRIVATE_PY_SCRIPTS = _update_examples_readme

PY_SRC = $(addsuffix .py,$(PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PY_SCRIPTS))) \
         $(addsuffix .py,$(PRIVATE_PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PRIVATE_PY_SCRIPTS)))

# ── TypeScript source ──────────────────────────────────────────────────────

# Python remains the scientific baseline; TS versions use mermaid's canonical
# parsers for higher-fidelity structural extraction. See .claude/rules/typescript/
# for conventions.
TS_SCRIPTS = color_contrast mermaid_complexity mermaid_contrast
TS_SRC = $(addsuffix .ts,$(TS_SCRIPTS)) $(addsuffix .test.ts,$(TS_SCRIPTS))

# ── Paths ──────────────────────────────────────────────────────────────────

THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
EXAMPLES_DIR := $(abspath $(THIS_DIR)../resources/examples)
EXAMPLES_README := $(EXAMPLES_DIR)/README.md

# --no-project prevents uv from discovering the root pyproject.toml,
# which would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project

# Shared pytest args to isolate from root pyproject.toml config
PYTEST_ARGS = -v --rootdir . -o 'addopts='

# Biome: invoked via bunx so it stays out of package.json devDependencies.
# `--bun` forces it to run on Bun's runtime rather than Node.
BIOME = bunx --bun @biomejs/biome

.PHONY: all debug help clean \
        format format-py format-ts \
        format-check format-check-py format-check-ts \
        lint lint-py lint-ts \
        lint-fix lint-fix-py lint-fix-ts \
        typecheck typecheck-py typecheck-ts \
        test test-py test-ts \
        test-cov test-cov-py test-cov-ts \
        install-ts docs parity ci fix

# Default target
all: format lint typecheck test-cov docs

debug:
	echo $(MAKEFILE_LIST)
	echo $(lastword $(MAKEFILE_LIST))
	echo $(abspath $(lastword $(MAKEFILE_LIST)))
	echo $(THIS_DIR)
	echo $(EXAMPLES_DIR)
	echo $(EXAMPLES_README)

# ── Format ─────────────────────────────────────────────────────────────────

format: format-py format-ts

format-py: $(PY_SRC)
	$(UV) ruff format $(PY_SRC)

format-ts: $(TS_SRC)
	$(BIOME) format --write $(TS_SRC)

format-check: format-check-py format-check-ts

format-check-py: $(PY_SRC)
	$(UV) ruff format --check $(PY_SRC)

format-check-ts: $(TS_SRC)
	$(BIOME) format $(TS_SRC)

# ── Lint ───────────────────────────────────────────────────────────────────

lint: lint-py lint-ts

lint-py: $(PY_SRC)
	$(UV) ruff check --line-length 120 $(PY_SRC)

lint-ts: $(TS_SRC)
	$(BIOME) lint $(TS_SRC)

lint-fix: lint-fix-py lint-fix-ts

lint-fix-py: $(PY_SRC)
	$(UV) ruff check --fix --line-length 120 $(PY_SRC)

lint-fix-ts: $(TS_SRC)
	$(BIOME) lint --write $(TS_SRC)

# ── Typecheck ──────────────────────────────────────────────────────────────

typecheck: typecheck-py typecheck-ts

typecheck-py: $(addsuffix .py,$(PY_SCRIPTS) $(PRIVATE_PY_SCRIPTS))
	$(UV) mypy $(addsuffix .py,$(PY_SCRIPTS) $(PRIVATE_PY_SCRIPTS)) --ignore-missing-imports --strict

# We invoke the local tsc binary directly rather than `bunx tsc`, because
# `bunx --cwd` has dependency-resolution quirks when the current directory
# and the cwd differ.
typecheck-ts:
	$(THIS_DIR)node_modules/.bin/tsc --project $(THIS_DIR)tsconfig.json --noEmit

# ── Test ───────────────────────────────────────────────────────────────────

test: test-py test-ts

# PEP-723 entry point — deps declared in the test file itself
test-py:
	$(UV) test_mermaid_complexity.py $(PYTEST_ARGS)
	$(UV) test__update_examples_readme.py $(PYTEST_ARGS)

test-ts:
	bun test --cwd $(THIS_DIR)

test-cov: test-cov-py test-cov-ts

test-cov-py:
	$(UV) test_mermaid_complexity.py $(PYTEST_ARGS) \
		--cov=mermaid_complexity --cov-report=term-missing --cov-fail-under=90
	$(UV) test__update_examples_readme.py $(PYTEST_ARGS) \
		--cov=_update_examples_readme --cov-report=term-missing --cov-fail-under=90

test-cov-ts:
	bun test --cwd $(THIS_DIR) --coverage

# ── Install / Docs / Misc ──────────────────────────────────────────────────

# Install TS deps into this directory's node_modules
install-ts:
	bun install --cwd $(THIS_DIR)

# Regenerate examples README from .mmd + .png pairs
docs:
	$(UV) _update_examples_readme.py
	uvx --from md-toc md_toc --in-place github --header-levels 4 $(EXAMPLES_README)


# Run all checks with coverage enforcement, then regenerate docs (CI standard).
# Note: format-check / lint / typecheck / test-cov all fan out to -py and -ts.
ci: format-check lint typecheck test-cov docs

# Run all auto-fixers (local development)
fix: format lint-fix

# Clean up cache and temp files
clean:
	rm -f *.pyc
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

# Show help
help:
	@echo "Composite targets (run both Python and TypeScript):"
	@echo "  all          - format + lint + typecheck + test-cov + docs (default)"
	@echo "  format       - Auto-format source"
	@echo "  format-check - Check formatting without modifying (CI-safe)"
	@echo "  lint         - Lint source (non-mutating)"
	@echo "  lint-fix     - Lint and auto-fix"
	@echo "  typecheck    - Type check source"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage"
	@echo "  ci           - format-check + lint + typecheck + test-cov + docs"
	@echo "  fix          - format + lint-fix"
	@echo ""
	@echo "Python-specific:"
	@echo "  format-py, format-check-py, lint-py, lint-fix-py"
	@echo "  typecheck-py, test-py, test-cov-py"
	@echo ""
	@echo "TypeScript-specific:"
	@echo "  format-ts, format-check-ts, lint-ts, lint-fix-ts"
	@echo "  typecheck-ts, test-ts, test-cov-ts, install-ts"
	@echo ""
	@echo "Misc:"
	@echo "  docs         - Regenerate examples README from .mmd files"
	@echo "  clean        - Remove temp files and caches"
