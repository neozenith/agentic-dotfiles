# ADR-0008 — Decision records are searched before any question is ranked

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-23 |
| **Provenance** | `ADJ-13` |
| **Relates to** | gives teeth to ADR-0007 check 3 |
| **Enforced in** | `SKILL.md` step 2 · §§ Decision records, Never · step 4.3 row 3 · check 3 · `question-template.md` |

> **Lens** — The first cost of a question is a search, not a sentence. If you cannot write the `Checked:`
> line, you are not ready to ask.

## Problem

### Symptom

`Already settled` was filled from whatever the agent happened to remember, and nothing in the loop forced it to state
*what it had checked*.

### Pain point

The user could not verify check 3 without redoing the search. A question whose answer was already recorded spends
attention re-making a decision that was already made.

## Decision

### The lens

- **Given** — an inventory of open ambiguities, and record surfaces that may already answer some of them
- **We prefer** — paying a search before ranking, over ranking from what the agent remembers
- **Because** — attention spent re-making a recorded decision is the most expensive failure this skill can produce
- **Unless** — never; this one is unconditional. When no record surface exists and no tool reaches one, the search
  still runs and `Checked:` reports that nothing bears on it.

### In practice

- Records are a **role** with four backends in order: the ADR surface and CLAUDE.md lenses; the plan's decisions and
  markers; memory and this skill's adjudications; tool-reachable knowledge bases.
- A recorded **decision** settles the item outright — apply it, cite the record, drop it from the queue.
- A recorded **lens** does not settle it; it feeds the pragmatic-default test in step 3.
- `Already settled` opens with `Checked: …`, naming the records that were searched.

## Consequences

### Pros

- Questions become fewer and later.
- Check 3 is verifiable from the question itself rather than trusted.
- "Nothing recorded bears on this" becomes a valid and required finding rather than silence.

### Cons

- Every question pays a search before its first sentence is written.
- The never-table grows a row that a reviewer has to police.
