# librarian — Maintainer Decision Lens

Read the ADR log below before changing anything.
Each ADR carries a **Lens** — apply it to the next decision instead of re-deriving the trade-off.

## Development contract

Code gates first — the skill carries `scripts/` in two languages: TypeScript (bun) for the indexer, Python (uv) for the okf-yaml generator.
`ci` regenerates the shipped example bundle via `docs`, so a template change that stops reproducing the golden fails the gate. Run from repo root, never `cd`:

```sh
make -C .claude/skills/librarian/scripts fix   # mutates: format + lint --write, both languages
make -C .claude/skills/librarian/scripts ci    # the gate: format-check, lint, typecheck, test-cov (≥90%), docs
```

Doc gates before handoff, also from repo root:

```sh
bun run .claude/skills/mermaidjs-diagrams/scripts/mermaid_contrast.ts   .claude/skills/librarian/README.md
bun run .claude/skills/mermaidjs-diagrams/scripts/mermaid_complexity.ts .claude/skills/librarian/README.md
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
| `resources/adr_template.md` | Preferred shape of one ADR, for either layout (lazy; init + audit + apply) |
| `resources/structured_siblings.md` | Machine-readable layouts in general: authored-YAML vs indexed-markdown, triggers, output shape, gotchas (lazy; index mode) |
| `resources/adr_okf_yaml.md` | The named `okf-yaml` ADR-surface convention: record schema, relation vocabulary, OKF conformance, finding table, migration (lazy; named or observed) |
| `resources/okf_yaml/record.schema.json` | The okf-yaml record contract, copied into an adopting repo |
| `resources/okf_yaml/example/` | Worked two-record bundle; doubles as the golden fixture the Python suite diffs against |
| `scripts/okf_render.py` | Reference generator: validate, then render markdown + index + graph |
| `scripts/templates/*.j2` | Jinja templates, one per generated artifact |
| `scripts/test_okf_render.py` | pytest suite (PEP-723 entry point) |
| `scripts/conftest.py` | Coverage reload fixture |
| `resources/evidence.md` | Research citations + counter-evidence, dated 2026-07-23 |
| `scripts/md2yaml.ts` | The markdown → YAML/JSON indexer; `--check` is the byte-exact round-trip gate |
| `scripts/md2yaml.test.ts` | `bun:test` suite: structure, tables, lists, whitespace fields, CLI via subprocess |
| `scripts/Makefile` | `fix` / `ci` quality gates |
| `resources/learned/` | User adjudications on placement rulings (created on first rejection; already-decided) |
| `CLAUDE.md` | This file — rationale and decision log |

## Architecture principles

- Placement, existence, naming, linking only — content is cargo, never judged.
- Loss-free operations: `git mv`, inbound-link rewrites, link stubs; deletion is never an operation.
- Authority ladder: declared dialect > observed dialect > baseline; user adjudications beat all.
- Audit is read-only; only apply and init mutate.

## ADR log

### ADR-1: the skill judges location, never content

- **Status:** Accepted (2026-07)
- **Context:** The maintainer runs separate skills for content quality (drift/staleness, prose, within-one-file structure) and wants fine-grained independent control: organisation passes and quality passes must be composable without either being aware of the other.
  Mixing them would also make apply-mode diffs unreviewable (moves hiding rewrites).
- **Decision:** The librarian's verdict vocabulary is closed: missing, misnamed, misfiled, unlinked, duplicated.
  Extracted/moved content travels verbatim; a section that looks wrong in transit is flagged for a content-quality pass, never fixed here.
  The skill names no sibling skill and reads no sibling's files (skills are self-contained).
- **Consequences:** Apply diffs are pure moves and reviewable as such; the skill composes with any content-quality tooling; some obviously-stale text gets relocated untouched, which is correct.
- **Lens:** If a candidate feature needs to read a sentence to judge its *quality* rather than its *charter*, it belongs in a different skill.
  Charter questions ("which document should hold this?") are in; quality questions ("is this good/true?") are out.

### ADR-2: compliance resolves through a three-rung authority ladder

- **Status:** Accepted (2026-07)
- **Context:** Research found no ecosystem-standard docs layout to enforce: GitHub's health-file precedence, Diátaxis, and ADR conventions are strong defaults, but real repos hold deliberate local choices (single-file ADR logs, federated scoped logs, Ways-of-Working in README instead of CONTRIBUTING).
  A skill that imposes the textbook layout over a working local dialect creates churn, not compliance.
- **Decision:** Declared dialect (`docs/CONVENTIONS.md`) > observed dialect (a pattern consistently followed, ≥3 instances) > researched baseline.
  Internal inconsistency resolves to the majority pattern; the minority files are the findings.
  Baseline-preferred migrations (e.g. log → file-per-decision) are recommendations, never findings.
- **Consequences:** The audit must state which rung answered each contested question; two repos can both be fully compliant with different layouts.
- **Lens:** The librarian enforces *coherence with the repo's own declared or demonstrated system*, and only invents an answer (baseline) where the repo has none.
  Never file a finding whose only evidence is "the baseline prefers otherwise".

### ADR-3: docs/CONVENTIONS.md is the declared-dialect surface, and init describes rather than prescribes

- **Status:** Accepted (2026-07)
- **Context:** No standard docs-conventions filename exists in the wild; the role is filled piecemeal by `.adr-dir` (tiny pointer), GitLab's docs-about-docs directory (human meta-doc), and site-generator navs (machine manifests).
  The maintainer wants one file the root CLAUDE.md can reference so agents learn the local dialect before filing anything.
- **Decision:** Adopt `docs/CONVENTIONS.md` as this skill's convention: free-form markdown (AGENTS.md philosophy, no schema) holding Dialect lines, a path→charter→audience Layout map, naming rules, and greppable pointers.
  Init mode generates it by *describing observed practice*, marking baseline-defaulted lines for veto, and wires the root CLAUDE.md reference in the same change.
- **Consequences:** The layout map becomes the misplacement oracle for all future audits; evidence.md honestly records that this is a defined convention composing precedents, not an adopted industry standard.
- **Lens:** When the skill needs a repo to declare something, the declaration is markdown a human can edit and veto, generated from what the repo already does — never a schema, and never a prescription written before observation.

### ADR-4: partial misplacement is a first-class finding, judged against written charters

- **Status:** Accepted (2026-07)
- **Context:** The highest-value organisation failures are within-file: a README absorbing contributor policy, decisions buried in prose invisible to the ADR surface, agent files warehousing conventions.
  Whole-file checks (presence, naming, location) catch none of these; and "this section feels wrong here" is taste unless anchored to something.
- **Decision:** The audit builds a charter table (one line per document: what belongs in it) *before* judging any section; partial smells P1-P6 are detected by asking which charter a section serves.
  Sections serving two charters are reported with both candidates — uncertain is a question, not a move.
  Every extract leaves a one-line link at the source.
- **Consequences:** Audits require reading, not just globbing (subagent fan-out for large repos); findings carry evidence a user can check (section heading + charter mismatch).
- **Lens:** No placement verdict without a charter to cite.
  If a section's correct home is genuinely ambiguous, the ladder says the user decides — record the ruling in `learned/` and never re-litigate it.

### ADR-5: apply is mechanical, history-preserving, and loss-free

- **Status:** Accepted (2026-07)
- **Context:** Reorganisation is only trustworthy if nothing is lost and nothing breaks: renames that orphan inbound links, deletes disguised as moves, and renumbered ADRs that break citations all destroy more value than misplacement ever did.
- **Decision:** Apply's closed operation set (create-stub / move / rename / extract / merge / link / symlink) with invariants: `git mv` always; repo-wide inbound-reference rewrite; redirect stubs where external links may exist; ADR ids immutable; deletion not in the vocabulary (merge leaves a link); verification greps before done.
- **Consequences:** Apply is slower than a naive move script and every step is commit-sized and reversible; a plan row that can't be executed loss-free is reported back, not forced.
- **Lens:** An organisation change is done when every old path either resolves or intentionally redirects, and `git status` shows renames, not a delete+add pair.
  If an operation can't meet that bar, it's a finding for the user, not an action.

### ADR-6: GLOSSARY.md is required, and its currency obligation lives in CLAUDE.md wiring

- **Status:** Accepted (2026-07)
- **Context:** The maintainer treats the project's domain vocabulary as a **ubiquitous language** shared between developer and agent: naming in code, docs, and conversation must converge on one canonical term per concept, and the vocabulary must not silently grow outside the shared reference.
  But "is this glossary up to date?" is a content-freshness question — exactly what ADR-1 forbids the librarian from judging.
- **Decision:** GLOSSARY.md joins the required document set in every flavour.
  The librarian enforces the *structural* contract: the file exists; CLAUDE.md carries both standing instructions (use canonical terms for naming; add new domain terms in the same change that introduces them); and terms defined ad hoc elsewhere are consolidated (smell P7 — home and uniqueness are placement questions).
  Whether a definition is accurate or the glossary is complete stays out of scope: the CLAUDE.md wiring makes *every future agent session* the currency mechanism.
- **Consequences:** The audit can guarantee the shared-language contract is wired without reading a single definition; drift detection on glossary content belongs to content-quality tooling.
- **Lens:** When a document's value depends on staying current, the librarian's job is to install the *obligation* (the cross-link and the standing instruction in the agent file), never the *content*.
  Enforce wiring, not freshness.

### ADR-7: flavours are named presets; growth is handled by graduation triggers, not bigger defaults

- **Status:** Accepted (2026-07)
- **Context:** The maintainer initialises projects of very different use case, scale, complexity, and rigour, and wants (a) a deliberate starting layout per case rather than one-size-fits-all, and (b) to know *when* a growing project should adopt scale-up elements.
  A single baseline can't serve both a prototype and a regulated platform: sized for the large case it inflicts premature taxonomy (smell M9); sized for the small case it under-serves rigour.
- **Decision:** Three named flavours (minimal / standard / rigorous) in `resources/flavours.md`, each a coherent bundle across every layout dimension, all sharing the non-negotiable core set (README, CONTRIBUTING, CLAUDE.md-role, ADR surface, GLOSSARY.md + cross-links).
  Init records the flavour in CONVENTIONS.md, where it becomes declared dialect.
  Each scale-up element carries an observable graduation trigger; audit compares observed scale against the declared flavour and emits a Graduation section — 🟣 recommendations applied only on acceptance, never findings (ADR-2), and downscaling recommendations are equally legitimate.
- **Consequences:** Two repos on different flavours are both fully compliant; growth pressure surfaces as explicit, dated recommendations instead of silent drift or premature structure.
- **Lens:** Size structure to the project, not the textbook: a flavour sets the starting shape, an observable trigger justifies each escalation, and no element is ever introduced "because bigger projects have it" — only because its trigger fired.

### ADR-8: the preferred ADR format is a template the skill carries, not just a layout

- **Status:** Accepted (2026-08-25, user instruction)
- **Context:** The baseline covered where decision records *live* (single-file log vs file-per-decision) and said nothing about what one record *looks like*.
  So an audit could pass a repo whose ADRs were undated one-line bullets, and init produced an ADR surface with no shape to fill.
  Meanwhile the maintainer converged on a specific record format elsewhere in this repo: metadata table, a `Lens` blockquote holding the reusable rule, then Problem / Decision / Consequences under their own headings, with the decision itself written as `Given` / `We prefer … over …` / `Because` / `Unless`.
- **Decision:** Adopt that format as the librarian's preferred one and carry a **copy** at `resources/adr_template.md`, adapted to work in either layout (a file, or a section with headings demoted).
  Format is a dialect line like any other, so it sits at rung 3 of the authority ladder (ADR-2): a declared or consistently observed local format wins, and an accepted record is never rewritten to match.
  The skill uses it structurally only (ADR-1): a record missing Status, a decision statement, or reasoning is a finding; weak reasoning is not.
- **Provenance:** the format originates in the `concise-decisions` skill in this repo, which developed it over four layout iterations.
  This maintainer document may name that origin; no runtime surface here points at it.
  The copy is the skill's own, and it drifts from the origin on purpose (skills are self-contained).
- **Consequences:** Init now writes a `TEMPLATE.md` alongside the ADR surface and records the format as a Dialect line.
  Reformatting an existing log becomes an opt-in APPLY operation that preserves every id and anchor.
  This skill's own log (above) predates the format and has not been migrated, which is exactly the "never rewrite an accepted record" rule applied to itself.
- **Lens:** When the skill recommends a shape, ship the shape as a file it owns, not as prose describing one.
  A template can be copied into a repo, diffed, and vetoed; a paragraph saying "ADRs should have a status" cannot.
  Copy it in rather than pointing at wherever it came from.

### ADR-9: machine-readable siblings are generated artifacts, and the index is byte-reversible

- **Status:** Accepted (2026-08-30, user instruction)
- **Context:** Repos increasingly want their documentation *queried* — by scripts, CI gates, derived diagrams, and agents — not only read.
  Two arrangements answer that: author records as YAML and generate the markdown, or keep markdown authoritative and generate a YAML index beside it.
  Both create a second file per document, which every existing smell would flag as duplication (M-class) and which ADR-1 forbids the librarian from judging on content.
  The motivator is concrete: a corpus whose cross-references live in prose cannot be validated at all, so one-way references and drifted derived views survive indefinitely.
- **Decision:** Treat the arrangement as a **dialect line** (rung 3, ADR-2), so either is compliant and neither is a finding against the other.
  Generated files are build artifacts: exempt from naming and placement smells, never findings, never hand-edited, and always carrying a banner naming their generator.
  Adoption requires an **observable consumer** — a script, gate, or derived view that reads the records — mirroring the graduation-trigger rule (ADR-7); absent one, plain markdown is the correct answer and more structure is not an improvement.
  The indexer ships as a skill-owned script whose `--check` mode reconstructs the markdown and exits non-zero on any drift.
- **Consequences:** The skill stops being prose-only and takes on the scripts contract (`make fix` / `make ci`, ≥90% coverage) and a bun toolchain.
  Index mode mutates, but only generated paths — the first mutating mode that touches no source document.
  Prose-to-typed-relation conversion is inherently one-way and must be reported record-by-record before it runs (ADR-5's loss-free bar applies to *meaning*, not just to files).
- **Lens:** When the skill generates a file from another file, the generator must be able to reproduce the source **byte-for-byte** before the generated artifact is trusted.
  A round trip that is merely "equivalent" is a reformatter wearing an indexer's clothes, and it will silently rewrite documents the skill promised never to touch.
  Prove reversibility across the whole corpus, never a sample.

### ADR-10: a convention is invocable by name, or it is only advice

- **Status:** Accepted (2026-08-30, user instruction)
- **Context:** ADR-9 landed the *general* machine-readable pattern in `structured_siblings.md` — two arrangements, adoption triggers, output shape.
  But the concrete convention that motivated it (records authored as YAML, generating an OKF-conformant bundle with a record schema, typed relations and a derived graph) survived only as a shape sketch inside that general prose.
  The failure mode was immediate and observable: an agent could read the general resource and still not know which fields a record carries, which relations are legal, or what a finding against the convention looks like.
  Generalising a convention had erased the convention.
- **Decision:** Every convention the skill can be *asked for* ships as its own resource carrying four things a shelving plan needs: the layout, the finding table (finding → smell → operation → severity), the migration operation with its loss-free invariants, and a verification gate.
  It is selectable by name as an argument (`index okf-yaml <path>`), declarable as a dialect line, and detectable as an observed dialect — which makes it rung 1 or 2 evidence, displacing the generic template rather than competing with it.
  The general resource keeps the *choice* between arrangements and links down to each named instance; it never holds the instance's detail.
- **Consequences:** Adding a convention is now a known-shape task rather than an essay, and audits of a repo that follows one judge it against its own rules instead of the generic ADR template.
  The cost is one resource per convention, and the mirror of ADR-7's discipline applies: a named convention still needs an observable trigger, or naming it is just fashion.
- **Lens:** A convention the skill cannot be *invoked with by name* is documentation, not doctrine.
  When distilling a worked example into the skill, ask what an agent would need to file a finding against it and to migrate a repo to it; if the answer is not in one loadable file, the distillation is incomplete no matter how well the general principle reads.

### ADR-11: the convention ships its artifacts, and the skill goes mixed-language to run them

- **Status:** Accepted (2026-08-30, user decision)
- **Context:** ADR-10 made the convention invocable, but `adr_okf_yaml.md` still only *described* the schema and the bundle in fenced blocks.
  That is the failure ADR-8's lens already names — "ship the shape as a file it owns, not as prose describing one" — applied to the record and not to the bundle.
  Three options were weighed: schema plus golden fixtures only; a TypeScript port keeping the skill single-language; or vendoring the working Python/Jinja generator as-is.
  The maintainer chose the last: the generator is proven over a real corpus, and a port would trade that evidence for toolchain tidiness.
- **Decision:** Vendor the generator and its Jinja templates unchanged in substance, and accept the **mixed-language scripts contract** — one Makefile fanning out to `-py` and `-ts` sub-targets, `conftest.py`, pytest via PEP-723, ruff and mypy alongside biome and tsc, ≥90% coverage on both.
  The schema and a two-record worked bundle ship under `resources/okf_yaml/`, and that bundle is the **golden fixture**: `ci`'s `docs` target regenerates it, and the Python suite fails if the output drifts, so a generator ported to any other language has bytes to conform to.
  Genericisation is the price of vendoring: hardcoded group names became data (`group`, or `--group-by tag|plan_id`), and the author became `--author`.
- **Consequences:** A contributor now needs both `uv` and `bun` to run `ci`, and the README says so under requirements rather than letting it surface as a failure.
  Adopting repos are expected to port the generator to their own language, which is exactly what the golden fixture is for.
  Porting found a real defect the prose could not have: a null field rendered as `plan_id: None`, which parses as the string `'None'` — present in the origin bundle too, and fixed in both.
- **Lens:** Vendor the working implementation over a cleaner rewrite when the implementation carries evidence a rewrite would discard, and pay the toolchain cost openly in the requirements.
  But never vendor an artifact without a **fixture that pins its output**: the generator is the part that will be replaced, and the bytes it produces are the part that must not change.

## Extension checklist

- [ ] New smells enter `misplacement_smells.md` with symptom, detection, fix, and severity — and never a content-quality judgement (ADR-1).
- [ ] New baseline claims cite a source in `evidence.md` with the research date; deployment/adoption stats re-verified if load-bearing (ADR-2).
- [ ] Any new apply operation defines its loss-free invariant before use (ADR-5).
- [ ] Rejected findings appended to `resources/learned/adjudications.md` in the same session (statefulness rule, Pathway 2).
- [ ] New required documents enter via the flavour table (all flavours or a graduation trigger) with their cross-link obligations stated (ADR-6/7).
- [ ] New scale-up elements define an observable graduation trigger before entering `flavours.md` (ADR-7).
- [ ] Deterministic checks (presence, naming, link resolution) are candidates for further `scripts/` helpers per the skills scripts contract.
- [ ] Any change under `scripts/` leaves `make -C .claude/skills/librarian/scripts ci` at exit 0, coverage ≥ 90% (ADR-9).
- [ ] A new generated-artifact kind states its regenerate banner and its reversibility proof before it ships (ADR-9).
- [ ] A new **named** convention ships as its own resource with a layout, a shelving-plan finding table, a migration operation and a verification gate — never as prose inside the general resource (ADR-10).
- [ ] Both mermaid gates + mdtoc re-run if README touched; all files ≤ 500 lines; prose stays brand-agnostic.

## Known gotchas

- A single existing file is not a convention: the observed-dialect rung needs ≥3 consistent instances, or the librarian will canonise an accident (ADR-2).
- Grep-only audits miss every P-smell — partial misplacement requires reading sections; budget subagents for it on large repos (ADR-4).
- `git mv` alone doesn't rewrite links; the inbound-reference grep must cover agent files, configs, and code comments, not just markdown (ADR-5).
- Health files moved *out* of the three GitHub-recognised locations silently lose platform surfacing — the file still exists, so nothing errors; only the audit's location check catches it.
- Renaming a heading during an extract changes its anchor; inbound `#anchor` links break invisibly.
  Grep old anchors, not just old paths.
- Whitespace is content: blank lines before a heading, two fences butted together, and a missing final newline are invisible in a diff viewer and all break a round trip.
  `md2yaml.ts` models them as `gap` / `leading` / `trailing`; a new block type that ignores them reformats documents silently (ADR-9).
- YAML resolves an unquoted `2026-08-30` to a date, not a string, so a JSON Schema `"type": "string"` rejects it — validate the JSON projection, not the raw load.
- Flattening a heading to text (right for a slug) and *storing* that flattened text (wrong for anything reconstruction reads) are different operations; store the slice, or an inline-code heading loses its backticks.
- Content before the first heading is normal wherever the title lives in frontmatter, and a parser that assumes a heading comes first drops the document's opening with no error.
- The description of CLAUDE.md/AGENTS.md interchangeability rots fastest: harness support shifts (evidence.md counter-evidence) — re-verify before hardening any symlink recommendation into a finding.
