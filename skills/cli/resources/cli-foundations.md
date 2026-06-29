# CLI foundations — the shared skeleton

Part of the **cli** skill ([SKILL.md](../SKILL.md)). The base every other pattern
sits on: argument wiring, project-root discovery, packaged assets, output discipline.
Siblings: [static-spa-viewer](static-spa-viewer.md), [gha-templating](gha-templating.md),
[git-worktrees](git-worktrees.md), [svg-diagrams](svg-diagrams.md),
[pr-comments](pr-comments.md).

## Library choice

`argparse` (stdlib) is the default — zero deps, and the `_help`-closure pattern below
covers subcommands cleanly. `Typer` is a fine alternative when you want declarative
decorators and rich `--help`; the command *shape* (generate/serve/status verbs, the
dispatch, root discovery) is identical either way. Pick one per CLI and stay with it.

## The argparse skeleton

`app.py` is wiring + `main()` only — **no business logic** (handlers live in
`commands/`). Three load-bearing moves:

1. A `common` parent parser holds global flags with **`default=argparse.SUPPRESS`**, so
   a flag works *before or after* the subcommand and an unset occurrence on the
   subparser never clobbers a value parsed at the top level.
2. Each parser's default `func` is a `_help` closure that prints *that* parser's help —
   so an incomplete path (`tool group`) prints help instead of erroring.
3. `main()` dispatches `args.func(args)` unconditionally; leaves override `func`.

```python
import argparse, logging, sys

def _help(p):                                    # default func: print THIS parser's help
    def run(_): p.print_help(); return 0
    return run

def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--debug", action="store_true", default=argparse.SUPPRESS)
    common.add_argument("--project-dir", default=argparse.SUPPRESS)
    p = argparse.ArgumentParser(prog="tool", parents=[common])
    p.set_defaults(func=_help(p))
    sub = p.add_subparsers(dest="command", required=False)

    gen = sub.add_parser("generate", parents=[common]); gen.set_defaults(func=cmd_generate)
    st  = sub.add_parser("status",   parents=[common]); st.set_defaults(func=cmd_status)
    return p

def main(argv=None):
    args = build_parser().parse_args(argv)
    args.debug = getattr(args, "debug", False)   # normalise the SUPPRESS-maybe-absent attrs
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, stream=sys.stderr)
    try:
        rc = args.func(args)
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        logging.error("❌ %s", exc); raise SystemExit(1) from exc
    raise SystemExit(rc or 0)
```

**Handler factory for repetitive subcommands.** When N leaves differ only by a name,
close over it so each gets its own `func` (avoids a late-binding loop bug):

```python
def _add_action(sub, common, name):
    leaf = sub.add_parser(name, parents=[common])
    leaf.set_defaults(func=lambda a, _n=name: run_action(_n, a))
```

## Project-root discovery — never assume cwd

A CLI installed as a tool runs from anywhere. Resolve the root with a fixed precedence
and **fail loud** — never silently fall back to cwd:

```python
def resolve_root(override=None, *, sentinel="pyproject.toml", env="TOOL_PROJECT_DIR"):
    cand = override or os.environ.get(env)
    if cand:
        root = Path(cand).expanduser().resolve()
        if not (root / sentinel).exists():
            raise RuntimeError(f"--project-dir/{env} '{root}' has no {sentinel}")
        return root
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / sentinel).exists():
            return d
    raise RuntimeError(f"no {sentinel} in --project-dir, ${env}, cwd ({here}), or any parent")
```

Resolve once in `main()` for the commands that need it, store it on a module/config
holder, and pass an explicit `cwd`/`root` into pure logic so it stays unit-testable.
A repo with two roots (e.g. a tool root *and* the git root) resolves each independently
(git root via `git rev-parse --show-toplevel`).

## Packaged assets — `importlib.resources`, not cwd-relative

Templates, viewer HTML/JS, design tokens, base workflows — anything non-`.py` the tool
ships — must resolve identically from source and when installed. Bundle it as package
data and read it package-relative, **never** by a path relative to cwd or the repo root
(that breaks the instant the tool is installed globally).

```toml
# pyproject.toml — hatchling ships every file under the package into the wheel
[tool.hatch.build.targets.wheel]
packages = ["src/tool"]
```

```python
from importlib.resources import files
TEMPLATE = files("tool").joinpath("assets/workflow-template.yml")   # installed-safe
ASSETS   = Path(__file__).resolve().parent / "assets"              # dev-tree equivalent
```

## Output discipline

`logging` (→ stderr) for everything human; **stdout carries only the machine payload**.
This is what makes a CLI composable:

```python
import json, sys
def emit(report, *, as_json):
    if as_json:
        json.dump(report.to_dict(), sys.stdout)      # ONLY this on stdout
    else:
        for line in report.human_lines(): print(line, file=sys.stderr)
    return 0 if report.ok else 1
```

A command that prints a resolved path for `X=$(tool defer-state …)` prints **only**
that path to stdout; all progress goes to stderr.

## Verb convention

- Read-only / inspection → `status`, `validate`, `analyse`, `list`.
- Generators → `generate`, `create`, `update`.
- Long-running host → `serve`.
- Destructive / state-changing → imperative (`reset`, `init`, `set`).
- A mutation is **opt-in** (`--fix`), never the default; a dry-run that prints the exact
  command instead of running it (`--commands`) is cheap and trust-building.

## Module layout

```
src/tool/
├── app.py            # build_parser() + main(); wiring only
├── __main__.py       # `python -m tool`
├── config.py         # root discovery, default paths, packaged-asset locations
├── commands/         # one module per command group; the handlers + evaluation logic
├── assets/           # packaged data (templates, viewer html/js, design-tokens.json)
└── <domain>.py       # pure logic, no argparse/IO coupling — unit-testable
```

## Pitfalls

- **The `SUPPRESS` trick is the non-obvious bit.** Without it, `tool --debug sub` loses
  `--debug` (the subparser's unset default overwrites the top-level value).
- **Discovery must fail loud.** Defaulting to cwd "to be helpful" produces baffling
  wrong-project runs; raise a typed error naming what was tried.
- **Never read assets cwd-relative.** It works in dev and breaks on install — the single
  most common reason a packaged CLI "can't find its template".
- **Keep pure logic free of `argparse`/`print`.** Pass `cwd`/flags in; return data; let a
  thin handler render. It is the difference between testable and not.
