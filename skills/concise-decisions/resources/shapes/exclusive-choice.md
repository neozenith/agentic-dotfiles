# Shape: exclusive choice

Part of `concise-decisions` ([../../SKILL.md](../../SKILL.md) step 4). Load
for a decision with 2–3 mutually exclusive options. This is the baseline
shape; the other shape files describe deltas from it.

## Recognise it

- Exactly one option will be implemented; choosing A excludes B and C.
- Each option is something you would genuinely build — not "do it / don't
  do it / something else".
- If only two options are real, load [binary.md](binary.md) instead; if the
  options compose, load [subset-as-permutations.md](subset-as-permutations.md).

## Anatomy

The base template in
[../question-template.md](../question-template.md), unchanged. What carries
the weight in this shape:

- **Complete previews.** Each option shows the *same* real scenario rendered
  in that option's terms — the same command, the same file — so the user
  compares like with like. Where a second surface is affected (a saved config
  that mirrors a CLI grammar, an API response that mirrors a schema), show
  that surface per option too.
- **Compare table with domain columns.** Choose columns that expose the real
  trade-off (quoting layers, parser count, mapping fidelity), not generic
  "pros/cons" headers — those already sit under each preview.
- **Recommendation in the title** of the recommended option *and* in the
  Recommendation line.

## Worked example (generic)

A CLI must express several "rule groups" (selector → target → action) in one
invocation using only a stdlib flag parser that has no native repeated groups.

````markdown
## ADR-RULES — multi-group syntax for `mytool apply`

**Decision to make:** choose how one `mytool apply` invocation expresses an ordered list of selector, target, and action groups using the standard library flag parser.

### Why decide this now

| Context | Effect on this decision |
|---|---|
| Parser and planner | `internal/rule/flags.go` cannot parse several groups until their boundaries have a syntax. |
| Regex spelling decision | The grouping syntax decides how many quoting layers surround values such as `title=/Work/`. |
| Saved-profile format | The CLI grammar must map losslessly onto the `match` / `target` / `action` keys in YAML. |
| Why this one first | Three other questions are queued (regex spelling, profile directory, distribution); this answer narrows the first and blocks none of the others, whereas none of them unblocks the parser. |
| Outside this decision | Config directory, capture feature, distribution channel. |

**Already settled:** Checked `docs/adrs/`, `CLAUDE.md`, and the plan's Decisions section. The stdlib-parser decision (ADR-0003 there) rules out a framework's native repeated groups — which is why the syntax is a decision at all. Ordering (first match wins) is settled and unaffected.

**Reversibility:** low. The command becomes muscle memory and saved profiles freeze the key names.

### A: repeat one complete `--rule` string

```zsh
mytool apply --rule 'match="bundle=com.example.editor" target=index=1 action=maximize' \
             --rule "match=\"app='Browser' title=/Work/\" target=index=2 action=left-half"
```

**Pros:** Each repeated flag is an explicit boundary; order preserved.
**Cons:** A second parser; a two-term selector nests shell, rule, and selector quoting; YAML stores an opaque string or re-parses it.

### B (Recommended): each `--match` opens a group

```zsh
mytool apply --match bundle=com.example.editor     --target index=1 --action maximize \
             --match 'app="Browser" title=/Work/'   --target index=2 --action left-half
```

**Pros:** One quoting layer; CLI and YAML keys identical; stdlib `Set` is called in command order, so saving preserves structure.
**Cons:** `--target`/`--action` bind to the most recent `--match`; a field before the first `--match` must be a clear usage error.

### C: positional groups separated by `--`

```zsh
mytool apply -- bundle=com.example.editor index=1 maximize -- 'app="Browser" title=/Work/' index=2 left-half
```

**Pros:** No custom flag value type.
**Cons:** The parser stops at the first `--`, so later separators are hand-split; roles are positional; YAML needs key names the CLI never shows.

### Compare

| Option | Quoting layers | Group boundary | CLI → YAML | Main cost |
|---|---:|---|---|---|
| A | 2–3 | each `--rule` | opaque or re-parsed | second grammar |
| B | 1 | each `--match` | exact mirror | ordered-flag coupling |
| C | 1 | each manual `--` | invented keys | fights the parser |

**Recommendation:** choose B — the only option where the CLI grammar *is* the saved-profile grammar.

### TBD: answer without deciding

| Route | What happens next |
|---|---|
| `explain: <part>` | Revise the unclear part and ask again. |
| `show` | One complete command plus its dry-run output per grammar. |
| `spike: <question>` | Parse all three against the real rule set (30 min, one script) and report what breaks. |
| `defer` or `handoff` | Log this question and the recommendation as a ticket (`gh issue`); record the seam; continue with B provisionally. |
| `other: <syntax>` | Render it at the same depth and ask again. |

Your reasoning becomes ADR-RULES's Why.

```text
Reply with A, B or C and your reasoning.
Alternatively choose from <explain|show|spike|defer|handoff|other|task> and your reasoning to revise/iterate.
```
````

## Shape-specific checks

- Every option's preview is the **same scenario**; if one option's preview
  uses a simpler case, the comparison is rigged.
- The `Already settled` line explains why the obvious prior decision does
  not already pick the answer.
- Three options means three real implementations. A third "weak" option is
  padding — drop to [binary.md](binary.md).
