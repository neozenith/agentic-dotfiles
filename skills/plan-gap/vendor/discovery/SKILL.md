---
name: discovery
description: "Current/Desired State discovery research. Produces a review-only discovery document: Current State researched from the codebase with file:line citations, Desired State from verified external SOTA research, each drawn as 2–3 paired Mermaid lens diagrams sharing node IDs so they read as a before/after. Use when an initiative needs its as-is and to-be state researched and captured before planning, or when a plan's discovery/background file must be created or refreshed. Not for decomposing the delta into gaps, tickets, or an execution plan — this skill stops at the two states."
argument-hint: "<path/to/DISCOVERY.md | path/to/folder/> [one-line initiative brief]"
user-invocable: true
---

# Discovery — Current & Desired State Research

Research and capture the **Current State** of a system (grounded in its codebase) and the
**Desired State** it should reach (grounded in verified external research), in one review-only
discovery document. The document exists for a human reviewer — or a downstream planning workflow —
to see the before and the after side by side and derive work from the delta; this skill never
derives that work itself.

**Done when:** the target document holds a populated `## Current State` and `## Desired State`,
each drawn through the **same 2–3 lenses** with **shared node IDs**; every factual claim traces to
a `file:line` citation or a verified URL (or carries an explicit unverified marker); and every
diagram renders with mmdc in both themes (exit 0) and passes the contrast and complexity gates.

**Hallucination is a critical failure.** A claim that cannot be corroborated by a codebase
location or a verified URL is removed or flagged with a marker for the user to confirm — never
left standing as fact.

## Target document

| Argument | Meaning |
|----------|---------|
| a directory | the discovery document is `<dir>/DISCOVERY.md` |
| a `.md` path | that file is the discovery document |

- **File exists** — read it; refresh only `## Current State` and `## Desired State`. Any other
  section (a caller workflow may own sections after Desired State) is preserved verbatim — this
  skill never edits a section it does not author.
- **File missing** — create it from `resources/discovery-template.md`. If no initiative brief was
  given, ask the user for one sentence describing the initiative and the codebase areas it touches.

## Workflow

### Step 1: Target setup

Resolve the argument per the table above; create or read the document. Confirm the initiative
brief and the codebase scope before spending research effort.

### Step 2: Dual deep research

Launch **two parallel research subagents**:

**Track A — internal (codebase → Current State).** A read-only exploration agent over the areas
the brief names. It traces execution paths, maps architecture layers, documents dependencies,
data flows, and integration points, and notes technical debt and constraints. It reports concrete
file paths, function names, and line numbers — not summaries.

**Track B — external (web/SOTA → Desired State).** A research agent over the external landscape:
state-of-the-art approaches, documentation and tutorials for candidate technologies, open-source
projects solving similar problems (approach, maturity, license, activity), papers and talks, and
what has become a "solved problem" since the current implementation was built. It MUST record
**every URL** it references with a one-line assertion of what it expects that page to contain —
that list is the input to Step 3.

### Step 3: Link verification

Verify **every external URL** from Track B at the highest available tier. Read
`resources/playwright-cli.md` for the detection logic, command reference, verdict classification,
and marker definitions.

| Tier | Tool | Capability |
|------|------|------------|
| 1 | `playwright-cli` | Full browser — JS rendering, screenshots |
| 2 | `WebFetch` | HTTP fetch — static content only |
| 3 | *(none)* | Mark every external link `<!-- LINK_NOT_VERIFIED -->` |

Detect once, announce the selected tier, and verify the whole batch at that tier. If any link
ends up unverified, add the document-level warning comment from `resources/playwright-cli.md`.

### Step 4: Synthesis

Populate the two state sections from the verified findings:

1. **Pick 2–3 lenses** from the menu in `resources/mermaidjs-diagrams.md` (component, data-flow,
   sequence, deployment, state, entity) — only the lenses that genuinely illuminate this
   initiative. Use the **same** lenses for Current and Desired.
2. **Current State** — prose with `file:line` citations from Track A, plus one diagram per lens;
   problem areas in the danger fill.
3. **Desired State** — prose with verified URLs from Track B, plus one diagram per lens; new or
   changed nodes in the good/process fills.
4. **Reuse node IDs** across each Current/Desired pair so the reader diffs visually.
5. Follow the document shape and style rules in `resources/discovery-template.md`.

### Step 5: Validation

- Render every diagram with mmdc in both theme variants (commands in
  `resources/mermaidjs-diagrams.md`) — exit 0 required.
- Every diagram passes the **contrast** and **complexity** rules in
  `resources/mermaidjs-diagrams.md` → Color Theming.
- Audit the evidence contract: no uncited claim, no unverified URL without its marker.
- Report to the user: lenses chosen, claims verified vs marked, and anything that needs their
  confirmation (`<!-- ASSUMPTION: ... -->` markers).

## Output conventions

- Edit with precise changes, not whole-file rewrites; never touch sections this skill does not own.
- Front-load every section (first line states the outcome); semantic line breaks in prose.
- Do not add content the user has not confirmed — mark inferences `<!-- ASSUMPTION: ... -->` and
  surface them in the Step 5 report.

## Resources

Paths relative to this skill's directory.

| File | Purpose |
|------|---------|
| `resources/discovery-template.md` | The discovery document template + the style rules that govern it |
| `resources/playwright-cli.md` | Link verification — tier detection, commands, verdicts, markers |
| `resources/mermaidjs-diagrams.md` | Lens menu, mmdc rendering/validation, color theming + contrast rules |
