# docs/CONVENTIONS.md — template

The repo's declared documentation dialect: one file describing how *this*
project organises its documentation, referenced from the root CLAUDE.md. It is
the librarian's first authority — a declared dialect always outranks the
universal baseline.

Design precedents (see [evidence.md](evidence.md)): `.adr-dir` proves the
tiny-pointer pattern works across tools; GitLab's docs-about-docs directory
proves the human meta-doc; AGENTS.md proves free-form markdown at a well-known
path beats a rigid schema. This template composes all three: human-readable
markdown, greppable one-line pointers, no schema to validate against.

Keep the real file under ~150 lines. Every section below is optional except
**Dialect** and **Layout map** — omit what the project doesn't need.

---

```markdown
# Documentation Conventions

How this repository organises its documentation. Agents and humans: consult
this before creating, moving, or renaming any doc.

## Dialect

One line per genre — the declared choice, not a menu:

- **Flavour:** <minimal | standard | rigorous — the preset this dialect
  started from (see the librarian's flavours); local lines below override it>
- **Docs taxonomy:** <e.g. "Diátaxis under docs/ (tutorials/, how-to/,
  reference/, explanation/)" | "single sectioned README until ~10 pages">
- **Glossary:** <e.g. "GLOSSARY.md at root, one canonical term per concept,
  agents add new domain terms in the same change that introduces them">
- **ADR layout:** <e.g. "file-per-decision at adrs/NNNN-short-name.md, MADR
  template, README index" | "single-file ADRs.md log, scoped logs federate,
  nearest log up the tree wins">
- **Agent files:** <e.g. "AGENTS.md canonical, CLAUDE.md symlinks to it;
  nested per-package files for subtree rules">
- **Changelog:** <e.g. "Keep a Changelog at root, SemVer">
- **Proposals/RFCs:** <e.g. "docs/proposals/, mutable until accepted, then
  summarised into an ADR" | "not used">

## Layout map

Path → what belongs there → who reads it → when it changes. This table is the
misplacement oracle: content that doesn't match its row's charter is misfiled.

| Path | Charter (what belongs here) | Audience | Changes when |
|------|-----------------------------|----------|--------------|
| `README.md` | Orientation + routing only; ~2 screens | Consumers | Purpose or entry points change |
| `CONTRIBUTING.md` | Setup, build/test, PR conventions | Contributors | Dev workflow changes |
| `CLAUDE.md` | Agent invariants + pointers; no restated conventions | Agents | Commands or hard boundaries change |
| `ADRs.md` (or `adrs/`) | Immutable accepted decisions + lenses | Both | A binding decision is made |
| `GLOSSARY.md` | Ubiquitous language: one canonical term per concept | Both | A domain term enters code or conversation |
| `docs/…` | <one row per subtree> | … | … |

## Naming

- Root meta-files: UPPERCASE (`README.md`, `CONTRIBUTING.md`, …).
- Inside `docs/`: lowercase kebab-case.
- Point-in-time docs (findings, session notes): suffix `-YYYY-MM-DD`.
- <project-specific rules, e.g. numbered arc42 sections, index-file names>

## Pointers

Greppable one-liners for tooling and agents:

- ADR directory: `<adrs/ | ADRs.md>`
- Docs site source: `<docs/ | none>`
- Diagram conventions: `<link, if any>`

## Required cross-links

- Root CLAUDE.md → this file, and → the ADR surface with "check existing
  decisions before raising an open question".
- Root CLAUDE.md → GLOSSARY.md with both standing instructions: use canonical
  terms for all naming; add new domain terms in the same change.
- README → CONTRIBUTING.
- <project-specific obligations>

## Split/merge triggers

- <e.g. "docs/ adopts Diátaxis folders when the sectioned README passes 10
  topics"; "a scoped ADR log spawns beside any subtree with 3+ local
  decisions">
```

---

## Bootstrapping guidance (for the librarian, not the template)

When generating this file for a repo (`init` mode):

1. **Describe, don't prescribe.** Infer each Dialect line from what the repo
   *already does* (existing folder names, existing ADR files, existing agent
   files). Only fill gaps from the baseline — and mark inferred-vs-defaulted
   lines so the maintainer can veto defaults.
2. **The layout map covers every doc-bearing path that exists**, plus rows
   for baseline-required documents even if currently missing (their absence
   is then self-documenting).
3. **Wire the reference**: add the root CLAUDE.md line pointing here in the
   same change — an unreferenced conventions file is an orphan (smell M4).
4. Keep it a *dialect declaration*, not a style guide: how sentences read,
   whether content is stale, and prose quality belong to other tooling.
