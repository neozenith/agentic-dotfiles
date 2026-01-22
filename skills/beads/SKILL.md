---
name: beads
description: Distributed, git-backed issue tracking designed for AI agents. Use for persistent task management across sessions, dependency-aware work planning with `bd ready`, and structured project tracking. Replaces ephemeral todo lists with durable, versioned issue graphs.
allowed-tools:
  - Bash(bd *)
  - Read
  - Glob
user-invocable: true
---

# Beads: AI-Native Issue Tracking

Beads is a **distributed, git-backed issue tracker with DAG-based dependencies** designed specifically for AI coding agents. It provides persistent memory across sessions, dependency-aware work queues, and merge-conflict-resistant collaboration.

**Repository:** [github.com/steveyegge/beads](https://github.com/steveyegge/beads)

## Why Beads for AI Agents?

| Problem | Beads Solution |
|---------|----------------|
| TodoWrite items lost between sessions | Issues persist in `.beads/issues.jsonl` (git-tracked) |
| No dependency tracking | DAG structure with `bd dep add child parent` |
| What should I work on next? | `bd ready` shows unblocked tasks by priority |
| Context window limits | Closed issues summarized, active context preserved |
| Multi-branch conflicts | Hash-based IDs (`bd-a3f8`) prevent collisions |

## Quick Start for Sessions

```bash
# Start of session: What's actionable?
bd ready

# Pick a task and start working
bd update <issue-id> --status in_progress

# While working: add notes
bd comments add <issue-id> "Found edge case with token refresh"

# Task complete
bd close <issue-id> --reason "Implemented in commit abc123"

# Need to add a new task discovered during work?
bd create "Handle expired token edge case" --parent <epic-id>
```

## Essential Commands

### Viewing Issues

```bash
# List all open issues
bd list

# Show issue details
bd show <issue-id>

# What's ready to work on? (no blockers, sorted by priority)
bd ready

# View dependency graph
bd graph <issue-id>

# Database overview
bd status
```

### Creating Issues

```bash
# Simple task
bd create "Fix authentication bug"

# Task with priority (0=highest, 4=lowest)
bd create "Critical security fix" -p 0

# Task as child of epic
bd create "Implement rate limiting" --parent bd-epic-id

# Epic (container for related tasks)
bd create "v2.0 Release" -t epic

# With description
bd create "Add error boundary" -d "Graceful error handling with user-friendly messages"
```

### Managing Status

```bash
# Start working
bd update <id> --status in_progress

# Mark complete
bd close <id> --reason "Merged in PR #42"

# Block/unblock
bd update <id> --status blocked
bd update <id> --status open

# Reopen if needed
bd reopen <id>
```

### Dependencies

```bash
# Add blocking dependency (child depends on parent)
bd dep add <child-id> <parent-id>

# Remove dependency
bd dep remove <child-id> <parent-id>

# View what blocks an issue
bd show <id>  # Shows dependencies section
```

## Issue Types

| Type | Use Case | Example |
|------|----------|---------|
| `task` | Concrete work item | "Add login button" |
| `epic` | Container for related tasks | "v0.4.0 - G Suite Access" |
| `bug` | Something broken | "Token refresh fails silently" |
| `feature` | New capability | "Dark mode support" |
| `chore` | Maintenance | "Update dependencies" |

## Priority Levels

| Priority | Meaning | Usage |
|----------|---------|-------|
| P0 | Critical | Blocking release/broken production |
| P1 | High | Important feature/fix for current sprint |
| P2 | Medium | Normal priority (default) |
| P3 | Low | Nice to have |
| P4 | Backlog | Future consideration |

## Workflow Patterns

### Session Start Pattern

```bash
# 1. Check what's actionable
bd ready

# 2. Pick highest priority ready task
bd update <issue-id> --status in_progress

# 3. Work on it (Claude writes code, runs tests, etc.)

# 4. When done
bd close <issue-id> --reason "Completed: [summary of what was done]"

# 5. Check if anything became unblocked
bd ready
```

### Discovering Work Pattern

```bash
# Found something while working on another task?
bd create "Edge case: empty response handling" --parent <current-epic>

# Realized current task depends on something else?
bd create "Add retry logic first" -p 1
bd dep add <current-task> <new-prereq>
# Current task now blocked until prereq done
```

### Epic Planning Pattern

```bash
# Create the epic
bd create "v0.5.0 - Dashboard Redesign" -t epic -p 1 --silent
# Returns: bd-abc

# Add child tasks
bd create "Design new component structure" --parent bd-abc
bd create "Implement responsive grid" --parent bd-abc
bd create "Add dark mode toggle" --parent bd-abc
bd create "Write integration tests" --parent bd-abc

# Set up dependencies
bd dep add <tests-task> <grid-task>
bd dep add <tests-task> <dark-mode-task>

# View the plan
bd graph bd-abc
```

## Companion Tools

### beads-ui (Local Web Interface)

A browser-based dashboard for visual issue management.

**Installation:**
```bash
npm i beads-ui -g
```

**Usage:**
```bash
# Start UI and open browser
bdui start --open

# Start on specific port
bdui start --port 8080
```

**Features:**
- Live database monitoring (auto-updates)
- Kanban board (Blocked → Ready → In Progress → Closed)
- Epic progress tracking
- Keyboard navigation
- Inline editing

**Repository:** [github.com/mantoni/beads-ui](https://github.com/mantoni/beads-ui)

### beads-dashboard (Metrics Dashboard)

Lean metrics and analytics for workflow efficiency.

**Installation:**
```bash
npm install -g beads-dashboard
```

**Usage:**
```bash
# Start dashboard (defaults to port 3001)
beads-dashboard

# Point to specific project
beads-dashboard /path/to/project
```

**Features:**
- Lead time scatterplots
- Aging WIP analysis
- Cumulative flow diagrams
- Throughput tracking
- Configurable aging alerts

**Repository:** [github.com/rhydlewis/beads-dashboard](https://github.com/rhydlewis/beads-dashboard)

## Project Setup

### Initial Setup (Already Done)

```bash
# Install beads via Homebrew
brew install beads

# Initialize in project
bd init

# Verify
bd status
```

### Files Created

```
.beads/
├── config.yaml       # Project configuration
├── metadata.json     # Database settings
├── issues.jsonl      # Issue data (git-tracked)
├── beads.db          # SQLite cache (gitignored)
├── beads.db-wal      # SQLite WAL (gitignored)
├── daemon.pid        # Background process (gitignored)
└── README.md         # Quick reference
```

### Configuration Options

Edit `.beads/config.yaml`:

```yaml
# Git branch for sync commits
# sync-branch: "beads-sync"

# Default actor for audit trails
# actor: "claude-agent"

# Auto-start daemon
# auto-start-daemon: true
```

## Teardown (Removing Beads)

If you want to remove beads from the project:

```bash
# 1. Stop the daemon if running
bd daemon stop 2>/dev/null || true

# 2. Export issues to markdown for reference (optional)
bd list --json > beads-export.json

# 3. Remove the .beads directory
rm -rf .beads

# 4. Remove from .gitignore if you added entries
# (check for .beads/beads.db* entries)

# 5. Optionally uninstall beads CLI
brew uninstall beads
# or: pip uninstall beads-mcp
# or: npm uninstall -g beads-mcp
```

## Integration with ROADMAP.md

Beads complements (doesn't replace) your documentation:

| Artifact | Purpose | Beads Role |
|----------|---------|------------|
| `ROADMAP.md` | Human-readable project overview | Reference for creating epics |
| `specs/*.md` | Detailed implementation specs | Linked in issue descriptions |
| Beads issues | Active task tracking | AI agent session memory |

### Mapping Pattern

```
ROADMAP.md section → bd create -t epic "..."
├── Checkbox item → bd create "..." --parent <epic>
├── Checkbox item → bd create "..." --parent <epic>
└── "Depends on X" → bd dep add <this-epic> <dependency>
```

## Tips for AI Agent Usage

1. **Session start**: Always run `bd ready` to see actionable work
2. **One at a time**: Mark only one issue `in_progress` at a time
3. **Capture discoveries**: Create new issues for work discovered during implementation
4. **Close with context**: Include commit hashes or PR numbers in close reasons
5. **Use dependencies**: If task A needs task B done first, use `bd dep add A B`
6. **Check unblocked**: After closing, run `bd ready` to see newly unblocked work

## Troubleshooting

### "Database locked"

```bash
# Stop daemon and retry
bd daemon stop
bd list
```

### "Issue not found"

```bash
# Sync from JSONL
bd sync
```

### Prefix too long

The default prefix is the directory name. For shorter IDs:

```bash
# In .beads/config.yaml:
issue-prefix: "app"

# Then rename existing issues
bd rename-prefix app
```

## Resources

- **Official Docs:** [github.com/steveyegge/beads/docs](https://github.com/steveyegge/beads/tree/main/docs)
- **FAQ:** [github.com/steveyegge/beads/blob/main/docs/FAQ.md](https://github.com/steveyegge/beads/blob/main/docs/FAQ.md)
- **Better Stack Guide:** [betterstack.com/community/guides/ai/beads-issue-tracker-ai-agents](https://betterstack.com/community/guides/ai/beads-issue-tracker-ai-agents/)
