# ADR-0005 — Multi-select is never used; composing options become permutations

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-23 |
| **Provenance** | `ADJ-04`, `ADJ-06` |
| **Relates to** | a specific case of ADR-0013 — a surface that cannot carry reasoning is not used |
| **Enforced in** | `SKILL.md` step 4.1 · § Never · `shapes/subset-as-permutations.md` · `harnesses/claude-code.md` |

> **Lens** — When an answer surface cannot carry per-option reasoning, change the *question shape*, not the
> requirement.

## Problem

### Symptom

Some decisions are genuinely "pick any of these that apply", which invites a checkbox list.

### Pain point

A checkbox list captures *which* options were chosen but not *why per option* — the user wanted to pick a subset and
give their reasoning for each part of it. Rehearsal also showed that offering blends alone loses the identity of the
atoms: the user could not tell what a combination was made of.

## Decision

### The lens

- **Given** — a decision whose options can legitimately be chosen together
- **We prefer** — two or three named combinations offered as exclusive options, preceded by a table of the atomic
  options, over a checkbox list
- **Because** — an exclusive choice carries one free-text annotation that covers the whole combination, and the atomic
  table keeps the members visible inside the blends
- **Unless** — never; this one is unconditional. `multiSelect` is not used even where a harness offers it.

### In practice

- The atomic options are listed in a table **before** the combinations.
- At most two or three combinations are offered; `other` covers the rest.
- Structured pickers are always called single-select.

## Consequences

### Pros

- The user's reasoning survives, because it attaches to one selected option.
- The atoms stay legible instead of disappearing into blend names.

### Cons

- Only a few of the possible subsets can be offered, so `other` carries more weight in this shape.
