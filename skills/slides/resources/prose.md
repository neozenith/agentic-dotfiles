# Global-Audience Prose Standard

The sentence-level rules for every word this skill ships: slide copy, the docs it
writes, and its own prose. A **self-contained copy**, carried here on purpose so
the skill depends on nothing outside its own directory.

Two readers drive every rule: the skimmer who reads one line and moves on, and the
ESL reader or translator who must parse the sentence on the first pass. A sentence
that works for those two works for a native reader as well.

`scripts/prose_check.py` gates the mechanical subset (`make ci` in a scaffolded
deck). The rest needs a reader.

## The hard mechanics

A file that breaks one of these is not done.

1. **No em-dash. Ever.** The `—` (U+2014) is the clearest tell of unreviewed
   machine authorship. Use a comma, a colon, parentheses, or split the sentence.
   An en-dash in a genuine numeric range (`1.6–1.11`, `180–340 wpm`) is fine.
2. **Australian spelling in prose**: organise, colour, prioritise, licence (noun),
   judgement, behaviour. Quoted identifiers keep their own spelling verbatim:
   `color: #fff`, the `LICENSE` file, `Authorization`. A name is not prose.
3. **No persuasion flourishes.** Two banned patterns: the contrastive flourish
   ("That's not X. That's Y.") and consecutive very short sentences restating one
   idea in different words. Say it once, plainly.
4. **About 25 words per sentence**, and the target is clause count, not word
   count. Three short sentences beat one chained sentence, even when they run
   longer together. A sentence that resists splitting becomes a list or a table.
5. **Active voice, strong verbs.** "Choose encryption", not "Encryption should be
   chosen". Prefer the specific to the general, the concrete to the abstract.
6. **Cut needless words.** *In order to* becomes *to*. Delete *note that*,
   *please*, *you should*, *even*, *just*, *simply*, *very*, *actually*. Prefer
   the present tense over *will*.
7. **Complete sentences over fragments.** A fragment makes the reader rebuild the
   missing part.
8. **No idioms, slang or figurative phrases.** They do not translate.
9. **Keep modifiers next to what they modify.** Watch "only": "only the admin can
   delete" and "the admin can only delete" say different things.
10. **Resolve `-ing` and `-ed` ambiguity with a determiner**: "the running
    process", "a cached response". Keep the gerund for titles.
11. **Inclusive terms only**: allow list (not `whitelist`), deny list (not
    `blacklist`), primary or main (not `master`), replica (not `slave`), stop or
    cancel (not `abort`/`kill`), quick check (not `sanity check`), placeholder
    (not `dummy value`). Quoting a banned term is how you name it without using
    it, and it is how the checker reads the difference.
12. **One term per concept**, defined once, then reused. Synonym variety reads as
    style to a native skimmer and as a new concept to a translator. Disambiguate
    with a determiner: "the Terraform state file" against "the resource's state";
    "this run" against "the job".
13. **State the outcome a technical decision bought**, not only what was done.
    "Autoscaling holds response times during peak load" beats "we used
    autoscaling".

## Applied to slide copy

Slides are the shortest prose there is, so the rules bite hardest.

- A bullet is **a complete sentence or a clean fragment with a determiner**, never
  a chain of clauses. If it needs a comma splice, it is two bullets.
- The em-dash is most tempting in a bullet. Use a colon for a definition, a comma
  for an aside, or a second bullet.
- **Bold carries the point**, and the first few words must land it. A skimmer
  reads the bold and stops.
- One concept per slide is what keeps one term per concept honest.
- Say what is not built. An audience cannot tell an aspiration from a deployment,
  and a diagram of an unbuilt system is a false claim.

## Checking it

Cheapest first. Report which methods you ran.

**Method A, the deterministic gate** (free; `scripts/prose_check.py` covers the
first item, the rest need a read):

- longest sentence at or under 25 words;
- no sentence with more than two nested subordinate clauses;
- reading grade at or under 12 (aim for 8 to 10) by any readability measure;
- one term per concept, one concept per term.

**Method B, the reader's seat** (the primary check): read as an intermediate ESL
reader (CEFR B1). Any sentence needing a second pass fails. Any idiom fails. Any
bare `-ing`/`-ed` left ambiguous between verb and noun fails.

**Method C, round-trip translation** (optional, confirmatory): translate the
passage out and back with any translator, then compare. Idioms, tangled clauses
and ambiguous words break in the round trip. It is **blind to punctuation and
register** (a translator normalises an em-dash away), so it never runs alone and
never replaces Method A or B. Default to skipping it when A and B are clean. To
escalate, use diverse pivots: German exposes nested clauses, Mandarin Chinese
exposes `-ing`/`-ed` and definiteness ambiguity, Arabic maximises idiom distance.

## The checklist

```text
[ ] No em-dash in authored prose (a quoted/code-span mention is not a use).
[ ] Australian spelling in prose; quoted identifiers left verbatim.
[ ] No contrastive flourish, no consecutive short restatements.
[ ] Sentences about 25 words or fewer; long ones split, listed or tabled.
[ ] Active voice, strong verbs, needless words cut.
[ ] Modifiers next to what they modify; -ing/-ed ambiguity resolved.
[ ] Technical decisions state the outcome they bought.
[ ] Inclusive terms throughout; replacements fit the domain.
[ ] One term per concept, defined once, reused; determiners disambiguate.
```
