#!/usr/bin/env bun

/**
 * Automated setup script for Vite + React + TypeScript + Tailwind v4 + shadcn/ui
 * + Vitest + Biome + Playwright. Uses bun as the runtime and package manager.
 *
 * This script is a thin orchestrator: every config / Make recipe / e2e helper
 * lives as a real file under `resources/`. The script's job is to (1) scaffold
 * Vite + bun deps, (2) patch the few files the scaffold owns (tsconfigs,
 * biome.json, package.json), and (3) copy the resource tree on top.
 *
 * Usage:
 *   bun .claude/skills/vite-react-setup/setup-vite-react.ts              # current dir
 *   bun .claude/skills/vite-react-setup/setup-vite-react.ts frontend/    # subdirectory
 */

// @ts-ignore — `bun` is a runtime-provided module; types resolve at runtime
// even when bun-types isn't installed in the host project.
import { $ } from "bun";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmdirSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const RESOURCES = join(SCRIPT_DIR, "resources");

const targetDir = process.argv[2] ?? ".";
const isCurrentDir = targetDir === ".";
const displayName = isCurrentDir ? "current directory" : targetDir;

console.log(`Setting up Vite React app in ${displayName}...`);

// ============================================================================
// Helpers — all resource I/O routes through these.
// ============================================================================

/** Copy a single resource file from RESOURCES/<rel> to <cwd>/<dest>. */
const copyResource = (rel: string, dest: string = rel): void => {
  const source = join(RESOURCES, rel);
  mkdirSync(dirname(dest), { recursive: true });
  cpSync(source, dest);
  console.log(`  copied resources/${rel} -> ${dest}`);
};

/** Copy a directory tree recursively. */
const copyResourceTree = (relDir: string, destDir: string = relDir): void => {
  const source = join(RESOURCES, relDir);
  mkdirSync(dirname(destDir), { recursive: true });
  cpSync(source, destDir, { recursive: true });
  console.log(`  copied resources/${relDir}/ -> ${destDir}/`);
};

/** Read a template file, substitute {{var}} placeholders, write to dest. */
const writeTemplate = (
  rel: string,
  dest: string,
  vars: Record<string, string>,
): void => {
  let content = readFileSync(join(RESOURCES, rel), "utf8");
  for (const [k, v] of Object.entries(vars)) {
    content = content.replaceAll(`{{${k}}}`, v);
  }
  writeFileSync(dest, content);
  console.log(`  wrote ${dest} from template ${rel}`);
};

/** Snapshot a file's contents if it exists; null otherwise. */
const snapshotIfExists = (path: string): string | null =>
  existsSync(path) ? readFileSync(path, "utf8") : null;

// ============================================================================
// Step 0: Snapshot existing user-curated docs BEFORE scaffolding.
//
// `bun create vite` writes its own generic "React + TypeScript + Vite" README
// into tmp/vite-setup/, which the move loop in Step 1 would otherwise rename
// over the project's existing README — destroying the project's reason-to-exist
// description that nobody else can recover.
//
// Rule (per SKILL.md → "Documentation split"):
//   - README.md     = users (project overview, value prop, how-to-consume)
//   - CONTRIBUTING.md = developers (Make targets, dev/build/test workflow)
//
// Behaviour:
//   - README.md exists       -> preserve verbatim, discard scaffold version.
//   - README.md missing      -> Step 11 writes a minimal user-facing template.
//   - CONTRIBUTING.md exists -> preserve verbatim, user has likely curated it.
//   - CONTRIBUTING.md missing -> Step 11 generates a fresh developer doc.
//
// Snapshots are taken in the working directory the script was invoked from.
// For a `bun ... frontend/` invocation the snapshot intentionally targets `.`,
// because the new subdirectory cannot have pre-existing docs to preserve.
// ============================================================================

const preservedReadme = isCurrentDir ? snapshotIfExists("README.md") : null;
const preservedContributing = isCurrentDir
  ? snapshotIfExists("CONTRIBUTING.md")
  : null;
if (preservedReadme !== null) {
  console.log("Preserving existing README.md (project-overview content)");
}
if (preservedContributing !== null) {
  console.log("Preserving existing CONTRIBUTING.md");
}

// ============================================================================
// Step 1: Create Vite project.
// When the target is the current directory, the scaffold is created in
// `tmp/vite-setup/` first and then files are moved into the project root,
// because `bun create vite .` refuses to scaffold into a non-empty directory.
// `tmp/` is conventionally gitignored and wiped by `make clean`.
// ============================================================================

console.log("\nStep 1: Creating Vite project...");
if (isCurrentDir) {
  mkdirSync("tmp", { recursive: true });
  const tempDir = join("tmp", "vite-setup");
  await $`bun create vite@latest ${tempDir} --template react-ts`;

  for (const file of readdirSync(tempDir)) {
    renameSync(join(tempDir, file), file);
  }
  rmdirSync(tempDir);
  console.log("  moved files to current directory");

  // Restore preserved docs immediately, so any later step that reads them
  // sees the project's content rather than the Vite template's placeholder.
  // Templates for missing files are written in Step 11 once package.json
  // (project name) is finalised.
  if (preservedReadme !== null) {
    writeFileSync("README.md", preservedReadme);
    console.log("  restored preserved README.md");
  }
  if (preservedContributing !== null) {
    writeFileSync("CONTRIBUTING.md", preservedContributing);
    console.log("  restored preserved CONTRIBUTING.md");
  }
} else {
  await $`bun create vite@latest ${targetDir} --template react-ts`;
  process.chdir(targetDir);
}

