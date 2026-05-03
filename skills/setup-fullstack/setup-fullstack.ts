#!/usr/bin/env bun

/**
 * Automated setup for a fullstack web app:
 *   - Frontend: Vite + React 19 + TypeScript (strict family) + Tailwind v4 +
 *     shadcn/ui + Biome + Vitest (>=90% coverage) + Playwright
 *   - Backend:  FastAPI + uvicorn + uv + ruff (warnings-are-errors) + mypy strict
 *               + pytest (>=90% coverage) with tests/unit <-> tests/api split
 *   - Top-level Makefile with per-language rollup targets and the canonical
 *     `make fix ci` inner-loop
 *   - `make dev`         -> backend 8200 + frontend 5173 (human profile)
 *   - `make agentic-dev` -> backend 8201 + frontend 5174 (AI agent profile)
 *
 * This script is a thin orchestrator: every config / Make recipe / Python
 * module / TypeScript helper lives as a real file under `resources/`. The
 * script's job is to (1) scaffold Vite + bun deps, (2) patch the few files
 * that the scaffold owns (tsconfigs, biome.json, package.json), and (3)
 * copy the resource tree on top.
 *
 * Usage:
 *   bun .claude/skills/setup-fullstack/setup-fullstack.ts                 # current dir
 *   bun .claude/skills/setup-fullstack/setup-fullstack.ts my-fullstack-app  # subdirectory
 */

// @ts-ignore — `bun` is a runtime-provided module
import { $ } from "bun";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const RESOURCES = join(SCRIPT_DIR, "resources");

const targetDir = process.argv[2] ?? ".";
const isCurrentDir = targetDir === ".";
const projectRoot = resolve(targetDir);
const displayName = isCurrentDir ? "current directory" : targetDir;

console.log(`Setting up fullstack app in ${displayName}...`);

// ============================================================================
// Helpers — all resource I/O routes through these.
// ============================================================================

/** Copy a single resource file from RESOURCES/<rel> to <projectRoot>/<dest>. */
const copyResource = (rel: string, dest: string = rel): void => {
  const source = join(RESOURCES, rel);
  const target = join(projectRoot, dest);
  mkdirSync(dirname(target), { recursive: true });
  cpSync(source, target);
  console.log(`  copied resources/${rel} -> ${dest}`);
};

/** Copy a directory tree recursively. */
const copyResourceTree = (relDir: string, destDir: string = relDir): void => {
  const source = join(RESOURCES, relDir);
  const target = join(projectRoot, destDir);
  mkdirSync(dirname(target), { recursive: true });
  cpSync(source, target, { recursive: true });
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
  writeFileSync(join(projectRoot, dest), content);
  console.log(`  wrote ${dest} from template ${rel}`);
};

/** Snapshot a file's contents if it exists; null otherwise. */
const snapshotIfExists = (path: string): string | null =>
  existsSync(path) ? readFileSync(path, "utf8") : null;

/**
 * Run a Bun.$ shell promise with stdout/stderr suppressed, printing one short
 * label on success and dumping the captured output on failure (then re-throwing
 * so the script exits non-zero).
 *
 * The reliability case for verbose output is failure — when everything works,
 * the per-package install lists / preflight banners / coverage tables are pure
 * noise that just inflates Claude's context budget on every invocation.
 */
// biome-ignore lint/suspicious/noExplicitAny: Bun's ShellPromise typing isn't loaded
const runQuiet = async (label: string, p: any): Promise<void> => {
  try {
    await p.quiet();
    console.log(`  ${label}`);
  } catch (err) {
    console.error(`  ${label}: FAILED`);
    // biome-ignore lint/suspicious/noExplicitAny: ShellError is loosely typed
    const e = err as any;
    if (e?.stdout) console.error(e.stdout.toString());
    if (e?.stderr) console.error(e.stderr.toString());
    throw err;
  }
};

// ============================================================================
// Step 0: Snapshot existing user-curated docs BEFORE scaffolding.
// Only meaningful for the in-place / current-dir flow — a fresh subdir
// target has no prior docs to preserve.
// ============================================================================

const preservedReadme = isCurrentDir
  ? snapshotIfExists(join(projectRoot, "README.md"))
  : null;
const preservedContributing = isCurrentDir
  ? snapshotIfExists(join(projectRoot, "CONTRIBUTING.md"))
  : null;
if (preservedReadme !== null) {
  console.log("Preserving existing README.md (project-overview content)");
}
if (preservedContributing !== null) {
  console.log("Preserving existing CONTRIBUTING.md");
}

// ============================================================================
// Step 1: Create project root + backend dir; abort if frontend already exists.
// ============================================================================

