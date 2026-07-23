# Flavours — named convention presets and graduation triggers

A **flavour** is a named, coherent bundle of layout choices sized to a
project's use case, scale, complexity, and rigour. Init takes a flavour to
scaffold a new or young repo; the chosen flavour is recorded in
`docs/CONVENTIONS.md` (Dialect section) and becomes the declared dialect that
future audits judge against. A repo that has outgrown its declared flavour
gets **graduation recommendations** — never findings (authority ladder: a
declared choice is compliant until the maintainer changes it).

## The three flavours

| Dimension | `minimal` | `standard` | `rigorous` |
|-----------|-----------|------------|------------|
| Fits | solo/prototype, internal tool, single consumer | team product, active contributors | multi-team, regulated, public platform |
| README | one sectioned README carries orientation + quickstart + ways-of-working | thin hub routing to CONTRIBUTING + docs/ | thin hub; per-directory README indexes throughout |
| CONTRIBUTING.md | required, brief (setup + test + PR in one screen) | required, full dev workflow | required; deep contributor tree (`docs/internals/` or equivalent) |
| Agent file | root CLAUDE.md-role only | root + nested files where subtree rules exist | canonical AGENTS.md + symlinks, nested per package |
| ADR surface | single-file `ADRs.md` log | single-file log **or** `adrs/NNNN-*.md` (declared) | file-per-decision + index + scoped logs beside governed subtrees |
| GLOSSARY.md | required; may be short (every term counts from day one) | required; root or `docs/`, declared | required; per-domain sections or split glossaries with a root index |
| docs/ tree | none — README sections until the trigger | flat topic files under `docs/`, kebab-case | Diátaxis buckets (`tutorials/ how-to/ reference/ explanation/`) + `internals/` |
| CONVENTIONS.md | optional (baseline + observed carry it) | required | required, with split/merge triggers filled in |
| Proposals/RFCs | not used | not used | `docs/proposals/` (mutable in review → summarised into an ADR) |
| CHANGELOG.md | optional | required at first external consumer | required, Keep-a-Changelog + SemVer |
| Health files | LICENSE | + SECURITY.md | + CODE_OF_CONDUCT, SUPPORT, GOVERNANCE, CODEOWNERS in `.github/` |
| Dated docs | as needed | point-in-time docs dated `-YYYY-MM-DD` | dated + segregated from living docs (e.g. `docs/findings/`) |

All three flavours require the core set: README, CONTRIBUTING, CLAUDE.md-role
file, ADR surface, GLOSSARY.md, and the §2 baseline cross-links (CLAUDE.md →
ADRs "check before you ask"; CLAUDE.md → GLOSSARY naming + currency
obligations). Flavours scale the *structure around* the core, never waive it.

## Graduation triggers — when to introduce each scale-up element

Audit checks these when the observed repo exceeds its declared flavour, and
reports them as a "graduation" section of the shelving plan (recommendations,
severity 🟣, applied only on user acceptance):

| Element | Introduce when | Graduates toward |
|---------|----------------|------------------|
| `docs/` flat topic files | README exceeds ~2 screens or ~10 topics | standard |
| CONTRIBUTING split from README | second regular contributor, or setup section > 1 screen | standard |
| `docs/CONVENTIONS.md` | first audit disagreement about where something goes | standard |
| CHANGELOG.md | first external consumer or versioned release | standard |
| Nested agent files | root CLAUDE.md carries a rule binding only one subtree (smell P5) | standard |
| File-per-decision ADRs | log exceeds ~15 decisions, or two decisions land in one week (merge-conflict pressure) | rigorous |
| Scoped ADR logs | a subtree accumulates 3+ decisions of its own | rigorous |
| Diátaxis buckets | flat `docs/` exceeds ~10 files or mixes genres readers confuse | rigorous |
| Contributor tree (`internals/`) | contributor docs interleave with user docs (smell M6) | rigorous |
| `docs/proposals/` | decisions need review *before* acceptance (multi-team sign-off) | rigorous |
| Glossary split / per-domain sections | GLOSSARY.md exceeds ~100 terms or serves 2+ bounded contexts | rigorous |
| `.github/` health-file set | project goes public or takes external contributions | rigorous |

Downscaling is legitimate too: a rigorous layout serving a shrunken project
(four near-empty Diátaxis buckets — smell M9) gets a consolidation
recommendation toward the smaller flavour.

## Selecting a flavour (init guidance)

Ask, in order — the first "yes" from the bottom wins:

1. Multiple teams, external contributors, compliance/audit obligations, or a
   public platform surface? → `rigorous`
2. A team ships and maintains it; others consume it? → `standard`
3. Otherwise → `minimal`

When init runs on an *existing* repo with a flavour argument, the flavour
supplies only what the repo hasn't already decided: observed conventions
still outrank the preset (authority ladder), and every preset-defaulted line
in CONVENTIONS.md is marked for maintainer veto. A flavour is a starting
dialect, not an override.