// ============================================================================
// Step 2: Install all the deps the scaffold needs (base + Tailwind + shadcn
// + Vitest + Playwright + Biome). Batched so each `bun add` pays the network
// cost once, not per-package.
// ============================================================================

console.log("\nStep 2: Installing all dependencies...");
await $`bun install`;
await $`bun add tailwindcss @tailwindcss/vite class-variance-authority clsx tailwind-merge`;
await $`bun add -d @types/node @biomejs/biome @playwright/test \
        vitest @vitest/ui jsdom \
        @testing-library/react @testing-library/jest-dom`;

// ============================================================================
// Step 3: Replace ESLint with Biome.
//
// The Vite react-ts template scaffolds with ESLint by convention, but the
// project rules pick exactly one tool — Biome — so we strip ESLint deps and
// install Biome in its place. Combining Biome with ESLint+Prettier is
// explicitly disallowed: their rule sets fight on the same files.
// ============================================================================

console.log("\nStep 3: Switching from ESLint to Biome...");
await $`bun remove @eslint/js eslint eslint-plugin-react-hooks eslint-plugin-react-refresh globals typescript-eslint`;
if (existsSync("eslint.config.js")) {
  unlinkSync("eslint.config.js");
  console.log("  removed eslint.config.js");
}
await $`bunx --bun biome init`;

// ============================================================================
// Step 4: Install Playwright browsers (Chromium only — the Make/CI flow uses
// chromium for the e2e webServer config).
// ============================================================================

console.log("\nStep 4: Installing Playwright Chromium...");
await $`bunx --bun playwright install --with-deps chromium`;

// ============================================================================
// Step 5: Patch tsconfig.json AND tsconfig.app.json with path aliases.
//
// We patch via string replacement rather than JSON.parse because the Vite
// react-ts template ships tsconfig.app.json with `/* … */` comments (JSONC),
// which JSON.parse rejects. String replacement also preserves the template's
// original formatting and inline comments — useful when humans diff the file.
//
// `baseUrl` is deliberately omitted — it is deprecated in TypeScript 6+ and
// `paths` resolves relative to each tsconfig file's location.
// ============================================================================

console.log("\nStep 5: Configuring TypeScript paths...");

const patchTsconfig = (filePath: string): void => {
  if (!existsSync(filePath)) return;
  let content = readFileSync(filePath, "utf8");

  // Drop any existing baseUrl line (deprecated in TS 6+).
  content = content.replace(/^\s*"baseUrl"\s*:\s*"[^"]*"\s*,?\s*\n/m, "");

  // Replace any existing paths block, or insert one after `"compilerOptions": {`.
  const pathsLine = '    "paths": { "@/*": ["./src/*"] }';
  if (/"paths"\s*:\s*\{[^}]*\}/.test(content)) {
    content = content.replace(/"paths"\s*:\s*\{[^}]*\}/, pathsLine.trim());
  } else {
    content = content.replace(
      /("compilerOptions"\s*:\s*\{)/,
      `$1\n${pathsLine},`,
    );
  }

  writeFileSync(filePath, content);
  console.log(`  patched ${filePath}`);
};

patchTsconfig("tsconfig.json");
patchTsconfig("tsconfig.app.json");

// ============================================================================
// Step 6: Patch biome.json — exclude common build/test/scratch dirs and
// enable Tailwind directive parsing so `@apply`, `@theme`, etc. don't trip
// the CSS parser. Biome's init writes a JSONC-style file with tabs.
// ============================================================================

console.log("\nStep 6: Configuring Biome...");
if (existsSync("biome.json")) {
  let bio = readFileSync("biome.json", "utf8");
  bio = bio.replace(
    /"includes":\s*\[[^\]]*\]/,
    `"includes": [
		"**",
		"!!**/.claude",
		"!!**/dist",
		"!!**/coverage",
		"!!**/e2e-screenshots",
		"!!**/playwright-report",
		"!!**/test-results",
		"!!**/tmp"
	]`,
  );
  if (!/"css"\s*:/.test(bio)) {
    bio = bio.replace(
      /("javascript"\s*:\s*\{[^}]*\}\s*,?)/,
      `$1
	"css": {
		"parser": {
			"cssModules": true,
			"tailwindDirectives": true
		}
	},`,
    );
  }
  writeFileSync("biome.json", bio);
  console.log("  patched biome.json");
}

