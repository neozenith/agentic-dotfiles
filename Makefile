.PHONY: help xharness-local xharness-pypi xharness-status evals

TOGGLE := uv run --no-sync scripts/toggle_xharness_eval_editable.py

help:
	@echo "xharness-local   use the editable ../pytest-xharness-eval checkout, then uv sync"
	@echo "xharness-pypi    use the published pytest-xharness-eval release, then uv sync"
	@echo "xharness-status  print which source pyproject.toml currently points at"
	@echo "evals            run the paid skill eval matrix (uv run pytest skills/*/evals)"

# Both toggles are idempotent: re-running in the current state is a no-op edit
# followed by a no-op sync. `uv sync` re-locks when pyproject.toml drifts from
# uv.lock, so no separate `uv lock` step is needed.
xharness-local:
	$(TOGGLE) local
	uv sync

xharness-pypi:
	$(TOGGLE) pypi
	uv sync

xharness-status:
	@$(TOGGLE) status

evals:
	uv run pytest skills/*/evals -v

evals-list:
	uv run pytest skills/*/evals --collect-only -v

# Rebuild captured results, history and report.html from the captured session logs.
# No CLI runs, nothing is spent: use it after changing the plugin or xharness_skill_ignore.
evals-replay:
	uv run -m pytest_xharness_eval.replay skills/$(SKILL)/evals/captured

# Serve one skill's captured/report.html (it fetches the JSON beside it, so it needs HTTP).
# Usage: make evals-report SKILL=mermaidjs-diagrams
SKILL ?= mermaidjs-diagrams
evals-report:
	@test -f skills/$(SKILL)/evals/captured/report.html || { echo "no captured report for $(SKILL); run make evals first"; exit 1; }
	@echo "open http://localhost:8765/report.html"
	python3 -m http.server 8765 --directory skills/$(SKILL)/evals/captured
