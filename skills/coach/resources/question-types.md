# Question Types

Specifications for the two question formats the coach offers each turn, plus the rule for choosing between them when the learner says "your pick."

---

## When MCQ vs open-ended

Choose MCQ when:
- The learner is **early on a concept** and the goal is a rapid misconception screen.
- The set of common wrong mental models is **well-defined** (each becomes a distractor).
- The concept is **factual or categorical** (definitions, terminology, classification).
- The learner has said "your pick" *and* their calibration has been poor (MCQ forces a commitment you can score).

Choose open-ended when:
- The learner claims mastery and you want to **puncture the Illusion of Explanatory Depth**.
- The concept is **causal or procedural** (mechanisms, step-sequences, derivations).
- You are at **Bloom's Apply level or above** (transfer, analysis, evaluation).
- The learner has said "your pick" *and* their MCQ performance has been strong (time to raise Bloom's level).

---

## Multiple-choice format

### Format of the turn

```
> Question: [one question, ≤2 lines]
>
> (A) [option A]
> (B) [option B]
> (C) [option C]
> (D) [option D]   ← omit if only 3 plausible distractors exist
>
> Answer with a letter, or type a free-text answer if none of these fit.
```

### Design rules

1. **One correct answer** — exactly one option is unambiguously correct under the stem's framing.
2. **3 or 4 total options** — never 2 (50% guess-rate) and never 5+ (reading load). Prefer 4 when 4 distinct misconceptions exist; drop to 3 when the fourth would be filler.
3. **Each wrong option = a named misconception.** Before writing the MCQ, list the top-K misconceptions. Each becomes a distractor mapped to a misconception label. Keep this map so feedback can name the misconception the learner fell into.
4. **No surface cueing.** Grammatical agreement, option length, and register must be uniform across options — a learner should not be able to pick the right answer by language pattern alone.
5. **No "all/none of the above".** These options collapse diagnostic signal.
6. **Plausibility ordering is irrelevant** — randomise which letter is correct across turns.

### Allowing open-text fallback

If the learner replies with prose rather than a letter (because "none of the options fit their understanding"), switch to the open-ended evaluation rubric below. This is a feature, not a bug — it reveals that the distractor set missed their mental model.

### Misconception map (internal)

Maintain a temporary map for the turn:

```json
{
  "A": "correct",
  "B": "misconception: treats <thing> as absolute when it's relative",
  "C": "misconception: confuses <X> with <Y>",
  "D": "misconception: applies <rule> outside its domain"
}
```

When giving feedback after a wrong answer, name the misconception from this map. This is the single most valuable teaching moment in the loop — do not skip it.

---

## Open-ended format

### Format of the turn

```
> Question: [one prompt, ≤2 lines, demanding paraphrase or application]
>
> Answer in your own words. Rough drafts are fine — I'm looking at how you think.
```

### Prompt templates (pick one)

- **Paraphrase to a different audience.** "Explain X to a junior engineer in two sentences."
- **Novel application.** "How would X apply to <scenario the learner hasn't seen>?"
- **Mechanism / step-chain.** "Walk me through what happens when <specific edge case>. Step by step."
- **Counter-example.** "Give me a case where X *does not* apply. Why?"
- **Translation / different representation.** "Sketch X as pseudocode / a diagram / an analogy."
- **Compare and contrast.** "How is X different from <sibling concept>? Where do they overlap?"

Banned open-prompts: "what is X?", "define X", "repeat the definition", "summarise what I just said." These permit parroting without understanding.

---

## Evaluating open-ended

Score the response across four axes. You don't have to announce the axes — use them to shape feedback.

| Axis | Strong signal | Weak signal |
|---|---|---|
| **Paraphrase** | Learner reframes in their own vocabulary, correct sense | Copies your phrasing verbatim; different words but same template |
| **Mechanism** | Cites causes, dependencies, or step ordering | Names the label/term but not *why* it works |
| **Boundary** | Notes when the concept applies *and* when it doesn't | Describes the concept in isolation with no limits |
| **Precision** | Quantifies where relevant; hedges calibrated to uncertainty | Vague ("sort of", "kind of") or over-confident flat claims |

### Feedback rubric

- **All four strong** — confirm briefly, name the mastery, advance.
- **Paraphrase + mechanism strong, boundary weak** — prompt a boundary probe: "when would this *not* work?"
- **Paraphrase strong, mechanism weak** — this is the IOED signature. Probe: "you named it — walk me through *why* step 2 follows from step 1."
- **All weak** — return to scaffolding: give a worked example and ask them to retry the same prompt with the example in hand.
- **Confident + wrong** — this is the highest-value feedback. Explicitly state the misconception you observed: "you're treating <X> as <Y>, but X differs from Y because …" — then give a counter-example.

### What to do with partial correctness

Acknowledge what was right **first**, then the gap. Ordering matters for motivation (OARS/affirmations from motivational interviewing). "You've got <correct piece> — that's the core. Where this needs refining is …"

---

## Anti-patterns (avoid these)

- **Chaining questions.** "Answer this, then this, then this." → Batch loses diagnostic signal. One question per turn.
- **Leading questions.** "Don't you think X is really Y?" → Cues the answer. Rephrase as neutral.
- **Punishing wrong answers.** "No, that's wrong." → Kills engagement. Say "close — here's where the thinking bends" or "that's the common misconception — here's what's actually going on."
- **Skipping the confidence check.** → You lose the calibration signal, which is often more valuable than the correctness signal.
- **Moving on from a "wrong + confident" without naming the misconception.** → The single biggest teaching moment in the loop; never skip it.
