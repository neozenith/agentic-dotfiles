// Preflight checks — verify required tools are on PATH before the scaffold
// pipeline starts. Failing fast here (with a clear actionable message) is
// better than discovering a missing tool halfway through a multi-minute run.

import { spawnSync } from "node:child_process";
import { elog } from "./logger.ts";

interface ToolCheck {
  cmd: string;
  installHint: string;
}

const REQUIRED_TOOLS: ToolCheck[] = [
  {
    cmd: "uv",
    installHint: "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
  },
  {
    cmd: "make",
    installHint:
      "Install make via your system package manager (e.g. apt install make / xcode-select --install)",
  },
  {
    cmd: "bunx",
    installHint: "bunx ships with bun — ensure bun is up to date: bun upgrade",
  },
];

/** Sentinel error thrown by runPreflight; message already printed to stderr. */
export class PreflightError extends Error {
  constructor(missing: string[]) {
    super(`missing required tools: ${missing.join(", ")}`);
    this.name = "PreflightError";
  }
}

/** Returns true if `cmd` is resolvable on PATH, false otherwise.
 *  Uses Node's spawnSync with a fixed argument vector — no shell interpolation. */
const isAvailable = (cmd: string): boolean => {
  const result = spawnSync("which", [cmd], { stdio: "ignore" });
  return result.status === 0;
};

/**
 * Check that every required external tool is on PATH.
 * Prints actionable install hints and throws PreflightError if any are missing.
 * The caller is responsible for terminating the process.
 */
export const runPreflight = (): void => {
  const missing: ToolCheck[] = REQUIRED_TOOLS.filter(
    (tool) => !isAvailable(tool.cmd),
  );
  if (missing.length === 0) return;

  elog("setup-fullstack: preflight check failed — missing required tools:\n");
  for (const tool of missing) {
    elog(`  ✗ ${tool.cmd}`);
    elog(`    → ${tool.installHint}`);
  }
  elog("\nInstall the tools above and re-run.");
  throw new PreflightError(missing.map((t) => t.cmd));
};
