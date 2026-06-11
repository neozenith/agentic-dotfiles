---
paths:
  - ".claude/skills/**/scripts/*.py"
  - ".claude/skills/**/scripts/*.ts"
  - ".claude/skills/**/scripts/Makefile"
---

# Claude Skills Script Conventions

Rules for scripts in `.claude/skills/{skill-name}/scripts/`. Covers **Python**,
**TypeScript**, and **mixed-language** skills. A single `Makefile` orchestrates
all quality gates regardless of language mix; the per-language details differ,
but the target surface does not.

## The SDLC Loop (read this first)

**Every skill-script change is complete when these two commands are green:**

```bash
# Auto-fix everything that a machine can fix (formatter + linter auto-fixes,
# for Python AND TypeScript). Run this before you stop editing.
make -C .claude/skills/{skill_name}/scripts/ fix

# Test everything and be loud about quality-control breaches (format-check,
# lint, typecheck, test-cov, docs regeneration). Treat failure as "not done."
make -C .claude/skills/{skill_name}/scripts/ ci
```

This is the entire development loop. Everything else in this document exists
to make `fix` and `ci` meaningful — the target surface, per-language
sub-targets, biome/ruff/mypy/tsc tool choices, coverage thresholds, the
private-helper `docs` wiring — all of it is scaffolding around those two
commands.

If you only remember two things:

1. **`make fix` mutates.** It reshapes your source. Run it before committing.
2. **`make ci` is the gate.** It must be 0-exit-code before you hand work off
   or open a PR. Per-language sub-targets (`format-check-py`, `lint-ts`,
   `test-cov-py`, `typecheck-ts`, etc.) exist for debugging a failure —
   but the contract is `ci`, not the individual pieces.

Anything that can't be enforced by `make ci` doesn't exist.

## When a Skill Is Mixed-Language

Some skills start pure-Python or pure-TypeScript and then grow a port in the
other language (Python for scientific baselines, TypeScript for canonical
parsers / web interop / `bun:test` speed). A skill becomes **mixed** the moment
the `scripts/` directory contains both `.py` and `.ts` files. When that
happens:

- Keep **one** `Makefile` per `scripts/` directory. The targets fan out to
  language-specific sub-targets (`format-py`, `format-ts`, etc.).
- Keep **one** `.gitignore` covering both `node_modules/` and `__pycache__/`.
- Keep language-specific config siblings (`tsconfig.json`, `biome.json`,
  `package.json`, `bun.lock`) at the directory level, one set per language.
- Do **not** split scripts into `python/` and `typescript/` subdirectories.
  They live side-by-side so the Makefile stays simple and so parity tests
  between the two implementations remain trivial (`make parity`).

## Required Sibling Files

### Python-only skill

```
.claude/skills/{skill-name}/scripts/
├── {name}.py              # Main script with PEP-723 metadata
├── {name}.sh              # Optional — see "Shell wrappers" exception
├── test_{name}.py         # Pytest test file (PEP-723 entry point)
├── conftest.py            # Coverage reload fixture
└── Makefile               # Build automation
```

### TypeScript-only skill

```
.claude/skills/{skill-name}/scripts/
├── {name}.ts              # Main script (ESM, shebang `#!/usr/bin/env bun`)
├── {name}.sh              # Optional — see "Shell wrappers" exception
├── {name}.test.ts         # bun:test file
├── package.json           # deps + devDeps
├── tsconfig.json          # strict + types: ["bun"]
├── biome.json             # formatter + linter config
├── bun.lock               # committed lockfile
├── .gitignore             # node_modules/
└── Makefile               # Build automation
```

### Mixed-language skill

```
.claude/skills/{skill-name}/scripts/
├── shared_name.py         # Python implementation
├── shared_name.ts         # TypeScript port
├── test_shared_name.py    # Pytest
├── shared_name.test.ts    # bun:test
├── only_py_tool.py
├── test_only_py_tool.py
├── only_ts_tool.ts
├── only_ts_tool.test.ts
├── conftest.py            # Python coverage reload fixture
├── package.json
├── tsconfig.json
├── biome.json
├── bun.lock
├── .gitignore
└── Makefile               # Single Makefile, language-aware targets
```

## Shell Wrappers

Shell wrappers (`{name}.sh`) historically existed because some Claude Code
skill launchers couldn't directly invoke `uv` or `bun`. **Skip the `.sh`
wrapper** when the skill's `SKILL.md` invokes the script directly via `uv run`
(Python) or `bun run` (TypeScript). Pure scripts with no system-level side
effects qualify. Document the invocation in `SKILL.md` instead.

When a wrapper is required, keep it minimal:

**Python (`{name}.sh`):**

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run "$SCRIPT_DIR/{name}.py" "$@"
```

