---
paths:
  - "**/*.py"
---

# Python Code Conventions

Universal rules for all Python code.

## Imports

**All imports MUST be at the top of the file.** No exceptions.

```python
# ✅ CORRECT - all imports at top
import json
from pathlib import Path
from typing import Any

def my_function():
    data = json.loads(content)
```

```python
# ❌ FORBIDDEN - nested/conditional imports
def my_function():
    import json  # NEVER DO THIS
    from pathlib import Path  # NEVER DO THIS
```

**Why this matters:**
- Nested imports hide dependencies and make code harder to understand
- Import errors should fail fast at module load time, not at runtime
- Tools like linters and type checkers work better with top-level imports
- Performance: imports are cached, but the lookup still has overhead

## File Handling

**Always use `pathlib`**, never `os.path`:

```python
from pathlib import Path

# Reading files
content = path.read_text(encoding="utf-8")
data = json.loads(path.read_text(encoding="utf-8"))

# Writing files
path.write_text(content, encoding="utf-8")

# Path operations
full_path = base_dir / "subdir" / "file.json"
```

## Logging

- Use `logging` module, **never `print()` for output**
- Get logger at module level: `log = logging.getLogger(__name__)`
- Use appropriate levels: `debug`, `info`, `warning`, `error`

```python
import logging
log = logging.getLogger(__name__)

log.info("Processing %d items", count)  # Use % formatting, not f-strings
log.debug("Details: %s", details)
log.error("Failed to process: %s", error)
```

## Environment Variables

- Check for `.env.sample` to see available variables
- Use `python-dotenv` for loading:

```python
from dotenv import load_dotenv
load_dotenv()
```

## Git Integration

For code needing git context:

```python
import subprocess
from shlex import split

_run = lambda cmd: subprocess.check_output(split(cmd), text=True).strip()  # noqa: E731

GIT_ROOT = Path(_run("git rev-parse --show-toplevel"))
GIT_BRANCH = _run("git rev-parse --abbrev-ref HEAD")
```

## Testing

- Use `pytest` as the test framework
- Leverage parametrized tests for coverage with minimal code
- Write code that is easy to test (pure functions, dependency injection)

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("a", 1),
    ("b", 2),
])
def test_function(input, expected):
    assert function(input) == expected
```

## Quality Assurance

Run these tools regularly (ideally via `make fix` or `make lint`):

```bash
# Formatting
uvx ruff format . --respect-gitignore --line-length 120
uvx isort src/ tests/ scripts/

# Linting
uvx ruff check . --line-length 120 --respect-gitignore --fix-only
uvx ruff check . --line-length 120 --respect-gitignore --statistics

# Type checking
uvx mypy .

# Markdown (if applicable)
uvx --from md-toc md_toc --in-place github --header-levels 4 README.md
uvx rumdl check . --fix --respect-gitignore -d MD013
```

## Documentation

- When generating README.md, include MermaidJS architecture diagrams
- Use color to make diagram boxes visually distinct
- Ensure text color contrasts with background colors
- Use emoji in diagram box names for expressiveness

## Data Formats

**Avoid CSV** unless explicitly requested. Prefer:
- **In-memory**: pandas/Polars DataFrames, Arrow tables
- **Persistence**: Parquet, SQLite, DuckDB
- **Exchange**: JSON, Arrow IPC

```python
# DuckDB queries DataFrames directly - no temp files needed
import duckdb
import pandas as pd

df = pd.DataFrame({"col": [1, 2, 3]})
result = duckdb.sql("SELECT * FROM df WHERE col > 1")
```
