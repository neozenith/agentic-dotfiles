// Variation registry — the source of truth for the runtime configurations
// the scaffold supports. Each entry pairs a name (used as the CLI argument
// and log filename) with a `run(ctx)` function that boots the stack, runs
// assertions, and returns one of "pass" | "fail" | "skip".
//
// Both the `variation` and `matrix` subcommands consume this list. Adding a
// new variation means adding ONE entry here.

import { $ } from "bun";
import { join } from "node:path";

import { appendLogLine, appendShellOutput } from "./shell-log.ts";

export type Outcome = "pass" | "fail" | "skip";

export interface VariationCtx {
  /** Project root containing the top-level Makefile. */
  root: string;
  /** Backend port for HTTP status checks (matches docker-compose). */
  port: number;
  /** Absolute path to the per-variation log file. */
  log: string;
  /** Optional override for the AWS S3 bucket name (postgres-aws-backup). */
  awsBucket?: string;
  /** Optional override for the AWS region (postgres-aws-backup). */
  awsRegion?: string;
  /** Optional explicit AWS profile (postgres-aws-backup). */
  awsProfile?: string;
}

export interface Variation {
  name: string;
  description: string;
  run: (ctx: VariationCtx) => Promise<Outcome>;
}

const DEFAULT_AWS_BUCKET = "skills-practice-postgres-backup-7b04fa58";
const DEFAULT_AWS_REGION = "ap-southeast-2";

// ── Shared helpers used by individual variations ─────────────────────────

const failReason = async (
  ctx: VariationCtx,
  reason: string,
): Promise<Outcome> => {
  await appendLogLine(ctx.log, `FAIL: ${reason}`);
  return "fail";
};

const skipReason = async (
  ctx: VariationCtx,
  reason: string,
): Promise<Outcome> => {
  await appendLogLine(ctx.log, `SKIP: ${reason}`);
  return "skip";
};

/**
 * Tear down every overlay combination. The bash original does the same fan-out
 * because a previous variation may have booted a different overlay than the
 * current one, and `docker compose down` only knows about the overlays it was
 * launched with.
 */
export const cleanupAllOverlays = async (root: string): Promise<void> => {
  const dbs = ["sqlite", "postgres"] as const;
  const backups = ["none", "local", "minio"] as const;
  for (const db of dbs) {
    for (const backup of backups) {
      // nothrow + quiet — best-effort cleanup, errors are expected when the
      // overlay isn't running.
      await $`make docker-down`
        .cwd(root)
        .env({
          ...process.env,
          DATABASE_BACKEND: db,
          BACKUP_BACKEND: backup,
        })
        .quiet()
        .nothrow();
    }
  }
};

/** Boot the docker stack with the given env. Returns true on success. */
const bootStack = async (
  ctx: VariationCtx,
  env: Record<string, string>,
): Promise<boolean> => {
  await appendLogLine(
    ctx.log,
    `--- BOOT: ${Object.entries(env)
      .filter(([k]) => k !== "PATH")
      .map(([k, v]) => `${k}=${v}`)
      .join(" ")} ---`,
  );
  const out = await $`make docker-up`
    .cwd(ctx.root)
    .env({ ...process.env, ...env })
    .quiet()
    .nothrow();
  await appendShellOutput(ctx.log, out);
  return out.exitCode === 0;
};

/** Hit /api/admin/backup/status; assert `enabled` matches `expected`. */
const assertBackupEnabled = async (
  ctx: VariationCtx,
  expected: boolean,
): Promise<boolean> => {
  const url = `http://localhost:${ctx.port}/api/admin/backup/status`;
  const res = await $`curl -sf ${url}`.quiet().nothrow();
  if (res.exitCode !== 0) {
    await appendLogLine(ctx.log, `  status endpoint unreachable: ${url}`);
    return false;
  }
  const body = res.stdout.toString();
  await appendLogLine(ctx.log, `  status: ${body.trim()}`);
  const wanted = expected ? '"enabled":true' : '"enabled":false';
  return body.includes(wanted);
};

