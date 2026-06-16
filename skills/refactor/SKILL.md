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

1. **Hotspots** — high churn × high complexity. Honest scope: hotspots are a
   *where-to-look* heuristic, not a promise (deployed file-ranking at Google
   changed nothing because rankings alone aren't actionable; metric-fault
   correlations largely vanish when size is controlled). Every hotspot
   candidate must therefore carry a concrete, human-actionable reason —
   "splitting along this co-change seam shrinks the blast radius of X" — or
   it doesn't rank.
2. **Dependency cycles that cross intended module boundaries or block a
   concrete goal** (testability, extraction, build parallelism). Cycles are
   ubiquitous in healthy software and the cycle-defect link is correlational;
   "cycle exists" alone never triggers work.
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
| **Conflicting** | contradicts an Accepted ADR | **STOP and surface.** Never silently refactor against a recorded decision — but present the ADR's age and last-touched date alongside the conflict (most ADR sets are abandoned fossils; ~50% of ADR-using repos hold ≤5 records). Offer two paths: a lightweight amendment note (default for stale, never-reaffirmed ADRs) or full supersession (for decisions with recent reaffirmation). The user decides; the agent never does. |

## Phase 3 — Safety net (before any edit)

- Verify test coverage at the affected seams — and don't trust green alone:
  the empirical norm is that only ~22% of refactoring edits are adequately
  covered by existing tests. Where coverage is thin, write **characterization
  tests** at the module boundary capturing *current* behavior; for high-risk
  moves, spot-check the net with a quick mutation probe (introduce a deliberate
  break, confirm a test fails, revert).
- Characterization tests are not literally immutable — they pin noise as well
  as behavior. A change to one requires explicit classification, logged in the
  plan: **pinned-bug** (keep pinning, note the bug), **pinned-noise**
  (timestamp/ordering artifacts — fix the assertion, say so), or **genuine
  behavior change** (= not a refactoring: stop and report).
- Risk-tier the plan: renames/extracts → standard suite suffices.
  Moves across module boundaries and inheritance-hierarchy surgery → mandatory
  characterization tests + exported-surface re-check (hierarchy surgery induces
  bugs in up to ~40% of cases even for humans; spend the safety budget there,
  not uniformly).

## Phase 4 — Execution (small reversible steps)

- **Two hats is a commit-staging discipline, not a workflow ban.** In the
  wild, 91% of refactoring happens interleaved with other work ("floss
  refactoring") and that practice is effective — what must never mix is a
  single *commit*: stage structure and behavior separately (`git add -p`),
  one named transformation per structure commit. During a planned macro
  refactor under this skill, drive-by behavior fixes are logged as follow-ups,
  not snuck into structure commits.
- Full test suite green between every step; audit each diff against the
  stated plan before moving on.
- For boundary replacement use branch-by-abstraction / strangler-fig style —
  with **kill criteria declared up front**: every facade/adapter gets a
  decommission condition and target date, because the documented strangler
  failure mode is permanent dual-system limbo. (Rewrites do sometimes win —
  stable domain, mature team knowledge — but recommending one is a scope
  change to raise, not a refactoring.)
- Prefer deterministic tooling for mechanical transforms (IDE/LSP rename,
  codemod, `git mv`) over hand-editing many files.

## Phase 5 — Verification + lock-in

1. Full `make ci` (or suite + typecheck + lint). Green tests are necessary,
   not sufficient.
2. **Re-measure the macro claim in operational terms**: the named outcome
   from Phase 1 ("module X extractable", "test time halved", "cycle across
   the api/storage boundary gone"). Static quality scores (LCOM, smell
   counts) are NOT success metrics — refactoring routinely worsens them while
   achieving its real goal. If the named outcome didn't materialize, the
   refactoring failed regardless of green tests — say so.
3. **Encode the restored invariant as a fitness function** where tooling
   allows (dependency-cruiser / import-linter rule, cycle check in CI) so the
   boundary can't silently erode again. Each fitness function carries an
   owner and a review-by date, and enters CI in warn-mode for a grace period
   before hard-fail — a stale architecture test doesn't just mislead, it
   breaks builds until someone with the least context deletes it.
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
