# TypeScript Tooling: Always Use bun

## Core Rule

**Always use `bun` for all TypeScript/JavaScript operations.** Never fall back to `node`, `tsx`, `ts-node`, `npm`, `yarn`, `pnpm` (unless the project explicitly uses pnpm workspaces — see subdirectory section), or direct `.ts` → `.js` transpilation via the TypeScript compiler.

## Running Scripts and Modules

```bash
# Run a single TypeScript file (Bun handles TS natively — no build step)
bun run scripts/analyze.ts

# Run a package.json "scripts" entry
bun run build
bun run test

# Run with the shebang form
./scripts/analyze.ts          # if the file has `#!/usr/bin/env bun`

# Run without reading the lockfile (env already correct, or offline)
bun run --no-install scripts/analyze.ts

# Run in a frozen lockfile mode (CI, reproducible runs)
bun install --frozen-lockfile && bun run scripts/analyze.ts
```

**`--no-install`** — skip the implicit `bun install`; use existing `node_modules` as-is. Use when offline or when the env is known good.
**`--frozen-lockfile`** — use `bun.lock` as-is, fail if drift detected. Use in CI or reproducible runs.

## Managing Dependencies

```bash
# Add a runtime dependency (updates package.json + bun.lock)
bun add somelib

# Add multiple dependencies
bun add libA libB libC

# Add a dev dependency
bun add --dev @types/bun typescript biome

# Add an exact version (no ^ or ~)
bun add --exact somelib@1.2.3

# Install from lockfile (equivalent to `bun install`)
bun install

# Install without dev dependencies
bun install --production
```

**NEVER use `npm install`, `yarn add`, or `pnpm add`** inside a bun project — they produce a different lockfile, mismatched `node_modules` layout, and break `bun install`'s integrity checks.

## One-Off Package Execution

Bun exposes `bunx` as the equivalent of `npx` / `uvx`:

```bash
# Run a package without installing it globally
bunx @biomejs/biome check .
bunx --bun tsc --noEmit
bunx prettier --write .
```

The `--bun` flag forces the package to execute on Bun's runtime instead of Node. Use it for CLIs that work on Bun; omit for CLIs that don't (rare).

## Subdirectory Projects

For self-contained subprojects with their own `package.json`:

```bash
bun install --cwd subproject
bun run --cwd subproject test
bun run --cwd subproject scripts/analyze.ts
```

This keeps you at the project root while activating the correct `node_modules` for that subproject. Never `cd` into a subdirectory — see the global `CLAUDE.md` working directory rules.

### pnpm Workspaces Exception

If the project is a `pnpm` workspace (has `pnpm-workspace.yaml`), use `pnpm` for install and dependency management, but **still use `bun run` to execute scripts**. `pnpm` is the lockfile/workspace tool; `bun` is the runtime. Do not mix `bun add` and `pnpm add` in the same workspace.

## Runtime Shebangs

Self-contained executable scripts get a bun shebang:

```typescript
#!/usr/bin/env bun
// script content
```

Make it executable with `chmod +x script.ts` and it runs as `./script.ts`. This is the TypeScript equivalent of the `#!/usr/bin/env -S uv run python` pattern, except Bun doesn't need a launcher — it executes `.ts` files directly.

## What NOT to Do

```bash
# WRONG — never invoke node directly on a .ts file
node script.ts
ts-node script.ts
tsx script.ts

# WRONG — never use npm/yarn in a bun project
npm install somelib
yarn add somelib

# WRONG — never cd to use bun
cd subproject && bun install

# WRONG — never use npm scripts that shell out to node
"scripts": { "start": "node dist/index.js" }
# use instead:
"scripts": { "start": "bun run src/index.ts" }

# WRONG — never compile TS to JS just to run it
tsc && node dist/script.js
# Bun runs .ts directly:
bun run src/script.ts
```

## Lockfile

Bun uses a text lockfile: `bun.lock` (Bun ≥ 1.2). Older projects may have `bun.lockb` (binary) — migrate to text with `bun install --save-text-lockfile` on the next lock change. **Commit the lockfile**, never ignore it.
