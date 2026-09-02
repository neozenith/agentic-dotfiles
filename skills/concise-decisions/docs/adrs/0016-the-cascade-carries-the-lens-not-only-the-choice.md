# ADR-0016 — The cascade carries the lens, not only the choice

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-24 |
| **Provenance** | user instruction, 2026-08-23 — extract the reasoning and apply it before the next question |
| **Relates to** | ADR-0012 makes room for the cascade; ADR-0011 fixes the grammar the lens is written in |
| **Enforced in** | `SKILL.md` step 5 · § After the answer 2–4 · § Never · `harnesses/*.md` |

> **Lens** — An answer resolves the question it was asked about; the reasoning behind it resolves questions nobody has
> asked yet. Cascading only the choice throws away most of what was just bought.

## Problem

### Symptom

After an answer, the choice was applied to the question that had been asked and to obviously-related items. The
reasoning was recorded and then left there.

### Pain point

The user's framing is that the agent should "extract your reasoning and apply it to all open questions before asking
the next question". A choice settles one item. A lens — *we value X over Y* — settles every open item where X and Y
compete, including items that look unrelated to the question that produced it. Leaving the lens unapplied means asking
questions whose answer was already given, which is the same failure ADR-0008 prevents from the record side.

## Decision

### The lens

- **Given** — an answer that carries both a choice and the user's reasoning
- **We prefer** — cascading the choice *and* the reasoning-as-lens across the whole queue, over cascading the choice
  alone
- **Because** — the lens generalises beyond the question that produced it, and applying it is free where asking is not
- **Unless** — never; this one is unconditional. When the reply carries no reasoning, the lens is inferred rather than
  skipped.

### In practice

- The choice is applied to every related ambiguity from the inventory; the lens is applied to any ambiguity it
  settles, related or not.
- The turn states which other ambiguities cascaded resolved, and whether each was resolved by the choice or by the
  lens alone.
- **Missing why:** if the reply names an option but no reasoning, do not ask again. Infer the lens from the briefing —
  the pros the user accepted, the cons they tolerated — state it in one line ("recording the why as: *X over Y because
  Z* — correct me if that is wrong"), and mark the record `<!-- LENS: unconfirmed -->` until confirmed. A statement in
  passing, never a second question.
- The decision and its reasoning are both recorded where decisions live for this work.

## Consequences

### Pros

- The queue shrinks faster than it is asked, because one lens can settle several items.
- Recorded lenses become the material ADR-0008's search finds on the next run.

### Cons

- An inferred lens can be wrong, and it is recorded before the user has confirmed it.
