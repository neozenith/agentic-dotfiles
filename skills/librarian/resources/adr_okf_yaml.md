# The `okf-yaml` ADR surface convention

A named, selectable convention for a decision-record surface: **records are authored as YAML, and their markdown is generated in a form that conforms to the Open Knowledge Format (OKF)**.

Invoke it by name — `/librarian index okf-yaml <path>` to adopt or migrate, `/librarian audit` to judge a surface that already declares it.
It is one option, not the default.
[adr_template.md](adr_template.md) owns the shape of a single record and remains the rung-3 default; this file owns the shape of the whole **bundle** and is only correct when a trigger from [structured_siblings.md](structured_siblings.md) has fired.

Recorded in `docs/CONVENTIONS.md` as a dialect line, so it sits at rung 1 of the authority ladder once declared:

```markdown
- ADR surface: `okf-yaml` — records authored in `adrs/NNNN-slug.yml`, markdown generated
- Generated paths: `adrs/*.md`, `adrs/index.md`, `adrs/graph.json`, `adrs/graph.html`
- Regenerate: `make adrs`
```

## Why this convention exists

Three capabilities plain markdown records cannot offer, each with the failure it prevents:

| Capability | Prevents |
|---|---|
| Typed relations over a closed vocabulary | One-way cross-references that no reader notices and no tool can check |
| A JSON Schema with `additionalProperties: false` | A typo in a field name silently becoming an ignored field |
| Index and graph generated from the same fields that render the records | A derived view drifting from the records it depicts |
| A viewer generated beside the graph data | A typed relation graph nobody can see, and therefore nobody checks |

And one it borrows from OKF: the generated markdown is a **portable bundle** any OKF-aware consumer can read without bespoke parsing.

## What the skill ships

The convention is not described here and left to be rebuilt — the artifacts are in the skill and are copied into the adopting repo:

| Artifact | Path | Role |
|---|---|---|
| Record schema | `resources/okf_yaml/record.schema.json` | The contract. Copy it and tighten the patterns to the repo's dialect. |
| Worked bundle | `resources/okf_yaml/example/` | Two records, their generated markdown, index and graph. Doubles as the **golden fixture**: a generator ported to another language must reproduce these bytes. |
| Generator | `scripts/okf_render.py` | Reference implementation. Validates first, then renders. |
| Templates | `scripts/templates/*.j2` | Jinja: one per generated artifact. |

```sh
uv run --no-project --with PyYAML --with Jinja2 --with jsonschema \
  .claude/skills/librarian/scripts/okf_render.py <bundle-dir>
```

`--group-by tag|plan_id` picks the graph clustering key; `--author` sets the generated `generated.by`; `--schema` points at the repo's own copy once it has diverged.

## Layout

```
adrs/
├── record.schema.json     source    — the record contract
├── NNNN-slug.yml          source    — one record each
├── templates/             source    — one template per generated artifact
├── okf_render.py          source    — the generator
│
├── tokens.json            source    — OPTIONAL design tokens for the viewer
│
├── NNNN-slug.md           GENERATED — OKF-conformant, the human reading surface
├── index.md               GENERATED — OKF reserved directory listing
├── graph.md               GENERATED — companion doc holding the graph
├── graph.json             GENERATED — the typed relation graph
└── graph.html             GENERATED — the viewer for that graph
```

### `graph.html` is always generated

A typed relation graph exists to be checked, and a graph nobody can see is not
checked. The viewer therefore ships with every bundle rather than being an
opt-in extra, and the generator writes it unconditionally.

It is a single self-contained file that works from `file://` with no server:

- **Three inlined data blocks** — the Cytoscape elements, every record's
  rendered markdown, and the design tokens. The reading pane needs no fetch,
  so opening the file is the whole setup.
- **Two CDN scripts**, cytoscape.js and marked.js, are the only network
  dependency. With no network the page says so and points at `index.md`.
- **A deterministic layout.** Groups are shelf-packed from the sorted record
  ids, so the committed file draws the same picture on every rebuild. A force
  layout would make every regeneration a diff.
- **Both channels derived, not assigned.** Fill is the record's group, node
  size is in-degree (how many records refine or supersede it), and status
  rides on the border rather than spending a colour channel.
- **The hash is the address**, so a pasted link opens its record and the
  browser's back button walks the reading history.

A repo with its own brandpack drops a `tokens.json` beside its records, shaped
`{"themes": {"light": {...}, "dark": {...}}}` with CSS custom property names
minus the `--` prefix. Absent that file the generator inlines its own defaults,
so the viewer is never broken by a missing brandpack.

## The record

The authority is `resources/okf_yaml/record.schema.json`; this is its shape in prose.
Every field the generator or a query needs is declared there — a field only a template reads still belongs in the schema, or the generator grows a second undocumented contract.
`resources/okf_yaml/example/0001-validate-at-the-boundary.yml` is a complete, valid record to copy.

```yaml
id: REC-0008
slug: strict-tolerance-on-verification
plan_id: null                # optional external identifier; null once that axis ends
title: "<the decision, as a short assertion>"
description: "<one-line routing summary; a label, not a sentence, so no trailing full stop>"
status: accepted             # proposed | accepted | superseded | retired
accepted_on: 2026-08-28
last_changed_on: 2026-08-28
tags: [verification, placement]

lens: |-
  <the forward-looking rule, one or two sentences>
  <multi-line prose uses a literal block scalar so sentence-per-line survives>

provenance: "<what forced the decision, in prose>"
enforced_in:
  - <surface the decision binds>

relates_to:
  - relation: see_also
    target: REC-0010
    note: <what the relation means, in a clause>

problem:
  symptom: <what was observed>
  pain_point: <what it cost, and why that cost matters>

decision:
  given: <the fact the decision rests on>
  we_prefer: <the choice, naming the rejected alternative: "X, over Y">
  because: <why the preference follows from the given>
  unless: <the escape hatch, or "never" when unconditional>
  in_practice:
    - <how it shows up in the work>

consequences:
  pros:
    - <what it buys>
  cons:
    - <what it costs; a record with no cons has not been thought about>
```

### Schema rules worth encoding

- `additionalProperties: false` at every level — the whole point is that a typo fails.
- `id` and `slug` patterns; `status` as a closed enum; `plan_id` nullable rather than absent.
- `consequences.cons` with `minItems: 1`.
- `description` anchored (`not: {pattern: "\\.$"}`) rather than banning `.`, or any value containing a path fails.
- Dates validate as strings only after a JSON projection — YAML resolves an unquoted `2026-08-28` to a date object.

### The relation vocabulary

Closed, and every relation paired with its inverse so a validator can check symmetry:

| Relation | Inverse | Means |
|---|---|---|
| `extends` | `extended_by` | Adds a clause without replacing the earlier decision |
| `split_from` | `split_to` | Carved out when one record grew two decisions |
| `supersedes` | `superseded_by` | Replaces it; the earlier record stays, marked superseded |
| `depends_on` | `depended_on_by` | Only implementable because the other holds |
| `tests` | `tested_by` | Names how the other decision is verified |
| `excepts` | `excepted_by` | A scoped carve-out; the rule stands everywhere else |
| `see_also` | `see_also` | Related reasoning, no dependency |

A missing inverse is **reported, never failed**: it is a gap in the record set, and the first symmetry run on an existing corpus normally finds several.

## OKF conformance of the generated markdown

The bundle conforms when, and only when:

1. Every non-reserved `.md` has parseable YAML frontmatter carrying a non-empty `type`.
2. `index.md` and `log.md` are the only reserved names, and they carry **no** frontmatter.
3. `log.md` date headings are ISO `YYYY-MM-DD`.

Everything else in OKF is soft guidance a consumer must not reject a bundle over — missing optional fields, unknown `type` values, custom keys, broken links, an absent index.

Generated frontmatter:

```yaml
---
type: Architecture Decision
title: "<from title>"
description: "<from description>"
tags: [verification, placement]
status: accepted
accepted_on: 2026-08-28
plan_id: <custom key; producers may extend, consumers must preserve>
provenance: "<custom key>"
enforced_in:
  - <custom key>
generated: { by: human:<handle>, at: <last_changed_on>T00:00:00Z }
---
```

Two consequences worth stating up front:

- **The title lives in frontmatter, not an H1.** That is what makes the record open with its Lens blockquote and no heading above it, and it shortens every query path by one segment.
- **Links are untyped in OKF.** The typed graph is this convention's addition, carried in `relates_to` and rendered into the body as prose plus `graph.json`. An OKF consumer sees ordinary links; a schema-aware one sees the edges.

## Curating a shelving plan against this convention

Once declared, the convention is the oracle. Findings are structural only — a record's reasoning is never judged ([SKILL.md](../SKILL.md), cross-cutting rules).

| Finding | Smell | Operation | Severity |
|---|---|---|---|
| A `.yml` record fails `record.schema.json` | — | fix the record (source, not generated) | 🔴 |
| A generated `.md` has no frontmatter `type` | — | regenerate; if it persists, fix the template | 🔴 |
| `relates_to` names a target that does not exist | — | fix the record | 🔴 |
| A generated file was hand-edited (differs from a fresh build) | M-class duplication | regenerate; the edit belongs in the source | 🔴 |
| `graph.html` is absent from the bundle | M1 (missing) | regenerate; the viewer is not optional | 🔴 |
| `graph.html` fetches its data instead of inlining it | — | regenerate; a viewer that needs a server is not usable from `file://` | 🔴 |
| A record exists as `.md` only, with no `.yml` source | M1 (missing) | migrate the record into the bundle | 🟡 |
| `index.md` or `log.md` carries frontmatter | — | regenerate; reserved files take none | 🟡 |
| A relation has no inverse on the far record | — | report; the user decides whether to add it | 🟡 |
| `README.md` sits in the bundle without frontmatter | M-class | rename to `index.md`, or give it frontmatter, or move it out | 🟡 |
| Regeneration is a remembered command, not a target | — | wire a `make` target | 🟡 |
| The convention is undeclared while the repo follows it | — | add the dialect lines to `docs/CONVENTIONS.md` | 🟣 |

Generated files are build artifacts everywhere else in the audit: exempt from naming and placement smells, never hand-edited, and a stale one is a content-quality question this skill does not answer.

## Migrating an existing ADR surface into it

An APPLY operation, opt-in, one commit-sized step per numbered finding.

1. **Extract, do not rewrite.** Parse each existing record into the record shape; ids and slugs are immutable, so every citation and anchor still resolves.
2. **Prove the argument survives.** Generate the markdown and diff `## Problem` onward against the original. **Byte-identical or the migration stops** — anything else means the templates are reformatting decisions.
   The shipped example bundle is the same proof at small scale: `make -C .claude/skills/librarian/scripts ci` fails if the generator stops reproducing it.
3. **Declare the one-way conversion before running it.** Turning prose relations into typed edges loses the phrasing: `"Feeds the verdict in REC-0008"` becomes `see_also REC-0008 (feeds the verdict)`. The nuance survives in `note`; the sentence does not. List every affected record and get acceptance.
4. **Carry non-conforming metadata into custom keys** rather than dropping it. A `Status` cell reading `Accepted, <date> (split from REC-0001 on <date>)` becomes `accepted_on` + `last_changed_on` + a `split_from` edge; say so, because the sentence is gone.
5. **Keep the old surface until the new one is verified**, then swap in one commit so no window exists where citations dangle.
6. **Record the dialect lines and wire the make target** in the same change.

## Verification gate

Not done until all of these pass:

```text
[ ] Every record validates against record.schema.json (via the JSON projection).
[ ] Every relates_to target resolves; asymmetric relations are reported, not failed.
[ ] Every generated .md carries frontmatter with a non-empty type.
[ ] index.md and log.md carry no frontmatter; log.md headings are ISO dates.
[ ] Each generated argument is byte-identical to the record it came from.
[ ] graph.json ids are unique and every edge endpoint resolves to a node.
[ ] graph.html exists, inlines all three data blocks, and contains no unrendered template markers.
[ ] Every generated file carries a regenerate banner naming its generator.
[ ] Regeneration is a make target, and re-running it leaves the tree clean.
```

## Known gotchas

- **A `README.md` in the bundle is a concept, not a reserved name**, so OKF requires it to carry frontmatter. Either rename it to `index.md`, give it frontmatter, or move it out — and remember an agent file may point at the old path.
- **Bundle-relative links (`/adrs/NNNN-slug.md`) are OKF's recommendation but resolve against the repo root on most forges**, breaking rendering. Relative links are permitted; choose one and record it.
- **Cross-bundle linking is unspecified.** OKF addresses concepts within a bundle only; a reference to another bundle's record belongs in `provenance` or a citation, not a link that looks resolvable.
- **A generator in a language the repo does not otherwise use** adds an install step, a lint config, and a CI job. Say so when recommending; porting the generator to the repo's own language is often the better answer.
