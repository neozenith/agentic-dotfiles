# Evals

Live agent evals for this skill, run by the
[`pytest-xharness-eval`](https://github.com/neozenith/pytest-xharness-eval) pytest plugin.
Each case runs the `claude` and `codex` CLIs headlessly against a fixture workspace,
then grades what the agent left behind.

The plugin is a dev dependency of this repository, so `uv run pytest` picks it up.

| Path | What it checks |
|------|----------------|
| `eval_palette_mandate.py` | Theming a four-node flowchart, compared facet by facet against a golden |
| `eval_dual_density.py` | Splitting a 46-node diagram into overview and detail, graded by the skill's own gates |
| `fixtures/<name>/` | The seed workspace each cell starts from |
| `goldens/<name>/` | Known-good output. See [`goldens/README.md`](goldens/README.md) |

## Prerequisites

- `claude` and `codex` on your `PATH`, each logged in.
- The gate scripts' Bun dependencies: `make -C skills/mermaidjs-diagrams/scripts install-ts`.

## Run

Run from the repository root.
A bare `pytest` never collects these, so the path is required.

Preview the matrix first. Nothing is invoked and nothing is billed:

```sh
uv run pytest skills/mermaidjs-diagrams/evals --dry-run
```

Then run it live. **Every cell is a billed agent session.**

```sh
uv run pytest skills/mermaidjs-diagrams/evals -v
```

Narrow the spend with `--harness claude|codex`, `--model <substring>`, or `-k <expr>`.
Session logs and a browsable report land in `.xharness_eval_cache/` at the repository root, which is git-ignored.

## Run in parallel

Cells run one at a time by default.
Add [`pytest-xdist`](https://pytest-xdist.readthedocs.io/) and pass `-n <workers>` to run several at once:

```sh
uv run --with pytest-xdist==3.8.0 pytest skills/mermaidjs-diagrams/evals -v -n auto
```
