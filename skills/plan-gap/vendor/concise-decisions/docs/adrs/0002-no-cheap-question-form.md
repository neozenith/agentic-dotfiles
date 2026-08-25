# ADR-0002 — There is no cheap question form

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-23 |
| **Provenance** | user rehearsal, 2026-08-23 — the low-stakes v1 question |
| **Relates to** | constrains every shape file; ADR-0004 stops a shape delta reintroducing a lite form |
| **Enforced in** | `SKILL.md` §§ Rules/Never/Pragmatic default · `question-template.md` · `shapes/low-stakes.md` |

> **Lens** — If a proposed variant removes a section, it is not a variant; it is a defect. Shrink content, never
> structure.

## Problem

### Symptom

A low-stakes rehearsal compressed the briefing and labelled its options by pointer — `Take C`, `Veto -> A`.

### Pain point

The user had no prior information about what those labels referred to and could not orient. What made the question
cheap to *write* was exactly what made it impossible to *answer*.

## Decision

### The lens

- **Given** — a decision is low-stakes and highly reversible
- **We prefer** — the full anatomy with previews shrunk to the value, over a compressed briefing
- **Because** — what makes a question cheap to *write* is exactly what makes it impossible to *answer* cold
- **Unless** — never; this one is unconditional. Removing a section is a defect at any stakes level.

### In practice

- Every question carries the full anatomy, however reversible the decision is.
- Previews shrink to the value itself — a path, a key name — for a rename-grade choice.
- The only genuinely cheaper path is the pragmatic default, and that is a statement in passing, not a question.

## Consequences

### Pros

- Low-stakes questions stay short but remain answerable cold.
- No skill can introduce a "lite" variant, so the anatomy cannot erode one shape file at a time.

### Cons

- Even a trivial decision costs a full briefing to ask, which raises the bar for asking at all.
