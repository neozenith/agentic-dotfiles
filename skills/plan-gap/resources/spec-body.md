# Gap Analysis Spec Structure Specification

Single source of truth for the **structure** of a gap analysis spec — the tiers, their sections, and
the per-tier templates. For the **voice and format** rules that govern every chunk (front-loading,
no bold-pseudo-headings, container-by-shape, gap-scoped ADRs, …) read `resources/style.md` first;
this file assumes them.

A gap analysis spec is a **set of files** sharing a kebab-case stem (`<plan>`), not one monolithic
document. The split is driven by context economy — see the document-set table and rationale in
`resources/style.md`. The mapping to a GitHub-issue backend (one parent issue + per-gap sub-issues)
is in `resources/gh-issues.md`.

```
<plan>.md              index     — Execution Plan, Overview, Gap Analysis, Decisions, Measures
<plan>-G<n>.md         gap       — one per gap: Context, Outputs, Key logic?, ADRs, Tickets table
<plan>-G<n>-T<x.y>.md  ticket    — one per ticket: Done checkbox, contract, Test/Implements table
<plan>-DISCOVERY.md    discovery — Current State + Desired State (review only, not in the loop)
```

A small spec (1–2 gaps, no per-gap ADRs) MAY inline gap and ticket detail into the index. The moment
a gap grows its own ADRs, a key-logic snippet, or ≥3 tickets, split it into its own file.

---

## Tier 1 — Index (`<plan>.md`)

Genre: navigation + framing. The index holds the diagrams and the rolled-up tables; per-gap and
per-ticket detail are pointers to their files. Current State and Desired State are **not** in the
index — they live in the Discovery file (rule 12, context economy).

### Section order

```
# [Title]
<!-- VERIFICATION / WARNING comments, if any -->
<details> Table of Contents </details>        ← folded (rule 11)
## Execution Plan                              ← heading visible; body folded in <details>
## Overview
## Gap Analysis
  ### Gap Map            (MANDATORY diagram)
  ### Dependencies       (MANDATORY diagram)
  ### Gaps (detailed specs)                    ← table linking to each <plan>-G<n>.md
## Decisions (ADRs)                            ← roll-up table of every settled ADR
## Success Measures
  ### Project Quality Bar (CI Gates)
  ### Domain-Specific Measures
## Negative Measures
  ### Quality Bar Violations
  ### Domain-Specific Failures
```

### Execution Plan

The entry point for autonomous execution via `/loop`. Until Phase 4 runs it is a placeholder; after
Phase 4 it holds the runner prompt, a progress roll-up, and the done criteria. The whole body is
wrapped in `<details>` (the runner prompt is one expand away); only the `## Execution Plan` heading
stays visible.

#### Loop Runner Prompt

A self-contained prompt an agent in a fresh context can execute. It embeds the spec's own location so
the loop re-enters without external arguments. Substitute `<SPEC_PATH>` with the index file's path
(relative to the repo root), or `<owner/repo#N>` for a GitHub-issue spec.

````markdown
```
/loop Read the gap analysis spec index at <SPEC_PATH>.

1. Read `.claude/skills/plan-gap/resources/tdd/tdd.md` and apply its red-green-refactor workflow.
2. In the index Progress table, find the lowest-numbered "Next eligible" ticket whose `Depends on`
   are all `[x]`. Open that ticket file. If none is eligible, write "spec complete" and exit the loop.
3. RED — write the test named in the ticket's `Test` row. Run the suite. Confirm the new test fails.
4. GREEN — write the minimum code named in the ticket's `Implements` row. Run the suite. Confirm the
   new test passes and nothing regressed.
5. REFACTOR (optional) — apply the ticket's `Refactor` row while staying green; re-run after each step.
6. Mark the ticket file's `- [ ] **Done**` checkbox `[x]`.
7. Update the Progress table in the index (`[x]` done count, Next eligible, Blocked on).
8. Commit with message `T<n>.<m>: <ticket title>`.
9. Return — the loop fires again for the next eligible ticket.

If you hit an ambiguity the spec does not resolve, STOP the loop: add an `<!-- UNRESOLVED -->` ADR
placeholder under the relevant gap file, write a short status note on what blocked progress, and exit.
The user must re-enter Phase 2 refinement to resolve the ADR before the loop can resume.
```
````

