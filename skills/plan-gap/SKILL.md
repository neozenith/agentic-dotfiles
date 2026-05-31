---
name: plan-gap
description: "Gap analysis planning mode. Iteratively refines a gap analysis spec — a tiered file set (index + per-gap + per-ticket + discovery files, or a GitHub issue with per-gap sub-issues) covering Execution Plan, Overview, Gap Analysis, Decisions (ADRs), Success Measures, and Negative Measures, with Current/Desired State held in a review-only Discovery file. Validates Mermaid diagrams and enforces requirement integrity through structured questioning."
argument-hint: "<path-to-plan.md | path/to/folder/ | owner/repo#N | owner/repo>"
user-invocable: true
---

# Gap Analysis Planning Mode

You are now in **planning mode**. Your sole purpose is to iteratively refine a gap analysis document at the target provided as an argument. The target may be a local markdown file or a GitHub issue.

## Target Document

The argument is a **file path**, a **directory path**, or a **GitHub issue reference**.

### Resolving the target

1. **Argument ends with `.md`** — treat it as the **index** file path; its stem (minus `.md`) is the
   `<plan>` stem the rest of the file set shares.
   - If the file exists, read it and the sibling `<plan>-G*.md` / `<plan>-*-T*.md` / `<plan>-DISCOVERY.md`
     files, and continue refining from the set's current state.
   - If the file does not exist, create it with the index skeleton from `resources/spec-body.md` and a
     companion `<plan>-DISCOVERY.md` from the discovery template. Gap and ticket files are added later
     (gap stubs in Phase 1e, ticket files in Phase 4).

2. **Argument is a directory** (no `.md` extension, or ends with `/`) — create a new
   markdown file inside that directory.
   - Ask the user to describe the initiative in one sentence.
   - Derive a filename from that description using `kebab-case`: strip filler words,
     lowercase, join with hyphens, append `.md`.
     Example: "Migrate auth service to OAuth2" → `migrate-auth-to-oauth2.md`
   - Confirm the proposed filename with the user before creating it.
   - If the directory does not exist, create it.

3. **Argument matches `owner/repo#N`** or is a **GitHub issue URL**
   (`https://github.com/owner/repo/issues/N`) — treat it as an existing GitHub issue.
   - Verify `gh` CLI is available and authenticated (see `resources/gh-cli.md`).
   - Read the issue via `gh issue view N --repo owner/repo --json number,title,body,state,labels,comments`.
   - Continue refining from the issue body's current state.
   - Read `resources/gh-issues.md` for the full mapping between document structure
     and issue body/comments.

4. **Argument matches `owner/repo`** (no `#N`) — create a **new GitHub issue**.
   - Verify `gh` CLI is available and authenticated (see `resources/gh-cli.md`).
   - Ask the user to describe the initiative in one sentence.
   - Derive an issue title: `"Gap Analysis: <description>"`.
   - Confirm the proposed title with the user before creating.
   - Create the issue with the skeleton from `resources/spec-body.md` as the body via `gh issue create`.
   - The issue title serves as the `# [Title]` heading — do not duplicate it in the body.

### GitHub issue backend notes

When the target is a GitHub issue, these rules apply throughout all phases:

- **Reads** use `gh issue view --json body` (not the Read tool).
- **Edits** use the read-modify-write pattern: read body → modify section → write
  entire body back via `gh issue edit --body`. The `--body` flag performs a **full
  replacement** — see `resources/gh-cli.md` for details.
- **Phase 2 questions** are posted as **issue comments** (append-only), not body edits.
  After incorporating an answer, update the body to reflect the new state.
- **Mermaid diagrams** render natively on GitHub — no mmdc validation is required for
  rendering correctness, but local mmdc validation is still recommended if available
  to catch syntax errors before pushing to the issue.
- **HTML comments** (`<!-- ... -->`) are preserved in the body but hidden in the
  rendered view — use them for markers (`ASSUMPTION`, `PAYWALLED`, `LINK_NOT_VERIFIED`).
- **Closing the issue** signals that the gap analysis is complete (Phase 3 passed).

