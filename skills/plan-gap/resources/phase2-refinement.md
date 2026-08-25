# Phase 2 — Iterative refinement loop (full playbook)

The step-by-step detail for Phase 2, referenced from `SKILL.md` → Workflow → Phase 2. `SKILL.md` holds
the one-line summary of each step; this file holds the mechanics. Paths are relative to
`.claude/skills/plan-gap/`.

Phase 2 converts the open design decisions surfaced in Phase 1 into settled ADRs. **The question loop
itself is not authored here** — it is the vendored Concise Decisions skill at
`vendor/concise-decisions/`. This playbook owns the two ends that vendored loop deliberately leaves to
its caller: **what counts as an ambiguity in a gap analysis spec**, and **what an answer does to the
file set**.

## Division of labour

| Owner | Owns |
|-------|------|
| `vendor/concise-decisions/SKILL.md` + its `resources/**` | the question contract: self-answering from decision records, ranking by cross-cutting impact, the pragmatic-default test, the nine-section briefing, the five-question check, the answer surface, the lens grammar, the TBD route family |
| This playbook | the ambiguity inventory (`<!-- UNRESOLVED -->` ADRs + the non-ADR sweep), the decision-record backends of a spec, how a settled decision is written into gap files and the index, how a TBD route lands in the documents, the exit gate |

Read `vendor/concise-decisions/SKILL.md` once before the first iteration — it is a runtime surface, load
it like any other resource. So are the files it names on demand: one shape file and one harness adapter
per question, plus its question template and TBD routes. Everything else in that tree — `README.md`,
`CLAUDE.md`, `docs/adrs/` — is the upstream maintainer's **development-time** material. It exists to
guide someone *editing* that skill; it is not loaded when the skill *runs*, is not a decision record for
this session, and is never cited as authority. Never edit any vendored file (`vendor/README.md`).

Read `resources/escalators-not-stairs.md` once before the first iteration too: a refinement answer that
quietly downgrades a requirement — turning a gap's real deliverable into an optional or fallback path —
is the failure this loop exists to catch, not propagate. "Graceful degradation" is never an option in a
question.

Repeat the cycle below until no `<!-- UNRESOLVED -->` markers remain and the file set is internally
consistent.

## Step 2a: Assemble the ambiguity inventory

This is the vendored loop's step 1 ("inventory the ambiguities"), specialised to a spec folder. Collect
every `<!-- UNRESOLVED -->` ADR entry across all `G<n>.md` gap files (an `<!-- UNRESOLVED -->`
placeholder is the *only* place a Pros/Cons table is allowed — see `resources/spec-body.md` →
"Unresolved ADRs"). Then sweep for ambiguity that has **no** ADR yet:

- Missing details an executor would have to guess (an unspecified format, threshold, library, schema).
- Implicit assumptions in the Outputs / Key logic of any gap, and every open `<!-- ASSUMPTION: … -->`.
- Requirements whose success is not yet falsifiable.
- Defaults you wrote into a spec file without permission — the vendored loop counts these as ambiguities
  even though nothing in the document looks open.

For each such gap, create a new `<!-- UNRESOLVED -->` ADR placeholder in the relevant gap file so the
question becomes rankable alongside the rest. Do not ask anything yet — first assemble the full open
set, then hand it to step 2b as one inventory.

## Step 2b: Self-answer, then rank

Run the vendored loop's steps 2–3 over that inventory. Before ranking anything, search the decision
records; an item a record already answers is **already decided** — apply it, cite the record, drop it
from the queue, and never ask it.

The vendored loop names *Decision records* as a role and resolves it per environment. In a gap analysis
spec that role resolves to, in order:

| Order | Backend | What it answers |
|---|---|---|
| 1 | The spec's own decisions: settled `ADR<n>.<m>` bullets in every `G<n>.md`, the index **Decisions (ADRs)** roll-up | decisions already made in this refinement |
| 2 | The spec's in-flight markers: `<!-- ASSUMPTION -->`, `<!-- DEFERRED -->`, `<!-- CHANGE-REQUEST -->`, and `DISCOVERY.md` (Current/Desired State, the per-gap increment stack) | seams already cut, and the state the plan is reasoning about |
| 3 | The **target project's** decision surface: its `docs/adrs/`, `CLAUDE.md` / `AGENTS.md` lenses, `STRATEGY.md` | binding decisions the plan must not contradict |
| 4 | The user's prior feedback in this session, and persisted memory | how this user decides, here and now |
| 5 | Knowledge bases reachable through tools (issue tracker, wiki, docs search) — searched on the decision's own nouns | decisions recorded outside the repo |

