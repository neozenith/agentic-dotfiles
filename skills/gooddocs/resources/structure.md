# Markdown Structure: Encoding Information in Hierarchy

How to use markdown's structural features — headings, lists, tables, fences,
whitespace — so a document's *shape* carries its information. Applies to every
lens in [lenses.md](lenses.md) and is the rulebook for `restructure` mode.

## The evidence in four sentences

Readers scan, they don't read: at most ~28% of words, more typically ~20%
(NN/g). The best realistic outcome is **layer-cake scanning** — fixating on
headings and first sentences, dropping into body text only where needed; the
F-pattern wall-of-text skim is the failure mode formatting exists to prevent.
Working memory holds ~4±1 chunks (Cowan 2001), so groups of anything —
sections, bullets, phases — should stay near that size. Caution: the
oft-quoted "whitespace improves comprehension 20% (Lin 2004)" is a misquoted
citation — justify whitespace by chunking and scanning, never by that number.

## The 18 rules

### Headings (the document's API)

1. **One H1 (the title); never skip levels.** The heading tree is the outline;
   skips break navigation. (Lintable: MD001/MD025/MD041.)
2. **Stop at H3; H4 is a restructure signal, H5+ forbidden.** Deep heading
   nesting means the chunking is wrong, not the indentation.
3. **Headings are frontloaded statements, not labels.** "Sessions resume from
   the URL" beats "Session considerations". Headings appear out of context
   (TOC, anchors, search) and must carry meaning alone.
4. **The TOC test:** the headings alone must read as a coherent outline of the
   document — layer-cake scanners see nothing else.
5. **Sibling headings use parallel phrasing** — all imperative or all noun
   phrases, never mixed.
6. **A heading every 3-5 paragraphs; no orphan headings** (heading followed
   immediately by another heading) **and no lonely subheading** (exactly one
   H3 under an H2 — a split with one part is not a split).

### Frontloading (BLUF — scoped by rung)

7. **Doc opens with a 1-3 sentence summary; every section's first sentence
   states its point; every paragraph's first sentence is its topic sentence.**
   Scanners read first sentences and bail. **Scope:** full force on lookup
   pages (how-to, reference, reports); on tutorials the BLUF is a
   *destination preview* ("here's what you'll build"), never each step's
   resolution; explanations may open with a motivated question. Scanning
   research comes from lookup tasks — learning pages legitimately favor
   connected, coherent prose (see lenses.md counter-evidence).
8. **Paragraphs: one idea, 3-5 sentences.** A run of one-sentence paragraphs
   is faulty organization — merge them or convert to a list.

### Lists and tables

