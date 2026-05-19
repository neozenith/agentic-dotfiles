# Persistence + Backup Matrix

The scaffold ships with a cloud-agnostic object-storage layer plus an optional
Postgres backup feature. The matrix is **selectable at runtime** via env vars
and Make vars — no scaffold-time choice required. Same code, all options.

## Storage backend axis (env: `STORAGE_BACKEND`)

| Value      | What it stores                                | When to use                                        |
|------------|-----------------------------------------------|----------------------------------------------------|
| *(unset)*  | nothing — backup feature is OFF               | Default. Local dev when you don't care about backup. |
| `memory`   | dict in-process                               | Unit tests; quick smoke checks. Lost on restart.    |
| `local`    | files under a directory                       | Local dev with persistence; cheap CI tier.         |
| `s3`       | AWS S3 / MinIO / any S3-API service           | Production + integration tests via MinIO.          |

`s3` covers both AWS and MinIO: same backend class, switched via `S3_ENDPOINT_URL`
(`http://minio:9000` for local MinIO, omit for AWS) plus `S3_ADDRESSING_STYLE=path`
for MinIO. Adding GCS / Azure later is a single new file implementing the same
`StorageBackend` Protocol — no factory, env, or test changes beyond one entry.

## Database backend axis (Make var: `DATABASE_BACKEND`)

| Value      | Compose overlay                  | DSN shape                                    |
|------------|----------------------------------|----------------------------------------------|
| `sqlite`   | `docker-compose.sqlite.yml`      | `sqlite+aiosqlite:///...`                    |
| `postgres` | `docker-compose.postgres.yml`    | `postgresql+asyncpg://...`                   |

## Backup feature axis (Make var: `BACKUP_BACKEND`)

| Value   | Compose overlay              | Effect                                          |
|---------|------------------------------|-------------------------------------------------|
| `none`  | (no overlay)                 | Default. Backup feature inert.                  |
| `minio` | `docker-compose.minio.yml`   | Adds MinIO + bucket-init sidecar; backend wired |

## How the matrix combines

```bash
# Plain SQLite, no backup (default — fastest local dev)
make docker-up

# Postgres, no backup (testing the postgres data path)
DATABASE_BACKEND=postgres make docker-up

# Postgres + MinIO + scheduler enabled (full backup roundtrip locally)
make docker-up-postgres-minio

# Postgres + AWS S3 (real cloud backups; no MinIO)
DATABASE_BACKEND=postgres \
STORAGE_BACKEND=s3 STORAGE_BUCKET=<your-bucket> \
S3_REGION=<region> \
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
make docker-up

# End-to-end backup/restore integration test (boots stack, runs, tears down)
make test-backup-roundtrip
```

## Test matrix

The unit tests (`tests/unit/test_storage_contract.py`) parametrize the same
8-assertion contract across `memory` and `local` backends — both real
implementations of the protocol. The S3 backend honors the same contract; it's
exercised by the dockerized `test-backup-roundtrip` integration test against
MinIO. Adding a new backend means adding ONE line to the parametrize map.

## Configuration knobs

| Env var                    | Default      | Notes                                              |
|----------------------------|--------------|----------------------------------------------------|
| `STORAGE_BACKEND`          | (unset)      | `s3` / `local` / `memory` / `""` (disabled)        |
| `STORAGE_BUCKET`           | —            | Required when `STORAGE_BACKEND=s3`                 |
| `STORAGE_LOCAL_PATH`       | tempfile     | Optional path for `local`; falls back via mkdtemp  |
| `S3_ENDPOINT_URL`          | (AWS native) | Set for MinIO / S3-compatible non-AWS              |
| `S3_REGION`                | `us-east-1`  | MinIO ignores it; AWS requires it                  |
| `S3_ADDRESSING_STYLE`      | `auto`       | `path` for MinIO; `auto` works for AWS             |
| `BACKUP_INTERVAL_SECONDS`  | `900`        | 15-minute periodic dump cadence                    |
| `BACKUP_KEY_PREFIX`        | `backups/`   | Object-key prefix; `latest.dump` is the cold-start pointer |
| `BACKUP_ENABLED`           | (auto)       | Force-disable with `0`/`false`/`no`/`off`          |
