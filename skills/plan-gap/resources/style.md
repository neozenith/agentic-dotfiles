# Gap Analysis Authoring Style

The voice-and-format contract for every file in a gap analysis spec set. `resources/spec-body.md`
defines *what goes where* (the tiers, sections, and templates); this file defines *how each chunk
is written*. Read both before authoring or restyling a spec.

Guiding principle — **precise and concise**: cut any token that does not change what the reader
*does*; express structure through Markdown (headings, tables, lists), not bold labels; keep the
loop-time files free of review-only context.

> Sources: [Diátaxis](https://diataxis.fr/reference/), [Google](https://developers.google.com/style/tables) &
> [Microsoft](https://learn.microsoft.com/en-us/style-guide/top-10-tips-style-voice) style guides,
> [Nygard ADR](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) / [MADR](https://adr.github.io/madr/),
> [Gherkin](https://cucumber.io/docs/bdd/better-gherkin/), [SemBr](https://sembr.org/),
> [WebAIM headings](https://webaim.org/techniques/headings/), [GFM](https://github.github.com/gfm/).

## Rules (all tiers)

1. **Front-load.** The first line states the outcome; readers scan in an F-pattern and may not scroll.
2. **Headings are verb-led sentence fragments** — sentence case, no end punctuation. An ID-prefixed
   heading separates the ID with a colon: `G<n>:`, `T<x.y>:`, `ADR<n>.<m>:`.
3. **No bold-pseudo-headings.** A `**Label:**` line becomes a real heading, a table column, or is
   deleted — bold is not navigable structure (WCAG 1.3.1). (Inline bold *lead-ins* inside a
   definition-style list item are fine, e.g. `- **Decision:** …`.)
4. **Container by shape.** A record with ≥3 properties → table; a sequence or set → list; one idea →
   prose. Keep table cells short — no nested lists inside a cell.
5. **Cut filler and constants.** Drop hedges (*currently*, *you can*, *simply*). Drop any field that
   is identical on every item (e.g. a `Cycle: RED → GREEN` that every ticket repeats, a `Mocks: none`).
   State a field only when it *varies*.
6. **Separate genres.** *Why* is short prose; *what* is an austere table; *steps* are the loop. Do not
   blend the three in one paragraph.
7. **One observable behavior per ticket**, phrased declaratively as `<actor> <observable outcome>`.
8. **ADRs are gap-scoped and bulleted.** Heading `ADR<n>.<m>: <concise decision>` (n = gap number,
   m = 1-based within that gap); the body is separate bullet lines — **Decision**, **Why**, optional
   **Rejected** / **Superseded**. No Pros/Cons table for a *settled* decision (that table belongs only
   to an `<!-- UNRESOLVED -->` placeholder while the question is still open).
9. **Semantic line breaks in prose only** — one clause per line, for clean agent diffs. Tables and
   list rows stay single-line.
10. **Self-contained, labeled chunks.** The test of a sentence: delete it — does the build change? If
    not, cut it.
11. **Fold meta, don't delete it.** Wrap the table of contents and the runner/execution blocks in
    `<details>` — a human skims past, an agent still reads the source. (A TOC generator resolves
    headings through the fold, and in-page anchors auto-expand the block.)
12. **Context economy.** The index, the gap files, and the ticket files are the agent's loop
    working-set; review/background (Current & Desired State) lives in the **Discovery** file, never in
    the working-set tiers.
13. **Cross-link by ID.** A gap's Depends-on/Blocks link to gap files; a ticket's Depends-on links to
    ticket files; every file back-links to the index. Use the `G<n>` / `T<x.y>` IDs as link text.
14. **No `·` middot delimiter.** Humans do not write middots. Use commas in prose and table cells, a
    colon after a heading ID, and a multiline blockquote list for navigation — never an
    inline-delimited run.

## Document set

A gap analysis spec is a **folder** (`<plan>/`, a kebab-case stem derived from the initiative) whose
`README.md` is the index; the siblings strip the stem. Each tier has a distinct genre and load profile.

| File | Tier | Genre | Loaded |
|------|------|-------|--------|
| `README.md` | index | navigation + framing + execution plan | loop entry |
| `G<n>.md` | gap | explanation + reference + ticket pointers | per-gap work |
| `G<n>-T<x.y>.md` | ticket | austere reference — one TDD slice | per-ticket work |
| `DISCOVERY.md` | discovery | Current + Desired State (multi-lens) + per-gap increments | human review only |
| `STYLE.md` *(optional)* | style | per-spec deviations from this contract | when editing the set |

The split exists for **context economy** (rule 12): an agent executing the `/loop` pays
attention-tokens for the index + the one gap + the one ticket it is on. Current/Desired State,
SOTA citations, and the before/after architecture are review material — they go in Discovery so they
never burden the loop. A small spec (1–2 gaps) MAY inline gap and ticket detail into the index, but
the moment a gap grows its own ADRs, key-logic snippet, or ≥3 tickets, split it out.

## Tier voice and shape

### Index (`README.md`)

Genre: navigation + framing. Keep the diagrams and the rolled-up tables here; everything else is a
pointer to a gap file.

- The **table of contents** and the **Execution Plan body** are each wrapped in `<details>`
  (collapsed for skim). Keep the `## Execution Plan` heading *visible* above its fold so the runner
  prompt is one expand away.
- A one-line **Background** blockquote points to `-DISCOVERY.md` (where Current/Desired State moved).
- Overview lists gaps as links + one-line outcomes.
- **Decisions (ADRs)** is a roll-up table — columns **ADR, Decision, Why**, one row per ADR, the ID
  linking to its owning gap file. It is a primary review lens, so every settled decision appears here.
- Gaps, Progress, and Success/Negative measures are tables; gap and ticket IDs are links.
- Diagrams (Overview dependencies, Gap Map, Dependencies) obey the mermaid gates below.

### Gap (`G<n>.md`)

Genre: explanation (why) + reference (what) + pointer (tickets). A blockquote-list nav header, a
front-loaded lead, then austere sections. See the template in `resources/spec-body.md`.

Cut from any older inline format: the `**Current:** / **Gap:**` bold labels (fold into the lead +
a `## Context` section), the ADR Pros/Cons tables (settled ADRs are bulleted), and any Outputs row
that merely restates a ticket.

### Ticket (`G<n>-T<x.y>.md`)

Genre: austere reference — one behavior, one test, the implementation target, the dependencies. A
blockquote nav header, a `- [ ] **Done**` checkbox, one lead sentence stating the precise
assertion-worthy contract, then a two-column table. See the template in `resources/spec-body.md`.

Cut from any older format: `Cycle: RED → GREEN` (every ticket is red-green-refactor — it lives in
the loop prompt, not on each ticket), `Mocks: none` (state mocks only when non-empty), the
`Behavior:` label (the title *is* the behavior; the lead sentence adds precision), and the 3-level
Test/Implementation bullet nest (collapse to table rows).

### Discovery (`DISCOVERY.md`)

Review/background only — the architecture that motivates the gaps, not loaded during the loop. Nav is a
blockquote-list backlink to the index, followed by a one-line review-only note. Holds `## Current State`
and `## Desired State` — **each as 2–3 lens diagrams** picked from the menu in
`resources/mermaidjs_diagrams.md` — and `## Gap Increments`, **one diagram per gap** under the exact
heading `### G<n> increment`. Gap files link to their increment by anchor (`DISCOVERY.md#g<n>-increment`); the
diagram never lives inline in the gap (rule 12).

## Diagrams

- **Lens menu, not one mega-diagram.** Current and Desired State each pick the 2–3 lenses (component,
  data-flow, sequence, deployment, state, entity — `resources/mermaidjs_diagrams.md`) that genuinely
  illuminate the initiative. Do not force a lens that adds no signal.
- **Reuse node IDs across the chain.** Current → Desired → every gap increment share node IDs so the
  reader diffs visually. Each increment starts from the prior baseline and highlights only the nodes
  *that* gap changes (process/good fills); `G<n+1>` builds on `G<n>`.
- Derive the palette from `resources/color_theming.md`. Use **`fill` + `color` only, no `stroke`** —
  a same-hue stroke fails the 3:1 border check; pick fills dark enough for white text (greens ≥
  `#166534`).
- Both gates are blockers; run them via `resources/mermaidjs_diagrams.md` before declaring a diagram
  done:
  - the **contrast** gate — WCAG AA on every `classDef`/`style`.
  - the **complexity** gate — medium density by default; a Gap Map MAY run detail-density (its 3×N
    current→gap→desired mapping is justified), captioned as such.

## Conventions

- **Dropped tickets:** strike the title in the gap's Tickets table —
  `~~<behavior>~~ **Dropped** (reason)` — keep the ticket file and its `[x]` (no work is owed), and
  record the reason in the index Progress section.
- **Done state is data, not style:** a restyle never flips `[ ]`↔`[x]`. Preserve whatever each file
  holds — the checkbox is execution state, the style pass only changes prose.