**TypeScript (`{name}.sh`):**

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bun run "$SCRIPT_DIR/{name}.ts" "$@"
```

## Private Helper Scripts

Some scripts exist solely to maintain the skill itself (e.g. regenerating a
README from source files). These are **private helpers** — never referenced in
`SKILL.md`, never invoked during skill execution, never exposed to consumers.

**Naming:** Prefix with `_` (Python private-module convention, extended to TS):

```
scripts/
├── script_a.py                # Public: documented in SKILL.md
├── _update_examples.py        # Private: maintenance helper
├── test_script_a.py
├── test__update_examples.py   # Double underscore: test_ + _private
└── Makefile
```

Rules:

- Follow all conventions that apply to public scripts.
- Add to `PRIVATE_PY_SCRIPTS` / `PRIVATE_TS_SCRIPTS` in the Makefile — **not**
  to `PY_SCRIPTS` / `TS_SCRIPTS`.
- Include in all quality targets (`format`, `lint`, `typecheck`, `test-cov`).
- Wire a **`docs`** target to the script; add `docs` as a dependency of `ci`.
- Reload in `conftest.py` alongside public modules (Python).
- **Do NOT add to `SKILL.md`** — that file describes the skill's public API.

## Python Script Structure

### PEP-723 Inline Script Metadata

Every Python script declares its deps at the top:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
```

Add dependencies only when absolutely necessary. Prefer pure stdlib.

### Module Layout

```python
from __future__ import annotations

import argparse
import logging
from pathlib import Path

# ── Configuration ───────────────────────────────────────────────────────
SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

log = logging.getLogger(__name__)

# ── Core ─────────────────────────────────────────────────────────────────
# ... implementation ...

# ── CLI ──────────────────────────────────────────────────────────────────
def main(args: argparse.Namespace) -> None:
    ...

if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(...)
    main(parser.parse_args())
```

### Dependency Injection for Testability

Functions that use global paths should accept optional parameters:

```python
def process_data(cache: CacheManager, data_path: Path | None = None) -> dict:
    if data_path is None:
        data_path = DEFAULT_DATA_PATH
    # ...

def main(args: argparse.Namespace, cache: CacheManager | None = None) -> None:
    owns_cache = cache is None
    if owns_cache:
        cache = CacheManager()
    # ...
```

### Tests as PEP-723 Entry Points

Tests are PEP-723 scripts, not separate pytest invocations. They declare all
their dependencies (including pytest itself) inline:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///

import sys
from pathlib import Path
import pytest

# ... tests ...

if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
```

**Why `--rootdir` and `-o addopts=`?** These isolate the test run from any
`pyproject.toml` higher in the directory tree. Without them, pytest discovers
the root project's `[tool.pytest.ini_options]` and injects unrelated coverage
config, producing 0% coverage or wrong-module targeting.

### `conftest.py` for Coverage Reload

When tests run via the PEP-723 `__main__` entry point, the module under test
is imported *before* `pytest.main()` starts coverage tracing. Module-level
code (imports, constants, SQL schemas) runs "in the dark" and reports 0%
coverage. Fix it with a `conftest.py` that reloads after coverage activates:

```python
"""Standalone test config for PEP-723 skill scripts."""
from __future__ import annotations
import importlib

import script_a
import _update_examples  # Private scripts reload here too
import pytest

@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    importlib.reload(script_a)
    importlib.reload(_update_examples)
