# AI-Slop Smells: a curated pruning catalog

Load on first use during **audit** and **write/restructure**. This is the
negative-space companion to [`lenses.md`](lenses.md): lenses say what good docs
*do*; this says what sloppy docs *contain* so the audit can prune it.

The premise the whole skill rests on: **code is authoritative; documentation
drifts.** A slop smell is documentation that was *born* drifted or that *raises
the cost of keeping docs true*, so it is debt the moment it is written, not
only when the code later moves.

This catalog is **curated and grown by the maintainer over time.** Each entry is
one smell. Treat it as append-only doctrine; add a new `### S<n>` block when you
spot a recurring smell. It applies to standalone docs **and to in-code
documentation** (comments, docstrings) equally.

## How an auditor uses this

- For each smell, emit a finding with `category: slop`, `evidence` = which smell
  (`S<n>`) and why this instance matches, and a `fix` that **prunes or
  rewrites**, never just flags for the sake of it.
- Slop is the **one sanctioned deletion**: removing identified slop is correct,
  whereas deleting *drifted* content is forbidden (that is fix-or-flag). Keep
  the two straight: pruning a self-note is good; deleting a stale-but-real
  claim to "resolve" drift is graceful degradation of the docs.
- Severity is still claim-type × rung-traffic: slop on a high-traffic quickstart
  outranks the same slop in a deep corner.

## Entry template (copy this to add a smell)

```
### S<n>: <short name>
- **Smell:** what it looks like in the wild.
- **Why it's slop:** the concrete cost it imposes (misleads a reader, or raises
  refactor/update cost).
- **Good instead:** what replaces it.
- **Detect:** how to spot it (a grep, a structural tell, a question to ask).
- **Fix:** prune or rewrite guidance.
```

## The catalog

### S1: Self-addressed tracking notes

- **Smell:** comments/doc lines that narrate the *author's* task history:
  "done X", "TODO came back to this", "as requested", "step 3 of my plan",
  changelog-in-a-comment, instead of addressing a future reader.
- **Why it's slop:** the audience is wrong. A comment exists so the next reader
  understands **concisely and precisely WHAT this is and WHY**, not to journal
  what the author did. The note ages into noise the moment the task is over.
- **Good instead:** a comment in the reader's frame: what the code does and the
  reason it must be this way. If it records a decision, that is a WHY worth
  keeping (see "Capture THE WHY" below), phrased for the reader, not the doer.
- **Detect:** first-person/process language ("I", "we then", "as asked",
  "TODO(me)"), past-tense narration of edits, restating the diff.
- **Fix:** prune the journaling; if it encodes a real reason, rewrite it as a
  reader-facing WHY; if it is a genuine open task, move it to the issue tracker,
  not the prose.

### S2: Content that earns its keep only by existing

- **Smell:** a sentence/section/comment you could **delete and lose nothing**:
  it restates the obvious, paraphrases the code, or pads for length. Includes
  **hard-coded lists of values** (enum members, prices, file lists, flag names)
  copied into prose.
- **Why it's slop:** filler dilutes signal; and a duplicated value list is a
  second source of truth that silently drifts the instant the code changes,
  making every refactor a multi-file chore. Docs should have the **fewest touch
  points** so updating and refactoring stays lean.
- **Good instead:** say it once, where it lives. Replace an inline value list
  with a pointer to the authoritative definition ("the supported modes are
  defined in `<symbol>`"). Keep only prose that would be *missed* if removed.
- **Detect:** the delete test. Would removing this change a reader's
  understanding or action? A value/identifier in prose that also exists verbatim
  in code is a drift trap.
- **Fix:** prune pure filler; convert a duplicated list into a single pointer to
  its code definition.

### S3: Typographic tells no human types

- **Smell:** glyphs a person almost never types by hand, used as decoration or
  separators. The hallmark is the **interpunct/middle dot `·`** (U+00B7) strung
  between items: "fix · ci · test", "skeleton · discovery · assets". Its
  siblings: fancy "curly" quotes where straight ones suffice, and the
  non-breaking hyphen `‑`. None sit on a standard keyboard; they appear because
  a model emitted them. (The em-dash is the worst of this family and gets its
  own entry, S4.)
- **Why it's slop:** the `·` is a reliable **AI-authorship tell** (like the
  em-dash habit in S4 and the "not just X, but Y" cadence), so its presence
  quietly signals machine-generated text and erodes a reader's trust in the doc.
  As a separator it also carries **zero information** over a comma, slash, or a
  real list: pure stylistic flourish, the kind the delete test (S2) targets.
- **Good instead:** a plain separator a human would actually type: a comma,
  ` / `, a `|` in a table cell, or break the run into a real bullet list. Use
  straight quotes and a normal hyphen. Reserve `·` only for the rare place it is
  genuinely conventional (e.g. a units expression).
- **Detect:** `grep -n '·'`. Any prose/heading/table where items are joined by
  `·` is the tell.
- **Fix:** replace `·` with the appropriate plain separator: keep the
  separation, drop the glyph; convert a long `·`-joined run into a bullet list.

### S4: Em-dashes

- **Smell:** the em-dash `—` (U+2014) used anywhere: a parenthetical aside ("the
  fixture, migrated for this, parses"), an appositive, or a separator between
  clauses. Spaced (` — `) or unspaced. This is the single most common AI-slop
  smell in prose.
- **Why it's slop:** the em-dash is now the most recognisable
  **AI-authorship tell** there is; readers pattern-match it to machine-generated
  text and trust the doc less on sight. A human writing fast reaches for a
  comma, a colon, or a full stop. The glyph is not on a standard keyboard, which
  is precisely why its prevalence betrays the author.
- **Good instead:** a **comma** for a light aside, a **colon** to introduce or
  expand, **parentheses** for a true aside, or **split into two sentences** for
  emphasis. An en-dash `–` in a genuine numeric range (`1.6–1.11`, `pp. 4–9`) is
  legitimate and exempt.
- **Detect:** `grep -n '—'` (U+2014). Any hit in prose, headings, list intros,
  or even code comments is the smell.
- **Fix:** replace each `—` with a comma, colon, parentheses, or a sentence
  break. Preserve the meaning, drop the glyph. This is a sanctioned rewrite, not
  a flag.

## Capture THE WHY (the inverse failure)

Slop is content that should not exist; the opposite failure is the **missing
WHY**: code and docs capture *what* and *how* but not *why a thing exists*. The
reasoning is the most valuable and most perishable layer, and it rarely lives in
the artifact.

- Critical places (non-obvious decisions, deliberate constraints, "why not the
  simpler way") should carry a short WHY **in the comment/docstring next to the
  code**, so the decision lens travels with the context, not only in a distant
  doc.
- Bigger, project-shaping reasons are curated as **ADRs**; ADRs progressively
  accumulate the project's *values*, and those values become the decision lens
  for future work. A WHY in code is the local echo of that lens.
- The reasoning is often richest in the **language a maintainer uses while
  prompting**: that prose explains why a feature or requirement matters.
  Capture it with reverence, **like a letter to a future reader**, rather than
  letting it evaporate when the session ends.
- Audit emits these as `category: why-gap`. A why-gap is **flag-only, never
  auto-fixed**: the rationale cannot be invented, only the author knows it.
