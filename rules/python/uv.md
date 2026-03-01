# Python Tooling: Always Use uv

## Core Rule

**Always use `uv` for all Python operations.** Never fall back to `.venv/bin/python`, `python`, `pip`, or any other direct invocation.

## Running Scripts and Modules

```bash
# Run a module from project root
uv run -m mypackage.module

# Run a script
uv run scripts/analyze.py

# Run without syncing (env already correct, or offline)
uv run --no-sync -m mypackage.module
uv run --frozen -m mypackage.module
```

**`--no-sync`** — skip environment sync entirely, use existing `.venv` as-is. Use when offline or when the env is known good.
**`--frozen`** — use lockfile as-is, skip up-to-date check. Use in CI or reproducible runs.

## Managing Dependencies

```bash
# Add a dependency (updates pyproject.toml + uv.lock)
uv add somelib

# Add multiple dependencies
uv add libA libB libC

# Add a dev dependency
uv add --dev pytest ruff

# Sync environment to lockfile
uv sync

# Sync without dev deps
uv sync --no-dev
```

**NEVER use `uv pip install`** — it bypasses `pyproject.toml` tracking. Always use `uv add`.

## Subdirectory Projects

For self-contained subprojects with their own `pyproject.toml`:

```bash
uv run --directory subproject pytest
uv run --directory subproject -m mypackage.module
```

This keeps you at the project root while activating the correct `.venv` for that subproject. Never `cd` into a subdirectory — see the `CLAUDE.md` working directory rules.

## What NOT to Do

```bash
# WRONG — never invoke python directly
.venv/bin/python -m mypackage.module
python scripts/analyze.py

# WRONG — never use pip or uv pip install
pip install somelib
uv pip install somelib

# WRONG — never cd to use uv
cd subproject && uv run pytest
```
