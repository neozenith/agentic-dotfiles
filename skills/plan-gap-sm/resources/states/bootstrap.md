# State: bootstrap — stand up the spec file set from research

Produce, inside the plan directory, a tiered gap-analysis spec:

| File | Tier | Holds |
|------|------|-------|
| `README.md` | index | Execution Plan (placeholder), Overview, Gap Analysis (Gap Map + Dependencies diagrams + Gaps table), Decisions roll-up, Success/Negative Measures |
| `G<n>.md` | gap | Context, Outputs (incl. one proof-of-execution artifact), optional Key logic, gap-scoped ADRs, Tickets table (empty until decomposition) |
| `DISCOVERY.md` | discovery | Current State (≥2 lens diagrams), Desired State (same lenses), per-gap increment stack |

Work this state as follows:

1. **Dual deep research — two parallel subagents.**
   - Track A (codebase): map the current state relevant to the brief; every claim cites `file:line`.
   - Track B (web/SOTA): research the desired state; record every external URL consulted.
   Launch both with the Agent tool in one message so they run concurrently.
2. **Link verification.** Verify every Track B URL (WebFetch). Mark anything unverifiable with
   `<!-- LINK_NOT_VERIFIED -->`. A hallucinated citation is a critical failure.
3. **Synthesis.** Write `DISCOVERY.md` (2–3 Current lenses, the same lenses for Desired with
   consistent node IDs, and a `### G<n> increment` diagram per gap). Draft each `G<n>.md` stub
   (lead, Context, Outputs) and the index Overview, Gap Map (`flowchart TD`), Dependencies
   (`flowchart LR`), Gaps table, and Success/Negative Measures.
4. **Per-gap enrichment.** One fresh-context subagent per gap fills `## Outputs` (including the
   gap's committed proof-of-execution artifact) and optional `## Key logic`.
5. **Open decisions.** Every unsettled design choice becomes an `## ADR<n>.<m>` heading in its gap
   file marked `<!-- UNRESOLVED -->` with a Pros/Cons table. Do NOT silently decide for the user —
   `<!-- UNRESOLVED -->` markers are the *expected* output of bootstrap; the refinement state
   exists to settle them.
6. Leave the index `## Execution Plan` body as `<!-- TODO -->` placeholders — it is populated in
   the decomposition state, never now.

Hard rules:

- Every requirement is mandatory: no gap may describe its deliverable as optional, fallback, or
  skip-with-warning. A gap whose only evidence would be a stub or a mock of its own deliverable is
  mis-scoped — restate it until a real, committed, run-on-real-input artifact proves it.
- Use assumptions sparingly and mark each `<!-- ASSUMPTION: ... -->`; the exit gates treat them as
  open questions for refinement.
- Diagrams: hex colors only, every `fill:` paired with explicit `color:`, ≤ ~15 nodes per diagram;
  split dense diagrams rather than growing them.
