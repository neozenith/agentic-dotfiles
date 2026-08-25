# Question template

- Fill every `<…>` angle bracket template location.
- Delete no section. 
- The shape file you loaded tells you which variant below to apply
- The harness adapter tells you how section 9 is bound.

## Base template

````markdown
## <DECISION-ID> — <short noun phrase for the choice>

**Decision to make:** <one complete sentence: choose <what>, for <which surface>, under <operating constraints>.>

### Why decide this now

| Context | Effect on this decision |
|---|---|
| <blocked work> | <the file, ticket, or step that cannot proceed until this is fixed> |
| <downstream decision 1> | <how this answer resolves or narrows it> |
| <downstream decision 2> | <…> |
| Why this one first | <the other open questions still queued, and why this answer resolves or narrows more of them than any of those would> |
| Outside this decision | <things that look related but are independent and will be asked separately> |

**Already settled:** Checked <the decision records searched: e.g. `docs/adrs/`, `CLAUDE.md`, `plan.md` Decisions, the tracker>. <prior decision(s)> fixed <what>; <why that does not answer this question — the constraint it left open, or the constraints it made compete>. <If nothing bears on it, say "nothing recorded bears on this". If a prior decision is assumed rather than recorded, say so and name `explain` as the route to reopen it.>

**Reversibility:** <low | high | asymmetric> — <affected surfaces and the cost of changing later, in one line>.

### A: <self-describing title>

```<lang>
<COMPLETE preview on the user's real data — their actual command / file / path / output>
```

**Pros:** <one line>.
**Cons:** <one line>.

### B (Recommended): <self-describing title>

```<lang>
<complete preview>
```

**Pros:** <…>.
**Cons:** <…>.

### C: <self-describing title>

```<lang>
<complete preview>
```

**Pros:** <…>.
**Cons:** <…>.

### Compare

| Option | <domain column 1> | <domain column 2> | <domain column 3> | Main cost |
|---|---|---|---|---|
| A: <short> | … | … | … | … |
| B: <short> | … | … | … | … |
| C: <short> | … | … | … | … |

**Recommendation:** choose <B>. <One sentence of why.>

### TBD: answer without deciding

| Route | What happens next |
|---|---|
| `explain: <part>` | Revise <the likely unclear part> and ask this decision again. |
| `show` | <One complete artifact per option> — or "not useful for this decision". |
| `spike: <question>` | <The concrete experiment on the user's real data>, timeboxed to <box>; the learning is recorded, then re-asked. |
| `defer` or `handoff` | Log this whole question and the recommendation as a backlog ticket (<backend>); record the scope seam; continue with <B> as a provisional assumption <where work must proceed>. |
| `other: <description>` | Render it at the same level of detail and ask again. |
| `task: <what>` | <The prerequisite work>, then ask again with what it revealed. |

<ANSWER CHANNEL — bound by the harness adapter. Session feed: the reply footer below. Structured picker: the picker call, with the footer's semantics.>

Your reasoning becomes <DECISION-ID>'s Why; a route reply is an answer, not a decision.

```text
Reply with A, B or C and your reasoning.
Alternatively choose from <explain|show|spike|defer|handoff|other|task> and your reasoning to revise/iterate.
```
````

## Filling rules

- **Real data or nothing.** The preview is the user's own command, names,
  paths, data set. Collect it before composing; a placeholder preview fails
  the first check.
- **`Checked:` is not optional.** `Already settled` opens with the decision
  records that were actually searched (SKILL.md *Decision records*). It is
  how the user verifies check 3 without redoing the search; a line that
  names no records fails that check.
- **`Why this one first` names the queue.** The user should see the other
  open questions this one outranks, in one line — that is check 2's
  "worthy of my attention".
- **One decision per message.** Cascade and re-rank before choosing the next.
- **Recommendation twice**: in the option title and in the Recommendation
  line. Recommended option goes first where the harness orders options.
- **Labelled context, not prose.** `Decision to make`, `Why decide this now`,
  `Already settled`, `Reversibility` stay as visible labels — they are what
  the user scans for.
- **Separate Pros/Cons lines** under every preview; never a blended paragraph.
- **Say what the reasoning becomes** ("becomes <DECISION-ID>'s Why", "is the
  lens reused for every future <class> question").
- **The reasoning is recorded as a four-clause lens** — `Given` the context,
  `We prefer` X over Y, `Because` …, `Unless` … (or "never; unconditional").
  Write it that way when recording; never ask the user to phrase it that way.
- **No meta text** in the question ("grade this", "do not answer"). If a
  rehearsal needs it, it goes in the surrounding turn.
- **Sizing:** low stakes ⇒ the preview is the value itself (a path, a key
  name). Everything else keeps the full outcome.

## Variants

Each shape file holds its own variant and a worked generic example. Summary:

| Shape | Delta from the base |
|-------|---------------------|
| Exclusive choice | none |
| Subset as permutations | an **atomic options** table *before* the options; options are combinations titled by their members |
| Binary | two options; a sub-choice inside one option rides in the reply footer ("picking B, also name <x\|y\|z>") |
| Low stakes | say "low stakes"; previews shrink to the value; every section stays |
| Resolved by cascade | `Already settled` names the prior decision, what it fixed, and the constraints it left competing; `explain` reopens it |
