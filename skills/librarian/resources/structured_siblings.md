# Structured siblings

A layout in which a document's **data lives in YAML** and the **markdown is generated**, or in which a markdown document gains a **generated YAML index** beside it.
Load this when a repo asks for machine-readable documentation: queryable decision records, a derived index or graph, or a schema gate on document structure.

Two distinct arrangements share the name.
Choose deliberately — they have opposite sources of truth.

| Arrangement | Source of truth | Generated | Use when |
|---|---|---|---|
| **Authored YAML** (`yaml-source`) | `NNNN-slug.yml` | `NNNN-slug.md`, index, graph | Records are uniform and want schema validation, typed relations, derived views |
| **Indexed markdown** (`md-source`) | `NNNN-slug.md` | `NNNN-slug.yml` | Prose stays the authoring surface; the index exists only to be queried |

The librarian treats either as a **dialect line**, so it sits at rung 3 of the authority ladder: a repo that has declared or consistently demonstrated one is compliant, and the other is never a finding against it.
Generated files are never findings at all — they are build artifacts, exempt from naming and placement smells, and a stale one is a content-quality question this skill does not judge.

## When to recommend it

Only on an observable trigger, never because it is more sophisticated:

| Trigger | Arrangement |
|---|---|
| A repo queries its own records (scripts, dashboards, CI gates reading decisions) | either |
| Records carry cross-references that a reader must follow to understand the set | yaml-source (typed relations) |
| Records must satisfy a structural contract stronger than "has a Status heading" | yaml-source (JSON Schema) |
| A derived view exists and drifts (a hand-drawn diagram of record relationships) | yaml-source |
| The corpus is read by agents more often than by humans | md-source |
| None of the above | **neither** — plain markdown is correct |

Adopting this on a repo with a handful of records and no consumer is premature structure.
Say so.

## Arrangement A: authored YAML

```
records/
├── record.schema.json     source   — the contract
├── NNNN-slug.yml          source   — one record each
├── templates/*.j2         source   — one template per generated artifact
├── build.<ext>            source   — the generator
│
├── NNNN-slug.md           GENERATED — human-readable, the reading surface
├── index.md               GENERATED — the directory listing
└── graph.json             GENERATED — the relation graph, for any viewer
```

Every generated file carries a "do not edit; regenerate" banner naming the generator.

### What earns the extra machinery

Three capabilities plain markdown cannot offer. If a repo wants none of them, it does not want this arrangement.

**1. Typed relations.** Prose cross-references (`"supersedes the earlier decision"`, `"relies on this"`) become `{relation, target, note}` over a closed vocabulary of paired inverses:

```yaml
relates_to:
  - relation: supersedes
    target: REC-0004
    note: the earlier tolerance rule
```

Pairing every relation with an inverse (`extends`/`extended_by`, `depends_on`/`depended_on_by`, `supersedes`/`superseded_by`, and `see_also` as its own inverse) lets a validator check symmetry, which surfaces one-way references no reader would notice.
Expect it to find some on first run: that is the point, and they are gaps in the record set rather than migration artifacts.

**2. Field-level linting.** A JSON Schema with `additionalProperties: false` turns a typo in a key into an error rather than a silently ignored field.
Constrain what is worth constraining: an id pattern, a closed `status` vocabulary, `minItems: 1` on the consequences a record must state.

**3. Derived views that cannot drift.** An index and a relation graph generated from the same fields that render the markdown cannot disagree with the records.

### Invariants

- **The generated markdown's argument must be byte-identical to what a human would have written.** Verify it, do not assume it.
- **Templates own presentation; the schema owns structure.** A change to how a record reads is a template change and touches no record.
- **A field only a template reads still belongs in the schema.** Undeclared fields are how a generator grows a second, undocumented contract.
- **Metadata beats a title heading.** Putting the title in frontmatter rather than an H1 shortens every query path by one segment, because no root heading nests the whole document (see the path rule below).

One fully-specified instance of this arrangement ships with the skill: the named **`okf-yaml`** ADR surface in [adr_okf_yaml.md](adr_okf_yaml.md), which fixes the schema, the relation vocabulary, the bundle layout and the finding table.
Reach for it when the document set is decision records; use the generic arrangement below when it is not.

### Migration

Migrating existing records into this arrangement is an opt-in APPLY operation with the usual loss-free bar: ids immutable, every anchor still resolving, the generated markdown diffed against the originals before the originals are touched.

One conversion is inherently one-way and must be called out before it runs: **turning prose relations into typed edges loses the phrasing.** `"Feeds the verdict in REC-0008"` becomes `see_also REC-0008 (feeds the verdict)`.
The nuance survives in `note`; the sentence does not.
Report the exact list of affected records and let the user accept it.

