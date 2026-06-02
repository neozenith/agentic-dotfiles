---
paths:
  - ".claude/skills/**"
---

# Claude Skill Documentation Contract

Every skill under `.claude/skills/<name>/` carries **three** documents with distinct
audiences. The *code* contract (Makefile `fix`/`ci`, tests, coverage) lives in
[`claude_skills.md`](claude_skills.md); this rule governs the *docs*. All three are
mandatory; a skill is not "done" until they exist and the README's diagrams pass the gates
below.

| File | Audience | Answers | Voice |
|------|----------|---------|-------|
| `SKILL.md` | the **agent at runtime** | "how do I operate this right now?" | imperative, terse, trigger-rich frontmatter |
| `README.md` | a **human consumer** | "what is this, why, and how do I start?" | explanatory, diagrams, quickstart |
| `CLAUDE.md` | an **agent maintaining the skill** | "why is it built this way, and how do I decide the next change?" | decision lenses (ADR log) |

Keep them DRY by role: don't duplicate the command reference across all three — `SKILL.md`
owns the operating detail; `README.md` links to it; `CLAUDE.md` never restates usage, only
rationale.

## SKILL.md — the agent operating manual

Already conventional in this repo. Minimum: YAML frontmatter (`name`, a `description` written
as **trigger conditions** + when-to-skip, `user-invocable` if applicable), a quick-start block,
a command/option reference, and pointers to lazy-loaded `resources/*.md`. Defer deep material
to `resources/` so the always-loaded surface stays small.

## README.md — the human explainer

Model it on a sibling skill's README (e.g. `art-gen`, `art-edit`). Required sections, in order:

1. **Title + 2–3 sentence purpose** — what it turns into what, and the one reason it exists.
2. **Table of Contents** — a `<details><summary>` block with `<!--TOC-->` markers, populated
   by the `mdtoc` skill (never hand-maintained):
   ```bash
   uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 \
     .claude/skills/<name>/README.md
   ```
3. **Quickstart** — the fastest path to value, mirroring the `art-gen`/`art-edit` shape:
   - the in-Claude invocation (`/<name> <natural-language brief>`), **and**
   - driving the script directly (the real command(s)), **and**
   - the single most common "escape hatch" / next-most-useful snippet.
   Every snippet must be copy-pasteable and accurate — verify it runs before writing it.
4. **Architecture** — **at least one Mermaid diagram** authored per the `mermaidjs_diagrams`
   skill (see the diagram rules below). Prefer **dual-density**: a small "at a glance" diagram
   inline, and a fuller one inside a `<details>` block for readers who want depth.
5. **Reference** — requirements/config, command reference (or a link to `SKILL.md`), worked
   **examples**, and a **Troubleshooting** table (symptom → cause/fix).
6. **For maintainers** — a closing pointer to `CLAUDE.md` for the dev contract + rationale.

**Brand-agnostic** per [`agnostic_examples.md`](agnostic_examples.md): no client/project-specific
names, palettes, or mascots — generic by construction.

### Architecture diagram rules (non-negotiable)

Diagrams are governed by the `mermaidjs_diagrams` skill. A diagram is not done until it passes
**both** gates with a 0 exit code:

```bash
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_contrast.ts   .claude/skills/<name>/README.md
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts .claude/skills/<name>/README.md
```

- **Palette from [`color_theming.md`](../skills/mermaidjs_diagrams/resources/color_theming.md).**
  For primary (foreground) nodes use a 600–700 Tailwind fill with **`stroke:#fff,color:#fff`** —
  white border + white text clears both the text-AA (≥ 4.5:1) and border-AA (≥ 3:1) checks. For
  secondary nodes use a 100-shade fill with a 500-shade stroke and `color:#1e293b`. **Always pair
  `fill:` with an explicit `color:`** (never rely on the theme default).
  - Watch-outs that fail the gate: a same-hue darker *stroke* on a primary fill (border < 3:1),
    and teal-600 `#0d9488` under white text (text 3.74:1 — use teal-700 `#0f766e`).
- **Complexity**: keep each diagram within the skill's limits (roughly ≤ ~15 nodes); split a
  dense diagram into a simple overview + a detailed `<details>` variant rather than one giant graph.
- Only hex colors; `stroke-dasharray` uses spaces (`5 5`), not commas.

## CLAUDE.md — the maintainer decision lens

This is the **curated decision lens**: a record that lets an agent self-answer a new question by
applying recorded reasoning instead of re-deriving or guessing. Model it on `art-gen`/`art-edit`
`CLAUDE.md`. Required sections:

1. **Preamble** — instruct the reader to read the ADR log first; state that each ADR carries a
   **Lens** to apply to the next decision.
2. **The development contract** — the two-command loop, run from repo root (never `cd`):
   `make -C .claude/skills/<name>/scripts fix` then `… ci`. `ci` must be 0-exit before handoff.
3. **File map** — a table: each file and its one-line role.
4. **Architecture principles** — the invariants a change must preserve.
5. **ADR log** — the heart. One entry per real decision, each with:
   **Status · Context · Decision · Consequences · Lens.**
   - **Capture motivators, not just outcomes.** Record *why a feature exists* (the problem that
     forced it), not only what was chosen — e.g. "feature X exists because Y was too slow/blocking."
   - The **Lens** is a forward-looking imperative heuristic: "When you next face <class of
     question>, decide it by <rule>." It is what makes the ADR reusable rather than historical.
6. **Extension checklist** — a `- [ ]` list a change must satisfy before it's done.
7. **Known gotchas** — the traps (with the symptom) that cost time to rediscover.

### The Lens principle

A good Lens converts a past decision into a future-proof rule. Write it so an agent reading only
the Lens can answer the next related question without re-litigating the original trade-off.

> ❌ Historical: "We made the fallback pure bash."
> ✅ Lens: "A fallback must never depend on the toolchain it backstops — keep it bash-only; a
> Python helper would die in the exact scenario it exists to rescue."

## Done-when checklist (repeatable)

```text
[ ] SKILL.md   — frontmatter triggers + quickstart + resources pointers
[ ] README.md  — purpose, mdtoc-populated TOC, Quickstart (invoke + direct + escape-hatch),
                 ≥1 Mermaid architecture diagram, troubleshooting, "For maintainers" → CLAUDE.md
[ ] README diagrams — mermaid_contrast.ts AND mermaid_complexity.ts both exit 0
[ ] CLAUDE.md  — dev contract, file map, ADR log (Status/Context/Decision/Consequences/Lens,
                 motivators captured), extension checklist, known gotchas
[ ] brand-agnostic (agnostic_examples.md); code gate green (make … ci)
```