Supply these to the vendored loop explicitly; they are the plan-gap-specific resolution of its role
table and they replace it. Nothing under `vendor/` is a decision record for a run: the vendored
`docs/adrs/` is the upstream maintainer's development-time material, not this session's decisions, and
searching it wastes context on the wrong repository's history.

Then rank the remainder as the vendored loop directs, using the gap analysis's own impact axes:

1. How many distinct ADRs the answer resolves (directly or by cascade).
2. How many gaps those ADRs span.
3. How much downstream work it unblocks — a foundational decision other gaps build on outranks a leaf.

Prefer breadth: one answer that settles ADRs in G2, G5, and G6 beats three narrow questions. Show the
ranking, do not merely perform it — the question's *why this one first* names the open questions it
outranks. Everything else waits; a later answer may dissolve it.

If the top-ranked item passes the vendored loop's **pragmatic default** test (established convention,
prior feedback or a recorded lens pointing the same way, easily reversible, and no Type 2 failure
possible), settle it yourself: write the ADR in bulleted form with the default as the Decision, state it
in one line in passing, and re-rank. Do not spend a question on it.

## Step 2c: Ask exactly one question

Compose it with the vendored loop's step 4 — its shape table, harness adapter, nine-section template,
and five-question check apply verbatim and unmodified. Nothing in this playbook shrinks a section or
substitutes a cheaper form; there is no cheap question.

Plan-gap overlays only these bindings:

- **`DECISION-ID`** is the ADR ID the question settles — `ADR<n>.<m>`. Where the question spans several,
  use the highest-leverage one and list the rest under *what it affects*.
- **Section 2 (why decide this now)** names the specific `G<n>` gaps and `ADR<n>.<m>` IDs the answer
  resolves, plus the cascade into Outputs, Key logic, Measures, and the `DISCOVERY.md` diagrams.
- **Section 3 (already settled)** names the backends of step 2b that were searched, per the `Checked:`
  contract — "nothing in the spec or the project's ADRs bears on this" is a valid finding; silence is
  not.
- **Section 5 (Options)** carries previews that are complete outcomes on the spec's **real** content: the actual gap's Outputs
  block as it would read under each option, the actual diagram, the actual ticket contract sentence —
  never an illustrative fragment. The spec is on disk; there is no excuse for a synthetic preview.
- **GitHub-issue spec** — ask in the conversation through the sensed harness adapter, then mirror the
  briefing as an issue **comment** (append-only, never a body edit) so the record lives with the issue.
  See `resources/gh-issues.md`. The comment carries sections 1–8; the conversation carries the answer
  surface.

## Step 2d: Incorporate the answer

The vendored loop's step 5 says to cascade the choice *and* the reasoning, and to record both where
decisions live for this work. For a gap analysis spec, "where decisions live" is the gap file and the
index roll-up, and the cascade is this:

1. **Settle the affected ADRs.** In each owning gap file rewrite the placeholder from its
   `<!-- UNRESOLVED -->` Pros/Cons form into the settled bulleted form — `ADR<n>.<m>:` heading +
   **Decision** / **Why** / optional **Rejected** / **Superseded** (`resources/style.md` rule 8) — and
   delete the marker and the table.
2. **Write the lens as the Why.** The vendored loop captures reasoning as a four-clause lens; it maps
   onto the ADR bullets without inventing a new field:

   | Lens clause | Lands in |
   |---|---|
   | **Given** | the opening clause of **Why** — the context that makes this the right call today |
   | **We prefer … over …** | **Decision**, with the named alternative in **Rejected** |
   | **Because** | the body of **Why** |
   | **Unless** | the closing clause of **Why** — the condition that would invert it, or "unconditional" |

   An ADR whose Why has no *Unless* is an assertion, not a decision: a later run cannot tell when it
   stopped applying. If the user named an option but no reasoning, infer the lens from the briefing,
   state it in one line as a statement (never a second question), and mark the entry
   `<!-- LENS: unconfirmed -->` until they confirm or edit it.
3. **Update the roll-up.** Add or update the corresponding row in the index (`README.md`) **Decisions
   (ADRs)** table — columns ADR, Decision, Why; the ID links to its owning gap file.
4. **Cascade the choice.** Propagate consequences into the `## Outputs` / `## Key logic` of every
   affected gap, and into the index Success/Negative Measures. If the decision changes an architecture,
   update the relevant `DISCOVERY.md` lens diagram and the gap's increment diagram (the gap file links
   to it by anchor — `DISCOVERY.md#g<n>-increment`).
