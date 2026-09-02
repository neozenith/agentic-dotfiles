# Shape: low stakes

Part of `concise-decisions` ([../../SKILL.md](../../SKILL.md) step 4). Load
when the decision is highly reversible and nothing downstream depends on it,
**but** the user's lens is still worth recording — a convention they will
want reused (paths, naming, defaults).

## Recognise it

- Reversibility is high: a rename, a `mv`, an env-var default.
- No other open decision cascades from it.
- It *almost* passes the pragmatic-default test, except that no recorded
  lens points the way yet — and the answer will become one.

If all four pragmatic-default criteria hold, do not use this shape: state
the default in one line and move on.

## Anatomy — one delta from the base

**Previews shrink to the value; sections do not.** When each option *is* a
path, a key name, or a one-line default, that value is the complete preview.
Say so in the body ("low stakes, so each option's path is its preview").

Every other section stays: decision sentence, why now, already settled,
reversibility, pros/cons per option, compare, recommendation, TBD, answer
channel.

## The failure this shape exists to prevent

The first rehearsal of a low-stakes question tried a *compressed* form: no
decision sentence, no "already settled", a feature grid instead of options,
and picker labels that pointed into the body (`Confirm C`, `Veto → A`). The
user saw the picker with no visible context and could not tell what was being
asked. The second attempt kept the full anatomy with one-line previews and
passed. Lesson: **there is no cheap question**; cheapness lives in the
previews only.

## Worked example (generic)

Where a CLI writes its saved profiles, and what may override the location.

````markdown
## ADR-DIR — where profile files live

**Decision to make:** choose the directory that `mytool profile save office` writes `office.yaml` into, including which environment variables may override it.

### Why decide this now
| Context | Effect on this decision |
|---|---|
| Implementation | `internal/profile/dir.go` needs one deterministic resolution rule. |
| Diagnostics | `mytool doctor` must print the resolved directory. |
| Why this one first | Nothing else queued depends on it; it is asked now only because `doctor` and `dir.go` are the next files to write. |
| Outside this decision | Profile contents, syntax, distribution. |

**Already settled:** Checked `docs/adrs/` and `CLAUDE.md`. The file-format decision fixes the YAML library but not a location. The user's CLI configs are managed through dotfiles under `~/.config`, but no record states that preference — which is why this is asked rather than defaulted.

**Reversibility:** high. Moving YAML files between these directories is mechanical; the recommended chain carries its own override.

Low stakes, so each option's path is its preview.

### A: always `~/.config/mytool`

```text
~/.config/mytool/profiles/office.yaml
```

**Pros:** Minimal code; dotfiles-friendly.
**Cons:** Ignores `XDG_CONFIG_HOME`; no per-machine override.

### B: the platform's documented config directory

```text
~/Library/Application Support/mytool/profiles/office.yaml
```

**Pros:** Matches the language runtime's documented platform default.
**Cons:** A space in the path; outside the dotfiles layout; the runtime ignores `XDG_CONFIG_HOME` on this platform anyway.

### C (Recommended): environment chain

```text
$MYTOOL_HOME/profiles/office.yaml
  or $XDG_CONFIG_HOME/mytool/profiles/office.yaml
  or ~/.config/mytool/profiles/office.yaml        (doctor prints the winner)
```

**Pros:** Dotfiles-friendly default; honours XDG; a machine-specific root.
**Cons:** Two extra environment checks; differs from the platform default.

### Compare
| Option | Dotfiles-friendly | Honours XDG | Machine override | Platform default |
|---|---|---|---|---|
| A | yes | no | no | no |
| B | awkward | no | no | yes |
| C | yes | yes | yes | no |

**Recommendation:** choose C — A plus two overrides, at little cost.

### TBD: answer without deciding
| Route | What happens next |
|---|---|
| `explain: <part>` | Expand the platform or environment-variable behaviour and ask again. |
| `show` | Not useful for a path-only decision. |
| `spike: <question>` | Inspect the user's other dotfiles-managed CLIs and report their actual rules. |
| `defer` or `handoff` | Use C provisionally; record the seam. |
| `other: <chain>` | Render the proposed order and ask again. |

Your reasoning — a phrase like "dotfiles over platform convention" — becomes the lens reused for every future path/config question.

```text
Reply with A, B or C and your reasoning.
Alternatively choose from <explain|show|spike|defer|handoff|other|task> and your reasoning to revise/iterate.
```
````

## Shape-specific checks

- The body says "low stakes" and why (reversibility line).
- Previews are the value itself, nothing less.
- The answer-channel line says what class of future question the lens will
  settle — that is the whole reason this question is being asked rather than
  defaulted.
