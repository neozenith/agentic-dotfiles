// Step 13: write README.md + CONTRIBUTING.md.
//
// Preserved docs (snapshotted in Step 0) always win — for the in-place flow
// where the user has already curated their own README. Otherwise substitute
// {{projectName}} into the templates under resources/templates/.
//
// projectName is read from frontend/package.json's `name` field; falls back
// to "fullstack-app" if anything goes wrong (the value is purely cosmetic
// in the generated docs).

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { log } from "../lib/logger.ts";
import { makeResourceCopiers } from "../lib/resources.ts";
import type { Ctx } from "../lib/types.ts";

const resolveProjectName = (projectRoot: string): string => {
  try {
    const fePkg = JSON.parse(
      readFileSync(join(projectRoot, "frontend", "package.json"), "utf8"),
    );
    return typeof fePkg.name === "string" && fePkg.name.length > 0
      ? fePkg.name
      : "fullstack-app";
  } catch {
    return "fullstack-app";
  }
};

export const writeDocs = (ctx: Ctx): void => {
  const { projectRoot, preservedReadme, preservedContributing } = ctx;
  const { writeTemplate } = makeResourceCopiers(projectRoot);

  log("\nStep 13: Writing README.md / CONTRIBUTING.md...");

  const projectName = resolveProjectName(projectRoot);

  if (preservedReadme !== null) {
    writeFileSync(join(projectRoot, "README.md"), preservedReadme);
    log("  README.md preserved verbatim");
  } else {
    writeTemplate("templates/README.md.template", "README.md", { projectName });
  }

  if (preservedContributing !== null) {
    writeFileSync(
      join(projectRoot, "CONTRIBUTING.md"),
      preservedContributing,
    );
    log("  CONTRIBUTING.md preserved verbatim");
  } else {
    writeTemplate("templates/CONTRIBUTING.md.template", "CONTRIBUTING.md", {
      projectName,
    });
  }
};
