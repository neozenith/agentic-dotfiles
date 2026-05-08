#!/usr/bin/env bun

/**
 * setup-fullstack — standalone CLI for scaffolding a Python (FastAPI + uv)
 * backend + React (Vite) frontend, and for exercising the runtime variation
 * matrix the scaffold supports.
 *
 * Subcommands:
 *   scaffold           Produce the project (the original behavior).
 *   variation <name>   Boot the stack for one variation, run its tests.
 *   matrix             Scaffold once + run every variation in sequence.
 *   list-variations    Print every known variation.
 *
 * The CLI is self-contained: nothing in this tree assumes it lives under
 * .claude/skills/. Drop the `scripts/` + `resources/` pair anywhere on disk
 * and the orchestrator works (path resolution is anchored to the script's
 * own location, not the project's git root).
 */

import { elog } from "./lib/logger.ts";
import { matrixMain, MATRIX_HELP } from "./commands/matrix.ts";
import { scaffoldMain, SCAFFOLD_HELP } from "./commands/scaffold.ts";
import { variationMain, VARIATION_HELP } from "./commands/variation.ts";
import {
  listVariationsMain,
  LIST_VARIATIONS_HELP,
} from "./commands/list-variations.ts";

const TOP_LEVEL_HELP = `\
setup-fullstack — scaffold + exercise a Python (FastAPI + uv) backend +
                  React (Vite) frontend project.

USAGE
  setup-fullstack <command> [options]
  setup-fullstack <command> --help     # detailed help for one command
  setup-fullstack --help               # this message

COMMANDS
  scaffold           Produce the fullstack project. Defaults to the current
                     working directory; pass an explicit target to scaffold
                     elsewhere. This is what you want when starting fresh.

  variation <name>   Boot the docker stack for one named variation
                     (database × storage × backup combo), run that variation's
                     assertions + tests, then tear down. Exits 0 on PASS,
                     1 on FAIL, 77 on SKIP. See \`list-variations\`.

  matrix             Scaffold once + iterate every variation. Exits 0 if every
                     variation either PASSed or SKIPped, else 1.

  list-variations    Print every known variation. \`--names-only\` for pipelines.

GLOBAL FLAGS
  -h, --help         Show this message (when used with no subcommand) or the
                     subcommand's help (when after a subcommand).

INVOCATION
  This is a standalone Bun CLI. The recommended invocation is:

    bun setup-fullstack.ts <command> [options]

  Or, if executed directly with a shebang on a +x file:

    ./setup-fullstack.ts <command> [options]

EXAMPLES
  # Scaffold a fresh project into a new subdirectory
  bun setup-fullstack.ts scaffold ./my-fullstack-app

  # Run the in-process unit suite for the sqlite-memory variation
  bun setup-fullstack.ts variation sqlite-memory --root ./my-fullstack-app

  # Run every variation against an existing scaffold (skip re-scaffolding)
  bun setup-fullstack.ts matrix --root ./my-fullstack-app --skip-scaffold

  # Pipeline-style: iterate every variation by name
  bun setup-fullstack.ts list-variations --names-only \\
    | xargs -n1 bun setup-fullstack.ts variation --root ./my-fullstack-app

EXIT CODES
   0  Success
   1  Runtime error (failed step, FAIL verdict, scaffold or build failure)
   2  Usage error (unknown subcommand, bad flag — caught by parseArgs)
  77  SKIP (variation only)
`;

const HELP_BY_COMMAND: Record<string, string> = {
  scaffold: SCAFFOLD_HELP,
  variation: VARIATION_HELP,
  matrix: MATRIX_HELP,
  "list-variations": LIST_VARIATIONS_HELP,
};

const main = async (): Promise<number> => {
  const argv = Bun.argv.slice(2);
  const cmd = argv[0];

  if (!cmd || cmd === "-h" || cmd === "--help") {
    process.stdout.write(TOP_LEVEL_HELP);
    return 0;
  }

  if (cmd === "help") {
    const sub = argv[1];
    if (!sub) {
      process.stdout.write(TOP_LEVEL_HELP);
      return 0;
    }
    const help = HELP_BY_COMMAND[sub];
    if (!help) {
      elog(`error: unknown command '${sub}'`);
      return 2;
    }
    process.stdout.write(help);
    return 0;
  }

  const rest = argv.slice(1);

  switch (cmd) {
    case "scaffold":
      await scaffoldMain(rest);
      return 0;
    case "variation":
      return variationMain(rest);
    case "matrix":
      return matrixMain(rest);
    case "list-variations":
      return listVariationsMain(rest);
    default:
      elog(`error: unknown command '${cmd}'`);
      elog(
        "Valid: scaffold, variation, matrix, list-variations. Try `--help`.",
      );
      return 2;
  }
};

if (import.meta.main) {
  main()
    .then((code) => process.exit(code))
    .catch((err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      elog(`setup-fullstack: ${msg}`);
      process.exit(1);
    });
}
