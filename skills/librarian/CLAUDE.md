# librarian — Maintainer Decision Lens

Read the ADR log below before changing anything. Each ADR carries a **Lens** —
apply it to the next decision instead of re-deriving the trade-off.

## Development contract

Prose-only skill (no `scripts/` yet — see extension checklist). Doc gates
before handoff, run from repo root:

```sh
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_contrast.ts   .claude/skills/librarian/README.md
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts .claude/skills/librarian/README.md
uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 .claude/skills/librarian/README.md
```

All files ≤ 500 lines (`.claude/rules/claude_skills/index.md`).

## File map

| File | Role |
|------|------|
| `SKILL.md` | Agent operating manual: modes, authority ladder, audit steps, apply invariants |
| `README.md` | Human explainer: purpose, quickstart, architecture diagram |
| `resources/baseline.md` | Universal compliance baseline: required set, locations, naming, ADR/agent-file rules (lazy) |
| `resources/misplacement_smells.md` | Detection catalog: M1-M10 whole-doc + P1-P6 within-file smells (lazy; audit) |
| `resources/conventions_template.md` | docs/CONVENTIONS.md template + bootstrapping guidance (lazy; init) |
| `resources/flavours.md` | Named presets (minimal/standard/rigorous) + graduation triggers (lazy; init + audit) |
| `resources/evidence.md` | Research citations + counter-evidence, dated 2026-07-23 |
| `resources/learned/` | User adjudications on placement rulings (created on first rejection; already-decided) |
| `CLAUDE.md` | This file — rationale and decision log |

## Architecture principles

- Placement, existence, naming, linking only — content is cargo, never judged.
- Loss-free operations: `git mv`, inbound-link rewrites, link stubs; deletion
  is never an operation.
- Authority ladder: declared dialect > observed dialect > baseline; user
  adjudications beat all.
- Audit is read-only; only apply and init mutate.

## ADR log

### ADR-1: the skill judges location, never content

- **Status:** Accepted (2026-07)
- **Context:** The maintainer runs separate skills for content quality
  (drift/staleness, prose, within-one-file structure) and wants fine-grained
  independent control: organisation passes and quality passes must be
  composable without either being aware of the other. Mixing them would also
  make apply-mode diffs unreviewable (moves hiding rewrites).
- **Decision:** The librarian's verdict vocabulary is closed: missing,
  misnamed, misfiled, unlinked, duplicated. Extracted/moved content travels
  verbatim; a section that looks wrong in transit is flagged for a
  content-quality pass, never fixed here. The skill names no sibling skill
  and reads no sibling's files (skills are self-contained).
- **Consequences:** Apply diffs are pure moves and reviewable as such; the
  skill composes with any content-quality tooling; some obviously-stale text
  gets relocated untouched, which is correct.
- **Lens:** If a candidate feature needs to read a sentence to judge its
  *quality* rather than its *charter*, it belongs in a different skill.
  Charter questions ("which document should hold this?") are in; quality
  questions ("is this good/true?") are out.

### ADR-2: compliance resolves through a three-rung authority ladder

- **Status:** Accepted (2026-07)
- **Context:** Research found no ecosystem-standard docs layout to enforce:
  GitHub's health-file precedence, Diátaxis, and ADR conventions are strong
  defaults, but real repos hold deliberate local choices (single-file ADR
  logs, federated scoped logs, Ways-of-Working in README instead of
  CONTRIBUTING). A skill that imposes the textbook layout over a working
  local dialect creates churn, not compliance.
- **Decision:** Declared dialect (`docs/CONVENTIONS.md`) > observed dialect
  (a pattern consistently followed, ≥3 instances) > researched baseline.
  Internal inconsistency resolves to the majority pattern; the minority
  files are the findings. Baseline-preferred migrations (e.g. log →
  file-per-decision) are recommendations, never findings.
- **Consequences:** The audit must state which rung answered each contested
  question; two repos can both be fully compliant with different layouts.
- **Lens:** The librarian enforces *coherence with the repo's own declared
  or demonstrated system*, and only invents an answer (baseline) where the
  repo has none. Never file a finding whose only evidence is "the baseline
  prefers otherwise".

