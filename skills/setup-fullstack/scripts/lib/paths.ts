// Path resolution for the setup-fullstack script.
//
// Two layers of paths:
//   - SCRIPT-LOCAL: where the orchestrator lives. Static, computed once.
//     RESOURCES is one directory up from `scripts/` (we're in scripts/lib/, so
//     two parents up).
//   - PROJECT-LOCAL: where the scaffold is being applied. Depends on argv —
//     resolved via `resolveProjectPaths(target)` and passed around as a Ctx.

import { dirname, isAbsolute, relative, sep, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// scripts/lib/paths.ts → scripts/lib → scripts → setup-fullstack (skill root).
const LIB_DIR = dirname(fileURLToPath(import.meta.url));
export const SCRIPTS_DIR = dirname(LIB_DIR);
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

// True when `candidate` is `parent` itself or a descendant of it.
const isInsideOrEqual = (parent: string, candidate: string): boolean => {
  const rel = relative(parent, candidate);
  if (rel === "") return true;
  if (isAbsolute(rel)) return false;
  return rel !== ".." && !rel.startsWith(`..${sep}`);
};

/** Resolve the user-supplied target into a stable set of project paths. */
export const resolveProjectPaths = (target: string): ProjectPaths => {
  const isCurrentDir = target === ".";
  const projectRoot = resolve(target);

  // Refuse to scaffold into the skill's own source tree. Running the script
  // with CWD inside scripts/ would otherwise drop a fullstack project as
  // siblings to setup-fullstack.ts and (if `git add` is run blindly) end up
  // committed alongside the orchestrator. The skill is the template, not the
  // scaffold target.
  if (isInsideOrEqual(SKILL_ROOT, projectRoot)) {
    throw new Error(
      [
        `refusing to scaffold into the skill's own source tree: ${projectRoot}`,
        `  skill root:  ${SKILL_ROOT}`,
        `  scripts dir: ${SCRIPTS_DIR}`,
        `Pass an explicit target outside this tree, e.g.`,
        `  bun ${SCRIPTS_DIR}/setup-fullstack.ts ~/path/to/new-app`,
      ].join("\n"),
    );
  }

  return {
    projectRoot,
    isCurrentDir,
    displayName: isCurrentDir ? "current directory" : target,
    targetArg: target,
  };
};
