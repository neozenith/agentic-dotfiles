---
name: plan-gap
description: "Gap analysis planning mode. Iteratively refines a gap analysis spec — a tiered file set (index + per-gap + per-ticket + discovery files, or a GitHub issue with per-gap sub-issues) covering Execution Plan, Overview, Gap Analysis, Decisions (ADRs), Success Measures, and Negative Measures, with Current/Desired State held in a review-only Discovery file. Validates Mermaid diagrams and enforces requirement integrity through structured questioning."
argument-hint: "<path-to-plan.md | path/to/folder/ | owner/repo#N | owner/repo>"
user-invocable: true
---

# Gap Analysis Planning Mode

You are now in **planning mode**. Your sole purpose is to iteratively refine a gap analysis document at the target provided as an argument. The target may be a local markdown file or a GitHub issue.

## First principle — escalators, not expensive stairs

Read `resources/escalators-not-stairs.md` now; it governs **every phase**, not just final validation. A
gap analysis exists to make **real, demonstrable work** happen — so every gap and every ticket must
have an **evidenceable real outcome**: a committed artifact produced by running the real code path on
real input. Bake this into the gaps you draft (Phase 1), the Success Measures
(Phase 1f), the tickets you decompose (Phase 4), and the validation gates (Phases 3–4e).

## Target Document

A spec is a **folder** (`<plan>/`) whose `README.md` is the index — the GitHub-repo convention where
`README.md` is the default page. The sibling files strip the stem: `G<n>.md`, `G<n>-T<x.y>.md`,
`DISCOVERY.md` (+ optional `STYLE.md`). The argument is a **directory path**, an **`.md` index path**,
or a **GitHub issue reference**.

### Resolving the target

1. **Argument is a directory** — the directory *is* the plan folder (`<plan>/`); its name is the
   `<plan>` stem.
   - If it contains a `README.md`, read it and every sibling `G*.md` / `*-T*.md` / `DISCOVERY.md`, and
     continue refining from the set's current state.
   - If it has no `README.md`, treat it as a new plan: ask the user to describe the initiative in one
     sentence (the folder name is the slug — confirm or refine it with the user using `kebab-case`),
     then create `README.md` from the index skeleton in `resources/spec-body.md` and `DISCOVERY.md` from
     the discovery template inside it. Gap and ticket files are added later (gap stubs in Phase 1c,
     ticket files in Phase 4). Create the directory if it does not exist.
   - **Convenience:** if the directory is a plans *container* (it already holds other plan folders, e.g.
     `docs/plans/`), do not author into it directly — ask the user for the initiative, derive a
     `kebab-case` slug, confirm it, and create the new plan folder as `<container>/<slug>/`.

2. **Argument ends with `.md`** — treat it as the **index** path. Its parent directory is the plan
   folder; the stem is the folder name. Read it and the siblings (`G*.md` / `*-T*.md` / `DISCOVERY.md`)
   if present, else create the `README.md` + `DISCOVERY.md` skeletons in that folder.
   (A bare `<plan>/README.md` is the canonical index path; a legacy flat `<plan>.md` is read-compatible
   — see "Legacy flat sets" below.)

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

