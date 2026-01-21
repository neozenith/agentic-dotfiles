---
name: introspect
description: Self-introspect Claude Code sessions, analyze conversation history, track tool usage, and explore memory files. Use when reviewing past sessions, debugging tool failures, analyzing conversation patterns, or understanding what happened in previous Claude Code interactions.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(.claude/skills/introspect/scripts/query_sessions.sh *)
user-invocable: true
---

# Claude Code Introspection

A skill for self-introspection and analysis of Claude Code sessions, memory files, skills, hooks, and plugins.

## Current Session ID

The current session ID is automatically available:

```
${CLAUDE_SESSION_ID}
```

Use this to query the current session directly without needing to look it up.

## Quick Start

Use the bash wrapper script to query session data:

```bash
# Get summary of the CURRENT session
.claude/skills/introspect/scripts/query_sessions.sh summary ${CLAUDE_SESSION_ID}

# Show recent turns in the CURRENT session
.claude/skills/introspect/scripts/query_sessions.sh turns ${CLAUDE_SESSION_ID} -n 20

# Get tool usage for the CURRENT session
.claude/skills/introspect/scripts/query_sessions.sh tools ${CLAUDE_SESSION_ID}

# List all projects with session counts
.claude/skills/introspect/scripts/query_sessions.sh projects

# Get help
.claude/skills/introspect/scripts/query_sessions.sh --help
```

**Note:** For project IDs that start with hyphens (e.g., `-Users-joshpeak-...`), use `--` before the argument to prevent argparse from interpreting it as an option flag.

## Session Data Location

Claude Code stores session logs at:
```
~/.claude/projects/{project-path-kebab-cased}/{session_uuid}.jsonl
```

Each JSONL file contains events with these types:
- `user` - User messages
- `assistant` - Claude's responses
- `tool_use` - Tool call requests (name, input, id)
- `tool_result` - Tool execution results
- `thinking` - Claude's thinking blocks
- `summary` - Session summary
- `file-history-snapshot` - File backup information

## Available Commands

### Session Summary (Current Session)

```bash
# Get comprehensive metrics for THIS session
.claude/skills/introspect/scripts/query_sessions.sh summary ${CLAUDE_SESSION_ID}
```

Returns:
- Total events, user/assistant message counts
- Tool calls count
- Duration and token usage
- Models used

### Show Turns (Current Session)

```bash
# Show last 20 turns in THIS session
.claude/skills/introspect/scripts/query_sessions.sh turns ${CLAUDE_SESSION_ID} -n 20

# Show only user and assistant messages
.claude/skills/introspect/scripts/query_sessions.sh turns ${CLAUDE_SESSION_ID} -t user assistant

# Show turns from the last hour
.claude/skills/introspect/scripts/query_sessions.sh turns ${CLAUDE_SESSION_ID} --since 1h
```

Options:
- `-t, --types TYPE [TYPE...]` - Filter event types (user, assistant, tool_use, etc.)
- `--since TIME` - Filter events after this time
- `--until TIME` - Filter events before this time
- `-n, --limit N` - Max turns to show (default: 100)
- `--offset N` - Skip first N turns
- `--no-content` - Exclude message content (faster)
- `-p, --project PROJECT` - Specify project for faster queries

Time filters support:
- ISO format: `2025-01-14T10:00:00`
- Relative: `1h` (1 hour ago), `30m`, `7d`, `2w`

### Tool Usage (Current Session)

```bash
# Summary of tools used in THIS session
.claude/skills/introspect/scripts/query_sessions.sh tools ${CLAUDE_SESSION_ID}

# Detailed tool calls
.claude/skills/introspect/scripts/query_sessions.sh tools ${CLAUDE_SESSION_ID} --detail

# Filter to specific tool
.claude/skills/introspect/scripts/query_sessions.sh tools ${CLAUDE_SESSION_ID} --tool Bash
```

### List Projects

```bash
.claude/skills/introspect/scripts/query_sessions.sh projects
```

Shows all projects with:
- Project ID (kebab-cased path)
- Session count
- First/last activity timestamps

### List Sessions

```bash
.claude/skills/introspect/scripts/query_sessions.sh sessions -n LIMIT --since TIME -- PROJECT_ID
```

