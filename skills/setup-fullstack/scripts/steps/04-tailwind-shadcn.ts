// Steps 8.5 + 9 + 9.5: pre-stage Tailwind v4 wiring, then initialise shadcn/ui
// and add the components the layout depends on.
//
// Step 8.5 must run BEFORE shadcn init: shadcn-cli's preflight checks
// vite.config.ts for the @tailwindcss/vite plugin and src/index.css for the
// `@import "tailwindcss"` directive. Without those, "Validating Tailwind CSS"
// fails. The same resources get re-copied in Step 10; that pass becomes a
// no-op for these two files.
//
// Steps 9 and 9.5 use `< /dev/null` defensively even though shadcn-cli's
// `-d` (init) and `--yes` (add) flags should make it non-interactive — the
// redirect costs nothing and prevents future TTY-detection regressions.

// @ts-ignore — `bun` is a runtime-provided module
import { $ } from "bun";

import { log } from "../lib/logger.ts";
import { makeResourceCopiers } from "../lib/resources.ts";
import { runQuiet } from "../lib/shell.ts";
import type { Ctx } from "../lib/types.ts";

export const setupTailwindAndShadcn = async (ctx: Ctx): Promise<void> => {
  const { copyResource } = makeResourceCopiers(ctx.projectRoot);

  // Step 8.5: pre-stage Tailwind v4 wiring before shadcn init.
  log("\nStep 8.5: Pre-staging Tailwind v4 wiring...");
  copyResource("frontend/vite.config.ts");
  copyResource("frontend/src/index.css");

  // Step 9: shadcn init (with `-d` defaults, stdin from /dev/null).
  log("\nStep 9: Initializing shadcn/ui...");
  await runQuiet(
    "shadcn/ui initialized",
    $`bunx --bun shadcn@latest init -d < /dev/null`,
  );

  // Step 9.5: add the components the layout + pages depend on.
  log("\nStep 9.5: Adding shadcn components (button, card)...");
  await runQuiet(
    "shadcn components added (button, card)",
    $`bunx --bun shadcn@latest add button card --yes --overwrite < /dev/null`,
  );
};
