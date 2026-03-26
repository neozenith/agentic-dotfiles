# GitHub CLI (`gh`) Reference for Gap Analysis

Reference for using the `gh` CLI to interact with GitHub issues as a storage backend
for gap analysis documents. Covers availability detection, key commands, and important
behavioral notes.

## Availability Detection

Before attempting GitHub issue operations, verify `gh` is installed and authenticated:

```bash
which gh && gh --version && gh auth status
```

| Check | Pass | Fail |
|-------|------|------|
| `which gh` | Path printed | Command not found |
| `gh --version` | Version printed (e.g., `2.87.2`) | — |
| `gh auth status` | Shows `Logged in` + `repo` scope | Not logged in or missing `repo` scope |

**All three must pass.** The `repo` scope is required for issue create/edit/comment
operations. If authentication fails, instruct the user to run:

```bash
gh auth login
```

## Core Commands

### Create an issue

```bash
gh issue create \
  --repo owner/repo \
  --title "Gap Analysis: Initiative Title" \
  --body "$(cat <<'EOF'
## Overview
...
EOF
)"
```

Returns the issue URL (e.g., `https://github.com/owner/repo/issues/42`).

### Read an issue

```bash
# Structured JSON — use for programmatic access
gh issue view 42 --repo owner/repo \
  --json number,title,body,state,labels,comments

# Human-readable markdown
gh issue view 42 --repo owner/repo
```

The `--json` form is preferred — it returns the full body as a JSON string field,
making it safe to parse even when the body contains markdown formatting.

### Edit an issue (title and/or body)

```bash
gh issue edit 42 --repo owner/repo \
  --title "Updated Title" \
  --body "$(cat <<'EOF'
Full replacement body here.
EOF
)"
```

**CRITICAL: `--body` performs a FULL REPLACEMENT**, not an append or patch. To make
a targeted edit:

1. Read the current body via `gh issue view --json body`
2. Modify the relevant section
3. Write the entire body back via `gh issue edit --body`

This is the same read-modify-write pattern as editing a markdown file.

### Add a comment

```bash
gh issue comment 42 --repo owner/repo \
  --body "Comment text here."
```

Comments are **append-only** — they cannot be edited or deleted via `gh`. Use comments
for refinement Q&A, status updates, and iteration history. They provide a natural
audit trail of the planning conversation.

### Manage labels

```bash
# List available labels on a repo
gh label list --repo owner/repo --json name

# Add a label (must already exist on the repo)
gh issue edit 42 --repo owner/repo --add-label "enhancement"

# Remove a label
gh issue edit 42 --repo owner/repo --remove-label "enhancement"
```

**Labels must pre-exist on the repository.** Attempting to add a non-existent label
produces an error. Check available labels first with `gh label list`.

### Close an issue

```bash
gh issue close 42 --repo owner/repo \
  --comment "Gap analysis complete. See final state in issue body."
```

### Reopen an issue

```bash
gh issue reopen 42 --repo owner/repo
```

## Behavioral Notes

| Behavior | Detail |
|----------|--------|
| Body replacement | `gh issue edit --body` replaces the entire body — never appends |
| Body size limit | GitHub issues support up to ~65,536 characters in the body |
| Mermaid rendering | ` ```mermaid ` fences render natively in GitHub — no mmdc needed |
| HTML comments | `<!-- ... -->` comments are preserved in the body but hidden in rendered view |
| HEREDOC for body | Always use `"$(cat <<'EOF' ... EOF)"` to pass multi-line bodies safely |
| Rate limits | GitHub API has rate limits (~5,000 requests/hour for authenticated users) |

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `'label-name' not found` | Label does not exist on repo | Use `gh label list` to check available labels |
| `HTTP 403` | Insufficient token scope | Re-authenticate with `gh auth login` |
| `HTTP 404` | Repo not found or private without access | Verify repo name and permissions |
| `HTTP 422` | Invalid request (e.g., empty title) | Check required fields |
