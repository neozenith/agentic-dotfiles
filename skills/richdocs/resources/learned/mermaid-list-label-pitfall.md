# Learned: flowchart node labels must not start with list markers (`1. `, `- `)

- **Date:** 2026-07-23
- **Case:** a flowchart node authored as `S1["1. Renumber ADRs<br/>..."]`
  rendered as **"Unsupported Markdown: list"** in the HTML companion instead
  of the label text.
- **Root cause:** the pinned mermaid (`11.4.1`, see the CDN table in
  `scripts/md2html.py`) treats EVERY flowchart label as markdown — a v11.0.0
  regression (mermaid-js/mermaid issue #5824). A label whose text begins with
  a list marker (`1. `, `2. `, `- `, `* `, `+ `) lexes as a markdown list,
  which mermaid's label renderer does not support, so it prints the error
  string as the label. This happens at parse-of-label time, in both
  `htmlLabels` modes — **no `mermaid.initialize` option in 11.4.1 avoids
  it** (`htmlLabels`, `markdownAutoWrap`, `securityLevel` were all checked;
  none gate the markdown lexing of plain labels).
- **Upstream status:** fixed by mermaid PR #7276 (merged 2026-02-27, after
  11.4.1): plain labels stop being markdown; only backtick strings
  (`["`**md**`"]`) opt in. A renderer-level fix here therefore means bumping
  the pinned mermaid to a release containing #7276 — do that only with the
  full browser re-verification the CLAUDE.md extension checklist demands
  (the `foreignObject` clipping behaviour was tuned against 11.4.1).
- **Authoring fix (use this):** never start a node/edge label with
  `digits.` + space or `-`/`*`/`+` + space. Rewrite `"1. Renumber ADRs"` as
  `"Step 1: Renumber ADRs"` / `"1) Renumber ADRs"`, or break the marker with
  an HTML entity: `"1&#46; Renumber ADRs"` (entities render fine in
  flowchart htmlLabels — the mindmap entity trap in
  `mermaid-syntax-gate.md` is mindmap-specific).
- **Gate note:** the vendored parse gate
  (`vendor/mermaidjs_diagrams/scripts/mermaid_complexity.ts`) does NOT catch
  this — the fence parses fine; only label *rendering* fails. The vendored
  copy is refreshed wholesale (ADR-007, never cherry-pick), so the check was
  not patched locally; if the upstream `mermaidjs_diagrams` skill grows a
  list-marker label lint, it arrives here on the next re-vendor. Until then
  this file and the CLAUDE.md gotcha are the guard: grep the source fences
  for `["'\`]\s*(\d+\.|[-*+]) ` before handoff.
