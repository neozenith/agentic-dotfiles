# ADR template: the preferred shape of one decision record

The format the librarian prefers for a single ADR, whichever layout the repo
uses. In a file-per-decision layout it is one file (`NNNN-short-name.md`); in a
single-file log (`ADRs.md`) it is one section, with the `#` heading demoted to
`##` and the sub-headings demoted to match.

Format is a **dialect line like any other** (SKILL.md, authority ladder). A repo
that has declared a different ADR shape in `docs/CONVENTIONS.md`, or that
consistently uses one across three or more records, keeps it: this template is
the rung-3 default for repos that have not chosen, and the recommendation when a
repo asks what good looks like. Never rewrite an accepted ADR to fit this shape.

## The template

```markdown
# ADR-NNNN — <the decision, as a short assertion>

| Field | Value |
|---|---|
| **Status** | Accepted · YYYY-MM-DD |
| **Provenance** | <the session, rehearsal, or research that forced it, named in prose, never an id into another file> |
| **Relates to** | <extends / supersedes / superseded by ADR-NNNN, or a one-clause relation, or `—`> |
| **Enforced in** | <the surfaces that must satisfy this decision, `·`-separated> |

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

- <operative clause the enforcing surfaces must implement>
- <operative clause>

## Consequences

### Pros

- <what is gained>

### Cons

- <what is paid>
```

## Why this shape

Four properties earn it the default slot, and an audit can check each one:

- **Headings index the hierarchy.** The record is readable out of order. A
  reader who wants only the rule stops at the Lens; a reader who wants the
  argument reads on. A flat bullet list forces linear reading.
- **The Lens is the reusable part, and it comes first.** An ADR's value on a
  later visit is the rule it hands you, not the history. Putting it above the
  argument means a decision can be applied without re-reading why it was made.
- **The lens has a `Given` and an `Unless`.** A preference with no stated
  context and no stated inversion is an assertion. `Given` says what made it
  right, `Unless` says what would make it wrong, so a later reader can tell
  whether it still applies.
- **Bolded keys are machine-extractable.** `Given` / `We prefer` / `Because` /
  `Unless` read like fields. A parser can lift or replace them, so the log is
  queryable rather than only readable.

## Filling rules

- **One rule per ADR.** If a record needs two Lenses, it is two ADRs. A grouped
  ADR cannot carry a coherent `Enforced in` row and cannot be indexed.
- **`Unless` is never blank.** When a preference is absolute, write "never; this
  one is unconditional" out loud: that is information the reader would otherwise
  have to infer.
- **`Enforced in` names surfaces, not conditions.** What a surface must *do*
  belongs in `In practice`. The row is an index into the thing being governed,
  not a specification of it.
- **`Provenance` is prose.** Name the session, rehearsal, or research that
  forced the decision. Never an id pointing into a companion ledger: the ADR is
  the whole record, and a second store of the same rulings fragments the log.
- **The record is immutable in substance.** Reformatting to a new template shape
  is not a change of mind. A change of mind is a new ADR that supersedes the old
  one, with links both ways. Adopting this template across an existing log is a
  reformat, and it is an APPLY operation, never a silent rewrite.

## What the librarian does with it

Placement and existence only, per the skill's own boundary (SKILL.md, "never
judge content"):

- **Audit** reports an ADR surface whose records carry no `Status`, no decision
  statement, or no reasoning as a **structural** finding, and names this
  template as the recommended shape. It never reports that the reasoning is
  *weak*, which is a content judgement.
- **Init** writes this template to the repo's ADR surface (as
  `<adr-dir>/TEMPLATE.md`, or an appendix in a single-file log) and records the
  choice as a Dialect line in `docs/CONVENTIONS.md`.
- **Apply** migrates existing records to this shape only on explicit user
  acceptance, preserving every id, anchor, and inbound `ADR-NNNN` citation.
