---
paths:
  - ".claude/skills/**"
---

# Claude Skill Documentation Contract

This is the **documentation** child of the skill/rule family rooted at
[`index.md`](index.md) (which owns the 500-line size invariant and the
self-balancing tree). Its sibling [`scripts.md`](scripts.md) owns the *code*
contract (Makefile `fix`/`ci`, tests, coverage); this rule governs the *docs*.

Every skill under `.claude/skills/<name>/` carries **three** documents with distinct
audiences. All three are mandatory; a skill is not "done" until they exist and the
README's diagrams pass the gates below.

| File | Audience | Answers | Voice |
|------|----------|---------|-------|
| `SKILL.md` | the **agent at runtime** | "how do I operate this right now?" | imperative, terse, trigger-rich frontmatter |
| `README.md` | a **human consumer** | "what is this, why, and how do I start?" | explanatory, diagrams, quickstart |
| `CLAUDE.md` | an **agent maintaining the skill** | "why is it built this way, and how do I decide the next change?" | decision lenses (ADR log) |

Keep them DRY by role: don't duplicate the command reference across all three — `SKILL.md`
owns the operating detail; `README.md` links to it; `CLAUDE.md` never restates usage, only
rationale.

> **The only skill these rules name by relative path is `mermaidjs_diagrams`** — because the
> diagram gates are *executable scripts* you must run, not a prose example to imitate. Do not
> introduce "model it on skill X" pointers to any other skill; the quality bar is the
> distilled checklists in this file, not another skill's current state.

## SKILL.md — the agent operating manual

Already conventional in this repo. Minimum: YAML frontmatter (`name`, a `description` written
as **trigger conditions** + when-to-skip, `user-invocable` if applicable), a quick-start block,
a command/option reference, and pointers to lazy-loaded `resources/*.md`. Defer deep material
to `resources/` so the always-loaded surface stays small.

## README.md — the human explainer

Required sections, in order:

1. **Title + 2–3 sentence purpose** — what it turns into what, and the one reason it exists.
2. **Table of Contents** — a `<details><summary>` block with `<!--TOC-->` markers, populated
   by the `mdtoc` skill (never hand-maintained):
   ```bash
   uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 \
     .claude/skills/<name>/README.md
   ```
3. **Quickstart** — the fastest path to value, in three copy-pasteable forms:
   - the in-Claude invocation (`/<name> <natural-language brief>`), **and**
   - driving the script directly (the real command(s)), **and**
   - the single most common "escape hatch" / next-most-useful snippet.
   Every snippet must be copy-pasteable and accurate — **run it before you write it.**
4. **Architecture** — **at least one Mermaid diagram** authored per the `mermaidjs_diagrams`
   skill (see the diagram rules below). Prefer **dual-density**: a small "at a glance" diagram
   inline, and a fuller one inside a `<details>` block for readers who want depth.
5. **Reference** — requirements/config, command reference (or a link to `SKILL.md`), worked
   **examples**, and a **Troubleshooting** table (symptom → cause/fix).
6. **For maintainers** — a closing pointer to `CLAUDE.md` for the dev contract + rationale.

**Brand-agnostic** per [`../agnostic_examples.md`](../agnostic_examples.md): no client/project-specific
names, palettes, or mascots — generic by construction.

### What makes a README good vs. bad (the curated checklist)

Judge a README against these signals — not against any other skill. The left column is the bar;
the right column is the failure mode that most often replaces it.

| Dimension | ✅ Good — the bar | ❌ Bad — the anti-pattern |
|-----------|------------------|---------------------------|
| **Opening** | 2–3 sentences: what-into-what + the one reason to exist. A reader knows in 10s if this is their tool. | A marketing paragraph with no runnable command in the first screen; the reader still doesn't know what it *does*. |
| **Quickstart placement** | A runnable command is the first thing after the TOC. | The first command is buried below pages of background/theory. |
| **Snippet fidelity** | Every command was actually executed; flags, paths, and output are real. | Illustrative pseudo-commands with wrong flags or stale paths — a copy-paste that errors destroys trust instantly. |
| **Three entry forms** | Shows the in-Claude `/<name>` invocation **and** the direct script call **and** one escape hatch. | Only one form (usually the agent invocation), leaving direct/CI users stuck. |
| **DRY by role** | Links to `SKILL.md` for the exhaustive option table; points to `CLAUDE.md` for rationale. | Re-lists the full flag reference inline, where it silently drifts out of sync with `SKILL.md`. |
| **Architecture** | ≥1 Mermaid diagram passing both gates; dual-density (overview inline + detail in `<details>`). | No diagram (wall of prose), or one 30-node graph that fails the complexity gate. |
| **Troubleshooting** | A symptom → cause/fix table covering the real first-run failures. | "See the code / open an issue" with no concrete symptom mapping. |
| **TOC** | `mdtoc`-generated between `<!--TOC-->` markers. | Hand-maintained list that no longer matches the headings. |
| **Brand neutrality** | Generic examples; obviously-placeholder hex codes and names. | A client's palette, mascot, or project nouns leaking into the prose. |
| **Cost/external calls** | If it spends money or hits a network, says so up front with how to estimate/limit it. | Silent about cost or credentials until the user is surprised by a bill or an auth error. |

### Architecture diagram rules (non-negotiable)

Diagrams are governed by the `mermaidjs_diagrams` skill. A diagram is not done until it passes
**both** gates with a 0 exit code:

```bash
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_contrast.ts   .claude/skills/<name>/README.md
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts .claude/skills/<name>/README.md
```

- **Palette from [`color_theming.md`](../../skills/mermaidjs_diagrams/resources/color_theming.md).**
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
applying recorded reasoning instead of re-deriving or guessing. Required sections:

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

### What makes a CLAUDE.md good vs. bad

| ✅ Good | ❌ Bad |
|--------|--------|
| Each ADR records the *motivator* — the problem that forced the feature. | A changelog of *what* changed with no *why*; unusable for the next decision. |
| Every ADR ends in a forward-looking **Lens** (an imperative rule). | Purely historical entries ("we did X") with no rule to reapply. |
| Restates only rationale; defers usage to `SKILL.md`/`README.md`. | Re-documents commands and flags, duplicating the other two docs. |
| File map + extension checklist make the next change mechanical. | No map, no checklist — every change re-discovers the layout from scratch. |
| Known-gotchas list the symptom, so the trap is recognised when hit. | Gotchas described abstractly with no observable symptom to match against. |

## Done-when checklist (repeatable)

```text
[ ] SKILL.md   — frontmatter triggers + quickstart + resources pointers
[ ] README.md  — purpose, mdtoc-populated TOC, Quickstart (invoke + direct + escape-hatch),
                 ≥1 Mermaid architecture diagram, troubleshooting, "For maintainers" → CLAUDE.md
[ ] README scored against the good/bad checklist — no anti-pattern column applies
[ ] README diagrams — mermaid_contrast.ts AND mermaid_complexity.ts both exit 0
[ ] CLAUDE.md  — dev contract, file map, ADR log (Status/Context/Decision/Consequences/Lens,
                 motivators captured), extension checklist, known gotchas
[ ] brand-agnostic (../agnostic_examples.md); code gate green (make … ci)
[ ] every touched doc ≤ 500 lines (index.md invariant)
```
