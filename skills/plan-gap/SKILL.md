---
name: plan-gap
description: "Gap analysis planning mode. Iteratively refines a markdown document with Overview, Current State, Desired State, Gap Analysis, Success Measures, and Negative Measures sections. Validates Mermaid diagrams and enforces requirement integrity through structured questioning."
argument-hint: "<path-to-plan.md | path/to/folder/>"
user-invocable: true
---

# Gap Analysis Planning Mode

You are now in **planning mode**. Your sole purpose is to iteratively refine a gap analysis document at the target file path provided as an argument.

## Target Document

The argument is either a **file path** or a **directory path**.

### Resolving the target

1. **Argument ends with `.md`** — treat it as a file path.
   - If the file exists, read it and continue refining from its current state.
   - If the file does not exist, create it with the skeleton below.

2. **Argument is a directory** (no `.md` extension, or ends with `/`) — create a new
   markdown file inside that directory.
   - Ask the user to describe the initiative in one sentence.
   - Derive a filename from that description using `kebab-case`: strip filler words,
     lowercase, join with hyphens, append `.md`.
     Example: "Migrate auth service to OAuth2" → `migrate-auth-to-oauth2.md`
   - Confirm the proposed filename with the user before creating it.
   - If the directory does not exist, create it.

## Document Structure

The plan document MUST contain exactly these six sections in this order:

```markdown
# [Title]

## Overview

Brief description of the initiative, its scope, and why this gap analysis exists.

## Current State

What exists today. Describe the system, process, or situation as it is now.
MUST contain at least one Mermaid diagram visualizing the current architecture,
data flow, or relationships. Text alone is not sufficient.

## Desired State

What the target looks like when done. Describe the system, process, or situation
as it should be after the work is complete.
MUST contain at least one Mermaid diagram visualizing the target architecture,
data flow, or relationships. Text alone is not sufficient.

## Gap Analysis

The delta between Current State and Desired State. Each gap should be a concrete,
actionable item — not a vague aspiration.
MUST contain at least one Mermaid diagram visualizing the transitions, migration
paths, or dependency graph between current and desired states.

## Success Measures

Escalator criteria. Each measure is a mandatory requirement that MUST be satisfied
for the work to be considered complete. These are not "nice to haves."

## Negative Measures

Expensive-stairs criteria. Each negative measure describes a failure mode where the
system appears to work but silently fails to deliver the intended value. These are
the Type 2 failures — false signals of success.
```

## Workflow

### Phase 1: Bootstrap

#### Step 1a: File setup

1. If the file does not exist, create it with the skeleton above and a placeholder title.
2. If the file exists, read it and assess completeness of each section.

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

After Track B completes, verify **every external URL** cited in the research using
the `/playwright-cli` skill (NOT Playwright MCP). For each URL:

1. `playwright-cli open` → `playwright-cli goto <url>`
2. Check the page loaded successfully:
   - **Dead link / 404 / 5xx** → remove the citation, note it was unverifiable
   - **Paywall / login wall** → keep the citation but mark it `<!-- PAYWALLED -->`
     and note that content could not be independently verified
   - **Content mismatch** — the page exists but does not contain the asserted content
     → remove or correct the citation
   - **Success** — page loads and content matches the assertion → keep the citation
3. `playwright-cli close` when done

**Hallucination is a critical failure.** Every factual claim in the research must be
traceable to either:
- A specific location in the codebase (file:line), OR
- A verified external URL

Any finding that cannot be corroborated by one of these must be removed or flagged
as `<!-- UNVERIFIED: ... -->` for the user to confirm.

#### Step 1d: Research synthesis

Combine the verified findings from both tracks into the document:

1. Populate **Current State** from Track A findings (with codebase citations)
2. Populate **Desired State** from Track B findings (with verified URLs)
3. Draft initial **Gap Analysis** from the delta between the two
4. Add Mermaid diagrams to all three sections (minimum one each)
5. Summarize what is present and what remains ambiguous — transition to Phase 2

### Phase 2: Iterative Refinement Loop

Repeat the following cycle until the document is complete and unambiguous:

1. **Evaluate ambiguities** — Review the entire document. Identify all open questions,
   unclear requirements, missing details, and implicit assumptions.

2. **Rank by impact** — From all identified ambiguities, determine the single most
   important question. This is the question whose answer will resolve the most
   uncertainty and likely cascade into answering other open questions.

3. **Ask one question** — Present the question to the user clearly. Explain:
   - Why this question matters
   - What sections it affects
   - What other ambiguities might be resolved by the answer

4. **Incorporate the answer** — Update the document with the new information.
   A single answer often resolves multiple ambiguities — propagate changes to all
   affected sections.

5. **Re-evaluate** — After updating, reassess remaining ambiguities. If the document
   is now complete and internally consistent, exit the loop. Otherwise, return to step 1.

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
- When editing the document, use the Edit tool to make precise changes rather than
  rewriting the entire file.
- Do not add content the user has not confirmed. If you need to make an assumption
  to fill a section, mark it explicitly with `<!-- ASSUMPTION: ... -->` and flag it
  as an ambiguity to resolve.

## Resources

This skill bundles the following reference documents in its `resources/` directory
(paths relative to `.claude/skills/plan-gap/`):

| File | Purpose |
|------|---------|
| `resources/escalators-not-stairs.md` | Requirement integrity principles — read during Phase 3 validation |
| `resources/mermaidjs_diagrams.md` | Mermaid diagram reference — rendering, complexity thresholds, pitfalls |
