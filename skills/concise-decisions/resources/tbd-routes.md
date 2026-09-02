# TBD routes — answers that are not decisions

Part of the `concise-decisions` skill (see [../SKILL.md](../SKILL.md)). Load
when composing section 8 of the template or when the user's answer is a TBD
route.

## Why a route family, not an "other"

An "other / describe a different approach" escape lets the user redirect, but
it gives them no way to say *"I cannot decide this from what you've shown
me"* without aborting the question. That cornering was observed in rehearsal:
the user had three options and an "other", and none of them was the true
answer, which was "not yet". The fix is one option whose annotation (or reply
line) names a **route**. The route is an *answer*; only one of them is a
(partial) decision.

There is a difference between **answering a question** and **making a
decision**. Every route below is the first without the second.

## The routes

The first four are the canonical family, in the user's own order and
meaning. Two further answers joined them: `other` proved necessary in
rehearsal (the user was cornered by three bad choices), and `task` was
adopted from wayfinding research and user-confirmed — the "work before we
can decide" case that `defer` and `spike` do not cover.

| Route | User means | Skill does next | Decision status |
|-------|------------|-----------------|-----------------|
| `explain: <part>` | Despite best efforts I need part of the existing explanation **expanded and revised** before I can make an informed decision | **Revise** that part of the body — rewrite it, do not append to it: more of the cascade, a fuller preview, the constraint that was unclear, the prior decision spelled out — and ask the **same** question again. Change the options only if the revision shows one was wrong. | none |
| `show` | The question is visual or interactive; text previews are not enough — I need **real prototypes** before an informed decision | Create one **complete** artifact per option (a rendered page, a diagram, a sample output file, a plan dry-run) somewhere the user can open it, then **revise the question** with the artifacts attached. When text previews already *are* the artifact, say "not useful for this decision" in the route table rather than promising nothing. | none |
| `spike: <question>` | We cannot blindly trust claimed performance metrics or benchmarks; we need to **empirically collect our own data** | Run (or propose) the smallest experiment on the user's real data that would decide it, inside a **timebox** — propose one (e.g. 30 min, one script, one run) and stop when it ends whether or not it converged. Its outcome is a **learning**: write it down next to the decision, then re-ask, or resolve if the learning makes one option obviously right under the pragmatic-default test. | none yet — the learning routes it |
| `defer` / `handoff` | The question is **valid** but **not important right now** | **Log the entire question — every section of the briefing and the recommendation — as a ticket in the backlog** (see *Where the ticket goes*), with the condition that must be true before it is revisited. Then mark the seam as a **scope boundary** on the decision record (`<!-- DEFERRED: <seam> → <ticket ref> -->` or the host format's equivalent). `handoff` names who, or which session, picks it up. Where work cannot wait, continue with the recommendation as an explicitly *provisional* assumption. | **partial** — deferring is itself a decision about scope and is recorded as one |
| `other: <description>` | None of these | Render the described option at the **same** level of detail as the others (complete preview, pros, cons, comparison row) and re-ask with it included. | none |
| `task: <what>` | Human-side work must happen before anyone can decide — a meeting needs to occur, a person needs to research it, an authority needs to give a go/no-go, access must be granted, data must be moved so its shape can be seen | Hand the user a precise checklist naming who and what, or do it yourself where you can; the answer records what was done and any resulting facts later decisions depend on. Unlike `defer`, the decision *is* important now; unlike `spike`, the agent cannot produce the missing input. | none |

## Where the ticket goes (`defer` / `handoff`)

The backlog is an **issue-tracking role**, not a fixed backend. Sense in this
order, use the richest one present, and say which was chosen:

| Order | Backend | Sense by |
|---|---|---|
| 1 | Issue-tracker tool in the session (Jira, Linear, GitHub Issues via an MCP server) | the tool is listed |
| 2 | `gh issue create` | `gh auth status` succeeds and the repo has a GitHub remote |
| 3 | The plan/spec file's own backlog or handoff section | the file being refined has one |
| 4 | A local markdown ticket — `docs/handoffs/<DECISION-ID>.md` or the project's existing `issues/` directory | always available: the **universal floor** |

The ticket **is the question**: title = `<DECISION-ID> — <decision sentence>`;
body = sections 1–8 verbatim (decision, why now, already settled,
reversibility, every option with its preview, compare, recommendation, the
remaining routes) plus a `Revisit when:` line. A one-line ticket loses the
briefing the user would need to decide later, which is the whole cost being
deferred.

## Presenting the routes

- In a **session feed** the routes are a table with "what happens next" per
  route, placed after the recommendation and before the reply footer.
- In a **structured picker** the routes ride on the last option ("Not a
  decision yet → annotate the route"); its preview card lists the route names
  with a one-line meaning each. The user picks it and names the route in the
  annotation.
- Every route line is **specific to this decision**: `explain` names the
  part most likely to be unclear, `show` names the artifact or says it is not
  useful here, `spike` names the actual experiment and its timebox, `defer`
  names the revisit condition.
- The visible label for the non-decision option is the word **TBD** (or
  "Not a decision yet"), never a single letter.
- Reply footer's route line, everywhere:
  `Alternatively choose from <explain|show|spike|defer|handoff|other|task> and your reasoning to revise/iterate.`
  A bare route name in a reply is a TBD answer; the `TBD:` prefix is
  accepted but never required.

## Mapping to roadmap/wayfinding vocabularies

Where another skill classifies open items by type, the routes correspond to:
`spike` ↔ *Research*, `show` ↔ *Prototype*, `task` ↔ *Task*, `defer` ↔
*Not yet specified*. Use that skill's nouns in its documents; use the route
names in the question.
