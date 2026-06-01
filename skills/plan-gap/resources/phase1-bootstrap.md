# Phase 1 — Bootstrap (full playbook)

The step-by-step detail for Phase 1, referenced from `SKILL.md` → Workflow → Phase 1. `SKILL.md` holds
the one-line summary of each step; this file holds the mechanics. Paths are relative to
`.claude/skills/plan-gap/`.

## Step 1a: Target setup

**Local markdown file (the index):**
1. If the index does not exist, create it with the index skeleton from `resources/spec-body.md`
   (placeholder title) and a companion `DISCOVERY.md` from the discovery template.
2. If the index exists, read it and every sibling `G*.md` / `*-T*.md` /
   `DISCOVERY.md`, and assess completeness across the set.

**GitHub issue:**
1. If creating a new issue (`owner/repo`), create it with the skeleton from
   `resources/spec-body.md` as the body via `gh issue create`.
2. If resuming an existing issue (`owner/repo#N`), read it via
   `gh issue view N --repo owner/repo --json number,title,body,state,labels,comments`
   and assess completeness of each section in the body.
3. In both cases, cache the issue body locally — see `resources/gh-issues.md` for the
   local cache pattern.

## Step 1b: Dual deep research

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

This research directly feeds the **Current State** section of `DISCOVERY.md`.

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

This research directly feeds the **Desired State** section of `DISCOVERY.md` and the **Gap
Analysis** in the index.

## Step 1c: Link verification

After Track B completes, verify **every external URL** cited in the research.
Read `resources/playwright-cli.md` for the full detection logic, command reference, and marker
definitions.

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

## Step 1d: Research synthesis

Combine the verified findings from both tracks across the file set:

1. Populate **Current State** in `DISCOVERY.md` from Track A findings (with codebase citations), drawn
   through **2–3 lenses** chosen from the menu in `resources/mermaidjs_diagrams.md` (component,
   data-flow, sequence, deployment, state, entity) — only the lenses that illuminate this initiative
2. Populate **Desired State** in `DISCOVERY.md` from Track B findings (with verified URLs), through the
   **same** lenses and **same node IDs**, so each pair reads as a before/after
3. Draft the initial **Gap Analysis** in the index from the delta between the two — identify the
   top-level `G<N>` gaps with titles, and create a stub `G<n>.md` for each (nav header — including the
   `Architecture: DISCOVERY.md#g<n>-increment` back-link — lead + `## Context`)
4. Seed the `## Gap Increments` stack in `DISCOVERY.md` — one diagram per gap under the exact heading
   `### G<n> increment`, each starting from the prior baseline and highlighting only what that gap
   changes (`G1` extends Current State, `G<n+1>` extends `G<n>`)
5. Populate the index **Overview** with the linked gap bullet list, the Dependencies diagram, and the
   one-line **Background** blockquote pointing to `DISCOVERY.md`
6. Add the index Mermaid diagrams: Gap Map + Dependencies (minimum one each)
7. In each gap file, seed any obvious `<!-- UNRESOLVED -->` ADR placeholders (with the Pros/Cons table
   form from `resources/spec-body.md`) for design decisions that surfaced but lack clear answers

## Step 1e: Per-gap deep research

Once the top-level gaps are identified, launch **N parallel subagents** (one per gap)
for a focused second pass. Each subagent receives a fresh context containing only:

- The gap title, the Current and Gap fields as drafted in Step 1d
- The specific area of the codebase or external landscape to investigate

Each per-gap subagent should:

- Perform deeper codebase exploration (`Explore` or `feature-dev:code-explorer`)
  targeting the specific files, functions, and data flows relevant to that single gap
- Identify concrete **Output(s)** — exact file paths to create or modify, with
  languages, line numbers, and function signatures, and the proof-of-execution artifact the gap will
  produce by running the real code path on real input (see `resources/spec-body.md` → Outputs)
- Draft **References** — code snippets, SQL patterns, algorithm pseudocode, or
  configuration templates that capture the intended implementation approach
- Surface any design decisions that need resolution as candidate ADR entries

The per-gap agents run in parallel. Their findings are incorporated into the respective
`G<n>.md` files — enriching the `## Outputs` table and the optional `## Key logic` snippet
(the gap-file analogues of Output(s) and References) beyond what the broad Phase 1b research could
provide.

## Step 1f: Quality and failure mode research

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

## Step 1g: Final assembly

Incorporate findings from Steps 1e and 1f:

1. Update each `G<n>.md` with an enriched `## Outputs` table, an optional `## Key logic`
   snippet, and any `<!-- UNRESOLVED -->` ADR placeholders
2. Populate the index **Success Measures** with the Project Quality Bar (from Subagent A) and draft
   domain-specific measures (one per gap minimum, each linking its gap file). Every domain-specific
   measure must be an **executable-evidence escalator** — a falsifiable check satisfied only by the
   gap's committed proof-of-execution Output (the artifact produced by running the real code path on
   real input), never by "a test exists" or "it ran" (`resources/escalators-not-stairs.md`). Ensure
   each gap's `## Outputs` names that proof-of-execution artifact.
3. Populate the index **Negative Measures** with Quality Bar Violations (from Subagent B) and draft
   domain-specific failures
4. Update the index Overview gap list and the Gaps table if any gaps were added, merged, or reordered
5. Summarize what is present and what remains ambiguous — transition to Phase 2
