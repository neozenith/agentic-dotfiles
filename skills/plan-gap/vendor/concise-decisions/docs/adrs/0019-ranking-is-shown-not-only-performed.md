# ADR-0019 — The ranking is shown, not only performed

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-24 |
| **Provenance** | the user's grading question, 2026-08-23 — “the next most impactful question” |
| **Relates to** | makes check 2 of ADR-0007 verifiable, as ADR-0008 does for check 3 |
| **Enforced in** | `SKILL.md` step 4.3 row 2 · check 2 · `question-template.md` § Why decide this now |

> **Lens** — Claiming a question is the most important one is not evidence. Name the questions it outranks and why,
> and the claim becomes checkable by the person paying for it.

## Problem

### Symptom

Step 2 of the loop ranked the open ambiguities by cross-cutting impact, and then the question said only that this one
mattered. The ranking happened privately and left no trace in the output.

### Pain point

The user's check is "why is it **the next most impactful question** worthy of my attention?" — and nothing in the
question let them answer it. They had to take the ranking on trust, which means an agent that ranked badly and an
agent that ranked well produced indistinguishable questions.

## Decision

### The lens

- **Given** — a question selected from a queue of open ambiguities by a private ranking
- **We prefer** — naming the queue and why this item outranks it, over asserting that this question matters
- **Because** — the user is the one spending the attention, so the ranking is theirs to check, and a wrong ranking is
  otherwise invisible
- **Unless** — never; this one is unconditional. When the queue holds one item, the row says so, which is itself the
  answer to "why this one".

### In practice

- The `Why decide this now` table carries a **`Why this one first`** row naming the other open questions still queued
  and why this answer resolves or narrows more of them than any of those would.
- The same table carries an **`Outside this decision`** row, so the user can see what is *not* being decided and stop
  reading for it.
- Check 2 asks both halves: why this question, and why now.

## Consequences

### Pros

- A bad ranking becomes visible to the user instead of silently costing them a turn.
- The user can redirect to a queued question they consider more urgent, using `other`.

### Cons

- Every question exposes the whole queue, which makes the remaining work look larger than the one question implies.
