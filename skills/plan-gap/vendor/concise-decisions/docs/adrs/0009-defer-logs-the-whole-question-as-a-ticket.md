# ADR-0009 — `defer`/`handoff` logs the entire question as a backlog ticket

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-23 |
| **Provenance** | user rulings, 2026-08-23 and 2026-08-24 — the spike/defer route definitions, and `task` from Wayfinder research |
| **Relates to** | extends ADR-0003, which made `defer` a partial decision |
| **Enforced in** | `tbd-routes.md` §§ Routes/Where the ticket goes · `SKILL.md` § After the answer 5 · `question-template.md` |

> **Lens** — A TBD route must leave behind everything the user needs to take its next step without the agent in the
> room. An artefact that is a pointer rather than content has thrown away the attention already spent.

## Problem

### Symptom

ADR-0003 made `defer` a partial decision that records a scope seam, but the seam was a one-line marker.

### Pain point

A one-line seam discards the briefing the user will need when the question returns — which is precisely the cost being
deferred. Deferring should postpone the decision, not destroy the work that made it answerable.

## Decision

### The lens

- **Given** — a question that is valid but not important right now
- **We prefer** — the entire briefing logged as a backlog ticket, over a one-line seam marker
- **Because** — the briefing is the cost being deferred; a pointer throws away the attention already spent on it
- **Unless** — the work cannot wait; then the recommendation continues as an explicitly provisional assumption, and
  the ticket is still written.

### In practice

- The ticket body is sections 1–8 of the question verbatim, plus a `Revisit when:` line.
- The backlog is an **issue-tracking role**: tracker MCP → `gh issue` → the plan's own backlog → a local markdown
  ticket as the universal floor. Announce which backend was used.
- The seam marker on the decision record cites the ticket.
- `spike` carries a proposed timebox and ends when the box ends, converged or not.
- Route order is fixed everywhere: `explain` → `show` → `spike` → `defer`/`handoff`, with `other` and `task`.

## Consequences

### Pros

- A deferred question is re-askable months later without reconstruction.
- The skill needs no specific tracker to exist.

### Cons

- The reply grammar line is long.
- Deferring costs a real write to a backlog rather than a comment.
