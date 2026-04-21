# Learner State Schema

The coach writes a JSON file at `./.claude/coach/state/<slug>.json` to persist the learner's mental model across sessions. This document defines the schema and the update rules.

---

## File location

- **Default**: `./.claude/coach/state/<topic-slug>.json` relative to the current working directory.
- **Override**: if the env var `COACH_STATE_DIR` is set, resolve relative to that path instead.
- **Slug**: lowercase topic, filler words removed, hyphen-joined. E.g. `bayesian-knowledge-tracing`, `oauth-2-1-pkce-flow`.

Create the directory if missing. Never silently skip the state write; if the write fails, surface the error to the learner immediately (fail-loud).

---

## Schema (v1)

```json
{
  "schema_version": 1,
  "topic": "Bayesian Knowledge Tracing",
  "slug": "bayesian-knowledge-tracing",
  "created_at": "2026-04-21T14:03:00Z",
  "updated_at": "2026-04-21T14:47:00Z",
  "sources": [
    {
      "kind": "web",
      "url": "https://example.org/...",
      "title": "...",
      "trust": "high"
    }
  ],
  "summary_bullets": [
    "Bullet 1 text",
    "Bullet 2 text"
  ],
  "concepts": [
    {
      "id": "bkt-core-four-params",
      "label": "The four BKT parameters: p(L0), p(T), p(S), p(G)",
      "prerequisites": [],
      "mastery_tier": "partial",
      "attempts": 3,
      "correct": 2,
      "consecutive_fail_count": 0,
      "confidence_calibration": [
        { "confidence": 80, "correct": true,  "timestamp": "..." },
        { "confidence": 90, "correct": false, "timestamp": "..." },
        { "confidence": 60, "correct": true,  "timestamp": "..." }
      ],
      "noted_misconceptions": [
        "Treats p(T) as a fixed value per-student rather than per-skill"
      ],
      "last_seen_at": "2026-04-21T14:40:00Z",
      "last_question_type": "open"
    }
  ],
  "session_log": [
    {
      "started_at": "2026-04-21T14:03:00Z",
      "ended_at":   "2026-04-21T14:47:00Z",
      "concepts_touched": ["bkt-core-four-params", "bkt-vs-dkt"],
      "what_clicked":    "How slip and guess parameters separate ability from luck.",
      "still_fuzzy":     "When BKT is preferable to DKT in practice."
    }
  ]
}
```

---

## Field definitions

### Top-level

- **`schema_version`** — integer. Bump on breaking schema changes. Current: `1`.
- **`topic`** — human-readable topic as the learner wrote it.
- **`slug`** — canonical slug (matches filename).
- **`created_at` / `updated_at`** — ISO 8601 timestamps with timezone.
- **`sources`** — the grounded research sources surfaced in Phase 1. Kind is one of `web`, `arxiv`, `github`, `codebase`, `confluence`, `gdrive`. Trust is `high` / `medium` / `low` based on source authority.
- **`summary_bullets`** — the ≤5 bullets produced in Phase 2. Kept verbatim so resumes can cite them.

### Concepts

An **array** of concept objects. Order is insertion order; sorting is done at read-time when picking next concept.

- **`id`** — kebab-case stable identifier. Reused across sessions. Never rewrite an ID once assigned.
- **`label`** — human-readable description, one line.
- **`prerequisites`** — array of concept `id`s that must be mastered before this concept can be tested. Empty for foundation concepts. Populated incrementally as the research and quizzing reveal dependencies.
- **`mastery_tier`** — one of `unseen` / `introduced` / `partial` / `solid` / `transfer`. See tier rules below.
- **`attempts`** — total quiz attempts on this concept across all sessions.
- **`correct`** — count of attempts scored correct (for MCQ) or "strong across all four axes" (for open-ended; see `question-types.md`).
- **`consecutive_fail_count`** — reset on any success. Used to trigger the "tell after two failed generations" rule.
- **`confidence_calibration`** — rolling log (cap at last 20 entries). Confidence 0–100 before reveal, correctness after, timestamp.
- **`noted_misconceptions`** — free-text labels for misconceptions the learner has shown. Kept across sessions so the coach can re-probe them deliberately.
- **`last_seen_at`** — ISO timestamp of the most recent quiz on this concept. Drives spacing (Rule 2: prefer concepts with the oldest `last_seen_at`).
- **`last_question_type`** — `mcq` or `open`. Used to vary format across sessions (interleaving within a concept's history).

### Mastery tier rules

| Tier | Criterion |
|---|---|
| `unseen` | Concept defined but never quizzed. |
| `introduced` | At least one attempt, mixed success, `correct/attempts < 0.5`. |
| `partial` | `correct/attempts ≥ 0.5` and at least one correct in the last 3 attempts. |
| `solid` | Last 3 attempts all correct, with at least one at Bloom's-Apply level. |
| `transfer` | Last correct attempt was on a *novel application* / counter-example / mechanism prompt — i.e. the learner demonstrated transfer, not just recognition. |

When picking the next concept (Rule 9), skip `solid` and `transfer` unless the learner asks explicitly, and unless the concept's `last_seen_at` is older than 14 days (spacing re-check).

### Session log

One entry per session. Append-only, cap at last 20 entries. `what_clicked` / `still_fuzzy` are captured in the metacognitive wrap (`session-loop.md` § "Session close").

---

## Update rules

### When to write

Write the state file at these points, not on every turn:

1. **End of Phase 1** — after research, write the `sources`, `summary_bullets`, and seed the `concepts` array with `unseen` entries for each sub-concept surfaced by the research agents.
2. **End of each quiz turn** (after evaluation + feedback) — update the relevant concept entry's attempts/correct/consecutive_fail_count/calibration/last_seen_at/noted_misconceptions.
3. **End of session** (on stop signal) — append a `session_log` entry, update top-level `updated_at`.

### How to write

- Read the existing file, modify the object in memory, write the whole file back. Preserve JSON key order for diff-readability.
- Never truncate to save space; JSON is small.
- Use ISO 8601 timestamps with timezone offset.

### Never do

- Don't delete concept entries. If a concept was mis-identified, mark it with a `deprecated: true` field; do not remove history.
- Don't rewrite `id`s — references in other concepts' `prerequisites` would break.
- Don't store per-turn transcript text. The state file is a mental-model snapshot, not a chat log. If deeper traces are useful, that's a different feature.

---

## Seeding prerequisites

After Phase 1 research, the coach seeds the `concepts` array. At this point prerequisites are best-guess from the research — they will be refined as the learner's quiz performance reveals actual dependency structure.

Heuristic: if concept A's definition mentions concept B, add B as a prerequisite of A. If the learner later answers A correctly without demonstrating B, remove the prereq edge; if they repeatedly fail A while B is `unseen`, surface B as a prereq to test first.

This is a lightweight approximation of prerequisite discovery in ITS literature (arxiv 2402.01672). Do not over-engineer — the heuristic is enough for most topics.
