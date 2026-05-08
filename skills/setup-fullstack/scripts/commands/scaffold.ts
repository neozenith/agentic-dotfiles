// `scaffold` subcommand — runs the seven-step pipeline that produces a
// fullstack project. The orchestration logic was previously inline in
// setup-fullstack.ts; it is unchanged here, only relocated.

import { parseArgs } from "node:util";

import { elog, log } from "../lib/logger.ts";
import { resolveProjectPaths } from "../lib/paths.ts";
import { applyResources } from "../steps/05-apply-resources.ts";
import { writeDocs } from "../steps/06-docs.ts";
import { finalize } from "../steps/07-finalize.ts";
import { prepare } from "../steps/01-prepare.ts";
import { scaffoldVite } from "../steps/02-vite-scaffold.ts";
import { installFrontendTooling } from "../steps/03-frontend-tooling.ts";
import { setupTailwindAndShadcn } from "../steps/04-tailwind-shadcn.ts";

export const SCAFFOLD_HELP = `\
setup-fullstack scaffold — produce a Python (FastAPI + uv) backend + React
                            (Vite) frontend project with shared Makefile
                            orchestration.

USAGE
  setup-fullstack scaffold [target] [--no-fix] [--no-verify]

ARGUMENTS
  target              Project root for the scaffold. Defaults to "." (current
                      working directory). May be relative or absolute. A
                      non-existent path is created.

OPTIONS
  -h, --help          Show this help and exit.
  --no-fix            Skip Step 15 (\`make fix\` autofix pass).
  --no-verify         Skip Step 16 (typecheck + tests verification). Implies
                      that the user will run \`make ci\` themselves. \`make fix\`
                      still runs unless --no-fix is also passed.

PIPELINE
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
  Step 12  Copy top-level orchestration files
  Step 13  Write README.md + CONTRIBUTING.md
  Step 14  uv sync to materialise the backend venv
  Step 15  make fix (autofix)
  Step 16  Verify: make typecheck + make test

EXIT CODES
   0  Setup complete.
   1  Any step failed.
   2  Bad arguments.

EXAMPLES
  setup-fullstack scaffold
  setup-fullstack scaffold my-fullstack-app
  setup-fullstack scaffold --no-verify
`;

export interface ScaffoldOptions {
  target: string;
  skipFix: boolean;
  skipVerify: boolean;
}

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

export const runScaffold = async (opts: ScaffoldOptions): Promise<void> => {
  const paths = resolveProjectPaths(opts.target);
  log(`Setting up fullstack app in ${paths.displayName}...`);

  const ctx = prepare(paths);
  await scaffoldVite(ctx);
  await installFrontendTooling();
  await setupTailwindAndShadcn(ctx);
  applyResources(ctx);
  writeDocs(ctx);
  await finalize({ skipFix: opts.skipFix, skipVerify: opts.skipVerify });

  printSummary(paths.targetArg, paths.isCurrentDir);
};

/** Parse `scaffold`-subcommand argv into options + dispatch. */
export const scaffoldMain = async (argv: string[]): Promise<void> => {
  const { values, positionals } = parseArgs({
    args: argv,
    options: {
      help: { type: "boolean", short: "h", default: false },
      "no-fix": { type: "boolean", default: false },
      "no-verify": { type: "boolean", default: false },
    },
    allowPositionals: true,
    strict: true,
  });

  if (values.help) {
    process.stdout.write(SCAFFOLD_HELP);
    return;
  }

  if (positionals.length > 1) {
    elog(`error: too many positional arguments (got ${positionals.length}, expected 0–1)`);
    process.exit(2);
  }

  await runScaffold({
    target: positionals[0] ?? ".",
    skipFix: values["no-fix"] === true,
    skipVerify: values["no-verify"] === true,
  });
};
