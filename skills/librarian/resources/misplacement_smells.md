# Misplacement Smells — content in the wrong location

The audit's detection catalog. Each smell names the symptom, how to detect it,
and the shelving move that fixes it. The librarian judges **where content
lives**, never whether it is true, current, or well written — a smell here is
always answered by a move, extract, rename, or link, never by a rewrite.

Severity: 🔴 breaks discovery or platform surfacing; 🟡 misleads navigation;
🟣 hygiene. Report in that order.

## Whole-document smells

| # | Smell | Symptom / detection | Fix |
|---|-------|---------------------|-----|
| M1 | Missing required document | A §1 baseline document (or dialect-required doc) absent entirely. | Create a minimal correct-location stub with the required links; flag content authoring as out of scope. 🔴 |
| M2 | Health file in an unrecognised location | `CONTRIBUTING.md` at `docs/community/guide.md`, `SECURITY.md` nested in a subfolder — platform auto-linking silently stops. | Move to `.github/`, root, or `docs/` (the three recognised locations). 🔴 |
| M3 | Divergent agent-file twins | `CLAUDE.md` and `AGENTS.md` both exist as full, differing copies. | Pick one source of truth; the other becomes a symlink or a one-line import plus harness-specific extras. 🔴 |
| M4 | Orphan document | A doc no index, README, or agent file links to — unreachable except by directory listing. | Link it from the nearest hub, or file it where its content says it belongs. 🟡 |
| M5 | Duplicate homes | The same topic substantively covered in two files (setup steps in README *and* CONTRIBUTING, layout described in README *and* CLAUDE.md). | Choose the owning home per the dialect's layout map; the other location keeps a one-line link. Each fact lives in exactly one document. 🟡 |
| M6 | Wrong-audience directory | Contributor/internal docs (release process, CI internals) interleaved with user docs, or vice versa. | Split trees (`docs/internals/` or equivalent); a user learning the API must not traverse maintainer material. 🟡 |
| M7 | External canonical docs | README or CLAUDE.md points at a wiki/drive page as the authority for something that changes with the code. | Flag for import into the repo; docs-as-code. (Importing content is an APPLY step only if the user provides the content.) 🟡 |
| M8 | Naming violation | Lowercase root meta-file, CamelCase or spaces in `docs/`, un-padded ADR numbers, undated point-in-time doc. | Rename per the naming rules; rewrite inbound links. 🟣 |
| M9 | Premature taxonomy | Four Diátaxis buckets holding one file each in a 6-page project. | Collapse into one sectioned README/doc; note the split trigger in CONVENTIONS.md. 🟣 |
| M10 | Generated/vendored docs shelved as source | Build output, tool-generated API dumps, or vendored third-party docs sitting inside the hand-maintained tree. | Relocate under a generated/vendored path (or gitignore); never hand-file machine output with source docs. 🟣 |

## Partial (within-file) smells — a *section* in the wrong file

These are the librarian's hardest and highest-value findings: the file is fine,
but part of its content semantically belongs elsewhere. Detection is by reading
each section and asking "which document's charter does this serve?"

| # | Smell | Symptom / detection | Fix |
|---|-------|---------------------|-----|
| P1 | Overgrown README | Contributor policy, full API/config reference, or deep architecture essays inside README; README exceeds ~2 screens of orientation. | Extract each foreign section to its charter home (CONTRIBUTING.md, `docs/reference/…`, `docs/explanation/…`); README keeps a one-line link where the section was. 🟡 |
| P2 | Decisions buried in prose | "We chose X because Y" rationale living in README paragraphs, code comments' surroundings, or a design doc — invisible to the ADR surface. | Extract to the ADR surface in the repo's declared ADR layout; original location keeps the conclusion plus an `ADR-NNNN` citation. 🟡 |
| P3 | Agent-file warehouse | CLAUDE.md restating conventions, style rules, or architecture that an existing doc/linter owns; root agent file well past ~200 lines. | Move the substance to (or dedupe against) its owning doc; CLAUDE.md keeps the pointer. 🟡 |
| P4 | Genre bleed across files | Reference tables inside a tutorial, a how-to embedded mid-explanation — *and the repo's dialect gives that genre its own home*. | Extract the section to the genre's home; leave a link. If the dialect deliberately fuses genres, not a finding. 🟣 |
| P5 | Root-file subtree rules | Root CLAUDE.md carrying rules that only bind one subdirectory ("in packages/db never edit migrations"). | Extract to a nested agent file in that subtree (closest-file-wins). 🟣 |
| P6 | Homeless section | A section that matches no existing document's charter (e.g. an ops runbook fragment in CONTRIBUTING). | Promote to a new correctly-named document in the right tree; link from the nearest hub. 🟡 |
| P7 | Scattered ubiquitous language | Domain terms defined ad hoc inside README, CLAUDE.md, or topic docs ("a *widget* here means…") instead of in GLOSSARY.md — or the same term defined differently in two places. | Consolidate the definition into GLOSSARY.md; the original location keeps the term (linked on first use where practical). Judging whether a definition is *correct* stays out of scope — only its home and its uniqueness are placement questions. 🟡 |

## Detection discipline

- **Charter first.** Before judging any section, write one line per existing
  document stating its charter (from the dialect's layout map, or inferred
  from §1 baseline roles). Misplacement is always *relative to a charter* —
  never a taste call.
- **Read, don't grep-only.** Partial smells require reading section content;
  filename/path checks catch only whole-document smells. Fan out subagents
  per directory or doc cluster for large repos.
- **Moves must be loss-free.** Every extract leaves a link stub at the old
  location; every rename rewrites inbound links (grep the old path and old
  anchors repo-wide). A move that breaks one inbound link is not done.
- **Uncertain is a question, not a move.** When a section plausibly serves
  two charters, report both candidate homes with a recommendation — APPLY
  only executes unambiguous or user-adjudicated moves.
