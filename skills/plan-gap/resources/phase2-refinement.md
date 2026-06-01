# Phase 2 — Iterative refinement loop (full playbook)

The step-by-step detail for Phase 2, referenced from `SKILL.md` → Workflow → Phase 2. `SKILL.md` holds
the one-line summary of each step; this file holds the mechanics. Paths are relative to
`.claude/skills/plan-gap/`.

Phase 2 converts the open design decisions surfaced in Phase 1 into settled ADRs by asking the human
**one maximally-leveraged question at a time**. The driving metric is *questions asked* — every
iteration must reduce the total ambiguity count, never grow it. Read
`resources/escalators-not-stairs.md` once before the first iteration: a refinement answer that quietly
downgrades a requirement (turns a gap's real deliverable into an optional/fallback path) is the failure
this loop exists to catch, not propagate.

Repeat the five-step cycle below until no `<!-- UNRESOLVED -->` markers remain and the file set is
internally consistent.

## Step 2a: Scan unresolved ADRs

Collect every `<!-- UNRESOLVED -->` ADR entry across all `G<n>.md` gap files (an `<!-- UNRESOLVED -->`
placeholder is the *only* place a Pros/Cons table is allowed — see `resources/spec-body.md` →
"Unresolved ADRs"). Then sweep for ambiguity that has **no** ADR yet:

- Missing details an executor would have to guess (an unspecified format, threshold, library, schema).
- Implicit assumptions in the Outputs / Key logic of any gap.
- Requirements whose success is not yet falsifiable.

For each such gap, create a new `<!-- UNRESOLVED -->` ADR placeholder in the relevant gap file so the
question becomes rankable alongside the rest. Do not ask anything yet — first assemble the full open set.

## Step 2b: Rank by cross-gap impact

From the full open set, pick the **single** question whose answer resolves the most ADRs at once.
Prefer breadth: one answer that settles ADRs in G2, G5, and G6 beats three narrow questions. Score each
candidate by:

1. How many distinct ADRs it resolves (directly or by cascade).
2. How many gaps those ADRs span.
3. How much downstream work it unblocks (a foundational decision that other gaps build on ranks above a
   leaf decision).

The top-ranked question is the one to ask this iteration. Everything else waits — a later answer may
dissolve it.

## Step 2c: Ask one question

Present exactly one question to the user. Never dump a list. The message must explain:

- **Why now** — why this is the highest-leverage question at this moment.
- **What it affects** — list the specific `G<n>` gaps and `ADR<n>.<m>` IDs it resolves.
- **Cascade** — the other ambiguities the answer would knock out.
- **Your researched recommendation(s)** — a short ranked list of plausible options with one-line
  reasoning each, so the user can confirm a sensible default with a single word rather than compose an
  answer from scratch.

For a **GitHub-issue spec**, post the question as an issue **comment** (append-only), not a body edit —
see `resources/gh-issues.md`. For a local spec, ask in the conversation.

## Step 2d: Incorporate the answer

Propagate the answer through the file set:

1. **Settle the affected ADRs.** In each owning gap file rewrite the placeholder from its
   `<!-- UNRESOLVED -->` Pros/Cons form into the settled bulleted form — `ADR<n>.<m>:` heading +
   **Decision** / **Why** / optional **Rejected** / **Superseded** (`resources/style.md` rule 8) — and
   delete the marker and the table.
2. **Update the roll-up.** Add or update the corresponding row in the index (`README.md`) **Decisions
   (ADRs)** table — columns ADR, Decision, Why; the ID links to its owning gap file.
3. **Cascade.** Propagate consequences into the `## Outputs` / `## Key logic` of every affected gap, and
   into the index Success/Negative Measures. If the decision changes an architecture, update the
   relevant `DISCOVERY.md` lens diagram and the gap's increment diagram (the gap file links to it by
   anchor — `DISCOVERY.md#g<n>-increment`).
4. **Restructure if needed.** If gaps were added, merged, split, or reordered, update the index Overview
   gap list, the Gaps table, the Gap Map, and the Dependencies diagram.

Use the Edit tool for local files — a precise diff, never a whole-file rewrite. A refinement edit never
flips a `[ ]`↔`[x]` checkbox: done state is execution data, not content (`resources/style.md` →
Conventions). For a GitHub-issue spec, read the body, modify the section, write the full body back via
`gh issue edit --body`, then post a one-line sync note as a comment.

## Step 2e: Re-evaluate

Reassess the remaining open set. If a question opened new sub-questions, fold them into the ranking for
the next iteration — do not ask them now. Exit the loop when **both** hold:

- No `<!-- UNRESOLVED -->` markers remain in any gap file.
- The set is internally consistent (every ADR appears in both its gap file and the roll-up; every gap's
  Outputs and Measures reflect the settled decisions).

Otherwise return to Step 2a. When the loop exits, declare the spec ready and move to Phase 3.

## Status line each iteration

After every iteration, show the user a brief status:

- Which file(s) and section(s) were updated.
- Roughly how many ambiguities remain.
- The next most important question — or "complete, moving to validation".
