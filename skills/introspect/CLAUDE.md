# CLAUDE.md — maintaining the `introspect` skill

Guidance for an assistant editing files under `.claude/skills/introspect/`. Read the ADR log
below before changing behaviour — each ADR records *why* a decision was made and a **Lens**
for applying it to the next decision. The Lens is the point: when a new question comes up,
answer it through these lenses rather than re-deriving from scratch.

## The development contract

Two commands are the entire loop. Run from the repo root (never `cd` in):

```bash
make -C .claude/skills/introspect/scripts fix   # auto-format + lint-fix (MUTATES source)
make -C .claude/skills/introspect/scripts ci    # the gate: format, lint, mypy --strict, tests
```

`ci` must be 0-exit before handing work off. Use sub-targets (`lint`, `typecheck`, `test-cov`,
`smoke`) only to narrow a failure; the contract is `ci`. See `.claude/rules/claude_skills.md`
for the canonical convention and `.claude/rules/claude_skills_docs.md` for the docs contract.

## File map

| File | Role |
|------|------|
| `scripts/introspect_sessions.py` | The engine: JSONL → SQLite ingest + query CLI. Pure stdlib. Has its **own** copy of the pricing dict + `msg_kind` logic (cannot import the package). |
| `scripts/introspect_sessions.sh` | Thin `uv run` wrapper (skills can't invoke `uv` directly). |
| `scripts/introspect_duckdb.sh` | **Pure-bash** DuckDB fallback over raw JSONL. Depends only on `bash` + `duckdb` (ADR-009). |
| `scripts/test_introspect_sessions.py` | PEP-723 pytest entry point. |
| `scripts/conftest.py` | `importlib.reload` fixture so module-level lines count toward coverage. |
| `scripts/Makefile` | `fix` / `ci` and sub-targets. |
| `SKILL.md` | Agent operating manual (commands, message kinds, fallback cascade). |
| `README.md` | Human-facing explainer (data model, cost model, analytics). |
| `resources/*.md` | Lazy-loaded deep references (cache, kg, commands, use-cases, duckdb-fallback). |

## Architecture principles

- **The JSONL is the source of truth; the cache is derived state.** `~/.claude/projects/**/*.jsonl`
  is append-only and authoritative. `~/.claude/cache/introspect_sessions.db` can be deleted and
  rebuilt at any time. Never store anything in the cache you cannot regenerate from the JSONL.
- **Compute once at ingest, read with plain `SUM()`.** Cost, `msg_kind`, `is_response_head`,
  and the tokenometrics fields are denormalized onto rows at ingest so query paths carry no
  per-row CASE/joins. The price of this is migrations (ADR-003).
- **Two ingesters, one schema, proven identical.** This skill's standalone script and the
  dashboard package ingester share `SCHEMA_VERSION` and must produce byte-identical event rows
  (`tests/test_introspect_parity.py`).

## ADR log

### ADR-001 — JSONL is truth; the cache is a rebuildable index
**Status:** Accepted.
**Decision:** Treat the SQLite cache as pure derived state over the append-only JSONL logs.
Every query checks file mtime/size and incrementally re-ingests only what changed.
**Consequences:** The cache can always be nuked and rebuilt; reads are normally instant.
**Lens:** Before adding a column or table, ask "can this be recomputed from the JSONL?" If yes,
it's a cache concern (compute at ingest). If no, it doesn't belong in the cache at all.

### ADR-002 — Two ingesters in lockstep, guarded by a parity test
**Status:** Accepted.
**Context:** The dashboard (`src/claude_code_sessions/database/sqlite/`) and this skill both
ingest JSONL, but the skill is a standalone PEP-723 script and **cannot import the package**.
**Decision:** Keep byte-equivalent copies (pricing dict, `_base_message_kind`, call extraction)
in both, and assert equality in `tests/test_introspect_parity.py`.
**Lens:** Any change to ingest/classification/pricing must be applied to **both** copies in the
same change, and the parity test must stay green. Never fix one side only.

### ADR-003 — Schema migrations are DROP+recreate, gated on `SCHEMA_VERSION`
**Status:** Accepted.
**Context:** `CREATE TABLE IF NOT EXISTS` is a no-op on an existing table — new columns never
appear.
**Decision:** Bumping `SCHEMA_VERSION` triggers a DROP of the cache tables and a one-time full
reingest. `clear()` DROPs (not `DELETE FROM`).
**Lens:** Adding/renaming a column ⇒ bump `SCHEMA_VERSION` in the same change, or existing caches
silently serve stale schemas. Migration cost is acceptable because the cache is rebuildable (ADR-001).

### ADR-004 — Cost denormalized at ingest; pricing is a hardcoded family dict
**Status:** Accepted.
**Decision:** `token_rate`/`billable_tokens`/`total_cost_usd` are computed at ingest and stored.
`token_rate` is by model **family** (substring match: opus 15.0 / sonnet 3.0 / haiku 1.0 /
unknown 0.0), so new model versions price automatically.
**Lens:** A price change means editing the dict in **every** copy (package + script) **and**
bumping `SCHEMA_VERSION` so existing rows get re-costed. Family-substring keeps it version-proof —
don't special-case individual model ids.

### ADR-005 — The `is_response_head` invariant
**Status:** Accepted.
**Context:** One response (`requestId`) is logged as N content-block rows, each repeating the
same request-level usage — a naive `SUM` over-counts ~2–3×.
**Decision:** Mark exactly one head per `requestId`; zero the token/cost columns on non-heads.
**Lens:** Token/cost `SUM()`s are correct **without** a head filter. When *counting responses*
(not summing), filter `is_response_head = 1`. Levels (`context_*`) are NOT zeroed — they're true
of every block.

### ADR-006 — `msg_kind`: 9 kinds, `subagent-` prefixed in sidechains
**Status:** Accepted.
**Decision:** Classify every event into one of 9 kinds from `type` + `isMeta` + first
content-block type; prefix `subagent-` when the event is a sidechain or lives in a
subagent/agent_root file. Source of truth: `_base_message_kind()`.
**Lens:** `msg_kind='human'` is "string-content user event" — it still includes slash-command
and caveat wrappers. "What the user actually typed" is a *stricter* predicate; don't conflate them
(see ADR-009's `is_human_prompt`).

### ADR-007 — Zero-dependency stdlib engine; ML deps injected, never base
**Status:** Accepted.
**Decision:** `introspect_sessions.py` uses only Python 3.12+ stdlib (sqlite3, json, argparse,
subprocess). Knowledge-graph/embedding work injects HuggingFace deps at runtime via
`uv run --with`, never as base deps.
**Lens:** Keep the core import-light so `--help` and every read path are instant and portable.
Heavy/optional libraries are runtime-injected at the point of use, never module-top.

### ADR-008 — Fail loud; never graceful-degrade a requirement
**Status:** Accepted (global rule).
**Decision:** Missing dependency or unmet precondition halts with a clear, actionable error —
no silent fallback that returns partial/empty results dressed as success.
**Lens:** If a feature can't run, raise. The one *sanctioned* fallback is the **explicit,
user-invoked** DuckDB mode (ADR-009) — a deliberate choice, not an automatic try/except.

### ADR-009 — The pure-bash DuckDB fallback (`--duckdb`)
**Status:** Accepted (2026-06-02).
**Context (the motivator):** **Active development of a new cache feature — especially a
schema-changing one — forces a long full reingest (ADR-003) before the cache is usable again.**
While that work is mid-flight, the SQLite cache is broken/half-migrated, yet you still want a
*subset* of introspection (read prompts, grep content, sanity-check costs) **without** waiting on
a rebuild or a working Python/`uv` toolchain.
**Decision:** Provide `/introspect --duckdb <subcmd>` → `introspect_duckdb.sh`, a **pure-bash**
helper that queries the raw JSONL directly with the `duckdb` CLI. It is read-only (never writes
the cache), defines a DuckDB view `events` over the JSONL glob, and reproduces `msg_kind` /
`is_human_prompt` in SQL (parity-checked against the cache for every message-bearing kind).
**Consequences:** A 3-rung cascade — Python+cache → direct `sqlite3` → DuckDB-on-JSONL — where
each rung drops a dependency of the one above.
**Lens:** The fallback must **never depend on the toolchain it backstops**. Keep it `bash` +
`duckdb` only — *not* a Python/`uv` script, which would die in the exact scenarios it rescues.
New fallback features are read-only SQL over the `events` view; if something needs to write the
cache, it belongs in the primary engine, not here. Cost queries MUST dedup by `requestId` first
(no `is_response_head` in raw JSONL — ADR-005).

### ADR-010 — No numeric LLM-as-judge in the knowledge graph
**Status:** Accepted.
**Decision:** Entity/community labelling uses binary/pairwise LLM classification, never a 1–5
numeric rating. A numeric judge is pseudo-quantitative; only a binary call yields an honest
proportion.
**Lens:** When adding an LLM-scored field, make it a classification that aggregates to a real
proportion — don't introduce numeric rating scales.

## Extension checklist

Before you finish a change here:

- [ ] Ingest/classification/pricing change → mirrored in **both** copies, parity test green (ADR-002).
- [ ] New/renamed column → `SCHEMA_VERSION` bumped (ADR-003).
- [ ] New token/cost field → denormalized at ingest, respects the head invariant (ADR-004/005).
- [ ] New base runtime dependency → don't; inject via `uv run --with` instead (ADR-007).
- [ ] New `--duckdb` capability → read-only SQL over the `events` view, bash-only (ADR-009).
- [ ] `make … fix` run, then `make … ci` green.
- [ ] `SKILL.md` (agent), `README.md` (human), and this ADR log updated if behaviour changed.

## Known gotchas

- **`introspect_duckdb.sh` clause helpers must `return 0`.** Under `set -euo pipefail`, an
  optional-SQL-fragment helper used in command substitution inside an assignment
  (`where="…$(kind_clause)$(human_clause)"`) aborts the script if it ends on a false `[[ … ]]`
  test — and the failure depends on argument order (silent exit 1, no output). Use `if` blocks,
  not `&&` chains. (Discovered when `events -t tool_use` died but `--human` worked.)
- **The `other` `msg_kind` bucket differs between the cache and the DuckDB view** — system/progress
  rows (`attachment`, `mode`, `file-history-snapshot`, `queue-operation`, …) are enumerated
  differently. All *message-bearing* kinds match exactly. Don't chase that delta.
- **`raw_json` on `events` is intentionally empty** — reconstruct payloads from
  `source_files.filepath` at `line_number`.
- **Three copies of the pricing dict** (package, script, and the doc tables) — keep in sync.
