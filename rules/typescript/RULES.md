---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.mts"
  - "**/*.cts"
---

# TypeScript Code Conventions

Universal rules for all TypeScript code. Assumes Bun as the runtime (see `bun.md`).

## Modules

**ESM only.** `"type": "module"` in every `package.json`. No CommonJS (`require`, `module.exports`, `__dirname`, `__filename`).

**All imports MUST be at the top of the file.** No dynamic `import()` inside functions unless the import is genuinely conditional (code-splitting, optional peer deps) and that conditionality is documented.

```typescript
// ✅ CORRECT - all imports at top, ESM
import { parseArgs } from "node:util";
import { resolve } from "node:path";
import { readFile } from "node:fs/promises";
```

```typescript
// ❌ FORBIDDEN - dynamic import used to hide a missing dep
async function maybeDoThing() {
  const mod = await import("some-lib");  // NEVER use this as a fallback pattern
}

// ❌ FORBIDDEN - CommonJS
const fs = require("fs");
```

**Why:** dynamic imports hide dependency graphs, break tree-shaking and type resolution, and mask missing packages as runtime errors instead of load-time errors. Same reasoning as Python's "imports at the top" rule.

## File Handling

**Prefer `Bun.file()` over `node:fs`** in Bun scripts. Bun's file API is zero-copy and lazy, equivalent to the async pattern you'd want anyway.

```typescript
// ✅ CORRECT - Bun native
const file = Bun.file(path);
if (!(await file.exists())) throw new Error(`not found: ${path}`);
const text = await file.text();
const json = await file.json();

// ✅ CORRECT - cross-runtime (node:fs/promises) when the code must also run under Node
import { readFile, writeFile } from "node:fs/promises";
const text = await readFile(path, "utf8");
await writeFile(path, content, "utf8");
```

Never use sync versions (`readFileSync`, `writeFileSync`) outside of top-level script init. Never hand-join paths with `"/"` — use `node:path`.

## Strings and Paths

Use template literals for interpolation. Use `node:path` (`resolve`, `join`, `dirname`, `basename`) for all path manipulation.

```typescript
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = fileURLToPath(import.meta.url);
const SCRIPT_DIR = dirname(SCRIPT);
const PROJECT_ROOT = resolve(SCRIPT_DIR, "..");
```

(ESM has no `__dirname`; use `import.meta.url` + `fileURLToPath`. Bun also exposes `import.meta.dir` and `import.meta.path` as shortcuts.)

## Logging

- **Never use `console.log` for production output** — use a structured logger (`consola`, `pino`, or a minimal in-house wrapper).
- For CLI tools, `console.log` is acceptable for *user-facing* output (the "print to stdout" channel). Errors and diagnostics go to `console.error` (stderr) so `| jq` and friends keep working.
- Get a logger at module scope, not per-call.

```typescript
import { consola } from "consola";
const log = consola.withTag("my-module");

log.info("processing %d items", count);
log.debug({ details }, "details");
log.error({ err }, "failed to process");
```

## Environment Variables

Bun auto-loads `.env`, `.env.local`, and `.env.<NODE_ENV>` — **do not** add `dotenv`.

```typescript
const apiKey = Bun.env.API_KEY ?? process.env.API_KEY;
if (!apiKey) throw new Error("API_KEY not set");
```

Check for `.env.sample` at the project root to discover what variables exist.

## Git Integration

For code needing git context, use `Bun.$` (the tagged-template shell) — it handles quoting correctly and returns trimmed text:

```typescript
import { $ } from "bun";

const GIT_ROOT = (await $`git rev-parse --show-toplevel`.text()).trim();
const GIT_BRANCH = (await $`git rev-parse --abbrev-ref HEAD`.text()).trim();
```

Never assemble shell commands by string concatenation — that's command injection.

## Type Safety

Enable the strict family in every `tsconfig.json`:

```jsonc
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noPropertyAccessFromIndexSignature": true,
    "exactOptionalPropertyTypes": true
  }
}
```

`noUncheckedIndexedAccess` in particular catches the same class of bug as Python's `list[i]` returning `None` for out-of-range — it forces you to narrow before use.

**Never use `any`.** If you truly don't know the shape, use `unknown` and narrow with a type guard. `any` propagates silently; `unknown` forces a check at the boundary.

```typescript
// ✅ CORRECT
function parseJson(raw: string): unknown {
  return JSON.parse(raw);
}

const data = parseJson(input);
if (isRecord(data) && typeof data.count === "number") {
  // data.count is now typed
}

// ❌ FORBIDDEN
function parseJson(raw: string): any { ... }
```

## Testing

- Use `bun:test` (built into Bun) — no `jest`, `vitest`, or `mocha` unless cross-runtime is required.
- Leverage `test.each(...)` for parametrized tests.
- Write code that is easy to test (pure functions, dependency injection).

See `tests.md` for the full testing rules.

## Quality Assurance

Run these regularly (wire into `Makefile`):

```bash
# Format + lint (pick ONE — do not combine Biome with ESLint/Prettier)
bunx --bun @biomejs/biome check --write .

# OR the legacy ESLint + Prettier stack, if the project already uses it:
bunx eslint --fix .
bunx prettier --write .

# Type check (Bun has no native tsc; use the TypeScript compiler through bun)
bun run tsc --noEmit
```

Biome is preferred for new TypeScript projects — it's a single binary that replaces both ESLint and Prettier, and it's ~10-100x faster.

## Documentation

- When generating `README.md`, include MermaidJS architecture diagrams.
- Use color to make diagram boxes visually distinct.
- Ensure text color contrasts with background colors (WCAG AA: 4.5:1 minimum).
- Use emoji in diagram box names for expressiveness.

## Data Formats

**Avoid CSV** unless explicitly requested. Prefer:
- **In-memory**: plain objects, `Map`/`Set`, Arrow tables via `apache-arrow`
- **Persistence**: JSON, SQLite (`bun:sqlite` is built-in), DuckDB, Parquet
- **Exchange**: JSON, Arrow IPC, MessagePack

```typescript
// Bun has bun:sqlite built-in — no dep needed
import { Database } from "bun:sqlite";
const db = new Database(":memory:");
db.run("CREATE TABLE items (id INTEGER, name TEXT)");
```