For a GitHub-issue spec, replace the path with `<owner/repo#N>`, read the body via
`gh issue view N --repo owner/repo --json body`, and write back via `gh issue edit` (see
`resources/gh-issues.md`).

#### Progress

A roll-up table, one row per gap, gap and ticket IDs linked to their files:

```markdown
| Gap | Tickets total | `[x]` done | `[ ]` todo | Next eligible | Blocked on |
|-----|---------------|-----------|-----------|---------------|------------|
| [G1](./<plan>-G1.md) | 4 | 0 | 4 | [T1.1](./<plan>-G1-T1.1.md) | — |
| [G2](./<plan>-G2.md) | 3 | 0 | 3 | — | [T1.2](./<plan>-G1-T1.2.md) |
```

"Next eligible" is the lowest-numbered `[ ]` ticket whose `Depends on` are all `[x]`; "Blocked on"
lists the dependencies still `[ ]`. Record any **dropped** tickets here with their reason (they count
as `[x]`, no work owed — see the dropped-ticket convention in `resources/style.md`).

#### Done Criteria

The checklist the runner uses to detect "spec complete":

- [ ] Every ticket file is marked `[x]`
- [ ] Every Success Measure (Project Quality Bar + Domain-Specific) passes when executed
- [ ] No `<!-- UNRESOLVED -->` ADR markers remain in any gap file
- [ ] No `<!-- LINK_NOT_VERIFIED -->`, `<!-- ASSUMPTION -->`, or `<!-- PAYWALLED -->` markers
      requiring user resolution

### Overview

Front-loaded prose stating the initiative's scope and purpose, then:

- A **bullet list of gaps** — each `[G<n>: Title](./<plan>-G<n>.md)` linked, with a one-line outcome.
- The **Dependencies diagram** (the same `flowchart LR` as in Gap Analysis) embedded so readers see
  the implementation order before diving in.
- A one-line **Background** blockquote linking the Discovery file:
  `> **Background — Current vs Desired State:** … lives in [<plan>-DISCOVERY.md](./<plan>-DISCOVERY.md) — review context, not needed once the loop starts.`

### Gap Analysis

#### Gap Map (MANDATORY)

Fixed heading. A `flowchart TD` mapping Current-State items through each gap to its Desired-State
counterpart. Three subgraphs — Current, Gaps, Desired — with each current item flowing through a gap
node to its desired item. This diagram MAY run detail-density (caption it as such); gap-to-gap
ordering is left to the Dependencies diagram.

#### Dependencies (MANDATORY)

Fixed heading, immediately after the Gap Map. A `flowchart LR` of the ordering between gaps — solid
arrows for hard dependencies, dotted labeled arrows for validation/parity relationships. Follow it
with a one-line recommended implementation order.

#### Gaps (detailed specs)

A table pointing to each gap file — full Current/Gap/Outputs/References/ADRs/Tickets live there, not
inline:

```markdown
| Gap | Spec | Tickets | Summary |
|-----|------|:-------:|---------|
| G1 | [<short title>](./<plan>-G1.md) | 4 | <one-line outcome> |
```

### Decisions (ADRs)

A roll-up of every settled ADR across all gaps — a primary review lens. Columns **ADR, Decision,
Why**; one row per ADR; the ID links to its owning gap file. Full Decision/Why/Rejected text stays in
the gap file (rule 13).

```markdown
| ADR | Decision | Why |
|-----|----------|-----|
| [ADR1.1](./<plan>-G1.md) | <concise decision> | <one-line rationale> |
```

### Success Measures

Escalator criteria — each a mandatory, testable requirement, never a "nice to have". Two subsections:

- **Project Quality Bar (CI Gates)** — a table of the project's existing gates (command, threshold,
  applies-to), discovered by the Phase 1f quality subagent across `CLAUDE.md` / `AGENTS.md` /
  `.claude/rules/`, CI workflows, and project tooling. The project's own bar is the minimum.
