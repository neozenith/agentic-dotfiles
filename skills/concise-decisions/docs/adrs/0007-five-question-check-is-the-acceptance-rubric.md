# ADR-0007 — The five-question check is the acceptance rubric

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-23 |
| **Provenance** | `ADJ-11` |
| **Relates to** | check 3 is given teeth by ADR-0008; check 4 by ADR-0013; check 2 by ADR-0019 |
| **Enforced in** | `SKILL.md` step 4.4 · step 4.5 |

> **Lens** — Grade a question cold, from the answer surface, with the five checks. Never grade it against how it reads
> with the full context already in mind.

## Problem

### Symptom

The user graded every rehearsal with the same five questions, and those five explained every verdict — pass
and fail — across two harnesses and five shapes.

### Pain point

Without a fixed rubric, question quality is the author's judgement, and the author is the one person who cannot judge
it: they have the context the reader lacks. A question that reads well to its writer is the default failure.

## Decision

### The lens

- **Given** — a question that has been composed and is about to be sent
- **We prefer** — grading it cold against five fixed checks, over the author's sense that it reads well
- **Because** — the author holds context the user does not, so only a cold reading from the answer surface predicts
  whether the user can act on it
- **Unless** — never; this one is unconditional. The rubric also grades proposed template changes and evals, not only
  live questions.

### In practice

- The five checks, in the user's own wording: informed decision? why this, why now? why do prior decisions not answer
  it, and were records checked? can I attach my reasoning? can I give a TBD answer?
- All five must be yes. A "no" means the question is fixed, not sent.
- The same five are the rubric for evals and for any future rehearsal sign-off.

## Consequences

### Pros

- Question quality is testable rather than felt.
- Every later ADR can point at the check it strengthens, which keeps the log coherent.

### Cons

- A composed question can fail the rubric late, after the work of composing it is already done.