// ============================================================================
// Step 7: Merge our package.json scripts into the scaffold's.
//
// Quality scripts:
//   - `lint`         strict read-only check. Uses `biome ci` (not `biome lint`)
//                    so warnings AND info-level findings fail — same behavior
//                    as the generated GitHub Actions workflow. Enforces the
//                    strict no-warnings policy.
//   - `lint-fix`     apply lint auto-fixes only, leave formatting alone.
//                    Includes --unsafe so `useNodejsImportProtocol` etc. get
//                    rewritten.
//   - `format`       autofix formatting only (whitespace, indentation).
//   - `format-check` read-only format check; fails if any file would be
//                    reformatted.
//
// Note: there's no `fix` script here. The Makefile's `fix` target is a meta-
// target that depends on `format` + `lint-fix`, composing the autofix chain
// at the Make level rather than via a redundant package.json wrapper.
// ============================================================================

console.log("\nStep 7: Merging package.json scripts...");
type PackageJson = { scripts?: Record<string, string>; [k: string]: unknown };
const packageJson: PackageJson = JSON.parse(readFileSync("package.json", "utf8"));
packageJson.scripts = {
  ...packageJson.scripts,
  lint: "biome ci .",
  "lint-fix": "biome lint --write --unsafe .",
  format: "biome format --write .",
  "format-check": "biome format .",
  test: "vitest",
  "test:ui": "vitest --ui",
  "test:e2e": "playwright test",
};
writeFileSync("package.json", `${JSON.stringify(packageJson, null, 2)}\n`);
console.log("  merged scripts into package.json");

// ============================================================================
// Step 8: Initialize shadcn/ui (with defaults). Adds src/lib/utils.ts (cn()).
// Must run AFTER package.json is patched because shadcn reads it.
// ============================================================================

console.log("\nStep 8: Initializing shadcn/ui...");
await $`bunx --bun shadcn@latest init -d`;

// ============================================================================
// Step 9: Copy frontend resources on top of the scaffold. These OVERWRITE the
// Vite-generated equivalents (vite.config.ts, src/index.css, src/vite-env.d.ts)
// and add the e2e suite + Playwright config + Makefile + GitHub Actions.
// ============================================================================

console.log("\nStep 9: Copying frontend resources...");
copyResource("vite.config.ts");
copyResource("playwright.config.ts");
copyResource("Makefile");
copyResource("src/index.css");
copyResource("src/vite-env.d.ts");
copyResourceTree("e2e");
copyResource(".github/workflows/build.yml");

// ============================================================================
// Step 10: Format generated files with Biome (shadcn writes its own style).
// Best-effort: don't abort the script if some auto-fix can't be applied.
// ============================================================================

console.log("\nStep 10: Running Biome check on generated files...");
await $`bunx --bun biome check --write --unsafe . || true`;

// ============================================================================
// Step 11: README.md / CONTRIBUTING.md.
// Preserved docs always win. Otherwise substitute {{projectName}} into the
// templates under resources/templates/.
// See SKILL.md → "Documentation split" for the rule.
// ============================================================================

console.log("\nStep 11: Writing README.md / CONTRIBUTING.md...");
const projectName = (() => {
  try {
    const pkg = JSON.parse(readFileSync("package.json", "utf8"));
    return typeof pkg.name === "string" && pkg.name.length > 0
      ? pkg.name
      : "project";
  } catch {
    return "project";
  }
})();

if (preservedReadme !== null) {
  console.log("  README.md preserved verbatim");
} else {
  writeTemplate("templates/README.md.template", "README.md", { projectName });
}

if (preservedContributing !== null) {
  console.log("  CONTRIBUTING.md preserved verbatim");
} else {
  writeTemplate("templates/CONTRIBUTING.md.template", "CONTRIBUTING.md", {
    projectName,
  });
}

// ============================================================================
// Step 12: Verify build.
// ============================================================================

console.log("\nStep 12: Testing build...");
await $`bun run build`;

// ============================================================================
// Step 13: Verify e2e (smoke test the home route).
// ============================================================================

console.log("\nStep 13: Running e2e smoke test...");
await $`bun run test:e2e`;

// ============================================================================
// Done.
// ============================================================================

console.log("\nSetup complete.");
console.log("\nCanonical inner-loop:");
if (!isCurrentDir) {
  console.log(`  cd ${targetDir}`);
}
console.log("  make fix ci          # Autofix everything, then run the strict gate");
console.log("\nOther make targets:");
console.log("  make dev             # Vite dev server, port 5173 (human profile)");
console.log("  make agentic-dev     # Vite dev server, port 5174 (AI agent profile)");
console.log("  make build           # Production build → dist/");
console.log("  make test            # Vitest unit tests");
console.log("  make test-e2e        # Playwright e2e tests");
console.log("  make help            # Auto-discovered list of every target");
console.log("\nNote: use `bun run test`, NOT `bun test` — the latter invokes");
console.log("bun's built-in test runner instead of Vitest.");
console.log("\nAdd shadcn components:");
console.log("  bunx --bun shadcn@latest add button card");
console.log("\nGitHub Pages: in repo Settings → Pages, set Source: GitHub Actions.");
console.log("Pushes to main will deploy automatically via .github/workflows/build.yml.");
