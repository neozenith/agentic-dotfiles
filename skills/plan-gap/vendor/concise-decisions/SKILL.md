---
name: concise-decisions
description: "Concise Decisions. Use mid-session when two or more ambiguities have accumulated and you'd otherwise interrupt the user with several questions, and whenever a design decision must be put to the user. Self-answers first from existing decision records (ADRs, CLAUDE.md lenses, plan decisions, knowledge bases), then consolidates what remains into the single highest-leverage decision question: a full briefing (decision sentence, why now and why this one first, already settled with what was checked, reversibility, complete previews on real data, pros/cons, recommendation, TBD routes explain/show/spike/defer) plus ONE answer surface that captures the choice AND the user's reasoning, then cascades the answer and its reasoning across every related ambiguity before asking another. Loads one question-shape file and one harness adapter on demand. Skip when a single trivial, reversible ambiguity is open: state a default in passing and move on."
user-invocable: true
---

# Concise Decisions

> Every question you ask the user is a tax on their attention. Spend it like
> it is the scarcest resource in the loop — because it is.

Concise Decisions is the mid-session ambiguity resolution loop. Invoke it when
**two or more open decisions** block your work and you are tempted to
interrupt the user with a chain of questions. Do not dump the list. Run the
loop.

## The requirement every question must meet

> The user must be able to make an **informed decision** and **give their
> reasoning** — from the answer surface alone, coming in cold.

The reasoning is the product. A captured "why" becomes the decision record's
lens (*we value X over Y*), and a codified lens is what lets later questions
be answered without asking. A question that captures the choice but loses the
why has failed.

## When to invoke

- You have a queue of clarifying questions about scope, naming, behaviour,
  data shape, format, or trade-offs.
- You are about to ask "should I X? and also Y? and also Z?".
- You drafted code with several `TODO: confirm with user` markers, or hold
  more than one pending `<!-- ASSUMPTION: … -->`.
- You started one branch and found that unmade decisions block other branches.
- A planning skill (e.g. a gap-analysis refinement phase) needs to put an
  architectural decision to the user.

If exactly one ambiguity is open **and** it passes the pragmatic-default test
below, state the default and move on. Otherwise run the loop — even for one
question, the question itself still follows step 4 in full.

## The loop

Repeat until no material ambiguity remains:

1. **Inventory the ambiguities.** Privately list every open decision as
   "I don't know whether X, which would determine Y." Include implicit ones:
   assumptions you quietly made, defaults written without permission, code
   paths skipped because the input shape was unclear.
2. **Check decision records, then rank by cross-cutting impact.** Before
   ranking, search the *Decision records* (below) for every item in the
   inventory. An item a recorded decision answers is **already decided**:
   apply it, cite the record, drop it from the queue — never ask it. An item
   a recorded *lens* answers is a pragmatic-default candidate for step 3.
   Then pick the single remaining question whose answer resolves the *most*
   downstream ambiguities. Knowing the data shape often resolves naming,
   validation, and storage at once — ask that.
3. **Resolve it yourself if you can.** See *Pragmatic default* below. If all
   four criteria hold, pick it, state it in one line, move on. The user's
   attention is more expensive than your deliberation.
4. **Otherwise ask exactly one question** — composed as described in the next
   section. Never more than one decision per turn.
5. **Cascade the answer and the reasoning.** Apply the *choice* to every
   related ambiguity from step 1, and apply the *reasoning* — now a lens — to
   any ambiguity it settles, related or not. Record the decision *and the
   user's reasoning* where decisions live for this work (ADR, plan file,
   in-code comment), update in-flight code and the queue. See *After the
   answer*.
6. **Re-evaluate, then loop or exit.** Re-rank before asking anything else —
   yesterday's #2 is rarely today's #1 after a cascade.

## Decision records — check before you ask

"Decision records" is a **role**, not a place. Resolve it in this order, use
every backend that exists, and name what you checked in the question's
`Already settled` line (`Checked: …` — "nothing bears on this" is a valid
finding; silence is not):

| Order | Backend | What it answers |
|---|---|---|
| 1 | The work's ADR surface (`docs/adrs/`, `docs/adr/`, `ADRs.md`, `decisions/`) and its `CLAUDE.md`/`AGENTS.md` lenses | binding decisions and the reasoning to reuse |
| 2 | The plan, spec, or gap-analysis file being refined: its Decisions section, `<!-- DECISION -->` / `<!-- ASSUMPTION -->` / `<!-- DEFERRED -->` markers | decisions made in-flight, and seams already cut |
| 3 | The user's prior feedback this session, and persisted memory | how this user decides, here and now |
| 4 | Knowledge bases reachable through tools (issue tracker, wiki, docs search) — search the decision's own nouns | decisions recorded outside the repo |

