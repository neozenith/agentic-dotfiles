# ADR-0012 — One decision per turn; a wizard cannot cascade

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-24 |
| **Provenance** | `ADJ-01` |
| **Relates to** | ADR-0016 defines what the single answer is cascaded *with* |
| **Enforced in** | `SKILL.md` step 4 · step 4.5 · step 6 · § Never · `harnesses/claude-code.md` · `harnesses/session-feed.md` |

> **Lens** — Two questions asked together are worth less than the same two asked in sequence, because the first answer
> can no longer change the second question. Batching questions destroys information.

## Problem

### Symptom

Multi-question wizards were used to save the user's time — several structured questions presented in one turn.

### Pain point

In the user's words, this "SUCKS because it does not cascade information from one response into answering others and
should NEVER be used." Question 2 was composed before answer 1 existed, so it could not be narrowed, dropped, or
re-ranked by it — and answering a question that answer 1 had already settled is a pure tax.

## Decision

### The lens

- **Given** — two or more open ambiguities, and a harness able to ask several questions at once
- **We prefer** — one decision per turn, cascaded before the next is ranked, over a batch presented together
- **Because** — an answer changes which question should be asked next, and a batch is composed before any answer exists
- **Unless** — never; this one is unconditional. Even a single sub-choice rides inside its parent option rather than
  becoming a second question.

### In practice

- Exactly one question per turn, and nothing else in that turn.
- Structured pickers are called with a single question, never two to four.
- A binary's sub-choice folds into the reply footer ("picking B, also name `<x|y|z>`") rather than becoming a
  question of its own.
- After every answer the queue is re-ranked before anything else is asked — yesterday's #2 is rarely today's #1.

## Consequences

### Pros

- Every question is composed with all prior answers already applied.
- The queue usually shrinks faster than it is asked, because cascades resolve items outright.

### Cons

- More turns for the user, each one blocking, where a batch would have been one interruption.
