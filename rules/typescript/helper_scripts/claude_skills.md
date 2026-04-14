---
paths:
  - ".claude/skills/**/scripts/*.ts"
---

# Claude Skills TypeScript Script Conventions

Rules for TypeScript scripts in `.claude/skills/{skill-name}/scripts/`.

## Required Sibling Files

Every TypeScript script `{name}.ts` in a skill's scripts directory lives alongside this shared support layout:

```
.claude/skills/{skill-name}/scripts/
├── {name}.ts              # Main script (ESM, ends in `.ts`, shebang `#!/usr/bin/env bun`)
├── {name}.sh              # Shell wrapper — see exception below
├── {name}.test.ts         # bun:test file
├── package.json           # deps + devDeps (shared across all scripts in the dir)
├── tsconfig.json          # strict + types: ["bun"] (shared)
├── bun.lock               # committed lockfile (shared)
├── .gitignore             # node_modules/
└── Makefile               # Build automation
```

### Exception: Shell Wrappers for Pure TS Scripts

Shell wrappers (`.sh`) exist because Claude Code skills historically couldn't invoke `uv` directly. **Skip the `.sh` wrapper** when the script is invoked via `bun run` directly in SKILL.md (e.g. `bun run .claude/skills/{skill}/scripts/{name}.ts`). Pure TS scripts with no system-level side effects qualify. Document the invocation in SKILL.md instead.

### Exception: Private Helper Scripts (`_{name}.ts`)

Some scripts exist solely to maintain the skill itself (e.g. regenerating a README from source files). These are **private helpers** — never referenced in SKILL.md, never invoked during skill execution, never exposed to skill consumers.

**Naming convention:** Prefix with `_` (mirroring the Python private-module convention):

```
.claude/skills/{skill-name}/scripts/
├── script_a.ts             # Public: documented in SKILL.md
├── _update_examples.ts     # Private: maintenance helper, NOT in SKILL.md
├── script_a.test.ts
├── _update_examples.test.ts
└── Makefile
```

**Rules for private helper scripts:**

- Follow all the same conventions as public scripts (strict tsconfig, argparse via `node:util`, logging, etc.)
- Add to `PRIVATE_SCRIPTS` in the Makefile — **not** `SCRIPTS`
- Include in all quality targets (`format`, `lint`, `typecheck`, `test-cov`)
- Wire a **`docs` target** to the script; add `docs` as a dependency of `ci`
- **Do NOT add to SKILL.md** — that file describes the skill's public interface

### Shared package.json, tsconfig.json, Makefile

When a skill's `scripts/` directory contains **multiple TypeScript scripts**, all scripts share a **single** `package.json`, `tsconfig.json`, `bun.lock`, and `Makefile`. This differs from the Python pattern where each script declares its own PEP-723 metadata — TypeScript dependencies live at the directory level, not the file level.

The shared `tsconfig.json` uses `"include": ["*.ts"]` so any new script is picked up automatically. The shared `Makefile` uses `SCRIPTS = script_a script_b` and expands targets via shell globbing so adding a new script only requires updating that one variable.

## TypeScript Script Structure (`{name}.ts`)

### Shebang + Module-Level Organization

```typescript
#!/usr/bin/env bun
// Single-line description of what this script does.
//
// Usage:
//   bun run scripts/{name}.ts <args>

// ─── Imports (stdlib first, then packages, then relative) ────────────────────
import { parseArgs } from "node:util";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import consola from "consola";

// ─── Configuration ───────────────────────────────────────────────────────────
const SCRIPT = fileURLToPath(import.meta.url);
const SCRIPT_DIR = dirname(SCRIPT);
const log = consola.withTag("{name}");

// ─── Core types and functions ────────────────────────────────────────────────
interface Result { /* ... */ }

export function doTheThing(input: string): Result { /* ... */ }

// ─── CLI interface ───────────────────────────────────────────────────────────
function printHelp(): void { /* ... */ }

export async function main(argv: string[] = Bun.argv.slice(2)): Promise<void> {
  const { values, positionals } = parseArgs({
    args: argv,
    options: { /* ... */ },
    allowPositionals: true,
    strict: true,
  });
  // ... dispatch ...
}

if (import.meta.main) {  // Bun's equivalent of `if __name__ == "__main__":`
  main().catch((err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`error: ${msg}`);
    process.exit(1);
  });
}
```

Two things to note:

1. **`export`**: the core functions are exported so tests can import them without executing `main()`.
2. **`if (import.meta.main)`**: guards the CLI bootstrap so the module is importable without side effects. This is the direct analog of Python's `if __name__ == "__main__":` block.

### Dependency Injection for Testability

Functions that use global paths should accept optional parameters:

```typescript
// ✅ CORRECT - allows testing with temp directories
export function processData(cachePath: string, dataPath: string = DEFAULT_DATA_PATH): Result {
  // ...
}

