# Gap Analysis Spec Structure Specification

Single source of truth for the **structure** of a gap analysis spec — the tiers, their sections, and
the per-tier templates. For the **voice and format** rules that govern every chunk (front-loading,
no bold-pseudo-headings, container-by-shape, gap-scoped ADRs, …) read `resources/style.md` first;
this file assumes them.

A gap analysis spec is a **folder** (`<plan>/`, a kebab-case stem) of tiered files, not one monolithic
document — `README.md` is the index (the GitHub-repo convention) and the siblings strip the stem. The
split is driven by context economy — see the document-set table and rationale in `resources/style.md`.
The mapping to a GitHub-issue backend (one parent issue + per-gap sub-issues) is in
`resources/gh-issues.md`.

```
<plan>/
├── README.md          index     — Execution Plan, Overview, Gap Analysis, Decisions, Measures
├── G<n>.md            gap       — one per gap: Context, Outputs, Key logic?, ADRs, Tickets table
├── G<n>-T<x.y>.md     ticket    — one per ticket: Done checkbox, contract, Test/Implements table
└── DISCOVERY.md       discovery — Current + Desired State + per-gap increments (review only)
```

A small spec (1–2 gaps, no per-gap ADRs) MAY inline gap and ticket detail into the index. The moment
a gap grows its own ADRs, a key-logic snippet, or ≥3 tickets, split it into its own file.

---

## Tier 1 — Index (`README.md`)

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
  ### Gaps (detailed specs)                    ← table linking to each G<n>.md
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
4. GREEN — write the minimum *real* code named in the ticket's `Implements` row. Run the suite.
   Confirm the new test passes and nothing regressed. Do not stub, mock the deliverable, or
   re-implement the behavior to force a pass.
5. REFACTOR (optional) — apply the ticket's `Refactor` row while staying green; re-run after each step.
6. Mark the ticket file's `- [ ] **Done**` checkbox `[x]`.
7. Update the Progress table in the index (`[x]` done count, Next eligible, Blocked on).
8. Commit with message `T<n>.<m>: <ticket title>`.
9. Return — the loop fires again for the next eligible ticket.

If you hit an ambiguity the spec does not resolve, STOP the loop: add an `<!-- UNRESOLVED -->` ADR
placeholder under the relevant gap file, write a short status note on what blocked progress, and exit.
The user must re-enter Phase 2 refinement to resolve the ADR before the loop can resume.

If implementing the ticket honestly seems to require a stub, a mock of its own deliverable, or a
parallel re-implementation, do NOT reach for a Change Request first. Run a quick root-cause check
(`.claude/skills/plan-gap/resources/5ys.md`): ask "why can't this be real yet?" a few times. Most
blockers dissolve into real work — a missing fixture, an un-wired dependency, a step that belongs in an
earlier ticket — and the fix is to do that work, not to rescope. Only when the 5-Whys chain bottoms out
at a genuine plan defect (the gap as written cannot produce real evidence) do you STOP the loop: add a
`<!-- CHANGE-REQUEST -->` marker under the relevant gap file recording the root cause and what the
ticket needs to become real, and exit without marking the ticket `[x]`. The user re-enters Phase 2 to
rescope.
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
| [G1](./G1.md) | 4 | 0 | 4 | [T1.1](./G1-T1.1.md) | — |
| [G2](./G2.md) | 3 | 0 | 3 | — | [T1.2](./G1-T1.2.md) |
```

"Next eligible" is the lowest-numbered `[ ]` ticket whose `Depends on` are all `[x]`; "Blocked on"
lists the dependencies still `[ ]`. Record any **dropped** tickets here with their reason (they count
as `[x]`, no work owed — see the dropped-ticket convention in `resources/style.md`).

#### Done Criteria

The checklist the runner uses to detect "spec complete":

- [ ] Every ticket file is marked `[x]`
- [ ] Every Success Measure (Project Quality Bar + Domain-Specific) passes when executed
- [ ] **Executable evidence:** every gap's `## Outputs` includes a committed proof-of-execution
      artifact — produced by running the real code path on real input — and that run is genuine; no
      deliverable is satisfied by a stub, a mock of itself, or a parallel re-implementation
      (`resources/escalators-not-stairs.md`)
- [ ] No `<!-- UNRESOLVED -->` ADR or `<!-- CHANGE-REQUEST -->` markers remain in any gap file
- [ ] No `<!-- LINK_NOT_VERIFIED -->`, `<!-- ASSUMPTION -->`, or `<!-- PAYWALLED -->` markers
      requiring user resolution

### Overview

Front-loaded prose stating the initiative's scope and purpose, then:

- A **bullet list of gaps** — each `[G<n>: Title](./G<n>.md)` linked, with a one-line outcome.
- The **Dependencies diagram** (the same `flowchart LR` as in Gap Analysis) embedded so readers see
  the implementation order before diving in.
