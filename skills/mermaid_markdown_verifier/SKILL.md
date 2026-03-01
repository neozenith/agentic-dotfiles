---
name: mermaid-markdown-verifier
description: "Verify Mermaid diagrams embedded in Markdown files. Extracts mermaid code fence snippets, renders each via mermaid-cli (mmdc), and outputs a JSON report of pass/fail status with error details. Use when checking documentation for broken Mermaid diagrams, auditing a docs directory, or confirming a diagram renders correctly after edits."
argument-hint: "[markdown-files-or-glob-or-directory...]"
allowed-tools:
  - Bash
  - Read
  - Glob
user-invocable: true
---

# Mermaid Markdown Verifier

Verify that Mermaid diagrams embedded in Markdown files render correctly using mermaid-cli (`mmdc`).

## When to Use

- After writing or modifying Mermaid diagrams in documentation
- Before committing documentation changes that include diagrams
- To audit all diagrams in a docs directory for render errors
- When a CI check reports a broken Mermaid diagram

## Requirements

Node.js and `npx` must be available. The `@mermaid-js/mermaid-cli` package is fetched automatically via `npx -p @mermaid-js/mermaid-cli`.

## Workflow

### Step 1: Run the Verifier

Run the script on the target files and capture the JSON report:

```bash
uv run .claude/skills/mermaid_markdown_verifier/scripts/mermaid_markdown_verifier.py docs/ -v
```

For a single file:

```bash
uv run .claude/skills/mermaid_markdown_verifier/scripts/mermaid_markdown_verifier.py docs/plans/kg/00_gap_analysis.md
```

For a glob pattern (quote to prevent shell expansion):

```bash
uv run .claude/skills/mermaid_markdown_verifier/scripts/mermaid_markdown_verifier.py "docs/**/*.md"
```

### Step 2: Parse the JSON Report

The script always outputs JSON to stdout. Read the `summary` first:

- `total_snippets`: Total mermaid code fences found
- `passed`: Count that rendered successfully
- `failed`: Count that failed (these need fixing)
- `files_scanned`: Unique source files with at least one mermaid snippet

### Step 3: Fix Broken Diagrams

For each result where `"success": false`:

1. Open the file at `file_path`
2. Navigate to `line_start` through `line_end` (the code fence range)
3. Inspect the `stderr` field for the mermaid-cli error message
4. Fix the Mermaid syntax
5. Re-run the verifier to confirm the fix

### Step 4: Confirm All Pass

Re-run and verify `"failed": 0` in the summary before completing.

## Output Format

Always outputs JSON to stdout:

```json
{
  "summary": {
    "total_snippets": 3,
    "passed": 2,
    "failed": 1,
    "files_scanned": 2
  },
  "results": [
    {
      "slug": "00_gap_analysis_md__a3f7b2c1d2e3__L45_L68",
      "file_path": "/absolute/path/to/docs/plans/kg/00_gap_analysis.md",
      "line_start": 45,
      "line_end": 68,
      "content": "graph TD\n    A --> B",
      "success": true,
      "exit_code": 0,
      "stdout": "",
      "stderr": "",
      "png_path": "/tmp/tmpXXXXXX/00_gap_analysis_md__a3f7b2c1d2e3__L45_L68.png"
    },
    {
      "slug": "readme_md__b4e8c9f1a2b3__L12_L20",
      "file_path": "/absolute/path/to/README.md",
      "line_start": 12,
      "line_end": 20,
      "content": "graph TD\n    BAD SYNTAX",
      "success": false,
      "exit_code": 1,
      "stdout": "",
      "stderr": "Error: ...",
      "png_path": null
    }
  ]
}
```

## Slug Format

Each snippet gets a unique slug composed of:
- The markdown filename (human-readable, non-alphanumeric chars → underscores)
- A 12-character SHA-1 hash of the absolute file path (guarantees uniqueness across files with the same name in different directories)
- The line numbers of the opening and closing ` ```mermaid ` fences

Example: `00_gap_analysis_md__a3f7b2c1d2e3__L45_L68`

## Exit Codes

- `0`: All diagrams rendered successfully (or no diagrams found)
- `1`: One or more diagrams failed to render

## CLI Quick Reference

```bash
# Single file
uv run .claude/skills/mermaid_markdown_verifier/scripts/mermaid_markdown_verifier.py path/to/file.md

# Directory (recursive scan)
uv run .claude/skills/mermaid_markdown_verifier/scripts/mermaid_markdown_verifier.py docs/

# Glob pattern (quote to prevent shell expansion)
uv run .claude/skills/mermaid_markdown_verifier/scripts/mermaid_markdown_verifier.py "docs/plans/**/*.md"

# Multiple paths
uv run .claude/skills/mermaid_markdown_verifier/scripts/mermaid_markdown_verifier.py README.md docs/plans/

# Verbose mode (shows per-snippet progress)
uv run .claude/skills/mermaid_markdown_verifier/scripts/mermaid_markdown_verifier.py docs/ -v

# Quiet mode (suppress info/debug, errors only)
uv run .claude/skills/mermaid_markdown_verifier/scripts/mermaid_markdown_verifier.py docs/ -q
```