// ✅ CORRECT - main() accepts optional dependencies
export async function main(argv: string[], deps: { cache?: CacheManager } = {}): Promise<void> {
  const cache = deps.cache ?? new CacheManager();
  // ...
}
```

## Shell Wrapper (`{name}.sh`)

When required (see exception above), a minimal wrapper that invokes bun:

```bash
#!/usr/bin/env bash
# Wrapper script for {name}.ts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bun run "$SCRIPT_DIR/{name}.ts" "$@"
```

## Test File (`{name}.test.ts`)

Uses `bun:test`. No mocks — see `../tests.md`.

```typescript
import { describe, test, expect } from "bun:test";
import { doTheThing } from "./{name}.ts";

describe("{name}", () => {
  test("doTheThing returns expected result", () => {
    const result = doTheThing("input");
    expect(result).toEqual({ /* ... */ });
  });
});
```

### Running Tests

Tests run via `bun test` — not via a PEP-723-style `__main__` entry point. Unlike Python's pytest-cov reload hack, `bun test` instruments coverage from process start, so there's no "0% on module-level code" problem to solve.

```bash
bun test --cwd .claude/skills/{skill}/scripts/
bun test --cwd .claude/skills/{skill}/scripts/ --coverage
```

### Coverage Requirements

- **Minimum 90% line coverage**.
- Exclude the `if (import.meta.main)` bootstrap from coverage targets — it's equivalent to the `# pragma: no cover` Python convention.

## Makefile

Standard targets for all skill scripts. Key design decisions:

- **`--cwd`** keeps you at the project root while executing in the scripts directory.
- **Bun handles TS natively** — no separate compile step before test.
- **`bun run tsc --noEmit`** is the explicit typecheck step (Bun doesn't typecheck at runtime).

```makefile
# Makefile for {skill} TypeScript scripts
# Run from repo root: make -C .claude/skills/{skill}/scripts <target>

SCRIPT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
BUN := bun --cwd $(SCRIPT_DIR)

SCRIPTS = script_a script_b
PRIVATE_SCRIPTS = _update_examples

SRC := $(addsuffix .ts,$(SCRIPTS)) $(addsuffix .test.ts,$(SCRIPTS)) \
       $(addsuffix .ts,$(PRIVATE_SCRIPTS)) $(addsuffix .test.ts,$(PRIVATE_SCRIPTS))

.PHONY: all install test test-cov format format-check lint lint-fix \
        typecheck check fix clean help smoke ci docs

all: format lint typecheck test-cov

install:
	$(BUN) install

test:
	$(BUN) test

test-cov:
	$(BUN) test --coverage --coverage-reporter=text

format:
	$(BUN) x @biomejs/biome format --write .

format-check:
	$(BUN) x @biomejs/biome format .

lint:
	$(BUN) x @biomejs/biome lint .

lint-fix:
	$(BUN) x @biomejs/biome lint --write .

typecheck:
	$(BUN) x tsc --noEmit

# Wire private maintenance scripts to docs, make docs a ci dependency
docs:
	$(BUN) run _update_examples.ts

ci: format-check lint typecheck test-cov docs

fix: format lint-fix

smoke:
	$(BUN) run script_a.ts --help

clean:
	rm -rf node_modules .bun

help:
	@echo "Targets: all test test-cov format lint typecheck ci fix smoke clean"
```

## Running Quality Checks

Always run from project root using `make -C`:

```bash
make -C .claude/skills/{skill}/scripts all
make -C .claude/skills/{skill}/scripts test-cov
make -C .claude/skills/{skill}/scripts fix
```

## Differences from Python Skill Scripts

A few places where the TS version diverges from `../../python/helper_scripts/claude_skills.md`:

| Aspect | Python | TypeScript |
|--------|--------|------------|
| Dependency declaration | PEP-723 inline metadata, per-file | `package.json`, per-directory |
| Test entry point | `uv run test_{name}.py` (`__main__` dispatch) | `bun test` (native test runner) |
| Coverage reload hack | `conftest.py` with `importlib.reload()` | Not needed — `bun test` traces from process start |
| `if __name__ == "__main__":` | Python idiom | `if (import.meta.main)` |
| Lockfile | `uv.lock` | `bun.lock` |
| Typechecker | `mypy --strict` | `tsc --noEmit` (strict in `tsconfig.json`) |
| Formatter/Linter | `ruff format` + `ruff check` | `biome format` + `biome lint` |