5. **Cascade the lens.** Apply the reasoning to every *other* open item it settles, related or not, and
   drop those from the inventory citing the lens. State which ambiguities cascaded resolved and whether
   each fell to the choice or to the lens alone.
6. **Restructure if needed.** If gaps were added, merged, split, or reordered, update the index Overview
   gap list, the Gaps table, the Gap Map, and the Dependencies diagram.

Use the Edit tool for local files — a precise diff, never a whole-file rewrite. A refinement edit never
flips a `[ ]`↔`[x]` checkbox: done state is execution data, not content (`resources/style.md` →
Conventions). For a GitHub-issue spec, read the body, modify the section, write the full body back via
`gh issue edit --body`, then post a one-line sync note as a comment.

**If the user overruled the skill itself** — rejected the framing, called the question premature,
corrected the ranking, or vetoed a cascade — that is a defect in *this skill*, not a decision about the
plan. It does not belong in the spec and it does not belong in a runtime file. Say so in the turn, and
carry it to the skill's `CLAUDE.md` ADR log as a maintenance change: a new ADR whose Lens states how the
next question of that class should be composed, plus the edit to `SKILL.md` or this playbook that
enforces it. A ruling that changes behaviour must change a loaded surface; a ruling recorded only in a
document the run never loads changes nothing.

### When the answer is a TBD route

`vendor/concise-decisions/resources/tbd-routes.md` defines what each route means; the spec defines what
it does to the documents. The ADR stays `<!-- UNRESOLVED -->` in every case except `defer`:

| Route | Effect on the spec |
|-------|--------------------|
| `explain` | Revise the unclear part of the briefing — the fuller preview, the constraint, the prior ADR spelled out — and re-ask the **same** question. The spec is untouched. |
| `show` | Build one complete artifact per option where the user can open it: the rendered `DISCOVERY.md` lens diagram under each option, the gap's Outputs block as it would read, a sample of the real output file. Attach them and re-ask. |
| `spike` | The experiment becomes a **ticket** under the owning gap (`G<n>-T<x.y>.md`), timeboxed, with the question it must answer as its contract sentence. Its outcome is a learning written next to the ADR; then re-ask, or settle it under the pragmatic-default test if the learning makes one option obviously right. |
| `defer` / `handoff` | The **whole briefing** — all eight sections plus a `Revisit when:` line — is logged as a ticket per the vendored route's backend order (issue tracker → `gh issue create` → the spec's own backlog → `docs/handoffs/<ADR-ID>.md`). Mark the seam in the gap file: `<!-- DEFERRED: <seam> → <ticket ref> -->`, and replace the `<!-- UNRESOLVED -->` marker with a settled ADR whose Decision is the provisional recommendation, explicitly labelled provisional. Deferring is a scope decision and is recorded as one. |
| `other` | Render the described option at the same detail as the rest — complete preview, pros, cons, comparison row — and re-ask with it included. |
| `task` | Write the prerequisite as a precise checklist naming who and what. If it is work the plan owns, it becomes a ticket or a new gap; if it is human-side work (an approval, an access grant, a meeting), it is a `<!-- BLOCKED: <what> -->` note on the ADR and the loop moves to the next-ranked question. |

## Step 2e: Re-evaluate, then loop or exit

Re-rank before asking anything else — yesterday's #2 is rarely today's #1 after a cascade. If a question
opened new sub-questions, fold them into the ranking for the next iteration; do not ask them now.

Exit the loop when **all** hold:

- No `<!-- UNRESOLVED -->` markers remain in any gap file.
- No open `<!-- ASSUMPTION: … -->` or `<!-- BLOCKED: … -->` that would change the design, a gap's
  Outputs, a Measure, or user-visible behaviour.
- The set is internally consistent: every ADR appears in both its gap file and the roll-up, and every
  gap's Outputs and Measures reflect the settled decisions.

Wanting to ask a tenth-priority question "to be safe" is the signal to exit: choose conservatively,
leave an `<!-- ASSUMPTION: … -->` marker, and surface it in the status line. Otherwise return to Step
2a. When the loop exits, declare the spec ready and move to Phase 3.

## Status line each iteration

After every iteration, show the user a brief status:

- Which file(s) and section(s) were updated.
- Which ambiguities cascaded resolved, and whether by the choice or by the lens.
- Roughly how many ambiguities remain.
- The next most important question — or "complete, moving to validation".
