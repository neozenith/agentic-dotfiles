# Global-Audience Prose Style

Load on first use during **write** and **restructure**. This is the
sentence-level companion to [`lenses.md`](lenses.md) and
[`slop_smells.md`](slop_smells.md). Lenses set the page's structure and
register; slop smells say what to prune; this file governs how each **sentence**
reads.

Every rule here serves one of two readers:

- the busy, attention-scarce reader who skims;
- the English-as-a-Second-Language (ESL) reader or translator who needs the
  sentence to parse on the first pass.

A sentence that works for those two works for a native reader as well. Clarity
for the hardest case is clarity for everyone.

> **Scope by mode.** In **write** mode, apply this file in full. In
> **restructure** mode, apply only the meaning-preserving subset: remove
> em-dashes, correct spelling to Australian English, fix a non-inclusive term,
> and split one over-long sentence whose claim is unchanged. Any rewrite that
> alters a claim is a mode switch the user must see (ADR-5), not a drive-by edit.

## Detection is tooling-agnostic

This file states **what** to look for, never **which command** finds it. Prose
tooling is an evolving space, and naming a specific `grep` here would bake in one
assumed path and constrain the running model prematurely. When a rule below says
"find X", the agent picks the fittest available mechanism for the environment
(a search tool, a linter, a script, or a read), and reports what it used. The
requirement is the finding, not the tool.

## Part 1: The non-negotiable mechanics

These are hard rules. A doc that breaks one is not done.

### No em-dash. Ever.

The em-dash `—` (U+2014) is banned in all authored prose. It is the most
recognisable AI-authorship tell, and it manufactures the exact smell the slop
catalogue exists to prune (see `slop_smells.md` S4, and CLAUDE.md ADR-13). Use a
comma, a colon, parentheses, or split the sentence in two. An en-dash `–` in a
genuine numeric range (`1.6–1.11`, `pp. 4–9`) stays legitimate.

### Australian English, always

Use Australian spelling everywhere: "organise", "modernise", "prioritise",
"colour", "labour", "licence" (noun), "judgement". Never the US forms
("organize", "color", "labor", "judgment"). When the doc names a real API,
config key, or third-party term that ships US spelling (`color: #fff`,
`Authorization` header, `LICENSE` file), keep that identifier verbatim: it is a
name, not prose. Spelling discipline applies to the words you write, not to the
symbols you quote.

### Plain English, no persuasion flourishes

Two patterns are banned because they read as machine cadence:

- **The contrastive flourish**: "That's not X. That's Y." Write the plain
  statement instead.
- **Consecutive very short sentences** that restate the same idea in different
  words. Say it once.

## Part 2: Curate for shorter, coherent clauses

### Limit a sentence to about 25 words

Long sentences with many clauses are hard for ESL readers and painful for
translators. Where a sentence resists shortening, convert it to a bullet list or
a table.

**The target is clause count, not word count.** A single long sentence with
three subordinate clauses is worse than three short sentences that together run
longer. Consider:

> **Prefer** (43 words, 3 sentences): An AI agent reads user stories,
> requirements, and code changes, then generates structured test cases. A human
> reviews and refines them before anything moves forward. Approved test cases go
> to manual execution or feed into test-code generation.

> **Avoid** (37 words, 1 sentence): An AI agent reads user stories,
> requirements, and code changes and generates structured test cases so a human
> can review and refine before anything moves forward to manual execution or to
> feed directly into test-code generation.

The shorter-reading version is the one with more words. Break the clause chain.

### Use lists to break up dense runs

When a sentence enumerates three or more parallel things, promote them to a
list. Lists clarify, catch the eye, and reduce density. Repeated bullet patterns
with the same shape become a table (this is also `structure.md` discipline).

### Active voice, strong verbs

The subject acts. Prefer the specific to the general, the concrete to the
abstract. Avoid "to be" and "to have" where a stronger verb exists.

| Prefer | Avoid |
|--------|-------|
| Choose encryption. | Encryption should be chosen. |
| You can now use encryption. | Support is now available for encryption. |

### Tighten: omit needless words

| Instead of | Write |
|------------|-------|
| In order to | To |
| Whether or not | Whether |
| Note that | (delete) |
| Please | (delete) |
| You should / you must | (delete, or use the imperative) |

