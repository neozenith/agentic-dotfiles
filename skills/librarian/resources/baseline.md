# Universal Baseline — "compliant" when no local dialect is declared

This is the researched default the librarian falls back to when a repo has no
`docs/CONVENTIONS.md` and no strong observable dialect of its own. A declared
local dialect always outranks this baseline (SKILL.md, discovery ladder).

Research date: 2026-07 (sources in [evidence.md](evidence.md)).

## 1. The required document set

Every project must carry these, regardless of size:

| Document | Audience | Purpose |
|----------|----------|---------|
| `README.md` | human consumer | What this is, why it exists, fastest path to value. Routes outward (hub-and-spoke), does not answer everything. |
| `CONTRIBUTING.md` | human contributor | How to set up, build, test, and get a change accepted. |
| `CLAUDE.md` / `AGENTS.md` | agentic harness | Operating instructions for coding agents. The two names are interchangeable surfaces for the same role (see §5); the librarian refers to the role as CLAUDE.md after first mention. |
| ADR surface | humans + agents | The decision log: `ADRs.md` (single-file log) **or** `adrs/NNNN-short-name.md` (file-per-decision). Either layout is compliant; the repo picks one and declares it. |
| `GLOSSARY.md` | humans + agents | The **ubiquitous language**: every project/domain-specific term with its one canonical name and definition. The shared vocabulary contract between developer and agent — code identifiers, doc prose, and conversation all use these terms. Root or `docs/GLOSSARY.md`; the dialect declares which. |
| `LICENSE` | everyone | Root only — license detection requires it there. Public repos: mandatory. Private: recommended. |

## 2. Sibling and link obligations

Presence alone is not compliance — key documents must reference each other:

- **CLAUDE.md → ADR surface.** The CLAUDE.md must point at the sibling ADR
  surface with a "check before you ask" instruction: when facing ambiguity,
  consult existing decisions and self-answer before raising an open question.
  New binding decisions are recorded back as ADRs.
- **Root CLAUDE.md → `docs/CONVENTIONS.md`** when that file exists (see
  [conventions_template.md](conventions_template.md)). The conventions file
  is the repo's declared documentation dialect; the agent entry point must
  route to it.
- **CLAUDE.md → GLOSSARY.md, with two standing instructions**: (a)
  *cross-reference naming* — new identifiers, docs, and prose use the
  glossary's canonical terms, never ad-hoc synonyms; (b) *keep it current* —
  when a new domain term enters the conversation or the code, add it to the
  glossary in the same change. The glossary only works as a shared-language
  contract if the agent file makes both obligations explicit.
- **README → CONTRIBUTING.** The README links contributors onward; it never
  absorbs contributor policy.
- **README as hub.** A thin root README routes to detailed docs that live
  near the code they describe. Every non-trivial directory earns a
  `README.md` index (GitHub renders it as the free landing page).
- **ADR immutability.** Accepted decisions are never rewritten; a new
  decision supersedes with a cross-link.

## 3. Recognised locations and precedence

GitHub resolves community health files by precedence: **`.github/` first,
then repo root, then `docs/`** — first match wins. Practical split:

- **Human-first files stay at root**: `README.md`, `LICENSE`, `CHANGELOG.md`,
  and usually `CONTRIBUTING.md` (large projects keep it at root as a signpost
  into deeper contributor docs).
- **Machine/process files go in `.github/`**: `CODEOWNERS`, `FUNDING.yml`,
  issue/PR templates (location mandatory), workflows.
- **`SECURITY.md`, `CODE_OF_CONDUCT.md`, `SUPPORT.md`, `GOVERNANCE.md`**:
  any of the three recognised locations; root or `.github/` both fine —
  a *fourth* location (e.g. `docs/community/`) breaks platform surfacing
  and is a placement finding.
- **`CHANGELOG.md`**: root, Keep-a-Changelog format is the de facto standard.

## 4. The docs/ tree

- **Diátaxis is the default taxonomy** for a `docs/` tree that has outgrown
  the README: `tutorials/` (learning), `how-to/` (task), `reference/`
  (information), `explanation/` (understanding). Folder names themselves
  declare the dialect.
- **Small projects (< ~10 pages) get one good sectioned README**, not four
  near-empty buckets. Premature taxonomy is itself a finding.
- **Separate contributor docs from user docs** (Django's `internals/`,
  Kubernetes' dedicated community repo). A user hitting release-process docs
  while learning the API is the symptom of the missing split.
- **Docs-as-code**: anything that changes with the code ships in the repo
  with the code. External wikis/drives referenced as canonical are a
  placement finding.
- **RFC/proposal trees** (`docs/rfcs/`, `docs/proposals/`) are distinct from
  ADRs: an RFC is a pre-decision discussion artifact (mutable in review); an
  ADR is a post-decision record (immutable). Keep both roles separate.

## 5. Agent-file conventions

- **AGENTS.md is the cross-harness standard** (Linux Foundation, 60k+ repos);
  CLAUDE.md is what Claude Code reads natively. Compliant repos have **one
  source of truth** with the other name as a symlink, or a CLAUDE.md whose
  first line imports AGENTS.md (`@AGENTS.md`) followed by harness-specific
  extras. Two divergent full copies is a finding.
- **Router, not warehouse**: target under ~200 lines at root; exact
  build/test commands, layout by directory purpose, hard "never" boundaries,
  and *pointers* into `docs/` — never pasted conventions an existing doc or
  linter already owns. Each fact lives in exactly one document.
- **Nesting**: per-directory agent files override the root for their subtree
  (closest file to the edited code wins). Subtree invariants belong in a
  subtree agent file, not appended to the root.

## 6. Naming rules

| Rule | Detail |
|------|--------|
| UPPERCASE root meta-files | `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `SECURITY.md` — the "read me before the code" signal. |
| lowercase kebab-case in `docs/` | `getting-started.md`, `how-to-deploy.md` — URL-safe, case-insensitive-filesystem safe. |
| ADR file-per-decision | `NNNN-short-name.md`, 4-digit zero-padded so lexical sort = chronological; `0001-record-architecture-decisions.md` is the customary first entry. |
| Directory index | `README.md` in every non-trivial directory. |
| Point-in-time docs are dated | Findings, session notes, snapshots carry an ISO date in the filename (`*-YYYY-MM-DD.md`); living docs never do. Mixing the two undated is a finding. |
| Ordered sequences | Prefer nav/frontmatter ordering over `01-` numeric prefixes (fragile under insertion); tolerate existing prefixes rather than churn them. |

## 7. ADR layouts in detail

Both compliant; the repo declares its pick in `docs/CONVENTIONS.md`:

- **Single-file log** (`ADRs.md`): suits small projects and agent-context
  logs; may federate into scoped logs (a log beside each subtree it governs,
  nearest log up the tree wins) with the root file as index.
- **File-per-decision** (`adrs/` or `docs/adr/` or `docs/decisions/`):
  diffable, linkable, explicit supersession; the scale default. Carry an
  index (`README.md` table: number, title, status, date).
- Migration between layouts is a librarian APPLY operation: mechanical,
  content-preserving, index regenerated, inbound `ADR-NNNN` citations kept
  resolvable.