- **Domain-Specific Measures** — one bullet per gap minimum, each linking the gap
  (`**[G1](./<plan>-G1.md):** …`) and stating a falsifiable check.

### Negative Measures

Expensive-stairs criteria — Type 2 failures where the system *looks* done but silently isn't. Two
subsections:

- **Quality Bar Violations** — failure modes that silently breach the project's own standards
  (forbidden anti-patterns, historical gotchas from agentic memory/rules).
- **Domain-Specific Failures** — initiative-specific false signals of success.

### Index skeleton

Use this as the initial index body when creating a new spec (gap and ticket files are generated later
from their templates; the Discovery file is created alongside this one):

```markdown
# [Title]

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->
<!--TOC-->
</details>

## Execution Plan

<details>
<summary><b>Loop runner, progress, done criteria</b> — execution detail for the <code>/loop</code> agent</summary>

### Loop Runner Prompt
<!-- TODO: Self-contained /loop prompt embedding <SPEC_PATH>. Pending Phase 4. -->

### Progress
<!-- TODO: Roll-up table — one row per gap. Pending Phase 4. -->

### Done Criteria
<!-- TODO: Checklist — all tickets [x], all Success Measures pass, no UNRESOLVED markers. Pending Phase 4. -->

</details>

## Overview

<!-- TODO: Scope + purpose; bullet list of linked gaps; Dependencies diagram; Background blockquote → DISCOVERY -->

## Gap Analysis

### Gap Map
<!-- TODO: flowchart TD — Current → Gaps → Desired subgraphs -->

### Dependencies
<!-- TODO: flowchart LR — gap ordering + recommended implementation order -->

### Gaps (detailed specs)
<!-- TODO: table linking each <plan>-G<n>.md -->

## Decisions (ADRs)
<!-- TODO: roll-up table (ADR, Decision, Why), one row per settled ADR, populated in Phase 2 -->

## Success Measures

### Project Quality Bar (CI Gates)
<!-- TODO: table of CI gates — command, threshold, applies-to -->

### Domain-Specific Measures
<!-- TODO: one falsifiable measure per gap minimum -->

## Negative Measures

### Quality Bar Violations
<!-- TODO: Type 2 failures against the project's own standards -->

### Domain-Specific Failures
<!-- TODO: initiative-specific false signals of success -->
```

---

## Tier 2 — Gap (`<plan>-G<n>.md`)

Genre: explanation (why) + reference (what) + pointer (tickets). Created as a stub in Phase 1
(title + lead + Context) and enriched through Phases 1e–4.

````markdown
# G<n>: <Title>

> - **Index:** [<plan>.md](./<plan>.md)
> - **Depends on:** [G..](./<plan>-G...md), … — or none
> - **Blocks:** [G..](./<plan>-G...md), … — or none
> - **Prev:** [G..](./<plan>-G...md)        ← omit on the first gap
> - **Next:** [G..](./<plan>-G...md)        ← omit on the last gap

<1–2 sentences: what closing this gap delivers — front-loaded.>

## Context
<Current state for this gap and the binding constraint, 1–3 sentences, semantic line breaks.>

## Outputs
| File | Change |
|------|--------|
| `path` (lang) | <what changes> |

## Key logic              ← optional; include only when a snippet de-risks the work
```python
…                         # function signatures, SQL, pseudocode, config — annotate non-obvious choices
```

## ADR<n>.<m>: <concise decision summary>    ← gap-scoped id, one heading per settled ADR
- **Decision:** <full sentence>.
- **Why:** <1–2 sentences>.
- **Rejected:** <option (reason); …>          ← only when options were weighed
- **Superseded:** <prior ADR withdrawn + why> ← only when a decision is reversed

## Tickets
Each ticket is a standalone TDD vertical slice (one test → one implementation); full outlines live in
the linked files.

| Ticket | Behavior | Depends on |
|--------|----------|------------|
| [T<n>.1](./<plan>-G<n>-T<n>.1.md) | <actor> <observable outcome> | — |
````

