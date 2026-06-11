# Makefile for the mingrammer_diagrams skill scripts (Python-only)
# Run from repo root: make -C .claude/skills/mingrammer_diagrams/scripts <target>
#
# The public "scripts" of this skill are the runnable diagram examples under
# resources/examples/*.py (content, not scripts/). The only file gated here is
# the private gallery generator, _update_examples_readme.py.

# ── Python source ──────────────────────────────────────────────────────────

# No public Python scripts (diagram examples live in resources/examples/).
PY_SCRIPTS =

# Private maintenance helper — regenerates resources/examples/README.md.
PRIVATE_PY_SCRIPTS = _update_examples_readme

PY_SRC = $(addsuffix .py,$(PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PY_SCRIPTS))) \
         $(addsuffix .py,$(PRIVATE_PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PRIVATE_PY_SCRIPTS)))

# ── Paths ──────────────────────────────────────────────────────────────────

THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
EXAMPLES_DIR := $(abspath $(THIS_DIR)../resources/examples)
EXAMPLES_README := $(EXAMPLES_DIR)/README.md
EXAMPLE_SRCS := $(sort $(wildcard $(EXAMPLES_DIR)/*.py))

# --no-project prevents uv from discovering the root pyproject.toml, which
# would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project

# Isolate pytest from any root pyproject.toml config (plugins/warning filters
# that aren't in our minimal PEP-723 test env).
PYTEST_ARGS = -v -c /dev/null --rootdir .

.PHONY: all help clean diagrams \
        format format-py format-check format-check-py \
        lint lint-py lint-fix lint-fix-py \
        typecheck typecheck-py \
        test test-py test-cov test-cov-py \
        docs ci fix

# Default target
all: format lint typecheck test-cov docs

# ── Format ─────────────────────────────────────────────────────────────────

format: format-py
format-py:
	$(UV) ruff format $(PY_SRC)

format-check: format-check-py
format-check-py:
	$(UV) ruff format --check $(PY_SRC)

# ── Lint ───────────────────────────────────────────────────────────────────

lint: lint-py
lint-py:
	$(UV) ruff check --line-length 120 $(PY_SRC)

lint-fix: lint-fix-py
lint-fix-py:
	$(UV) ruff check --fix --line-length 120 $(PY_SRC)

# ── Typecheck ──────────────────────────────────────────────────────────────

typecheck: typecheck-py
typecheck-py:
	$(UV) mypy $(addsuffix .py,$(PRIVATE_PY_SCRIPTS)) --ignore-missing-imports --strict

# ── Test ───────────────────────────────────────────────────────────────────

test: test-py
test-py:
	$(UV) test__update_examples_readme.py $(PYTEST_ARGS)

test-cov: test-cov-py
test-cov-py:
	$(UV) test__update_examples_readme.py $(PYTEST_ARGS) \
		--cov=_update_examples_readme --cov-report=term-missing --cov-fail-under=90

# ── Docs ───────────────────────────────────────────────────────────────────

# Regenerate the examples gallery README from .py + .png pairs, then populate
# its <!--TOC--> markers. Wired into `ci`.
docs:
	$(UV) _update_examples_readme.py
	uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 2 $(EXAMPLES_README)

# ── Diagrams (render PNGs — requires Graphviz `dot` on PATH) ────────────────

# Re-render every example PNG by running its self-rendering source. NOT part of
# `ci` (needs Graphviz + the diagrams lib); run it when you add/edit an example.
diagrams:
	@for f in $(EXAMPLE_SRCS); do echo "render $$(basename $$f)"; $(UV) "$$f" || exit $$?; done

# ── CI / fix ───────────────────────────────────────────────────────────────

ci: format-check lint typecheck test-cov docs
fix: format lint-fix

clean:
	rm -f *.pyc
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

help:
	@echo "Targets (run from repo root via make -C .claude/skills/mingrammer_diagrams/scripts):"
	@echo "  all        - format + lint + typecheck + test-cov + docs (default)"
	@echo "  fix        - format + lint-fix (mutates source)"
	@echo "  ci         - format-check + lint + typecheck + test-cov + docs (the gate)"
	@echo "  diagrams   - re-render every resources/examples/*.png (needs Graphviz)"
	@echo "  docs       - regenerate resources/examples/README.md gallery"
	@echo "  clean      - remove caches and temp files"
