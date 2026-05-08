# Gap Analysis Document Body Specification

Single source of truth for the structure and content requirements of a gap analysis
document body. Applies identically whether the document is stored as a local markdown
file or as the body of a GitHub issue.

## Section Order

The document MUST contain exactly these seven sections in this order. When stored as a
GitHub issue, the issue title serves as the `# [Title]` — do not duplicate it in the
body.

```
# [Title]
## Execution Plan          ← populated in Phase 4 (TDD decomposition); placeholder before
## Overview
## Current State
## Desired State
## Gap Analysis
  ### Gap Map
  ### Dependencies
  ### G1: ...
    #### Tickets           ← populated in Phase 4; one row per TDD vertical slice
  ### G2: ...
    #### Tickets
## Success Measures
## Negative Measures
```

## Section Specifications

### Execution Plan

The first section in the body. It is the entry point for autonomous spec execution
via the `/loop` construct. Until Phase 4 (TDD Ticket Decomposition) runs, this section
is a placeholder — once Phase 4 completes it contains the runner prompt, a progress
roll-up, and explicit done criteria.

MUST include three subsections, in order:

#### Loop Runner Prompt

A self-contained prompt that an agent in a fresh context can execute. The prompt
embeds the spec's own location so the loop can re-enter without external arguments.

The exact prompt template (substitute `<SPEC_PATH>` with the document's path or
`<owner/repo#N>` with the issue reference):

````markdown
```
/loop Read the gap analysis spec at <SPEC_PATH>.

1. Read `resources/tdd/tdd.md` and apply its red-green-refactor workflow.
2. Find the next ticket whose status is `[ ]` and whose `Depends on` are all `[x]`.
   If none exists, write "spec complete" and exit the loop.
3. RED — write the test described in the ticket's `Test outline`. Run the test
   suite. Confirm the new test fails.
4. GREEN — write the minimum code described in `Implementation outline`. Run the
   test suite. Confirm the new test passes and no existing tests regressed.
5. REFACTOR (optional) — apply the ticket's `Refactor candidates` while staying
   green. Re-run the test suite after each refactor step.
6. Mark the ticket's status checkbox `[x]` in <SPEC_PATH>.
7. Update the Progress table in the Execution Plan section.
8. Commit the changes with message `T<N>.<M>: <ticket title>`.
9. Return — the loop will fire again for the next eligible ticket.

If you encounter an ambiguity that the spec does not resolve, STOP the loop:
add an `<!-- UNRESOLVED -->` ADR placeholder under the relevant `G<N>`,
write a short status note explaining what blocked progress, and exit.
The user must re-enter Phase 2 refinement to resolve the ADR before the
loop can resume.
```
````

When the document is a GitHub issue, replace the file path with `<owner/repo#N>`
and instruct the runner to read the body via `gh issue view N --repo owner/repo
--json body` and write back via `gh issue edit`.

#### Progress

A roll-up table of ticket status across all gaps. One row per gap. Columns:

| Gap | Tickets total | `[x]` done | `[ ]` todo | Next eligible | Blocked on |
|-----|---------------|-----------|-----------|---------------|------------|
| G1  | 4             | 0         | 4         | T1.1          | —          |
| G2  | 3             | 0         | 3         | —             | T1.2       |

The runner updates this table after every completed ticket. "Next eligible" is the
lowest-numbered `[ ]` ticket whose `Depends on` are all `[x]`. "Blocked on" lists
the dependencies still `[ ]`.

#### Done Criteria

A short checklist that the runner uses to detect "spec complete":

- [ ] Every ticket in every `G<N>` is marked `[x]`
- [ ] Every Success Measure (Project Quality Bar + Domain-Specific) passes when
      executed (commands listed in the Success Measures table)
- [ ] No `<!-- UNRESOLVED -->` ADR markers remain
- [ ] No `<!-- LINK_NOT_VERIFIED -->`, `<!-- ASSUMPTION -->`, or `<!-- PAYWALLED -->`
      markers requiring user resolution

When all four are true, the spec is complete. The runner emits "spec complete" and
exits.

### Overview

Brief description of the initiative, its scope, and why this gap analysis exists.

MUST include:
- A **bullet-point summary** of each identified gap (`G<N>: Title` — one line each)
  that serves as a navigable index into the Gap Analysis section.
- The **Dependencies diagram** (same `flowchart LR` from the Gap Analysis section)
  embedded directly, so readers see the implementation order before diving into details.

The gap list and dependency diagram are populated after Phase 1 research completes
and updated as gaps are added, merged, or reordered during Phase 2 refinement.

### Current State

What exists today. Describe the system, process, or situation as it is now.
MUST contain at least one Mermaid diagram visualizing the current architecture,
data flow, or relationships. Text alone is not sufficient.

### Desired State

What the target looks like when done. Describe the system, process, or situation
as it should be after the work is complete.
MUST contain at least one Mermaid diagram visualizing the target architecture,
data flow, or relationships. Text alone is not sufficient.