Searching is cheaper than asking. A question whose answer was sitting in a
record is the failure this skill exists to prevent.

## Step 4 — composing the question

A question is **one message with a fixed anatomy** followed by **one answer
surface**. Build it in this order:

1. **Pick the shape** and load its file (one only):

   | Shape | Recognise it when | Load |
   |-------|-------------------|------|
   | Exclusive choice | 2–3 mutually exclusive options | [resources/shapes/exclusive-choice.md](resources/shapes/exclusive-choice.md) |
   | Subset as permutations | several options can be chosen together | [resources/shapes/subset-as-permutations.md](resources/shapes/subset-as-permutations.md) |
   | Binary | exactly two real options | [resources/shapes/binary.md](resources/shapes/binary.md) |
   | Low stakes | highly reversible, nothing downstream depends on it, yet the lens is worth recording | [resources/shapes/low-stakes.md](resources/shapes/low-stakes.md) |
   | Resolved by cascade | a prior decision narrowed this one but left constraints competing | [resources/shapes/resolved-by-cascade.md](resources/shapes/resolved-by-cascade.md) |

2. **Sense the harness** and load its adapter (one only). Identity is not
   capability — the adapter decides only where the answer is typed:

   | Signal | Load |
   |--------|------|
   | `CLAUDECODE` set, or a structured single-select question tool with per-option free text is available | [resources/harnesses/claude-code.md](resources/harnesses/claude-code.md) |
   | `CODEX_SANDBOX`, `CODEX_PROXY_CERT`, or any `CODEX_ENV_*` set | [resources/harnesses/codex.md](resources/harnesses/codex.md) |
   | anything else (chat, cloud runner, unknown) | [resources/harnesses/session-feed.md](resources/harnesses/session-feed.md) |

   Announce the adapter in one clause if it is not the structured one.

3. **Fill [resources/question-template.md](resources/question-template.md)**
   using the shape's variant. The anatomy, in order:

   | # | Section | One-line contract |
   |---|---------|-------------------|
   | 1 | Decision to make | one complete sentence: the choice and its operating constraints |
   | 2 | Why decide this now | blocked work; downstream cascade; **why this one first** — the other open questions it outranks; what is *outside* this decision |
   | 3 | Already settled | `Checked:` the decision records searched; the prior decisions that bear on this and *why they do not answer it* |
   | 4 | Reversibility | low / high / asymmetric, honestly, with affected surfaces |
   | 5 | Options | 2–3 real ones; title carries `(Recommended)`; **complete** preview on the user's real data; `Pros:` and `Cons:` on separate lines |
   | 6 | Compare | one table with domain-specific columns |
   | 7 | Recommendation | the option and one sentence of why |
   | 8 | TBD routes | the answers that are not decisions: `explain`, `show`, `spike`, `defer`/`handoff` (+ `other`, `task`) — [resources/tbd-routes.md](resources/tbd-routes.md) |
   | 9 | Answer channel | one surface that captures option **and** reasoning; says what the reasoning becomes |

4. **Run the five-question check** as the user, seeing only the answer
   surface, cold. All five must be yes; if any is no, fix the question — do
   not ask it. The wording is the user's own:

   1. Can I make an **informed decision** from what is presented?
   2. Do I understand why **this** question is being asked **now** — why it is
      the next most impactful question worthy of my attention?
   3. Do I understand why prior decisions do **not** already answer it — were
      existing decision records and knowledge bases checked, and does the
      question say so?
   4. Can I attach my reasoning to whichever option I pick? Multichoice or
      multi-select without space for free text is a failure.
   5. Can I give a **TBD answer** — an answer that is not a decision —
      without aborting?

5. **Send it.** Body first, then the answer surface, in the same turn.
   Nothing else in the turn: no meta instructions, no second question.

### Rules that do not bend

- **There is no cheap question.** Low stakes shrinks the *previews*; it never
  removes a section. A compressed briefing with pointer labels fails.
- Previews are **complete outcomes on the user's real data** (their actual
  command, file, path, output), never illustrative fragments. If you lack the
  data, get it before asking.
- Option titles are **self-describing** — they must make sense with the body
  off-screen. `B (Recommended): each --match opens a group` passes;
  `Confirm C` fails.
- The recommendation is in the option **title** and in the Recommendation
  line. Never only after the previews.
- Conciseness never damages grammar. A decision sentence that reads as a
  fragment fails check 1.
- Rehearsal or meta text ("grade this", "don't answer yet") stays outside
  the question surface.

## After the answer

1. Confirm the choice in one line and quote the reasoning.
2. **Extract the reasoning.** If the reply names an option but no why, do
   not ask again: infer the lens from the briefing (the pros the user
   accepted, the cons they tolerated), state it in one line — "recording the
   why as: *given X, we prefer Y over Z because …* — correct me if that is
   wrong" — and mark the record `<!-- LENS: unconfirmed -->` until the user
   confirms or edits it. A statement in passing, not a second question.