Options:
- `-n, --limit` - Max sessions to show (default: 20)
- `--since` - Filter sessions since timestamp (ISO or relative like '7d', '1h')

### Search Sessions

```bash
.claude/skills/introspect/scripts/query_sessions.sh search "error pattern" [-p PROJECT] [-t TYPES] [-n LIMIT]
```

Searches across all sessions for content matching the pattern (case-insensitive).

## Output Formats

All commands support multiple output formats:

```bash
# Table format (default)
.claude/skills/introspect/scripts/query_sessions.sh summary ${CLAUDE_SESSION_ID}

# JSON format
.claude/skills/introspect/scripts/query_sessions.sh -f json summary ${CLAUDE_SESSION_ID}

# JSONL format (one JSON object per line)
.claude/skills/introspect/scripts/query_sessions.sh -f jsonl turns ${CLAUDE_SESSION_ID} -n 10
```

## Common Use Cases

### Introspect This Session

```bash
# How many turns have we had?
.claude/skills/introspect/scripts/query_sessions.sh summary ${CLAUDE_SESSION_ID}

# What tools have been used?
.claude/skills/introspect/scripts/query_sessions.sh tools ${CLAUDE_SESSION_ID}

# Show the conversation flow
.claude/skills/introspect/scripts/query_sessions.sh turns ${CLAUDE_SESSION_ID} -t user assistant
```

### Debug a Previous Session

```bash
# Find recent sessions for this project
.claude/skills/introspect/scripts/query_sessions.sh sessions -n 5 -- PROJECT_ID

# Get summary of a specific session
.claude/skills/introspect/scripts/query_sessions.sh summary OTHER_SESSION_ID

# View tool results (often where errors appear)
.claude/skills/introspect/scripts/query_sessions.sh turns OTHER_SESSION_ID -t tool_result
```

### Analyze Tool Patterns Across Sessions

```bash
# Search for specific tool usage across all sessions
.claude/skills/introspect/scripts/query_sessions.sh search "Edit" -t tool_use

# Search for errors
.claude/skills/introspect/scripts/query_sessions.sh search "error" -n 20
```

## Technical Details

### Architecture

```
query_sessions.sh (bash wrapper)
       │
       └── uv run query_sessions.py (PEP-723 script)
                    │
                    └── DuckDB queries on ~/.claude/projects/**/*.jsonl
```

The bash wrapper is needed because Claude Code skills cannot directly invoke `uv`. The wrapper simply calls `uv run` on the Python script.

### String Substitution

Claude Code provides `${CLAUDE_SESSION_ID}` which is automatically substituted with the current session's UUID when the skill is invoked. This enables self-introspection without manual lookup.

### PEP-723 Inline Dependencies

The Python script uses PEP-723 for inline dependency declaration:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "duckdb>=1.0.0",
#   "pytz",
# ]
# ///
```

This means `uv run` will automatically create an isolated environment with dependencies installed - no manual `pip install` required.

### Data Schema

The script queries JSONL files with this structure:

```json
{
  "type": "user|assistant|tool_use|tool_result|thinking|...",
  "timestamp": "2025-01-14T10:00:00.000Z",
  "uuid": "unique-event-id",
  "parentUuid": "parent-event-id",
  "message": {
    "role": "user|assistant",
    "content": "...",
    "model": "claude-opus-4-5-20251101",
    "usage": {
      "input_tokens": 1000,
      "output_tokens": 500,
      "cache_read_input_tokens": 200
    }
  },
  "name": "ToolName",
  "input": {},
  "id": "tool-call-id"
}
```

### DuckDB Advantages

Using DuckDB for session analysis provides:
- Fast querying across thousands of JSONL files
- SQL-based filtering and aggregation
- In-memory processing (no database setup)
- Native JSON parsing with nested field access
- Glob pattern matching for file discovery

### Requirements

- Python 3.12+
- `uv` (for running with PEP-723 dependencies)

Install uv if not present:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Future Capabilities (Planned)

- **Memory file management**: List, analyze, and organize CLAUDE.md files
- **Skill discovery**: Analyze and catalog available skills
- **Hook inspection**: View configured hooks and their triggers
- **Plugin management**: List and analyze installed plugins
- **Session comparison**: Compare two sessions to understand differences
- **Cost analysis**: Calculate token costs across sessions
- **Reflection reports**: Generate insights about Claude's behavior patterns
