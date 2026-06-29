# GitHub Actions workflow templating

Part of the **cli** skill ([SKILL.md](../SKILL.md)). Generate / update / validate
per-slice GitHub Actions workflows from a CLI-owned base template, with trigger `paths`
**derived** from the slice's membership. Builds on [cli-foundations.md](cli-foundations.md);
the base template is a packaged asset (see that file's §packaged-assets).

## Two templating flavours — pick by who owns the file

| | One-shot stamp | Round-trip create/update |
|--|----------------|--------------------------|
| Tool | Jinja2 | ruamel.yaml |
| Owns the file? | the tool owns it outright | humans co-edit it |
| `update`? | re-generate wholesale | re-derive **only one block**, keep hand-edits |
| Comments | n/a | **preserved** |

**Flavour A — Jinja one-shot** (the tool owns the whole file; regeneration = re-run):

```python
from jinja2 import Environment, StrictUndefined
from importlib.resources import files
tpl = files("tool").joinpath("templates/workflow.yml.j2").read_text()
out = Environment(undefined=StrictUndefined).from_string(tpl).render(slice_name=name)
```

`StrictUndefined` fails loud on a missing token (never a silently-blank field). In the
template, wrap GitHub's own `${{ … }}` in `{% raw %}…{% endraw %}` so Jinja leaves it
alone.

**Flavour B — ruamel round-trip** (humans co-edit; `update` is surgical):

```python
from ruamel.yaml import YAML
yaml = YAML(); yaml.preserve_quotes = True              # keeps comments + quotes
data = yaml.load(path.read_text())                      # template (create) | existing (update)
on_key = "on" if "on" in data else True                 # YAML 1.1 bare-`on:` parses as boolean True
if creating:
    data["name"] = f"Workflow - {slice}"
    data["env"]["SELECTOR"] = slice
data[on_key]["pull_request"]["paths"] = derived_globs    # update touches ONLY this block
with path.open("w") as fh: yaml.dump(data, fh)
```

The three subcommands:

- **`create`** — clone the template, swap the slice tokens (`name`, `env`, the job name,
  the `paths`). Under `--all`, **skip** files that already exist (don't clobber
  hand-edits) and point the user at `update`; a single `create` without `--force` on an
  existing file fails loud.
- **`update`** — re-derive **only** the `on.pull_request.paths` block from current
  membership; every other hand-edit is untouched. This is the whole reason for ruamel.
- **`validate` / `analyse`** — read-only: confirm the file parses / tabulate the
  glob-collapse cost (below). Writes nothing.

## Trigger-path glob distillation — three algorithms

**Problem:** collapse N discovered files into a short `on.pull_request.paths` list. The
safety invariant: **over-match only over-triggers CI (harmless); under-match misses a
changed file (unsafe)** — every algorithm must be over-match-safe.

- **`strict`** — the file list verbatim. Zero false positives, longest list.
- **`leaf`** — collapse the filename per directory → `<dir>/*.{ext1,ext2}`. Catches
  sibling files in the same dir.
- **`recursive`** (default) — merge directories that differ in exactly one path
  component into a `**` wildcard (to a fixpoint), then drop any dir already covered by a
  shorter `prefix/**`. Shortest list, widest over-match.

```python
PATH_MODES = ("strict", "leaf", "recursive")
def discover_to_globs(paths: set[str], mode: str) -> list[str]:
    if mode not in PATH_MODES: raise ValueError(f"unknown mode {mode!r}")   # no silent fallback
    if mode == "strict": return sorted(paths)
    if mode == "leaf":   return sorted(f"{d}/*.{{sql,yml}}" for d in _dirs(paths))
    return sorted(f"{'/'.join(d)}/**" for d in _subsume(_wildcard_merge(_dirs(paths))))
```

**False-positive audit** — compile each glob to an anchored regex and report which files
in the universe a mode would *also* fire on (matched − canonical-strict-set), so a human
judges the over-match before committing the mode:

```python
def glob_to_regex(g):                       # **/ → (?:.*/)? ; ** → .* ; * → [^/]* ; {a,b} → (?:a|b)
    ...                                      # anchored ^…$
def false_positives(globs, universe, canonical):
    rx = [glob_to_regex(g) for g in globs]
    return {f for f in universe if any(r.match(f) for r in rx)} - canonical
```

`analyse` prints, per mode: true members, glob count, files matched, false-positive count
+ rate — a TUI table so the trade-off is visible. Always emit the audit; never hide the
over-match.

## Deriving the membership

The `paths` come from the slice itself, not a hand-kept list — e.g. resolve the slice's
files (a query/selector), optionally add the repo helpers those files depend on, then
collapse:

```python
discovered = resolve_slice_files(slice)            # the source of truth for membership
globs = discover_to_globs(discovered, mode) + ["<repo-config-file>"]  # + always-trigger statics
fps = false_positives(globs, universe(root), canonical=discovered)    # audit
```

## Curating reusable GHA assets

The CLI **owns** a canonical base under `src/tool/assets/` (or `templates/`), shipped as
package data (see [cli-foundations.md](cli-foundations.md) §packaged-assets). The
**generated workflow is a thin caller**, not a copy of the logic — it `uses:` a shared
reusable workflow / composite action (or calls the CLI itself, e.g.
`uv run … tool check`). One place to fix the real steps; the per-slice files only carry
the trigger + a few env tokens.

```
src/tool/assets/workflow-template.yml      # the owned base (packaged)
.github/workflows/reusable-*.yml           # the shared logic the generated files call
.github/actions/<name>/action.yml          # composite actions the reusable workflow uses
```

## Pitfalls

- **YAML 1.1 bare `on:` → boolean `True`.** Always normalise the key
  (`"on" if "on" in data else True`) before indexing, or the `paths` write silently
  lands under the wrong key.
- **Jinja vs GitHub `${{ }}`** — guard GitHub expressions with `{% raw %}`; use
  `StrictUndefined` so a missing token errors instead of rendering blank.
- **`update` must touch only `paths`.** Re-stamping the whole file on update destroys
  hand-edits — the round-trip exists precisely to avoid that.
- **Hardcoded `paths:` under-match.** A static path list goes stale as files move and
  silently stops triggering; derive from membership + run the fp audit instead.
- **Unknown `--paths` mode raises** — no silent fallback to a default algorithm; the
  caller chose a mode for a reason.
