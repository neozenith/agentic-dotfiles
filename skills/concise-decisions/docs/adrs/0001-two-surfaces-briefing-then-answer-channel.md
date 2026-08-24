# ADR-0001 — A question is two surfaces: a briefing, then one answer channel

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-23 |
| **Provenance** | `ADJ-02`, `ADJ-03`, `ADJ-05` |
| **Relates to** | ADR-0013 makes the free-text half of the answer surface mandatory |
| **Enforced in** | `SKILL.md` §§ The requirement, Never · step 4 · step 4.3 · step 4.5 · `question-template.md` · `harnesses/*.md` |

> **Lens** — When tempted to move information into the answer surface, ask whether it is *reasoning material* or *the
> choice*. Only the choice moves.

## Problem

### Symptom

Skill runs took one of two forms. Either the question was asked in prose, with no structured answer surface and a
full typed reply; or a picker was called with the reasoning crammed into option labels and preview panes, where it
truncated.

### Pain point

The user's requirement is to make an **informed decision** and **give their reasoning**. The prose form captured the
reasoning but made the choice hard to give; the picker form captured the choice and lost the reasoning. Each shape
dropped exactly one half of the requirement.

## Decision

### The lens

- **Given** — a harness that offers a structured answer surface alongside an ordinary message body
- **We prefer** — the full briefing in the body with exactly one answer surface after it, over reasoning packed into
  option labels and preview panes
- **Because** — an answer surface has a size budget and truncates, the body does not, and the reasoning is the product
- **Unless** — never; this one is unconditional. A harness with no structured surface still renders all nine sections
  and takes the answer as a typed reply (ADR-0006).

### In practice

- The body carries the nine-section briefing, in the fixed order of the
  [question template](../../resources/question-template.md).
- Exactly one answer surface follows, whose only job is to capture the choice and the reasoning.
- Section 9 is the only section a harness adapter may bind; adapters may not drop sections or shrink previews.
- Artifacts live in the body. A preview pane carries a card that points at them.
- Body first, then the answer surface, in the same turn, with nothing else in the turn.

## Consequences

### Pros

- No question is asked that the user cannot answer from the screen.
- Reasoning lands in decision records as lenses rather than being lost at the surface.

### Cons

- Messages are long, and a short decision still costs a full briefing.
