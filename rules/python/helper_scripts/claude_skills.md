---
paths:
  - ".claude/skills/**/scripts/*.py"
---

# Claude Skills Script Conventions

Rules for Python scripts in `.claude/skills/{skill-name}/scripts/`.

## Required Sibling Files

Every Python script `{name}.py` in a skill's scripts directory MUST have these sibling files:

```
.claude/skills/{skill-name}/scripts/
├── {name}.py           # Main script with PEP-723 metadata
├── {name}.sh           # Shell wrapper for uv run
├── test_{name}.py      # Pytest test file (PEP-723 entry point)
├── conftest.py         # Coverage reload fixture
└── Makefile            # Build automation
```

## Python Script Structure (`{name}.py`)

### PEP-723 Inline Script Metadata

Always include inline script metadata at the top:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
```

Add dependencies only when absolutely necessary. Prefer pure Python solutions.

### Module-Level Organization

```python
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

log = logging.getLogger(__name__)

# ============================================================================
# Core Classes/Functions
# ============================================================================

# ... implementation ...

# ============================================================================
# CLI Interface
# ============================================================================

def main(args: argparse.Namespace) -> None:
    """Main entry point."""
    # ... dispatch logic ...

if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(...)
    # ... argparse setup ...
    main(parser.parse_args())
```

### Dependency Injection for Testability

Functions that use global paths should accept optional parameters:

```python
# ✅ CORRECT - allows testing with temp directories
def process_data(cache: CacheManager, data_path: Path | None = None) -> dict:
    if data_path is None:
        data_path = DEFAULT_DATA_PATH
    # ...

# ✅ CORRECT - main() accepts optional dependencies
def main(args: argparse.Namespace, cache: CacheManager | None = None) -> None:
    owns_cache = cache is None
    if owns_cache:
        cache = CacheManager()
    # ...
```

## Shell Wrapper (`{name}.sh`)

Minimal wrapper that invokes uv run:

```bash
#!/usr/bin/env bash
# Wrapper script for {name}.py
# Claude Code skills cannot directly invoke `uv`, so this wrapper is needed.
#
# Usage: {name}.sh [command] [args...]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run "$SCRIPT_DIR/{name}.py" "$@"
```

## Test File (`test_{name}.py`)

### PEP-723 Metadata with Test Dependencies

Test files are **PEP-723 scripts** that invoke pytest via `__main__`. All dependencies
(including pytest itself) are declared in the inline metadata — `uv run` resolves them
without needing a project-level `pyproject.toml`.

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
```

### `__main__` Entry Point

Tests run as `uv run test_{name}.py`, NOT as `uv run pytest test_{name}.py`.
The test file itself is the entry point:

```python
if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    extra_args = sys.argv[1:]
    sys.exit(pytest.main(base_args + extra_args))
```

**Why `--rootdir` and `-o addopts=`?** These isolate the test run from any
`pyproject.toml` higher in the directory tree. Without them, pytest discovers
the root project's `[tool.pytest.ini_options]` and injects unrelated coverage
config or addopts, causing coverage to report 0% or target the wrong modules.

### No Mocks Policy

**NEVER use mocks.** Test real code with real dependencies:

```python
# ✅ CORRECT - real fixtures
@pytest.fixture
def temp_cache(temp_dir: Path) -> CacheManager:
    db_path = temp_dir / "test_cache.db"
    cache = CacheManager(db_path=db_path)
    cache.init_schema()
    return cache

# ✅ CORRECT - use capsys for output capture
def test_main_command(temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(command="status")
    main(args, cache=cache)
    captured = capsys.readouterr()
    assert "status" in captured.out

# ✅ CORRECT - use real argparse.Namespace
def _make_args(self, **kwargs: Any) -> Namespace:
    defaults = {"command": None, "format": "json"}
    defaults.update(kwargs)
    return Namespace(**defaults)
```

### Standard Fixtures

```python
@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
```

### Coverage Requirements

- **Minimum 90% coverage** required
- Use `# pragma: no cover` only for `if __name__ == "__main__":` block

## Coverage Reload Fixture (`conftest.py`)

