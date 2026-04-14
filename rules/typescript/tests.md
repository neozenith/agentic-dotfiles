---
paths:
  - "**/*.test.ts"
  - "**/*.spec.ts"
  - "**/test/**/*.ts"
  - "**/tests/**/*.ts"
---

# TypeScript Testing Rules

## Framework Choice

Use **`bun:test`** (built into Bun). Do not introduce `jest`, `vitest`, `mocha`, or `ava` unless the project must also run on Node/Deno and cross-runtime portability is a hard requirement — in which case prefer `vitest` (API-compatible with `bun:test`).

```typescript
import { describe, test, expect, beforeEach } from "bun:test";
```

Run with `bun test` (no script needed — it's a built-in subcommand). Coverage with `bun test --coverage`.

## No Mocks, No Stubs, No Spies — No Exceptions

**NEVER use mocking in tests.** This is non-negotiable. The rule applies to `bun:test`'s `mock()` and `spyOn()`, to `jest.mock()`, to `vi.mock()`, and to any hand-rolled mock object.

### Forbidden

```typescript
// ❌ ALL FORBIDDEN
import { mock, spyOn } from "bun:test";

const fakeFetch = mock(() => Promise.resolve({ json: () => ({}) }));
const spy = spyOn(obj, "method");
const fakeDb = { query: mock(), insert: mock() };  // ad-hoc fake object
```

### Why Mocks Are Forbidden

1. **Mocks test your assumptions, not your code** — a passing mock test only proves you correctly guessed the interface.
2. **Mocks hide bugs** — when the real implementation changes, mock tests keep passing.
3. **Mocks create maintenance burden** — every mock is technical debt that must track the real implementation.
4. **Mocks give false confidence** — high coverage with mocks is meaningless coverage.

### What To Do Instead

**Test real code with real dependencies:**

```typescript
// ✅ CORRECT - real SQLite database
import { Database } from "bun:sqlite";
import { test, expect } from "bun:test";

test("cache stores data", () => {
  const db = new Database(":memory:");
  const cache = new CacheManager(db);
  cache.initSchema();
  cache.store("key", "value");
  expect(cache.get("key")).toBe("value");
});
```

**Use dependency injection for external services:**

```typescript
// ✅ CORRECT - inject real implementations
function processData(db: Database, api: ApiClient) { ... }

// In tests, use real test instances:
test("processData", async () => {
  const db = new Database(":memory:");
  const api = new TestApiServer();  // real server on a random port
  await api.start();
  try {
    const result = await processData(db, api);
    expect(result).toEqual(...);
  } finally {
    await api.stop();
  }
});
```

**Skip tests for code that can't be tested without mocks:**

```typescript
// ✅ CORRECT - if you can't test it for real, don't pretend
test.skip("requires external claude CLI", () => { ... });
// Or simply don't write the test at all.
```

**Use `beforeEach`/`afterEach` for setup, not mock scaffolding:**

```typescript
let db: Database;
beforeEach(() => {
  db = new Database(":memory:");
  db.run("CREATE TABLE items (id INTEGER, name TEXT)");
});
afterEach(() => db.close());
```

## Never Skip Tests for Code You Wrote

**If you wrote the code, you test the code.** Conditional skips gated on `try { require(...) } catch` are NOT acceptable for testing code you just created.

### Forbidden Pattern

```typescript
// ❌ FORBIDDEN - this is a lie, not a test
let available = false;
try {
  await import("some-heavy-dep");
  available = true;
} catch { /* ignore */ }

test.skipIf(!available)("ML feature", () => { ... });  // NEVER RUNS
```

### Correct Pattern

Declare the dep in `package.json`. `bun install` resolves it. If it fails to install, the test suite fails — which is the correct signal that your environment is broken, not that the test should be skipped.

```json
{ "devDependencies": { "some-heavy-dep": "^1.0.0" } }
```

```typescript
// ✅ CORRECT - dep is always installed, test always runs
import { someHeavyDep } from "some-heavy-dep";
test("ML feature", () => { ... });
```

## Capturing Output

`bun:test` doesn't have a `capsys` analog — use `Bun.spawn()` for tests that assert on CLI output, not monkey-patching `console.log`.

```typescript
// ✅ CORRECT - run the CLI as a subprocess, assert on its output
test("cli prints status as json", async () => {
  const proc = Bun.spawn(["bun", "run", "src/cli.ts", "status", "--json"]);
  const output = await new Response(proc.stdout).text();
  const exitCode = await proc.exited;
  expect(exitCode).toBe(0);
  expect(JSON.parse(output)).toMatchObject({ healthy: true });
});

// ❌ FORBIDDEN
const originalLog = console.log;
console.log = mock();
myFunction();
console.log = originalLog;
```

## Testing CLI Arguments

Test the underlying command *function* with plain objects — not by patching `parseArgs`:

```typescript
// ✅ CORRECT - call the handler directly with a shaped args object
import { cmdStatus } from "../src/cli/commands/status.ts";

test("status handler", async () => {
  await cmdStatus({ json: true, _: [] });
  // assert on side effects, returned value, DB state, etc.
});

// ❌ FORBIDDEN
const mockArgs = mock();
mockArgs.command = "status";
```

## Temporary Directories

Use the project-local `tmp/` directory (see global `CLAUDE.md`), not the OS temp dir:

```typescript
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";

let tmpDir: string;
beforeEach(async () => {
  tmpDir = await mkdtemp(join("tmp", "test-"));  // project-local
});
afterEach(async () => {
  await rm(tmpDir, { recursive: true, force: true });
});
```

Never use `os.tmpdir()` — it resolves to `/tmp/` which violates the project-local-temp rule.

## Parametrized Tests

Use `test.each` (built into `bun:test`):

```typescript
test.each([
  ["a", 1],
  ["b", 2],
  ["c", 3],
])("function(%s) === %d", (input, expected) => {
  expect(myFunction(input)).toBe(expected);
});
```

## Coverage Requirements

- **Minimum 90% line coverage** for all non-trivial modules.
- Exclude `src/cli/app.ts` entry-point glue from coverage (analogous to Python's `if __name__ == "__main__":`) by moving the `.catch(process.exit)` boilerplate into a file the tests don't import.

```bash
bun test --coverage --coverage-reporter=text --coverage-reporter=lcov
```
