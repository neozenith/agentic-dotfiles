---
name: dadjoke
description: "Workshop themed dad jokes through short, feedback-led batches and carry the user's taste signal into each new wave. Use when a user asks to create, improve, evaluate, or refine dad jokes, puns, groaners, or themed question-and-answer jokes. Not for general comedy writing or non-pun humour."
---

# Dad Joke Workshop

Produce a fresh, themed batch of dad jokes that gives the user useful options to evaluate. The next consumer is the user selecting jokes or explaining what worked. Done when every candidate matches the requested format, accurately uses the theme, and tests a distinct enough premise for the feedback to guide the next wave.

## Build the brief

Extract the requested theme, format, batch size, domain vocabulary, and any accepted or rejected examples. Treat user feedback as evidence about this audience, not a universal comedy rule. If the user corrects a rule, replace the rule. For example, forced word surgery can be the intended groan when it still sounds clear aloud.

Generate immediately when the brief is sufficient. Otherwise ask only for the one missing constraint that would materially change the jokes.

## Generate a wave

Create the requested number of candidates. Default to three. Give only the jokes while the user is evaluating them.

Use a recognisable parenting ritual, prop, spoken phrase, or everyday scene as the first reading. Pair it with exact domain language that creates a second, natural reading. Put the semantic pivot in the answer, not in an explanation after it.

For a three-joke wave, vary the engine across at least two of these forms:

- A visual parenting setup recontextualised by domain language.
- A familiar phrase with a clean second meaning in the theme.
- A short sound, spelling, or word-boundary pun.

Do not make three synonyms of the same joke. Reuse a winning mechanism, but give it a new scene, object, or phrase.

## Question-and-answer form

When the user asks for question-and-answer jokes, write each candidate exactly as a short `Q:` and `A:` pair. Let the question set a sincere scene. Let the answer deliver one compact turn, usually beginning with “Because”. Do not explain the pun.

```text
Q: Why did the product manager bring a stroller to sprint planning?
A: Because the Epic was expecting more child issues.
```

Do not reuse a supplied example in a later wave unless the user asks for it.

## Quality bar

Keep a candidate only when the answer makes the setup funnier rather than restating it. Both readings must be grammatical, immediately recognisable to the audience, and depend on the named domain rather than unexplained trivia. Prefer a vivid, specific setup and a short punchline over a technical explanation.

## Learn from the user

When the user evaluates a wave, first distil three to six portable observations. Name the winning setup, the working wordplay, the placement of the reveal, and the rejected failure mode. Keep an explicitly restored technique available for later waves.

Then generate the next batch from those observations. If the user says a batch is not funny, do not defend it. Identify the mismatch privately and try a new mechanism or premise.
