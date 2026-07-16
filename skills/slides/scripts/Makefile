# Quality gates for the `slides` skill's scripts (Python-only).
# Run from repo root: make -C .claude/skills/slides/scripts <target>

# ── Python source ───────────────────────────────────────────────────────
PY_SCRIPTS = scaffold_deck tier_progress slide_durations prose_check

PY_SRC = $(addsuffix .py,$(PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PY_SCRIPTS))) conftest.py

# ── Paths ──────────────────────────────────────────────────────────────
THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# `--no-project` prevents uv from walking up and discovering a root pyproject.toml.
# The test files carry their own PEP-723 deps; ruff/mypy are one-off tools, so they
# are injected with --with rather than assumed to be on PATH.
UV = uv run --no-project
RUFF = $(UV) --with ruff ruff
MYPY = $(UV) --with mypy mypy
PYTEST_ARGS = -v --rootdir . -o 'addopts='

.PHONY: all help clean \
        format format-py \
        format-check format-check-py \
        lint lint-py \
        lint-fix lint-fix-py \
        typecheck typecheck-py \
        test test-py \
        test-cov test-cov-py \
        ci fix

all: format lint typecheck test-cov

# ── Format ──────────────────────────────────────────────────────────────
format: format-py
format-py:       ; $(RUFF) format --line-length 120 $(PY_SRC)
format-check: format-check-py
format-check-py: ; $(RUFF) format --check --line-length 120 $(PY_SRC)

# ── Lint ────────────────────────────────────────────────────────────────
lint: lint-py
lint-py:         ; $(RUFF) check --line-length 120 $(PY_SRC)
lint-fix: lint-fix-py
lint-fix-py:     ; $(RUFF) check --fix --line-length 120 $(PY_SRC)

# ── Typecheck ──────────────────────────────────────────────────────────
typecheck: typecheck-py
typecheck-py:    ; $(MYPY) $(addsuffix .py,$(PY_SCRIPTS)) --ignore-missing-imports --strict

# ── Test ────────────────────────────────────────────────────────────────
test: test-py
test-py:
	$(UV) test_tier_progress.py $(PYTEST_ARGS)
	$(UV) test_slide_durations.py $(PYTEST_ARGS)
	$(UV) test_prose_check.py $(PYTEST_ARGS)
	$(UV) test_scaffold_deck.py $(PYTEST_ARGS)

test-cov: test-cov-py
test-cov-py:
	$(UV) test_tier_progress.py $(PYTEST_ARGS) \
		--cov=tier_progress --cov-report=term-missing --cov-fail-under=90
	$(UV) test_slide_durations.py $(PYTEST_ARGS) \
		--cov=slide_durations --cov-report=term-missing --cov-fail-under=90
	$(UV) test_prose_check.py $(PYTEST_ARGS) \
		--cov=prose_check --cov-report=term-missing --cov-fail-under=90
	$(UV) test_scaffold_deck.py $(PYTEST_ARGS) \
		--cov=scaffold_deck --cov-report=term-missing --cov-fail-under=90

ci: format-check lint typecheck test-cov
fix: format lint-fix

clean:
	rm -f *.pyc
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

help:
	@echo "Targets: format format-check lint lint-fix typecheck test test-cov ci fix clean all"
