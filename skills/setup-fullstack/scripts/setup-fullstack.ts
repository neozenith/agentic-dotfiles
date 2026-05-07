#!/usr/bin/env bun

/**
 * setup-fullstack: scaffold a Python (FastAPI + uv) backend + React (Vite)
 * frontend, sibling backend/ + frontend/ under a top-level Makefile that
 * orchestrates both halves.
 *
 * This file is a thin CLI dispatcher. Each scaffolding phase lives in its
 * own module under steps/ and reuses helpers from lib/. The whole pipeline
 * is just calling each step in order, with a Ctx object plumbed through.
 *
 * For the full description of what gets scaffolded (tooling, ports, strict
 * policies, matrix variations), see the sibling SKILL.md.
 */

import { parseArgs } from "node:util";

import { elog, log } from "./lib/logger.ts";
import { resolveProjectPaths } from "./lib/paths.ts";
import { applyResources } from "./steps/05-apply-resources.ts";
import { writeDocs } from "./steps/06-docs.ts";
import { finalize } from "./steps/07-finalize.ts";
import { prepare } from "./steps/01-prepare.ts";
import { scaffoldVite } from "./steps/02-vite-scaffold.ts";
import { installFrontendTooling } from "./steps/03-frontend-tooling.ts";
import { setupTailwindAndShadcn } from "./steps/04-tailwind-shadcn.ts";

const HELP = `\
setup-fullstack — scaffold a Python (FastAPI + uv) backend + React (Vite)
                  frontend with shared Makefile orchestration.

USAGE
  bun .claude/skills/setup-fullstack/scripts/setup-fullstack.ts [target]

ARGUMENTS
  target              Project root for the scaffold. Defaults to "." (the
                      current working directory). May be relative or absolute.
                      A non-existent path is created.

OPTIONS
  -h, --help          Show this help and exit.
  --no-fix            Skip Step 15 (\`make fix\` autofix pass).
  --no-verify         Skip Step 16 (typecheck + tests verification). Implies
                      that the user will run \`make ci\` themselves.
                      \`make fix\` still runs unless --no-fix is also passed.

PIPELINE (each step is one module under scripts/steps/)
  Step 0   Snapshot user-curated docs (in-place flow only)
  Step 1   Create project structure
  Step 2   Vite + React + TypeScript scaffold (TTY-hardened)
  Step 3   Install frontend deps (Tailwind, shadcn deps, dev tooling)
  Step 4   Replace ESLint with Biome
  Step 5   Install Playwright Chromium
  Step 6   Patch tsconfig.json + tsconfig.app.json (strict family + @/*)
  Step 7   Patch biome.json (excludes + cssModules)
  Step 8   Merge package.json scripts
  Step 8.5 Pre-stage Tailwind v4 wiring
  Step 9   Initialize shadcn/ui
  Step 9.5 Add shadcn components (button, card)
  Step 10  Copy frontend resources on top of the Vite scaffold
  Step 10.5 Patch Vite-generated frontend files (.gitignore, main.tsx)
  Step 11  Copy backend resources
  Step 12  Copy top-level orchestration files (Makefile, .github, compose, …)
  Step 13  Write README.md + CONTRIBUTING.md
  Step 14  uv sync to materialise the backend venv
  Step 15  make fix (autofix) — surfaces failures loudly
  Step 16  Verify: make typecheck + make test

OUTPUT
  Every line is prefixed with [HH:MM:SS +Ns] showing wall-clock time and
  elapsed seconds since script start. A hang shows up as a long elapsed-time
  gap between adjacent lines. Long-running shell calls also emit a heartbeat
  (\`... still running: <label>\`) every 5 seconds.

EXIT CODES
   0  Setup complete.
   1  Any step failed (the failed step's output is dumped to stderr).
   2  Bad arguments (caught by parseArgs in strict mode).

EXAMPLES
  # Scaffold into the current directory
  bun .claude/skills/setup-fullstack/scripts/setup-fullstack.ts

  # Scaffold into a new subdirectory
  bun .claude/skills/setup-fullstack/scripts/setup-fullstack.ts my-fullstack-app

  # Scaffold but skip the verification step (faster for iteration)
  bun .claude/skills/setup-fullstack/scripts/setup-fullstack.ts --no-verify

DOCS
  See SKILL.md (sibling to scripts/) for the produced project's matrix of
  database backends, storage backends, and backup variations.
`;

const printSummary = (targetArg: string, isCurrentDir: boolean): void => {
  log("\nSetup complete.\n");
  log("Canonical inner-loop:");
  if (!isCurrentDir) {
    log(`  cd ${targetArg}`);
  }
  log("  make fix ci          # autofix everything, then run the strict gate");
  log("\nDev:");
  log("  make dev             # backend 8200 + frontend 5173 (human profile)");
  log("  make agentic-dev     # backend 8201 + frontend 5174 (agent profile)");
  log("\nNarrow inner-loops:");
  log("  make test-py         # backend pytest only");
  log("  make test-ts         # frontend vitest only");
  log("  make typecheck-py    # mypy only");
  log("  make typecheck-ts    # tsc only");
  log("  make test-e2e        # Playwright (auto-launches both halves)");
  log("\nDiscover everything:");
  log("  make help");
};

const main = async (): Promise<void> => {
  const { values, positionals } = parseArgs({
    args: Bun.argv.slice(2),
    options: {
      help: { type: "boolean", short: "h", default: false },
      "no-fix": { type: "boolean", default: false },
      "no-verify": { type: "boolean", default: false },
    },
    allowPositionals: true,
    strict: true,
  });

  if (values.help) {
    process.stdout.write(`${HELP}\n`);
    return;
  }

  const target = positionals[0] ?? ".";
  if (positionals.length > 1) {
    elog(`error: too many positional arguments (got ${positionals.length}, expected 0–1)`);
    process.exit(2);
  }

  const paths = resolveProjectPaths(target);
  log(`Setting up fullstack app in ${paths.displayName}...`);

  // Step 0 + 1: snapshot existing docs and create the project structure.
  const ctx = prepare(paths);

  // Step 2: Vite scaffold. Chdirs into frontend/ on success.
  await scaffoldVite(ctx);

  // Steps 3–8: deps, biome, playwright, configs.
  await installFrontendTooling();

  // Steps 8.5, 9, 9.5: Tailwind v4 + shadcn.
  await setupTailwindAndShadcn(ctx);

  // Steps 10–12: copy frontend, backend, top-level resources.
  applyResources(ctx);

  // Step 13: docs.
  writeDocs(ctx);

  // Steps 14–16: install backend, autofix, verify (with skip flags).
  await finalize({
    skipFix: values["no-fix"],
    skipVerify: values["no-verify"],
  });

  printSummary(paths.targetArg, paths.isCurrentDir);
};

if (import.meta.main) {
  main().catch((err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    elog(`setup-fullstack: ${msg}`);
    process.exit(1);
  });
}
