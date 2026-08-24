# ADR-NNNN — <the decision, as a short assertion>

| Field | Value |
|---|---|
| **Status** | Accepted · YYYY-MM-DD |
| **Provenance** | <`ADJ-NN`, or the session, rehearsal, or research that forced it> |
| **Relates to** | <extends / supersedes / superseded by ADR-NNNN, or a one-clause relation, or `—`> |
| **Enforced in** | <runtime surfaces only, `·`-separated: `SKILL.md` step N, §§ Name · `resources/<file>`> |

> **Lens** — <the forward-looking rule, one or two sentences. Applied to the next decision of this kind instead of
> re-deriving the trade-off.>

## Problem

### Symptom

<What was observed, in one short paragraph. The behaviour, not the theory.>

### Pain point

<What it cost and why that cost matters, in one short paragraph.>

## Decision

### The lens

- **Given** — <the context P that holds today>
- **We prefer** — <X>, over <Y>
- **Because** — <why the preference follows from P>
- **Unless** — <P → Q: the condition that would invert the preference — or "never; this one is unconditional">

### In practice

- <operative clause the runtime surfaces must implement>
- <operative clause>

## Consequences

### Pros

- <what is gained>

### Cons

- <what is paid>

---

## Filling rules

- **One rule per ADR.** If a file needs two Lenses, it is two ADRs. A grouped ADR cannot carry a coherent
  `Enforced in` row and cannot be indexed.
- **`Unless` is never blank.** When a preference is absolute, write "never; this one is unconditional" out loud —
  that is information the reader would otherwise have to infer.
- **`Enforced in` names surfaces, not conditions.** What a surface must *do* belongs in `In practice`. The row is an
  index into the runtime, not a specification of it.
- **This file is not loaded at runtime.** `SKILL.md` and `resources/` are the only runtime authority (ADR-0018). When
  a runtime surface and an ADR disagree, the surface is wrong — fix the surface, never edit the record.
- **Prose folds at ≤120 characters.** Metadata table rows cannot fold; keep them under 140 by shortening the values.
- **Bolded keys are the structural index.** The `Given`/`We prefer`/`Because`/`Unless` bullets are meant to be
  machine-extractable — a markdown parser should be able to read or replace them like fields (ADR-0011).
- **Accepted ADRs are immutable in substance.** Reformatting to a new template shape is not a change of mind; a change
  of mind is a new ADR that supersedes the old one, with links both ways.
