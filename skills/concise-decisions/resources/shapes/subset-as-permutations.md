# Shape: subset as permutations

Part of `concise-decisions` ([../../SKILL.md](../../SKILL.md) step 4). Load
when the options **compose** — several can be chosen together — and a naive
question would be a multi-select.

## Recognise it

- "Which of these should we support?" — install channels, export formats,
  auth providers, notification sinks.
- Choosing one option does not exclude the others, or excludes only some.
- The tempting answer surface is a checkbox list. **Do not use one**: a
  multi-select lets the user pick a subset but gives no way to say *why per
  option*, and the why is the product.

## Anatomy — two deltas from the base

1. **Atomic options first.** Before the options, add a table that says what
   each individual thing *is*: what the user runs or sees, what it needs,
   what it costs per use or per release. State exclusions ("W and X are
   mutually exclusive; Y and Z compose with either"). This table exists
   because, when the atomic facts are only visible inside the blended
   combinations, the reader loses track of what each ingredient is.
2. **Options are combinations**, titled by their members (`A (Recommended):
   W + Y + Z`), 2–3 realistic ones. Previews, pros, and cons sit at the
   combination tier. The answer is one combination.

Everything else — decision sentence, why now, already settled,
reversibility, compare, recommendation, TBD, answer channel — is unchanged.

## Worked example (generic, abridged)

A CLI must be installable on machines without an app store or a developer
account; channels: a prebuilt package-manager formula (W), a source-build
formula (X), a language-toolchain install (Y), committed per-architecture
binaries (Z).

````markdown
## ADR-DIST — distribution channels for `mytool`

**Decision to make:** choose which combination of install channels the release process supports for a client machine with no app store, no developer account, and possibly no build toolchain.

### Why decide this now
| Context | Effect on this decision |
|---|---|
| Release targets | Whether a formula file and a tap repository exist, and which `make` targets are real. |
| Diagnostics | Whether the quarantine check in `mytool doctor` is load-bearing. |
| Install runbook | One section per supported channel. |
| Outside this decision | CLI grammar, config format, config directory. |

**Already settled:** the no-daemon decision means no channel needs a signing certificate; the static-build decision means every channel can cross-compile from `make`. Neither says *which* channels to ship.

**Reversibility:** asymmetric — adding a channel later is cheap; removing one breaks whoever installed through it.

### The individual channels (what each one IS)

| Channel | Client runs | Needs | Release step |
|---|---|---|---|
| **W** prebuilt formula | `pkg tap org/tap && pkg install mytool` | package manager | build, checksum, bump formula, push tap |
| **X** source-build formula | same command; the manager installs the toolchain and compiles | package manager + toolchain download | tag + checksum bump |
| **Y** toolchain install | `lang install example.org/mytool@latest` | the language toolchain | nothing beyond the tag |
| **Z** committed binaries | download from the repo, clear the quarantine attribute | a browser | build + commit |

W and X are mutually exclusive (one formula). Y and Z compose with either.

### A (Recommended): W + Y + Z
<complete preview: client commands for each member, then the release commands>
**Pros:** …  **Cons:** …

### B: X
<complete preview>
**Pros:** …  **Cons:** …

### C: Y + Z
<complete preview>
**Pros:** …  **Cons:** …

### Compare
| Combination | Client needs | Upgrade path | Release cost |
|---|---|---|---|
| A | manager *or* toolchain | yes | formula bump per release |
| B | manager + toolchain download | yes | checksum bump |
| C | toolchain, or browser + attribute removal | no | build + commit |

**Recommendation:** choose A …

### TBD: answer without deciding
| Route | What happens next |
|---|---|
| `explain: <part>` | … |
| `show` | Not useful here — the commands are the artifact. |
| `spike: <question>` | Create the tap and time a cold install on this machine. |
| `defer` or `handoff` | Ship C now (no new repository); revisit the formula when a client install happens. |
| `other: <channels>` | e.g. an installer package or a version manager; render the combination and ask again. |

Reply … (reply footer, per the template)
````

## Shape-specific checks

- The atomic table appears **before** any combination.
- Exclusions between atomic options are stated, so the combinations offered
  are visibly the realistic ones, not an arbitrary three.
- Pros/cons live at the combination tier only; the atomic table carries
  facts, not opinions.
- The reply footer expects **one** combination letter, never a list.