```

pytest-cov's tracer starts in `pytest_sessionstart`, which fires *after*
conftest.py loads but *before* session-scoped fixtures. The `importlib.reload()`
re-executes every module-level statement under active tracing, recovering the
~10-17% coverage that would otherwise be invisible.

### No Mocks Policy

**NEVER use mocks.** Test real code with real dependencies. Use temp
directories, real `argparse.Namespace`, `capsys` for output:

```python
@pytest.fixture
def temp_cache(tmp_path: Path) -> CacheManager:
    db_path = tmp_path / "test_cache.db"
    cache = CacheManager(db_path=db_path)
    cache.init_schema()
    return cache

def test_main_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(command="status")
    main(args)
    assert "status" in capsys.readouterr().out
```

### Coverage Requirements

- **Minimum 90% coverage**.
- Use `# pragma: no cover` only for `if __name__ == "__main__":` block.

## TypeScript Script Structure

### File Layout

```typescript
#!/usr/bin/env bun
// Single-line description.

// ── Imports (stdlib first, then packages, then relative) ─────────────────
import { parseArgs } from "node:util";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

// ── Configuration ─────────────────────────────────────────────────────────
const SCRIPT = fileURLToPath(import.meta.url);
const SCRIPT_DIR = dirname(SCRIPT);

// ── Core ──────────────────────────────────────────────────────────────────
export const doTheThing = (input: string): Result => { /* ... */ };

// ── CLI ───────────────────────────────────────────────────────────────────
export const main = async (argv: string[] = Bun.argv.slice(2)): Promise<void> => {
  const { values, positionals } = parseArgs({
    args: argv,
    options: { /* ... */ },
    allowPositionals: true,
    strict: true,
  });
  // ... dispatch ...
};

if (import.meta.main) {
  main().catch((err: unknown) => {
    console.error(`error: ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
  });
}
```

Two things to note:

1. **`export`** — core functions are exported so tests can import them
   without executing `main()`.
2. **`if (import.meta.main)`** — Bun's equivalent of
   `if __name__ == "__main__":`. Guards the CLI bootstrap so the module is
   importable without side effects.

### Dependency Injection for Testability

```typescript
export const processData = (
  cachePath: string,
  dataPath: string = DEFAULT_DATA_PATH,
): Result => { /* ... */ };

export const main = async (
  argv: string[],
  deps: { cache?: CacheManager } = {},
): Promise<void> => {
  const cache = deps.cache ?? new CacheManager();
  // ...
};
```

### Tests via `bun:test`

```typescript
import { describe, test, expect } from "bun:test";
import { doTheThing } from "./{name}.ts";

describe("{name}", () => {
  test("doTheThing returns expected result", () => {
    expect(doTheThing("input")).toEqual({ /* ... */ });
  });
});
```

Run via `bun test`, not via a PEP-723-style `__main__` entry. Unlike pytest,
`bun test` instruments coverage from process start, so there's no
"0% on module-level code" problem to solve — no `conftest.py` analogue needed.

### Coverage Requirements

- **Minimum 90% line coverage**.
- Exclude the `if (import.meta.main)` bootstrap from coverage targets — it's
  the TS analogue of Python's `# pragma: no cover`.

## Makefile

The canonical `Makefile` applies to Python-only, TypeScript-only, and mixed
skills. The target surface is language-agnostic; sub-targets handle the
language specifics.

### Variables

| Variable | Purpose |
|----------|---------|
| `PY_SCRIPTS` | Public Python scripts (referenced in SKILL.md) |
| `PRIVATE_PY_SCRIPTS` | Private Python helpers (NOT in SKILL.md) |
| `PY_SRC` | Every `.py` file: public + private, including tests |
| `TS_SCRIPTS` | Public TypeScript scripts (referenced in SKILL.md) |
| `PRIVATE_TS_SCRIPTS` | Private TypeScript helpers (NOT in SKILL.md) |
| `TS_SRC` | Every `.ts` file: public + private, including `*.test.ts` |

Language-specific variables are **omitted** (not defined) in single-language
skills, and their associated targets are omitted from `.PHONY`.

### Target Surface

| Generic | Python-specific | TS-specific | Mutates? |
|---------|----------------|-------------|----------|
| `format` | `format-py` | `format-ts` | Yes |
| `format-check` | `format-check-py` | `format-check-ts` | No |
| `lint` | `lint-py` | `lint-ts` | No |
| `lint-fix` | `lint-fix-py` | `lint-fix-ts` | Yes |
| `typecheck` | `typecheck-py` | `typecheck-ts` | No |
| `test` | `test-py` | `test-ts` | No |
| `test-cov` | `test-cov-py` | `test-cov-ts` | No |

