---
name: refactor
description: "Macro-level, evidence-based refactoring: maps the system's dependency structure and churn hotspots, reads ADRs and project decisions as a lens of values, and executes behavior-preserving change in small test-guarded steps. Use when the user asks to refactor, restructure, untangle modules, reduce coupling, or 'clean up' a codebase area. Skip for pure formatting (linters own that) and for bug fixes or feature work (refactoring never mixes with behavior change)."
argument-hint: "[target area | smell | goal] (default: propose ranked opportunities)"
user-invocable: true
---

# Refactor

Refactoring here means **structure-only change at the system level**, directed
by what empirically matters (churn × complexity hotspots, dependency cycles,
hub modules, ADR drift) — not by smell checklists, which do not predict
maintenance effort once size and churn are controlled for. ADRs are the lens of
values: a refactoring that contradicts an Accepted ADR is not a refactoring,
it's an architecture change that needs a superseding decision first.

Evidence behind every rule: [resources/evidence.md](resources/evidence.md).

## Phase 0 — Discovery (map system + read values) — BLOCKING

1. **Read the decision layer first**: `docs/adr/`, `CONTEXT.md`, `CLAUDE.md`,
   design docs. List Accepted ADRs as explicit constraints. Skipping this is
   the "blindly change" failure mode ADRs exist to prevent.
2. **Map the macro structure**: import/dependency graph of the target area
   (language tooling or grep-based), noting cycles, hub files (high fan-in ×
   fan-out), and shallow pass-through modules.
3. **Pull behavioral signals from git**: churn per file
   (`git log --since=<~12mo> --name-only --pretty=format: | grep -v '^$' | sort | uniq -c | sort -rn`),
   co-change clusters, file sizes. Hotspot = high churn × high complexity.
4. Inventory the **exported surface** of anything that might move: public APIs,
   serialization formats, DI wiring, routes/CLI flags, reflection targets.

## Phase 1 — Opportunity identification (macro first)

Rank candidates by, in order:

1. **Hotspots** — high churn × high complexity (the only signals with strong
   empirical backing; low-quality code in hot paths carries 15x defect rates).
2. **Dependency cycles** — the empirically expensive architectural debt
   (first by practitioner-ranked refactoring cost; cyclically coupled files
   dominate defect- and vulnerability-prone sets).
3. **Hub/god modules** at coupling centers (antipattern participation predicts
   fault-proneness beyond size).
4. **ADR drift** — code that contradicts a documented decision. Restoring
   conformance is the highest-value refactoring kind.
5. **Shallow modules / leaky interfaces** — justify as "module X gets deeper /
   interface smaller / dependency edge removed", never "looks nicer".

Explicitly deprioritize: cold code, isolated micro-smells, anything in
**When NOT to refactor** below. Note: left undirected, agents default to
cosmetic renames — this ranking exists to force the macro framing.

When no target was given, present the ranked list with a one-line value
statement each and let the user pick before touching anything.

## Phase 2 — Value-alignment check (the ADR lens)

Classify each chosen candidate:

| Verdict | Meaning | Action |
|---------|---------|--------|
| **Conforming** | restores an ADR / documented decision | proceed; top priority |
| **Neutral** | no recorded decision speaks | proceed; if the change embodies a new decision, draft an ADR with it |
| **Conflicting** | contradicts an Accepted ADR | **STOP.** Surface the conflict, propose a superseding ADR, ask the user. Never silently refactor against a recorded decision. |

## Phase 3 — Safety net (before any edit)

- Verify test coverage at the affected seams. Where absent, write
  **characterization tests** at the module boundary capturing *current*
  behavior — including oddities. They are immutable during the refactor:
  a changed assertion = behavior change = stop and report.
- Risk-tier the plan: renames/extracts → standard suite suffices.
  Moves across module boundaries and inheritance-hierarchy surgery → mandatory
  characterization tests + exported-surface re-check (these operations induce
  bugs in up to ~40% of cases even for humans).

## Phase 4 — Execution (small reversible steps)

- **Two hats**: structure-only. No behavior change, no drive-by fixes, no
  "while I'm here" edits — log those as follow-ups instead.
- **One named transformation per commit**; full test suite green between every
  step; audit each diff against the stated plan before moving on.
- For boundary replacement use branch-by-abstraction / strangler-fig style:
  introduce the abstraction, move consumers incrementally, keep the old path
  as fallback until the last consumer moves, then delete. No big-bang.
- Prefer deterministic tooling for mechanical transforms (IDE/LSP rename,
  codemod, `git mv`) over hand-editing many files.

## Phase 5 — Verification + lock-in

1. Full `make ci` (or suite + typecheck + lint). Green tests are necessary,
   not sufficient.
2. **Re-measure the macro claim**: cycle removed? fan-in reduced? interface
   smaller? If the metric didn't move, the refactoring failed regardless of
   green tests — say so.
3. **Encode the restored invariant as a fitness function** where tooling
   allows (dependency-cruiser / import-linter rule, cycle check in CI) so the
   boundary can't silently erode again.
4. Update or add ADRs if a decision was made or superseded.

## When NOT to refactor

- **Cold code** — debt in code that doesn't change has cost and no payoff.
- **Code scheduled for deletion/replacement** — characterize and route around.
- **No safety net and no time to build one** — that's a gamble, not a refactor.
- **Smell-driven sweeps** — mass cleanup for a linter score is statistically
  churn; refactoring-heavy phases correlate with bug spikes.
- **Stability-critical hot paths near a release.**
- **Against an Accepted ADR** — escalate to a decision change instead.
- Economics test: tidying buys an option on future change; if no concrete
  upcoming change benefits, the option is likely worthless — don't.

## Agent pitfalls (self-checks)

- LLM refactorings silently change behavior ~7% of the time even on simple
  transforms: hence immutable characterization tests + per-step suite runs.
- Never edit a failing test's assertions to make a refactor "pass".
- Renames/moves safe inside a module still break serialization, DI, routes,
  reflection — check the Phase 0 exported-surface inventory before each move.
- Declare done only after Phase 5's re-measurement, not at first green.
