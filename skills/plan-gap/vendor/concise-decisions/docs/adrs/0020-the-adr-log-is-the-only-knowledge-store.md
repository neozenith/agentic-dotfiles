# ADR-0020 — The ADR log is the only knowledge store; there is no adjudications ledger

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-25 · supersedes one clause of [ADR-0018](0018-runtime-authority-is-skill-md-and-resources.md) |
| **Provenance** | user ruling, 2026-08-25 — "I never wanted these adjudications to exist or to be retained in a provenance list" |
| **Relates to** | supersedes one clause each of ADR-0018 (the carve-out) and ADR-0008 (backend 3); both linked below |
| **Enforced in** | `SKILL.md` § Resources · § Decision records row 3 |

> **Lens** — One store, or none. A second place to write down what the skill has learned always looks cheaper than
> amending the first, and it is: that is why it fragments. Write the ruling where the rule lives, or do not write it.

## Problem

### Symptom

`resources/learned/adjudications.md` held twenty-two `ADJ-NN` rows quoting the user's rulings, each one already
promoted into an ADR that restated the same ruling in its `Problem` section and cited the id in `Provenance`. The
ledger was searched at runtime as decision-record backend 3 — the single exception ADR-0018 carved out of its own
rule. The repo-level rule that had justified the file (a `resources/learned/` feedback space) was removed by the user
as a misapplication of its intent.

### Pain point

Two records of the same rulings is one record too many, and the user's position was that the second was never wanted:
the rulings "were ALWAYS meant to be in an ADR or not at all". Fragmentation costs more than duplication. A reader
does not know which copy is current; a promotion has two places to go stale; and the carve-out taught that "the skill
learns from this" could mean appending to a file rather than changing the surface a run actually loads — which
changes nothing about the next run.

## Decision

### The lens

- **Given** — a skill whose decisions are already recorded as ADRs, each carrying the ruling that forced it
- **We prefer** — the ADR log as the sole store, with the user's own words written into the ADR's `Problem`, over any
  companion ledger, learning file, or evidence appendix that the ADRs point into
- **Because** — a second store duplicates what the first already holds, and the pointer between them is the thing
  that rots; provenance that must be chased into another file is not provenance, it is an indirection
- **Unless** — never; this one is unconditional. Evidence too raw or too bulky for an ADR is evidence that has not
  been decided on yet, and it belongs in the session transcript until it is.

### In practice

- `resources/learned/` does not exist and is not recreated. No runtime file, and no file under `resources/` at all,
  accumulates rulings.
- `Provenance` names the session, rehearsal, or research in **prose** — never an id into another file.
- A user override during a run goes straight to a new ADR in the same turn, quoting the user in `Problem`, **plus**
  the change to the surface named in `Enforced in`. There is no staging area between the ruling and the ADR.
- Decision-record backend 3, set by [ADR-0008](0008-check-decision-records-before-asking.md), loses its third clause:
  it is the user's prior feedback this session and persisted memory, and nothing of this skill's own. ADR-0008's rule
  that the search runs before ranking is untouched.
- `SKILL.md` and `resources/` are the only runtime authority, now with no exception.

## Consequences

### Pros

- One place to read, one place to amend, and no pointer between them to go stale.
- A ruling costs a real surface change, which is the only kind of change a later run can feel.

### Cons

- Recording an override is heavier: an ADR plus a surface edit, where an append used to do.
- Rulings not yet worth an ADR are held only in the session transcript, and a session that ends loses them.
