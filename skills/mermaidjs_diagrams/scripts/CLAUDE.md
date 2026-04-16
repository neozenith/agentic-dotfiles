# Scripts Maintenance Guide — mermaidjs_diagrams

This file is the **self-contained developer reference** for maintaining the
scripts under `.claude/skills/mermaidjs_diagrams/scripts/`. It covers the SDLC
workflow, conventions, tool choices, and file layout for the public-facing
`SKILL.md` assets.

> **Scope.** Everything here applies to *this* scripts directory, which is a
> **mixed-language skill** (Python + TypeScript scripts side-by-side with a
> single `Makefile` orchestrating both).

## The SDLC Loop (read this first)

**Every script change is complete when these two commands are green:**

```bash
# Auto-fix everything that a machine can fix (ruff + biome auto-fixes,
# both Python and TypeScript). Run this before you stop editing.
make -C .claude/skills/mermaidjs_diagrams/scripts/ fix

# Test everything and be loud about QC breaches (format-check, lint,
# typecheck, test-cov, docs regeneration). Treat failure as "not done."
make -C .claude/skills/mermaidjs_diagrams/scripts/ ci
```

This is the entire development loop. Everything else in this document exists
to make `fix` and `ci` meaningful — per-language sub-targets, tool choices,
coverage thresholds, `docs` wiring, the `cli-demo` end-to-end smoke — all of
it is scaffolding around those two commands.

If you only remember two things:

1. **`make fix` mutates.** It reshapes your source. Run it before committing.
2. **`make ci` is the gate.** It must be 0-exit-code before you hand work off.
   Per-language sub-targets (`format-check-py`, `lint-ts`, `test-cov-py`,
   `typecheck-ts`, etc.) exist for **debugging** a failure — the contract is
   `ci`, not the individual pieces.

Anything that can't be enforced by `make ci` doesn't exist.

## Files in this Directory

### Public (documented in `SKILL.md`)

| File | Language | Purpose |
|------|----------|---------|
| `mermaid_complexity.ts` | TypeScript | Canonical-parser complexity scorer (`.mmd` + `.md`) via Langium + mermaid-core JISON. |
| `mermaid_contrast.ts` | TypeScript | WCAG contrast audit for `classDef`/`style` directives inside diagrams. |
| `color_contrast.ts` | TypeScript | WCAG + APCA calculator for arbitrary CSS color pairs. |
| `render_mermaid.sh` | Bash | Renders both standard variants (dark+transparent, default+white) via `mmdc`. |

### Private (NOT in `SKILL.md`)

| File | Language | Purpose |
|------|----------|---------|
| `_update_examples_readme.py` | Python | Regenerates `resources/examples/README.md` from `.mmd` files. Wired to `make docs`. |

Private helpers are prefixed with `_` (mirroring Python's private-module
convention, extended to any language). They follow all the same quality rules
as public scripts but never appear in `SKILL.md`.

### Test files

Every public/private script has a sibling test:

| Source | Test |
|--------|------|
| `mermaid_complexity.ts` | `mermaid_complexity.test.ts` |
| `mermaid_contrast.ts` | `mermaid_contrast.test.ts` |
| `color_contrast.ts` | `color_contrast.test.ts` |
| `_update_examples_readme.py` | `test__update_examples_readme.py` (double underscore: `test_` + `_private`) |

### Shared configuration

| File | Role |
|------|------|
| `Makefile` | Orchestrator for every quality gate. Do not fork per-script. |
| `conftest.py` | Python: reloads modules post-coverage-start (PEP-723 quirk — see below). |
| `package.json` | Bun/TS deps (shared across all TS scripts). |
| `tsconfig.json` | Strict TS config, `types: ["bun"]`. |
| `biome.json` | Biome formatter + linter config (spaces, 120-wide, double quotes). |
| `bun.lock` | Committed lockfile. |
| `.gitignore` | `node_modules/`, pycache, etc. |

## Target Surface

The `Makefile` exposes language-generic and language-specific targets. Generic
targets simply aggregate both language sub-targets — they have no recipe of
their own:

| Generic | Python-specific | TS-specific | Mutates? |
|---------|----------------|-------------|----------|
| `format` | `format-py` | `format-ts` | Yes |
| `format-check` | `format-check-py` | `format-check-ts` | No |
| `lint` | `lint-py` | `lint-ts` | No |
| `lint-fix` | `lint-fix-py` | `lint-fix-ts` | Yes |
| `typecheck` | `typecheck-py` | `typecheck-ts` | No |
| `test` | `test-py` | `test-ts` | No |
| `test-cov` | `test-cov-py` | `test-cov-ts` | No |

