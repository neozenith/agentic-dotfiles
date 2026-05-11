// Variation registry — the source of truth for the runtime configurations
// the scaffolded project supports. Each entry pairs a name with the env-var
// bundle that selects that runtime combination (database backend, storage
// backend, backup overlay).
//
// The scaffold CLI consumes this list to:
//   1. Validate the variation name supplied on the command line.
//   2. Write the bundle to `.env` in the scaffolded project so `make docker-up`
//      and `make ci` pick that runtime out of the box.
//
// VARIATION TESTING IS NOT PART OF THIS SKILL. The bash harness at
// `tmp/test-matrix.sh` + `tmp/test-variation.sh` exercises each variation
// against the scaffolded project. Do not re-introduce a TS implementation
// of variation testing here — it duplicates the bash harness and conflates
// the scaffolder's job with the harness's.

export interface Variation {
  /** Variation name — used as the CLI positional argument. */
  name: string;
  /** Human-readable description shown by `list-variations`. */
  description: string;
  /**
   * Env-var bundle written to `.env` in the scaffolded project. Empty for
   * the unit-test-only variation (`sqlite-memory`), which needs no docker.
   */
  env: Record<string, string>;
}

const DEFAULT_AWS_BUCKET = "skills-practice-postgres-backup-7b04fa58";
const DEFAULT_AWS_REGION = "ap-southeast-2";

export const VARIATIONS: Variation[] = [
  {
    name: "sqlite-memory",
    description: "Pure unit tests (in-process aiosqlite per test). No docker. Default.",
    env: {},
  },
  {
    name: "sqlite-persisted",
    description: "Docker sqlite file at /app/data/app.db. Backup OFF.",
    env: {
      DATABASE_BACKEND: "sqlite",
      BACKUP_BACKEND: "none",
    },
  },
  {
    name: "postgres-no-backup",
    description: "Postgres docker, no storage backend. Backup OFF.",
    env: {
      DATABASE_BACKEND: "postgres",
      BACKUP_BACKEND: "none",
    },
  },
  {
    name: "postgres-local-backup",
    description: "Postgres + LocalStorage overlay. Backup roundtrip on disk.",
    env: {
      DATABASE_BACKEND: "postgres",
      BACKUP_BACKEND: "local",
    },
  },
  {
    name: "postgres-minio-backup",
    description: "Postgres + MinIO overlay. Backup roundtrip via local S3.",
    env: {
      DATABASE_BACKEND: "postgres",
      BACKUP_BACKEND: "minio",
    },
  },
  {
    name: "postgres-aws-backup",
    description:
      "Postgres + real AWS S3. Caller must supply AWS_ACCESS_KEY_ID / AWS_PROFILE at runtime.",
    env: {
      DATABASE_BACKEND: "postgres",
      BACKUP_BACKEND: "none",
      STORAGE_BACKEND: "s3",
      STORAGE_BUCKET: DEFAULT_AWS_BUCKET,
      S3_REGION: DEFAULT_AWS_REGION,
      S3_ADDRESSING_STYLE: "auto",
    },
  },
];

export const variationByName = (name: string): Variation | undefined =>
  VARIATIONS.find((v) => v.name === name);

export const variationNames = (): string[] => VARIATIONS.map((v) => v.name);

export const DEFAULT_VARIATION = "sqlite-memory";
