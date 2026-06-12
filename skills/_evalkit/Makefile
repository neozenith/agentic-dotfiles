# Shared eval harness — offline self-tests are free and run in every skill's `make ci`.
# Run from repo root: make -C .claude/skills/_evalkit test

UV := uv run --no-project

.PHONY: test ci fix

test:
	$(UV) test_evalkit.py

ci:
	uvx ruff format --check evalkit.py test_evalkit.py
	uvx ruff check --line-length 120 evalkit.py test_evalkit.py
	$(MAKE) test

fix:
	uvx ruff format evalkit.py test_evalkit.py
	uvx ruff check --line-length 120 --fix evalkit.py test_evalkit.py
