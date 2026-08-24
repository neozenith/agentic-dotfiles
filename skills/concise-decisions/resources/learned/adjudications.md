# Learned: user adjudications

Self-curated learning file (skill rules, statefulness pathway 2). This file is **evidence, not rules**. Every entry
below has been promoted to an ADR, and the ADR is where the rule lives — apply the ADR, do not re-derive a rule from
the user's wording here.

Entries are **already-decided**: do not re-litigate them. Each has a stable `ADJ-NN` id that the ADRs cite in their
`Provenance` row, so an ADR can always be traced back to the moment and the words that forced it. Entries are deleted
only when a harness or model change invalidates them, which also supersedes their ADR.

Read this file at the first question of a session, and as backend 3 of the decision-records search (ADR-0008).

## Rulings

| ID | Date | Ruling, in the user's words (abridged) | ADR |
|---|---|---|---|
| ADJ-01 | 2026-08-22 | "Multi-question wizard SUCKS because it does not cascade information from one response into answering others and should NEVER be used." | [0012](../../docs/adrs/0012-one-decision-per-turn.md) |
| ADJ-02 | 2026-08-22 | "Single-select radio list OFTEN does not give me the 'Other' free-text option … so I am cornered into 3 bad choices." | [0013](../../docs/adrs/0013-free-text-on-the-chosen-option-is-the-contract.md), [0001](../../docs/adrs/0001-two-surfaces-briefing-then-answer-channel.md) |
| ADJ-03 | 2026-08-22 | "Single select with preview is sometimes ok, because it means I can pick one of the options and add annotations … Which IS THE POINT." | [0013](../../docs/adrs/0013-free-text-on-the-chosen-option-is-the-contract.md), [0001](../../docs/adrs/0001-two-surfaces-briefing-then-answer-channel.md) |
| ADJ-04 | 2026-08-22 | "Multi-select can also have the same failure mode where I want to pick a subset, AND ALSO give my reasoning WHY." | [0005](../../docs/adrs/0005-no-multi-select-composing-options-become-permutations.md) |
| ADJ-05 | 2026-08-22 | "The model often attempts to render or describe something in a preview but it gets cut off … better laid out as previews in the session log." | [0014](../../docs/adrs/0014-previews-are-complete-outcomes-on-real-data.md), [0001](../../docs/adrs/0001-two-surfaces-briefing-then-answer-channel.md) |
| ADJ-06 | 2026-08-23 | "Listing the individual multi-select options BEFORE listing the recommended subsets would have been easier." | [0005](../../docs/adrs/0005-no-multi-select-composing-options-become-permutations.md) |
| ADJ-07 | 2026-08-23 | Low-stakes v1: "zero pre information about what 'Take C' or 'Veto -> A' meant." | [0002](../../docs/adrs/0002-no-cheap-question-form.md) |
| ADJ-08 | 2026-08-23 | "We need the escape hatch to include a 'Wait what?' or a 'Please expand' or an 'unsure' option which is an _answer_ but it is NOT a _decision_." | [0003](../../docs/adrs/0003-tbd-route-family-defer-is-partial-decision.md) |
| ADJ-09 | 2026-08-23 | "Rename `waitwhat` to `explain`. `defer` can also accept `handoff`. `defer` is a form of partial decision … creating a scope boundary." | [0003](../../docs/adrs/0003-tbd-route-family-defer-is-partial-decision.md) |
| ADJ-10 | 2026-08-23 | "Sometimes the answer … would be to carve it out as a handoff … sometimes the question could be quite visual … sometimes we need to gather our own data and benchmarks … a spike." | [0003](../../docs/adrs/0003-tbd-route-family-defer-is-partial-decision.md) |
| ADJ-11 | 2026-08-23 | The five checks: informed? why now? why not already answered? can I add my reasoning? can I give a TBD answer? | [0007](../../docs/adrs/0007-five-question-check-is-the-acceptance-rubric.md) |
| ADJ-12 | 2026-08-23 | Codex series: fragments failed; pros/cons need separate lines; recommendation in the title; context needs labelled structure; `T` → `TBD`; meta text out of the question. | [0015](../../docs/adrs/0015-the-briefing-is-scanned-not-read.md), [0014](../../docs/adrs/0014-previews-are-complete-outcomes-on-real-data.md), [0006](../../docs/adrs/0006-text-feed-is-a-first-class-adapter.md) |
| ADJ-13 | 2026-08-23 | "Force the agent to leverage existing ADRs to self answer questions." / "Have you checked existing decision records and knowledge bases?" | [0008](../../docs/adrs/0008-check-decision-records-before-asking.md) |
| ADJ-14 | 2026-08-23 | "Why is it the next most impactful question worthy of my attention?" | [0019](../../docs/adrs/0019-ranking-is-shown-not-only-performed.md) |
| ADJ-15 | 2026-08-23 | "Multichoice and Multi-select without space for freetext is a failure." | [0013](../../docs/adrs/0013-free-text-on-the-chosen-option-is-the-contract.md) |
| ADJ-16 | 2026-08-23 | `spike` is **timeboxed**, outcome is a **learning**; `defer`/`handoff` = "Log the entire question and recommendations as a ticket for a backlog. Mark this seam as a scope boundary." Route order explain → show → spike → defer. | [0009](../../docs/adrs/0009-defer-logs-the-whole-question-as-a-ticket.md) |
| ADJ-17 | 2026-08-23 | "Guide the agent to extract your reasoning and apply it to all open questions before asking the next question." | [0016](../../docs/adrs/0016-the-cascade-carries-the-lens-not-only-the-choice.md) |
| ADJ-18 | 2026-08-24 | The `A:/B:/C:/TBD:` reply-grammar block collapses to two prose lines; a bare route name is a valid TBD reply with no `TBD:` prefix required. | [0017](../../docs/adrs/0017-reply-grammar-is-two-prose-lines.md) |
| ADJ-19 | 2026-08-24 | `README.md` and `CLAUDE.md` are supportive files during skill development, NOT load-bearing at runtime. The README "is, and always will be the human facing documentation to describe the skill, its value proposition, an overview of how it works". | [0018](../../docs/adrs/0018-runtime-authority-is-skill-md-and-resources.md) |
| ADJ-20 | 2026-08-24 | `task` confirmed as a valid route (provenance: Wayfinder research, not a rehearsal). "A different sort of *work* that must occur before we can make an informed decision" — human-side, where `defer` is "not important now" and `spike` is the agent gathering data. | [0009](../../docs/adrs/0009-defer-logs-the-whole-question-as-a-ticket.md), [0003](../../docs/adrs/0003-tbd-route-family-defer-is-partial-decision.md) |
| ADJ-21 | 2026-08-24 | On the ADR document template: "E is the better option using headings to index the hierarchy of information." Also: remove the Compliance section — "they are already too big and wordy"; metadata as a table "is a nice touch"; Consequences splits Pros and Cons as sub-headings; `Problem > Cost` renames to `Problem > Pain point`. | [0010](../../docs/adrs/0010-headings-index-the-hierarchy-of-information.md) |
| ADJ-22 | 2026-08-24 | On the decision grammar: "H is the superior format, the dot points with the bolded key work links nicely with Given/When/Then style BDD style language. The other options look like a wall of text and hard to index into structurally. H format I could use a Markdown parser and extract or replace those values like it is a YAML document." | [0011](../../docs/adrs/0011-lens-grammar-given-prefer-because-unless.md) |

## Open — not yet ruled

None. Add the next user override here in the same turn it happens: id, date, the user's own words, and `—` in the ADR
column until it is promoted. A ruling that sits here unpromoted for more than a session is drift: either it is a rule,
and it needs an ADR plus a runtime change, or it was situational and should be deleted.
