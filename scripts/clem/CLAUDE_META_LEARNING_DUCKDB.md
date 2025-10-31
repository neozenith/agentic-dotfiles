# Claude Meta-Learning: DuckDB Chat Log Queries

## Overview

Query all Claude Code chat logs across projects using DuckDB's powerful SQL interface. All conversation history is stored as JSONL files in `~/.claude/` and can be queried recursively.

## Session Architecture

**Key Concept**: Each `.jsonl` file represents a complete conversation session.

```
~/.claude/projects/
├── -path-to-project-name/
│   ├── session-id-1.jsonl          # Session 1 (complete conversation)
│   ├── session-id-2.jsonl          # Session 2 (complete conversation)
│   └── session-id-3.jsonl          # Session 3 (complete conversation)
└── -another-project-name/
    └── session-id-4.jsonl          # Session 4 (complete conversation)
```

**Session Properties**:
- **One file = One session**: Each `.jsonl` file contains all messages for a single conversation session
- **Project isolation**: Sessions are grouped by project directory
- **Persistent IDs**: Session IDs are UUIDs embedded in the filename and `sessionId` field
- **Chronological order**: Lines within a file are time-ordered messages
- **Message format**: Each line is a JSON object with `timestamp`, `message`, `sessionId`, etc.

## Core Pattern

```bash
duckdb -c "SELECT * FROM read_ndjson_auto('~/.claude/**/*.jsonl')"
```

## Key Schema Fields

| Field | Type | Description |
|-------|------|-------------|
| `project` | varchar | Full path to the project |
| `timestamp` | json | Unix timestamp in milliseconds |
| `message` | struct | Contains role, content, model, usage stats |
| `message.role` | varchar | `user` or `assistant` |
| `message.content` | json | The actual message text |
| `message.usage` | struct | Token usage statistics |
| `sessionId` | uuid | Unique session identifier |
| `cwd` | varchar | Working directory |
| `gitBranch` | varchar | Git branch context |

## Essential Queries

### Search Across All Conversations

```bash
duckdb -c "
SELECT project, timestamp, message.content
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE message.content LIKE '%your_search_term%'
ORDER BY timestamp DESC
LIMIT 50
"
```

### User Messages Only

```bash
duckdb -c "
SELECT project, timestamp, message.content
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE message.role = 'user'
ORDER BY timestamp DESC
"
```

### Conversation Statistics by Project

```bash
duckdb -c "
SELECT
    project,
    COUNT(*) as msg_count,
    COUNT(DISTINCT sessionId) as sessions
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
GROUP BY project
ORDER BY msg_count DESC
"
```

### Recent Activity Preview

```bash
duckdb -c "
SELECT
    project,
    timestamp,
    message.role,
    substring(message.content::VARCHAR, 1, 100) as preview
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE message IS NOT NULL
ORDER BY timestamp DESC
LIMIT 20
"
```

### Token Usage Analysis

```bash
duckdb -c "
SELECT
    project,
    SUM(message.usage.input_tokens) as total_input_tokens,
    SUM(message.usage.output_tokens) as total_output_tokens
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE message.usage IS NOT NULL
GROUP BY project
ORDER BY total_input_tokens DESC
"
```

### Search by Git Branch

```bash
duckdb -c "
SELECT project, gitBranch, timestamp, message.content
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE gitBranch = 'feature/your-branch'
ORDER BY timestamp DESC
"
```

## Session-Specific Queries

### List All Sessions (Files)

```bash
# List all session files across all projects
ls -lh ~/.claude/projects/*/*.jsonl

# Count total sessions
find ~/.claude/projects -name "*.jsonl" -type f | wc -l

# List sessions for specific project
ls -lh ~/.claude/projects/-path-to-project/*.jsonl
```

### Query Single Session File

```bash
# Query all messages from a specific session file
duckdb -c "
SELECT timestamp, message.role, message.content
FROM read_ndjson_auto('~/.claude/projects/-project-name/session-id.jsonl')
ORDER BY timestamp
"

# Count messages in a session
duckdb -c "
SELECT COUNT(*) as total_messages
FROM read_ndjson_auto('~/.claude/projects/-project-name/session-id.jsonl')
"
```

### Session Metadata

