# Harness adapter: session feed (text-only)

Part of `concise-decisions` ([../../SKILL.md](../../SKILL.md) step 4). Load
when no structured single-select question tool with per-option free text is
available: chat surfaces, cloud runners, Codex Default mode (see
[codex.md](codex.md)), unknown harnesses.

This is a **complete adapter, not a degraded one**. Text renders every
section of the template and captures choice and reasoning in one reply. Do
not describe it as a fallback and do not compress anything because "it is
only text".

## Pattern: one markdown message, one reply footer

Render all nine sections of
[../question-template.md](../question-template.md) as a single assistant
message. Section 9 is the reply footer, placed last:

```text
Reply with A, B or C and your reasoning.
Alternatively choose from <explain|show|spike|defer|handoff|other|task> and your reasoning to revise/iterate.
```

The user's single reply carries the option letter (or a route name) and the
reasoning. A binary folds its sub-choice into line 1 ("picking B, also name
<x|y|z>"). A letter with no why is the missing-why case: infer the lens from
the briefing, state it in passing, mark it unconfirmed (SKILL.md *After the
answer*).

## Rules specific to this adapter

- **The non-decision label is the visible word `TBD`**, never a bare letter
  (`T` read as a fourth option in rehearsal).
- **TBD routes render as a table** with "what happens next" per route,
  between the recommendation and the reply footer. In this adapter the
  table *is* the route preview card.
- **Recommendation in the option title** (`B (Recommended): …`) — in a feed
  there is no "first option" ordering cue, so the title is the only place the
  eye finds it.
- **Pros and cons on separate lines** under every preview. In a text feed a
  blended paragraph is not scannable.
- **Labelled context lines** (`Decision to make`, `Why decide this now`,
  `Already settled`, `Reversibility`) — in a feed these labels are the
  navigation.
- **No meta instructions** in the message. If the turn is a rehearsal, the
  grading request goes in a separate sentence before or after the question,
  never inside it.
- **Parse the reply leniently**: accept `B`, `b:`, `B —`, "B because …"; a
  bare route name (`spike: …`) is a TBD answer — the `TBD:` prefix is
  accepted but never required, since the footer invites the route directly;
  treat any reply that names no option and no route as `explain` with the
  reply text as the unclear part.

## Reading the reply

The `TBD:` prefix is optional on every route row.

| Reply | Action |
|---|---|
| `<letter> <why>` | record option + why as the lens; cascade the choice and the lens |
| `explain: …` | revise that part; re-ask the same question |
| `show` | produce one real artifact per option; re-ask with links |
| `spike: …` | run/propose the timeboxed experiment; write the learning; re-ask or resolve |
| `defer …` / `handoff …` | log the whole question + recommendation as a backlog ticket; record the scope seam; provisional default if work must continue |
| `other: …` | render the new option at full depth; re-ask |
| `task: …` | do or hand over the prerequisite; re-ask with what it revealed |
