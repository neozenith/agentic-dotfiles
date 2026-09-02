# Quality gates for the librarian skill's scripts (mixed Python + TypeScript).
# Run from repo root: make -C .claude/skills/librarian/scripts <target>

# ── Python source ───────────────────────────────────────────────────────
PY_SCRIPTS = okf_render
PY_SRC = $(addsuffix .py,$(PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PY_SCRIPTS))) conftest.py

# ── TypeScript source ───────────────────────────────────────────────────
TS_SCRIPTS = md2yaml
TS_SRC = $(addsuffix .ts,$(TS_SCRIPTS)) $(addsuffix .test.ts,$(TS_SCRIPTS))

# ── Paths ───────────────────────────────────────────────────────────────
THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
EXAMPLE  := $(THIS_DIR)../resources/okf_yaml/example

# `--no-project` stops uv walking up and discovering a root pyproject.toml.
UV = uv run --no-project
PYTEST_ARGS = -v --rootdir . -o 'addopts='

# biome via bunx so it stays out of package.json; --bun pins the runtime.
BIOME = bunx --bun @biomejs/biome

.PHONY: all help clean install \
        format format-py format-ts format-check format-check-py format-check-ts \
        lint lint-py lint-ts lint-fix lint-fix-py lint-fix-ts \
        typecheck typecheck-py typecheck-ts \
        test test-py test-ts test-cov test-cov-py test-cov-ts \
        docs ci fix

all: format lint typecheck test-cov docs

# ── Format ──────────────────────────────────────────────────────────────
format: format-py format-ts
format-py:       ; $(UV) --with ruff ruff format --line-length 110 $(PY_SRC)
format-ts:       ; $(BIOME) format --write $(TS_SRC)
format-check: format-check-py format-check-ts
format-check-py: ; $(UV) --with ruff ruff format --check --line-length 110 $(PY_SRC)
format-check-ts: ; $(BIOME) format $(TS_SRC)

# ── Lint ────────────────────────────────────────────────────────────────
lint: lint-py lint-ts
lint-py:         ; $(UV) --with ruff ruff check --line-length 110 $(PY_SRC)
lint-ts:         ; $(BIOME) lint $(TS_SRC)
lint-fix: lint-fix-py lint-fix-ts
lint-fix-py:     ; $(UV) --with ruff ruff check --fix --line-length 110 $(PY_SRC)
lint-fix-ts:     ; $(BIOME) lint --write $(TS_SRC)

# ── Typecheck ───────────────────────────────────────────────────────────
typecheck: typecheck-py typecheck-ts
typecheck-py:
	$(UV) --with mypy --with types-PyYAML --with Jinja2 --with jsonschema \
		mypy $(addsuffix .py,$(PY_SCRIPTS)) --ignore-missing-imports --strict
# Invoke local tsc directly — `bunx tsc` has dep-resolution quirks when cwd differs.
typecheck-ts:    ; $(THIS_DIR)node_modules/.bin/tsc --project $(THIS_DIR)tsconfig.json --noEmit

# ── Test ────────────────────────────────────────────────────────────────
test: test-py test-ts
test-py:         ; $(UV) $(THIS_DIR)test_okf_render.py $(PYTEST_ARGS)
test-ts:         ; bun test --cwd $(THIS_DIR)

test-cov: test-cov-py test-cov-ts
test-cov-py:
	$(UV) $(THIS_DIR)test_okf_render.py $(PYTEST_ARGS) \
		--cov=okf_render --cov-report=term-missing --cov-fail-under=90
test-cov-ts:     ; bun test --cwd $(THIS_DIR) --coverage --coverage-threshold=0.90

# ── Docs / Misc ─────────────────────────────────────────────────────────
# Regenerate the shipped example bundle: it is the golden fixture the Python
# suite diffs against, so a template change must be reflected here.
docs:
	$(UV) --with PyYAML --with Jinja2 --with jsonschema \
		$(THIS_DIR)okf_render.py $(EXAMPLE)

install:         ; bun install --cwd $(THIS_DIR)

ci: format-check lint typecheck test-cov docs
fix: format lint-fix

clean:
	rm -rf $(THIS_DIR)__pycache__ $(THIS_DIR).pytest_cache $(THIS_DIR).mypy_cache \
	       $(THIS_DIR).ruff_cache $(THIS_DIR).coverage $(THIS_DIR)tmp

help:
	@echo "fix  — format + lint --write, both languages (mutates)"
	@echo "ci   — format-check, lint, typecheck, test-cov, docs (the gate)"