```bash
# Get session metadata from filename and first/last message
duckdb -c "
SELECT
    sessionId,
    MIN(timestamp) as session_start,
    MAX(timestamp) as session_end,
    COUNT(*) as total_exchanges,
    SUM(CASE WHEN message.role = 'user' THEN 1 ELSE 0 END) as user_messages,
    SUM(CASE WHEN message.role = 'assistant' THEN 1 ELSE 0 END) as assistant_messages
FROM read_ndjson_auto('~/.claude/projects/-project-name/session-id.jsonl')
GROUP BY sessionId
"
```

## Current Project Queries

### Query All Sessions in Current Project

```bash
# All messages from current project across all sessions
duckdb -c "
SELECT timestamp, sessionId, message.role, message.content
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE project = '$(pwd)'
ORDER BY timestamp DESC
"
```

### Count Sessions in Current Project

```bash
duckdb -c "
SELECT COUNT(DISTINCT sessionId) as total_sessions
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE project = '$(pwd)'
"
```

### View Session Summary for Current Project

```bash
duckdb -c "
SELECT
    sessionId,
    COUNT(*) as messages,
    MIN(timestamp) as started,
    MAX(timestamp) as last_activity
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE project = '$(pwd)'
GROUP BY sessionId
ORDER BY started DESC
"
```

### Search Within Current Project

```bash
duckdb -c "
SELECT timestamp, sessionId, message.role, message.content
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE project = '$(pwd)'
  AND message.content LIKE '%your_search_term%'
ORDER BY timestamp DESC
"
```

### User Questions in Current Project

```bash
duckdb -c "
SELECT timestamp, sessionId, message.content
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE project = '$(pwd)'
  AND message.role = 'user'
ORDER BY timestamp DESC
"
```

### Current Project Token Usage

```bash
duckdb -c "
SELECT
    sessionId,
    SUM(message.usage.input_tokens) as input_tokens,
    SUM(message.usage.output_tokens) as output_tokens
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE project = '$(pwd)'
  AND message.usage IS NOT NULL
GROUP BY sessionId
ORDER BY input_tokens DESC
"
```

## Advanced Patterns

### Find Conversations with Specific Tools

```bash
duckdb -c "
SELECT project, timestamp, message.content
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
WHERE message.content::VARCHAR LIKE '%Bash%'
   OR message.content::VARCHAR LIKE '%Read%'
ORDER BY timestamp DESC
"
```

### Session-Based Analysis

```bash
duckdb -c "
SELECT
    sessionId,
    project,
    COUNT(*) as exchanges,
    MIN(timestamp) as started,
    MAX(timestamp) as ended
FROM read_ndjson_auto('~/.claude/**/*.jsonl')
GROUP BY sessionId, project
ORDER BY started DESC
LIMIT 10
"
```

### Export to CSV

```bash
duckdb -c "
COPY (
    SELECT project, timestamp, message.role, message.content
    FROM read_ndjson_auto('~/.claude/**/*.jsonl')
    WHERE message IS NOT NULL
) TO 'claude_history.csv' WITH (HEADER, DELIMITER ',')
"
```

## Use Cases

- **Pattern Discovery**: Find how you solved similar problems before
- **Learning Analytics**: Track token usage and conversation patterns
- **Knowledge Retrieval**: Search for specific code snippets or explanations
- **Project Context**: Understand what work was done in which projects
- **Workflow Analysis**: Identify common task patterns and optimization opportunities

## Tips

1. **Performance**: Add `LIMIT` clauses for faster results during exploration
2. **Text Search**: Use `LIKE '%term%'` for case-insensitive substring matching
3. **JSON Casting**: Convert JSON fields with `::VARCHAR` for string operations
4. **Null Handling**: Filter `WHERE message IS NOT NULL` to avoid empty records
5. **Timestamps**: Convert timestamps with `to_timestamp(timestamp/1000)` for human-readable dates

## Interactive Mode

For exploratory analysis, launch DuckDB in interactive mode:

```bash
duckdb
```

Then create a view:

```sql
CREATE VIEW claude_logs AS
SELECT * FROM read_ndjson_auto('~/.claude/**/*.jsonl');

SELECT project, COUNT(*) FROM claude_logs GROUP BY project;
```
