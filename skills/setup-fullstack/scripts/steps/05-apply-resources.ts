// Steps 10 + 10.5 + 11 + 12: copy frontend, backend, and top-level
// orchestration resources on top of the scaffold; patch Vite-generated files
// that would otherwise fail the strict gate.

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { log } from "../lib/logger.ts";
import { makeResourceCopiers } from "../lib/resources.ts";
import type { Ctx } from "../lib/types.ts";

/** Step 10: copy frontend resources on top of the Vite scaffold. */
const copyFrontendResources = (projectRoot: string): void => {
  const { copyResource, copyResourceTree } = makeResourceCopiers(projectRoot);
  log("\nStep 10: Copying frontend resources...");
  process.chdir(projectRoot); // copy helpers expect project-root-relative paths

  copyResource("frontend/vite.config.ts");
  copyResource("frontend/playwright.config.ts");
  copyResource("frontend/Makefile");
  copyResource("frontend/CLAUDE.md");
  copyResource("frontend/src/index.css");
  copyResource("frontend/src/vite-env.d.ts");
  copyResource("frontend/src/setupTests.ts");
  copyResource("frontend/src/App.tsx");
  // Tree copies merge into existing dirs — shadcn-init's lib/utils.ts and
  // any components/ui/* it added survive; our lib/api.ts, the Layout
  // component, and the page modules slot in alongside.
  copyResourceTree("frontend/src/lib");
  copyResourceTree("frontend/src/components");
  copyResourceTree("frontend/src/pages");
  copyResourceTree("frontend/e2e");
};

/** Step 10.5: patch Vite-generated frontend files that would fail the
 *  strict gate as-is.
 *
 *    (a) frontend/.gitignore — Vite's default omits coverage/, test-results/,
 *        playwright-report/. Biome's `vcs.useIgnoreFile: true` reads the
 *        .gitignore relative to its CWD; since `make -C frontend ...`
 *        invokes biome from frontend/, the repo-root .gitignore is invisible
 *        to it and biome ends up scanning the istanbul HTML coverage report.
 *
 *    (b) frontend/src/main.tsx — Vite's default uses
 *        `document.getElementById("root")!` (non-null assertion), which
 *        biome's `noNonNullAssertion` flags as a warning. Because the project
 *        runs `biome ci` (warnings-are-errors), the warning fails the gate.
 *        Replace with an explicit null-check that throws — matches the
 *        project's "no graceful degradation" rule.
 */
const patchViteGeneratedFiles = (projectRoot: string): void => {
  log("\nStep 10.5: Patching Vite-generated frontend files...");

  const frontendGitignore = join(projectRoot, "frontend", ".gitignore");
  if (existsSync(frontendGitignore)) {
    const existing = readFileSync(frontendGitignore, "utf8");
    const additions = [
      "coverage/",
      "test-results/",
      "playwright-report/",
      "e2e-screenshots/",
      ".vite/",
    ];
    const missing = additions.filter((line) => !existing.includes(line));
    if (missing.length > 0) {
      const block = [
        "",
        "# Test + coverage artifacts (also in repo-root .gitignore;",
        "# duplicated here so biome's useIgnoreFile sees them under frontend/)",
        ...missing,
        "",
      ].join("\n");
      writeFileSync(frontendGitignore, `${existing.trimEnd()}\n${block}`);
      log(`  patched frontend/.gitignore (added ${missing.length} entries)`);
    }
  }

  const mainTsx = join(projectRoot, "frontend", "src", "main.tsx");
  if (existsSync(mainTsx)) {
    const original = readFileSync(mainTsx, "utf8");
    const safeMainTsx = `import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";

const rootElement = document.getElementById("root");
if (!rootElement) {
\tthrow new Error("Root element #root not found in document");
}

createRoot(rootElement).render(
\t<StrictMode>
\t\t<App />
\t</StrictMode>,
);
`;
    if (original !== safeMainTsx) {
      writeFileSync(mainTsx, safeMainTsx);
      log("  patched frontend/src/main.tsx (removed non-null assertion)");
    }
  }
};

/** Step 11: copy backend resources file-by-file.
 *
 *  We deliberately do NOT use copyResourceTree("backend") even though it
 *  would work — that would also copy stale backend/Dockerfile + .dockerignore
 *  from earlier iterations. The bundled Docker image now builds from a
 *  project-root Dockerfile (Step 12), so the per-backend ones must not land
 *  in the user's tree. */
const copyBackendResources = (projectRoot: string): void => {
  const { copyResource, copyResourceTree } = makeResourceCopiers(projectRoot);
  log("\nStep 11: Copying backend resources...");
  copyResource("backend/pyproject.toml");
  copyResource("backend/Makefile");
  copyResource("backend/README.md");
  copyResource("backend/CLAUDE.md");
  copyResourceTree("backend/server");
  copyResourceTree("backend/tests");
};

/** Step 12: top-level orchestration files (Makefile, .gitignore, .github,
 *  CLAUDE.md, all docker-compose.*.yml overlays, Dockerfile, .dockerignore).
 *
 *  The .gitignore resource is named `gitignore` (no leading dot) so it
 *  doesn't accidentally gitignore the resource tree itself in the skill repo.
 */
const copyOrchestrationFiles = (projectRoot: string): void => {
  const { copyResource } = makeResourceCopiers(projectRoot);
  log("\nStep 12: Copying top-level orchestration files...");
  copyResource("Makefile");
  copyResource("gitignore", ".gitignore");
  copyResource(".github/workflows/build.yml");
  copyResource("CLAUDE.md");
  // Layered docker-compose: base + one overlay per DB backend, plus optional
  // storage overlays. The Makefile picks which to layer via DATABASE_BACKEND
  // and BACKUP_BACKEND.
  copyResource("docker-compose.yml");
  copyResource("docker-compose.sqlite.yml");
  copyResource("docker-compose.postgres.yml");
  copyResource("docker-compose.minio.yml");
  copyResource("docker-compose.local-storage.yml");
  // Multi-stage Dockerfile bundles SPA + FastAPI; build context is project
  // root, so it must live alongside docker-compose.yml.
  copyResource("Dockerfile");
  copyResource(".dockerignore");
};

/** Run Steps 10, 10.5, 11, 12 in order. */
export const applyResources = (ctx: Ctx): void => {
  copyFrontendResources(ctx.projectRoot);
  patchViteGeneratedFiles(ctx.projectRoot);
  copyBackendResources(ctx.projectRoot);
  copyOrchestrationFiles(ctx.projectRoot);
};
