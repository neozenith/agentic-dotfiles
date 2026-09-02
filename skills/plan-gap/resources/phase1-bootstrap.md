# Phase 1 — Bootstrap (full playbook)

The step-by-step detail for Phase 1, referenced from `SKILL.md` → Workflow → Phase 1. `SKILL.md` holds
the one-line summary of each step; this file holds the mechanics. Paths are relative to
`.claude/skills/plan-gap/`.

The Current/Desired State research discipline — dual-track research, link verification, and
lens-diagram synthesis — is owned by the **vendored discovery skill** at `vendor/discovery/`; Step 1b
below is the overlay that binds it to this skill's documents. This file owns only the ends the
vendored skill leaves to its caller.

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

## Step 1b: Discovery research (vendored skill)

**Read `vendor/discovery/SKILL.md` now** and run its full workflow — dual parallel research tracks
(Track A: codebase → Current State; Track B: web/SOTA → Desired State), link verification at the
highest available tier, synthesis into paired lens diagrams, and its validation gate. The vendored
copy is the authority on that discipline (its `resources/**` load per its own instructions); this
overlay binds the ends it leaves to its caller:

- **Target document:** `<plan>/DISCOVERY.md`, created in Step 1a from `resources/spec-body.md` →
  Tier 4. It carries the index backlink and the `## Gap Increments` section — plan-gap concepts the
  vendored skill does not know. The vendored run populates only `## Current State` and
  `## Desired State` and preserves everything else, which is exactly its section-ownership contract.
  On the GitHub backend, operate against the local cache file and sync per `resources/gh-issues.md`.
- **Brief:** the user's initiative description and the codebase areas it names (Track A scope).
- **Additional gates:** the diagrams also obey `resources/style.md` → Diagrams and may derive their
  palette from `resources/color_theming.md` (this skill's deeper palette reference).
- **Feeds:** Track A findings (with `file:line` citations) → Current State; verified Track B
  findings → Desired State and the Step 1c gap synthesis. Verification markers (`PAYWALLED`,
  `LINK_NOT_VERIFIED`, `UNVERIFIED`) carry into the spec set — on the GitHub backend they survive
  as hidden HTML comments (`resources/gh-issues.md`).

The vendored skill's evidence contract governs the whole spec, not just `DISCOVERY.md`:
**hallucination is a critical failure** — every factual claim in any tier traces to a `file:line`
citation or a verified URL, or is removed or flagged for the user to confirm.

## Step 1c: Gap synthesis

From the delta between the populated Current State and Desired State:

1. Draft the initial **Gap Analysis** in the index — identify the top-level `G<N>` gaps with
   titles, and create a stub `G<n>.md` for each (nav header — including the
   `Architecture: DISCOVERY.md#g<n>-increment` back-link — lead + `## Context`)
2. Seed the `## Gap Increments` stack in `DISCOVERY.md` — one diagram per gap under the exact
   heading `### G<n> increment`, each starting from the prior baseline and highlighting only what
   that gap changes (`G1` extends Current State, `G<n+1>` extends `G<n>`). Reuse the Current-State
   node IDs so the stack reads as the system growing one gap at a time
   (`resources/mermaidjs-diagrams.md` → Increment Chain)
3. Populate the index **Overview** with the linked gap bullet list, the Dependencies diagram, and
   the one-line **Background** blockquote pointing to `DISCOVERY.md`
4. Add the index Mermaid diagrams: Gap Map + Dependencies (minimum one each)
5. In each gap file, seed any obvious `<!-- UNRESOLVED -->` ADR placeholders (with the Pros/Cons
   table form from `resources/spec-body.md`) for design decisions that surfaced but lack clear
   answers

## Step 1d: Per-gap deep research

Once the top-level gaps are identified, launch **N parallel subagents** (one per gap)
for a focused second pass. Each subagent receives a fresh context containing only:

- The gap title, the Current and Gap fields as drafted in Step 1c
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
(the gap-file analogues of Output(s) and References) beyond what the broad Step 1b research could
provide.

## Step 1e: Quality and failure mode research

Launch **two parallel subagents** to research the project's quality standards and
potential failure modes. These run concurrently with each other (and may overlap
with Step 1d if context allows).

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

## Step 1f: Final assembly

Incorporate findings from Steps 1d and 1e:

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
