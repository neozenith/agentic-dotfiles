# Harness adapter: Claude Code (`AskUserQuestion`)

Part of `concise-decisions` ([../../SKILL.md](../../SKILL.md) step 4). Load
when `CLAUDECODE` is set, or when the harness exposes a structured
single-select question tool whose options carry a preview and accept
free-text annotation on the selected option.

An adapter binds **only section 9** (the answer channel) of the template. It
may not drop sections, shrink previews, or rename TBD routes.

## Pattern: body + picker

Render sections 1–8 as the message body, then call `AskUserQuestion` once in
the **same turn**. The body carries the reasoning material; the picker
carries the choice and, through annotation, the reasoning.

```jsonc
AskUserQuestion({ questions: [{              // exactly ONE question — never 2–4
  header: "<≤12 chars>",
  question: "<DECISION-ID> — <decision sentence>. <stakes in 3–6 words>. Annotate your pick with why; or pick the last option to answer without deciding: explain / show / spike / defer / handoff / other / task.",
  multiSelect: false,                        // never true
  options: [
    { label: "B (Recommended): <self-describing title>",     // recommended FIRST
      description: "<one-line trade-off>",
      preview: "<example line(s)>\n\nSolves: <…>\nCost: <…>\nFull rendering: block \"B\" above." },
    { label: "A: <self-describing title>", description: "…", preview: "…" },
    { label: "C: <self-describing title>", description: "…", preview: "…" },
    { label: "Not a decision yet → annotate the route",
      description: "explain | show | spike | defer/handoff | other | task",
      preview: "An ANSWER, not a decision. Annotate one of:\n  explain: <what needs revising>\n  show:    <render real artifacts per option>\n  spike:   <what data decides it> (timeboxed)\n  defer:   <why it can wait> -> whole question becomes a ticket (also: handoff)\n  other:   <describe>\n  task:    <prerequisite work>" }
  ]
}]})
```

## Rules specific to this adapter

- **Every option carries a `preview`.** The preview pane is what exposes the
  per-option annotation channel. Without it the user cannot attach reasoning
  (check 4 fails), and the tool's automatic "Other" escape has proven
  unreliable in practice.
- **The preview is a card, never the artifact.** Example line(s), `Solves:`,
  `Cost:`, and a pointer to the full block in the body. The pane truncates
  anything longer; the body is scroll-back-able, the pane is not.
- **Four options maximum** ⇒ **3 real options + 1 routed TBD**. Never spend
  the fourth slot on a weak alternative. For a binary: 2 + TBD.
- **The `question` text is the cold-start guard.** Restate the decision and
  stakes in it, because the picker has been observed rendering before, or
  over, the body. The user must be able to orient from the picker alone.
- **Labels are self-describing.** Never `Confirm C` / `Veto → A`.
- **Single-select only.** For composing options use the permutations shape;
  never `multiSelect: true`.
- **Annotations are the reasoning.** When the result arrives, copy the
  annotation on the selected option verbatim into the decision record's Why.
  An option selected **without** an annotation is the missing-why case:
  infer the lens from the briefing, state it in passing, mark it
  unconfirmed (SKILL.md *After the answer*). A selected TBD option's
  annotation names the route; act per [../tbd-routes.md](../tbd-routes.md).
- **Free text is the contract, not a courtesy.** A picker whose selected
  option cannot carry free text is not this adapter — route to
  [session-feed.md](session-feed.md). Multichoice without space for
  reasoning is the failure the user named.
- **A declined or cancelled tool call is not an answer.** Stop and wait for
  the user; do not re-ask in the same turn.

## Mapping to the reply footer

| Session-feed reply | Picker equivalent |
|---|---|
| "B — <why>" | select option B, annotate `<why>` |
| "spike: <why>" (a route, with or without a `TBD:` prefix) | select "Not a decision yet", annotate `spike: <why>` |

## Known gaps

- The picker-over-body rendering has been observed once and not reproduced;
  the `question`-text guard above is the mitigation.
