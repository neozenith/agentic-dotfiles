# ADR-0004 — Shapes and harnesses are separate lazy files

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-23 |
| **Provenance** | the skill docs contract (500-line cap, no duplication) and the request for one file per shape |
| **Relates to** | ADR-0002 — a shape delta may not remove a section |
| **Enforced in** | `SKILL.md` step 4.1 · step 4.2 · § Resources · `resources/shapes/*.md` · `resources/harnesses/*.md` |

> **Lens** — A rule that applies to every shape belongs in `SKILL.md` or the template; a rule that applies to one
> harness belongs in its adapter. A restatement is deleted, not tolerated.

## Problem

### Symptom

Five question shapes and three harness bindings all wanted space in one operating manual, against a 500-line file cap.

### Pain point

Shape and harness vary independently, so a combined manual makes every session read rules for four shapes it is not
using and two harnesses it is not in. Worse, base rules restated per shape drift out of agreement, and the drift is
invisible until a question is graded.

## Decision

### The lens

- **Given** — question shape and harness binding vary independently of each other
- **We prefer** — one file per shape and one per harness, loaded on demand, over a single manual covering the matrix
- **Because** — a session needs exactly one of each, and duplicated base rules drift apart silently
- **Unless** — never; this one is unconditional. A rule that genuinely spans shapes moves up into `SKILL.md` or the
  template rather than being copied down.

### In practice

- `resources/shapes/<shape>.md` — one loaded per question, chosen by the recognition signals in step 4.1.
- `resources/harnesses/<harness>.md` — one loaded per session, chosen by the environment markers in step 4.2.
- A shape file holds its anatomy deltas, one generic worked example, and its own checks — never a base rule.
- An adapter binds section 9 only; it may not drop sections, shrink previews, or rename routes.
- Adding either is one new file plus one routing row.

## Consequences

### Pros

- A session loads only what it needs, and the cap stays comfortable.
- Extending the skill is additive rather than a rewrite of the manual.

### Cons

- A reader wanting the whole picture opens several files.
- The routing tables are a surface that must stay in step with the directory.
