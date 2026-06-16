# Evals for this skill — contract: .claude/rules/claude_skills/evals.md
# Run from repo root: make -C .claude/skills/<name>/scripts <target>

UV := uv run --no-project
THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
EVALKIT := $(THIS_DIR)../../_evalkit

.PHONY: evals evals-nightly ci fix

# Paid tier: one cheap-model run per golden (needs claude CLI + ANTHROPIC_API_KEY).
evals:
	DEEPEVAL_TELEMETRY_OPT_OUT=1 $(UV) evals/test_evals.py

# Full model matrix incl. codex (dollars; nightly/on-demand).
evals-nightly:
	DEEPEVAL_TELEMETRY_OPT_OUT=1 \
	EVAL_MODELS="claude-haiku-4-5,claude-sonnet-4-6,claude-opus-4-8" \
	CODEX_EVAL_MODELS="gpt-5.5" \
	$(UV) evals/test_evals.py

# Free gate: lint this suite + shared-harness self-tests. Never calls an LLM.
ci:
	uvx ruff format --check evals/test_evals.py
	uvx ruff check --line-length 120 evals/test_evals.py
	$(MAKE) -C $(EVALKIT) test

fix:
	uvx ruff format evals/test_evals.py
	uvx ruff check --line-length 120 --fix evals/test_evals.py