- A one-line **Background** blockquote linking the Discovery file:
  `> **Background — Current vs Desired State:** … lives in [DISCOVERY.md](./DISCOVERY.md) — review context, not needed once the loop starts.`

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
| G1 | [<short title>](./G1.md) | 4 | <one-line outcome> |
```

### Decisions (ADRs)

A roll-up of every settled ADR across all gaps — a primary review lens. Columns **ADR, Decision,
Why**; one row per ADR; the ID links to its owning gap file. Full Decision/Why/Rejected text stays in
the gap file (rule 13).

```markdown
| ADR | Decision | Why |
|-----|----------|-----|
| [ADR1.1](./G1.md) | <concise decision> | <one-line rationale> |
```

### Success Measures

Escalator criteria — each a mandatory, testable requirement, never a "nice to have". Two subsections:

- **Project Quality Bar (CI Gates)** — a table of the project's existing gates (command, threshold,
  applies-to), discovered by the Phase 1f quality subagent across `CLAUDE.md` / `AGENTS.md` /
  `.claude/rules/`, CI workflows, and project tooling. The project's own bar is the minimum.
- **Domain-Specific Measures** — one bullet per gap minimum, each linking the gap
  (`**[G1](./G1.md):** …`) and stating a falsifiable check.

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
<!-- TODO: Checklist — all tickets [x], all Success Measures pass, each gap's proof-of-execution Output committed, no UNRESOLVED/CHANGE-REQUEST markers. Pending Phase 4. -->

</details>

## Overview

<!-- TODO: Scope + purpose; bullet list of linked gaps; Dependencies diagram; Background blockquote → DISCOVERY -->

## Gap Analysis

### Gap Map
<!-- TODO: flowchart TD — Current → Gaps → Desired subgraphs -->

### Dependencies
<!-- TODO: flowchart LR — gap ordering + recommended implementation order -->

### Gaps (detailed specs)
<!-- TODO: table linking each G<n>.md -->

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

## Tier 2 — Gap (`G<n>.md`)

Genre: explanation (why) + reference (what) + pointer (tickets). Created as a stub in Phase 1
(title + lead + Context) and enriched through Phases 1e–4.

````markdown
# G<n>: <Title>

> - **Index:** [README.md](./README.md)
> - **Architecture:** [G<n> increment](./DISCOVERY.md#g<n>-increment)
> - **Depends on:** [G..](./G...md), … — or none
> - **Blocks:** [G..](./G...md), … — or none
> - **Prev:** [G..](./G...md)        ← omit on the first gap
> - **Next:** [G..](./G...md)        ← omit on the last gap

<1–2 sentences: what closing this gap delivers — front-loaded.>

## Context
<Current state for this gap and the binding constraint, 1–3 sentences, semantic line breaks.>

## Outputs
| File | Change |
|------|--------|
| `path` (lang) | <what changes> |
| `path` (proof-of-execution) | <the committed artifact produced by running the real code path on real input — the gap's evidence it works> |

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
| [T<n>.1](./G<n>-T<n>.1.md) | <actor> <observable outcome> | — |
````

The **Output(s)** table is the gap's evidence of done: it answers "if this job were truly complete,
these artifacts would exist." Each row is a concrete artifact (source file with language, test file,
config, schema/CLI change), never vague "updated code". At least one row MUST be a
**proof-of-execution** artifact — produced by running the real code path on real input (a committed
result file, a rendered output, a recorded real command + its output) — so a stubbed, self-mocked, or
parallel-re-implemented deliverable cannot pass as done (`resources/escalators-not-stairs.md`). The
optional **Key logic** snippet is the early-review + few-shot-context lever — critical logic discovered
in research, so a fresh-context agent reproduces the intended approach instead of reinventing it.

The **Architecture** nav link points at this gap's increment diagram in `DISCOVERY.md`
(`#g<n>-increment`) — the picture lives in Discovery (review-only), never inline in the gap, so the
loop working-set stays lean (rule 12). The anchor `#g<n>-increment` is GitHub's slug of the exact
`### G<n> increment` heading; keep that heading stable so the link does not rot.

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

## Tier 3 — Ticket (`G<n>-T<x.y>.md`)

Genre: austere reference — one behavior, one test, the implementation target, the dependencies.
Generated in Phase 4, one file per TDD vertical slice.

```markdown
# T<x.y>: <actor> <observable outcome>

> - **Gap:** [G<n>: <title>](./G<n>.md)
> - **Index:** [README.md](./README.md)
> - **Prev:** [T..](./G<n>-T...md)   ← omit on the first ticket
> - **Next:** [T..](./G<n>-T...md)   ← omit on the last ticket

- [ ] **Done**

<One sentence stating the precise, assertion-worthy contract — exact endpoint/args/return or the
concrete fact the test checks.> <_(tracer bullet)_ — only on T<n>.1>

| | |
|--|--|
| Test | `path::test_name` — <assertion against the public interface, on real input> |
| Implements | `file` <symbol>, `file` — real production code, never a stub |
| Depends on | [T..](./G<a>-T<a>.<b>.md), … — or — |
| Mocks | <only if not none — a *true external boundary you do not own* per `resources/tdd/mocking.md`; NEVER the gap's own deliverable> |
| Refactor | <only if present — hints from `resources/tdd/refactoring.md`> |
```