const runMakeTarget = async (
  ctx: VariationCtx,
  cwd: string,
  target: string,
  env: Record<string, string> = {},
): Promise<boolean> => {
  const out = await $`make ${target}`
    .cwd(cwd)
    .env({ ...process.env, ...env })
    .quiet()
    .nothrow();
  await appendShellOutput(ctx.log, out);
  return out.exitCode === 0;
};

const runApiDockerTests = (ctx: VariationCtx): Promise<boolean> =>
  runMakeTarget(ctx, join(ctx.root, "backend"), "test-docker", {
    BACKEND_BASE_URL: `http://localhost:${ctx.port}`,
  });

const runRoundtrip = (ctx: VariationCtx): Promise<boolean> =>
  runMakeTarget(ctx, join(ctx.root, "backend"), "test-backup-roundtrip", {
    BACKEND_BASE_URL: `http://localhost:${ctx.port}`,
  });

/**
 * Resolve AWS credentials for the postgres-aws-backup variation. Honors:
 *   1. ctx.awsProfile / $AWS_PROFILE — runs `aws configure export-credentials`
 *      and returns the resulting static AKID/SAK/SESSION_TOKEN trio. This
 *      handles SSO and role-assumption profiles uniformly.
 *   2. $AWS_ACCESS_KEY_ID — direct passthrough of the host's static creds.
 * Returns null with a SKIP-tagged log line if neither is set, or if the
 * profile path was selected but the `aws` CLI isn't available.
 */
const resolveAwsCreds = async (
  ctx: VariationCtx,
): Promise<{
  AWS_ACCESS_KEY_ID: string;
  AWS_SECRET_ACCESS_KEY: string;
  AWS_SESSION_TOKEN: string;
} | null> => {
  const profile = ctx.awsProfile ?? process.env.AWS_PROFILE ?? "";
  if (profile) {
    const which = await $`command -v aws`.quiet().nothrow();
    if (which.exitCode !== 0) {
      await appendLogLine(
        ctx.log,
        `AWS_PROFILE=${profile} set but 'aws' CLI not on PATH`,
      );
      return null;
    }
    const out = await $`aws configure export-credentials --profile ${profile} --format env`
      .quiet()
      .nothrow();
    await appendShellOutput(ctx.log, out);
    if (out.exitCode !== 0) {
      await appendLogLine(
        ctx.log,
        `aws configure export-credentials failed for profile=${profile}`,
      );
      return null;
    }
    // Parse `export KEY=VALUE` lines from stdout.
    const env: Record<string, string> = {};
    for (const line of out.stdout.toString().split("\n")) {
      const m = line.match(/^export\s+(\w+)=(.*)$/);
      if (m) env[m[1] as string] = (m[2] as string).replace(/^"|"$/g, "");
    }
    if (!env.AWS_ACCESS_KEY_ID || !env.AWS_SECRET_ACCESS_KEY) {
      await appendLogLine(
        ctx.log,
        `aws export-credentials produced no AKID/SAK for profile=${profile}`,
      );
      return null;
    }
    return {
      AWS_ACCESS_KEY_ID: env.AWS_ACCESS_KEY_ID,
      AWS_SECRET_ACCESS_KEY: env.AWS_SECRET_ACCESS_KEY,
      AWS_SESSION_TOKEN: env.AWS_SESSION_TOKEN ?? "",
    };
  }
  if (process.env.AWS_ACCESS_KEY_ID) {
    return {
      AWS_ACCESS_KEY_ID: process.env.AWS_ACCESS_KEY_ID,
      AWS_SECRET_ACCESS_KEY: process.env.AWS_SECRET_ACCESS_KEY ?? "",
      AWS_SESSION_TOKEN: process.env.AWS_SESSION_TOKEN ?? "",
    };
  }
  return null;
};

// ── Variations ───────────────────────────────────────────────────────────

