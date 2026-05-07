// Steps 14 + 15 + 16: install backend deps, run autofix, verify.
//
// Step 14: `uv sync` materialises the backend venv. The --directory flag is
// a uv top-level option (must come BEFORE the subcommand); this is the only
// safe way to invoke uv against backend/ without violating the project rule
// against `cd`-ing in shell commands.
//
// Step 15: `make fix` is best-effort autofix. It MUST surface failures
// loudly (older versions had a blanket catch that swallowed real lint
// failures, then printed "Setup complete" on a scaffold that would fail
// `make ci`). Loud-but-recoverable beats silent-but-broken: print last 25
// lines of output and exit 1.
//
// Step 16: typecheck + tests. e2e is intentionally skipped here (slow on
// first run, dependency-heavy); the user runs `make ci` themselves to
// verify the full strict gate.

// @ts-ignore — `bun` is a runtime-provided module
import { $ } from "bun";

import { elog, log } from "../lib/logger.ts";
import { runQuiet } from "../lib/shell.ts";

const ABORT_HINT =
  "\n  Setup aborted. Resolve the issue above (typically a ruff/biome rule\n" +
  "  with no auto-fix) and re-run the setup script.";

const installBackendDeps = async (): Promise<void> => {
  log("\nStep 14: Running uv sync in backend/...");
  await runQuiet("backend deps installed", $`uv --directory backend sync`);
};

const runMakeFix = async (): Promise<void> => {
  log("\nStep 15: Running `make fix`...");
  const result = await $`make fix`.nothrow().quiet();
  if (result.exitCode === 0) {
    log("  autofix complete");
    return;
  }
  const combined = (
    result.stdout.toString() + result.stderr.toString()
  ).trim();
  const tail = combined.split("\n").slice(-25).join("\n");
  elog(`\n  ✗ make fix FAILED (exit ${result.exitCode})`);
  elog("  ─── last 25 lines ───");
  elog(tail.split("\n").map((l: string) => `    ${l}`).join("\n"));
  elog("  ─────────────────────");
  elog(ABORT_HINT);
  process.exit(1);
};

const runVerification = async (): Promise<void> => {
  log("\nStep 16: Verifying typecheck + tests on both halves...");
  await runQuiet("typecheck green (mypy + tsc)", $`make typecheck`);
  await runQuiet("tests green (pytest + vitest)", $`make test`);
};

/** Run Steps 14 + 15 + 16 in order. The verify subset can be skipped via the
 *  CLI's --no-verify flag; the caller controls that by simply not invoking
 *  this function. */
export const finalize = async (
  options: { skipFix?: boolean; skipVerify?: boolean } = {},
): Promise<void> => {
  await installBackendDeps();
  if (!options.skipFix) {
    await runMakeFix();
  }
  if (!options.skipVerify) {
    await runVerification();
  }
};
