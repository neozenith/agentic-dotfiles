# State: decomposition — TDD vertical-slice tickets + Execution Plan

Decompose every gap into ticket files and populate the index Execution Plan. One subagent per gap
(parallel when there is more than one gap), each receiving only its gap file's content.

## Ticket structure

One ticket file per behavior: `G<n>-T<n>.<m>.md` (`<m>` 1-based within the gap), each a standalone
TDD vertical slice — one test → one minimum real implementation:

```markdown
# T<n>.<m>: <actor> <observable outcome>

> - **Gap:** [G<n>: <title>](./G<n>.md)
> - **Index:** [README.md](./README.md)

- [ ] **Done**

<One sentence: the precise, assertion-worthy contract.>

| | |
|--|--|
| Test | `path::test_name` — <assertion against the public interface, on real input> |
| Implements | `file` <symbol> — real production code, never a stub |
| Depends on | [T<a>.<b>](./G<a>-T<a>.<b>.md), … — or — |
```

`T<n>.1` is the **tracer bullet**: the smallest slice threading the gap's highest-risk,
load-bearing path end-to-end through the real production interface, producing the gap's first
proof-of-execution Output. Never the cheapest peripheral leaf. Mark it `_(tracer bullet)_`.

Reject any ticket that: bundles multiple tests (horizontal slice); asserts implementation detail
(call counts, private methods); verifies via DB inspection/log scraping instead of the public
interface; mocks an internal module or the gap's own deliverable seam (mock only true external
boundaries you do not own); re-implements production logic in a parallel throwaway path; or could
complete without ever running the real deliverable on real input.

## Dependency DAG

Fill each ticket's `Depends on` with ticket links (cross-gap allowed). The graph must be acyclic —
if a cycle appears, split the smallest ticket in the cycle into a minimal-seam + full-implementation
pair. Add a `## Tickets` table to each gap file linking its tickets.

## Execution Plan (index)

Replace the index `## Execution Plan` TODO placeholders with:

- **Runner note** — one paragraph: "execution is driven by the plan-gap state machine; each turn the
  driver emits the composed prompt for the next eligible ticket" (no self-referential loop prompt is
  needed — the script owns scheduling).
- **Progress** — one row per gap: tickets total, done count, todo count, next eligible, blocked on.
- **Done Criteria** — every ticket `[x]`; every Success Measure passes when executed; every gap's
  proof-of-execution Output committed; no `<!-- UNRESOLVED -->` / `<!-- CHANGE-REQUEST -->` markers.

Before stopping, verify: every gap has ≥1 ticket and a tracer producing its proof-of-execution
Output; every ticket file opens with `- [ ] **Done**` and has Test/Implements/Depends-on populated;
the DAG is acyclic; Progress totals match the ticket files.
