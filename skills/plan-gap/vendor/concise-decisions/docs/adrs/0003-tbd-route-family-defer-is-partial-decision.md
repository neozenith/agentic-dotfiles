# ADR-0003 — The escape hatch is a route family, and `defer` is a partial decision

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-23 |
| **Provenance** | user rehearsals, 2026-08-23 — the “answer that is not a decision” series |
| **Relates to** | extended by ADR-0009, which makes `defer` write a whole ticket |
| **Enforced in** | `SKILL.md` step 4.3 row 8 · check 5 · § After the answer 5 · § Never · `tbd-routes.md` · `harnesses/*.md` |

> **Lens** — A new kind of "I can't answer yet" joins the route table with a *what happens next* and a *decision
> status*. It never joins as a fourth ordinary option.

## Problem

### Symptom

Questions offered three options and an "other". The user was cornered: none of the three was right, and "other" meant
describing a different approach, which was not what they wanted to say either.

### Pain point

The true answer was "not yet" — and there was no way to give it without declining the tool call, which reads as the
user exiting rather than answering. Answering a question and making a decision are different acts, and only one of
them had a surface.

## Decision

### The lens

- **Given** — a question the user cannot answer as posed
- **We prefer** — one option that routes to a named family, over a single free-text "other"
- **Because** — "I need this explained", "show me", "measure it", and "not now" are different answers with different
  consequences, and flattening them into "other" loses which one was meant
- **Unless** — never; this one is unconditional. A harness that cannot present the routes on an option routes to the
  session feed, where they render as a table (ADR-0006).

### In practice

- The routes are `explain`, `show`, `spike`, `defer`/`handoff`, plus `other` and `task`.
- Every route carries a *what happens next* and a *decision status*; only `defer` is even partly a decision.
- `defer` records a scope seam, because choosing to defer is itself a decision about scope.
- The visible label is the word `TBD` or "Not a decision yet", never a bare letter.
- Planning skills that adopt this loop define what each route does to their own documents.

## Consequences

### Pros

- The user can answer without deciding, and without aborting.
- Each non-decision answer has a defined next step rather than an improvised one.

### Cons

- Every question carries a route table, which is a section that most answers will not use.
