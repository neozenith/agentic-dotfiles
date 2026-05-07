// Steps 0 + 1: snapshot existing user-curated docs, create project root,
// create backend/, abort if frontend/ already exists.
//
// "Preserved docs" only matter for the in-place / current-dir flow — a fresh
// subdirectory target has no prior README/CONTRIBUTING to preserve.

import { existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

import { elog, log } from "../lib/logger.ts";
import { snapshotIfExists } from "../lib/resources.ts";
import type { Ctx } from "../lib/types.ts";
import type { ProjectPaths } from "../lib/paths.ts";

/** Snapshot existing docs (Step 0) and bootstrap project structure (Step 1). */
export const prepare = (paths: ProjectPaths): Ctx => {
  const { projectRoot, isCurrentDir } = paths;

  // Step 0: Snapshot user-curated docs BEFORE scaffolding overwrites them.
  const preservedReadme = isCurrentDir
    ? snapshotIfExists(join(projectRoot, "README.md"))
    : null;
  const preservedContributing = isCurrentDir
    ? snapshotIfExists(join(projectRoot, "CONTRIBUTING.md"))
    : null;
  if (preservedReadme !== null) {
    log("Preserving existing README.md (project-overview content)");
  }
  if (preservedContributing !== null) {
    log("Preserving existing CONTRIBUTING.md");
  }

  // Step 1: Create project root + backend/ dir; abort if frontend/ exists.
  log("\nStep 1: Creating project structure...");
  mkdirSync(projectRoot, { recursive: true });
  process.chdir(projectRoot);
  mkdirSync("backend", { recursive: true });

  if (existsSync("frontend")) {
    elog(
      "Error: frontend/ already exists. Aborting to avoid clobbering an existing scaffold.",
    );
    process.exit(1);
  }

  return { ...paths, preservedReadme, preservedContributing };
};
