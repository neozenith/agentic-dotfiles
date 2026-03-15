---
paths:
  - "scripts/**/*.py"
  - "**/scripts/*.py"
---

# Python Helper Scripts

Rules for standalone Python scripts using PEP-723 inline metadata.

> Extends `../RULES.md` for standalone scripts.

Detailed snippets [boilerplate](boilerplate.md) and [conventions](../RULES.md) apply.

## Execution

- **Always run with `uv`**: `uv run scripts/script_name.py`
- **Never use `python -c '...'`**: Create a script file instead
- **Support `--help`**: All scripts must be self-documenting

## PEP-723 Inline Dependencies

Every script must declare dependencies at the top:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "python-dotenv>=1.0.0",
# ]
# ///
```

## Structure

### Configuration at Top

All config variables CAPITALIZED below imports:

```python
SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent

CACHE_DIR = PROJECT_ROOT / "tmp" / "claude_cache" / SCRIPT_NAME
```

### Helper Lambdas

Use `# noqa: E731` for concise one-liners:

```python
_run = lambda cmd: subprocess.check_output(split(cmd), text=True).strip()  # noqa: E731
_is_cache_valid = lambda t: all(x > 0 for x in t)  # noqa: E731
```

## CLI Arguments

**DO NOT replace CAPITALISED config variables with CLI arguments or flags.**

Required flags:
- `-v/--verbose`: Debug logging
- `-q/--quiet`: Errors only

Optional flags (add when needed):
- `-f/--force`: Ignore cache
- `-n/--dry-run`: No changes
- `--cache-check`: Check cache status only
- `-L/--limit N`: Limit iterations
- `-T/--timeout N`: Self-imposed timeout

## Caching

- Output to `tmp/claude_cache/{script_name}/`
- Default timeout: 300 seconds (5 minutes)
- Implement `check_cache()` returning `(delta, remaining)` tuple

## Testing

- Test file as sibling: `scripts/test_{script_name}.py`
- Use pytest with PEP-723 dependencies
- Run standalone: `uv run scripts/test_script_name.py`