Words to cut wherever they add nothing: *even, just, simply, so, then, very,
own, actually*. Prefer the present tense over *will / 'll / would*.

## Part 3: Write for ESL readers and translators

The rules above already help. These add to them.

- **Complete sentences over fragments.** A fragment forces the reader to
  reconstruct the missing part.
- **Keep modifiers next to what they modify.** Watch "only" closely: "only the
  admin can delete" and "the admin can only delete" say different things.
- **Resolve `-ing` and `-ed` ambiguity.** A word like "running" or "cached" can
  be a verb, an adjective, or a noun, and the ESL reader must work out which. A
  determiner usually fixes it: "the running process", "a cached response". Keep
  the gerund for titles ("Getting Started"); avoid it in running text where an
  alternative exists.
- **Avoid slang, idioms, and colloquialisms.** They do not translate and they
  confuse.
- **Include the business outcome when explaining a technical decision.** State
  what the choice bought, not only what was done. "We used autoscaling to hold
  response times during peak load" beats "We used autoscaling".

### Evaluate ESL and translator readability (not just assert it)

"ESL-friendly" is only real if it can be checked. Make it an evaluable step, not
an adjective in a checklist. Use concrete, tool-agnostic methods, cheapest first;
pick the one that fits the environment and report which you used.

1. **Proxy metrics (deterministic).** Count what a rule already bounds: sentence
   length (about 25 words or fewer), one main clause per sentence where possible,
   and a reading-grade target (aim for roughly grade 8 to 10) from any readability
   measure. Confirm one term per concept and one concept per term.
2. **Round-trip translation (optional; the translator-specific check).**
   Translate the passage to another language and back to English with any
   available translator, then compare. Idioms, tangled clauses, and ambiguous
   `-ing`/`-ed` words break in the round trip; if the back-translation drifts or
   confuses, rewrite the source. This check is **blind to register and
   punctuation** (a translator normalises an em-dash away, and universal
   metaphors survive), so it never replaces Method A or the rubric. Scale the
   effort to the rigour you want, and default to fast and cheap:
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
   reader and flags any sentence that needs a second pass to parse. The Part 2
   and Part 3 rules become the rubric, which turns the read into a repeatable
   score.

## Part 4: Inclusive language and content

Content is inclusive and free of bias. Avoid ableist and sexist language, and
language that carries racist structure or stereotype. Bias-free content is also
clearer content, so this rule serves accessibility as much as respect.

Replace the term on the left with a fitter term for the context (the right
column is a starting suggestion, not the only answer):

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

This table grows as new terms surface. When you replace a term, choose the word
that fits the domain, then use it consistently (Part 5).

## Part 5: Reuse standardised domain language

Do not hunt for fresh, more interesting ways to say the same thing. Choose one
term for a concept, define it on first use, and use that exact term every time.
Synonym variety reads as style to a native skimmer and as a new concept to a
translator.

**Disambiguate with determiners where a word could confuse.** Many words carry
two meanings. Add a small clarifying word rather than leaving the reading to
chance:

- "run the job" (execute) vs "the current run of the job" (one execution). Write
  "this run", "each run", "the run record".
- "the table" (database) vs "the table" (markdown). Name it: "the `users`
  table", "the comparison table above".
- "state" (status) vs "state" (Terraform file). Write "the resource's state" vs
  "the Terraform state file".

The determiner (`this`, `each`, `the <noun>`, a possessive) is cheap and it
removes a whole class of misreadings. Prefer adding one clarifying word over
trusting the reader to infer the sense.

## The write-mode checklist

```text
[ ] No em-dash anywhere in the authored prose.
[ ] Australian spelling in prose; quoted identifiers left verbatim.
[ ] No contrastive flourish, no consecutive short restatements.
[ ] Sentences curated to ~25 words; long ones split or listed/tabled.
[ ] Active voice and strong verbs; needless words cut.
[ ] Modifiers sit next to what they modify; -ing/-ed ambiguity resolved.
[ ] Technical decisions state the outcome they bought.
[ ] No non-inclusive terms; replacements fit the domain.
[ ] One term per concept, defined once, reused; determiners disambiguate.
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
