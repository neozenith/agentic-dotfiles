---
name: dadjoke
description: "Workshop themed dad jokes in short, feedback-led waves, taking the theme as the invocation argument and carrying the user's taste signal into each new wave. Use when a user asks to create, improve, evaluate, or refine dad jokes, puns, groaners, or themed question-and-answer jokes. Not for general comedy writing or non-pun humour."
argument-hint: "<theme> [count] [Q&A]"
user-invocable: true
---

# Dad Joke Workshop

Produce a fresh, themed batch of dad jokes that gives the user useful options to evaluate. The next consumer is the user selecting jokes or explaining what worked. Done when every candidate matches the requested format, accurately uses the theme, and tests a distinct enough premise for the feedback to guide the next wave.

## Resolve the theme

The theme is the argument passed with the invocation.

Theme argument: $ARGUMENTS

Resolve it in this order, stopping at the first source that names a theme:

1. The substituted argument on the line above.
2. If that line is blank or still reads literally as a placeholder, the text that followed the skill mention in the user's message.
3. Failing that, the theme of any jokes the user pasted for review.
4. If none of these names a theme, ask for one. It is the only constraint nothing else can stand in for.

Split the argument when it carries more than the theme, for example "five Q&A jokes about kubernetes":

- Read a count out of it as part of the brief.
- Read a format out of it as part of the brief.
- Treat the rest as the theme.

## Build the brief

Extract from the request:

- The format (free-form or question-and-answer).
- The batch size.
- The domain vocabulary of the theme.
- Any accepted or rejected examples.

Handle feedback as evidence, not doctrine:

- Treat user feedback as evidence about this audience, not a universal comedy rule.
- If the user corrects a rule, replace the rule. For example, forced word surgery can be the intended groan when it still sounds clear aloud.

Decide whether to generate or ask:

- Generate immediately once the theme is known; the defaults below cover everything else.
- Ask only when a missing constraint would materially change the jokes.

## Generate a wave

Size and present the wave:

- Create the requested number of candidates. Default to three.
- Give only the jokes while the user is evaluating them.

Build each joke in this order:

1. Use a recognisable parenting ritual, prop, spoken phrase, or everyday scene as the first reading.
2. Pair it with exact domain language from the theme that creates a second, natural reading.
3. Put the semantic pivot in the answer, not in an explanation after it.

Vary the engine across the wave. For a three-joke wave, use at least two of these forms:

- A visual parenting setup recontextualised by domain language.
- A familiar phrase with a clean second meaning in the theme.
- A short sound, spelling, or word-boundary pun.

Check the wave before sending:

- No two candidates are synonyms of the same joke.
- A reused winning mechanism has a new scene, object, or phrase.

## Question-and-answer form

When the user asks for question-and-answer jokes, write each candidate exactly as a short `Q:` and `A:` pair. Let the question set a sincere scene. Let the answer deliver one compact turn, usually beginning with "Because". Do not explain the pun.

```text
Q: Why did the product manager bring a stroller to sprint planning?
A: Because the Epic was expecting more child issues.
```

Do not reuse a supplied example in a later wave unless the user asks for it.

## Quality bar

Keep a candidate only when the answer makes the setup funnier rather than restating it. Both readings must be grammatical, immediately recognisable to the audience, and depend on the named theme rather than unexplained trivia. Prefer a vivid, specific setup and a short punchline over a technical explanation.

## Learn from the user

When the user evaluates a wave, first distil three to six portable observations. Name the winning setup, the working wordplay, the placement of the reveal, and the rejected failure mode. Keep an explicitly restored technique available for later waves.

Then generate the next batch from those observations. If the user says a batch is not funny, do not defend it. Identify the mismatch privately and try a new mechanism or premise.
