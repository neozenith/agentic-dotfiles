# Discovery Document Template & Style

The shape and voice of a discovery document. `SKILL.md` → Workflow says *when* each section is
populated; this file says *what the finished document looks like*.

## Style rules

1. **Front-load.** The first line of the document and of each section states the outcome; readers
   scan in an F-pattern and may not scroll.
2. **Headings are sentence fragments** — sentence case, no end punctuation. Lens headings use the
   exact form `### Current State — <lens>` / `### Desired State — <lens>` so pairs sort together.
3. **No bold-pseudo-headings.** A `**Label:**` line becomes a real heading, a table column, or is
   deleted. (Inline bold lead-ins inside a list item are fine.)
4. **Container by shape.** A record with ≥3 properties → table; a sequence or set → list; one
   idea → prose. Keep table cells short.
5. **Semantic line breaks in prose** — one clause per line, for clean agent diffs. Tables and list
   rows stay single-line.
6. **Every claim carries its evidence** — a `file:line` citation (Current State) or a verified URL
   (Desired State). An unverifiable claim is removed or marked
   (`resources/playwright-cli.md` → Marker Reference).
7. **Review-only voice.** The document is background for a reader deciding what to do next — it
   states what *is* and what *should be*, never task lists or implementation steps.

## Template

The skill owns `## Current State` and `## Desired State`. A caller workflow may append its own
sections after Desired State; those are preserved verbatim on every refresh.

````markdown
# <Title> — Discovery (Current & Desired State)

Review/background context: the as-is and to-be architecture behind <initiative>, not a plan.

## Current State
<What exists today — file:line citations from Track A research.>

### Current State — <lens A, e.g. component structure>
```mermaid
flowchart TD
    …            ← components/modules as they are; problem nodes in the danger fill
```

### Current State — <lens B, e.g. data flow>
```mermaid
flowchart LR
    …            ← the same system through a second lens; reuse node IDs
```

## Desired State
<The target end state — informed by verified Track B research.>

### Desired State — <lens A>
```mermaid
flowchart TD
    …            ← target of lens A; new/changed nodes in the good/process fills
```

### Desired State — <lens B>
```mermaid
flowchart LR
    …            ← target of lens B; visually distinguishable from Current
```
````

## Diagram rules

- **Lens menu, not one mega-diagram.** Pick the 2–3 lenses
  (`resources/mermaidjs-diagrams.md` → Lens Menu) that genuinely illuminate the initiative; do not
  force a lens that adds no signal. Use the same lenses on both sides.
- **Reuse node IDs across each Current → Desired pair** so the reader diffs visually: unchanged
  nodes keep the neutral fill, problems carry the danger fill in Current, additions/changes carry
  the good/process fills in Desired.
- Derive the palette from `resources/mermaidjs-diagrams.md` → Color Theming. Always pair `fill:`
  with an explicit `color:`; prefer `fill` + `color` without a same-hue `stroke` (a same-hue
  stroke fails the 3:1 border contrast check); pick fills dark enough for white text.
- Both gates block completion: mmdc renders clean in dark and light variants (exit 0), and every
  `classDef`/`style` passes WCAG AA contrast. Keep each diagram at medium density — split rather
  than exceed roughly 15 nodes.
