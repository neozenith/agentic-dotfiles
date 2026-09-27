# Skills: Shared Principles (root)

This file holds principles that apply to **every** skill under
`.claude/skills/`. Individual skills keep their own `CLAUDE.md` for their own
decision log; this root holds only what is true across all of them.

## Principle: skills are fully self-contained

**A skill must stand on its own. It must not rely on, reference, or be aware of
another skill's files.** Decoupling and isolation are valued above DRY: when two
skills need the same doctrine, each carries its own copy rather than sharing a
source or pointing at a sibling.

Why, and what it buys:

- **Portability.** Copy a skill's directory anywhere, and it still resolves.
  Nothing breaks because a neighbour moved, was renamed, or is absent.
- **Isolation.** A change to one skill cannot silently alter another. There is no
  hidden coupling to trace when a skill misbehaves.
- **Independent evolution.** Each skill curates its own copy of shared doctrine at
  its own pace, tuned to its own surface.

The cost is duplication, and that cost is **accepted on purpose**. Two copies of a
writing standard or a smell catalogue may drift; each copy stays small and
independently curatable, and that is the trade the maintainer chose.

### What this means in practice

- **Copy, don't reference.** Shared doctrine (a prose standard, a style rule, a
  smell catalogue) is copied into each skill that needs it. No skill's runtime
  surface (`SKILL.md`, `resources/*`) links to another skill's files.
- **No "model it on skill X" pointers** in runtime surfaces. The quality bar is
  the skill's own distilled checklists, not another skill's current state.
- **Vendor wholesale when you need another skill's tooling.** If a skill needs a
  capability another skill owns (a gate script, an icon pack, a diagram
  toolchain), vendor a copy into its own `vendor/` directory and operate that
  copy. The skill then depends on nothing outside its own folder. Vendoring is
  the sanctioned way to reuse, never a runtime reference to a sibling.
- **Rules are not skills.** Referencing project rules under `.claude/rules/**`
  (the 500-line invariant, the docs/scripts contracts) is fine and
  expected. The prohibition is on depending on a **sibling skill**.

### The one named exception: the shared design-profile store

Decided by the maintainer (DT-TOOL-1, `docs/plans/refactor-design-tokens/DECISIONS.md`): skills that
consume brand colours (`richdocs`, `mermaidjs-diagrams`) may **read the `.design-profiles/` store**
and **name the `design-profiles` skill** so the agent can run it. That is awareness of shared *data*
and of a skill's *existence*, not a dependency: a consumer never imports, runs or reads
`design-profiles`' files, and it keeps working, on its own fallback, when no profile exists.

## The 500-line invariant still applies

Every prose file in every skill stays ≤ 500 lines
(`.claude/rules/claude_skills/index.md`). Self-containment does not license a
skill to grow an unbounded copy of shared doctrine: keep each copy lean, and split
at a natural seam if it approaches the ceiling.
