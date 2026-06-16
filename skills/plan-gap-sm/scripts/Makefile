# Makefile for plan-gap-sm scripts.
# Run from repo root: make -C .claude/skills/plan-gap-sm/scripts <target>

PY_SCRIPTS = pgsm trajectory rollout
PY_TESTS = $(addprefix test_,$(PY_SCRIPTS))
PY_SRC = $(addsuffix .py,$(PY_SCRIPTS)) $(addsuffix .py,$(PY_TESTS)) conftest.py evals/test_evals.py

# --no-project prevents uv from discovering the root pyproject.toml,
# which would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project
PYTEST_ARGS = -v --rootdir . -o 'addopts='

.PHONY: all debug help clean \
        format format-check lint lint-fix typecheck \
        test test-cov ci fix evals evals-nightly

all: format lint typecheck test-cov

debug:
	@echo "Makefile dir (PWD): $(PWD)"

# ── Format / lint / typecheck ───────────────────────────────────────────
format:
	$(UV) ruff format $(PY_SRC)

format-check:
	$(UV) ruff format --check $(PY_SRC)

lint:
	$(UV) ruff check --line-length 120 $(PY_SRC)

lint-fix:
	$(UV) ruff check --fix --line-length 120 $(PY_SRC)

typecheck:
	$(UV) mypy $(addsuffix .py,$(PY_SCRIPTS)) --ignore-missing-imports --strict

# ── Tests (free, deterministic — no LLM calls) ──────────────────────────
test:
	$(UV) test_pgsm.py $(PYTEST_ARGS)
	$(UV) test_trajectory.py $(PYTEST_ARGS)
	$(UV) test_rollout.py $(PYTEST_ARGS)

test-cov:
	$(UV) test_pgsm.py $(PYTEST_ARGS) \
		--cov=pgsm --cov-report=term-missing --cov-fail-under=90
	$(UV) test_trajectory.py $(PYTEST_ARGS) \
		--cov=trajectory --cov-report=term-missing --cov-fail-under=90
	$(UV) test_rollout.py $(PYTEST_ARGS) \
		--cov=rollout --cov-report=term-missing --cov-fail-under=90

# ── Gates ────────────────────────────────────────────────────────────────
ci: format-check lint typecheck test-cov

fix: format lint-fix

# ── Evals (REAL agent runs — spends money; never part of ci) ────────────
evals:
	$(UV) evals/test_evals.py $(PYTEST_ARGS)

evals-nightly:
	EVAL_MODELS=claude-haiku-4-5,claude-sonnet-4-6,claude-opus-4-8 \
		$(UV) evals/test_evals.py $(PYTEST_ARGS)

clean:
	rm -f *.pyc .coverage
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov

help:
	@echo "Targets: fix ci | format format-check lint lint-fix typecheck test test-cov | evals evals-nightly | clean"
	@echo "Usage from repo root: make -C .claude/skills/plan-gap-sm/scripts ci"