3. Record decision + reasoning where decisions live for this work. The
   reasoning is written as a **lens in four clauses**:

   | Clause | Holds |
   |---|---|
   | **Given** | the context that makes this the right call *today* |
   | **We prefer** | X, **over** the named alternative Y |
   | **Because** | why the preference follows from that context |
   | **Unless** | the condition that would invert it — or "never; unconditional" |

   A lens with no `Unless` is an assertion, not a decision: nothing in it
   says what it depended on, so a later run cannot tell when it stopped
   applying. Name the rejected alternative — a preference with no `over` is
   the rule restated.
4. State which other ambiguities cascaded resolved and how each was applied
   — by the choice, or by the lens alone.
5. If the answer was a TBD route, act per
   [resources/tbd-routes.md](resources/tbd-routes.md): `explain` revises the
   unclear part and re-asks; `show` builds one real artifact per option and
   re-asks; `spike` runs a timeboxed experiment whose outcome is a learning;
   `defer`/`handoff` logs the **entire question and recommendation** as a
   backlog ticket and records the scope seam; `other` renders the new option
   and re-asks; `task` hands over the prerequisite work.
6. Re-rank (step 6). Ask the next question only if one is still needed.

## Pragmatic default — when to skip the question

This is distinct from *already decided*: a decision record that answers the
question settles it outright (step 2 — apply and cite, no criteria needed).
The pragmatic default is for questions **no record answers**. Pick the option
yourself when **all four** hold:

- An established convention in the surrounding code, framework, or ecosystem
  already points to one answer.
- The user's prior feedback, memory, or a recorded lens (reasoning from a
  *different* decision) points the same way.
- The decision is **easily reversible** — a rename, a flag flip — not a
  schema, a public API, or a serialised data shape.
- Picking wrong cannot cause a Type 2 failure (code that looks correct but
  silently misses the requirement; see `escalators-not-stairs`).

If any is missing, ask. When you skip, state the default in one line in
passing — that is a statement, not a question, and the only legitimately
cheaper form.

## What counts as done

Exit when no remaining ambiguity would change the design, the API surface,
the data shape, or user-visible behaviour, and the rest are local, reversible,
and within conventions you can apply. Wanting to ask a tenth-priority question
"to be safe" is the signal to exit: choose conservatively, leave an
`<!-- ASSUMPTION: … -->` marker, surface it in the end-of-turn summary.

## Never

| Anti-pattern | Why it fails |
|--------------|--------------|
| Several questions in one turn, or a multi-question wizard | answer 1 cannot cascade into 2–n |
| Asking what a decision record already answers | the record was there to be read; check 3 fails and the user's attention was spent for nothing |
| Multi-select | a subset can be chosen but not *why* per option — use permutations |
| Any picker, single- or multi-select, with no free text on the chosen option | the choice is captured and the reasoning is lost — check 4 fails |
| Picker or option list with no briefing | reasoning crammed into labels, truncated |
| The artifact inside a preview pane | truncates; the body carries the artifact, the pane carries a card |
| Pointer labels (`Confirm C`, `Veto → A`) | meaningless when the body is not in view |
| A compressed "cheap" briefing | check 1 fails |
| Only an "other" escape | no way to answer "not yet" |
| No recommendation | you did the research — pick a default |
| Padding to three options when two are real | wastes the frame |
| Asking before cascading | the previous answer may already have resolved it |
| Treating "graceful degradation" as an option | a silent fallback is a Type 2 failure, not a choice |

## Resources

This file and `resources/` are the **only runtime authority**, with no
exceptions. `README.md`, `CLAUDE.md`, and `docs/adrs/` are development-time
documents: read them when *editing* the skill, never cite them as authority
when *running* it. This skill keeps no learning store of its own — what it
learns about how to ask becomes an ADR **and** a change to this file or a
`resources/` file, which is what the next run actually loads.

| File | Load when |
|------|-----------|
| [resources/question-template.md](resources/question-template.md) | composing any question |
| [resources/tbd-routes.md](resources/tbd-routes.md) | composing section 8, or acting on a TBD answer |
| `resources/shapes/*.md` | one per question, chosen in step 4.1 |
| `resources/harnesses/*.md` | one per session, chosen in step 4.2 |
| The work's own decision records (role, resolved per *Decision records* above) | step 2, every loop — before ranking, never after asking |

## Relationship to other skills

- `escalators-not-stairs` — the requirement-integrity guardrail. This skill
  asks *which* requirement to implement; that one ensures no option silently
  weakens a stated requirement.
- Planning skills with an iterative refinement phase use this loop verbatim
  for their decision questions; this skill owns the question contract, they
  own what a `defer`/`spike`/`show` answer does to their documents.
