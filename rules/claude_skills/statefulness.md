# Skill Statefulness & Feedback Loops

This is the **statefulness** child of the skill/rule family rooted at
[`index.md`](index.md). Siblings: [`docs.md`](docs.md) (the CLAUDE.md ADR
contract that implicit state feeds), [`evals.md`](evals.md) (the explicit
regression net), [`environments.md`](environments.md) (what persists where).

Skills are stateless prompts, but they operate inside stateful substrates.
This rule names the three state pathways and the contract for each.

## State is a role; backends vary

Name the *role* a skill needs ("issue tracking", "document store", "learning
journal") — never a specific backend. Every role has many valid stateful
integrations, and the skill uses its **agency** to act on whichever one the
environment offers, externalizing its learnings there:

| Role | Example backends |
|------|------------------|
| Issue tracking | Jira MCP, Linear MCP, GitHub Issues (`gh`), local `issues/*.md` or JSON |
| Document store | local filesystem, Google Drive MCP, Confluence MCP |
| Learning journal | `resources/learned/` (Pathway 2), a tracker ticket, a CLAUDE.md ADR |
| Run/experiment log | session transcripts, local JSONL, GCS/BigQuery |

Contract: SKILL.md names the **role** and a backend-resolution order — sense
what's available (MCP tools present? `gh` authenticated? Drive mounted? —
see [`environments.md`](environments.md) sensing), prefer the richest
integration, and state which one was chosen. The **local-filesystem variant
is the universal floor** every role must define, so the skill never loses its
memory pathway when richer integrations are absent. Backend choice is
environment degradation (announce it), never requirement degradation.

## Pathway 1 — Implicit state (the default; already mandatory)

The PR, the codebase, and the doc trio ARE the skill's memory:

- A skill run's outputs land in the repo (review comments, restructured docs,
  fitness functions, ADRs) — the next run reads them as context. Honor
  suppressions and prior adjudications found in the repo as already-decided.
- **When a skill run exposes a failure-mode gap, the fix is a CLAUDE.md (or
  AGENTS.md) update in the affected project** — a new ADR entry with a Lens,
  or a Known Gotcha with its symptom. That is the durable correction channel;
  do it in the same session the gap is found, not as a someday-task.
- The skill's own `CLAUDE.md` ADR log absorbs *design* learnings the same way
  (per [`docs.md`](docs.md)).

## Pathway 2 — Self-curated feedback space (`resources/learned/`)

The neuroplasticity pathway: each skill MAY maintain an extensible,
self-curated space at

```
.claude/skills/{skill}/resources/learned/
├── adjudications.md   # rejected/accepted findings the user ruled on
├── calibrations.md    # threshold/severity adjustments that proved right
└── <topic>.md         # anything the skill taught itself, one fact per file
```

Contract:

- **Append on adjudication**: when the user overrules the skill (false
  positive, wrong severity, unwanted restructure), record the case — claim,
  ruling, why — in `learned/`, in the same turn.
- **Load lazily**: SKILL.md points at `learned/` as a read-on-first-use
  resource ("treat prior adjudications as already-decided — don't
  re-litigate"). Never inline learned content into the always-loaded surface.
- **Curate, don't hoard**: entries that graduate into a real rule move into
  SKILL.md/resources with an ADR noting the promotion; entries invalidated by
  model or codebase changes are deleted. `learned/` files obey the 500-line
  invariant like everything else — overflow forces curation, by design.
- **Repo-tracked**: `learned/` is committed. It is project-context, not
  secret memory; the user can read, edit, and veto it like any other file.

## Pathway 3 — Explicit session state (rare; coach-style)

Skills whose value depends on cross-session user modeling (e.g. `coach`'s
learner state) keep structured state under `./.claude/<skill>/state/` with a
schema documented in the skill's resources. Most skills should NOT have this:
PR/codebase state (Pathway 1) plus `learned/` (Pathway 2) covers review,
refactoring, and docs work. Adding Pathway 3 to a skill requires an ADR
justifying why the substrate isn't enough.

## Evidence freshness (state about the skill's own claims)

Skills built on research carry dated claims. Every `resources/evidence.md`
(or equivalent) notes its research date; deployment-statistics claims (LLM
acceptance rates, tool precision numbers) rot fastest and should be re-checked
when they become load-bearing for a new decision. A red-team/disconfirmation
pass is part of skill creation, and its findings live in the evidence file
under "Counter-evidence" — bounded claims beat impressive ones.
