---
name: plan-gap
description: "Gap analysis planning mode. Iteratively refines a gap analysis document (local markdown file or GitHub issue) with Overview, Current State, Desired State, Gap Analysis, Success Measures, and Negative Measures sections. Validates Mermaid diagrams and enforces requirement integrity through structured questioning."
argument-hint: "<path-to-plan.md | path/to/folder/ | owner/repo#N | owner/repo>"
user-invocable: true
---

# Gap Analysis Planning Mode

You are now in **planning mode**. Your sole purpose is to iteratively refine a gap analysis document at the target provided as an argument. The target may be a local markdown file or a GitHub issue.

## Target Document

The argument is a **file path**, a **directory path**, or a **GitHub issue reference**.

### Resolving the target

1. **Argument ends with `.md`** — treat it as a local file path.
   - If the file exists, read it and continue refining from its current state.
   - If the file does not exist, create it with the skeleton from `resources/spec-body.md`.

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

Read `resources/spec-body.md` (relative to this skill's directory) for the full
specification of the six mandatory sections, their content requirements, Mermaid
diagram obligations, per-gap detail fields, and the skeleton template.

**Quick reference — the six sections in order:**

1. **Overview** — initiative scope and purpose, bullet-point gap index, Dependencies
   diagram
2. **Current State** — what exists today (MUST include Mermaid diagram)
3. **Desired State** — target end state (MUST include Mermaid diagram)
4. **Gap Analysis** — delta with mandatory Gap Map (`flowchart TD`), Dependencies
   (`flowchart LR`), and per-gap `G<N>:` subsections (Current / Gap / Output(s) /
   References / ADRs)
5. **Success Measures** — Project Quality Bar (CI Gates) + Domain-Specific Measures
6. **Negative Measures** — Quality Bar Violations + Domain-Specific Failures

## Workflow

### Phase 1: Bootstrap

#### Step 1a: Target setup

**Local markdown file:**
1. If the file does not exist, create it with the skeleton from `resources/spec-body.md`
   and a placeholder title.
2. If the file exists, read it and assess completeness of each section.

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

This research directly feeds the **Current State** section.

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

This research directly feeds the **Desired State** and **Gap Analysis** sections.

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

Combine the verified findings from both tracks into the document:

1. Populate **Current State** from Track A findings (with codebase citations)
2. Populate **Desired State** from Track B findings (with verified URLs)
3. Draft initial **Gap Analysis** from the delta between the two — identify the
   top-level `G<N>` gaps with titles
4. Populate the **Overview** with a bullet-point gap index and the Dependencies
   diagram (both are required per `resources/spec-body.md`)
5. Add Mermaid diagrams to Current State, Desired State, Gap Map, and Dependencies
   (minimum one each)
6. For each gap, seed any obvious `<!-- UNRESOLVED -->` ADR placeholders for design
   decisions that surfaced during research but lack clear answers

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

The per-gap agents run in parallel. Their findings are incorporated into the
respective `G<N>` subsections, enriching Output(s) and References beyond what the
broad Phase 1b research could provide.

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

1. Update each `G<N>` with enriched Output(s), References, and ADR placeholders
2. Populate **Success Measures** with Project Quality Bar (from Subagent A) and
   draft domain-specific measures (one per gap minimum)
3. Populate **Negative Measures** with Quality Bar Violations (from Subagent B) and
   draft domain-specific failures
4. Update the Overview gap index if any gaps were added, merged, or reordered
5. Summarize what is present and what remains ambiguous — transition to Phase 2

### Phase 2: Iterative Refinement Loop

Repeat the following cycle until the document is complete and unambiguous:

1. **Scan unresolved ADRs** — Collect all `<!-- UNRESOLVED -->` ADR entries across
   every `G<N>` subsection. Each represents a concrete design decision that needs
   human input. Also identify any non-ADR ambiguities (missing details, implicit
   assumptions, unclear requirements) and create ADR placeholders for them in the
   relevant gap.

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

4. **Incorporate the answer** — Update the document with the new information:
   - Resolve the affected ADRs: fill in **Decision** and **Rationale**, remove the
     `<!-- UNRESOLVED -->` marker
   - Propagate cascading effects to Output(s), References, Success Measures, and
     Negative Measures in all affected gaps
   - Update the Overview gap index if gaps were added, merged, or reordered

5. **Re-evaluate** — After updating, reassess remaining unresolved ADRs. If no
   `<!-- UNRESOLVED -->` markers remain and the document is internally consistent,
   exit the loop. Otherwise, return to step 1.

### Phase 3: Validation

After the refinement loop converges:

1. **Diagram validation** — Each of Current State, Desired State, and Gap Analysis
   MUST contain at least one ` ```mermaid ` code fence. If any section has zero
   diagrams, this is a validation failure — add the missing diagram before proceeding.
   Read `resources/mermaidjs_diagrams.md` (relative to this skill's directory) for
   rendering commands, complexity thresholds, and common pitfalls. For every diagram
   present, render the target document with mmdc (both dark and light variants) and
   verify exit code 0. Diagrams must stay within medium-density thresholds (<=20 nodes,
   VCS <=40) unless a detailed subsystem view justifies high-density.

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
   - Every gap in Gap Analysis has at least one corresponding Success Measure
   - Success Measures are falsifiable (can be objectively tested)
   - Negative Measures are the complement of Success Measures (what "looks done but isn't")
   - Diagrams in Current State and Desired State are visually distinguishable

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

- After each iteration, show the user a brief status:
  - Which section(s) were updated
  - How many ambiguities remain (rough count)
  - What the next most important question is (or "complete — moving to validation")
- When editing a **local file**, use the Edit tool to make precise changes rather than
  rewriting the entire file.
- When editing a **GitHub issue**, read the current body, modify the relevant section,
  and write the full body back via `gh issue edit --body`. Post refinement questions
  and status updates as issue comments.
- Do not add content the user has not confirmed. If you need to make an assumption
  to fill a section, mark it explicitly with `<!-- ASSUMPTION: ... -->` and flag it
  as an ambiguity to resolve.

## Resources

This skill bundles the following reference documents in its `resources/` directory
(paths relative to `.claude/skills/plan-gap/`):

| File | Purpose |
|------|---------|
| `resources/spec-body.md` | Document body specification — six sections, per-gap fields, skeleton template |
| `resources/escalators-not-stairs.md` | Requirement integrity principles — read during Phase 3 validation |
| `resources/mermaidjs_diagrams.md` | Mermaid diagram reference — rendering, complexity thresholds, pitfalls |
| `resources/playwright-cli.md` | Link verification — detection, fallback chain, and unverified markers |
| `resources/gh-cli.md` | GitHub CLI reference — detection, authentication, issue CRUD commands |
| `resources/gh-issues.md` | GitHub issues backend — local cache, sync protocol, edit history lineage |
