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
├── test_{name}.py      # Pytest test file
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

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
```

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

## Makefile

Standard targets for all skill scripts:

```makefile
# Makefile for {name} scripts
# Run from repo root: make -C .claude/skills/{skill}/scripts <target>

.PHONY: all test format lint typecheck check fix clean help smoke

# Default target
all: format lint typecheck test

# Run tests with pytest
test:
	uv run pytest test_{name}.py -v

# Run tests with coverage
test-cov:
	uv run --with pytest-cov pytest test_{name}.py -v --cov={name} --cov-report=term-missing

# Format code with ruff
format:
	uv run ruff format {name}.py test_{name}.py

# Check formatting without modifying (for CI)
format-check:
	uv run ruff format --check {name}.py test_{name}.py

# Lint with ruff (line-length 120)
lint: format
	uv run ruff check --line-length 120 {name}.py test_{name}.py

# Lint and auto-fix
lint-fix: format
	uv run ruff check --fix --line-length 120 {name}.py test_{name}.py

# Type check with mypy
typecheck: fix
	uv run mypy {name}.py --ignore-missing-imports --strict

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
	@echo "  lint        - Lint code with ruff"
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
