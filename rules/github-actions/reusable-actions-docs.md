---
paths:
  - ".github/actions/*"
---

# Reusable Action Documentation Contract

Every local composite/JS action under `.github/actions/<name>/` carries **two** documents
plus its `action.yml`. This is the action-flavoured sibling of the skill docs contract in
[`../claude_skills_docs.md`](../claude_skills_docs.md): same two audiences, **but there is no
`SKILL.md`** — an action has no runtime agent-skill surface; its machine interface is
`action.yml` (typed `inputs`/`outputs`). A new action is not "done" until both docs exist and
the README's diagrams pass the gates below.

| File | Audience | Answers | Voice |
|------|----------|---------|-------|
| `action.yml` | the **workflow** calling it | "what inputs/outputs, what does it run?" | declarative; every input `description` + `default` filled |
| `README.md` | a **human consumer** | "what is this, why, and how do I wire it into a workflow?" | explanatory, diagrams, copy-paste `uses:` quickstart |
| `CLAUDE.md` | an **agent maintaining it** | "why is it built this way, and how do I decide the next change?" | decision lenses (ADR log) |

> **No `SKILL.md`.** If you find yourself wanting one, the logic probably belongs in a
> `.claude/skills/` skill instead of (or in addition to) an action. Keep them DRY by role:
> `action.yml` owns the input/output contract; `README.md` links to it; `CLAUDE.md` never
> restates usage, only rationale.

## action.yml — the workflow-facing contract

- `name` + `description` (one line: what it turns into what).
- Every `input` has a `description` and, where sensible, a `default`; mark `required: true`
  only for what truly has no default (tokens, PR context).
- Prefer `using: composite` and keep secrets as **inputs** (`github-token`), never hard-coded.
- Reference bundled files via `${{ github.action_path }}` so the action is relocatable.

## README.md — the human explainer

Required sections, in order (model on a sibling action's README):

1. **Title + 2–3 sentence purpose** — what it does and the one reason it exists.
2. **Table of Contents** — a `<details><summary>` block with `<!--TOC-->` markers, populated by
   the `mdtoc` skill (never hand-maintained):
   ```bash
   uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 \
     .github/actions/<name>/README.md
   ```
3. **Quickstart** — the fastest path to value:
   - the `uses: ./.github/actions/<name>` snippet with its required `with:` inputs, **and**
   - how to run the engine directly for local iteration (the real command), **and**
   - the single most useful knob / escape hatch (an optional input).
   Every snippet must be copy-pasteable and accurate — verify it before writing it.
4. **Architecture** — **≥1 Mermaid diagram** authored per the `mermaidjs_diagrams` skill (gates
   below). Prefer dual-density: a small inline diagram + a fuller one in a `<details>` block.
5. **Reference** — the inputs/outputs table (or a link to `action.yml`), the files map, worked
   **examples**, and a **Troubleshooting** table (symptom → cause/fix).
6. **For maintainers** — a closing pointer to `CLAUDE.md`.

**Brand-agnostic** per [`../agnostic_examples.md`](../agnostic_examples.md) where the action is
reusable; project-specific defaults (e.g. a models path) belong in `action.yml` inputs, not prose.

### Architecture diagram rules (non-negotiable)

Governed by the `mermaidjs_diagrams` skill — a diagram is not done until **both** gates exit 0:

```bash
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_contrast.ts   .github/actions/<name>/README.md
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts .github/actions/<name>/README.md
```

- Palette from `color_theming.md`: primary nodes use a 600–700 fill with **`stroke:#fff,color:#fff`**;
  secondary nodes a 100-shade fill with a 500-shade stroke and `color:#1e293b`. Always pair `fill:`
  with an explicit `color:`. Only hex colors; `stroke-dasharray` uses spaces (`5 5`).
- Complexity: ≤ ~15 nodes per diagram; split dense graphs into overview + `<details>` detail.

## CLAUDE.md — the maintainer decision lens

The curated decision lens (model on a sibling `CLAUDE.md`). Required sections:

1. **Preamble** — read the ADR log first; each ADR carries a **Lens** to apply to the next decision.
2. **The development contract** — the local loop, run from repo root (never `cd`): how to
   syntax-check the engine, run `actionlint` on the workflow that uses it, and how to exercise it
   (e.g. a dry-run / benchmark). State what must be green before handoff.
3. **File map** — a table: each file and its one-line role.
4. **Architecture principles** — the invariants a change must preserve (e.g. "stay stdlib-only so
   `uv run --no-project` needs no network install"; "data files load relative to `__file__`").
5. **ADR log** — one entry per real decision: **Status · Context · Decision · Consequences · Lens.**
   Capture the *motivator* (the problem that forced the feature), and write the **Lens** as a
   forward-looking imperative so the next related question is answered without re-litigating.
6. **Extension checklist** — a `- [ ]` list a change must satisfy before it's done.
7. **Known gotchas** — the traps (with their symptom) that cost time to rediscover.

### The Lens principle

A good Lens converts a past decision into a future-proof rule.

> ❌ Historical: "We batched models per request."
> ✅ Lens: "When a per-item LLM loop trips a provider rate limit, batch items under a measured
> token budget before reaching for more retries — fewer requests beats more backoff."

## Done-when checklist (repeatable)

```text
[ ] action.yml — every input documented + defaulted; secrets are inputs; files via github.action_path
[ ] README.md  — purpose, mdtoc TOC, Quickstart (uses: + direct run + key input), ≥1 Mermaid
                 diagram, inputs/files/troubleshooting, "For maintainers" → CLAUDE.md
[ ] README diagrams — mermaid_contrast.ts AND mermaid_complexity.ts both exit 0
[ ] CLAUDE.md  — dev contract, file map, ADR log (Status/Context/Decision/Consequences/Lens,
                 motivators captured), extension checklist, known gotchas
[ ] NO SKILL.md (actions have no runtime skill surface)
[ ] brand-agnostic where reusable (agnostic_examples.md)
```
