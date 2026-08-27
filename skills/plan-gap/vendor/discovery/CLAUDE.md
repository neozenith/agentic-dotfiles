# `discovery` — maintainer notes

Read the **ADR log** first. Each entry carries a **Lens**: a forward-looking heuristic to apply to
the next decision of that class, so a change to this skill is settled by applying recorded
reasoning rather than re-deriving it.

**This file is not loaded when the skill runs.** Runtime authority is `SKILL.md` plus
`resources/**`; `README.md` and this file are development-time documents for whoever edits the
skill.

## File map

| Path | Role |
|------|------|
| `SKILL.md` | Runtime workflow — target resolution, dual research, verification, synthesis, validation |
| `resources/discovery-template.md` | The document template + the style rules that govern it |
| `resources/playwright-cli.md` | Link verification tiers, commands, verdicts, markers |
| `resources/mermaidjs-diagrams.md` | Lens menu, mmdc rendering commands, color theming + contrast rules |

## Architecture principles

- **Two states, nothing downstream.** This skill ends at a populated Current + Desired State. Gap
  decomposition, ticketing, and execution planning belong to whatever consumes the document.
- **Section ownership is the composition contract.** Owning only `## Current State` and
  `## Desired State` — and preserving everything after them verbatim — is what lets a caller
  workflow (operating a vendored copy) extend the same file without this skill knowing about it.
- **Evidence or marker, never bare assertion.** Every claim carries `file:line` or a verified URL,
  or an explicit marker. Weakening this weakens every consumer.

## ADR log

### ADR-001 — Extracted from plan-gap's Phase 1; consumers vendor, never link

- **Status:** accepted (user instruction, 2026-08-27)
- **Context:** The Current/Desired State research discipline (dual-track subagent research,
  tiered link verification, paired lens-diagram synthesis) lived inline as steps 1b–1d of the
  `plan-gap` skill's Phase 1 playbook. The user asked for it as a standalone skill so the
  discipline can run outside gap-analysis planning. Sibling skills may not reference each other
  (`skills/CLAUDE.md`), so plan-gap consumes this skill as a wholesale vendored copy under its
  `vendor/discovery/`, operated by an overlay in its Phase 1 playbook.
- **Decision:** this skill is the **upstream owner** of the discipline. It stays caller-agnostic:
  it writes only the two state sections, takes its target and brief as arguments, and never
  mentions gaps, tickets, or any consumer's concepts. Consumer-specific bindings (where the file
  lives, extra sections, extra gates) belong in the consumer's overlay, not here.
- **Consequences:** a behavior change here does not reach consumers until they re-vendor
  (`rsync -a --delete` of this directory), and their overlays must be reconciled in the same
  commit as a refresh. Duplicated diagram/verification doctrine between this skill and its
  consumers is the accepted cost of self-containment.
- **Lens:** when adding capability here, ask "does a caller-agnostic run need this?" If it only
  makes sense for one consumer's document set, it is overlay material — leave it out and let the
  consumer bind it.

## Extension checklist

- [ ] `SKILL.md` and every resource ≤ 500 lines (`rules/claude_skills/index.md`)
- [ ] No reference to any sibling skill or consumer concept in `SKILL.md` / `resources/**`
- [ ] README diagrams pass `mermaid_contrast.ts` and `mermaid_complexity.ts` (exit 0)
- [ ] Known consumers re-vendored and their overlays reconciled (plan-gap: `vendor/discovery/`)

## Known gotchas

- **A refresh that rewrites the whole target file destroys caller-owned sections.** The symptom:
  a consumer's appended section (e.g. an increments stack) vanishes after a discovery refresh.
  The template's ownership rule exists to prevent exactly this — edit sections, never the file.
- **mmdc renders fine in browser previews but fails in CI** — almost always non-ASCII characters
  in node labels (see `resources/mermaidjs-diagrams.md` → pitfalls).
