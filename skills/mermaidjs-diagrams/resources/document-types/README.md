# Document Types

A **document type** is a named, reusable shape for a whole Mermaid-heavy
markdown document: which diagrams appear, in what order, what invariants hold
across them, and what "done" means.

This is a different scope from the rest of the skill. `SKILL.md` and the other
`resources/` files govern **one diagram's** correctness — its density, its
palette, its contrast, its render. A document type governs the **sequence** of
diagrams and the contracts that run across the sequence.

| Scope | Owned by | Example rule |
|---|---|---|
| One fence | `SKILL.md`, `color_theming.md`, `contrast_tooling.md` | Every `classDef` with a `fill:` must set `color:`. |
| One section (a lens) | `diagram_organization.md` | Overview ≤12 nodes inline, detail ≤35 nodes collapsed. |
| One document | `document-types/*.md` | Every fence in the document reuses one shared `classDef` vocabulary. |

## Selecting a type

Match on what the user asked for, not on the subject matter. The same topic can
be written as either type.

| The request says | Type | File |
|---|---|---|
| "educational", "illustrative guide", "explain X visually", "teach me X", "one-pager on X", "distil this topic", "explainer" | Educational | [`educational.md`](educational.md) |
| "architecture doc", "how the system fits together", "C4-ish", "document this codebase", "system overview", "zoom into subsystem X" | Architectural | [`architectural.md`](architectural.md) |

When the request is ambiguous — "document our auth system" could be either —
resolve it by asking what the reader must be able to *do* afterwards:

- **explain a concept to someone else** → Educational.
- **locate a component, trace a call, or change something** → Architectural.

If the answer is genuinely both, write the Educational one-pager first and link
it from the Architectural document's L0 orientation section. Do not interleave
the two shapes in one file; their diagram sequences fight each other.

## What every type shares

These hold regardless of which type you pick. They are the reason the types are
siblings rather than unrelated templates.

1. **One shared `classDef` vocabulary per document.** Define the semantic roles
   once, name them the same way in every fence, and never let a role change
   colour between fences. A reader who learns the palette in diagram 1 must be
   able to read diagram 7 without relearning it. See
   [`../color_theming.md`](../color_theming.md) for the source palette; never
   pick ad-hoc hex.
2. **Every fence answers one named question.** If you cannot write the question
   above the fence and the takeaway below it, the fence is decoration — cut it
   or split it.
3. **Density budgets are per fence, not per document.** An always-visible fence
   targets the `low` preset (≤12 nodes, VCS ≤25). A collapsed detail fence
   targets `high` (≤35 nodes, VCS ≤60).
4. **Both gates run before the document is done.**

   ```bash
   bun run scripts/mermaid_complexity.ts path/to/document.md
   bun run scripts/mermaid_contrast.ts   path/to/document.md
   ```

   Non-zero exit means stop and fix. Shrink or split the fence; do not raise
   the budget.
5. **ASCII-only node labels, `<br/>` for line breaks.** Not `\n`, not Unicode
   box-drawing or emoji inside labels. See `SKILL.md` → *Common Pitfalls*.
6. **No live `-beta` fences.** `architecture-beta`, `block-beta`,
   `packet-beta`, `radar-beta`, `sankey-beta`, `treemap-beta`, and
   `xychart-beta` frequently fail to render on GFM hosts, which pin an older
   Mermaid version than your local toolchain. Ship them as a rendered PNG or
   SVG with the `.mmd` kept as a sibling source file. See
   [`../gfm_beta_diagrams.md`](../gfm_beta_diagrams.md).

## Adding a new type

A new file in this directory earns its place when it has a **distinct diagram
sequence** — not merely a different subject. `educational.md` and
`architectural.md` differ because one advances through *concepts* and the other
recurses through *levels of detail*. A "runbook" type would qualify (it
advances through *failure states*); a "security architecture" type would not —
that is the Architectural type with the security lens selected.

Each type file must state, in this order:

1. **Trigger** — the phrases that select it.
2. **Contract** — the invariants that make a document of this type recognisable.
3. **Sequence** — the ordered beats or levels.
4. **Diagram selection** — which Mermaid type serves which beat.
5. **Palette** — the semantic role set for the type.
6. **Anti-patterns** — the specific failures this type invites.
7. **Done checklist** — verifiable, not aspirational.
