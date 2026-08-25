# ADR-0017 — The reply grammar is two prose lines, and a bare route name is a valid answer

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-24 |
| **Provenance** | user ruling, 2026-08-24 — the reply-grammar block |
| **Relates to** | binds the routes of ADR-0003; the canonical semantics ADR-0006 refers to |
| **Enforced in** | `question-template.md` footer · `tbd-routes.md` § Presenting the routes · `harnesses/*.md` |

> **Lens** — A reply grammar is instructions to a person, not a parser specification. Write the sentence
> they should follow, then accept every reasonable thing they type instead.

## Problem

### Symptom

The reply footer was a block of labelled forms — `A:`, `B:`, `C:`, `TBD:` — one line each, which reads as a syntax to
be obeyed.

### Pain point

It made a `TBD:` prefix look mandatory, so a user who simply typed `spike: the parser is the risk` appeared to be
answering wrongly. It also spent four lines of the answer surface restating what the options already said.

## Decision

### The lens

- **Given** — a text surface where the user types their answer freely
- **We prefer** — two prose lines inviting the answer, over a per-option reply-form block
- **Because** — the block implies a required syntax, while the prose says the same thing in less space and leaves the
  route names usable on their own
- **Unless** — never; this one is unconditional. Structured pickers bind their options to these same semantics rather
  than defining their own.

### In practice

- The footer is exactly: "Reply with A, B or C and your reasoning." / "Alternatively choose from
  `<explain|show|spike|defer|handoff|other|task>` and your reasoning to revise/iterate."
- A bare route name is a valid TBD answer. The `TBD:` prefix is accepted but never required.
- Replies are parsed leniently: `B`, `b:`, `B —`, "B because …" all read as B.
- A reply naming no option and no route is treated as `explain`, with the reply text as the unclear part.
- The route line is single-sourced in `tbd-routes.md`; the picker adapter maps onto it rather than restating it.

## Consequences

### Pros

- The answer surface is shorter, and the TBD routes stop looking like a fourth option with special syntax.
- Route names work identically whether typed bare or as an annotation on a picker option.

### Cons

- Lenient parsing has to be implemented by every adapter, and a genuinely ambiguous reply is silently read as
  `explain`.
