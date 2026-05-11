#!/usr/bin/env bun

/**
 * setup-fullstack — scaffold a Python (FastAPI + uv) backend + React (Vite)
 * frontend project. The first positional argument selects a runtime variation
 * (database backend + storage backend + backup overlay) — its env-var bundle
 * is written to `.env` in the scaffolded project so `make docker-up` /
 * `make ci` pick that combo by default.
 *
 * Variations are CONFIG PRESETS. Testing them against the scaffolded project
 * is the harness's job (tmp/test-matrix.sh + tmp/test-variation.sh) — NOT the
 * skill's. Do not re-introduce variation-testing logic here.
 *
 * The CLI is self-contained: nothing in this tree assumes it lives under
 * .claude/skills/. Drop the `scripts/` + `resources/` pair anywhere on disk
 * and the orchestrator works (path resolution is anchored to the script's
 * own location, not the project's git root).
 */

import { elog } from "./lib/logger.ts";
import { scaffoldMain, SCAFFOLD_HELP } from "./commands/scaffold.ts";
import {
  listVariationsMain,
  LIST_VARIATIONS_HELP,
} from "./commands/list-variations.ts";
import { variationByName } from "./lib/variations.ts";

const HELP_BY_COMMAND: Record<string, string> = {
  "list-variations": LIST_VARIATIONS_HELP,
};

const main = async (): Promise<number> => {
  const argv = Bun.argv.slice(2);
  const first = argv[0];

  // Explicit help — print and exit.
  if (first === "-h" || first === "--help") {
    process.stdout.write(SCAFFOLD_HELP);
    return 0;
  }

  // No args — scaffold with the default variation.
  if (!first) {
    await scaffoldMain([]);
    return 0;
  }

  // Sub-help: `setup-fullstack help <topic>`.
  if (first === "help") {
    const sub = argv[1];
    if (!sub) {
      process.stdout.write(SCAFFOLD_HELP);
      return 0;
    }
    const help = HELP_BY_COMMAND[sub];
    if (!help) {
      elog(`error: unknown help topic '${sub}'`);
      return 2;
    }
    process.stdout.write(help);
    return 0;
  }

  // Discoverability subcommand.
  if (first === "list-variations") {
    return listVariationsMain(argv.slice(1));
  }

  // Default flow: scaffold with the positional treated as a variation name.
  // Unknown variations are rejected by scaffoldMain itself, so the user gets
  // the full variation list in the error message.
  if (first.startsWith("-")) {
    // Flags-only invocation (e.g. `--no-fix`) — pass through as scaffold args.
    await scaffoldMain(argv);
    return 0;
  }

  // If the positional doesn't match a known variation, fail-fast with a clear
  // error rather than silently treating it as something else.
  if (!variationByName(first)) {
    elog(`error: unknown variation '${first}'`);
    elog(`Try: setup-fullstack list-variations`);
    return 2;
  }

  await scaffoldMain(argv);
  return 0;
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
