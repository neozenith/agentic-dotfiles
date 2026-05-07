// Steps 3-8: install all frontend deps, swap ESLint for Biome, install
// Playwright Chromium, then patch tsconfig + biome.json + package.json.
//
// Runs from cwd = frontend/ (chdir performed at the end of Step 2).

// @ts-ignore — `bun` is a runtime-provided module
import { $ } from "bun";
import { existsSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";

import { log } from "../lib/logger.ts";
import { runQuiet } from "../lib/shell.ts";

const STRICT_FAMILY = [
  '"strict": true',
  '"noUncheckedIndexedAccess": true',
  '"exactOptionalPropertyTypes": true',
  '"noImplicitOverride": true',
  '"noPropertyAccessFromIndexSignature": true',
  '"noFallthroughCasesInSwitch": true',
];

/** Patch one tsconfig file with the strict family + the @/* path alias. */
const patchTsconfig = (filePath: string): void => {
  if (!existsSync(filePath)) return;
  let content = readFileSync(filePath, "utf8");

  // Drop deprecated baseUrl line.
  content = content.replace(/^\s*"baseUrl"\s*:\s*"[^"]*"\s*,?\s*\n/m, "");

  // Vite's root tsconfig.json has `files` + `references` only — no
  // compilerOptions block to patch into. shadcn-cli reads the root file for
  // the @/* alias, so we synthesise a fresh compilerOptions block at the top
  // of the object instead of falling through to the regex-driven branches.
  if (!/"compilerOptions"\s*:\s*\{/.test(content)) {
    const optsLines = [
      '"baseUrl": "."',
      '"paths": { "@/*": ["./src/*"] }',
      ...STRICT_FAMILY,
    ]
      .map((line, i, arr) => `    ${line}${i < arr.length - 1 ? "," : ""}`)
      .join("\n");
    const block = `  "compilerOptions": {\n${optsLines}\n  },`;
    content = content.replace(/^\s*\{\s*\n/, (m: string) => `${m}${block}\n`);
    writeFileSync(filePath, content);
    log(`  patched ${filePath} (inserted compilerOptions block)`);
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

  // Inject the strict family. Replace existing entries; insert any missing.
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
  log(`  patched ${filePath}`);
};

/** Patch biome.json: exclude common build/test/scratch dirs, enable cssModules. */
const patchBiomeJson = (): void => {
  if (!existsSync("biome.json")) return;
  // Parse-mutate-stringify avoids the nested-brace pitfall of regex patching.
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
      // Tailwind v4 + shadcn use @custom-variant, @theme inline, etc. which
      // Biome's CSS parser doesn't yet understand. Excluding the theme-token
      // entry point sidesteps the parsing errors without disabling Biome on
      // actual app code.
      "!!**/src/index.css",
    ],
  };
  // Biome 2.x has no `tailwindDirectives` key — Tailwind v4 uses
  // `@import "tailwindcss"` rather than `@tailwind` directives, so the parser
  // option is unnecessary. cssModules is the only knob we need.
  if (bio.css === undefined) {
    bio.css = { parser: { cssModules: true } };
  }
  writeFileSync("biome.json", `${JSON.stringify(bio, null, 2)}\n`);
  log("  patched biome.json");
};

/** Merge our package.json scripts into the Vite scaffold's. */
const mergePackageJsonScripts = (): void => {
  type PackageJson = {
    scripts?: Record<string, string>;
    [k: string]: unknown;
  };
  const pkg: PackageJson = JSON.parse(readFileSync("package.json", "utf8"));
  // Single-quoted strings: ${API_PORT:-8200} embeds as a literal shell
  // expansion in the JSON output. Don't switch to backticks without
  // re-escaping the dollar signs.
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
  log("  merged scripts into package.json");
};

/** Steps 3 + 4 + 5 + 6 + 7 + 8 in order. cwd must be frontend/ on entry. */
export const installFrontendTooling = async (): Promise<void> => {
  // Step 3: install all the deps the scaffold needs.
  log("\nStep 3: Installing all dependencies...");
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

  // Step 4: replace ESLint with Biome.
  log("\nStep 4: Switching from ESLint to Biome...");
  await runQuiet(
    "removed eslint deps",
    $`bun remove @eslint/js eslint eslint-plugin-react-hooks eslint-plugin-react-refresh globals typescript-eslint`,
  );
  if (existsSync("eslint.config.js")) {
    unlinkSync("eslint.config.js");
    log("  removed eslint.config.js");
  }
  await runQuiet("biome initialized", $`bunx --bun biome init`);

  // Step 5: install Playwright Chromium.
  log("\nStep 5: Installing Playwright Chromium...");
  await runQuiet(
    "Chromium installed",
    $`bunx --bun playwright install --with-deps chromium`,
  );

  // Step 6: patch tsconfig.json + tsconfig.app.json with the strict family.
  log("\nStep 6: Patching tsconfigs with the strict family...");
  patchTsconfig("tsconfig.json");
  patchTsconfig("tsconfig.app.json");

  // Step 7: patch biome.json (excludes + cssModules).
  log("\nStep 7: Patching biome.json...");
  patchBiomeJson();

  // Step 8: merge our package.json scripts into the scaffold's.
  log("\nStep 8: Merging package.json scripts...");
  mergePackageJsonScripts();
};