A gap analysis spec is a **folder** (`<plan>/`) of tiered files, not a single document. Read
`resources/spec-body.md` (relative to this skill's directory) for the full structure — the tiers, their
sections, and the per-tier templates — and `resources/style.md` for the voice and format rules
(front-loading, no bold-pseudo-headings, container-by-shape, gap-scoped ADRs, context economy) that
govern every chunk. **Read both before authoring or editing any spec file.**

**Quick reference — the four tiers (all inside `<plan>/`):**

| File | Tier | Holds | Loaded |
|------|------|-------|--------|
| `README.md` | index | Execution Plan, Overview, Gap Analysis (Gap Map + Dependencies + Gaps table), Decisions (ADRs) roll-up, Success/Negative Measures | loop entry |
| `G<n>.md` | gap | Context, Outputs, optional Key logic, gap-scoped ADRs, Tickets table | per-gap work |
| `G<n>-T<x.y>.md` | ticket | Done checkbox, contract sentence, Test/Implements/Depends-on table | per-ticket work |
| `DISCOVERY.md` | discovery | Current + Desired State (multi-lens diagrams) + per-gap increment stack | human review only |

> **Legacy flat sets.** Older specs use a flat sibling layout sharing a stem
> (`<plan>.md`, `<plan>-G1.md`, `<plan>-G1-T1.1.md`, `<plan>-DISCOVERY.md`). These remain
> read-compatible — resolve the stem from the index filename and read its `<plan>-*` siblings — but
> author **new** specs in the `<plan>/` folder form above.

The driving principle is **context economy**: the index + the one gap + the one ticket an agent is on
are its `/loop` working-set, so Current/Desired State and SOTA background move out to the Discovery
file, and the table of contents + Execution Plan body fold behind `<details>` (agents still read the
source; humans skim past). The `Tickets` table in each gap file is populated in Phase 4 as TDD
vertical slices, one ticket file per red-green-refactor cycle. A GitHub-issue spec maps the index to
the parent issue and each gap to a sub-issue — see `resources/gh-issues.md`.

## Workflow

Four phases, each with a detailed playbook in `resources/` — read the playbook before running that
phase. The summaries below are the one-line shape of each step; the mechanics live in the playbooks.

### Phase 1: Bootstrap

Stand up the file set and fill it from research. **Read `resources/phase1-bootstrap.md` for the full
step-by-step playbook**; the steps are:

- **1a — Target setup.** Create the index + Discovery skeleton, or read an existing set and assess
  completeness (local file or GitHub issue).
- **1b — Discovery research (vendored skill).** Run the vendored discovery skill
  (`vendor/discovery/SKILL.md`) against `<plan>/DISCOVERY.md`: dual parallel research tracks
  (Track A codebase → Current State, Track B web/SOTA → Desired State), verification of every
  external URL at the highest available tier, and synthesis into **2–3 paired lens diagrams** per
  state. Hallucination is a critical failure: every claim traces to a `file:line` or a verified URL.
- **1c — Gap synthesis.** From the Current/Desired delta, draft the `G<N>` gaps + stubs, seed the
  per-gap increment stack in `DISCOVERY.md`, the Overview, the index Gap Map + Dependencies
  diagrams, and any `<!-- UNRESOLVED -->` ADR placeholders.
- **1d — Per-gap deep research.** One fresh-context subagent per gap to enrich `## Outputs`
  (including the gap's proof-of-execution artifact) and `## Key logic`.
- **1e — Quality & failure-mode research.** Two subagents: the project's CI gates (→ Success Measures)
  and its known gotchas/anti-patterns (→ Negative Measures).
- **1f — Final assembly.** Populate Success/Negative Measures. Every domain-specific Success Measure is
  an **executable-evidence escalator** — satisfied only by the gap's committed proof-of-execution
  Output, never by "a test exists" or "it ran". Ensure each gap's `## Outputs` names that artifact.

### Phase 2: Iterative refinement loop

Settle the open design decisions by asking the human **one maximally-leveraged question at a time**.
The question loop is the **vendored Concise Decisions skill** at `vendor/concise-decisions/` — it owns
the question contract (self-answering from decision records, ranking, the pragmatic-default test, the
nine-section briefing, the five-question check, the lens grammar, the TBD routes). This skill owns what
counts as an ambiguity in a spec and what an answer does to the file set.
**Read `resources/phase2-refinement.md` for the full step-by-step playbook, and
`vendor/concise-decisions/SKILL.md` once before the first iteration**; the cycle is:

- **2a — Assemble the ambiguity inventory.** Collect every `<!-- UNRESOLVED -->` entry across all
  `G<n>.md` files, and create placeholders for any non-ADR ambiguity (missing details, implicit
  assumptions, unpermitted defaults) so the whole open set is rankable at once.
- **2b — Self-answer, then rank.** Search the spec's own ADRs and markers, then the target project's
  decision surface (`docs/adrs/`, `CLAUDE.md`/`AGENTS.md` lenses) — an item a record already answers is
  decided, and is never asked. Rank the rest by how many ADRs across how many gaps the answer resolves,
  show that ranking, and settle anything that passes the pragmatic-default test yourself.
- **2c — Ask one question.** Compose it with the vendored loop's shape file, harness adapter, and
  nine-section template, verbatim — previews are complete outcomes on the spec's real content.
- **2d — Incorporate the answer.** Settle the affected ADRs into bulleted form with the user's
  reasoning written as the lens (`Given / We prefer … over … / Because / Unless`), update the index
  Decisions roll-up, cascade both the choice and the lens into Outputs/Key logic/Measures and the
  affected `DISCOVERY.md` diagrams, and restructure the Overview/Gap Map/Dependencies if gaps changed.
- **2e — Re-evaluate.** Fold any new sub-questions into the next ranking; exit when no
  `<!-- UNRESOLVED -->` markers remain and the set is internally consistent.

### Phase 3: Validation

Gate the converged spec before decomposition. **Read `resources/phase3-validation.md` for the full
step-by-step playbook**; the three checks are:

- **3a — Diagram validation.** `DISCOVERY.md` MUST hold ≥2 Current and ≥2 Desired lens diagrams plus one
  increment diagram per gap; the index MUST hold the Gap Map (`flowchart TD`) and Dependencies
  (`flowchart LR`). Render every diagram-bearing file with mmdc (dark + light, exit 0) and pass the
  contrast + complexity gates (`resources/mermaidjs-diagrams.md`, `resources/style.md` → Diagrams).
- **3b — Requirement integrity.** Apply `resources/escalators-not-stairs.md` across every gap and ticket:
  every Success Measure is mandatory and falsifiable, every gap names a real proof-of-execution Output,
  every Negative Measure is a concrete Type 2 failure, and no requirement is silently downgraded.
- **3c — Cross-consistency.** Every gap has a Success Measure; Negative Measures complement them; every
  cross-link resolves (gap nav, ticket nav, `DISCOVERY.md#g<n>-increment` back-links, index→gap→ticket);
  every settled ADR appears in both its gap file and the index roll-up.

### Phase 4: TDD Ticket Decomposition

Decompose each `G<N>` into TDD vertical-slice tickets and write the index Execution Plan that drives
the spec to completion via `/loop`. **Read `resources/phase4-decomposition.md` for the full
step-by-step playbook** (and `resources/tdd/tdd.md` once before starting); the steps are:

- **4a — Per-gap behavior enumeration.** One subagent per gap enumerates user-observable behaviors,
  rejecting the anti-patterns in `resources/tdd/` and `resources/escalators-not-stairs.md` — including
  any behavior that mocks/stubs the gap's own deliverable, re-implements production logic in a parallel
  path, or could pass without ever running the real deliverable on real input.
- **4b — Ticket structuring.** One ticket file per behavior (template in `resources/spec-body.md`).
  The first ticket per gap (`T<n>.1`) is the **tracer bullet** — the smallest slice that threads the
  gap's highest-risk, load-bearing path end-to-end through the **real** production interface and
  produces the gap's first proof-of-execution Output. It is never the cheapest peripheral leaf.
- **4c — Dependency ordering.** Cross-link tickets; the DAG must be acyclic and topologically
  sortable; leaves are the tracer-bullet candidates.
- **4d — Execution Plan.** Write the index Loop Runner Prompt (substitute `<SPEC_PATH>`), Progress
  table, and Done Criteria (verbatim from `resources/spec-body.md`).
- **4e — Validation of the decomposition.** Verify every gap has a tracer that produces its
  proof-of-execution Output, no ticket mocks the deliverable or re-implements production logic, the DAG
  is sound, and the Progress/links are consistent.

The user then runs `/loop` with the runner prompt; each iteration consumes one ticket via
RED→GREEN→(REFACTOR). The loop exits on Done Criteria, on an `<!-- UNRESOLVED -->` ADR, or on a
`<!-- CHANGE-REQUEST -->` marker. A Change Request is the **last resort**, not a reflex: before raising
one, run the 5-Whys root-cause check (`resources/5ys.md`) on "why can't this be real yet?" — most
blockers resolve into real work rather than a scope change. Raise it only when the chain bottoms out at
a genuine plan defect (the gap as written cannot produce real evidence); then control returns to
Phase 2 to rescope. See `resources/phase4-decomposition.md` and the loop-runner protocol in
`resources/spec-body.md`.

## Questioning Principles

Every question this skill asks — in any phase, not only Phase 2 — is composed with the vendored loop at
`vendor/concise-decisions/SKILL.md`. These are its principles as they bind here; the vendored surface
is the authority on the mechanics, and no phase substitutes a cheaper form of question.

- **One question at a time.** Never dump a list of questions, and never a multi-question wizard: answer
  1 must be able to cascade into 2–n before 2 is asked.
- **Search before you ask.** A question whose answer was already sitting in an ADR, a settled decision,
  or a prior user ruling is the failure the loop exists to prevent. Say what you checked.
- **Cascade awareness.** Before asking, consider whether a previous answer — its *choice* or its
  *reasoning* — has already resolved it.
- **Capture the reasoning, not just the choice.** The answer surface must let the user attach their
  why; that why becomes the ADR's lens, and a codified lens is what lets later questions be
  self-answered.
- **Explain the "why now."** Always explain why this is the most impactful question right now, what it
  unblocks, and which open questions it outranks.
- **Leave room for a non-decision.** The user must be able to answer `explain`, `show`, `spike`,
  `defer`/`handoff`, `other`, or `task` without aborting the question.
- **Converge, don't diverge.** Each iteration should reduce the total number of ambiguities. If a
  question opens sub-questions, fold them into the ranking for next iteration.
- **Know when to stop.** When no ambiguities remain that materially affect the plan's actionability,
  declare the document complete and move to validation.

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
| `resources/phase1-bootstrap.md` | Phase 1 full playbook — Steps 1a–1f (target setup, vendored discovery research, gap synthesis, per-gap + quality/failure research, assembly) |
| `resources/phase2-refinement.md` | Phase 2 full playbook — Steps 2a–2e (inventory, self-answer + rank, ask one question via the vendored loop, incorporate the answer and its lens, re-evaluate) |
| `resources/phase3-validation.md` | Phase 3 full playbook — Steps 3a–3c (diagram lenses + increment gate, requirement integrity, cross-consistency) |
| `resources/phase4-decomposition.md` | Phase 4 full playbook — Steps 4a–4e (behavior enumeration, ticket structuring, DAG, Execution Plan, validation) + loop-exit conditions |
| `resources/escalators-not-stairs.md` | Requirement integrity + executable-evidence principles (no stubs, no mocks of the deliverable) — read at the start of planning and applied in every phase |
| `resources/5ys.md` | 5 Whys root-cause analysis — the precheck before raising a `<!-- CHANGE-REQUEST -->`, and for retrospectives of Type 2 failures |
| `resources/mermaidjs-diagrams.md` | Mermaid diagram reference — rendering, complexity thresholds, pitfalls |
| `resources/color_theming.md` | Diagram palette source — every diagram derives its colours here, then passes the contrast gate |
| `resources/gh-cli.md` | GitHub CLI reference — detection, authentication, issue CRUD commands |
| `resources/gh-issues.md` | GitHub issues backend — local cache, sync protocol, edit history lineage |
| `resources/tdd/tdd.md` | TDD workflow — red-green-refactor, vertical slicing, anti-patterns. Read at the start of Phase 4 |
| `resources/tdd/tests.md` | Good-vs-bad test examples — used in Phase 4 to reject implementation-detail behaviors |
| `resources/tdd/mocking.md` | When to mock — external-boundaries-only rule (never the deliverable) applied to the ticket `Mocks` field |
| `resources/tdd/interface-design.md` | Testable interface design — accept dependencies, return results, small surface |
| `resources/tdd/deep-modules.md` | Deep module guidance — small interface, deep implementation |
| `resources/tdd/refactoring.md` | Refactor candidates — populates the optional ticket `Refactor candidates` field |

The skill also carries a **`vendor/`** directory of wholesale copies of capabilities it needs but does
not author. They are operated in place and never edited; `vendor/README.md` holds the refresh procedure.

| Vendored | Load when |
|----------|-----------|
| `vendor/discovery/SKILL.md` | at Step 1b — it owns the Current/Desired State research (dual tracks, link verification, lens synthesis); its `resources/**` (template, link verification, lens menu) load per its own instructions |
| `vendor/concise-decisions/SKILL.md` | once before the first Phase 2 iteration — it is the question loop; its `resources/**` (one shape file, one harness adapter, the template, the TBD routes) load on demand per question |

Only `SKILL.md` and `resources/**` are runtime authority — in this skill and in anything vendored.
`README.md`, `CLAUDE.md`, and `docs/adrs/` are development-time documents for whoever *edits* the skill;
they are never loaded to run it and never cited as authority during a run. This skill keeps no learning
store: what it learns becomes an ADR in `CLAUDE.md` **and** a change to a loaded surface.

A skill-root **`CLAUDE.md`** documents how to audit this skill's own usage — using the `introspect`
skill to extract a timeline of which `resources/*` loaded in a session (and at what token cost) and
render it as a Mermaid gantt. Read it when reviewing whether a planning session followed the playbooks.
