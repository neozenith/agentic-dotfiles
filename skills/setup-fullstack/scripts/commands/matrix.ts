// `matrix` subcommand — orchestrates a full pass of every variation against
// one freshly-scaffolded project. Equivalent to the bash test-matrix.sh
// predecessor but routed through the same CLI.
//
// Default flow:
//   1. (optional) Scaffold the project at --root via the scaffold pipeline.
//   2. docker-build so every variation runs against the just-scaffolded code.
//   3. For each variation, dispatch through the variation runner; record
//      pass / fail / skip.
//   4. Print a final summary; exit 1 if anything failed, else 0.

import { $ } from "bun";
import { parseArgs } from "node:util";
import { resolve } from "node:path";

import { elog, log } from "../lib/logger.ts";
import { appendLogLine } from "../lib/shell-log.ts";
import {
  VARIATIONS,
  variationNames,
  type Outcome,
  type Variation,
} from "../lib/variations.ts";
import { runScaffold } from "./scaffold.ts";
import { runVariation } from "./variation.ts";

export const MATRIX_HELP = `\
setup-fullstack matrix — scaffold once + run every variation in sequence.

USAGE
  setup-fullstack matrix [--root PATH] [--port N] [--log PATH]
                          [--skip-scaffold] [--skip-build]
                          [--include LIST] [--exclude LIST]
                          [--bucket NAME] [--region REGION] [--profile NAME]

OPTIONS
  -h, --help          Show this help and exit.
  --root PATH         Project root (default: current working directory).
  --port N            Backend port for HTTP status checks (default: 8210).
  --log PATH          Path for the matrix-summary log file
                      (default: <root>/tmp/matrix-summary.log).
  --skip-scaffold     Skip the scaffold step. Use when the project is already
                      scaffolded and only the variations need to run.
  --skip-build        Skip \`make docker-build\`. Use only if the image is known
                      to match the current source.
  --include LIST      Comma-separated subset of variations to run.
  --exclude LIST      Comma-separated subset of variations to skip.
  --bucket NAME       AWS S3 bucket (postgres-aws-backup only).
  --region REGION     AWS region (postgres-aws-backup only).
  --profile NAME      AWS profile (postgres-aws-backup only).

EXIT CODES
   0  Every variation either PASSed or SKIPped (no FAILs).
   1  At least one variation FAILed (or scaffold / docker-build failed).

EXAMPLES
  setup-fullstack matrix
  setup-fullstack matrix --skip-scaffold
  setup-fullstack matrix --include sqlite-memory,postgres-minio-backup
  AWS_PROFILE=dev setup-fullstack matrix --include postgres-aws-backup
`;

export interface MatrixOptions {
  root: string;
  port: number;
  log: string;
  skipScaffold: boolean;
  skipBuild: boolean;
  include?: string[];
  exclude?: string[];
  bucket?: string;
  region?: string;
  profile?: string;
}

const splitList = (raw: string): string[] =>
  raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

const filterVariations = (opts: MatrixOptions): Variation[] => {
  let list = [...VARIATIONS];
  if (opts.include && opts.include.length > 0) {
    const want = new Set(opts.include);
    list = list.filter((v) => want.has(v.name));
  }
  if (opts.exclude && opts.exclude.length > 0) {
    const skip = new Set(opts.exclude);
    list = list.filter((v) => !skip.has(v.name));
  }
  return list;
};

