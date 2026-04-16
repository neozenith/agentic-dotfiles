---
paths:
  - "scripts/**/*.ts"
  - "**/scripts/*.ts"
---

# TypeScript Helper Scripts

Rules for standalone TypeScript helper scripts executed with Bun.

> Extends `../RULES.md` for standalone scripts.

See also [../../claude_skills.md](../../claude_skills.md) when the script lives under `.claude/skills/*/scripts/` (merged Python + TypeScript conventions, also covers mixed-language skills).

## Execution

- **Always run with `bun`**: `bun run scripts/script_name.ts`
- **Never use `node`, `tsx`, or `ts-node`** — Bun runs TypeScript natively without transpilation.
- **Never inline with `bun -e '...'`** — create a script file instead. Inline snippets are unreviewable and untestable.
- **Support `--help`** — all scripts must be self-documenting.
- **Add a shebang**: `#!/usr/bin/env bun` so the file can run as `./scripts/script_name.ts` after `chmod +x`.

## Dependencies

Unlike Python's PEP-723 inline metadata, TypeScript scripts declare dependencies in a sibling `package.json`. A self-contained script directory looks like:

```
scripts/
├── package.json        # deps + devDeps + "type": "module"
├── tsconfig.json       # strict, types: ["bun"], noEmit: true
├── bun.lock            # committed lockfile
├── .gitignore          # node_modules/
├── script_a.ts
└── ...
```

Minimum `package.json`:

```json
{
  "name": "<skill-or-project>-scripts",
  "private": true,
  "type": "module",
  "devDependencies": {
    "@types/bun": "latest",
    "typescript": "^5"
  }
}
```

Minimum `tsconfig.json`:

```jsonc
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "types": ["bun"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "skipLibCheck": true,
    "allowImportingTsExtensions": true,
    "noEmit": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["*.ts"]
}
```

Runtime dependencies go under `"dependencies"`; add them with `bun add <pkg>`.

## Structure

### Configuration at Top

All config constants `CAPITALIZED`, declared right after imports, before any functions:

```typescript
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = fileURLToPath(import.meta.url);
const SCRIPT_NAME = SCRIPT.split("/").pop()!.replace(/\.ts$/, "");
const SCRIPT_DIR = dirname(SCRIPT);
const PROJECT_ROOT = resolve(SCRIPT_DIR, "..");

const CACHE_DIR = resolve(PROJECT_ROOT, "tmp", "claude_cache", SCRIPT_NAME);
```

### No Global Side-Effects at Import Time

Keep import-time code to constant declarations. All I/O (reading files, spawning processes, fetching URLs) happens inside `main()` or a function it calls, never at the top level of the module. This is what makes the script testable without running it.

## CLI Arguments

**DO NOT replace CAPITALIZED config constants with CLI arguments or flags.** Constants are for values that don't change per-invocation; flags are for user intent.

Standard flags (include where relevant):
- `-v/--verbose`: Debug logging
- `-q/--quiet`: Errors only
- `-f/--force`: Ignore cache / overwrite
- `-n/--dry-run`: No destructive changes
- `--cache-check`: Check cache status only
- `-L/--limit N`: Limit iterations
- `-T/--timeout N`: Self-imposed timeout
- `--json`: Machine-readable output

Use `node:util.parseArgs`. See `../cli.md`.

## Caching

- Output to `tmp/claude_cache/{script_name}/` under the project root.
- Default timeout: **300 seconds (5 minutes)** — see the project-level `.claude/rules/caching.md`.
- Implement a `checkCache(): { delta: number; remaining: number }` helper returning the tuple described in `caching.md`.
- A cache is valid when both `delta > 0` and `remaining > 0`.

Never use the OS temp dir (`/tmp/`, `os.tmpdir()`) — see the global `CLAUDE.md` rule.

## Testing

- Test file as sibling: `scripts/{script_name}.test.ts`
- Use `bun:test` (see `../tests.md`).
- Run as `bun test scripts/{script_name}.test.ts` from the project root, or `bun test --cwd <scripts-dir>` for a scoped run.
- No mocks — test real code with real dependencies (in-memory SQLite, real file I/O in `tmp/`, real subprocesses).

## References

Conditional rule files that extend this base. Each activates based on its frontmatter `paths:` globs:

- [../../claude_skills.md](../../claude_skills.md) — Merged Python + TypeScript conventions for scripts inside `.claude/skills/*/scripts/`. Use when writing **TypeScript scripts that are part of a Claude skill** (also covers mixed-language skills).

(More conditional rule files — e.g., AWS patterns, ML workflows, manifest patterns — can be added here as TypeScript helper scripts grow into those domains, mirroring the Python helper-scripts hierarchy.)
