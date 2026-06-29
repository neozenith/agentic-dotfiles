---
name: cli
description: "Playbook for building and extending project-local developer CLIs and the recurring assets they generate, so the same patterns are never re-derived from scratch. Use when: scaffolding or adding a subcommand to a repo CLI (argparse/Typer, project-root discovery, packaged assets); generating a STATIC HTML single-page viewer (client-side SPA routing, collapsible sidebar, light/dark + rebrandable design-tokens theming, Cytoscape graph or Plotly chart, generate/serve, --inline single-file, --archive zip); templating GitHub Actions workflows from a base template (create/update/validate, trigger-path glob distillation, reusable composite-action assets); using git worktrees to act on another branch/ref safely; autogenerating SVG/PNG diagrams from a stencil pack; or automating sticky PR comments and embedding a CI-run artifact image in a PR comment. Skip for non-CLI app code, or one-off scripts with no reuse. Invoke as /cli or when the user names one of these patterns."
argument-hint: "[viewer | gha | worktree | diagrams | pr-comments | foundations] (default: route by intent)"
user-invocable: true
---

# Building project CLIs (and the assets they generate)

A field guide to the patterns that recur across project-local developer CLIs, so
you implement each **once, well** and re-skin/re-use it rather than re-deriving it.
Every pattern here is distilled from working implementations; the depth (with
copy-pasteable skeletons) lives in `resources/` — load the one you need.

## Route by intent

| You are about to… | Reach for | Resource |
|-------------------|-----------|----------|
| Scaffold a CLI / add a subcommand; find the project root; ship data files | the shared CLI skeleton | [resources/cli-foundations.md](resources/cli-foundations.md) |
| Generate a static HTML viewer (SPA, sidebar, themes, Cytoscape/Plotly, serve, inline, archive) | the static-SPA-viewer pattern | [resources/static-spa-viewer.md](resources/static-spa-viewer.md) |
| Create/update/validate a GitHub Actions workflow from a template; derive trigger `paths` | the GHA-templating pattern | [resources/gha-templating.md](resources/gha-templating.md) |
| Build an artifact from another branch/ref without disturbing the work tree | the git-worktree pattern | [resources/git-worktrees.md](resources/git-worktrees.md) |
| Autogenerate SVG + PNG diagrams from a stencil icon pack | the stencil-diagram pattern | [resources/svg-diagrams.md](resources/svg-diagrams.md) |
| Post/upsert a PR comment; embed a CI-run image artifact in a PR comment | the PR-comment pattern | [resources/pr-comments.md](resources/pr-comments.md) |

When a task spans several (e.g. "a CLI that generates a viewer and posts it to the
PR"), start at `cli-foundations.md` for the skeleton, then pull each feature
resource in turn.

## Non-negotiable conventions (apply to every pattern)

These hold across all the resources; they are the house contract a new CLI inherits.

- **Fail loud, never degrade.** A missing dependency, unresolved project root, or
  absent artifact raises with a clear message — never a silent skip or a fallback to
  a weaker path. (Optional features that are genuinely environmental — e.g. a
  best-effort metadata field — say so explicitly.)
- **Discover the project root; never assume cwd.** Explicit `--project-dir`/flag →
  env var → walk up for a sentinel file → fail loud. Resolve once, store it, pass it.
- **Ship data files as package data**, resolved via `importlib.resources` /
  `Path(__file__).parent`, never a cwd- or repo-relative path — so assets resolve
  identically from source and as an installed tool.
- **Output discipline:** human/log lines → **stderr**; the machine payload (`--json`,
  a resolved path) → **stdout** only. So `tool … --json | jq` and
  `X=$(tool print-path)` are always safe.
- **Temp/cache under the project's `tmp/`**, never the system `/tmp`, so artifacts are
  auditable and `git clean`-able.
- **`app.py`/entrypoint is wiring only** — no business logic; handlers live in
  `commands/`. Read-only subcommands use `status`/`validate`/`analyse`; generators use
  `create`/`generate`/`update`; destructive ones use imperative verbs.

## Quickstart

- **In Claude:** `/cli viewer` (or `gha`, `worktree`, `diagrams`, `pr-comments`) — or
  describe the goal ("add a `generate`/`serve` viewer to my CLI") and the matching
  resource is loaded and applied.
- **Direct:** open the resource for the pattern, copy its reference skeleton, adapt the
  generic names to your tool, and wire it per `cli-foundations.md`.
- **Re-skin instead of rebuild:** if a viewer already exists, you almost never fork the
  JS/HTML — edit `design-tokens.json` (palette/fonts/brand) and re-serve. See
  [static-spa-viewer.md](resources/static-spa-viewer.md) §theming.

## Maintaining this skill

See [CLAUDE.md](CLAUDE.md) for the decision lenses (why each pattern is shaped this way)
and the extension checklist. Keep every file ≤ 500 lines and brand-agnostic.
