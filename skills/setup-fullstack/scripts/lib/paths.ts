// Path resolution for the setup-fullstack script.
//
// Two layers of paths:
//   - SCRIPT-LOCAL: where the orchestrator lives. Static, computed once.
//     RESOURCES is one directory up from `scripts/` (we're in scripts/lib/, so
//     two parents up).
//   - PROJECT-LOCAL: where the scaffold is being applied. Depends on argv —
//     resolved via `resolveProjectPaths(target)` and passed around as a Ctx.

import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// scripts/lib/paths.ts → scripts/lib → scripts → setup-fullstack (skill root).
const LIB_DIR = dirname(fileURLToPath(import.meta.url));
const SCRIPTS_DIR = dirname(LIB_DIR);
export const SKILL_ROOT = dirname(SCRIPTS_DIR);
export const RESOURCES = resolve(SKILL_ROOT, "resources");

export interface ProjectPaths {
  /** Absolute path of the project being scaffolded. */
  projectRoot: string;
  /** True when target is "." (in-place scaffold of the current directory). */
  isCurrentDir: boolean;
  /** Human-readable label used in log lines. */
  displayName: string;
  /** Original target argument (".", "./foo", "/abs/path", etc.). */
  targetArg: string;
}

/** Resolve the user-supplied target into a stable set of project paths. */
export const resolveProjectPaths = (target: string): ProjectPaths => {
  const isCurrentDir = target === ".";
  return {
    projectRoot: resolve(target),
    isCurrentDir,
    displayName: isCurrentDir ? "current directory" : target,
    targetArg: target,
  };
};
