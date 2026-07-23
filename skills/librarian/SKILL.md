---
name: librarian
description: "Repo documentation organisation: ensures the canonical document set exists (README.md, CONTRIBUTING.md, CLAUDE.md/AGENTS.md, an ADR surface, GLOSSARY.md ubiquitous language) with required cross-links, and that every doc — and every section within a doc — lives where its content says it belongs. Modes: (1) AUDIT (default) — resolve the repo's dialect (docs/CONVENTIONS.md, else observed conventions, else researched baseline), then report missing/misfiled/misnamed docs and sections as a shelving plan, plus graduation advice when the repo outgrows its flavour; (2) APPLY — execute an approved plan with history-preserving moves and link rewrites; (3) INIT — bootstrap docs/CONVENTIONS.md from the observed dialect or a named flavour (minimal/standard/rigorous). Use when asked to organise repo docs, check doc layout/placement, add missing canonical docs, relocate/rename docs, or on 'librarian'. Skip when the ask is prose quality, staleness/drift, or within-one-file readability — content-quality skills own those."
argument-hint: "[audit | apply | init [minimal|standard|rigorous]] [paths] (default: audit whole repo)"
user-invocable: true
---

# Librarian

Shelves the repository's documentation: the right documents **exist**, carry
the right **names**, live in the right **locations**, and **cross-link** as
required. Content is cargo — the librarian moves it, extracts it, and renames
its containers, but never rewrites, fact-checks, or restyles it. Whether a doc
is true, current, or well written is out of scope by design; other skills own
content quality, and they run independently of this one.

Resources (read on first use):
- [resources/baseline.md](resources/baseline.md) — the universal compliance
  baseline: required document set, sibling/link obligations, canonical
  locations, docs/ taxonomy defaults, agent-file and naming rules.
- [resources/misplacement_smells.md](resources/misplacement_smells.md) — the
  detection catalog: whole-document smells (M1-M10) and partial within-file
  smells (P1-P6), with severities and fixes. Load during audit.
- [resources/conventions_template.md](resources/conventions_template.md) —
  the docs/CONVENTIONS.md template + bootstrapping guidance. Load for init,
  and during audit when the repo lacks a conventions file.
- [resources/flavours.md](resources/flavours.md) — the named convention
  presets (minimal / standard / rigorous) and the graduation triggers for
  scale-up elements. Load for init, and during audit to check whether the
  repo has outgrown its declared flavour.
- [resources/evidence.md](resources/evidence.md) — research citations and
  counter-evidence behind the baseline (dated; check freshness before
  extending doctrine).
- `resources/learned/` (if present) — prior user adjudications on placement
  rulings. Treat as already-decided; do not re-litigate.

## Mode selection

- `audit` (default, bare `/librarian`): discover the dialect, inventory,
  report a shelving plan. Read-only — no file is created, moved, or renamed.
- `apply`: execute a shelving plan (from this session's audit, or a plan the
  user supplies/edits). Mutating; every operation is loss-free.
- `init`: generate `docs/CONVENTIONS.md` describing the repo's existing
  dialect and wire the root CLAUDE.md reference to it.
- A path argument scopes audit/apply to that subtree (monorepo package case);
  the dialect is still resolved from the repo root downward.

## Step 0 — Discover the dialect (every mode)

Compliance is judged against an authority ladder; higher rungs win:

1. **Declared dialect** — `docs/CONVENTIONS.md` (or a file the root CLAUDE.md
   names in that role). If present, its Dialect lines and Layout map are the
   oracle; the baseline fills only what it leaves unstated.
2. **Observed dialect** — strong existing conventions the repo already
   follows consistently (an established `adrs/` tree, an existing docs
   taxonomy, scoped ADR logs, a dated-filename habit). Consistency is the
   test: a pattern followed in ≥3 places is a convention, one file is not.
3. **Universal baseline** — [resources/baseline.md](resources/baseline.md).

State which rung answered each question. **Never impose the baseline over a
declared or consistently-observed choice** — e.g. a repo on single-file
`ADRs.md` is compliant even though the baseline prefers file-per-decision at
scale; migrating layouts is a recommendation for the user, not a finding.
Where the repo is *internally inconsistent* (two ADR layouts, three naming
styles), the majority pattern is the dialect and the minority files are
findings.

The agent-file role: `CLAUDE.md`, `AGENTS.md`, and `AGENT.md` are
interchangeable surfaces for one role — detect any; call it CLAUDE.md
thereafter. Two divergent full copies is smell M3.

## Audit mode

### 1. Inventory

Glob `**/*.md` plus the extensionless canonicals (`LICENSE`, `CODEOWNERS`),
skipping vendored/generated/`node_modules`/build output. Record per doc:
path, name-style, which charter it apparently serves, inbound links (grep its
path and anchors), and whether any hub references it. Build the charter table
first (one line per existing doc from the dialect's layout map, or inferred
from baseline roles) — misplacement is judged against charters, never taste.

### 2. Check existence and links

Against the resolved dialect + baseline §1-§2:

