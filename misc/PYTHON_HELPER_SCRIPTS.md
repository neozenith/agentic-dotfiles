# Python Coding Conventions

---
<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [Python Coding Conventions](#python-coding-conventions)
  - [Script Guidelines](#script-guidelines)
    - [Running Scripts](#running-scripts)
    - [Script Dependencies](#script-dependencies)
    - [Naming Helper Scripts](#naming-helper-scripts)
    - [Environment Variables](#environment-variables)
    - [Git Integration](#git-integration)
    - [Helper Functions](#helper-functions)
    - [Handling Files](#handling-files)
    - [Configuration, Paths and Caching](#configuration-paths-and-caching)
    - [Logging Output](#logging-output)
    - [CLI Argument Parser](#cli-argument-parser)
    - [Main Function Integration](#main-function-integration)
    - [Testing](#testing)
    - [Triage Script Output Format](#triage-script-output-format)
    - [Interacting with AWS](#interacting-with-aws)
    - [System Documentation](#system-documentation)
    - [Quality Assurance](#quality-assurance)

<!--TOC-->
</details>

---


## Script Guidelines

### Running Scripts

NEVER run arbitrary `python` commands. Especially `python -c '...'`.

Create the python script first even if it is a temporary one. 

Each script should run independently using `uv` like:

```sh
uv run scripts/script_name_here.py
```

This is because most scripts will standalone and use the PEP-723 inline metadata for dependencies mentioned in [Script Dependencies](#script-dependencies)

You should be able to extract full usage information with the `--help` flag.

```sh
uv run scripts/script_name_here.py --help
```

### Script Dependencies

They should leverage the [PEP-723](https://peps.python.org/pep-0723/#example) inline metadata to define library dependencies. 
This example adds the `boto3`, `python-dotenv` and `networkx` libraries:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "python-dotenv>=1.0.0",
#   "networkx",
# ]
# ///

import networkx as nx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
```

### Naming Helper Scripts

The files should be named with a key verb to describe what it is doing and the task like `<verb>_<name_of_task>.py`.

Key Verbs:

- `explore`, `discover`, `analyse` - these are research type tasks to dynamically find the current state of something. 
  These can be one off single use scripts too.
- `triage` - these are used to collate log and test information and then critically think about the 
  output to systematically suggest a next step.
- `process`, `export`, `extract`, `migrate`, `convert` - these are all repeatable processes that are idempotent 
  transformations. I can delete their output and get the same deterministic output from the original inputs.
- `fix` - these are similar to transformations but they will be temporary and can be one off single use scripts.

Name of Task:

- Should be between 3-5 words.
- Coupled with the Key Verb conscisely describe what it does.

### Environment Variables

Scan for `.env.sample` to see what enviroment variables should be available and exported.

### Git Integration

For scripts that need Git context, use subprocess with shlex for clean command execution:

```python
import subprocess
from shlex import split

_run = lambda cmd: subprocess.check_output(split(cmd), text=True).strip() # noqa: E731

GIT_ROOT = Path(_run("git rev-parse --show-toplevel"))
GIT_BRANCH = _run("git rev-parse --abbrev-ref HEAD")
```

### Helper Functions

Define minimal helper lambdas at the top of the script for common operations. Use `# noqa: E731` to suppress Ruff's lambda assignment warnings:

```python
# Command execution helper
_run = lambda cmd: subprocess.check_output(split(cmd), text=True).strip()  # noqa: E731

# Cache validation helper - both values must be positive for valid cache
_is_cache_valid = lambda time_tuple: all(x > 0 for x in time_tuple)  # noqa: E731
```

Note: E731 warns against lambda assignments, but for simple one-liners they're more concise than `def` statements.


### Handling Files

Always prefer using `pathlib` for handling files. For example reading a JSON files should be as simple as:

```python
from pathlib import Path
import json

data_path = Path("data/")

nodes = json.loads((data_path / "exercises-catalog.json").read_text(encoding="utf-8"))
edges = nodes = json.loads((data_path / "exercise-relationships.json").read_text(encoding="utf-8"))
```

### Configuration, Paths and Caching

- All key configuration should be towards the top of the file under the imports.
- They should be all capitalised. (I know this is not "Pythonic" or PEP-8 compliant.)
- All Paths should be relative to `SCRIPT_DIR` as shown in the code example below.
- Use `tmp/claude_cache/{script_name}/` to output temporary files any script needs to leverage between runs.
- Implement a `check_cache()` function that returns a tuple of (delta, remaining) times for cache validation.
- Default cache timeout is 5 minutes (300 seconds).

**When Cache Strategy is Unclear:**

Ask follow-up questions and suggest pros/cons to better understand the trade-offs we are making like:

- **Longer**: Reduces costs, prevents rate limiting, forces systematic analysis, matches infrastructure realities
- **Shorter**: Enables faster iteration, more responsive to changes, better for rapid development cycles

Which of these do we value more in that context?

**Default Decision Framework:**
1. What's the natural update cycle of the system?
2. Is rapid iteration helping or hurting problem-solving?
3. Are there rate limits or costs to consider?
4. Would forced delays improve analysis quality?

```python
from pathlib import Path
from time import time

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent  # Common parent of SCRIPTS_DIR and CACHE_DIR

CACHE_DIR = PROJECT_ROOT / "tmp" / "claude_cache" / SCRIPT_NAME

# Input files
DATA_DIR = PROJECT_ROOT / "data"
INPUT_FILE_1 = DATA_DIR / "file1.json"
INPUT_FILE_2 = DATA_DIR / "file2.json"
ALL_INPUTS = [INPUT_FILE_1, INPUT_FILE_2]  # Can be a mixture of single files and rglobs

# Output files (example: transform each .py script to a .json analysis)
OUTPUT_SUMMARY = CACHE_DIR / "output_summary.json"
OUTPUT_ANALYSIS = [CACHE_DIR / f.relative_to(SCRIPT_DIR).with_suffix(".json") 
                   for f in SCRIPT_DIR.rglob("*.py") if f.is_file()]
ALL_OUTPUTS = [OUTPUT_SUMMARY, *OUTPUT_ANALYSIS]

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
```

### Logging Output

All scripts should use the standard library logger and NOT `print` statements. Support `-v/--verbose` and `-q/--quiet` flags with priority given to verbose.

```python
import logging
log = logging.getLogger(__name__)

# Body of code here

def main(dry_run: bool = False, force: bool = False):
    ...

if __name__ == "__main__":
    # Parser setup here (see CLI section)
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.ERROR if args.quiet else logging.INFO,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s", 
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    main(dry_run=args.dry_run, force=args.force)
```

### CLI Argument Parser

- Always implement an `ArgumentParser` that includes a comprehensive description of the script.
- Use `RawDescriptionHelpFormatter` for multi-line descriptions with `textwrap.dedent()`.
- Include standard flags with shorthand options:
  - `-v/--verbose`: Enable debug logging
  - `-q/--quiet`: Show only errors
- Add these ONLY IF NEEDED:
  - When needing to implement cache checking use these:
    - `-f/--force`: Force reprocessing, ignoring cache
    - `-n/--dry-run`: Run without making changes
    - `--cache-check`: Check cache status only
  - When needing to implement short test runs:
    - `-L/--limit N`: Iterate through the task only `N` times
    - `-T/timeout TIMEOUT`: Add a self imposed time out to safely kill the script after `TIMEOUT` seconds.
- DO NOT replace capitalised config variables with CLI arguments or flags.
- Document INPUTS and OUTPUTS in the description.

```python
import argparse
from textwrap import dedent

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
```

### Main Function Integration

The main function should accept standard flags and integrate with cache checking:

```python
def main(dry_run: bool = False, force: bool = False):
    cache_status = check_cache(CACHE_DIR, ALL_INPUTS, force=force)
    if not _is_cache_valid(cache_status):
        log.info("Cache is invalid or expired, processing...")
        # Main processing logic here
        if dry_run:
            log.info("DRY RUN: Would process files but not write output")
        else:
            # Actual processing
            pass
    else:
        log.info("Cache is valid, skipping processing.")

if __name__ == "__main__":
    # ... parser setup ...
    
    if args.cache_check:
        delta, remaining = check_cache(CACHE_DIR, ALL_INPUTS, force=args.force)
        if _is_cache_valid((delta, remaining)):
            log.info(f"Cache is up to date. Delta: {delta}s, Remaining: {remaining}s")
        else:
            log.warning(f"Cache is not up to date. Delta: {delta}s, Remaining: {remaining}s")
    else:
        main(dry_run=args.dry_run, force=args.force)
```

### Testing

When needing to iterate on fixing bugs keep in mind these principles:

- Write code that will be easy to test
- When writing unit tests, leverage parametrised tests. This often leads to the most test coverage of scenarios for the least test code to write (and maintain).

Always use `pytest` as the test framework.

Each `script/your_script_name.py` sould have it's test file as a sibling file like `script/test_your_script_name.py`.

Minimal example:

```python
#!/usr/bin/env python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest",
#   "pytest-cov",
# ]
# ///
import pytest

from your_script_name import your_function_to_test


def test_your_function_to_test():
    # Given
    input_data = ""

    # When
    results = your_function_to_test(input_data)

    # Then
    assert results is not None

if __name__ == "__main__":
    module = str(Path(__file__).stem.replace('test_', ''))
    pytest.main([__file__, "-v", f"--cov={module}", "--cov-report=term-missing", "--cov-fail-under=50"])
```

Then run it standalone like:

```sh
uv run script/test_your_script_name.py
```

### Triage Script Output Format

Triage scripts (`triage_*.py`) should produce structured, self-documenting output that enables autonomous decision-making.
Document the `--help` section with as much guidance need to help self-discover the following:

**Required Output Sections:**

- **STATUS SUMMARY**: Current system state with key metrics
- **FINDINGS**: Categorized issues (Critical/High/Medium/Low) with evidence
- **RECOMMENDATIONS**: Prioritized next steps with reasoning and confidence levels
- **EVIDENCE LINKS**: Specific log entries, files, or data points supporting conclusions
- **ASSUMPTIONS**: What the analysis assumes to be true
- **ALTERNATIVES**: Other hypotheses considered and why they were ruled out

**Output Format Standards:**
- Use structured text (YAML/JSON) for machine parsing when beneficial
- Include confidence percentages on recommendations (e.g., "90% confident this is network latency")
- Reference specific files/lines that led to conclusions
- Include success criteria for recommended actions
- Document any manual verification steps needed

### Interacting with AWS

- ASSUME that `AWS_PROFILE` is already exported in the current session to provide credentials for the target AWS account.
- Always prefer AWS CDK for deployment management.
- Make use of exporting JSON output results to `tmp/claude_cache/{script_name}/*.json`. This is helpful when triaging and analysing problems.
- Scripts with known cache files should list them as `pathlib.Path` variables at the top of the script as well as their cache timeout which should default to 5 minutes (300 seconds).
- Leverage helper caching checking script like:
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

### System Documentation

- When generating a README.md ALWAYS create MermaidJS architecture diagram(s) to quickly visually explain what is going on.
- Make use of colour to make the boxes visually distinct toi help with visual communication.
- Make sure the text colour is a good contrast with any background colours.
- Make use of Emoji in the names of boxes for extra expressiveness.

### Quality Assurance

Regularly run these tools for formatting and linting. eg:

```sh
# Docs
uvx --from md-toc md_toc --in-place github --header-levels 4 README.md scripts/*.md
uvx rumdl check . --fix --respect-gitignore -d MD013


# Formatting
uvx ruff format . --respect-gitignore --line-length 120
uvx isort src/ tests/ scripts

# Linting
uvx ruff check . --line-length 120 --respect-gitignore --fix-only
uvx ruff check . --line-length 120 --respect-gitignore --statistics

# Type checking
uvx mypy .
```

Ideally there is a `Makefile` so you can run `make fix` to run these.

