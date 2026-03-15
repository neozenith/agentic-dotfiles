---
name: plans
description: "Manage hierarchical planning documents with token-budgeted lazy loading, automatic rebalancing, and cascading context injection. Use when working with large planning docs, splitting oversized plans, or loading plan hierarchies into context efficiently."
allowed-tools:
  - Read
  - Write
  - Bash(.claude/skills/plans/scripts/plan_manager.sh *)
user-invokable: true
---

# Hierarchical Planning Documents

Manage markdown planning documents with YAML frontmatter, token-budgeted lazy loading, and automatic rebalancing.

## Quick Start

```bash
# Add frontmatter metadata to a plan document
.claude/skills/plans/scripts/plan_manager.sh init docs/plans/my-plan.md

# Show section tree with token estimates
.claude/skills/plans/scripts/plan_manager.sh analyze docs/plans/my-plan.md

# Load cascading context from a plan hierarchy
.claude/skills/plans/scripts/plan_manager.sh context docs/plans/my-plan.md --depth 2

# Split oversized documents into children
.claude/skills/plans/scripts/plan_manager.sh rebalance docs/plans/my-plan.md --threshold 4000

# Update summary and token estimate metadata
.claude/skills/plans/scripts/plan_manager.sh update-summary docs/plans/my-plan.md --propagate
```

## Commands

### `init <file> [--title TITLE]`

Add YAML frontmatter to an existing markdown file. Auto-detects the title from the first heading and generates a heuristic summary. Preserves existing frontmatter values.

### `analyze <file> [-f tree|json]`

Parse a plan document and display its section tree with per-section and total token estimates. Validates the document as CommonMark using marko. Default output is a visual tree; use `-f json` for structured output.

### `context <file> [-d DEPTH] [--max-tokens N] [--summaries-only]`

Emit cascading context for a planning doc hierarchy. Controls how much of the hierarchy to load:

- **depth 0**: Root metadata only (~100-200 tokens)
- **depth 1** (default): Root body + child summaries (~500-2000 tokens)
- **depth 2+**: Recursively load child bodies and grandchild summaries
- **depth -1**: Unlimited depth (load entire tree)

The `--max-tokens` budget (default 8000) prevents overloading context.

Use `--summaries-only` to emit only frontmatter summaries (no document bodies) — useful for quick hierarchy inspection.

### `rebalance <file> [--threshold N] [--min-section N] [--dry-run]`

When a document exceeds the token threshold (default 4000), extract the largest sections into child markdown files. Each child gets its own frontmatter with summary, parent link, and token estimate. The parent section is replaced with a summary link.

Section extraction uses the marko AST to ensure splits never occur inside code fences. Both parent and child files are validated as valid CommonMark after the split.

Use `--dry-run` to preview without modifying files.

### `update-summary <file> [--propagate]`

Update the frontmatter `summary` and `token_estimate` fields using `claude -p` for AI-generated summaries. Requires the Claude Code CLI.

With `--propagate`, performs bidirectional tree traversal: recurses DOWN to all leaf children first, updates each summary from leaves up, then bubbles changes back to the root.

## Frontmatter Schema

Every plan document uses this YAML frontmatter:

```yaml
---
id: "uuid-v4"
title: "Document Title"
summary: "2-4 sentence summary for LLM context injection."
status: draft | active | complete | blocked
parent: "../parent.md"
children:
  - "./child-a.md"
  - "./child-b.md"
token_estimate: 4200
created: "ISO8601"
updated: "ISO8601"
tags: []
---
```

## Workflow

1. **Start**: Write a plan document, then `init` it to add frontmatter
2. **Grow**: As the plan grows, `analyze` to see which sections are largest
3. **Split**: When it gets too large, `rebalance` to extract sections into children
4. **Load**: Use `context` to get token-budgeted views of the hierarchy
5. **Maintain**: After edits, `update-summary --propagate` to keep metadata fresh
