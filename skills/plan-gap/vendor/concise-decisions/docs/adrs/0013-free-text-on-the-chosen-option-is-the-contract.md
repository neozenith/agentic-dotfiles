# ADR-0013 — Free text on the chosen option is the contract, not a courtesy

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-24 |
| **Provenance** | user rehearsals, 2026-08-22 and 2026-08-23 — the radio-list and free-text cases |
| **Relates to** | makes check 4 of ADR-0007 binding; ADR-0005 is the multi-select case of it |
| **Enforced in** | `SKILL.md` § The requirement · step 4.3 row 9 · check 4 · § Never · `harnesses/*.md` |

> **Lens** — A surface that captures the choice but not the why is not an answer surface. If a harness cannot carry
> reasoning on the selected option, it is not an adapter for this skill.

## Problem

### Symptom

A single-select picker was used whose options carried no per-option free text. The tool's automatic "Other" escape
proved unreliable, so in the user's words they were "cornered into 3 bad choices".

### Pain point

The reasoning is the product. A captured "why" becomes the lens that lets later questions be answered without asking
at all — so a surface that drops it does not merely lose a nicety, it breaks the mechanism the whole loop runs on. The
user was explicit that "multichoice and multi-select without space for freetext is a failure", and equally explicit
about why the good case works: picking one option *and adding annotations* "IS THE POINT".

## Decision

### The lens

- **Given** — any harness surface used to capture a decision
- **We prefer** — a surface carrying free text on the selected option, over any surface that captures only the choice
- **Because** — the reasoning is what makes future questions unnecessary, and a choice without it is a decision the
  skill cannot reuse
- **Unless** — never; this one is unconditional. A surface that cannot carry reasoning is not degraded to, it is
  routed away from (ADR-0006).

### In practice

- Every option in a structured picker carries a `preview`, because the preview pane is what exposes the annotation
  channel.
- A harness whose selected option cannot carry free text routes to the session feed instead.
- An option selected with no annotation is the missing-why case, handled by ADR-0016 — never by asking again.
- The answer surface says what the reasoning becomes ("becomes `<DECISION-ID>`'s Why").

## Consequences

### Pros

- The lens is captured at the moment the decision is made, when the reasoning is cheapest to give.
- Adapter selection has an objective test rather than a preference.

### Cons

- Otherwise-usable harness surfaces are ruled out entirely on one missing capability.
