---
paths:
  - "scripts/**/*.py"
  - "**/scripts/*.py"
---

# Helper Script Boilerplate

Full implementation templates for helper scripts.

## Complete Script Template

```python
#!/usr/bin/env python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///
"""
Brief description of what this script does.
"""
import argparse
import logging
import subprocess
from pathlib import Path
from shlex import split
from textwrap import dedent
from time import time

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# Helper lambdas
_run = lambda cmd: subprocess.check_output(split(cmd), text=True).strip()  # noqa: E731
_is_cache_valid = lambda t: all(x > 0 for x in t)  # noqa: E731

# Configuration
SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent

CACHE_DIR = PROJECT_ROOT / "tmp" / "claude_cache" / SCRIPT_NAME

# Input files
DATA_DIR = PROJECT_ROOT / "data"
INPUT_FILE_1 = DATA_DIR / "file1.json"
INPUT_FILE_2 = DATA_DIR / "file2.json"
ALL_INPUTS = [INPUT_FILE_1, INPUT_FILE_2]

# Output files
OUTPUT_SUMMARY = CACHE_DIR / "output_summary.json"
ALL_OUTPUTS = [OUTPUT_SUMMARY]


def check_cache(cache_dir: Path, all_input_files: list[Path], timeout: int = 300, force: bool = False) -> tuple[int, int]:
    """Check if cache is invalid, 'dirty' or expired.

    Returns tuple of (delta, remaining) where:
    - delta: time difference between cache and inputs (positive = cache newer)
    - remaining: time left before cache expires (positive = not expired)
    """
    if force or not cache_dir.exists():
        return (-1, -1)  # Both negative = forced dirty

    cache_mtime = max([0] + [f.stat().st_mtime for f in cache_dir.rglob('*') if f.is_file()])
    all_inputs_mtime = max([0] + [f.stat().st_mtime for f in all_input_files if f.is_file()])

    delta = int(cache_mtime - all_inputs_mtime)
    remaining = int(timeout - (time() - cache_mtime))

    return (delta, remaining)


def main(dry_run: bool = False, force: bool = False):
    """Main processing logic."""
    cache_status = check_cache(CACHE_DIR, ALL_INPUTS, force=force)
    if not _is_cache_valid(cache_status):
        log.info("Cache is invalid or expired, processing...")

        if dry_run:
            log.info("DRY RUN: Would process files but not write output")
            return

        # Main processing logic here
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    else:
        log.info("Cache is valid, skipping processing.")


def _format_file_list(files: list[Path], max_show: int = 5) -> str:
    """Format paths relative to project root."""
    formatted = '\n        '.join(f"- {p.relative_to(PROJECT_ROOT)}" for p in files[:max_show])
    if len(files) > max_show:
        formatted += f"\n        ... and {len(files) - max_show} more files"
    return formatted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(f"""\
        {SCRIPT_NAME} - Brief description of what this script does.

        INPUTS:
        {_format_file_list(ALL_INPUTS)}

        OUTPUTS:
        {_format_file_list(ALL_OUTPUTS)}

        CACHE: tmp/claude_cache/{SCRIPT_NAME}/
        """)
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Run script in quiet mode")
    parser.add_argument("-v", "--verbose", action="store_true", help="Run script in verbose mode")
    parser.add_argument("-f", "--force", action="store_true", help="Force reprocessing of all inputs.")
    parser.add_argument("-n", "--dry-run", action="store_true",
                       help="Run the script without making any output changes.")
    parser.add_argument("--cache-check", action="store_true",
                       help="ONLY Check if cache is up to date. Does not run main processing.")
    parser.add_argument("--limit", type=int, help="Limit the number of iterations")
    parser.add_argument("--timeout", type=int, help="Safe shutdown script after N seconds")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.ERROR if args.quiet else logging.INFO,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if args.cache_check:
        delta, remaining = check_cache(CACHE_DIR, ALL_INPUTS, force=args.force)
        if _is_cache_valid((delta, remaining)):
            log.info(f"Cache is up to date. Delta: {delta}s, Remaining: {remaining}s")
        else:
            log.warning(f"Cache is not up to date. Delta: {delta}s, Remaining: {remaining}s")
    else:
        main(dry_run=args.dry_run, force=args.force)
```

## Test File Template

```python
#!/usr/bin/env python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest",
#   "pytest-cov",
# ]
# ///
"""Tests for {script_name}."""
from pathlib import Path

import pytest

from {script_name} import your_function_to_test


def test_your_function_to_test():
    # Given
    input_data = ""

    # When
    results = your_function_to_test(input_data)

    # Then
    assert results is not None


@pytest.mark.parametrize("input_val,expected", [
    ("a", 1),
    ("b", 2),
])
def test_parametrized(input_val, expected):
    assert some_function(input_val) == expected


if __name__ == "__main__":
    module = Path(__file__).stem.replace('test_', '')
    pytest.main([__file__, "-v", f"--cov={module}", "--cov-report=term-missing", "--cov-fail-under=50"])
```

## Standalone Cache Check Script

Useful as a Makefile helper:

```python
"""
Usage:
    python cache_check.py <target_file> [cache_timeout_seconds]

Exits with 0 if cache expired, or remaining seconds if within cache threshold.
Default cache_timeout is 300 seconds (5 minutes).
"""
from pathlib import Path
import time
import sys

file = Path(sys.argv[1])
cache_timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 300
sys.exit(int(max(0, min(255, cache_timeout - (time.time() - file.stat().st_mtime)))))
```
