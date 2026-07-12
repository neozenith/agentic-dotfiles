# Adjudications — user rulings on richdocs behaviour

Treat these as already-decided. Do not re-litigate.

## 2026-07-10 — Self-containment outranks the never-duplicate rule

- **Claim (skill's first fix):** the mermaid parse/contrast gate should be
  satisfied by pointing SKILL.md at the sibling `mermaidjs_diagrams` skill's
  scripts, honouring the never-duplicate rule.
- **Ruling (user):** rejected, emphatically. richdocs must maintain a
  **wholesale vendored copy** of the mermaid toolchain
  (`vendor/mermaidjs_diagrams/`) so it stands on its own. richdocs must NOT
  rely on or be aware of sibling skills.
- **Why:** a skill that depends on a sibling's files breaks when copied,
  shared, or run in an environment where the sibling is absent; the
  dependency is invisible until it fails. Wholesale vendoring (like the
  stencil zip) keeps the failure surface inside the skill.
- **How applied:** vendor copy at `vendor/mermaidjs_diagrams/`; all sibling
  references stripped from SKILL.md and `resources/*.md`; ADR-007 records
  the reversal and the refresh procedure; ADR-002's lateral-link approach
  marked partially superseded. Upstream may be named only in CLAUDE.md
  (maintainer provenance for re-vendoring).
