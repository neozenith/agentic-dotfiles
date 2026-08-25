# Shape: resolved by cascade

Part of `concise-decisions` ([../../SKILL.md](../../SKILL.md) step 4). Load
when a **prior decision narrowed this one** — so far that it is nearly
"confirm the implication" — but the ripple left constraints that now
**compete**, some of which were only visible after the prior decision landed.

## Recognise it

- The previous answer removed the factor you expected to decide this (e.g.
  quoting depth, once the grouping grammar is fixed).
- What remains is two or three external or system constraints pulling in
  different directions (a shell's expansion rules, a config format's literal
  rules, an engine's dialect).
- The user could reasonably ask "didn't we already decide this?" — check 3
  of the five is the one at risk.

## Anatomy — one delta from the base

**`Already settled` does extra work.** After the base `Checked:` line (the
records searched), it must say, in order:

1. the prior decision and its answer;
2. what that answer *fixed* — the factor that is no longer deciding;
3. what it did **not** settle, named as the constraints that now compete;
4. the reopen path: "if <PRIOR> was answered differently, this question
   reopens — say so via `explain`."

The rest is unchanged. Previews should render each option under **each
competing constraint** (the same selector in the shell, then in the saved
file) so the user sees the ripple, not just the options.

## Worked example (generic, abridged)

How a regex is marked inside a selector value, after the grouping-grammar
decision put every value under exactly one layer of shell quoting.

````markdown
## ADR-REGEX — how a regex is spelled inside a selector value

**Decision to make:** choose the marker that distinguishes a regex from a literal inside a selector term (`title=…`, `name=…`): `/pattern/`, `~pattern`, or `re:pattern`.

### Why decide this now
| Context | Effect on this decision |
|---|---|
| Parser | `ParseSelector` cannot be written without it. |
| Saved profiles | The template already contains `name: /Panel-4K/`; the same grammar must hold for every selector kind. |
| Outside this decision | Directory, capture, distribution. |

**Already settled:** Checked `docs/adrs/` and the plan's Decisions section. ADR-RULES = B (each `--match` opens a group) puts every value under exactly one layer of shell quoting, so quoting *depth* no longer decides this. What it did **not** settle, and what now competes: each marker's own shell hazard, whether the CLI literal survives into YAML unchanged, and the regex engine's dialect (look-arounds are rejected as a usage error under every option). If ADR-RULES was answered A instead, this question reopens — say so via `explain`.

**Reversibility:** low. The spelling lands in every saved profile and every alias the user types.

### A (Recommended): `/pattern/` with optional trailing `i`, terminated at the LAST slash

```zsh
--match 'app="Browser" title=/Work$/'
--match 'title=/Q3 a/b review/i'      # body up to the last slash
```

```yaml
title: /Work$/i                      # same literal as the CLI
```

**Pros:** Familiar; identical literal in CLI and YAML; a natural home for the `i` flag.
**Cons:** `/` is both delimiter and common in titles — last-slash termination handles it, but it is a rule to know.

### B: `title~pattern`

```zsh
--match title~Work$ --target name~Panel   # an unquoted ~ at word start expands to $HOME
```

```yaml
title: {regex: Work$}                # needs a structured form
```

**Pros:** No delimiter to escape.
**Cons:** Shell tilde expansion; a second YAML spelling.

### C: `title=re:pattern`

```zsh
--match 'title="re:Q3 a/b review"'     # no terminator, so spaces force inner quotes again
```

**Pros:** No shell metacharacters.
**Cons:** No terminator; nowhere for the `i` flag.

### Compare
| Option | Shell hazard | CLI = YAML literal | Flag home |
|---|---|---|---|
| A | none when quoted | yes | yes |
| B | `~` expansion | no | no |
| C | inner quotes for spaces | yes | no |

**Recommendation:** choose A — the one spelling that survives the shell, the file format, and the reader unchanged.

### TBD: answer without deciding
| Route | What happens next |
|---|---|
| `explain: <part>` | Expand it and ask again — say "ADR-RULES was A" if that is the issue. |
| `show` | Not useful here. |
| `spike: <question>` | Run all three against the real selector set under the user's shell and report what breaks. |
| `defer` or `handoff` | Record the seam; the template keeps `/…/` provisionally. |
| `other: <spelling>` | Render it and ask again. |

Reply … (reply footer, per the template)
````

## Shape-specific checks

- `Already settled` has all four parts (prior answer, what it fixed, what
  still competes, reopen path).
- Each preview shows the option under every competing constraint.
- The `explain` route explicitly offers to reopen the prior decision.