The **Output(s)** table answers "when complete I will have…": concrete artifacts (source files with
language, test files, config, schema/CLI changes), never vague "updated code". The optional
**Key logic** snippet is the early-review + few-shot-context lever — critical logic discovered in
research, so a fresh-context agent reproduces the intended approach instead of reinventing it.

### Unresolved ADRs (Phase 2)

Before a decision is settled it lives as an `<!-- UNRESOLVED -->` placeholder — the *only* place a
Pros/Cons table is allowed (rule 8). It makes the open question rankable across gaps:

```markdown
## ADR<n>.<m>: <Question title>
<!-- UNRESOLVED -->

| Option | Pros | Cons |
|--------|------|------|
| A | … | … |
| B | … | … |

- **Decision:** pending — see refinement question.
```

When resolved, delete the marker and the table, and rewrite the body as the bulleted Decision/Why/
Rejected form above. Add a row to the index **Decisions (ADRs)** roll-up.

---

## Tier 3 — Ticket (`<plan>-G<n>-T<x.y>.md`)

Genre: austere reference — one behavior, one test, the implementation target, the dependencies.
Generated in Phase 4, one file per TDD vertical slice.

```markdown
# T<x.y>: <actor> <observable outcome>

> - **Gap:** [G<n>: <title>](./<plan>-G<n>.md)
> - **Index:** [<plan>.md](./<plan>.md)
> - **Prev:** [T..](./<plan>-G<n>-T...md)   ← omit on the first ticket
> - **Next:** [T..](./<plan>-G<n>-T...md)   ← omit on the last ticket

- [ ] **Done**

<One sentence stating the precise, assertion-worthy contract — exact endpoint/args/return or the
concrete fact the test checks.> <_(tracer bullet)_ — only on T<n>.1>

| | |
|--|--|
| Test | `path::test_name` — <assertion against the public interface> |
| Implements | `file` <symbol>, `file` |
| Depends on | [T..](./<plan>-G<a>-T<a>.<b>.md), … — or — |
| Mocks | <only if not none — system boundaries per `resources/tdd/mocking.md`> |
| Refactor | <only if present — hints from `resources/tdd/refactoring.md`> |
```

Numbering: `<n>` matches the parent gap, `<x.y>` is `<n>.<m>` with `<m>` 1-based within the gap. The
first ticket per gap (`T<n>.1`) is the **tracer bullet** — the smallest end-to-end slice proving the
path through the public interface; mark it `_(tracer bullet)_`. Subsequent tickets layer on top.

Reject any ticket exhibiting these anti-patterns (see `resources/tdd/tdd.md`, `resources/tdd/tests.md`):

- **Horizontal slice** — one ticket bundling multiple tests, or tickets that write all tests before
  any implementation. Each ticket is one test → one impl.
- **Implementation-detail behavior** — "calls `X.process()`" rather than "produces Y output".
- **Internal mocking** — mocking your own modules; the test no longer proves the system works.
- **External-channel verification** — asserting via direct DB query, log scraping, or filesystem
  inspection rather than the public interface.
- **Speculative scope** — implementation beyond what the test requires.

---

## Tier 4 — Discovery (`<plan>-DISCOVERY.md`)

Review/background only — not loaded during the loop. Holds the before/after architecture that
motivates the gaps.

```markdown
# <Title> — Discovery (Current & Desired State)

> - **Index:** [<plan>.md](./<plan>.md)

Review/background context: the before/after architecture, not loaded during the implementation loop.

## Current State
<What exists today — file:line citations from Track A research.>

```mermaid
flowchart TD
    …            ← current architecture / data flow; problem nodes in the danger fill
```

## Desired State
<The target end state — informed by verified Track B research.>

```mermaid
flowchart TD
    …            ← target architecture; new/changed nodes in the good/process fills
```
```

Both diagrams are MANDATORY and must be visually distinguishable (Phase 3 cross-consistency check).
They obey the same mermaid gates as the index diagrams (`resources/style.md` → Diagrams).