## Arrangement B: indexed markdown

The markdown stays authoritative and a YAML index is generated beside it, so the corpus becomes queryable without changing how anyone writes.
`scripts/md2yaml.ts` produces the index; its `--check` mode is the gate.

### The design rule

**Use the markdown AST to find boundaries, not to represent content.**

Storing the parsed tree in YAML is unreadable and lossy on re-serialisation: emphasis markers and list bullets come back normalised.
Instead, every AST node carries source offsets, so each block's exact text is a *slice* of the original file.
Storing slices keeps inline formatting (it is literal markdown), keeps fenced code verbatim, keeps block order, and makes the round trip byte-exact — which is what lets the index be regenerated without ever reformatting the document it indexes.

### The shape

```yaml
frontmatter: { … }        # parsed, because it is data
preamble: …               # blocks before any heading
sections:                 # a SEQUENCE: document order is meaning
  - key: problem          # slugified heading — the queryable name
    path: problem         # dotted address, for direct selection
    heading: Problem      # the heading as written, formatting intact
    depth: 2
    sections:
      - key: pain_point
        path: problem.pain_point
        content:          # ordered blocks, because this section is mixed
          - type: paragraph
            md: "Prose before a fence:"
          - type: code
            md: "```go\n…\n```"
            lang: go
```

- `sections` is a **sequence**, not a mapping: mappings lose order once loaded.
- A section holding exactly one paragraph collapses to a plain scalar — the common case, and it keeps the file readable.
- Structural blocks expose their parts alongside `md`, never instead of it: `header`/`align`/`rows` on a table (one map per row, keyed by slugified column), `ordered`/`items` on a list, `lang` on code.
  Cell and item values are themselves slices, so a cell reading `**13 ms**` indexes as `**13 ms**` rather than flattened text.

### Querying

`path` is a dotted address, so a query selects a section directly instead of recursing.
`--json` emits the same index for `jq`; the YAML works with `yq` unchanged.

```sh
# every value of one metadata-table row, across a corpus
jq -r 'select([..|objects|select(has("rows"))|.rows[]
              |select(.field=="**Owner**")|.value]|any(test("platform")))|.file' corpus.ndjson
```

Because `path` is built from ancestor headings, a document whose title is an H1 yields `long_title_slug.problem.symptom`, while one whose title is in frontmatter yields `problem.symptom`.
Prefer the latter and queries stay legible.

### Whitespace is content

Byte-exactness needs three fields that a naive "join the blocks with a blank line" destroys.
Each is cheap to record and impossible to recover once lost:

| Field | Records |
|---|---|
| `gap` | Blank lines after a block or heading, when not exactly one — a command fence butted against its output fence, an extra line before a heading |
| `leading` | Blank lines before the first block, or after frontmatter |
| `trailing` | Newlines at end of file — none, one, or a trailing blank line are three different files |

A shortcut that collapses a section to a bare scalar must preserve `gap`, or it silently reformats.
A shortcut that discards a field is indistinguishable from a bug.

## Verification (both arrangements)

A structured-sibling setup is not done until a gate proves it. The gate is cheap and the failures it catches are all silent:

```text
[ ] Every source record validates against the schema (yaml-source).
[ ] Every relation target resolves; asymmetric relations are reported, not failed (yaml-source).
[ ] Round trip is byte-exact: `md2yaml.ts <file> --check` exits 0 for every indexed document.
[ ] Generated markdown's argument is byte-identical to the authored original (yaml-source migration).
[ ] Every generated file carries a regenerate banner naming its generator.
[ ] The generator is wired to a make target, not a remembered command.
```

Run the round-trip check across the **whole** corpus, not a sample.
Documents that differ are worth reading: the difference is usually a construct the reconstruction does not model (raw HTML blocks, setext headings) rather than a corpus problem.

## Known gotchas

- **YAML implicit typing.** An unquoted `2026-08-30` parses as a date, not a string, so a JSON Schema `"type": "string"` rejects it. Validate the JSON projection, not the raw load. Same family as the Norway problem (`NO` → `false`), which bites country codes and single-letter values.
- **A heading is content, not a label.** Flattening a heading to text loses `` `code` `` and emphasis. Only the slug should use flattened text.
- **Content before the first heading is not an edge case.** In any format whose title is metadata, the document opens with a block and no heading above it. A parser that assumes a heading comes first drops it silently.
- **Over-blunt schema rules.** A rule banning `.` to enforce "no trailing full stop" fails any value containing a path like `~/.config`. Anchor the pattern.
- **A second toolchain is a real cost.** A generator in a language the repo does not otherwise use adds an install step, a lint config, and a CI job. Say so when recommending; the answer is often to port the generator to the repo's own language rather than to skip the arrangement.
