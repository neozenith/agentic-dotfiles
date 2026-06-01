# art-edit skill — Python-only quality gate.
# Run from repo root:  make -C .claude/skills/art-edit/scripts <target>
#
#   make -C .claude/skills/art-edit/scripts fix   # auto-format + lint-fix (mutates)
#   make -C .claude/skills/art-edit/scripts ci    # the gate (no mutation)

PY_SCRIPTS = art_edit
PY_SRC = art_edit.py test_art_edit.py

UV = uv run --no-project
PYTEST_ARGS = -v --rootdir . -o 'addopts='
COV_MIN = 90

.PHONY: all help clean \
        format format-py format-check format-check-py \
        lint lint-py lint-fix lint-fix-py \
        typecheck typecheck-py \
        test test-py test-cov test-cov-py \
        ci fix

all: format lint typecheck test-cov

# ── Format ──────────────────────────────────────────────────────────────
format: format-py
format-py:       ; $(UV) ruff format $(PY_SRC)
format-check: format-check-py
format-check-py: ; $(UV) ruff format --check $(PY_SRC)

# ── Lint ────────────────────────────────────────────────────────────────
lint: lint-py
lint-py:         ; $(UV) ruff check --line-length 120 $(PY_SRC)
lint-fix: lint-fix-py
lint-fix-py:     ; $(UV) ruff check --fix --line-length 120 $(PY_SRC)

# ── Typecheck ──────────────────────────────────────────────────────────
typecheck: typecheck-py
typecheck-py:    ; $(UV) mypy $(addsuffix .py,$(PY_SCRIPTS)) --ignore-missing-imports --strict

# ── Test ────────────────────────────────────────────────────────────────
test: test-py
test-py:         ; $(UV) test_art_edit.py $(PYTEST_ARGS)
test-cov: test-cov-py
test-cov-py:
	$(UV) test_art_edit.py $(PYTEST_ARGS) \
		--cov=art_edit --cov-report=term-missing --cov-fail-under=$(COV_MIN)

# ── Aggregate ──────────────────────────────────────────────────────────
ci: format-check lint typecheck test-cov
fix: format lint-fix

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov

help:
	@echo "Targets: fix (format+lint-fix), ci (gate), test, test-cov, typecheck, clean"
