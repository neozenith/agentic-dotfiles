# Shared Makefile for all mermaidjs_diagrams skill scripts
# Run from repo root: make -C .claude/skills/mermaidjs_diagrams/scripts <target>

# ── Python source ──────────────────────────────────────────────────────────

# Public Python scripts (none — the TS port is now authoritative for
# complexity analysis; mermaid_complexity.py was removed once the TS
# implementation reached feature parity via canonical mermaid parsers).
PY_SCRIPTS =

# Private scripts: maintenance helpers for the skill itself, NOT in SKILL.md
PRIVATE_PY_SCRIPTS = _update_examples_readme

PY_SRC = $(addsuffix .py,$(PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PY_SCRIPTS))) \
         $(addsuffix .py,$(PRIVATE_PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PRIVATE_PY_SCRIPTS)))

# ── TypeScript source ──────────────────────────────────────────────────────

# TS is now the authoritative implementation for complexity + contrast.
# See .claude/rules/typescript/ for conventions.
TS_SCRIPTS = color_contrast mermaid_complexity mermaid_contrast
TS_SRC = $(addsuffix .ts,$(TS_SCRIPTS)) $(addsuffix .test.ts,$(TS_SCRIPTS))

# ── Paths ──────────────────────────────────────────────────────────────────

THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
EXAMPLES_DIR := $(abspath $(THIS_DIR)../resources/examples)
EXAMPLES_README := $(EXAMPLES_DIR)/README.md

# --no-project prevents uv from discovering the root pyproject.toml,
# which would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project

# Shared pytest args to isolate from root pyproject.toml config. We override
# both `addopts` and `filterwarnings` because the root project references
# pytest plugins / warning filters (pydantic, litellm) that aren't in our
# minimal PEP-723 test environment. Without these overrides, pytest picks
# them up via --rootdir discovery and fails before any test runs.
PYTEST_ARGS = -v -c /dev/null --rootdir .

# Biome: invoked via bunx so it stays out of package.json devDependencies.
# `--bun` forces it to run on Bun's runtime rather than Node.
#
# NOTE: `biome lint`, `biome format`, and `biome check` exit 0 when the only
# findings are warnings — only errors produce a non-zero exit. That silently
# masks lint regressions in CI. `--error-on-warnings` promotes any warning
# to a non-zero exit code so the instrumentation is loud.
BIOME = bunx --bun @biomejs/biome
BIOME_FLAGS = --error-on-warnings

.PHONY: all debug help clean \
        format format-py format-ts \
        format-check format-check-py format-check-ts \
        lint lint-py lint-ts \
        lint-fix lint-fix-py lint-fix-ts \
        typecheck typecheck-py typecheck-ts \
        test test-py test-ts \
        test-cov test-cov-py test-cov-ts \
        install-ts docs ci fix cli-demo

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
	$(BIOME) format $(BIOME_FLAGS) --write $(TS_SRC)

format-check: format-check-py format-check-ts

format-check-py: $(PY_SRC)
	$(UV) ruff format --check $(PY_SRC)

format-check-ts: $(TS_SRC)
	$(BIOME) format $(BIOME_FLAGS) $(TS_SRC)

# ── Lint ───────────────────────────────────────────────────────────────────

lint: lint-py lint-ts

lint-py: $(PY_SRC)
	$(UV) ruff check --line-length 120 $(PY_SRC)

lint-ts: $(TS_SRC)
	$(BIOME) lint $(BIOME_FLAGS) $(TS_SRC)

lint-fix: lint-fix-py lint-fix-ts

lint-fix-py: $(PY_SRC)
	$(UV) ruff check --fix --line-length 120 $(PY_SRC)

lint-fix-ts: $(TS_SRC)
	$(BIOME) lint $(BIOME_FLAGS) --write $(TS_SRC)

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
	$(UV) test__update_examples_readme.py $(PYTEST_ARGS)

test-ts:
	bun test --cwd $(THIS_DIR)

test-cov: test-cov-py test-cov-ts

test-cov-py:
	$(UV) test__update_examples_readme.py $(PYTEST_ARGS) \
		--cov=_update_examples_readme --cov-report=term-missing --cov-fail-under=90

