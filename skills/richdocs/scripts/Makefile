# Shared Makefile for all richdocs skill scripts (pure Python).
# Run from repo root: make -C .claude/skills/richdocs/scripts <target>

# ── Python source ──────────────────────────────────────────────────────────

# Public Python scripts (referenced in SKILL.md)
PY_SCRIPTS = serve stencil md2html showcase themecheck

# Private scripts: maintenance helpers for the skill itself (none yet)
PRIVATE_PY_SCRIPTS =

PY_SRC = $(addsuffix .py,$(PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PY_SCRIPTS))) \
         $(addsuffix .py,$(PRIVATE_PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PRIVATE_PY_SCRIPTS))) \
         conftest.py

# ── Paths ──────────────────────────────────────────────────────────────────

THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# --no-project prevents uv from discovering the root pyproject.toml,
# which would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project

# Isolate pytest from any root pyproject.toml config (addopts, plugins).
PYTEST_ARGS = -v -c /dev/null --rootdir .

.PHONY: themecheck all debug help clean \
        format format-py \
        format-check format-check-py \
        lint lint-py \
        lint-fix lint-fix-py \
        typecheck typecheck-py \
        test test-py \
        test-cov test-cov-py \
        ci fix

# Default target
all: format lint typecheck test-cov

debug:
	echo $(MAKEFILE_LIST)
	echo $(THIS_DIR)
	echo $(PY_SRC)

# ── Format ─────────────────────────────────────────────────────────────────

format: format-py

format-py: $(PY_SRC)
	$(UV) ruff format $(PY_SRC)

format-check: format-check-py

format-check-py: $(PY_SRC)
	$(UV) ruff format --check $(PY_SRC)

# ── Lint ───────────────────────────────────────────────────────────────────

lint: lint-py

lint-py: $(PY_SRC)
	$(UV) ruff check --line-length 120 $(PY_SRC)

lint-fix: lint-fix-py

lint-fix-py: $(PY_SRC)
	$(UV) ruff check --fix --line-length 120 $(PY_SRC)

# ── Typecheck ──────────────────────────────────────────────────────────────

typecheck: typecheck-py

# mypy resolved hermetically via `uv run --with mypy` — no system install assumed.
typecheck-py: $(addsuffix .py,$(PY_SCRIPTS) $(PRIVATE_PY_SCRIPTS))
	$(UV) --with mypy mypy $(addsuffix .py,$(PY_SCRIPTS) $(PRIVATE_PY_SCRIPTS)) --ignore-missing-imports --strict

# ── Test ───────────────────────────────────────────────────────────────────

test: test-py

# PEP-723 entry points — deps declared in each test file itself
test-py:
	$(UV) test_serve.py $(PYTEST_ARGS)
	$(UV) test_stencil.py $(PYTEST_ARGS)
	$(UV) test_md2html.py $(PYTEST_ARGS)
	$(UV) test_showcase.py $(PYTEST_ARGS)
	$(UV) test_themecheck.py $(PYTEST_ARGS)

test-cov: test-cov-py

test-cov-py:
	$(UV) test_serve.py $(PYTEST_ARGS) \
		--cov=serve --cov-report=term-missing --cov-fail-under=90
	$(UV) test_stencil.py $(PYTEST_ARGS) \
		--cov=stencil --cov-report=term-missing --cov-fail-under=90
	$(UV) test_md2html.py $(PYTEST_ARGS) \
		--cov=md2html --cov-report=term-missing --cov-fail-under=90
	$(UV) test_showcase.py $(PYTEST_ARGS) \
		--cov=showcase --cov-report=term-missing --cov-fail-under=90
	$(UV) test_themecheck.py $(PYTEST_ARGS) \
		--cov=themecheck --cov-report=term-missing --cov-fail-under=90

# ── CI / Fix / Misc ────────────────────────────────────────────────────────

# Run all checks with coverage enforcement (CI standard).
ci: format-check lint typecheck test-cov themecheck

# Run all auto-fixers (local development)
# The brandpack gate: a theme that renders unreadable text must not ship.
themecheck:
	$(UV) themecheck.py

fix: format lint-fix

# Clean up cache and temp files
clean:
	rm -f *.pyc
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

# Show help
help:
	@echo "Composite targets:"
	@echo "  all          - format + lint + typecheck + test-cov (default)"
	@echo "  format       - Auto-format source"
	@echo "  format-check - Check formatting without modifying (CI-safe)"
	@echo "  lint         - Lint source (non-mutating)"
	@echo "  lint-fix     - Lint and auto-fix"
	@echo "  typecheck    - Type check public scripts (mypy --strict)"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage (>=90%)"
	@echo "  ci           - format-check + lint + typecheck + test-cov"
	@echo "  fix          - format + lint-fix"
	@echo "  clean        - Remove temp files and caches"
