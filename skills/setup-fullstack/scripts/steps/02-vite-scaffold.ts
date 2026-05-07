// Step 2: Scaffold Vite + React + TypeScript into frontend/.
//
// Three invariants make this non-hanging in interactive TTY (zsh) sessions:
//
//   1. `bunx --bun create-vite@latest` (not `bun create vite@latest`) — bunx
//      forwards args directly to create-vite without bun-create's wrapping
//      that occasionally drops `--template` and forces a framework prompt.
//   2. `< /dev/null` redirects stdin so create-vite's prompt library reads
//      EOF and falls back to defaults instead of blocking forever waiting
//      on a TTY the user can't see.
//   3. NO `.quiet()` — create-vite's progress + any error/prompt is allowed
//      to flow through so you can SEE what it's doing. The trade-off is
//      ~30 lines of npm-install noise on success; worth it to never have
//      a 93-minute silent deadlock again.
//
// Post-validation: assert frontend/ exists. Older bug: create-vite exited 0
// after a TTY interrupt without creating the directory; the next chdir then
// ENOENT'd. Fail loudly here instead.

// @ts-ignore — `bun` is a runtime-provided module
import { $ } from "bun";
import { existsSync } from "node:fs";
import { join } from "node:path";

import { elog, log } from "../lib/logger.ts";
import type { Ctx } from "../lib/types.ts";

export const scaffoldVite = async (ctx: Ctx): Promise<void> => {
  log("\nStep 2: Scaffolding Vite + React + TypeScript into frontend/...");
  const result = await $`bunx --bun create-vite@latest frontend --template react-ts < /dev/null`.nothrow();
  if (result.exitCode !== 0) {
    elog(`  Vite scaffold FAILED (exit ${result.exitCode})`);
    process.exit(1);
  }
  const viteScaffoldDir = join(ctx.projectRoot, "frontend");
  if (!existsSync(viteScaffoldDir)) {
    elog(`  Vite scaffold reported success but ${viteScaffoldDir} does not exist.`);
    elog("  create-vite may have been TTY-interrupted; check above output.");
    process.exit(1);
  }
  log("  Vite scaffold complete");

  // All subsequent frontend steps run with cwd = frontend/.
  process.chdir(viteScaffoldDir);
};
