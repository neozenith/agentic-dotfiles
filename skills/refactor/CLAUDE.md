# refactor — Maintainer Decision Lens

Read the ADR log below before changing anything. Each ADR carries a **Lens** —
apply it to the next decision instead of re-deriving the trade-off.

## Development contract

Docs-only skill (no `scripts/`, so no Makefile `fix`/`ci` loop). Gates before
handoff, run from repo root:

```sh
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_contrast.ts   .claude/skills/refactor/README.md
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts .claude/skills/refactor/README.md
uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 .claude/skills/refactor/README.md
```

All files ≤ 500 lines (`.claude/rules/claude_skills/index.md`).

## File map

| File | Role |
|------|------|
| `SKILL.md` | Agent operating manual: 6 phases, ranking, when-NOT-to, pitfalls |
| `README.md` | Human explainer: purpose, quickstart, architecture diagram |
| `resources/evidence.md` | Research citations behind each rule (lazy-loaded) |
| `CLAUDE.md` | This file — rationale and decision log |

## Architecture principles

- Structure-only: behavior change is never mixed in; characterization tests
  are immutable during a refactor.
- Macro signals (hotspots, cycles, hubs, ADR drift) outrank micro-smells.
- Recorded decisions outrank the agent's aesthetic judgment.

## ADR log

### ADR-1: hotspots and cycles rank above smell checklists

- **Status:** Accepted
- **Context:** The empirical record shows individual code smells don't predict
  maintenance effort once size/churn are controlled (Sjøberg TSE 2012), while
  churn × complexity hotspots and dependency cycles carry measured cost.
- **Decision:** Phase 1 ranks: hotspots → cycles → hub modules → ADR drift →
  shallow modules; smell sweeps are explicitly deprioritized.
- **Consequences:** The skill sometimes declines "clean this up" requests on
  cold code, citing the when-NOT-to list.
- **Lens:** When a new "should we target X?" question arrives, ask for the
  empirical signal (churn, cycle participation, defect history) before adding
  it to the ranking — aesthetics never rank.

### ADR-2: conflicting ADRs hard-stop the refactor

- **Status:** Accepted
- **Context:** Nygard's failure mode — without rationale, an agent "blindly
  changes" deliberate indirections; LLM agents are especially prone to
  collapsing structure an ADR introduced on purpose.
- **Decision:** Phase 2 classifies every candidate conforming/neutral/
  conflicting; conflicting → stop, draft a superseding ADR, ask the user.
- **Consequences:** Occasional friction when an ADR is stale — that friction
  is the feature: staleness gets adjudicated by a human, not silently overridden.
- **Lens:** The agent may propose changing a decision; it may never act as if
  the decision were already changed.

### ADR-3: re-measurement is part of "done"

- **Status:** Accepted
- **Context:** Agents declare victory on green tests, but green tests don't
  show the architectural goal was reached; the macro claim is the point.
- **Decision:** Phase 5 requires the named metric (cycle count, fan-in,
  interface size) to be re-measured and reported; unchanged metric = failed
  refactor, reported as such.
- **Consequences:** Every engagement states its metric up front (Phase 1's
  one-line value statement), which also kills vague "general cleanup" scopes.
- **Lens:** If a proposed refactoring can't name the number it will move, it
  isn't a macro refactoring — reject or reframe it.

### ADR-4: lock-in via fitness functions where tooling exists

- **Status:** Accepted
- **Context:** Restored boundaries silently erode; governance-by-inspection
  doesn't scale.
- **Decision:** After a successful macro refactor, encode the invariant as a
  CI-checkable rule (dependency-cruiser/import-linter/cycle check) when the
  ecosystem has such tooling; otherwise record the invariant in an ADR.
- **Consequences:** Small CI additions per refactor; boundaries become
  regression-tested.
- **Lens:** Prefer an executable constraint over a prose convention whenever
  one exists; prose is the fallback, not the default.

### ADR-5: round-2 red-team amendments — floss-aware, fossil-aware, operationally measured

- **Status:** Accepted (2026-06; amends ADR-1/-2/-3 mechanics, keeps their goals)
- **Context:** Disconfirmation research (see resources/evidence.md
  "Counter-evidence"): 91% of real refactoring is interleaved (floss);
  deployed hotspot rankings changed nothing without actionable reasons; ADRs
  are mostly abandoned fossils (~50% of repos: ≤5 records); only ~22% of
  refactoring edits are test-covered; static quality metrics move the wrong
  way under successful refactoring.
- **Decision:** Two hats became commit-staging discipline (mix work, never
  commits); hotspot/cycle candidates require an actionable reason or concrete
  blocked goal; ADR conflicts surface with age + lightweight-amendment
  default while still always stopping; characterization-test changes are
  classified (pinned-bug / pinned-noise / behavior change) rather than
  forbidden; success re-measured in operational outcomes only; fitness
  functions get owner + review-by + warn-first.
- **Consequences:** The skill fights observed practice less and demands more
  specificity from its own recommendations.
- **Lens:** When a rule contradicts dominant successful practice, ask what
  the rule actually protects (here: reviewable commits, not separated work
  sessions) and enforce that narrower thing.

## Extension checklist

- [ ] New ranking signals come with a cited empirical basis in
      `resources/evidence.md` (ADR-1).
- [ ] Any new phase preserves the hard-stop semantics of the ADR lens (ADR-2).
- [ ] Output format changes keep the named-metric requirement (ADR-3).
- [ ] Both mermaid gates + mdtoc re-run if README touched; all files ≤ 500 lines.

## Known gotchas

- The churn one-liner counts renames as two files; add `--follow` per-file or
  accept the noise — don't trust raw counts near big moves.
- `bunx madge --circular` misses type-only import cycles unless `--ts-config`
  is passed in some setups; absence of output ≠ absence of cycles.
- Characterization tests that assert on incidental ordering/formatting create
  false reds during legitimate structure moves — pin behavior, not noise.
- "Neutral" ADR verdicts on boundary-crossing moves still warrant a user
  check-in: absence of a decision is not endorsement.