### Gap Analysis

The delta between Current State and Desired State. Each gap should be a concrete,
actionable item — not a vague aspiration.

#### Gap Map (MANDATORY)

Fixed heading. A `flowchart TD` Mermaid diagram mapping the Current State items
through each identified gap to the corresponding Desired State items. Three subgraphs:
Current (what exists), Gaps (what must change), Desired (what results). Each
current-state item connects through a gap node to its desired-state counterpart.

#### Dependencies (MANDATORY)

Fixed heading. Immediately follows the Gap Map. A `flowchart LR` Mermaid diagram
showing the dependency ordering between gaps — which gaps must be resolved before
others can begin. Use solid arrows for hard dependencies and dotted arrows (with
labels) for validation/feedback relationships. Include a recommended implementation
order below the diagram.

#### Per-Gap Detail

After the two mandatory diagrams, each gap gets its own `### G<N>: <Title>` subsection
with these fields:

- **Current:** What exists today for this specific area.
- **Gap:** What must change and why.
- **Output(s):** Tangible deliverables produced when this gap is closed. This section
  completes the sentence "When complete I will have..." List concrete artifacts: source
  files created or modified (specify language — C, Python, TypeScript, SQL, etc.), test
  files, configuration changes, documentation updates, new CLI commands, database
  schema changes, etc. Be specific about file types and locations, not vague ("updated
  code").
- **References** *(optional but strongly encouraged):* Exact code snippets of critical
  logic discovered during the research phase, or parametrised versions representing a
  pattern. This serves two purposes:
  1. **Early code review** — surfaces nuanced logic before full implementation, where
     the failure mode is ambiguity about how the logic should actually work.
  2. **Few-shot context for agentic execution** — when an agent picks up this plan in
     a clean context, these snippets act as concrete examples of the intended approach,
     preventing the agent from reinventing the logic differently.

  Include: function signatures, SQL queries, algorithm pseudocode, API call patterns,
  grammar definitions, or configuration templates. Annotate with comments explaining
  non-obvious choices.

- **Tickets** *(populated during Phase 4 TDD decomposition):* A nested
  `#### Tickets` subsection containing one entry per TDD vertical slice. Each
  ticket maps to a single red-green-refactor cycle from `resources/tdd/tdd.md`
  — one test verifying one user-observable behavior, plus the minimum code to
  pass it. Tickets are the unit of work the `/loop` runner consumes.

  Ticket format:
  ```markdown
  ##### T<N>.<M>: <Behavior phrased as "<actor> can <observable action>">

  - [ ] **Done**
  - **Cycle:** RED → GREEN → REFACTOR
  - **Behavior:** Single user-observable behavior this ticket verifies. No
    implementation details. Survives internal refactors.
  - **Test outline:**
    - File: `<path/to/test_file.ext>`
    - Name: `<test name matching the behavior>`
    - Asserts: <assertion against a public interface — no private methods,
      no call counts, no direct DB inspection>
  - **Implementation outline:**
    - File(s): `<path/to/source_file.ext>`
    - Minimum code to pass the test. No speculative scope.
  - **Mocks:** `none` | <list — only system boundaries per
    `resources/tdd/mocking.md`: external APIs, time/randomness, file
    system if unavoidable. Never internal collaborators.>
  - **Refactor candidates:** *(optional)* <hints from
    `resources/tdd/refactoring.md` — duplication to extract, shallow
    modules to deepen, etc.>
  - **Depends on:** `T<N>.<M-1>` | `T<other>.<M>` | `none`
  ```

  Ticket numbering: `T<N>.<M>` where `<N>` matches the parent gap and `<M>`
  is the 1-based ticket index within that gap. The first ticket per gap
  (`T<N>.1`) is the **tracer bullet** — the smallest end-to-end slice
  proving the path works through the public interface. Subsequent tickets
  layer behaviors on top.

  Anti-patterns (reject any ticket exhibiting these — see
  `resources/tdd/tdd.md` and `resources/tdd/tests.md`):
  - **Horizontal slice** — one ticket that bundles multiple tests OR multiple
    tickets that all write tests before any implementation. Each ticket is
    one test → one impl.
  - **Implementation-detail behavior** — "calls X.process()" rather than
    "produces Y output."
  - **Internal mocking** — mocking your own modules; the test no longer
    proves the system works.
  - **External-channel verification** — asserting via direct DB query,
    log scraping, or filesystem inspection rather than the public interface.
  - **Speculative scope** — implementation that goes beyond what the test
    requires.

- **Architecture Decision Records (ADRs)** *(populated during Phase 2 refinement):*
  Each gap may accumulate one or more `#### ADR: <Decision Title>` subsections that
  capture resolved design decisions and their rationale. ADRs serve three purposes:
  1. **Structured ambiguity tracking** — before a question is resolved, the ADR exists
     as an `<!-- UNRESOLVED -->` placeholder listing the question, options, and trade-offs.
     This makes remaining ambiguities per gap visible and rankable.
  2. **Cross-gap question optimization** — when selecting "the next most important
     question," the skill can scan all unresolved ADRs across all gaps and select the
     single question whose answer resolves the most ADRs simultaneously.
  3. **Decision provenance** — once resolved, the ADR records what was decided, why,
     and what alternatives were rejected. This prevents future agents from relitigating
     settled decisions.

  ADR format:
  ```markdown
  #### ADR: <Decision Title>
  <!-- UNRESOLVED -->   ← remove this marker once resolved

  | Option | Pros | Cons |
  |--------|------|------|
  | Option A | ... | ... |
  | Option B | ... | ... |

  **Decision:** [Option chosen, or "pending — see refinement question"]
  **Rationale:** [Why this option was selected]
  ```

### Success Measures

Escalator criteria. Each measure is a mandatory requirement that MUST be satisfied
for the work to be considered complete. These are not "nice to haves."

MUST include two subsections:

#### Project Quality Bar (CI Gates)

When the gap analysis targets a code project change, a dedicated research subagent
(see Phase 1, Step 1f in SKILL.md) scans the project for codified quality standards.
The sources it searches — in priority order:

1. **Agentic configuration** — `CLAUDE.md`, `AGENTS.md`, `.claude/rules/`, agentic
   memory files, and similar AI-assistant instruction files
2. **CI/CD pipelines** — GitHub Actions workflows, Makefiles, build scripts
3. **Project tooling** — `pyproject.toml` (ruff, mypy, pytest config),
   `biome.json`, `.eslintrc`, `tsconfig.json`, etc.
4. **README and contributing docs** — `README.md`, `CONTRIBUTING.md`, `docs/`

Present findings as a concrete table of CI gates: command, threshold, and which
deliverables each gate applies to. The project's own bar is the minimum — the gap
analysis may add domain-specific measures on top, but must never fall below what
the project already enforces.

#### Domain-Specific Measures

Measures specific to the initiative that go beyond the project's existing quality
bar. Every gap in the Gap Analysis section must have at least one corresponding
domain-specific measure.

### Negative Measures

Expensive-stairs criteria. Each negative measure describes a failure mode where the
system appears to work but silently fails to deliver the intended value. These are
the Type 2 failures — false signals of success.

MUST include two subsections:

#### Quality Bar Violations

Failure modes where deliverables appear to pass but silently violate the project's
own quality standards. A dedicated research subagent (see Phase 1, Step 1f in
SKILL.md) scans the same sources as the Success Measures subagent, but looks for:

- Common anti-patterns the project explicitly forbids (e.g., mocking, graceful
  degradation, specific import patterns)
- Historical "gotchas" recorded in agentic memory or rules files
- Conventions that are easy to accidentally violate when adding new code

#### Domain-Specific Failures

Type 2 failures specific to the initiative — scenarios where the system gives a
false signal of success while silently failing to deliver the intended value.

## Skeleton Template

Use this as the initial body when creating a new gap analysis document:

```markdown
## Execution Plan

<!-- TODO: Populated in Phase 4 (TDD Ticket Decomposition). Placeholder until then. -->

### Loop Runner Prompt

<!-- TODO: Self-contained /loop prompt embedding <SPEC_PATH>. Pending Phase 4. -->

### Progress

<!-- TODO: Roll-up table — one row per gap. Pending Phase 4. -->

### Done Criteria

<!-- TODO: Checklist — all tickets [x], all Success Measures pass, no UNRESOLVED markers. Pending Phase 4. -->

## Overview

<!-- TODO: Brief description of the initiative, scope, and purpose -->

**Gaps identified:**

<!-- TODO: Bullet-point list of G<N>: Title (one line each) -->

<!-- TODO: Dependencies flowchart LR (same diagram as in Gap Analysis) -->

## Current State

<!-- TODO: Description + at least one Mermaid diagram -->

## Desired State

<!-- TODO: Description + at least one Mermaid diagram -->

## Gap Analysis

### Gap Map

<!-- TODO: flowchart TD with Current → Gaps → Desired subgraphs -->

### Dependencies

<!-- TODO: flowchart LR showing gap dependency ordering -->

<!-- TODO: ### G1: Title — with Current, Gap, Output(s), References, Tickets, ADRs fields -->
<!--      Tickets subsection populated in Phase 4 (TDD decomposition).            -->
<!-- TODO: ### G2: Title, etc.                                                    -->

## Success Measures

### Project Quality Bar (CI Gates)

<!-- TODO: Table of CI gates — command, threshold, applies-to -->

### Domain-Specific Measures

<!-- TODO: Mandatory, testable requirements — every gap must have at least one -->

## Negative Measures

### Quality Bar Violations

<!-- TODO: Type 2 failures against the project's own quality standards -->

### Domain-Specific Failures

<!-- TODO: Type 2 failure modes — false signals of success -->
```