- Required set present? (README, CONTRIBUTING, CLAUDE.md-role, ADR surface,
  GLOSSARY.md; dialect-required extras.)
- Required cross-links present? (CLAUDE.md → ADR surface with a
  check-before-you-ask line; CLAUDE.md → GLOSSARY.md with both standing
  instructions — canonical terms for all naming, new domain terms added in
  the same change; root CLAUDE.md → CONVENTIONS.md when it exists;
  README → CONTRIBUTING; ADR index covers all scoped logs.)
- Locations recognised? (health-file precedence, baseline §3.)
- Flavour still fits? Compare observed scale against the declared flavour's
  graduation triggers ([resources/flavours.md](resources/flavours.md));
  exceeded triggers become a **Graduation** section of the plan
  (🟣 recommendations, applied only on user acceptance — never findings).

### 3. Detect misplacement

Apply [resources/misplacement_smells.md](resources/misplacement_smells.md):
whole-document smells M1-M10 via the inventory; partial smells P1-P6 by
reading each substantial doc's sections and asking which charter each serves.
For large repos fan out read-only subagents (one per directory or doc
cluster), each returning: finding → smell id → evidence (path / section
heading + first line) → proposed move → confidence. A section that plausibly
serves two charters is reported with both candidates and a recommendation —
uncertain is a question, not a move.

### 4. The shelving plan

```
## Librarian audit: <N> docs · <E> existence gaps · <W> misfiled docs · <S> misfiled sections
Dialect authority: <declared | observed | baseline> (per question where mixed)

| # | Finding | Smell | Evidence | Operation | Severity |
|---|---------|-------|----------|-----------|----------|
| 1 | CONTRIBUTING.md missing | M1 | required set | create stub + README link | 🔴 |
| 2 | Release process inside README §Deploy | P1 | README.md#deploy | extract → docs/how-to/release.md, leave link | 🟡 |
```

Order 🔴 → 🟡 → 🟣. Each row's Operation is one of: **create-stub / move /
rename / extract / merge / link / symlink**. Offer: (a) apply all, (b) apply
🔴 only, (c) report only. Findings the user rejects are recorded in
`resources/learned/adjudications.md` (create on first use) so later audits
honour the ruling.

## Apply mode

Execute the plan mechanically, one numbered finding per commit-sized step:

1. **Moves/renames preserve history**: `git mv` (never delete+create).
2. **Rewrite every inbound reference**: grep the old path and old anchors
   repo-wide (markdown links, agent-file pointers, code comments, configs);
   update all. For externally-linked docs (published READMEs), leave a
   one-line redirect stub at the old path; internal-only docs need no stub.
3. **Extracts are verbatim**: the section moves unchanged (heading level may
   be adjusted to fit the target); the source keeps a one-line link where the
   section was. Never reword cargo in transit — if a moved section looks
   wrong or stale, flag it for a content-quality pass; do not fix it here.
4. **Created stubs are minimal**: title, one-sentence charter, the required
   cross-links, and an explicit `<!-- librarian stub: content pending -->`
   marker. Authoring real content is out of scope.
5. **ADR operations keep citations resolvable**: renumbering is forbidden;
   layout migration (log ↔ file-per-decision) preserves ids and regenerates
   the index.
6. **Verify before done**: every moved/renamed path resolves from every
   inbound link (grep the old path returns only stubs/history), required
   cross-links exist, no file was lost (`git status` shows renames, not
   deletions), and any TOC in a touched file is regenerated (via the `mdtoc`
   skill where available).

## Init mode

Read [resources/conventions_template.md](resources/conventions_template.md)
and [resources/flavours.md](resources/flavours.md). With a flavour argument
(`init standard`), the preset supplies the starting dialect; without one,
apply the flavour-selection questions to the repo's evident use case and say
which flavour was chosen and why. Then: infer each Dialect line from what the
repo already does (rung 2 evidence — observed conventions outrank the
preset); fill remaining gaps from the flavour, marking those lines as
defaulted so the maintainer can veto. Build the Layout map covering every
doc-bearing path plus rows for missing required docs. Wire the root CLAUDE.md
references (CONVENTIONS.md, ADR surface, GLOSSARY.md obligations) in the same
change. Show the draft before writing when running interactively.

## Cross-cutting rules

- **Never judge content.** No finding may be "this is stale/wrong/verbose";
  the only verdicts are missing, misnamed, misfiled, unlinked, duplicated.
- **Loss-free or not at all.** Every operation is reversible via git and
  leaves no dangling inbound link; deletion is never an operation (merge
  leaves a link behind).
- **Dialect beats baseline; declared beats observed; user beats all.** Prior
  adjudications in `resources/learned/` are already-decided.
- **Audit is read-only**; only apply and init mutate, and init creates
  exactly one file plus one reference line.
- Respect the repo's file-size conventions when extracting (a target file
  near its size ceiling gets a new sibling, not a forced append).
- Report which authority rung answered each contested question so the user
  can audit the librarian's own reasoning.
