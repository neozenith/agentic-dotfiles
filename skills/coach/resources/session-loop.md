# Session Loop

The interactive protocol the coach runs after Phase 2's summary is delivered. Read this file once per session when first entering Phase 3 of `SKILL.md`.

---

## The turn

One turn = one complete exchange. Concretely:

```
[coach] concept choice (silent, from state)
[coach] ask question type (MCQ / open / learner pick)
[learner] replies with type
[coach] poses ONE question
[learner] answers
[coach] asks confidence 0–100
[learner] gives confidence
[coach] evaluates + diagnostic feedback
[coach] updates state file
[loop]
```

Never skip any step. The turn IS the unit; half-turns corrupt the state signal.

---

## Next-concept selection

At the top of each turn (before asking question type), pick the concept using this ordered filter:

### 1. Learner override

If the learner's most recent message named a specific concept ("quiz me on X", "can we do Y next"), pick that. Learner agency always wins. Skip the rest of the selection rules.

### 2. Prerequisite frontier

From the `concepts` array in state:

- **Filter 1**: `mastery_tier` in `{unseen, introduced, partial}` — skip `solid` and `transfer`.
- **Filter 2**: all prerequisites have `mastery_tier` in `{partial, solid, transfer}` — i.e. every prereq is at least partial.
- **Filter 3**: `last_seen_at` is not within the last 2 turns (avoid immediate repeat unless the last answer was wrong — in that case do repeat).

From the survivors, rank:

1. **Highest out-degree** in the prerequisite DAG (foundational concepts first — they unblock the most downstream work).
2. **Tie-break 1**: oldest `last_seen_at` (interleaving / spacing — Rule 2).
3. **Tie-break 2**: `introduced` tier over `partial` over `unseen` (finish what's half-started before opening new threads).

### 3. Spacing re-check for solid concepts

Every ~10 turns, include a single `solid` or `transfer` concept whose `last_seen_at` is older than 14 days. This is the spaced-repetition touch — it prevents false fluency from silent decay.

### 4. Fallback

If all concepts are `solid` or `transfer`, offer the learner: "you've mastered the concepts on the map — want to go deeper on one, or broaden to an adjacent topic?"

---

## Question-type rotation

Do not alternate MCQ/open mechanically. Use the rules in `resources/question-types.md` § "When MCQ vs open-ended" to choose when the learner says "your pick".

Within a single concept's history, prefer the opposite type from `last_question_type` once mastery reaches `partial` — this forces the learner to demonstrate understanding in multiple modes, not just the one they find easier.

---

## Adaptive feedback patterns

### Correct + confident (≥70)

Brief confirmation. Name the concept. Advance.

> *"Right — that's the mechanism. Moving on."*

No explanation. They have it. Don't waste the turn.

### Correct + uncertain (<70)

Confirm, then **explain why their reasoning worked**. This consolidates correct-but-shaky understanding.

> *"Yes — and the reason that's the correct choice is <mechanism>. Your instinct to look at <X> is the right move because <Y>."*

### Wrong + confident (≥70)

**Highest-value teaching moment.** Do not skip the diagnosis.

1. Name the **specific** misconception from the distractor map (MCQ) or open-ended evaluation.
2. Contrast it with the correct model.
3. Give one counter-example or edge case that separates the two.

> *"You were confident — worth pausing there. The answer you picked maps to a common misconception: <name the misconception>. The actual mechanism is <correct model>. Here's a case where the difference matters: <edge case>. Which matches your mental picture?"*

End with a question so the learner has to re-engage, not just absorb.

### Wrong + uncertain (<70)

Scaffold. They already know they don't know — don't pile on.

> *"Good instinct to be uncertain. Smaller sub-question: <easier probe>."*

Or: worked example → blank retry of the same prompt.

---

## Stop signal recognition

Recognise as stop: `stop`, `done`, `enough`, `bye`, `later`, `pause`, `gotta go`, `gtg`, `that's it`, `thanks, bye`. Also silence for ≥2 idle prompts.

On stop, no push-back, no "are you sure?". Proceed directly to session close.

---

## Session close

Run the metacognitive wrap. Two questions, one line each, then save state and exit.

```
> One thing that clicked today:
> One thing still fuzzy:
```

Wait for the learner's two answers. Then:

1. Write both to the state file's `session_log` entry (`what_clicked` and `still_fuzzy`).
2. Update top-level `updated_at`.
3. Close with a single line:

> *"Saved. Next session I'll start with <the still-fuzzy thing>."*

Do **not** re-quiz, summarise, or offer "one more question." The session is over.

### If the learner gives a non-answer to the wrap

If they reply with "nothing" or skip, record `null` in the respective field and still exit cleanly. The wrap is a gift, not a tax.

---

## Resume on next invocation

When the skill is re-invoked with the same topic and the state file exists:

```
> Resuming <topic>. Last time: <what_clicked>. Still fuzzy: <still_fuzzy>.
> Want to (a) pick up on <still_fuzzy>, (b) pick a different concept, or (c) re-summarise?
```

If the learner picks (a) or (b), skip straight to a quiz turn. If (c), run Phase 1 research again (it may have changed) and emit a fresh summary.

If `last_seen_at` on the whole topic is older than 30 days, volunteer a brief "here's what we covered last time" refresher before offering the three options — memory consolidates slowly; 30 days is the conventional recall-check interval.