# test-cov-ts enforces a 90% coverage floor on both function and line coverage.
# Bun 1.3.7's bunfig `coverageThreshold` key is documented to fail the run
# when unmet but is silently non-enforcing in this version, so we parse the
# "All files" row of the text reporter and fail the target ourselves. That
# ensures the instrumentation is loud — coverage regressions exit non-zero
# with a clearly-labeled message, not a generic make error.
#
# CRITICAL: the `bun test | tee` pipeline needs `set -o pipefail` — without
# it `$?` captures tee's exit code (always 0), not bun's, so failing tests
# silently pass. Historical bug. We also explicitly tell make to use bash
# (rather than dash/sh) via SHELL so pipefail is available. Every shell line
# in this recipe runs in ONE sub-shell (backslash continuation), so the
# `set -o pipefail` at the top applies to the whole recipe.
COVERAGE_THRESHOLD = 90
SHELL := /bin/bash
test-cov-ts:
	@set -o pipefail; \
	bun test --cwd $(THIS_DIR) --coverage 2>&1 | tee $(THIS_DIR)tmp-cov.log; \
	bun_status=$$?; \
	line="$$(grep '^All files' $(THIS_DIR)tmp-cov.log || true)"; \
	funcs=$$(printf '%s' "$$line" | awk -F'|' '{gsub(/ /,""); print $$2}'); \
	lines=$$(printf '%s' "$$line" | awk -F'|' '{gsub(/ /,""); print $$3}'); \
	rm -f $(THIS_DIR)tmp-cov.log; \
	if [ $$bun_status -ne 0 ]; then \
		printf "\n[FAIL] test-cov-ts: bun test exited %s (failing tests)\n" "$$bun_status" >&2; \
		exit $$bun_status; \
	fi; \
	if [ -z "$$funcs" ] || [ -z "$$lines" ]; then \
		printf "\n[FAIL] test-cov-ts: could not parse coverage totals from bun output\n" >&2; \
		exit 1; \
	fi; \
	if awk -v f="$$funcs" -v l="$$lines" -v t=$(COVERAGE_THRESHOLD) 'BEGIN { exit (f+0 < t || l+0 < t) ? 1 : 0 }'; then \
		printf "\n[PASS] test-cov-ts: funcs=%s%% lines=%s%% (threshold %s%%)\n" "$$funcs" "$$lines" "$(COVERAGE_THRESHOLD)"; \
	else \
		printf "\n[FAIL] test-cov-ts: coverage below %s%% -- funcs=%s%% lines=%s%%\n" "$(COVERAGE_THRESHOLD)" "$$funcs" "$$lines" >&2; \
		exit 1; \
	fi

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

# End-to-end CLI demo of every public TS analyzer against fixture inputs.
# Non-zero exits are tolerated (demo showcases both pass and fail cases), so
# each command is prefixed with `-` to keep `make cli-demo` running to the end.
# Paths use $(THIS_DIR) / $(EXAMPLES_DIR) so the target works regardless of
# where `make -C` was invoked from.
cli-demo:
	@echo "=== mermaid_complexity.ts ==="
	-bun run $(THIS_DIR)mermaid_complexity.ts $(EXAMPLES_DIR)/test_complexity.md
	@echo ""
	@echo "=== mermaid_contrast.ts ==="
	-bun run $(THIS_DIR)mermaid_contrast.ts $(EXAMPLES_DIR)/test_contrast.md
	@echo ""
	@echo "=== color_contrast.ts: single pair (passes AA) ==="
	-bun run $(THIS_DIR)color_contrast.ts "#ffffff" "#2563eb"
	@echo ""
	@echo "=== color_contrast.ts: single pair (fails AA) ==="
	-bun run $(THIS_DIR)color_contrast.ts "#aaaaaa" "#ffffff"
	@echo ""
	@echo "=== color_contrast.ts: CSS color syntaxes (oklch + rgb) ==="
	-bun run $(THIS_DIR)color_contrast.ts "rgb(55 65 81)" "oklch(0.98 0 0)"
	@echo ""
	@echo "=== color_contrast.ts: batch via stdin, JSON output ==="
	-echo '[["#fff","#2563eb"],["#aaa","#fff"],["red","blue"]]' | bun run $(THIS_DIR)color_contrast.ts --stdin --json



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
