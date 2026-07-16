# Prose Style for Authored Content

Load when this skill **authors or rewrites** prose. It applies to prose this
skill produces, never to the user's canonical markdown, which is rendered as
written.

## Where this applies (and where it must not)

richdocs renders markdown to an HTML companion. The `.md` stays the source of
truth (ADR-001), so **faithfully-rendered user content is never rewritten** to
satisfy a style rule. Apply this standard only to prose **richdocs itself
authors**:

- text the skill generates (showcase labels and copy, section intros it writes);
- UI and error strings emitted by the scripts;
- this skill's own docs (`SKILL.md`, `README.md`, `resources/*`);
- prose richdocs writes when it **upgrades** a discovery doc under an author's
  explicit instruction (see `discovery-docs.md`), where a rewrite is in scope.

If the user's canonical markdown breaks a rule below, that is the user's prose to
keep. Render it as written; do not silently correct it.

## Detection is tooling-agnostic

This file states **what** to look for, never **which command** finds it. Prose
tooling is an evolving space, and naming one `grep` here would bake in a single
assumed path. When a rule says "find X", pick the fittest mechanism for the
environment and report what you used. The requirement is the finding, not the
tool.

## The non-negotiable mechanics

### No em-dash. Ever.

The em-dash `—` (U+2014) is banned in all authored prose, including UI strings
and code comments. It is the most recognisable AI-authorship tell, and it erodes
a reader's trust on sight. Use a comma, a colon, parentheses, or split the
sentence in two. An en-dash `–` in a genuine numeric range (`1.6–1.11`) stays
legitimate.

### Australian English, always

Use Australian spelling in prose: "organise", "colour", "prioritise",
"behaviour", "licence" (noun), "judgement". Never the US forms. When the code
names a real identifier that ships US spelling (`color: #fff`, a `--color` flag,
an `Authorization` header), keep that identifier verbatim: it is a name, not
prose.

### Plain English, no persuasion flourishes

- Avoid the **contrastive flourish** ("That's not X. That's Y."). Write the
  plain statement.
- Avoid **consecutive very short sentences** that restate one idea. Say it once.

## Curate for shorter, coherent clauses

- **Limit a sentence to about 25 words.** Where a sentence resists shortening,
  make it a bullet list or a table. The target is **clause count**, not word
  count: three short sentences beat one sentence with three subordinate clauses,
  even when the three run longer in total.
- **Active voice, strong verbs.** The subject acts. Prefer "the toggle re-feeds
  the palette" over "the palette is re-fed by the toggle".
- **Cut needless words.** "In order to" becomes "to". Drop *even, just, simply,
  so, very, actually* where they add nothing. Prefer present tense over *will*.

## Write for ESL readers and translators

A sentence that parses for an ESL reader or a translator on the first pass parses
for everyone.

- **Complete sentences over fragments.**
- **Keep modifiers next to what they modify.** Watch "only": "only the admin can
  delete" differs from "the admin can only delete".
- **Resolve `-ing` / `-ed` ambiguity with a determiner:** "the running server",
  "a cached response". Keep the gerund for titles ("Getting Started").
- **Avoid slang and idioms.** They do not translate.

### Evaluating ESL and translator readability

"ESL-friendly" is only real if it can be checked. Evaluate authored prose with
concrete, tool-agnostic methods, cheapest first. Pick the one that fits the
environment and report which you used.

1. **Proxy metrics (deterministic).** Count what a rule already bounds: sentence
   length (about 25 words or fewer), one main clause per sentence where possible,
   and a reading-grade target (aim for roughly grade 8 to 10) from any readability
   measure. One term per concept, one concept per term.
