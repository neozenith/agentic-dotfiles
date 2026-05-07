// Resource I/O helpers — every read/write of a `resources/<rel>` path goes
// through these so the resource layer is auditable in one place. Each helper
// emits a stamped log line on success.
//
// `copyResource` and `copyResourceTree` create destination parent directories
// as needed (recursive mkdir is idempotent). `writeTemplate` substitutes
// `{{var}}` placeholders before writing. `snapshotIfExists` is the building
// block for "preserve existing user-curated docs" behavior.

import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { log } from "./logger.ts";
import { RESOURCES } from "./paths.ts";

/** Build a closure over a project's destination root. */
export const makeResourceCopiers = (projectRoot: string) => {
  const copyResource = (rel: string, dest: string = rel): void => {
    const source = join(RESOURCES, rel);
    const target = join(projectRoot, dest);
    mkdirSync(dirname(target), { recursive: true });
    cpSync(source, target);
    log(`  copied resources/${rel} -> ${dest}`);
  };

  const copyResourceTree = (relDir: string, destDir: string = relDir): void => {
    const source = join(RESOURCES, relDir);
    const target = join(projectRoot, destDir);
    mkdirSync(dirname(target), { recursive: true });
    cpSync(source, target, { recursive: true });
    log(`  copied resources/${relDir}/ -> ${destDir}/`);
  };

  const writeTemplate = (
    rel: string,
    dest: string,
    vars: Record<string, string>,
  ): void => {
    let content = readFileSync(join(RESOURCES, rel), "utf8");
    for (const [k, v] of Object.entries(vars)) {
      content = content.replaceAll(`{{${k}}}`, v);
    }
    writeFileSync(join(projectRoot, dest), content);
    log(`  wrote ${dest} from template ${rel}`);
  };

  return { copyResource, copyResourceTree, writeTemplate };
};

/** Read a file's contents if it exists, else null. Used to snapshot
 *  user-curated docs before scaffolding overwrites them. */
export const snapshotIfExists = (path: string): string | null =>
  existsSync(path) ? readFileSync(path, "utf8") : null;
