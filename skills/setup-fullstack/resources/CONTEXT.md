# Context

Domain language used across this scaffold. Names defined here appear in code,
tests, and `CLAUDE.md`. Updating a name here means updating it everywhere it
appears.

## Code tiers

The backend distinguishes code by **who owns it**. The two tiers correspond to
real folders, and the tier determines where new code goes.

### User-contributed code

Where your fork's domain logic lives.

- **Home**: `backend/server/core/`.
- **Constraint**: NO FastAPI imports. Pure functions, deterministic,
  exhaustively unit-testable.
- **Tests**: `backend/tests/unit/`. The ≥90% coverage gate targets this surface.
- **Scaffold ships**: `core/echo()` as a placeholder — replace it with whatever
  your fork actually does (a billing engine, a quote calculator, an order intake
  module).
- **Naming**: name modules after the domain (`quote_calculator.py`,
  `order_intake.py`), not the technical role (`services/`, `handlers/`).

### Framework-managed code

Parts of the scaffold a fork generally inherits unchanged. Replace only when the
scaffold's defaults are wrong for your fork; if a change is repeated across
forks, fold it back into the scaffold itself.

- `backend/server/api/` — FastAPI wire layer (routes, schemas, app factory).
- `backend/server/storage/` — cloud-agnostic object-storage adapters behind the
  `StorageBackend` Protocol (`memory`, `local`, `s3`).
- `backend/server/storage/backup/` — Postgres backup + restore against a
  `StorageBackend`. Owns the periodic-dump scheduler and cold-start restore.
- `backend/server/db.py`, `models.py`, `config.py` — DB engine, SQLAlchemy
  `Base`, env-driven config.
- `frontend/` — Vite + React + TypeScript + Tailwind + shadcn + Biome scaffold.
  Replace `frontend/src/pages/*` with your fork's pages but keep the e2e harness
  shape.

Prefer adding a new seam over forking framework-managed code. Seams the scaffold
already exposes: the `StorageBackend` Protocol, the env-var-driven `client`
fixture, the FastAPI lifespan.

## Storage and backup

- **Storage backend** — concrete adapter satisfying the `StorageBackend`
  Protocol. The scaffold ships three: `InMemoryBackend` (tests + dev),
  `LocalStorage` (filesystem), `S3Backend` (works against AWS S3 and MinIO via
  `S3_ENDPOINT_URL`). Add a new backend by implementing the four-method
  Protocol: `put_object`, `get_object`, `head_object`, `list_objects`.
- **Backup archive** — the on-storage layout the backup feature uses. An
  archive consists of timestamped immutable dumps
  (`<prefix><yyyymmddThhmmssZ>.dump`) plus a single always-current pointer
  (`<prefix>latest.dump`). The pointer convention is owned by
  `backend/server/storage/backup/pointer.py`. No other module knows the
  pointer's filename — changing the scheme is a one-file edit.
- **Cold-start restore** — startup hook that pulls the latest dump and
  `pg_restore`s it iff the database is empty. Idempotent — second boot with data
  present skips the restore.
- **Periodic backup** — `BackupScheduler` runs `dump_database` on an
  `interval_seconds` cadence, plus one final dump on graceful shutdown.

## Configuration

The backup feature is opt-in via environment:

- `STORAGE_BACKEND` — `memory`, `local`, `s3`, or empty (feature disabled).
- `STORAGE_BUCKET` — required when `STORAGE_BACKEND=s3`.
- `S3_ENDPOINT_URL` — set for MinIO; omit for AWS.
- `BACKUP_INTERVAL_SECONDS` — periodic-dump cadence (default 300).
- `BACKUP_KEY_PREFIX` — archive prefix in the bucket (default `backups/`).
- `BACKUP_ENABLED=false` — overrides everything, disables the feature.