2. **Round-trip translation (optional; the translator-specific check).**
   Translate the passage to another language and back to English with any
   available translator, then compare. Idioms, tangled clauses, and ambiguous
   `-ing`/`-ed` words break in the round trip; if the back-translation drifts or
   confuses, rewrite the source, not the translation. This check is **blind to
   register and punctuation** (a translator normalises an em-dash away, and
   universal metaphors survive), so it never replaces the proxy-metric or rubric
   checks. Scale the effort to the rigour you want, and default to fast and cheap:
   - **Default (cheap):** skip it when the proxy-metric and rubric checks are
     clean, or run **one** diverse pivot. A single distant pivot already catches
     blatant problems.
   - **Escalate (a small council):** run single trips through a few diverse
     pivots and require the passage to survive all of them. Recommended trio:
     **German** (exposes nested clauses and merged terminology), **Mandarin
     Chinese** (exposes `-ing`/`-ed` and definiteness ambiguity), **Arabic**
     (maximal idiom distance; forces number and definiteness). German plus
     Chinese alone is a strong two-pivot bar.
   - **Deep (broad council):** add more distant languages (for example Japanese,
     Russian, Spanish) only when the user asks for thorough multilingual
     accessibility. Russian is weak at exposing nesting, so it does not replace
     German. Cost rises with each pivot, so run the broad council on request.
3. **Read from the reader's seat.** A reviewer (person or model) reads as an ESL
   reader and flags any sentence that needs a second pass to parse. The rules
   above become the rubric, which turns the read into a repeatable score.

## Inclusive language

Content is inclusive and free of bias. Replace the term on the left with one that
fits the context:

| Avoid | Use instead |
|-------|-------------|
| abort | stop, cancel |
| blacklist | deny list, block list |
| whitelist | allow list |
| master (branch, node) | primary, main, leader |
| slave | replica, secondary, standby |
| kill / hang | end, stop, stop responding |
| sanity check | quick check, confidence check |
| dummy value | placeholder, sample value |

This table grows as new terms surface.

## Reuse standardised domain language

Choose one term per concept, define it once, and reuse it. Synonym variety reads
as a new concept to a translator. This skill already fixes its own vocabulary
(companion, brandpack, canvas palette, stencil, fenced rich block); use those
exact words, not near-synonyms.

**Disambiguate with determiners where a word could confuse.** richdocs prose
carries several two-meaning words:

- "canvas": the HTML `<canvas>` element vs the brand's design canvas. Write "the
  cytoscape canvas" or "the brand canvas".
- "theme": a named brand directory vs the light/dark mode. Write "the brand
  theme" vs "the colour mode".
- "render": generate the HTML vs draw a block on screen. Name which: "render the
  companion" vs "draw the graph".

The determiner is cheap and removes a class of misreadings. Add one clarifying
word rather than trusting the reader to infer the sense.

## Checklist for authored prose

```text
[ ] No em-dash anywhere; Australian spelling in prose, identifiers verbatim.
[ ] No contrastive flourish, no consecutive short restatements.
[ ] Sentences curated to ~25 words; long ones split, listed, or tabled.
[ ] Active voice, strong verbs, needless words cut.
[ ] Modifiers close to their target; -ing/-ed ambiguity resolved.
[ ] No non-inclusive terms; replacements fit the domain.
[ ] Skill vocabulary reused exactly; determiners disambiguate canvas/theme/render.
[ ] User's canonical markdown rendered as written, never silently corrected.
```

### ESL/translator evaluation (auditable checks)

Run and record which methods you used. Method A is the free deterministic
pre-filter; Method D is the primary check; round-trip is a confirmatory pass for
ambiguity and terminology (and is blind to punctuation, so it never runs alone).

```text
Method A, proxy metrics (deterministic gate; a tripped box fails the passage):
[ ] A1 Longest sentence ≤ 25 words.
[ ] A2 Reading grade ≤ 12 (target grade 8–10) by any readability measure.
[ ] A3 No sentence carries more than 2 nested subordinate clauses.

Method D, reader's-seat rubric (read as an intermediate ESL reader; any tripped
item fails the passage):
[ ] D1 Every sentence parses on the first pass, with no re-read.
[ ] D2 No idiom, slang, or figurative phrase.
[ ] D3 No bare -ing/-ed word left ambiguous between verb and noun (add a determiner).
[ ] D4 One concept is named by one term throughout, with no synonym drift.
[ ] D5 No em-dash or other authorship tell (an en-dash in a numeric range is exempt).
```

Method A catches sentence *shape* and nothing semantic; it passes short idioms and
ambiguity. Method D covers all five defect classes at low cost, but D1 and D3 are
judgement calls, so pin them to a fixed reader band (for example CEFR B1) when the
result must be repeatable.
