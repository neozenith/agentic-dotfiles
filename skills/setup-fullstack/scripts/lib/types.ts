// Shared types passed between scaffold steps.

import type { ProjectPaths } from "./paths.ts";

/** Per-run context plumbed through every step. */
export interface Ctx extends ProjectPaths {
  /** Snapshotted README.md content from before scaffolding (in-place flow);
   *  null when the target was a fresh subdirectory or no README existed. */
  preservedReadme: string | null;
  /** Same as preservedReadme but for CONTRIBUTING.md. */
  preservedContributing: string | null;
}
