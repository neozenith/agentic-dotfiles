# ADR-0011 — A lens is written `Given` / `We prefer` / `Because` / `Unless`

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-24 |
| **Provenance** | `ADJ-22` — the ADR-DECISION-GRAMMAR decision |
| **Relates to** | fills the `Decision` section defined by ADR-0010; replaces the loose phrasing in `SKILL.md` |
| **Enforced in** | `SKILL.md` § After the answer 3 · `resources/question-template.md` § Filling rules |

> **Lens** — A recorded preference states the context it holds in and the condition that would invert it. A lens
> without an `Unless` is an assertion, not a decision — and cannot be safely reused when the context moves.

## Problem

### Symptom

`SKILL.md` told the agent to record reasoning "as a lens (*we prefer X over Y because Z*)" — three clauses, freely
phrased, with no slot for context. The ADR log used a different, equally free phrasing in each file.

### Pain point

Two failures follow. A lens recorded absolutely gets reused after its context has moved, because nothing in it says
what it depended on. And a lens phrased as prose cannot be located mechanically — a later run has to read the whole
argument to find the preference it should be applying.

## Decision

### The lens

- **Given** — a decision whose reasoning will be reused by a later run, possibly in a different context
- **We prefer** — four named clauses with bolded keys, over a prose sentence or a Y-statement
- **Because** — bolded-key bullets read as Given/When/Then, and a markdown parser can extract or replace
  their values like fields in a YAML document, where prose is a wall of text with no structural index
- **Unless** — never; this one is unconditional. A grammar that applies to only some lenses cannot be parsed uniformly,
  which defeats its purpose.

### In practice

- `Given` states the context P that holds today, narrowly enough that a reader can tell when it stops holding.
- `We prefer` names X **and** the rejected Y. A preference with no named alternative is a restatement of the rule.
- `Because` explains why the preference follows from P, not why X is good in general.
- `Unless` states P → Q — the condition that inverts the preference — or says "never; this one is unconditional".
- The same four clauses are used when the skill records a user's reasoning at runtime, so the log and the loop speak
  one grammar.
- The Y-statement form (*in the context of … facing … we chose … over … to achieve … accepting …*) was
  considered and rejected: it has no inversion slot, and six blanks in one sentence are not filled honestly
  in practice.

## Consequences

### Pros

- A contextual lens ("X over Y today, Y over X once P becomes Q") is expressible in the same shape as an absolute one.
- The author must write "unconditional" out loud rather than leaving absoluteness implied.
- Lenses can be extracted, diffed, and reviewed as fields.

### Cons

- Four clauses where a sentence would do, on decisions that genuinely have no context dependence.
- `Given` can restate the `Problem` section if it is written loosely.