Convenience targets:

| Target | What it does |
|--------|-------------|
| `all` | `format + lint + typecheck + test-cov + docs` (default) |
| `ci` | `format-check + lint + typecheck + test-cov + docs` (non-mutating gate) |
| `fix` | `format + lint-fix` (auto-apply everything fixable) |
| `docs` | Regenerates `resources/examples/README.md` via `_update_examples_readme.py` |
| `cli-demo` | Runs every public TS analyzer against fixture inputs — live tutorial |
| `install-ts` | `bun install` into this directory's `node_modules` |
| `clean` | Removes caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `htmlcov`, `.coverage`) |

### Design rules for targets

- **`lint` does NOT depend on `format`.** Mutating source as a side-effect of
  a "check" target is a footgun. Users who want the combined workflow run
  `make fix`.
- **`ci` uses the non-mutating variants.** `format-check` (not `format`),
  `lint` (not `lint-fix`).
- **Adding a new script:** update `PY_SCRIPTS` / `TS_SCRIPTS` / `PRIVATE_PY_SCRIPTS`
  in the Makefile variable block — that's the only source-of-truth edit
  needed. Targets expand automatically.

## Tool Choices

| Concern | Python | TypeScript |
|---------|--------|-----------|
| Formatter | `ruff format` | `biome format` (via `bunx --bun @biomejs/biome`) |
| Linter | `ruff check --line-length 120` | `biome lint` |
| Typechecker | `mypy --strict --ignore-missing-imports` | `tsc --noEmit` (strict in `tsconfig.json`) |
| Test runner | PEP-723 `__main__` via `uv run` | `bun test` |
| Coverage | `pytest-cov` (declared in test file's PEP-723 deps) | `bun test --coverage` |

**Why biome via `bunx --bun`?** Keeping biome out of `package.json`
`devDependencies` avoids polluting the skill's dep graph. The `--bun` flag
forces bunx to execute biome on Bun's runtime rather than Node.

**Why `uv run --no-project`?** Without `--no-project`, uv walks up and
discovers a root `pyproject.toml`, which would inject unrelated coverage
config or deps. The Makefile pins this via `UV = uv run --no-project`.

## Python Script Conventions

### PEP-723 Inline Metadata

Every Python script declares its deps at the top:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
```

Add dependencies only when absolutely necessary. Prefer pure stdlib.

### Tests as PEP-723 Entry Points

Tests are PEP-723 scripts — they declare pytest + pytest-cov inline and are
invoked via `uv run test_{name}.py`, not `uv run pytest test_{name}.py`.

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

**Why `--rootdir` and `-o addopts=`?** Isolates the test run from any
`pyproject.toml` higher in the directory tree. Without them, pytest discovers
the root project's `[tool.pytest.ini_options]` and injects unrelated coverage
config, producing 0% coverage or wrong-module targeting.

### `conftest.py` Coverage Reload

When tests run via the PEP-723 `__main__` entry point, the module under test
is imported *before* `pytest.main()` starts coverage tracing. Module-level
code (imports, constants) runs "in the dark" and reports 0% coverage. The
local `conftest.py` reloads the modules after coverage activates:

```python
from __future__ import annotations
import importlib

import mermaid_complexity
import _update_examples_readme
import pytest

@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    importlib.reload(mermaid_complexity)
    importlib.reload(_update_examples_readme)
```

When you add a new public or private Python script, add an `importlib.reload()`
line for it here.

### No Mocks Policy

**NEVER use mocks** in tests. Test real code with real dependencies — temp
directories, real `argparse.Namespace`, `capsys` for output capture.

### Coverage Requirement

**Minimum 90% coverage.** Use `# pragma: no cover` only on the
`if __name__ == "__main__":` block.

## TypeScript Script Conventions

### File Layout

```typescript
#!/usr/bin/env bun
// Single-line description.

// ── Imports (stdlib → packages → relative) ─────────────────────────────
import { parseArgs } from "node:util";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

// ── Configuration ──────────────────────────────────────────────────────
const SCRIPT = fileURLToPath(import.meta.url);
const SCRIPT_DIR = dirname(SCRIPT);

// ── Core ───────────────────────────────────────────────────────────────
export const doTheThing = (input: string): Result => { /* ... */ };

// ── CLI ────────────────────────────────────────────────────────────────
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

### Tests via `bun:test`

```typescript
import { describe, test, expect } from "bun:test";
import { doTheThing } from "./mermaid_complexity.ts";

describe("mermaid_complexity", () => {
  test("doTheThing returns expected result", () => {
    expect(doTheThing("input")).toEqual({ /* ... */ });
  });
});
```

Run via `bun test` (the Makefile handles `--cwd` and `--coverage`). Unlike
pytest, `bun test` instruments coverage from process start — no
`conftest.py` analogue needed.

### Coverage Requirement

**Minimum 90% line coverage.** Exclude the `if (import.meta.main)` bootstrap
from coverage targets — the TS analogue of Python's `# pragma: no cover`.

## Private Helper Scripts (`_name.py` / `_name.ts`)

Private helpers exist solely to maintain the skill itself — e.g.
`_update_examples_readme.py` regenerates `resources/examples/README.md` from
the `.mmd` files in that directory.

**Rules:**

- Prefix filename with `_`.
- Add to `PRIVATE_PY_SCRIPTS` / `PRIVATE_TS_SCRIPTS` in the Makefile — **not**
  to `PY_SCRIPTS` / `TS_SCRIPTS`.
- Include in every quality target (`format`, `lint`, `typecheck`, `test-cov`).
- Wire to a **`docs`** Makefile target if it regenerates documentation.
- Reload in `conftest.py` alongside public modules (Python only).
- **Do NOT add to `SKILL.md`** — that file describes the skill's public API.

## Debugging a Failing `make ci`

The two commands at the top (`make fix` + `make ci`) are the contract. When
`ci` goes red, use per-language sub-targets to narrow the failure without
re-running the whole suite:

```bash
make -C .claude/skills/mermaidjs_diagrams/scripts format-check-py   # Ruff formatting drift
make -C .claude/skills/mermaidjs_diagrams/scripts format-check-ts   # Biome formatting drift
make -C .claude/skills/mermaidjs_diagrams/scripts lint-py           # Ruff lint rules
make -C .claude/skills/mermaidjs_diagrams/scripts lint-ts           # Biome lint rules
make -C .claude/skills/mermaidjs_diagrams/scripts typecheck-py      # mypy --strict
make -C .claude/skills/mermaidjs_diagrams/scripts typecheck-ts      # tsc --noEmit
make -C .claude/skills/mermaidjs_diagrams/scripts test-cov-py       # pytest + coverage
make -C .claude/skills/mermaidjs_diagrams/scripts test-cov-ts       # bun test --coverage
make -C .claude/skills/mermaidjs_diagrams/scripts docs              # README regen
```

Once you've fixed the root cause, **always re-run `make ci` end-to-end** — a
per-target green does not prove the aggregate is green.

Run from project root with `make -C`. Never `cd` into the scripts directory
(see the working-directory rules in the project's root `CLAUDE.md`).

## Language Divergences Quick Reference

| Aspect | Python | TypeScript |
|--------|--------|-----------|
| Dependency declaration | PEP-723 inline, **per-file** | `package.json`, **per-directory** |
| Private-helper prefix | `_name.py` | `_name.ts` |
| Test file naming | `test_name.py` | `name.test.ts` |
| Test entry point | `uv run test_name.py` (`__main__` dispatch) | `bun test` (native runner) |
| Coverage reload hack | `conftest.py` + `importlib.reload()` | Not needed — `bun test` traces from start |
| `if __name__ == "__main__":` | Python idiom | `if (import.meta.main)` |
| Lockfile | Absent (PEP-723 resolves on-demand) | `bun.lock` |
| Typechecker | `mypy --strict` | `tsc --noEmit` (strict in `tsconfig.json`) |
| Formatter / Linter | `ruff format` + `ruff check` | `biome format` + `biome lint` via `bunx --bun` |
| Per-dir config siblings | `conftest.py` | `tsconfig.json`, `biome.json`, `package.json`, `bun.lock` |

## Related

- `../SKILL.md` — public-facing skill surface (what this skill does).
- `../README.md` — ultra-short feature pitch for drive-by readers.
- `.claude/rules/claude_skills.md` — the canonical convention doc this file
  was derived from. If it changes, consider updating this file to match (or
  prune it if you'd rather link-only).