When tests run via PEP-723 entry point (`uv run test_{name}.py`), the module under
test is imported **before** `pytest.main()` starts coverage tracing. Module-level code
(imports, constants, SQL schemas, class definitions) executes "in the dark" and reports
0% coverage.

The fix is a `conftest.py` that reloads the module after coverage activates:

```python
"""Standalone test configuration for PEP-723 skill scripts.

When tests run via __main__ (PEP-723 entry point), the module under test
is imported before pytest.main() starts coverage tracing. This conftest
reloads it after coverage activates so module-level statements are traced.
"""

from __future__ import annotations

import importlib

import {name} as mod
import pytest


@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    """Reload module under test so pytest-cov captures module-level code."""
    importlib.reload(mod)
```

**Why this works:** pytest-cov starts its tracer during `pytest_sessionstart`,
which fires *after* conftest.py loads but *before* session-scoped fixtures run.
The `importlib.reload()` re-executes every module-level statement under active
tracing, recovering the ~10-17% coverage that would otherwise be invisible.

## Makefile

Standard targets for all skill scripts. Key design decisions:

- **`--no-project`** prevents `uv` from walking up to discover a root `pyproject.toml`
- **PEP-723 entry point** — tests run as `$(UV) test_{name}.py`, not `$(UV) pytest test_{name}.py`
- **`PYTEST_ARGS`** isolates pytest from inherited config (rootdir, addopts)

```makefile
# Makefile for {name} scripts
# Run from repo root: make -C .claude/skills/{skill}/scripts <target>

# Source files
SRC = {name}.py test_{name}.py

# --no-project prevents uv from discovering the root pyproject.toml,
# which would otherwise inject unrelated coverage config and deps.
UV = uv run --no-project

# Shared pytest args to isolate from root pyproject.toml config
PYTEST_ARGS = -v --rootdir . -o 'addopts='

.PHONY: all test test-cov format format-check lint lint-fix typecheck check fix clean help smoke

# Default target
all: format lint typecheck test

# Run tests via PEP-723 entry point (deps declared in test file)
test:
	$(UV) test_{name}.py $(PYTEST_ARGS)

# Run tests with coverage — via same PEP-723 entry point
test-cov:
	$(UV) test_{name}.py $(PYTEST_ARGS) \
		--cov={name} --cov-report=term-missing --cov-fail-under=90

# Format code with ruff
format:
	$(UV) ruff format $(SRC)

# Check formatting without modifying (for CI)
format-check:
	$(UV) ruff format --check $(SRC)

# Lint with ruff (line-length 120 for SQL strings and long docstrings)
lint: format
	$(UV) ruff check --line-length 120 $(SRC)

# Lint and auto-fix
lint-fix: format
	$(UV) ruff check --fix --line-length 120 $(SRC)

# Type check with mypy
typecheck: fix
	$(UV) mypy {name}.py --ignore-missing-imports --strict

# Run all checks (CI-friendly)
check: format-check lint typecheck

# Run all auto-fixers (local development)
fix: format lint-fix

# Quick CLI smoke test
smoke:
	./{name}.sh --help

# Clean up cache and temp files
clean:
	rm -f *.pyc
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

# Show help
help:
	@echo "Available targets:"
	@echo "  all         - Run format, lint, typecheck, and test (default)"
	@echo "  test        - Run pytest tests"
	@echo "  test-cov    - Run tests with coverage report"
	@echo "  format      - Format code with ruff"
	@echo "  format-check- Check formatting without modifying"
	@echo "  lint        - Lint code with ruff"
	@echo "  lint-fix    - Lint and auto-fix issues"
	@echo "  typecheck   - Type check with mypy"
	@echo "  check       - Run all checks (CI-friendly)"
	@echo "  fix         - Run all auto-fixers"
	@echo "  smoke       - Quick CLI smoke test"
	@echo "  clean       - Remove temp files and caches"
```

## Running Quality Checks

Always run from project root using `make -C`:

```bash
# Run all checks
make -C .claude/skills/{skill}/scripts all

# Run tests with coverage
make -C .claude/skills/{skill}/scripts test-cov

# Auto-fix formatting and lint issues
make -C .claude/skills/{skill}/scripts fix
```