### ADR-3: docs/CONVENTIONS.md is the declared-dialect surface, and init describes rather than prescribes

- **Status:** Accepted (2026-07)
- **Context:** No standard docs-conventions filename exists in the wild; the
  role is filled piecemeal by `.adr-dir` (tiny pointer), GitLab's
  docs-about-docs directory (human meta-doc), and site-generator navs
  (machine manifests). The maintainer wants one file the root CLAUDE.md can
  reference so agents learn the local dialect before filing anything.
- **Decision:** Adopt `docs/CONVENTIONS.md` as this skill's convention:
  free-form markdown (AGENTS.md philosophy, no schema) holding Dialect
  lines, a path→charter→audience Layout map, naming rules, and greppable
  pointers. Init mode generates it by *describing observed practice*,
  marking baseline-defaulted lines for veto, and wires the root CLAUDE.md
  reference in the same change.
- **Consequences:** The layout map becomes the misplacement oracle for all
  future audits; evidence.md honestly records that this is a defined
  convention composing precedents, not an adopted industry standard.
- **Lens:** When the skill needs a repo to declare something, the
  declaration is markdown a human can edit and veto, generated from what
  the repo already does — never a schema, and never a prescription written
  before observation.

### ADR-4: partial misplacement is a first-class finding, judged against written charters

- **Status:** Accepted (2026-07)
- **Context:** The highest-value organisation failures are within-file: a
  README absorbing contributor policy, decisions buried in prose invisible
  to the ADR surface, agent files warehousing conventions. Whole-file
  checks (presence, naming, location) catch none of these; and "this
  section feels wrong here" is taste unless anchored to something.
- **Decision:** The audit builds a charter table (one line per document:
  what belongs in it) *before* judging any section; partial smells P1-P6
  are detected by asking which charter a section serves. Sections serving
  two charters are reported with both candidates — uncertain is a question,
  not a move. Every extract leaves a one-line link at the source.
- **Consequences:** Audits require reading, not just globbing (subagent
  fan-out for large repos); findings carry evidence a user can check
  (section heading + charter mismatch).
- **Lens:** No placement verdict without a charter to cite. If a section's
  correct home is genuinely ambiguous, the ladder says the user decides —
  record the ruling in `learned/` and never re-litigate it.

### ADR-5: apply is mechanical, history-preserving, and loss-free

- **Status:** Accepted (2026-07)
- **Context:** Reorganisation is only trustworthy if nothing is lost and
  nothing breaks: renames that orphan inbound links, deletes disguised as
  moves, and renumbered ADRs that break citations all destroy more value
  than misplacement ever did.
- **Decision:** Apply's closed operation set (create-stub / move / rename /
  extract / merge / link / symlink) with invariants: `git mv` always;
  repo-wide inbound-reference rewrite; redirect stubs where external links
  may exist; ADR ids immutable; deletion not in the vocabulary (merge
  leaves a link); verification greps before done.
- **Consequences:** Apply is slower than a naive move script and every step
  is commit-sized and reversible; a plan row that can't be executed
  loss-free is reported back, not forced.
- **Lens:** An organisation change is done when every old path either
  resolves or intentionally redirects, and `git status` shows renames, not
  a delete+add pair. If an operation can't meet that bar, it's a finding
  for the user, not an action.

### ADR-6: GLOSSARY.md is required, and its currency obligation lives in CLAUDE.md wiring

- **Status:** Accepted (2026-07)
- **Context:** The maintainer treats the project's domain vocabulary as a
  **ubiquitous language** shared between developer and agent: naming in
  code, docs, and conversation must converge on one canonical term per
  concept, and the vocabulary must not silently grow outside the shared
  reference. But "is this glossary up to date?" is a content-freshness
  question — exactly what ADR-1 forbids the librarian from judging.
- **Decision:** GLOSSARY.md joins the required document set in every
  flavour. The librarian enforces the *structural* contract: the file
  exists; CLAUDE.md carries both standing instructions (use canonical terms
  for naming; add new domain terms in the same change that introduces
  them); and terms defined ad hoc elsewhere are consolidated (smell P7 —
  home and uniqueness are placement questions). Whether a definition is
  accurate or the glossary is complete stays out of scope: the CLAUDE.md
  wiring makes *every future agent session* the currency mechanism.