## Document Structure

A gap analysis spec is a **tiered file set** sharing a kebab-case stem (`<plan>`), not a single
document. Read `resources/spec-body.md` (relative to this skill's directory) for the full structure —
the tiers, their sections, and the per-tier templates — and `resources/style.md` for the voice and
format rules (front-loading, no bold-pseudo-headings, container-by-shape, gap-scoped ADRs, context
economy) that govern every chunk. **Read both before authoring or editing any spec file.**

**Quick reference — the four tiers:**

| File | Tier | Holds | Loaded |
|------|------|-------|--------|
| `<plan>.md` | index | Execution Plan, Overview, Gap Analysis (Gap Map + Dependencies + Gaps table), Decisions (ADRs) roll-up, Success/Negative Measures | loop entry |
| `<plan>-G<n>.md` | gap | Context, Outputs, optional Key logic, gap-scoped ADRs, Tickets table | per-gap work |
| `<plan>-G<n>-T<x.y>.md` | ticket | Done checkbox, contract sentence, Test/Implements/Depends-on table | per-ticket work |
| `<plan>-DISCOVERY.md` | discovery | Current State + Desired State (each with a Mermaid diagram) | human review only |

The driving principle is **context economy**: the index + the one gap + the one ticket an agent is on
are its `/loop` working-set, so Current/Desired State and SOTA background move out to the Discovery
file, and the table of contents + Execution Plan body fold behind `<details>` (agents still read the
source; humans skim past). The `Tickets` table in each gap file is populated in Phase 4 as TDD
vertical slices, one ticket file per red-green-refactor cycle. A GitHub-issue spec maps the index to
the parent issue and each gap to a sub-issue — see `resources/gh-issues.md`.

## Workflow

### Phase 1: Bootstrap

#### Step 1a: Target setup

**Local markdown file (the index):**
1. If the index does not exist, create it with the index skeleton from `resources/spec-body.md`
   (placeholder title) and a companion `<plan>-DISCOVERY.md` from the discovery template.
2. If the index exists, read it and every sibling `<plan>-G*.md` / `<plan>-*-T*.md` /
   `<plan>-DISCOVERY.md`, and assess completeness across the set.

**GitHub issue:**
1. If creating a new issue (`owner/repo`), create it with the skeleton from
   `resources/spec-body.md` as the body via `gh issue create`.
2. If resuming an existing issue (`owner/repo#N`), read it via
   `gh issue view N --repo owner/repo --json number,title,body,state,labels,comments`
   and assess completeness of each section in the body.
3. In both cases, cache the issue body locally — see `resources/gh-issues.md` for the
   local cache pattern.

#### Step 1b: Dual deep research

After reading the user's initial brief, launch **two parallel research tracks** using
Agent subagents. These run concurrently to maximize throughput.

**Track A — Internal research (codebase exploration)**

Launch an `Explore` subagent (or `feature-dev:code-explorer`) to deeply analyze the
areas of the codebase specified in the user's brief. The agent should:

- Trace execution paths, map architecture layers, identify patterns and abstractions
- Document dependencies, data flows, and integration points
- Build a thorough picture of the current implementation state
- Note technical debt, limitations, and constraints in the existing code
- Report concrete file paths, function names, and line numbers — not summaries

This research directly feeds the **Current State** section of `<plan>-DISCOVERY.md`.

**Track B — External research (SOTA and prior art)**

Launch a `general-purpose` subagent to research the external landscape. The agent should:

- Search the web for state-of-the-art approaches relevant to the initiative
- Find documentation, blog posts, and tutorials for technologies being considered
- Identify open-source projects solving similar problems — note their approach,
  maturity, license, and community activity
- Look for research papers or conference talks on the topic
- Identify what has become a "solved problem" since the current implementation was
  built — easy wins the desired state could leverage
- Collect all URLs discovered during research for verification in Step 1c

The agent MUST record every URL it references along with a one-line summary of what
content it expects to find there. This list is the input for link verification.

This research directly feeds the **Desired State** section of `<plan>-DISCOVERY.md` and the **Gap
Analysis** in the index.

#### Step 1c: Link verification

After Track B completes, verify **every external URL** cited in the research.
Read `resources/playwright-cli.md` (relative to this skill's directory) for the full
detection logic, command reference, and marker definitions.

**Step 1: Detect available verification tooling**

```bash
which playwright-cli && playwright-cli --version
```

Select the highest-available tier for the entire verification batch:

| Priority | Tool | Capability |
|----------|------|------------|
| Tier 1 | `playwright-cli` (the `/playwright-cli` skill, NOT Playwright MCP) | Full browser — JS rendering, screenshots, interaction |
| Tier 2 | `WebFetch` tool | HTTP fetch — static content, no JS rendering |
| Tier 3 | *(none)* | Mark all external links `<!-- LINK_NOT_VERIFIED -->` |

**Step 2: Verify each URL using the selected tier**

For each URL, classify the outcome:

| Outcome | Action |
|---------|--------|
| Page loads, content matches assertion | Keep citation as-is |
| Dead link / 404 / 5xx | Remove citation, note it was unverifiable |
| Paywall / login wall | Keep citation, mark `<!-- PAYWALLED -->` |
| Content mismatch (page exists, wrong content) | Remove or correct the citation |
| JS-required page with Tier 2 only | Mark `<!-- UNVERIFIED: requires browser rendering -->` |

**Step 3: Add document-level warning if any links are unverified**

If operating at Tier 2 or Tier 3, or if any individual URL could not be confirmed,
add a warning comment at the top of the document:

```markdown
<!-- WARNING: N external link(s) could not be independently verified. Search for LINK_NOT_VERIFIED to review. -->
```

**Hallucination is a critical failure.** Every factual claim in the research must be
traceable to either:
- A specific location in the codebase (file:line), OR
- A verified external URL

Any finding that cannot be corroborated by one of these must be removed or flagged
with the appropriate marker (see `resources/playwright-cli.md`) for the user to confirm.

#### Step 1d: Research synthesis

Combine the verified findings from both tracks across the file set:

1. Populate **Current State** in `<plan>-DISCOVERY.md` from Track A findings (with codebase citations)
2. Populate **Desired State** in `<plan>-DISCOVERY.md` from Track B findings (with verified URLs)
3. Draft the initial **Gap Analysis** in the index from the delta between the two — identify the
   top-level `G<N>` gaps with titles, and create a stub `<plan>-G<n>.md` for each (nav header + lead +
   `## Context`)
4. Populate the index **Overview** with the linked gap bullet list, the Dependencies diagram, and the
   one-line **Background** blockquote pointing to `<plan>-DISCOVERY.md`
5. Add Mermaid diagrams: Current State + Desired State in the Discovery file, Gap Map + Dependencies in
   the index (minimum one each)
6. In each gap file, seed any obvious `<!-- UNRESOLVED -->` ADR placeholders (with the Pros/Cons table
   form from `resources/spec-body.md`) for design decisions that surfaced but lack clear answers

#### Step 1e: Per-gap deep research

Once the top-level gaps are identified, launch **N parallel subagents** (one per gap)
for a focused second pass. Each subagent receives a fresh context containing only:

- The gap title, the Current and Gap fields as drafted in Step 1d
- The specific area of the codebase or external landscape to investigate

Each per-gap subagent should:

- Perform deeper codebase exploration (`Explore` or `feature-dev:code-explorer`)
  targeting the specific files, functions, and data flows relevant to that single gap
- Identify concrete **Output(s)** — exact file paths to create or modify, with
  languages, line numbers, and function signatures
- Draft **References** — code snippets, SQL patterns, algorithm pseudocode, or
  configuration templates that capture the intended implementation approach
- Surface any design decisions that need resolution as candidate ADR entries

The per-gap agents run in parallel. Their findings are incorporated into the respective
`<plan>-G<n>.md` files — enriching the `## Outputs` table and the optional `## Key logic` snippet
(the gap-file analogues of Output(s) and References) beyond what the broad Phase 1b research could
provide.

#### Step 1f: Quality and failure mode research

Launch **two parallel subagents** to research the project's quality standards and
potential failure modes. These run concurrently with each other (and may overlap
with Step 1e if context allows).

**Subagent A — Quality standards (feeds Success Measures)**

Launch an `Explore` subagent to scan the project for codified quality standards.
Search locations in priority order:

1. Agentic configuration — `CLAUDE.md`, `AGENTS.md`, `.claude/rules/`, agentic
   memory files (`~/.claude/projects/*/memory/`)
2. CI/CD pipelines — GitHub Actions workflows (`.github/workflows/`), Makefiles,
   build scripts
3. Project tooling — `Makefile`, `package.json`, `pyproject.toml`, `biome.json`, `.eslintrc`, `tsconfig.json`,
   coverage configs, linter configs
4. README and contributing docs — `README.md`, `CONTRIBUTING.md`, `docs/`

The agent should return a concrete table of CI gates (command, threshold, enforcement
status) and a list of coding conventions that apply to the gap analysis deliverables.

**Subagent B — Failure modes (feeds Negative Measures)**

Launch an `Explore` subagent to proactively discover potential "gotchas" and failure
modes. Search locations:

1. Agentic memory — `~/.claude/projects/*/memory/` files, especially feedback-type
   memories recording past corrections and anti-patterns
2. Agentic rules — `.claude/rules/` directories for explicit prohibitions and
   conventions
3. Lessons learned — project memory entries, `CLAUDE.md` sections on known pitfalls
4. Test patterns — existing test suites for patterns the project enforces (e.g., no
   mocking, real database connections, specific assertion patterns)

The agent should return a list of project-specific failure modes that could apply to
the gap analysis deliverables — scenarios where code appears correct but violates a
project convention or repeats a known historical mistake.

#### Step 1g: Final assembly

Incorporate findings from Steps 1e and 1f:

1. Update each `<plan>-G<n>.md` with an enriched `## Outputs` table, an optional `## Key logic`
   snippet, and any `<!-- UNRESOLVED -->` ADR placeholders
2. Populate the index **Success Measures** with the Project Quality Bar (from Subagent A) and draft
   domain-specific measures (one per gap minimum, each linking its gap file)
3. Populate the index **Negative Measures** with Quality Bar Violations (from Subagent B) and draft
   domain-specific failures
4. Update the index Overview gap list and the Gaps table if any gaps were added, merged, or reordered
5. Summarize what is present and what remains ambiguous — transition to Phase 2

### Phase 2: Iterative Refinement Loop

Repeat the following cycle until the document is complete and unambiguous:

1. **Scan unresolved ADRs** — Collect all `<!-- UNRESOLVED -->` ADR entries across every
   `<plan>-G<n>.md` file. Each represents a concrete design decision that needs human input. Also
   identify any non-ADR ambiguities (missing details, implicit assumptions, unclear requirements) and
   create ADR placeholders for them in the relevant gap file.

2. **Rank by cross-gap impact** — From all unresolved ADRs, determine the single
   question whose answer would resolve the most ADRs simultaneously. Prefer questions
   that span multiple gaps — a single answer that resolves ADRs in G2, G5, and G6
   is better than three separate questions. This is the key mechanism for reducing
   total questions asked of the human.

3. **Ask one question** — Present the question to the user clearly. Explain:
   - Why this question matters
   - Which `G<N>` gaps and ADRs it affects (list them)
   - What other ambiguities would be resolved by the answer (cascade effect)
   - Also provide your own list of plausible researched recommendations (and reasoning) 
     for the user to allow easy confirmation for sensible suggestions.

4. **Incorporate the answer** — Update the file set with the new information:
   - Resolve the affected ADRs in their gap files: rewrite each from the `<!-- UNRESOLVED -->`
     Pros/Cons placeholder into the settled bulleted form (`ADR<n>.<m>:` heading + **Decision** /
     **Why** / optional **Rejected** / **Superseded**) per `resources/style.md` rule 8, and remove
     the marker
   - Add or update the corresponding row in the index **Decisions (ADRs)** roll-up table
   - Propagate cascading effects to the `## Outputs` / `## Key logic` of the gap files and to the
     index Success/Negative Measures in all affected gaps
   - Update the index Overview gap list and Gaps table if gaps were added, merged, or reordered

5. **Re-evaluate** — After updating, reassess remaining unresolved ADRs. If no
   `<!-- UNRESOLVED -->` markers remain and the document is internally consistent,
   exit the loop. Otherwise, return to step 1.

### Phase 3: Validation

After the refinement loop converges:

1. **Diagram validation** — `<plan>-DISCOVERY.md` MUST contain a Current State diagram and a Desired
   State diagram; the index MUST contain the Gap Map (`flowchart TD`) and Dependencies (`flowchart LR`)
   diagrams. If any is missing, that is a validation failure — add it before proceeding. Read
   `resources/mermaidjs_diagrams.md` (relative to this skill's directory) for rendering commands,
   complexity thresholds, and common pitfalls, and follow the palette/gate rules in
   `resources/style.md` (Diagrams). Render every file that carries a diagram with mmdc (both dark and
   light variants) and verify exit code 0. Diagrams must stay within medium-density thresholds
   (<=20 nodes, VCS <=40) unless a detailed subsystem view justifies high-density (the Gap Map is the
   common exception — caption it as detail-density).

2. **Requirement integrity** — Read `resources/escalators-not-stairs.md` (relative to
   this skill's directory) and apply its principles to audit the full document. Specifically:
   - Every **Success Measure** must be a mandatory, testable requirement — not a
     "nice to have," not a vague aspiration, not something that degrades gracefully.
   - Every **Negative Measure** must describe a concrete Type 2 failure — a scenario
     where the system gives a false signal of success while silently failing to
     deliver the intended value.
   - No requirement from the Gap Analysis should be silently downgraded in the
     Success Measures section.

3. **Cross-consistency** — Verify that:
   - Every gap has at least one corresponding Success Measure
   - Success Measures are falsifiable (can be objectively tested)
   - Negative Measures are the complement of Success Measures (what "looks done but isn't")
   - The Current State and Desired State diagrams in the Discovery file are visually distinguishable
   - Every cross-link resolves: each gap file's Depends-on/Blocks/Prev/Next, each ticket's Gap/Depends-on,
     and every index → gap → ticket link points at a file that exists (rule 13)
   - Every settled ADR appears both in its gap file and as a row in the index Decisions roll-up

### Phase 4: TDD Ticket Decomposition

After Phase 3 validation passes, decompose each `G<N>` into TDD vertical-slice tickets — **one ticket
file per slice** (`<plan>-G<n>-T<x.y>.md`) plus the gap file's `## Tickets` table — and write the
index Execution Plan that drives the spec to completion via `/loop`. The bundled TDD reference lives
in `resources/tdd/`; the ticket-file template and anti-pattern list are in `resources/spec-body.md`.

Read `resources/tdd/tdd.md` once before starting Phase 4. Pay particular
attention to the **horizontal-slice anti-pattern** — every ticket MUST be a single
vertical slice (one test → one minimum implementation), never "all tests first then
all implementation."

#### Step 4a: Per-gap behavior enumeration

For each `G<N>`, launch a focused subagent (parallel across gaps when N > 1). Each
subagent receives a fresh context containing only:

- The gap file's lead, `## Context`, `## Outputs`, optional `## Key logic`, and settled `ADR<n>.<m>`
  sections (`<plan>-G<n>.md`)
- Read access to `resources/tdd/` (tdd.md, tests.md, mocking.md,
  interface-design.md, deep-modules.md, refactoring.md) and `resources/style.md`

The subagent enumerates the user-observable behaviors the gap's Outputs must support. Each behavior:

- Is phrased declaratively as `<actor> <observable outcome>` (rule 7) — precondition detail belongs
  in the ticket's lead/contract sentence, not the title
- Is verifiable through a public interface — see `resources/tdd/interface-design.md`
- Is the smallest unit that delivers a falsifiable signal — one assertion per behavior
- Survives an internal refactor — see `resources/tdd/tests.md` for the
  good-vs-bad-test contrast

The subagent rejects any candidate behavior matching the anti-patterns in
`resources/tdd/tdd.md` and `resources/tdd/tests.md`:

- "Tests the shape of things" rather than user-facing behavior
- Asserts on call counts, call order, or private methods
- Verifies via direct DB inspection, log scraping, or filesystem reads instead of
  the public interface
- Mocks an internal collaborator the project owns (only system boundaries per
  `resources/tdd/mocking.md`)

#### Step 4b: Ticket structuring

For each behavior, write one **ticket file** `<plan>-G<n>-T<x.y>.md` using the ticket template in
`resources/spec-body.md`. Numbering: `<n>` matches the parent gap, `<x.y>` is `<n>.<m>` with `<m>`
1-based within that gap. The first ticket per gap (`T<n>.1`) is the **tracer bullet** — the smallest
end-to-end slice proving the path through the public interface; mark it `_(tracer bullet)_`.
Subsequent tickets layer behaviors on top.

Each ticket file holds, in the austere form (rules 3–5 — no `Cycle:` line, no `Mocks: none`, no
3-level nesting):

- A blockquote nav header (Gap, Index, optional Prev/Next)
- A status checkbox `- [ ] **Done**` the `/loop` runner toggles to `[x]`
- One lead sentence stating the precise, assertion-worthy contract (exact endpoint/args/return or the
  concrete fact the test checks)
- A two-column table: `Test` (`path::test_name` + assertion against a public interface), `Implements`
  (file(s) + symbol, minimum code only), `Depends on` (linked ticket files or `—`), `Mocks` (only
  when non-empty — system boundaries per `resources/tdd/mocking.md`), `Refactor` (only when present —
  hints from `resources/tdd/refactoring.md`)

Then add the ticket's row to the gap file's `## Tickets` table (ID link, behavior, Depends-on links).
Validate every ticket against the anti-pattern list in `resources/spec-body.md` before accepting it.
Any ticket exhibiting a horizontal slice (multiple tests bundled, or test-first without matching
implementation) is rejected and split into N separate tickets.

#### Step 4c: Dependency ordering

Cross-link tickets across gaps. A ticket in `G2` may depend on a ticket in `G1`
when it requires deliverables from `G1`. Capture dependencies in each ticket's
`Depends on` field.

The complete dependency DAG must be topologically sortable — no cycles. If a cycle
is detected:

1. Identify the smallest ticket in the cycle that can be split into a "minimal stub"
   plus a "full implementation" pair.
2. Replace the original with the two new tickets.
3. Re-check the DAG.

Confirm the DAG by walking it from the leaves (no incoming dependencies) to the
roots. The leaves are the candidates for `T<N>.1` tracer bullets.

#### Step 4d: Write the Execution Plan section

Populate the `## Execution Plan` section of the **index** (`<plan>.md`) — body wrapped in `<details>`,
heading visible — per the spec in `resources/spec-body.md`:

1. **Loop Runner Prompt** — substitute `<SPEC_PATH>` with the index file's path (relative to the repo
   root) or `<owner/repo#N>` for a GitHub issue. The prompt is self-contained — an agent in a fresh
   context invoked by `/loop` can execute it without external arguments, finding the next ticket via
   the index Progress table and opening its ticket file. Do not modify the prompt skeleton from
   `resources/spec-body.md`; only substitute the path.

2. **Progress** — emit one row per gap with the ticket counts, gap and ticket IDs linked to their
   files. Initial state is `0` done, all `[ ]` todo, "Next eligible" set to the lowest-numbered ticket
   with no unresolved dependencies, "Blocked on" lists outstanding dependencies.

3. **Done Criteria** — copy the four-item checklist verbatim from `resources/spec-body.md`. The
   `/loop` runner uses it to detect "spec complete."

#### Step 4e: Validation of the decomposition

After Steps 4a–4d, verify that:

- Every `G<N>` has at least one ticket file — no gap is left without execution material
- Every ticket file exists, opens with `- [ ] **Done**`, and has its Test, Implements, and Depends-on
  rows populated (Mocks and Refactor only when non-empty)
- Every ticket-file row in a gap's `## Tickets` table links a file that exists, and vice versa
- The dependency DAG is acyclic and topologically sortable
- The index Progress table totals match the per-gap ticket-file counts
- The Loop Runner Prompt's `<SPEC_PATH>` substitution is correct and points at the index file

The user can now invoke `/loop` with the runner prompt to drive the spec to
completion. Each iteration of the loop consumes one ticket via the
RED→GREEN→(REFACTOR) cycle from `resources/tdd/tdd.md` and updates the
Progress table. The loop exits when Done Criteria are satisfied or when an
`<!-- UNRESOLVED -->` ADR placeholder appears (returning control to Phase 2
refinement).

## Questioning Principles

- **One question at a time.** Never dump a list of questions. The user should focus
  on the single most impactful question.
- **Cascade awareness.** Before asking a question, consider whether the answer to a
  previous question has already resolved it.
- **Explain the "why."** Always explain why this question is the most important one
  right now and what it unblocks.
- **Converge, don't diverge.** Each iteration should reduce the total number of
  ambiguities, not increase them. If a question opens up new sub-questions, fold
  them into the ranking for next iteration — don't ask them all at once.
- **Know when to stop.** When no ambiguities remain that materially affect the plan's
  actionability, declare the document complete and move to validation.

## Output Conventions

- Every file you author or edit MUST obey `resources/style.md` (front-loading, no bold-pseudo-headings,
  container-by-shape, gap-scoped ADRs, semantic line breaks, no `·` delimiter, cross-link by ID). When
  in doubt about a chunk's shape, that file decides.
- After each iteration, show the user a brief status:
  - Which file(s) and section(s) were updated
  - How many ambiguities remain (rough count)
  - What the next most important question is (or "complete — moving to validation")
- When editing a **local file**, use the Edit tool to make precise changes rather than rewriting the
  whole file. A restyle never flips a `[ ]`↔`[x]` checkbox — done state is execution data, not style.
- When editing a **GitHub issue**, read the current body, modify the relevant section, and write the
  full body back via `gh issue edit --body`. Post refinement questions and status updates as issue
  comments. Per-gap sub-issues mirror the local gap files — see `resources/gh-issues.md`.
- Do not add content the user has not confirmed. If you need to make an assumption to fill a section,
  mark it explicitly with `<!-- ASSUMPTION: ... -->` and flag it as an ambiguity to resolve.

## Resources

This skill bundles the following reference documents in its `resources/` directory
(paths relative to `.claude/skills/plan-gap/`):

| File | Purpose |
|------|---------|
| `resources/spec-body.md` | Spec structure — the tiers, the index/gap/ticket/discovery templates, the Execution Plan + Done Criteria, and the index skeleton |
| `resources/style.md` | Authoring style contract — the voice/format rules every file obeys; read alongside `spec-body.md` before authoring or restyling |
| `resources/escalators-not-stairs.md` | Requirement integrity principles — read during Phase 3 validation |
| `resources/mermaidjs_diagrams.md` | Mermaid diagram reference — rendering, complexity thresholds, pitfalls |
| `resources/playwright-cli.md` | Link verification — detection, fallback chain, and unverified markers |
| `resources/gh-cli.md` | GitHub CLI reference — detection, authentication, issue CRUD commands |
| `resources/gh-issues.md` | GitHub issues backend — local cache, sync protocol, edit history lineage |
| `resources/tdd/tdd.md` | TDD workflow — red-green-refactor, vertical slicing, anti-patterns. Read at the start of Phase 4 |
| `resources/tdd/tests.md` | Good-vs-bad test examples — used in Phase 4 to reject implementation-detail behaviors |
| `resources/tdd/mocking.md` | When to mock — system-boundaries-only rule applied to ticket `Mocks` field |
| `resources/tdd/interface-design.md` | Testable interface design — accept dependencies, return results, small surface |
| `resources/tdd/deep-modules.md` | Deep module guidance — small interface, deep implementation |
| `resources/tdd/refactoring.md` | Refactor candidates — populates the optional ticket `Refactor candidates` field |
