# The Maintainer's Voice Fingerprint

Distilled from ~10k lines of the maintainer's hand-written documentation in a
complex multi-stack data-platform monorepo (conventions docs, runbooks,
empirical investigations, design plans, CLI references). Load this file only
when `voice` was requested; apply it ON TOP of the lens discipline in
[lenses.md](lenses.md) — voice changes register, never structure.

One-line distillation: **second-person, evidence-counted, table-dense
engineering docs that declare their authority in the first sentence, document
what things do NOT do as rigorously as what they do, show every command with
its real output, cost every decision against its rejected alternative, and
reserve humour for self-deprecating battle scars — never for hype.**

## The 13 imitable rules

1. **Open with a 1-2 sentence purpose statement directly under the H1**,
   before any heading or TOC. If the doc is normative, declare its authority:
   "This document defines X… It is the source of truth for Y."
2. **Address the reader as "you"; signature phrase "You will want to…"** for
   setup steps. Use "we" only for shared design rationale ("This is why we
   have to…").
3. **Document the negative space.** Every component gets a "does NOT do" list
   as prominent as its "DOES" list; every decision gets a "Why NOT <the
   obvious alternative>" section.
4. **Tables whenever comparing ≥2 things or listing ≥3 structured facts.**
   Favourite column patterns: "What it IS / What it is NOT",
   "Purpose / Example", "Command / What it does".
5. **Commands in fenced `sh` blocks with inline `#` comments, followed by the
   literal expected output** under an "Output:" label (including the real ✅
   characters the tool prints). Dry-run is the default; applying is explicit —
   and the doc says so.
6. **Coin memorable proper-noun names for concepts and reuse them
   religiously** (the pattern: a vivid two-to-four-word title-case coinage for
   a recurring concept). Backtick every domain noun on every mention.
7. **Normatively blunt in conventions; never hedge without data.** Capitalised
   MUST / NOT / NEVER: "Each layer has strict responsibilities. Do not skip
   layers or bleed responsibilities across boundaries."
8. **Quantify everything.** Record counts, byte overheads, line counts, TTLs
   in both seconds and human units ("7,776,000 | 90 days"). Numbers replace
   adjectives; a claim worth making is a claim worth counting — add a
   `### Proof` section when the claim is surprising.
9. **Short declarative sentences; fragments allowed for emphasis.** "No
   conversion needed. DST-proof by construction." Bold the load-bearing words
   mid-sentence ("it **silently miscalculates** local times").
10. **Emoji are rare and semantic, never decorative**: 🚨 flanking a warning,
    ✅ only inside real command output, 🫠 exclusively for self-deprecating
    experience-scars, in parenthetical italic asides: "(Yes this comes from
    _experience_ 🫠 )".
11. **Headings are imperative tasks ("Adding a New Data Source", "Unlocking a
    Stuck State Lock") or strict pattern labels.** Tool READMEs lead with
    "Quickstart" (often a "***tl;dr***" block); specs lead with a metadata
    block (**Status** / **Branch** / **Stack**).
12. **Decisions carry their trade-off cost inline**: "Trade-off: <what it
    costs>. But <what it buys>." Rejected alternatives get their own
    subsection explaining the rejection ("X is mathematically cleaner, but
    the current approach already works. Switching adds complexity without
    solving a real problem.").
13. **Australian English** ("behaviour", "catalogue", "parametrise"), spaced
    em-dash appositions (" — "), `----` rules between major sections,
    `> **NOTE:**` blockquotes for warnings, `<details>` blocks (even nested)
    for opt-in depth with inviting summaries, `<!--TOC-->`-generated TOCs on
    anything over ~100 lines.

## What is deliberately absent

- No marketing fluff or superlatives about his own work — humour substitutes
  for hype.
- No passive-voice process narration.
- No walls of prose: longest unbroken run ≈ 4 sentences before a table, code
  block, or diagram interrupts.
- No unexplained magic values; no "TODO: document this" stubs in shipped docs.
- (The source docs ship fast and contain light typos — imitate the directness,
  not the typos.)

## Structural habits

- **Hub-and-spoke**: thin root README (concepts + layout + "read further at…"
  links); depth lives next to the code it describes.
- **Every abstract pattern points at concrete code**: pattern sections end
  with "Reference examples:" lists of real file paths, each annotated with
  *why* it's the example.
- **Mermaid diagrams with a disciplined WCAG-safe palette**, each followed by
  a one-sentence prose summary of what the diagram shows.