console.log("\nStep 1: Creating project structure...");
mkdirSync(projectRoot, { recursive: true });
process.chdir(projectRoot);
mkdirSync("backend", { recursive: true });

if (existsSync("frontend")) {
  console.error(
    "Error: frontend/ already exists. Aborting to avoid clobbering an existing scaffold.",
  );
  process.exit(1);
}

// ============================================================================
// Step 2: Scaffold Vite + React + TypeScript into frontend/.
// ============================================================================

console.log("\nStep 2: Scaffolding Vite + React + TypeScript into frontend/...");
await runQuiet(
  "Vite scaffold complete",
  $`bun create vite@latest frontend --template react-ts`,
);

// All subsequent frontend steps run with cwd = frontend/.
process.chdir(join(projectRoot, "frontend"));

// ============================================================================
// Step 3: Install all the deps the scaffold needs (base + Tailwind + shadcn
// + Vitest + Biome + Playwright + concurrently). Batched so each `bun add`
// pays the network cost once, not per-package.
// ============================================================================

console.log("\nStep 3: Installing all dependencies...");
await runQuiet("scaffold deps installed", $`bun install`);
await runQuiet(
  "Tailwind + shadcn + react-router + lucide deps installed",
  $`bun add tailwindcss @tailwindcss/vite class-variance-authority clsx tailwind-merge react-router-dom lucide-react`,
);
await runQuiet(
  "dev deps installed (biome, playwright, vitest, etc.)",
  $`bun add -d @types/node @biomejs/biome @playwright/test concurrently \
        vitest @vitest/ui @vitest/coverage-v8 jsdom \
        @testing-library/react @testing-library/jest-dom`,
);

// ============================================================================
// Step 4: Replace ESLint with Biome (project rule: pick ONE — never combine
// Biome with ESLint+Prettier; their rule sets fight on the same files).
// ============================================================================

console.log("\nStep 4: Switching from ESLint to Biome...");
await runQuiet(
  "removed eslint deps",
  $`bun remove @eslint/js eslint eslint-plugin-react-hooks eslint-plugin-react-refresh globals typescript-eslint`,
);
if (existsSync("eslint.config.js")) {
  unlinkSync("eslint.config.js");
  console.log("  removed eslint.config.js");
}
await runQuiet("biome initialized", $`bunx --bun biome init`);

// ============================================================================
// Step 5: Install Playwright browsers (Chromium only — the Make/CI flow
// uses chromium for the e2e webServer config).
// ============================================================================

console.log("\nStep 5: Installing Playwright Chromium...");
await runQuiet(
  "Chromium installed",
  $`bunx --bun playwright install --with-deps chromium`,
);

// ============================================================================
// Step 6: Patch tsconfig.json + tsconfig.app.json with the strict family +
// `@/*` path alias. Both files need the alias because Vite's react-ts template
// uses TypeScript project references and `tsconfig.app.json` is the leaf the
// build actually consults.
// ============================================================================

console.log("\nStep 6: Patching tsconfigs with the strict family...");

const STRICT_FAMILY = [
  '"strict": true',
  '"noUncheckedIndexedAccess": true',
  '"exactOptionalPropertyTypes": true',
  '"noImplicitOverride": true',
  '"noPropertyAccessFromIndexSignature": true',
  '"noFallthroughCasesInSwitch": true',
];

