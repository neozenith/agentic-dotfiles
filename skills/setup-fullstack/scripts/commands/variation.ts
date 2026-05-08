// `variation` subcommand — boots the docker stack for one named variation,
// runs that variation's assertions + tests, and tears the stack down. The
// per-variation logic lives in lib/variations.ts; this file only handles the
// CLI plumbing (arg parsing, log path resolution, exit code mapping).
//
// Exit codes match the test-variation.sh predecessor:
//   0   PASS
//   1   FAIL  (or unknown variation, or arg error)
//   77  SKIP  (variation requires unavailable creds / config)

import { parseArgs } from "node:util";
import { resolve } from "node:path";

import { elog, log } from "../lib/logger.ts";
import { appendLogLine } from "../lib/shell-log.ts";
import {
  cleanupAllOverlays,
  variationByName,
  variationNames,
  type Outcome,
} from "../lib/variations.ts";

export const VARIATION_HELP = `\
setup-fullstack variation — boot the stack for one named variation, run its
                              assertions + tests, then tear down.

USAGE
  setup-fullstack variation <name> [--root PATH] [--port N] [--log PATH]
                                     [--bucket NAME] [--region REGION]
                                     [--profile NAME]

ARGUMENTS
  <name>              Variation to run. See \`setup-fullstack list-variations\`.

OPTIONS
  -h, --help          Show this help and exit.
  --root PATH         Project root containing the top-level Makefile.
                      Defaults to the current working directory.
  --port N            Backend port for HTTP status checks. Default: 8210.
  --log PATH          Path for the per-variation log file.
                      Default: <root>/tmp/variation-<name>.log.
  --bucket NAME       AWS S3 bucket name (postgres-aws-backup only).
                      Default: \$STORAGE_BUCKET_AWS or a built-in fallback.
  --region REGION     AWS region (postgres-aws-backup only).
                      Default: \$AWS_REGION or ap-southeast-2.
  --profile NAME      AWS profile to source credentials from
                      (postgres-aws-backup only). Falls back to \$AWS_PROFILE,
                      then static \$AWS_ACCESS_KEY_ID.

EXIT CODES
   0  PASS
   1  FAIL (or argument / dispatch error)
  77  SKIP (variation requires unavailable creds / config)

EXAMPLES
  setup-fullstack variation sqlite-memory
  setup-fullstack variation postgres-minio-backup --root /path/to/project
  AWS_PROFILE=dev setup-fullstack variation postgres-aws-backup
`;

export interface VariationOptions {
  name: string;
  root: string;
  port: number;
  log: string;
  bucket?: string;
  region?: string;
  profile?: string;
}

/** Map an Outcome to its exit code. */
export const outcomeExitCode = (outcome: Outcome): number => {
  switch (outcome) {
    case "pass":
      return 0;
    case "skip":
      return 77;
    case "fail":
      return 1;
  }
};

export const runVariation = async (
  opts: VariationOptions,
): Promise<Outcome> => {
  const variation = variationByName(opts.name);
  if (!variation) {
    elog(`error: unknown variation '${opts.name}'`);
    elog(`Valid: ${variationNames().join(", ")}`);
    return "fail";
  }

  const start = Date.now();
  await appendLogLine(
    opts.log,
    `===== VARIATION ${opts.name}  ${new Date().toISOString()} =====`,
  );
  log(`▶ ${opts.name}`);

  const ctx = {
    root: opts.root,
    port: opts.port,
    log: opts.log,
    awsBucket: opts.bucket,
    awsRegion: opts.region,
    awsProfile: opts.profile,
  };

  let outcome: Outcome;
  try {
    outcome = await variation.run(ctx);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    await appendLogLine(opts.log, `EXCEPTION: ${msg}`);
    outcome = "fail";
  } finally {
    await cleanupAllOverlays(opts.root);
  }

  const elapsed = Math.floor((Date.now() - start) / 1000);
  const verdict = outcome.toUpperCase();
  const tail =
    outcome === "pass"
      ? `(${elapsed}s)`
      : outcome === "skip"
        ? `(skipped, ${elapsed}s)`
        : `(${elapsed}s)  log=${opts.log}`;
  log(`VARIATION ${opts.name}: ${verdict} ${tail}`);
  return outcome;
};

export const variationMain = async (argv: string[]): Promise<number> => {
  const { values, positionals } = parseArgs({
    args: argv,
    options: {
      help: { type: "boolean", short: "h", default: false },
      root: { type: "string" },
      port: { type: "string" },
      log: { type: "string" },
      bucket: { type: "string" },
      region: { type: "string" },
      profile: { type: "string" },
    },
    allowPositionals: true,
    strict: true,
  });

  if (values.help) {
    process.stdout.write(VARIATION_HELP);
    return 0;
  }

  if (positionals.length === 0) {
    elog("error: variation name required");
    elog(`Valid: ${variationNames().join(", ")}`);
    return 1;
  }
  if (positionals.length > 1) {
    elog(`error: too many positional arguments (got ${positionals.length}, expected 1)`);
    return 1;
  }

  const name = positionals[0] as string;
  const root = resolve(values.root ?? ".");
  const port = values.port ? parseInt(values.port, 10) : 8210;
  if (Number.isNaN(port)) {
    elog(`error: --port must be an integer (got '${values.port}')`);
    return 1;
  }
  const logPath = values.log ?? resolve(root, "tmp", `variation-${name}.log`);

  const opts: VariationOptions = {
    name,
    root,
    port,
    log: logPath,
    ...(values.bucket !== undefined ? { bucket: values.bucket } : {}),
    ...(values.region !== undefined ? { region: values.region } : {}),
    ...(values.profile !== undefined ? { profile: values.profile } : {}),
  };

  const outcome = await runVariation(opts);
  return outcomeExitCode(outcome);
};
