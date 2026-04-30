---
name: ais
description: "Attention Is Scarce. Use mid-session when two or more ambiguities have accumulated and you'd otherwise interrupt the user with several questions. Consolidates the open question set into the single highest-leverage multiple-choice question with a recommended pragmatic default, then cascades the answer across every related ambiguity before asking another."
user-invocable: true
---

# Attention Is Scarce (AIS)

> Every question you ask the user is a tax on their attention. Spend it like
> it is the scarcest resource in the loop — because it is.

AIS is the mid-session ambiguity resolution loop. Invoke it whenever you
notice that **two or more open decisions** are blocking your work and you are
tempted to interrupt the user with a chain of questions. Do not dump the list.
Run AIS first.

## When to invoke

Trigger this skill when, mid-task, you find yourself in any of these states:

- You have a queue of clarifying questions about scope, naming, behaviour,
  data shape, format, or trade-offs.
- You are about to ask the user "should I X? and also Y? and also Z?".
- You've drafted code with multiple `TODO: confirm with user` markers.
- You started implementing one branch and realised that three unmade
  decisions block other branches too.
- You're considering an `<!-- ASSUMPTION: ... -->` marker and you have more
  than one such assumption pending.

If the answer to "how many open ambiguities are blocking me?" is 1, just ask
that question directly — AIS overhead isn't worth it. If it's ≥2, run AIS.

## The loop

Repeat until no material ambiguity remains:

1. **Inventory the ambiguities.** Privately list every open decision point.
   Phrase each one as "I don't know whether X, which would determine Y."
   Include the implicit ones — assumptions you quietly made, defaults you
   wrote without explicit permission, code paths you skipped because the
   input shape was unclear.

2. **Rank by cross-cutting impact.** Find the single question whose answer
   would resolve the *most* downstream ambiguities. Prefer questions that
   collapse multiple branches over questions that resolve only one. Knowing
   the data shape often resolves naming, validation, and storage in one
   shot — that's the question to ask.

3. **Resolve it yourself if you can.** Before asking, check whether a
   pragmatic default is obviously right given the surrounding code,
   established conventions, prior feedback, or memory. If yes, pick it and
   move on. The user's attention is more expensive than your own
   deliberation. (See *What counts as a pragmatic default* below.)

4. **Otherwise, ask exactly one question — multiple choice.** Structure it
   with:
   - **Why this question matters.** Name the cascade — list the other
     ambiguities that fall out of the answer.
   - **2–4 educated options.** Each option must be one you would genuinely
     consider implementing. **Do not pad with filler options for the sake
     of "giving choices."** Two strong options is better than three weak
     ones.
   - **Your recommendation.** Mark which option you'd pick by default and
     explain why in one sentence. Make confirmation cheap: a single letter
     reply should be enough.
   - **An open-ended escape hatch.** End with "or describe a different
     approach" so the user can redirect.

5. **Cascade the answer.** Apply the user's answer not just to the specific
   question asked but to every related ambiguity from step 1. Update your
   working notes, your in-flight code, and your remaining queue. Many of
   the ambiguities listed in step 1 should now be resolved.

6. **Re-evaluate, then loop or exit.** Reassess the remaining open
   ambiguities:
   - If none materially affect the work, exit the loop and proceed.
   - If any remain, return to step 1. **Do not** ask a follow-up question
     until you've re-ranked — yesterday's #2 may not be today's #1 after
     the cascade.

## Question framing rules

| Rule | Why |
|------|-----|
| One question per turn. | The whole point — don't fragment the user's attention. |
| Multiple-choice with labelled options (A/B/C). | A single-character reply suffices. Cheaper than free-form prose. |
| Always recommend a default. | If you have no opinion, you haven't researched enough — go research first. |
| Options must be substantive. | "A: do it. B: don't do it. C: something else." is one option plus noise. |
| Lead with the cascade. | The user should see *why* this question is the bottleneck before seeing the options. |
| State reversibility. | If picking wrong creates rework, say so. If it's trivially reversible, say that too — it lowers the stakes and speeds the reply. |

## What counts as a pragmatic default

Pick the option yourself (skip the question entirely) when **all** of these
hold:

- An established convention in the surrounding code, framework, or
  language ecosystem already points to one answer.
- The user's prior feedback or memory entries point in a clear direction.
- The decision is **easily reversible** — a rename, a flag flip, a small
  refactor — not a schema migration, a public API commitment, or a data
  shape that propagates through serialised storage.
- Picking wrong cannot cause a Type 2 failure — code that looks correct
  but silently fails to meet the requirement. (See the
  `escalators-not-stairs` skill: never let a "graceful default" silently
  downgrade an explicit requirement.)

If any of those four is missing, ask the question.

## What counts as "done"

Exit AIS when:

- No remaining ambiguity would change the design, the API surface, the
  data shape, or the user-visible behaviour.
- All remaining decisions are local, reversible, and within the scope of
  conventions you can confidently apply.
- The work can proceed without further human input until the next natural
  review point.

If you find yourself wanting to ask a tenth-priority question "just to be
safe," that's the signal to exit. Make a conservative choice, leave an
`<!-- ASSUMPTION: ... -->` marker (or equivalent in-code comment), and
surface it in your end-of-turn summary so the user can correct cheaply if
wrong.

## Anti-patterns

| Anti-pattern | Why it fails |
|--------------|--------------|
| Asking 5 questions in one message. | Defeats the entire purpose — forces the user to context-switch between unrelated decisions. |
| Back-to-back yes/no questions. | Two yes/nos can almost always be reframed as one multiple-choice covering the combinations. |
| "Which of these do you prefer?" with no recommendation. | Pushes cognitive load onto the user. You did the research — pick a default. |
| Padding to three options when only two are real. | Wastes the multiple-choice frame. If only one option is real, just ask directly with the recommendation. |
| Asking before cascading. | If the previous answer already resolved this question implicitly, asking it again is a tax for nothing. |
| Asking about reversible details. | Pick a default, mark it as an assumption, keep moving. |
| Treating "graceful degradation" as a third option. | A silent fallback is not a real choice — it's a Type 2 failure waiting to happen. Force the explicit decision instead. |

## Output template

When you ask the AIS question, structure the message like this:

```
**Open ambiguities (N):** brief one-line list, ordered by leverage.

**Highest-leverage question:** <one sentence>.

**Why now:** answering this resolves <list referenced from above>.

A. <option> — <one-line description and trade-off>
B. <option> — <one-line description and trade-off>  (default — <why>)
C. <option> — <one-line description and trade-off>

Reversibility: <one line — is this hard to change later, or trivial?>

Or describe a different approach.
```

After the user answers, your next message should:

1. Confirm the choice in one line.
2. State which other ambiguities cascaded resolved and how each was applied.
3. Either proceed with the work, or ask the next AIS question — but only if
   step 6 of the loop says one is still needed.

## Relationship to other skills

- `escalators-not-stairs` — the requirement-integrity guardrail. AIS asks
  *which* requirement to implement; `escalators-not-stairs` ensures none of
  the options silently weaken a stated requirement.
- `plan-gap` — uses the same iterative-question loop inside its Phase 2
  refinement of a gap-analysis document. AIS is the same mechanism extracted
  for general mid-session use, with no document-specific obligations.