const patchTsconfig = (filePath: string): void => {
  if (!existsSync(filePath)) return;
  let content = readFileSync(filePath, "utf8");

  // Drop deprecated baseUrl line.
  content = content.replace(/^\s*"baseUrl"\s*:\s*"[^"]*"\s*,?\s*\n/m, "");

  // Vite's root tsconfig.json is `files` + `references` only — no
  // compilerOptions block to patch into. shadcn-cli reads the root file
  // for the `@/*` alias, so synthesise a fresh compilerOptions block at the
  // top of the object instead of falling through to the regex-driven
  // branches below (which silently no-op without a target).
  if (!/"compilerOptions"\s*:\s*\{/.test(content)) {
    const optsLines = [
      '"baseUrl": "."',
      '"paths": { "@/*": ["./src/*"] }',
      ...STRICT_FAMILY,
    ]
      .map(
        (line, i, arr) =>
          `    ${line}${i < arr.length - 1 ? "," : ""}`,
      )
      .join("\n");
    const block = `  "compilerOptions": {\n${optsLines}\n  },`;
    content = content.replace(/^\s*\{\s*\n/, (m: string) => `${m}${block}\n`);
    writeFileSync(filePath, content);
    console.log(`  patched ${filePath} (inserted compilerOptions block)`);
    return;
  }

  // Patch / insert paths.
  const pathsLine = '    "paths": { "@/*": ["./src/*"] }';
  if (/"paths"\s*:\s*\{[^}]*\}/.test(content)) {
    content = content.replace(/"paths"\s*:\s*\{[^}]*\}/, pathsLine.trim());
  } else {
    content = content.replace(
      /("compilerOptions"\s*:\s*\{)/,
      `$1\n${pathsLine},`,
    );
  }

  // Inject the strict family. Replace existing entries; insert any missing ones.
  for (const flag of STRICT_FAMILY) {
    const key = flag.split('":')[0]?.replace(/"/g, "") ?? "";
    if (!key) continue;
    const re = new RegExp(`"${key}"\\s*:\\s*[^,\\n}]+`);
    if (re.test(content)) {
      content = content.replace(re, flag);
    } else {
      content = content.replace(
        /("compilerOptions"\s*:\s*\{)/,
        `$1\n    ${flag},`,
      );
    }
  }

  writeFileSync(filePath, content);
  console.log(`  patched ${filePath}`);
};

patchTsconfig("tsconfig.json");
patchTsconfig("tsconfig.app.json");

// ============================================================================
// Step 7: Patch biome.json — exclude common build/test/scratch dirs and
// enable Tailwind directive parsing so @apply, @theme, etc. don't trip the
// CSS parser. Biome's init writes a JSONC file with tabs.
// ============================================================================

console.log("\nStep 7: Patching biome.json...");
if (existsSync("biome.json")) {
  // Parse-mutate-stringify avoids the nested-brace pitfall of regex patching.
  // (A previous regex-based approach captured only the inner `}` of the
  // `"javascript": { "formatter": {...} }` block, leaving the outer `}`
  // dangling after the appended `css` block.)
  type BiomeConfig = {
    files?: { includes?: string[] };
    css?: { parser?: { cssModules?: boolean } };
    [k: string]: unknown;
  };
  const bio: BiomeConfig = JSON.parse(readFileSync("biome.json", "utf8"));
  bio.files = {
    ...(bio.files ?? {}),
    includes: [
      "**",
      "!!**/.claude",
      "!!**/dist",
      "!!**/coverage",
      "!!**/e2e-screenshots",
      "!!**/playwright-report",
      "!!**/test-results",
      "!!**/tmp",
      // Tailwind v4 + shadcn use `@custom-variant`, `@theme inline`, etc.
      // which Biome's CSS parser doesn't yet understand. Excluding the
      // theme-token entry point sidesteps the parsing errors without
      // disabling Biome on actual app code.
      "!!**/src/index.css",
    ],
  };
  // Biome 2.x does not have a `tailwindDirectives` key — Tailwind v4 uses
  // `@import "tailwindcss"` rather than `@tailwind` directives, so the parser
  // option is unnecessary. `cssModules: true` is the only knob we need.
  if (bio.css === undefined) {
    bio.css = { parser: { cssModules: true } };
  }
  writeFileSync("biome.json", `${JSON.stringify(bio, null, 2)}\n`);
  console.log("  patched biome.json");
}

// ============================================================================
// Step 8: Merge our package.json scripts into the scaffold's. Single-quoted
// strings in TS source mean ${API_PORT:-8200} embeds as a literal shell
// expansion in the JSON output. Don't switch these to backticks without
// re-escaping the dollar signs.
// ============================================================================

console.log("\nStep 8: Merging package.json scripts...");
type PackageJson = { scripts?: Record<string, string>; [k: string]: unknown };
const pkg: PackageJson = JSON.parse(readFileSync("package.json", "utf8"));

pkg.scripts = {
  ...pkg.scripts,
  dev: 'concurrently -k -n api,web -c blue,green "uv run --directory ../backend python -m server --port ${API_PORT:-8200} --reload" "vite --port ${DEV_PORT:-5173} --strictPort"',
  "agentic-dev":
    'concurrently -k -n api,web -c blue,green "uv run --directory ../backend python -m server --port ${API_PORT:-8201} --reload" "vite --port ${DEV_PORT:-5174} --strictPort"',
  "dev:frontend-only": "vite",
  build: "tsc -b && vite build",
  preview: "vite preview",
  test: "vitest run --coverage",
  "test:ui": "vitest --ui",
  "test:e2e": "playwright test",
  lint: "biome ci .",
  "lint-fix": "biome check --write --unsafe .",
  format: "biome format --write .",
  "format-check": "biome format .",
  typecheck: "tsc -b --noEmit",
};
writeFileSync("package.json", `${JSON.stringify(pkg, null, 2)}\n`);
console.log("  merged scripts into package.json");

// ============================================================================
// Step 8.5: Pre-stage Tailwind v4 wiring before shadcn init.
// shadcn-cli's preflight checks `vite.config.ts` for the @tailwindcss/vite
// plugin and `src/index.css` for the `@import "tailwindcss"` directive.
// Without these, "Validating Tailwind CSS" fails. The same resources are
// re-copied in Step 10 — that pass becomes a no-op for these two files.
// ============================================================================

console.log("\nStep 8.5: Pre-staging Tailwind v4 wiring...");
copyResource("frontend/vite.config.ts");
copyResource("frontend/src/index.css");

// ============================================================================
// Step 9: Initialize shadcn/ui (with defaults). Adds src/lib/utils.ts (cn()).
// Must run AFTER package.json is patched (shadcn reads it) and AFTER Step 8.5
// so the Tailwind v4 wiring is in place for the preflight check.
// ============================================================================

console.log("\nStep 9: Initializing shadcn/ui...");
await runQuiet("shadcn/ui initialized", $`bunx --bun shadcn@latest init -d`);

// ============================================================================
// Step 9.5: Add the shadcn components the layout + pages depend on (button,
// card). The `--yes` flag suppresses the "ready to add?" confirmation prompt;
// `--overwrite` is the safe choice because nothing should exist at the target
// paths yet. shadcn-cli auto-installs any required Radix peer-deps.
// ============================================================================

console.log("\nStep 9.5: Adding shadcn components (button, card)...");
await runQuiet(
  "shadcn components added (button, card)",
  $`bunx --bun shadcn@latest add button card --yes --overwrite`,
);

// ============================================================================
// Step 10: Copy frontend resources on top of the scaffold. These OVERWRITE
// the Vite-generated equivalents (vite.config.ts, src/index.css, etc.) and
// add the e2e suite + Playwright config + frontend Makefile.
// ============================================================================

console.log("\nStep 10: Copying frontend resources...");
process.chdir(projectRoot); // copy helpers expect project-root-relative paths

copyResource("frontend/vite.config.ts");
copyResource("frontend/playwright.config.ts");
copyResource("frontend/Makefile");
copyResource("frontend/CLAUDE.md");
copyResource("frontend/src/index.css");
copyResource("frontend/src/vite-env.d.ts");
copyResource("frontend/src/setupTests.ts");
copyResource("frontend/src/App.tsx");
// Tree copies merge into existing dirs — shadcn-init's `lib/utils.ts` and any
// `components/ui/*` it adds later survive; our `lib/api.ts`, the Layout
// component, and the page modules slot in alongside.
copyResourceTree("frontend/src/lib");
copyResourceTree("frontend/src/components");
copyResourceTree("frontend/src/pages");
copyResourceTree("frontend/e2e");

// ============================================================================
// Step 10.5: Patch Vite-generated files that the Vite scaffold owns but
// would otherwise fail the strict gate.
//
//   (a) frontend/.gitignore — Vite's default omits coverage/, test-results/,
//       playwright-report/. Biome's `vcs.useIgnoreFile: true` reads the
//       .gitignore relative to its CWD; since `make -C frontend ...` invokes
//       biome from frontend/, the repo-root .gitignore is invisible to it
//       and biome ends up scanning the istanbul HTML coverage report.
//
//   (b) frontend/src/main.tsx — Vite's default uses
//       `document.getElementById("root")!` (non-null assertion), which
//       biome's `noNonNullAssertion` flags as a warning. Because the project
//       runs `biome ci` (warnings-are-errors), the warning fails the gate.
//       Replace with an explicit null-check that throws — matches the
//       project's "no graceful degradation" rule.
// ============================================================================

console.log("\nStep 10.5: Patching Vite-generated frontend files...");

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
    writeFileSync(frontendGitignore, existing.trimEnd() + "\n" + block);
    console.log(
      `  patched frontend/.gitignore (added ${missing.length} entries)`,
    );
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
    console.log("  patched frontend/src/main.tsx (removed non-null assertion)");
  }
}

// ============================================================================
// Step 11: Copy backend resources file-by-file.
//
// Note: we deliberately DO NOT use `copyResourceTree("backend")` here even
// though it would work — it would also copy the stale `backend/Dockerfile`
// and `backend/.dockerignore` from earlier iterations. The bundled Docker
// image now builds from a project-root Dockerfile (see Step 12), so the
// per-backend ones must not land in the user's tree.
// ============================================================================

console.log("\nStep 11: Copying backend resources...");
copyResource("backend/pyproject.toml");
copyResource("backend/Makefile");
copyResource("backend/README.md");
copyResource("backend/CLAUDE.md");
copyResourceTree("backend/server");
copyResourceTree("backend/tests");

// ============================================================================
// Step 12: Top-level orchestration files.
//   - Makefile: top-level make targets (delegates via `make -C ...`).
//   - .gitignore: covers Python, Node/Bun/Vite, e2e artefacts, Docker. The
//     resource is named `gitignore` (no leading dot) so it doesn't accidentally
//     gitignore the resource tree itself in the skill repo.
//   - .github/workflows/build.yml: bun + uv + `make ci` + Playwright cache.
//   - CLAUDE.md: project-root agent memory (inner-loop, ports, Docker, anti-
//     patterns). The backend/CLAUDE.md and frontend/CLAUDE.md are copied with
//     their respective resource trees in Steps 10 / 11.
//   - docker-compose.yml: backend service for deploy-parity testing.
// ============================================================================

console.log("\nStep 12: Copying top-level orchestration files...");
copyResource("Makefile");
copyResource("gitignore", ".gitignore");
copyResource(".github/workflows/build.yml");
copyResource("CLAUDE.md");
// Layered docker-compose: the base + one overlay per DB backend. The Makefile
// picks which overlay to layer in via DATABASE_BACKEND={sqlite,postgres}.
copyResource("docker-compose.yml");
copyResource("docker-compose.sqlite.yml");
copyResource("docker-compose.postgres.yml");
// Multi-stage Dockerfile bundling the React SPA + FastAPI backend; build
// context is project root, so it must live alongside docker-compose.yml.
copyResource("Dockerfile");
copyResource(".dockerignore");

// ============================================================================
// Step 13: README.md + CONTRIBUTING.md.
// Preserved docs always win. Otherwise substitute {{projectName}} into the
// templates under resources/templates/.
// ============================================================================

console.log("\nStep 13: Writing README.md / CONTRIBUTING.md...");

const projectName = (() => {
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
})();

if (preservedReadme !== null) {
  writeFileSync(join(projectRoot, "README.md"), preservedReadme);
  console.log("  README.md preserved verbatim");
} else {
  writeTemplate("templates/README.md.template", "README.md", { projectName });
}

if (preservedContributing !== null) {
  writeFileSync(join(projectRoot, "CONTRIBUTING.md"), preservedContributing);
  console.log("  CONTRIBUTING.md preserved verbatim");
} else {
  writeTemplate("templates/CONTRIBUTING.md.template", "CONTRIBUTING.md", {
    projectName,
  });
}

// ============================================================================
// Step 14: uv sync to materialise the backend venv. The --directory flag is
// a uv top-level option (must come BEFORE the subcommand). This is the only
// safe way to invoke uv against backend/ without violating the project rule
// against `cd`-ing in shell commands.
// ============================================================================

console.log("\nStep 14: Running uv sync in backend/...");
await runQuiet("backend deps installed", $`uv --directory backend sync`);

// ============================================================================
// Step 15: One-shot autofix pass (best effort) so the verification step in
// Step 16 starts from clean files.
// ============================================================================

console.log("\nStep 15: Running `make fix`...");
try {
  await $`make fix`.quiet();
  console.log("  autofix complete");
} catch {
  console.log("  (some autofix steps had warnings — moving on)");
}

// ============================================================================
// Step 16: Verification — typecheck + tests on both halves. Skip e2e here
// (slow on first run, dependency-heavy); the user runs `make ci` themselves
// to verify the full strict gate.
// ============================================================================

console.log("\nStep 16: Verifying typecheck + tests on both halves...");
await runQuiet("typecheck green (mypy + tsc)", $`make typecheck`);
await runQuiet("tests green (pytest + vitest)", $`make test`);

// ============================================================================
// Done.
// ============================================================================

console.log("\nSetup complete.\n");
console.log("Canonical inner-loop:");
if (!isCurrentDir) {
  console.log(`  cd ${targetDir}`);
}
console.log("  make fix ci          # autofix everything, then run the strict gate");
console.log("\nDev:");
console.log("  make dev             # backend 8200 + frontend 5173 (human profile)");
console.log("  make agentic-dev     # backend 8201 + frontend 5174 (agent profile)");
console.log("\nNarrow inner-loops:");
console.log("  make test-py         # backend pytest only");
console.log("  make test-ts         # frontend vitest only");
console.log("  make typecheck-py    # mypy only");
console.log("  make typecheck-ts    # tsc only");
console.log("  make test-e2e        # Playwright (auto-launches both halves)");
console.log("\nDiscover everything:");
console.log("  make help");
