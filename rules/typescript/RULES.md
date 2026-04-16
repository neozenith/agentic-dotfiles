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

## Functions

**Prefer arrow functions over `function` declarations.** Arrow form is more consistent with the rest of modern TypeScript, avoids the `this`-binding pitfalls of `function`, and reads uniformly whether the body is a one-liner or a block.

```typescript
// ✅ CORRECT
const toSlug = (name: string): string => name.toLowerCase().replace(/\s+/g, "-");

export const processData = async (input: Input): Promise<Output> => {
  // ...
};
```

```typescript
// ❌ AVOID — do not use `function` declarations for new code
export function processData(input: Input): Promise<Output> { ... }
```

Exceptions — use `function` only when you genuinely need one of these:
- Hoisting (rarely required if imports/constants are ordered correctly).
- A named function for clearer stack traces in hot paths where stack readability matters.
- Generator functions (`function*`) — arrow form has no generator equivalent.

## Logging

- **Never use `console.log` for production output** — use a structured logger.
- For CLI tools, `console.log` is acceptable for *user-facing* output (the "print to stdout" channel). Errors and diagnostics go to `console.error` (stderr) so `| jq` and friends keep working.
- Get a logger at module scope, not per-call.

**Preferred: `pino` with `pino-pretty` for local dev.** Pino is the default structured logger; it emits JSON in production and a human-readable stream in dev.

Every project gets a `utils/logger.ts` like this:

```typescript
// utils/logger.ts
import pino from "pino";

const isDev = process.env.NODE_ENV !== "production";

export const logger = pino(
  isDev ? { transport: { target: "pino-pretty" } } : {}
);
```

Consumers import the shared instance:

```typescript
import { logger } from "./utils/logger.ts";

logger.info({ count }, "processing items");
logger.debug({ details }, "details");
logger.error({ err }, "failed to process");
```

`consola` remains acceptable for CLI tools where pretty output is the *only* mode (no production JSON stream needed) — but pino is the default for services and long-lived processes.

## Environment Variables

Bun auto-loads `.env`, `.env.local`, and `.env.<NODE_ENV>` — **do not** add `dotenv`.

**All env-var access goes through a central `utils/const.ts` registry.** Never read `process.env` (or `Bun.env`) inline elsewhere in the codebase. This mirrors the Python `cli/config.py` convention — one file owns the environment surface, so missing-variable errors surface at load time rather than on first-use deep in a request handler.

```typescript
// utils/const.ts
const required = (key: string): string => {
  const value = process.env[key];
  if (value === undefined) {
    throw new Error(`Undefined required environment variable - ${key}`);
  }
  return value;
};

const optional = (key: string, fallback: string): string => process.env[key] ?? fallback;

export const PORT = parseInt(optional("PORT", "3000"), 10);
export const API_KEY = required("API_KEY");
// Add every env var the app reads here — and nowhere else.
```

Check for `.env.sample` at the project root to discover what variables exist.

For complex env shapes (nested config, coerced types, enums), validate the final export with **zod** — see *Runtime Validation* below.

## Runtime Validation

**Use `zod` for any data crossing a trust boundary.** The TypeScript compiler validates shapes *inside* your code; zod validates shapes coming *into* your code. Anywhere you'd normally trust a `JSON.parse` result, a form submission, or an external API response, wrap it in a zod schema so the `unknown` becomes a typed value through a runtime check, not a cast.

```typescript
import { z } from "zod";

const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  age: z.number().int().nonnegative(),
});
type User = z.infer<typeof UserSchema>;

const parseUser = (raw: unknown): User => UserSchema.parse(raw);
```

Apply zod at these boundaries specifically:

- **HTTP request bodies / query params** — parse inside the route handler, before business logic sees the value.
- **External API responses** — never trust response bodies to match the OpenAPI schema in production.
- **Config files** (`*.json`, `*.yaml` loaded at startup) — validate shape at load time, fail fast on misconfiguration.
- **Inter-service messages** (queue payloads, websocket frames) — validate on receive.

Prefer `.parse()` (throws) over `.safeParse()` (returns a discriminated union) unless the calling code has a specific fallback for invalid data. A thrown `ZodError` at a boundary is the correct failure signal — same reasoning as the "no graceful degradation" rule.

## HTTP & Network Services

Use Bun's built-in APIs instead of adding Node-era libraries:

| Instead of | Use |
|---|---|
| `express`, `fastify`, `koa` | `Bun.serve()` (routes + HTTPS + WebSockets, no deps) |
| `ws` | The built-in `WebSocket` (client) and `Bun.serve({ websocket })` (server) |
| `ioredis`, `node-redis` | `Bun.redis` |
| `pg`, `postgres.js` | `Bun.sql` |
| `better-sqlite3` | `bun:sqlite` |
| `execa`, `child_process` | `` Bun.$`command` `` |

### `Bun.serve()`

```typescript
import index from "./index.html";

Bun.serve({
  routes: {
    "/": index,
    "/api/users/:id": {
      GET: (req) => Response.json({ id: req.params.id }),
    },
  },
  websocket: {
    open: (ws) => ws.send("connected"),
    message: (ws, msg) => ws.send(msg),
    close: () => {},
  },
  development: { hmr: true, console: true },
});
```

Validate request bodies with zod inside the handler before doing any work.

### `Bun.sql` (Postgres)

```typescript
import { sql } from "bun";
const users = await sql`SELECT id, email FROM users WHERE active = ${true}`;
```

Tagged-template parameters are always escaped — never build SQL by string concatenation.

### `bun:sqlite`

```typescript
import { Database } from "bun:sqlite";
const db = new Database("app.db");
```

### `Bun.redis`

```typescript
import { redis } from "bun";
await redis.set("key", "value");
const value = await redis.get("key");
```

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
- **Persistence**: JSON, SQLite (`bun:sqlite` is built-in — see *HTTP & Network Services*), DuckDB, Parquet
- **Exchange**: JSON, Arrow IPC, MessagePack