Numbering: `<n>` matches the parent gap, `<x.y>` is `<n>.<m>` with `<m>` 1-based within the gap. The
first ticket per gap (`T<n>.1`) is the **tracer bullet** — the smallest slice that threads the gap's
*highest-risk, load-bearing path* end-to-end through the real production interface (for a pipeline:
produce → consume → emit), runs the real deliverable seam on real input, and produces the gap's first
proof-of-execution Output. It is **never** the cheapest peripheral leaf and never proves a side path; mark
it `_(tracer bullet)_`. Subsequent tickets layer on top.

Reject any ticket exhibiting these anti-patterns (see `resources/tdd/tdd.md`, `resources/tdd/tests.md`,
`resources/escalators-not-stairs.md`):

- **Horizontal slice** — one ticket bundling multiple tests, or tickets that write all tests before
  any implementation. Each ticket is one test → one impl.
- **Implementation-detail behavior** — "calls `X.process()`" rather than "produces Y output".
- **Stubbed or self-mocked deliverable** — the behavior passes against a `NotImplementedError`, a
  hard-coded return, or a mock of the very seam the gap exists to build. Expensive stairs: reject.
- **Internal mocking** — mocking your own modules; the test no longer proves the system works. Mock
  only a true external boundary you do not own (`resources/tdd/mocking.md`).
- **Parallel re-implementation** — a new throwaway/script path that re-implements production logic
  instead of exercising the shipped code path.
- **External-channel verification** — asserting via direct DB query, log scraping, or filesystem
  inspection rather than the public interface.
- **Deferred real run** — the only real, on-real-input execution is pushed past the tracer to a
  later/optional ticket, so the gap could complete without ever running for real.
- **Speculative scope** — implementation beyond what the test requires.

---

## Tier 4 — Discovery (`DISCOVERY.md`)

Review/background only — not loaded during the loop. Holds the architecture that motivates the gaps,
shown through **multiple lenses** and a **per-gap increment stack**. Current State and Desired State
each pick **2–3 lenses** from the menu in `resources/mermaidjs_diagrams.md` (component, data-flow,
sequence, deployment, state, entity) — only the lenses that genuinely illuminate *this* initiative.
Use **consistent node IDs** across Current → Desired → every increment so the reader diffs visually.

The `## Gap Increments` section is the spine of the file: one diagram per gap, each starting from the
Current-State baseline and highlighting (process/good fills) only the nodes that gap changes; `G<n+1>`
builds on `G<n>`'s diagram so the stack reads as the system growing one gap at a time. Each increment
sits under the exact heading `### G<n> increment` that the gap file links to (`DISCOVERY.md#g<n>-increment`).

````markdown
# <Title> — Discovery (Current, Desired & Increments)

> - **Index:** [README.md](./README.md)

Review/background context: the architecture that motivates the gaps, not loaded during the loop.

## Current State
<What exists today — file:line citations from Track A research.>

### Current State — <lens A, e.g. component structure>
```mermaid
flowchart TD
    …            ← components/modules as they are; problem nodes in the danger fill
```

### Current State — <lens B, e.g. data flow>
```mermaid
flowchart LR
    …            ← the same system through a second lens; reuse node IDs
```

## Desired State
<The target end state — informed by verified Track B research.>

### Desired State — <lens A>
```mermaid
flowchart TD
    …            ← target of lens A; new/changed nodes in the good/process fills
```

### Desired State — <lens B>
```mermaid
flowchart LR
    …            ← target of lens B; visually distinguishable from Current
```

## Gap Increments
One diagram per gap, in dependency order — each builds on the previous.

### G1 increment
**<what G1 changes>** — extends Current State.
```mermaid
flowchart TD
    …            ← Current-State baseline; G1's changed nodes in the process/good fill
```

### G2 increment
**<what G2 adds on top of G1>** — extends the G1 result.
```mermaid
flowchart TD
    …            ← G1's result as the new baseline; G2's changed nodes highlighted
```
````

Heading is **exactly** `### G<n> increment` (the descriptor goes on the line below, not in the heading)
so GitHub slugifies it deterministically to `#g<n>-increment` — the anchor the gap file's `Architecture`
nav link targets.

Current/Desired lenses (≥2 each) and one increment per gap are MANDATORY; the states must be visually
distinguishable and each increment distinct from the baseline it extends (Phase 3 checks). All diagrams
obey the same mermaid gates as the index diagrams (`resources/style.md` → Diagrams).