- **Consequences:** The audit can guarantee the shared-language contract is
  wired without reading a single definition; drift detection on glossary
  content belongs to content-quality tooling.
- **Lens:** When a document's value depends on staying current, the
  librarian's job is to install the *obligation* (the cross-link and the
  standing instruction in the agent file), never the *content*. Enforce
  wiring, not freshness.

### ADR-7: flavours are named presets; growth is handled by graduation triggers, not bigger defaults

- **Status:** Accepted (2026-07)
- **Context:** The maintainer initialises projects of very different use
  case, scale, complexity, and rigour, and wants (a) a deliberate starting
  layout per case rather than one-size-fits-all, and (b) to know *when* a
  growing project should adopt scale-up elements. A single baseline can't
  serve both a prototype and a regulated platform: sized for the large
  case it inflicts premature taxonomy (smell M9); sized for the small case
  it under-serves rigour.
- **Decision:** Three named flavours (minimal / standard / rigorous) in
  `resources/flavours.md`, each a coherent bundle across every layout
  dimension, all sharing the non-negotiable core set (README, CONTRIBUTING,
  CLAUDE.md-role, ADR surface, GLOSSARY.md + cross-links). Init records the
  flavour in CONVENTIONS.md, where it becomes declared dialect. Each
  scale-up element carries an observable graduation trigger; audit compares
  observed scale against the declared flavour and emits a Graduation
  section — 🟣 recommendations applied only on acceptance, never findings
  (ADR-2), and downscaling recommendations are equally legitimate.
- **Consequences:** Two repos on different flavours are both fully
  compliant; growth pressure surfaces as explicit, dated recommendations
  instead of silent drift or premature structure.
- **Lens:** Size structure to the project, not the textbook: a flavour sets
  the starting shape, an observable trigger justifies each escalation, and
  no element is ever introduced "because bigger projects have it" — only
  because its trigger fired.

## Extension checklist

- [ ] New smells enter `misplacement_smells.md` with symptom, detection, fix,
      and severity — and never a content-quality judgement (ADR-1).
- [ ] New baseline claims cite a source in `evidence.md` with the research
      date; deployment/adoption stats re-verified if load-bearing (ADR-2).
- [ ] Any new apply operation defines its loss-free invariant before use
      (ADR-5).
- [ ] Rejected findings appended to `resources/learned/adjudications.md` in
      the same session (statefulness rule, Pathway 2).
- [ ] New required documents enter via the flavour table (all flavours or a
      graduation trigger) with their cross-link obligations stated (ADR-6/7).
- [ ] New scale-up elements define an observable graduation trigger before
      entering `flavours.md` (ADR-7).
- [ ] Deterministic checks (presence, naming, link resolution) are candidates
      for a future `scripts/` helper + eval suite per the skills scripts/evals
      contracts — added as Tier A/B scripts when audit volume justifies it.
- [ ] Both mermaid gates + mdtoc re-run if README touched; all files ≤ 500
      lines; prose stays brand-agnostic.

## Known gotchas

- A single existing file is not a convention: the observed-dialect rung needs
  ≥3 consistent instances, or the librarian will canonise an accident (ADR-2).
- Grep-only audits miss every P-smell — partial misplacement requires reading
  sections; budget subagents for it on large repos (ADR-4).
- `git mv` alone doesn't rewrite links; the inbound-reference grep must cover
  agent files, configs, and code comments, not just markdown (ADR-5).
- Health files moved *out* of the three GitHub-recognised locations silently
  lose platform surfacing — the file still exists, so nothing errors; only
  the audit's location check catches it.
- Renaming a heading during an extract changes its anchor; inbound `#anchor`
  links break invisibly. Grep old anchors, not just old paths.
- The description of CLAUDE.md/AGENTS.md interchangeability rots fastest:
  harness support shifts (evidence.md counter-evidence) — re-verify before
  hardening any symlink recommendation into a finding.