Rules:

- Each **generic** target is a `.PHONY` target that depends on both
  `-py` and `-ts` variants (or just the one that exists in a single-language
  skill). It has **no recipe of its own** — it only aggregates.
- Each **language-specific** target contains the actual commands.
- `lint` targets **do not** depend on `format` targets. Making a "check"
  target mutate source is a footgun. Users who want the combined workflow run
  `make fix` (= `format` + `lint-fix`).
- The `ci` target uses the **generic** non-mutating variants:
  `ci: format-check lint typecheck test-cov docs`.

### Tool Choices

| Concern | Python | TypeScript |
|---------|--------|-----------|
| Formatter | `ruff format` | `biome format` (via `bunx --bun @biomejs/biome`) |
| Linter | `ruff check --line-length 120` | `biome lint` |
| Typechecker | `mypy --strict --ignore-missing-imports` | `tsc --noEmit` (strict in `tsconfig.json`) |
| Test runner | PEP-723 `__main__` via `uv run` | `bun test` |
| Coverage | `pytest-cov` (declared in test file's PEP-723 deps) | `bun test --coverage` |

**Why `biome` via `bunx`?** Keeping biome out of `package.json`
`devDependencies` avoids polluting the skill's dep graph and lets the V2 bun
runtime resolve it at build time. The `--bun` flag forces bunx to execute on
Bun's runtime rather than Node.

### Reference Implementation

```makefile
# Shared Makefile for a mixed-language skill.
# Run from repo root: make -C .claude/skills/{skill}/scripts <target>

# ── Python source ───────────────────────────────────────────────────────
PY_SCRIPTS = public_script_a
PRIVATE_PY_SCRIPTS = _update_examples

PY_SRC = $(addsuffix .py,$(PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PY_SCRIPTS))) \
         $(addsuffix .py,$(PRIVATE_PY_SCRIPTS)) $(addprefix test_,$(addsuffix .py,$(PRIVATE_PY_SCRIPTS)))

# ── TypeScript source ──────────────────────────────────────────────────
TS_SCRIPTS = public_script_a new_ts_tool
TS_SRC = $(addsuffix .ts,$(TS_SCRIPTS)) $(addsuffix .test.ts,$(TS_SCRIPTS))

# ── Paths ──────────────────────────────────────────────────────────────
THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# `--no-project` prevents uv from walking up and discovering a root pyproject.toml
UV = uv run --no-project
PYTEST_ARGS = -v --rootdir . -o 'addopts='

# biome via bunx so it stays out of package.json; --bun pins the runtime.
BIOME = bunx --bun @biomejs/biome

.PHONY: all debug help clean \
        format format-py format-ts \
        format-check format-check-py format-check-ts \
        lint lint-py lint-ts \
        lint-fix lint-fix-py lint-fix-ts \
        typecheck typecheck-py typecheck-ts \
        test test-py test-ts \
        test-cov test-cov-py test-cov-ts \
        install-ts docs ci fix

all: format lint typecheck test-cov docs

# ── Format ──────────────────────────────────────────────────────────────
format: format-py format-ts
format-py:       ; $(UV) ruff format $(PY_SRC)
format-ts:       ; $(BIOME) format --write $(TS_SRC)
format-check: format-check-py format-check-ts
format-check-py: ; $(UV) ruff format --check $(PY_SRC)
format-check-ts: ; $(BIOME) format $(TS_SRC)

# ── Lint ────────────────────────────────────────────────────────────────
lint: lint-py lint-ts
lint-py:         ; $(UV) ruff check --line-length 120 $(PY_SRC)
lint-ts:         ; $(BIOME) lint $(TS_SRC)
lint-fix: lint-fix-py lint-fix-ts
lint-fix-py:     ; $(UV) ruff check --fix --line-length 120 $(PY_SRC)
lint-fix-ts:     ; $(BIOME) lint --write $(TS_SRC)

# ── Typecheck ──────────────────────────────────────────────────────────
typecheck: typecheck-py typecheck-ts
typecheck-py:    ; $(UV) mypy $(addsuffix .py,$(PY_SCRIPTS) $(PRIVATE_PY_SCRIPTS)) --ignore-missing-imports --strict

# Invoke local tsc directly — `bunx tsc` has dep-resolution quirks when cwd differs.
typecheck-ts:    ; $(THIS_DIR)node_modules/.bin/tsc --project $(THIS_DIR)tsconfig.json --noEmit

# ── Test ────────────────────────────────────────────────────────────────
test: test-py test-ts
test-py:
	$(UV) test_public_script_a.py $(PYTEST_ARGS)
	$(UV) test__update_examples.py $(PYTEST_ARGS)
test-ts:         ; bun test --cwd $(THIS_DIR)

test-cov: test-cov-py test-cov-ts
test-cov-py:
	$(UV) test_public_script_a.py $(PYTEST_ARGS) \
		--cov=public_script_a --cov-report=term-missing --cov-fail-under=90
	$(UV) test__update_examples.py $(PYTEST_ARGS) \
		--cov=_update_examples --cov-report=term-missing --cov-fail-under=90
test-cov-ts:     ; bun test --cwd $(THIS_DIR) --coverage

# ── Install / Docs / Misc ──────────────────────────────────────────────
install-ts:      ; bun install --cwd $(THIS_DIR)

# Wire private maintenance scripts to docs, make docs a ci dependency.
docs:            ; $(UV) _update_examples.py

ci: format-check lint typecheck test-cov docs
fix: format lint-fix

clean:
	rm -f *.pyc
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
```

### Single-Language Simplification

For a pure-Python or pure-TypeScript skill, omit the other language's
variables and targets. The generic targets then collapse to single
dependencies:

```makefile
# Pure-Python skill
format: format-py
lint: lint-py
# ... etc
```

The generic target names stay stable so downstream tooling (`make ci`,
`make fix`) works identically regardless of language mix — only the fan-out
shrinks.

## Debugging a Failing `make ci`

The two commands at the top of this document (`make fix` + `make ci`) are the
contract. When `ci` goes red, use the per-language sub-targets to narrow the
failure without re-running the whole suite:

```bash
# Isolate by language and concern
make -C .claude/skills/{skill}/scripts format-check-py   # Ruff formatting drift
make -C .claude/skills/{skill}/scripts format-check-ts   # Biome formatting drift
make -C .claude/skills/{skill}/scripts lint-py           # Ruff lint rules
make -C .claude/skills/{skill}/scripts lint-ts           # Biome lint rules
make -C .claude/skills/{skill}/scripts typecheck-py      # mypy --strict
make -C .claude/skills/{skill}/scripts typecheck-ts      # tsc --noEmit
make -C .claude/skills/{skill}/scripts test-cov-py       # pytest + coverage
make -C .claude/skills/{skill}/scripts test-cov-ts       # bun test --coverage
make -C .claude/skills/{skill}/scripts docs              # README regen (private helper)
```

Once you've fixed the root cause, **always re-run `make ci` end-to-end** to
confirm — a per-target green does not prove the aggregate is green.

Run from project root with `make -C` — never `cd` into the scripts directory.

## Language Divergences Quick Reference

| Aspect | Python | TypeScript |
|--------|--------|-----------|
| Dependency declaration | PEP-723 inline, **per-file** | `package.json`, **per-directory** |
| Private-helper prefix | `_name.py` | `_name.ts` |
| Test file naming | `test_name.py` | `name.test.ts` |
| Test entry point | `uv run test_name.py` (`__main__` dispatch) | `bun test` (native runner) |
| Coverage reload hack | `conftest.py` + `importlib.reload()` | Not needed — `bun test` traces from start |
| `if __name__ == "__main__":` | Python idiom | `if (import.meta.main)` |
| Lockfile | `uv.lock` (if any) | `bun.lock` |
| Typechecker | `mypy --strict` | `tsc --noEmit` (strict in `tsconfig.json`) |
| Formatter / Linter | `ruff format` + `ruff check` | `biome format` + `biome lint` via `bunx --bun` |
| Config siblings | `conftest.py` | `tsconfig.json`, `biome.json`, `package.json`, `bun.lock` |
