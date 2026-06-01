# Phase 4 — TDD Ticket Decomposition (full playbook)

The step-by-step detail for Phase 4, referenced from `SKILL.md` → Workflow → Phase 4. `SKILL.md` holds
the one-line summary of each step; this file holds the mechanics. Paths are relative to
`.claude/skills/plan-gap/`.

After Phase 3 validation passes, decompose each `G<N>` into TDD vertical-slice tickets — **one ticket
file per slice** (`G<n>-T<x.y>.md`) plus the gap file's `## Tickets` table — and write the
index Execution Plan that drives the spec to completion via `/loop`. The bundled TDD reference lives
in `resources/tdd/`; the ticket-file template and anti-pattern list are in `resources/spec-body.md`.

Read `resources/tdd/tdd.md` once before starting Phase 4. Pay particular attention to the
**horizontal-slice anti-pattern** — every ticket MUST be a single vertical slice (one test → one
minimum implementation), never "all tests first then all implementation."

## Step 4a: Per-gap behavior enumeration

For each `G<N>`, launch a focused subagent (parallel across gaps when N > 1). Each
subagent receives a fresh context containing only:

- The gap file's lead, `## Context`, `## Outputs`, optional `## Key logic`, and settled `ADR<n>.<m>`
  sections (`G<n>.md`)
- Read access to `resources/tdd/` (tdd.md, tests.md, mocking.md,
  interface-design.md, deep-modules.md, refactoring.md) and `resources/style.md`

The subagent enumerates the user-observable behaviors the gap's Outputs must support. Each behavior:

- Is phrased declaratively as `<actor> <observable outcome>` (rule 7) — precondition detail belongs
  in the ticket's lead/contract sentence, not the title
- Is verifiable through a public interface — see `resources/tdd/interface-design.md`
- Is the smallest unit that delivers a falsifiable signal — one assertion per behavior
- Survives an internal refactor — see `resources/tdd/tests.md` for the good-vs-bad-test contrast

The subagent rejects any candidate behavior matching the anti-patterns in
`resources/tdd/tdd.md`, `resources/tdd/tests.md`, and `resources/escalators-not-stairs.md`:

- "Tests the shape of things" rather than user-facing behavior
- Asserts on call counts, call order, or private methods
- Verifies via direct DB inspection, log scraping, or filesystem reads instead of the public interface
- Mocks an internal collaborator the project owns, or mocks/stubs the gap's own deliverable seam —
  mock only a true external boundary you do not own (`resources/tdd/mocking.md`)
- Re-implements production logic in a parallel/throwaway path instead of exercising the shipped code
- Can be satisfied without ever running the real deliverable on real input (no executable evidence)

## Step 4b: Ticket structuring

For each behavior, write one **ticket file** `G<n>-T<x.y>.md` using the ticket template in
`resources/spec-body.md`. Numbering: `<n>` matches the parent gap, `<x.y>` is `<n>.<m>` with `<m>`
1-based within that gap. The first ticket per gap (`T<n>.1`) is the **tracer bullet** — the smallest
slice that threads the gap's *highest-risk, load-bearing path* end-to-end through the **real**
production interface (for a pipeline: produce → consume → emit), runs the real deliverable seam on real
input, and produces the gap's first proof-of-execution Output; it is never the cheapest peripheral leaf
and never a side path; mark it `_(tracer bullet)_`. Subsequent tickets layer on top.

Each ticket file holds, in the austere form (rules 3–5 — no `Cycle:` line, no `Mocks: none`, no
3-level nesting):

- A blockquote nav header (Gap, Index, optional Prev/Next)
- A status checkbox `- [ ] **Done**` the `/loop` runner toggles to `[x]`
- One lead sentence stating the precise, assertion-worthy contract (exact endpoint/args/return or the
  concrete fact the test checks)
- A two-column table: `Test` (`path::test_name` + assertion against a public interface, on real
  input), `Implements` (file(s) + symbol, minimum **real** code — never a stub), `Depends on` (linked
  ticket files or `—`), `Mocks` (only when non-empty — a *true external boundary you do not own* per
  `resources/tdd/mocking.md`, never the gap's own deliverable), `Refactor` (only when present — hints
  from `resources/tdd/refactoring.md`)

The test is the ticket's evidence: an assertion on real input through the public interface. The gap's
proof-of-execution Output (named in `## Outputs`) is produced by the tracer and asserted by its test.

## Step 4c: Dependency ordering

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

## Step 4d: Write the Execution Plan section

Populate the `## Execution Plan` section of the **index** (`README.md`) — body wrapped in `<details>`,
heading visible — per the spec in `resources/spec-body.md`:

1. **Loop Runner Prompt** — substitute `<SPEC_PATH>` with the index file's path (relative to the repo
   root) or `<owner/repo#N>` for a GitHub issue. The prompt is self-contained — an agent in a fresh
   context invoked by `/loop` can execute it without external arguments, finding the next ticket via
   the index Progress table and opening its ticket file. Do not modify the prompt skeleton from
   `resources/spec-body.md`; only substitute the path.

2. **Progress** — emit one row per gap with the ticket counts, gap and ticket IDs linked to their
   files. Initial state is `0` done, all `[ ]` todo, "Next eligible" set to the lowest-numbered ticket
   with no unresolved dependencies, "Blocked on" lists outstanding dependencies.

3. **Done Criteria** — copy the checklist verbatim from `resources/spec-body.md`. The `/loop` runner
   uses it to detect "spec complete."

## Step 4e: Validation of the decomposition

After Steps 4a–4d, verify that:

- Every `G<N>` has at least one ticket file — no gap is left without execution material
- Every `G<N>` names a proof-of-execution Output and has a tracer (`T<n>.1`) that produces it by
  running the real deliverable on real input — no gap can complete on stubs or mocks alone
- Every ticket file exists, opens with `- [ ] **Done**`, and has its Test, Implements, and Depends-on
  rows populated (Mocks and Refactor only when non-empty)
- No ticket's `Mocks` row names an internal module or the gap's own deliverable seam (external
  boundaries only), and no ticket re-implements production logic in a parallel path
- Every ticket-file row in a gap's `## Tickets` table links a file that exists, and vice versa
- The dependency DAG is acyclic and topologically sortable
- The index Progress table totals match the per-gap ticket-file counts
- The Loop Runner Prompt's `<SPEC_PATH>` substitution is correct and points at the index file

## Execution and loop-exit conditions

The user can now invoke `/loop` with the runner prompt to drive the spec to completion. Each iteration
consumes one ticket via the RED→GREEN→(REFACTOR) cycle from `resources/tdd/tdd.md` and updates the
Progress table. The loop exits when:

- **Done Criteria are satisfied** — the spec is complete.
- **An `<!-- UNRESOLVED -->` ADR placeholder appears** — an up-front design ambiguity surfaced;
  control returns to Phase 2 refinement.
- **A `<!-- CHANGE-REQUEST -->` marker is raised** — the midflight discovery that the gap as written
  cannot produce real evidence (a ticket can only ship a stub, a mock of its own deliverable, or a
  parallel re-implementation). This is the **last resort**, not the first move: before raising it, run
  the 5-Whys root-cause check (`resources/5ys.md`) on "why can't this be real yet?" — most blockers
  resolve into real work (wire a dependency, build a fixture, reorder a ticket) rather than a scope
  change. Only when the chain bottoms out at a genuine plan defect do you STOP, add the marker
  recording the root cause and what the ticket needs to become real, and return control to Phase 2 to
  rescope. See the loop-runner protocol in `resources/spec-body.md`.
