# State: execution — one ticket, red → green → (refactor)

The composed context below is exactly the working set for this turn: the index, the owning gap
file, and ONE assigned ticket (the lowest-numbered eligible ticket — selection is done by the
script; do not re-derive it). Work that ticket and only that ticket:

1. **RED** — write the test named in the ticket's `Test` row. Run the suite. Confirm the new test
   fails for the expected reason.
2. **GREEN** — write the minimum *real* code named in the `Implements` row. Run the suite. Confirm
   the new test passes and nothing regressed. Do not stub, mock the deliverable, or re-implement
   the behavior in a parallel path to force a pass.
3. **REFACTOR** (only if the ticket lists candidates) — apply while staying green; re-run the suite
   after each step.
4. Flip the ticket file's `- [ ] **Done**` checkbox to `- [x] **Done**`.
5. Update the index Progress table (done count, next eligible, blocked on).
6. Commit with message `T<n>.<m>: <ticket title>`.
7. STOP. The driver re-evaluates gates and issues the next turn.

## Blocked? Root-cause before rescoping

If implementing the ticket honestly seems to require a stub, a mock of its own deliverable, or a
parallel re-implementation, do NOT rescope first. Ask "why can't this be real yet?" repeatedly
(five times is usually enough — follow the causal chain, not the symptom). Most blockers dissolve
into real work: a missing fixture, an un-wired dependency, a step that belongs to an earlier
ticket. Do that work as part of this ticket.

Only two outcomes end a turn without a green ticket, and each is a marker the machine routes on:

- **Design ambiguity the spec does not resolve** → add an `<!-- UNRESOLVED -->` ADR placeholder
  (with a Pros/Cons table) under the owning gap file, leave the ticket `[ ]`, and STOP.
- **Genuine plan defect** (the root-cause chain bottoms out at "the gap as written cannot produce
  real evidence") → add a `<!-- CHANGE-REQUEST -->` marker under the owning gap file recording the
  root cause and what the ticket needs to become real, leave the ticket `[ ]`, and STOP.

Either marker transitions the machine back to refinement on the next `pgsm next`; never push
through with fake evidence instead.