export const VARIATIONS: Variation[] = [
  {
    name: "sqlite-memory",
    description: "Pure unit tests (in-process aiosqlite per test). No docker.",
    run: async (ctx) => {
      const ok = await runMakeTarget(ctx, ctx.root, "test-py");
      return ok ? "pass" : failReason(ctx, "make test-py");
    },
  },
  {
    name: "sqlite-persisted",
    description:
      "Default docker-up (sqlite file at /app/data/app.db). Backup OFF.",
    run: async (ctx) => {
      if (!(await bootStack(ctx, { DATABASE_BACKEND: "sqlite", BACKUP_BACKEND: "none" })))
        return failReason(ctx, "docker-up");
      if (!(await assertBackupEnabled(ctx, false)))
        return failReason(ctx, "backup should be OFF for sqlite-persisted");
      if (!(await runApiDockerTests(ctx)))
        return failReason(ctx, "test-docker");
      return "pass";
    },
  },
  {
    name: "postgres-no-backup",
    description: "Postgres docker, no storage backend. Backup OFF.",
    run: async (ctx) => {
      if (!(await bootStack(ctx, { DATABASE_BACKEND: "postgres", BACKUP_BACKEND: "none" })))
        return failReason(ctx, "docker-up");
      if (!(await assertBackupEnabled(ctx, false)))
        return failReason(ctx, "backup should be OFF for postgres-no-backup");
      if (!(await runApiDockerTests(ctx)))
        return failReason(ctx, "test-docker");
      return "pass";
    },
  },
  {
    name: "postgres-local-backup",
    description: "Postgres + LocalStorage overlay. Backup roundtrip on disk.",
    run: async (ctx) => {
      if (!(await bootStack(ctx, { DATABASE_BACKEND: "postgres", BACKUP_BACKEND: "local" })))
        return failReason(ctx, "docker-up");
      if (!(await assertBackupEnabled(ctx, true)))
        return failReason(ctx, "backup should be ON for postgres-local-backup");
      if (!(await runRoundtrip(ctx)))
        return failReason(ctx, "backup-roundtrip");
      return "pass";
    },
  },
  {
    name: "postgres-minio-backup",
    description: "Postgres + MinIO overlay. Backup roundtrip via local S3.",
    run: async (ctx) => {
      if (!(await bootStack(ctx, { DATABASE_BACKEND: "postgres", BACKUP_BACKEND: "minio" })))
        return failReason(ctx, "docker-up");
      if (!(await assertBackupEnabled(ctx, true)))
        return failReason(ctx, "backup should be ON for postgres-minio-backup");
      if (!(await runRoundtrip(ctx)))
        return failReason(ctx, "backup-roundtrip");
      return "pass";
    },
  },
  {
    name: "postgres-aws-backup",
    description:
      "Postgres + real AWS S3. SKIPs (rc=77) if no creds. Honors AWS_PROFILE or static AKID.",
    run: async (ctx) => {
      const creds = await resolveAwsCreds(ctx);
      if (!creds) return skipReason(ctx, "no AWS credentials available");
      const bucket = ctx.awsBucket ?? process.env.STORAGE_BUCKET_AWS ?? DEFAULT_AWS_BUCKET;
      const region = ctx.awsRegion ?? process.env.AWS_REGION ?? DEFAULT_AWS_REGION;
      await appendLogLine(ctx.log, `  bucket: s3://${bucket}  region: ${region}`);
      const ok = await bootStack(ctx, {
        DATABASE_BACKEND: "postgres",
        BACKUP_BACKEND: "none",
        STORAGE_BACKEND: "s3",
        STORAGE_BUCKET: bucket,
        S3_REGION: region,
        S3_ADDRESSING_STYLE: "auto",
        ...creds,
      });
      if (!ok) return failReason(ctx, "docker-up");
      if (!(await assertBackupEnabled(ctx, true)))
        return failReason(ctx, "backup should be ON for postgres-aws-backup");
      if (!(await runRoundtrip(ctx)))
        return failReason(ctx, "backup-roundtrip");
      return "pass";
    },
  },
];

export const variationByName = (name: string): Variation | undefined =>
  VARIATIONS.find((v) => v.name === name);

export const variationNames = (): string[] => VARIATIONS.map((v) => v.name);