export const runMatrix = async (opts: MatrixOptions): Promise<number> => {
  const targets = filterVariations(opts);
  if (targets.length === 0) {
    elog("error: --include / --exclude left no variations to run");
    return 1;
  }

  await appendLogLine(
    opts.log,
    `===== MATRIX RUN  ${new Date().toISOString()} =====`,
  );

  if (!opts.skipScaffold) {
    log("─── Step 1: scaffold ─────────────────────────────");
    await runScaffold({
      target: opts.root,
      skipFix: false,
      skipVerify: true,
    });
    log("  ✓ scaffold ok");
  } else {
    log("  → reusing existing scaffold (--skip-scaffold)");
  }

  if (!opts.skipBuild) {
    log("─── Step 1.5: docker-build ───────────────────────");
    const build = await $`make docker-build`
      .cwd(opts.root)
      .quiet()
      .nothrow();
    if (build.exitCode !== 0) {
      await appendLogLine(opts.log, "FATAL: docker-build failed");
      await appendLogLine(opts.log, build.stdout.toString());
      await appendLogLine(opts.log, build.stderr.toString());
      elog(`FATAL: docker-build failed; see ${opts.log}`);
      return 1;
    }
    log("  ✓ image built");
  } else {
    log("  → skipping docker-build (--skip-build)");
  }

  log("─── Step 2: matrix variations ────────────────────");

  const results: { name: string; outcome: Outcome; logPath: string }[] = [];
  let anyFail = false;

  for (const v of targets) {
    const variationLog = resolve(opts.root, "tmp", `variation-${v.name}.log`);
    const outcome = await runVariation({
      name: v.name,
      root: opts.root,
      port: opts.port,
      log: variationLog,
      ...(opts.bucket !== undefined ? { bucket: opts.bucket } : {}),
      ...(opts.region !== undefined ? { region: opts.region } : {}),
      ...(opts.profile !== undefined ? { profile: opts.profile } : {}),
    });
    results.push({ name: v.name, outcome, logPath: variationLog });
    if (outcome === "fail") anyFail = true;
  }

  log("");
  log("═══════════════════════════════════════════════════════════");
  log("  Matrix Summary");
  log("═══════════════════════════════════════════════════════════");
  await appendLogLine(opts.log, "");
  await appendLogLine(
    opts.log,
    `===== MATRIX SUMMARY  ${new Date().toISOString()} =====`,
  );
  for (const r of results) {
    const verdict = r.outcome.toUpperCase().padEnd(4);
    const tail = r.outcome === "fail" ? `  log=${r.logPath}` : "";
    const line = `${verdict}  ${r.name}${tail}`;
    log(`  ${line}`);
    await appendLogLine(opts.log, `  ${line}`);
  }
  log("");
  if (anyFail) {
    log("  ✗ matrix has FAILs — inspect the per-variation logs");
    return 1;
  }
  log("  ✓ matrix clean — every variation either PASSed or SKIPped");
  return 0;
};

export const matrixMain = async (argv: string[]): Promise<number> => {
  const { values } = parseArgs({
    args: argv,
    options: {
      help: { type: "boolean", short: "h", default: false },
      root: { type: "string" },
      port: { type: "string" },
      log: { type: "string" },
      "skip-scaffold": { type: "boolean", default: false },
      "skip-build": { type: "boolean", default: false },
      include: { type: "string" },
      exclude: { type: "string" },
      bucket: { type: "string" },
      region: { type: "string" },
      profile: { type: "string" },
    },
    allowPositionals: false,
    strict: true,
  });

  if (values.help) {
    process.stdout.write(MATRIX_HELP);
    return 0;
  }

  const root = resolve(values.root ?? ".");
  const port = values.port ? parseInt(values.port, 10) : 8210;
  if (Number.isNaN(port)) {
    elog(`error: --port must be an integer (got '${values.port}')`);
    return 1;
  }
  const logPath = values.log ?? resolve(root, "tmp", "matrix-summary.log");

  const include = values.include ? splitList(values.include) : undefined;
  const exclude = values.exclude ? splitList(values.exclude) : undefined;

  const allNames = new Set(variationNames());
  for (const name of [...(include ?? []), ...(exclude ?? [])]) {
    if (!allNames.has(name)) {
      elog(`error: unknown variation '${name}' in --include / --exclude`);
      elog(`Valid: ${variationNames().join(", ")}`);
      return 1;
    }
  }

  const opts: MatrixOptions = {
    root,
    port,
    log: logPath,
    skipScaffold: values["skip-scaffold"] === true,
    skipBuild: values["skip-build"] === true,
    ...(include !== undefined ? { include } : {}),
    ...(exclude !== undefined ? { exclude } : {}),
    ...(values.bucket !== undefined ? { bucket: values.bucket } : {}),
    ...(values.region !== undefined ? { region: values.region } : {}),
    ...(values.profile !== undefined ? { profile: values.profile } : {}),
  };

  return runMatrix(opts);
};