9. **Bullets only for genuinely parallel, enumerable items; reasoning stays in
   prose.** If items carry "because/unless/therefore" relationships, bullets
   destroy the logic (Tufte's Columbia-slides critique). Numbered lists ONLY
   for sequence or priority. Every list gets a lead-in sentence ending in a
   colon.
10. **Parallel grammar, consistent fragment-vs-sentence style, ~7 items before
    grouping, nesting ≤ 2 levels.**
11. **≥3 bullets repeating an internal pattern → promote to a table.**
    `- **Term** — definition` is the intermediate form for name→explanation
    pairs; tables are for scanning across two dimensions. Don't tablify what
    reads fine as a list.

### Whitespace and rhythm

12. **Blank line between every block; no prose wall longer than ~4 paragraphs
    without a visual interrupt** (heading, list, table, or code fence — they
    act as fixation anchors). (Lintable: MD012/MD022/MD031/MD032.) On
    learning-rung pages (tutorial narration, explanation) coherent prose may
    run longer when the connected reasoning is doing the work.
13. **Pick a source-line discipline and state it:** ~80-100-col wrap, or
    semantic line breaks (one sentence/clause per line — diff-friendly for
    specs under review; [sembr.org](https://sembr.org/)). Never reflow-wrap:
    one-word edits become whole-paragraph diffs.
14. **Horizontal rules only at genuine document-level seams** (metadata →
    body, body → appendix) — headings already separate sections.

### GFM features as structure

15. **Use the extended features structurally, with restraint:**
    language-tagged fences always (MD040); `<details>` for progressive
    disclosure of logs, deep-dives, and big tables; intra-doc anchor links in
    anything long enough for a TOC; alerts (`> [!NOTE]`, `> [!WARNING]`)
    capped ~1-2 per page, never stacked — if everything is highlighted,
    nothing is.

### Visuals and cascading detail

16. **Diagrams are first-class visual interrupts.** Where information is
    flow-, structure-, or sequence-shaped, a diagram breaks the prose wall
    AND encodes the information more densely than the paragraph it replaces.
    Every diagram gets a one-sentence prose summary directly below it (the
    diagram is scannable; the sentence is searchable and accessible).
    Authoring is delegated: diagram curation, palette, and the contrast/
    complexity gates belong to the `mermaidjs_diagrams` skill — invoke it in
    a subagent rather than hand-rolling mermaid.
17. **Dual-density cascading detail:** show the visually simplified diagram
    inline at the top level, and hide the ultra-detailed variant inside a
    `<details><summary>` block immediately after it. The happy-path reader
    gets the at-a-glance model; depth is opt-in, not imposed. The same
    cascade applies to prose: summary table inline, full matrix in
    `<details>`; headline numbers inline, full logs in `<details>`. Give
    every `<summary>` an inviting, specific label ("Detailed flow",
    "Full configuration matrix") — never a bare "Details".

### Specs and plans

18. **Specs/plans follow a canonical skeleton** with a status/metadata block,
    BLUF summary, stable numbered requirement IDs (R1, R2… — citable from
    reviews and commits), and an explicit Open Questions section (the Rust
    RFC's "Unresolved questions" — prevents fake completeness).

## Structure smells (what restructure mode hunts)

| Smell | Symptom | Fix |
|-------|---------|-----|
| Prose wall | >4 paragraphs, no interrupt | insert heading/list/table at the idea seams |
| Bullet wall | 10+ flat bullets; sections that are only bullets | group under headings, or restore reasoning to prose |
| Deep nest | bullets ≥3 deep or H4/H5 | re-chunk: promote to sections or flatten |
| Heading skip | H2 → H4 | fix levels (MD001) |
| Vague label heading | "Overview", "Notes", "Considerations" | rewrite as a frontloaded statement |
| Orphan / lonely heading | heading→heading; one H3 under an H2 | merge or genuinely split |
| Buried lede | summary at the bottom | move to BLUF position |
| Mixed-grammar list | fragments + sentences interleaved | pick one; rewrite for parallelism |
| Disguised table | repeated `**Bold** — value (note)` bullets | promote to a table |
| Alert spam | 3+ admonitions per screen, stacked alerts | demote to prose; keep the one that matters |
| Naked code fence | no language tag, no lead-in | tag it; one sentence saying what it shows |
| Monolithic diagram | one dense 20+-node diagram trying to show everything | split into the dual-density pair: simplified inline + detailed in `<details>` |
| Orphan diagram | diagram with no prose summary beneath it | add the one-sentence summary (rule 16) |
| Zombie metadata | status block stale vs reality | update or delete — wrong status is worse than none |

## Canonical skeletons

### Spec / design doc

```markdown
# <Title as a claim: "Sessions are durable and URL-resumable">

| Status | Owner | Last updated | Tracking |
|--------|-------|--------------|----------|
| Draft / In review / Approved / Superseded | @who | YYYY-MM-DD | link |

## Summary
<BLUF: 2-4 sentences — what, why, and the decision if made.>

## Background
<Why now; constraints. Link to prior docs, don't restate them.>

## Goals and non-goals
- **Goals:** G1 …, G2 …
- **Non-goals:** NG1 … (explicit scope fence)

## Requirements
- **R1.** The server MUST mint all session IDs.   <!-- RFC 2119 verbs -->
- **R2.** …

## Design
### <Frontloaded statement per component>
<Prose for reasoning; one diagram/table/fence per subsection as anchor.>

## Alternatives considered
| Option | Pros | Cons | Why rejected |
|--------|------|------|--------------|

## Open questions
- [ ] Q1: … (owner, needed-by)
```

### Plan file with task tracking

```markdown
# Plan: <outcome as a result: "Asset explorer ships with audit trail">

**Status:** In progress | **Owner:** @who | **Updated:** YYYY-MM-DD
**Done means:** <1-2 sentence acceptance statement for the whole plan>

## Summary
<BLUF: approach in 2-3 sentences + current phase.>

### Phase 1: <result, not activity: "Backend persists sessions">
Goal: <one sentence>.

- [x] T1.1 Define session schema
- [ ] T1.2 Cold-start rebuild from store

**Acceptance:** <observable check — a command to run, behavior to see>.

## Decisions log
| Date | Decision | Why |
|------|----------|-----|

## Open questions / blockers

## Out of scope
```

3-5 phases max (the chunk limit); every task checkable against an observable
criterion, not vibes.

## Lintable vs judgment

Mechanics are lintable with markdownlint: MD001/MD025/MD041 (heading tree),
MD022/MD031/MD032/MD012 (blank-line discipline), MD004/MD005/MD007/MD029/MD030
(list consistency), MD040 (fence language), MD013 (line length), MD043
(required skeleton per glob). Scriptable but non-stock: orphan headings,
nesting depth, flat-list length, alert count. **Pure judgment — this skill's
actual job:** frontloaded headings, the TOC test, BLUF placement, parallelism,
prose-vs-bullets for reasoning, list→table promotion, `<details>` candidates.

## Sources

NN/g: [How Users Read](https://www.nngroup.com/articles/how-users-read-on-the-web/) ·
[How Little Do Users Read](https://www.nngroup.com/articles/how-little-do-users-read/) ·
[Layer-Cake Pattern](https://www.nngroup.com/articles/layer-cake-pattern-scanning/) ·
[F-Pattern](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/) ·
[Inverted Pyramid](https://www.nngroup.com/articles/inverted-pyramid/) ·
[Headings Are Pick-Up Lines](https://www.nngroup.com/articles/headings-pickup-lines/) ·
[Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/).
[Cowan 2001 (4±1 chunks)](https://www.cambridge.org/core/journals/behavioral-and-brain-sciences/article/magical-number-4-in-shortterm-memory-a-reconsideration-of-mental-storage-capacity/44023F1147D4A1D44BDC0AD226838496) ·
[Dyson & Haselgrove 2001 (line length)](https://www.sciencedirect.com/science/article/abs/pii/S1071581901904586) ·
whitespace-myth debunks: [Myhill on "Lin 2004"](https://www.linkedin.com/pulse/lin-2004-did-discover-margins-white-space-increase-20-carl-myhill),
[Poole on Wheildon](https://alexpoole.info/blog/fighting-bad-typography-research/).
[Google tech-writing: paragraphs](https://developers.google.com/tech-writing/one/paragraphs) ·
[lists & tables](https://developers.google.com/tech-writing/one/lists-and-tables) ·
[Google Markdown style](https://google.github.io/styleguide/docguide/style.html) ·
[Microsoft lists](https://learn.microsoft.com/en-us/style-guide/scannable-content/lists) ·
[GitLab style guide](https://docs.gitlab.com/development/documentation/styleguide/) ·
[plainlanguage.gov](https://www.plainlanguage.gov/guidelines/) ·
Tufte, *The Cognitive Style of PowerPoint*.
Templates: [Rust RFC](https://github.com/rust-lang/rfcs/blob/master/0000-template.md) ·
[Oxide RFD 1](https://rfd.shared.oxide.computer/rfd/0001) ·
[Nygard ADRs](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) ·
[PEP 12](https://peps.python.org/pep-0012/).
Mechanics: [markdownlint rules](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md) ·
[sembr.org](https://sembr.org/) ·
[GitHub alerts](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts).
