# Shape: binary

Part of `concise-decisions` ([../../SKILL.md](../../SKILL.md) step 4). Load
when exactly two options are real — typically *in scope / out of scope*,
*now / later*, *strict / lenient*.

## Recognise it

- Two genuine implementations; a third would be padding.
- Often a scope cut: "does feature F belong in this spec?"
- One of the two may carry a sub-choice the user must also make if they pick
  it (e.g. *in scope* ⇒ which failure mode for the hard case).

## Anatomy — deltas from the base

- **Two options + TBD.** Do not invent a third. The answer surface has A, B,
  and the TBD route.
- **A sub-choice rides in the reply footer**, and the option's preview says
  so:

  ```text
  Reply with A or B and your reasoning; picking B, also name <sub-choice-1|sub-choice-2|sub-choice-3>.
  Alternatively choose from <explain|show|spike|defer|handoff|other|task> and your reasoning to revise/iterate.
  ```

- **Show the hard case in the "in scope" preview.** A binary is usually
  decided by the one input the feature handles badly; render that input in
  the preview (the record that maps to nothing, the window that fits no
  region, the file with no extension) with the honest alternatives for it.
- **`defer` needs its own line.** In a scope binary, `defer` is close to the
  "out of scope" option; say how it differs (it is recorded as a seam with a
  revisit condition, whereas "out of scope" closes the question).

## Worked example (generic, abridged)

Whether a "capture the current state into a saved profile" feature is in this
spec, or profiles are authored only from flags and a template.

````markdown
## ADR-CAPTURE — is "capture current state into a profile" in this spec?

**Decision to make:** decide whether the profile command ships `save NAME --from-current`, which reads the live state and writes one rule per group, or whether profiles are authored only from flags and the `init` template.

### Why decide this now
| Context | Effect on this decision |
|---|---|
| Profile outputs | In scope adds a flag and a state→rule heuristic that exists nowhere in the plan. |
| Discovery output | Its JSON shapes become a stable input API rather than output only. |
| Outside this decision | Syntax, directory, distribution. |

**Already settled:** the strict-verification decision forbids a capture that silently *snaps* an unmappable item to the nearest named value; the group-by-identifier decision is why capture cannot infer a title-based selector. Neither decides scope.

**Reversibility:** high — purely additive either way.

### A (Recommended): out of scope — author from flags or the template

```zsh
mytool profile init office
mytool profile save office --match bundle=com.example.editor --target index=1 --action maximize
```

**Pros:** Smallest surface; every rule intentional; no approximation.
**Cons:** About three lines of typing per context, once.

### B: in scope — `profile save office --from-current`

```yaml
rules:
  - match: {bundle: com.example.editor}
    target: {index: 1}
    action: maximize          # frame matched a named region
  - match: {bundle: com.example.chat}
    target: {index: 3}
    action: ???               # frame (120,80,1100,700) matches no named region
```

The last rule needs a defined behaviour, and choosing B means choosing one: `absolute` (new grammar), `snap` (contradicts strict verification), or `fail` (exit 1 naming the item).

**Pros:** Fastest first profile; nothing to memorise.
**Cons:** A heuristic with a defined failure mode; cannot infer title selectors.

**Recommendation:** choose A …

### TBD: answer without deciding
| Route | What happens next |
|---|---|
| `spike: <question>` | Prototype the mapping against the real state file and report how many items map to a named value. |
| `defer` or `handoff` | Same effect as A but recorded as a seam: "capture revisited after profiles ship". |
| … | … |

Your reasoning becomes ADR-CAPTURE's Why.

```text
Reply with A or B and your reasoning; picking B, also name <absolute|snap|fail>.
Alternatively choose from <explain|show|spike|defer|handoff|other|task> and your reasoning to revise/iterate.
```
````

## Shape-specific checks

- Exactly two lettered options in the reply footer.
- The sub-choice, if any, is named in the option's preview **and** in the
  footer's first line.
- `defer` is distinguished from the "out of scope" option.
