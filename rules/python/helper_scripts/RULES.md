---
paths:
  - "scripts/**/*.py"
  - "**/scripts/*.py"
---

# Python Helper Scripts

Rules for standalone Python scripts using PEP-723 inline metadata.

> Extends `python/RULES.md` for standalone scripts.

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

## References

Conditional rule files that extend this base. Each activates based on its frontmatter `paths:` globs:

- [boilerplate.md](boilerplate.md) — Full implementation templates (PEP-723 metadata, argparse, logging, caching). Use when **creating a new script from scratch**.
- [manifest_pattern.md](manifest_pattern.md) — Subcommand-based CLI for permutation pipelines with staged builds, hierarchical logging, and self-command generation. Use when a script **generates multiple output artifacts from a cross-product of parameters**.
- [triage.md](triage.md) — Conventions for `triage_*.py` scripts that collate logs/tests and suggest next steps. Use when writing a script whose **verb is `triage`**.
- [aws.md](aws.md) — AWS service interaction rules (authentication, boto3 patterns, error handling). Use when a script **calls AWS APIs or uses boto3/CDK**.
- [ml_huggingface.md](ml_huggingface.md) — HuggingFace `transformers` pipeline conventions, including the deferred-import exception for heavy ML libraries. Use when a script **loads ML models via HuggingFace**.
- [claude_skills.md](claude_skills.md) — Conventions for scripts inside `.claude/skills/*/scripts/`. Use when writing **Python scripts that are part of a Claude skill**.
