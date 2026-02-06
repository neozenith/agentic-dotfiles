#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
introspect_sessions - Query and analyze Claude Code session logs using pure Python with SQLite cache.

A self-contained CLI for querying session JSONL files stored at:
    ~/.claude/projects/{project-path-kebab-cased}/{session_uuid}.jsonl

Features:
    - SQLite caching with incremental updates based on file mtime
    - FTS5 full-text search on message content
    - No external dependencies (pure Python 3.12+ with sqlite3)
    - Full session event parsing with parent-child relationships
    - UUID-based event lookup and tree traversal
    - Meta-prompt evaluation via claude -p subprocess

Usage:
    uv run introspect_sessions.py cache init              # Initialize cache
    uv run introspect_sessions.py cache update            # Incremental update
    uv run introspect_sessions.py cache rebuild           # Full rebuild
    uv run introspect_sessions.py cache status            # Show cache status
    uv run introspect_sessions.py projects                # List all projects
    uv run introspect_sessions.py search "pattern"        # Full-text search
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from textwrap import dedent
from typing import Any, Literal

# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

CLAUDE_HOME = Path.home() / ".claude"
PROJECTS_PATH = CLAUDE_HOME / "projects"

# Cache stored in current working directory's .claude/cache/
CWD_CLAUDE_DIR = Path.cwd() / ".claude"
CACHE_DIR = CWD_CLAUDE_DIR / "cache"
CACHE_DB_PATH = CACHE_DIR / "introspect_sessions.db"

# Logging setup
log = logging.getLogger(__name__)

SCHEMA_VERSION = "2"

# ML Analysis Configuration (used by reflect --engine)
ML_DEFAULT_MODELS: dict[str, str] = {
    "sentiment": "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    "zero-shot": "facebook/bart-large-mnli",
    "summarize": "facebook/bart-large-cnn",
    "ner": "dslim/bert-base-NER",
}

ML_TASK_NAMES: dict[str, str] = {
    "sentiment": "sentiment-analysis",
    "zero-shot": "zero-shot-classification",
    "summarize": "summarization",
    "ner": "ner",
}

ML_DEFAULT_MAX_CHARS = 2000  # ~512 tokens for BERT-family models


# ============================================================================
# Pricing Configuration
# ============================================================================

PRICING = {
    "opus": {
        "input": 15.0,  # per 1M tokens
        "output": 75.0,
        "cache_read_multiplier": 0.1,  # 90% discount
        "cache_write_multiplier": 1.25,  # 25% premium
    },
    "sonnet": {
        "input": 3.0,
        "output": 15.0,
        "cache_read_multiplier": 0.1,
        "cache_write_multiplier": 1.25,
    },
    "haiku": {
        "input": 1.0,
        "output": 5.0,
        "cache_read_multiplier": 0.1,
        "cache_write_multiplier": 1.25,
    },
}


def model_family_from_id(model_id: str | None) -> str:
    """Extract model family (opus/sonnet/haiku) from a full model ID string."""
    if model_id is None:
        return "unknown"
    model_lower = model_id.lower()
    for family in ("opus", "sonnet", "haiku"):
        if family in model_lower:
            return family
    return "unknown"


# ============================================================================
# SQLite Cache Schema
# ============================================================================

SCHEMA_SQL = """
-- Source files table: tracks all parsed JSONL files
CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    mtime REAL NOT NULL,
    size_bytes INTEGER NOT NULL,
    line_count INTEGER NOT NULL,
    last_ingested_at TEXT NOT NULL,
    project_id TEXT NOT NULL,
    session_id TEXT,  -- NULL for orphan agent files
    file_type TEXT NOT NULL CHECK (file_type IN ('main_session', 'subagent', 'agent_root'))
);

CREATE INDEX IF NOT EXISTS idx_source_files_project ON source_files(project_id);
CREATE INDEX IF NOT EXISTS idx_source_files_session ON source_files(session_id);
CREATE INDEX IF NOT EXISTS idx_source_files_mtime ON source_files(mtime);

-- Projects table: aggregated project metadata
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT UNIQUE NOT NULL,
    first_activity TEXT,
    last_activity TEXT,
    session_count INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_projects_last_activity ON projects(last_activity);

-- Sessions table: aggregated session metadata
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    first_timestamp TEXT,
    last_timestamp TEXT,
    event_count INTEGER DEFAULT 0,
    subagent_count INTEGER DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cache_read_tokens INTEGER DEFAULT 0,
    total_cache_creation_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    UNIQUE(project_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last_timestamp ON sessions(last_timestamp);

-- Events table: all parsed events
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT,
    parent_uuid TEXT,
    event_type TEXT NOT NULL,
    timestamp TEXT,
    timestamp_local TEXT,
    session_id TEXT,
    project_id TEXT NOT NULL,
    is_sidechain INTEGER DEFAULT 0,
    agent_id TEXT,
    agent_slug TEXT,
    message_role TEXT,
    message_content TEXT,  -- Plain text for FTS
    message_content_json TEXT,  -- Original JSON structure
    model_id TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_creation_tokens INTEGER DEFAULT 0,
    cache_5m_tokens INTEGER DEFAULT 0,
    source_file_id INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_uuid ON events(uuid);
CREATE INDEX IF NOT EXISTS idx_events_parent_uuid ON events(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_source_file ON events(source_file_id);

-- FTS5 virtual table for full-text search on message content
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    message_content,
    content='events',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
    INSERT INTO events_fts(rowid, message_content) VALUES (new.id, new.message_content);
END;

CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
    INSERT INTO events_fts(events_fts, rowid, message_content) VALUES('delete', old.id, old.message_content);
END;

CREATE TRIGGER IF NOT EXISTS events_au AFTER UPDATE ON events BEGIN
    INSERT INTO events_fts(events_fts, rowid, message_content) VALUES('delete', old.id, old.message_content);
    INSERT INTO events_fts(rowid, message_content) VALUES (new.id, new.message_content);
END;

-- Cache metadata table
CREATE TABLE IF NOT EXISTS cache_metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Event edges table: parent-child relationships for graph traversal
CREATE TABLE IF NOT EXISTS event_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_uuid TEXT NOT NULL,
    parent_event_uuid TEXT NOT NULL,
    source_file_id INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_event_edges_forward ON event_edges(project_id, session_id, event_uuid);
CREATE INDEX IF NOT EXISTS idx_event_edges_reverse ON event_edges(project_id, session_id, parent_event_uuid);
CREATE INDEX IF NOT EXISTS idx_event_edges_source_file ON event_edges(source_file_id);

-- Reflections table: persisted meta-prompt evaluations
CREATE TABLE IF NOT EXISTS reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    reflection_prompt TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- FTS5 for reflections
CREATE VIRTUAL TABLE IF NOT EXISTS reflections_fts USING fts5(
    reflection_prompt, content='reflections', content_rowid='id'
);

-- Triggers to keep reflections_fts in sync
CREATE TRIGGER IF NOT EXISTS reflections_ai AFTER INSERT ON reflections BEGIN
    INSERT INTO reflections_fts(rowid, reflection_prompt) VALUES (new.id, new.reflection_prompt);
END;

CREATE TRIGGER IF NOT EXISTS reflections_ad AFTER DELETE ON reflections BEGIN
    INSERT INTO reflections_fts(reflections_fts, rowid, reflection_prompt)
        VALUES('delete', old.id, old.reflection_prompt);
END;

CREATE TRIGGER IF NOT EXISTS reflections_au AFTER UPDATE ON reflections BEGIN
    INSERT INTO reflections_fts(reflections_fts, rowid, reflection_prompt)
        VALUES('delete', old.id, old.reflection_prompt);
    INSERT INTO reflections_fts(rowid, reflection_prompt)
        VALUES(new.id, new.reflection_prompt);
END;

-- Event annotations table: reflection results linked to events
CREATE TABLE IF NOT EXISTS event_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_uuid TEXT NOT NULL,
    reflection_id INTEGER NOT NULL REFERENCES reflections(id) ON DELETE CASCADE,
    annotation_result TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_annotations_reflection ON event_annotations(reflection_id);
CREATE INDEX IF NOT EXISTS idx_event_annotations_event ON event_annotations(event_uuid);
CREATE INDEX IF NOT EXISTS idx_event_annotations_session ON event_annotations(project_id, session_id);

-- Composite indexes on existing tables for common query patterns
CREATE INDEX IF NOT EXISTS idx_events_project_session ON events(project_id, session_id);
CREATE INDEX IF NOT EXISTS idx_events_session_type ON events(session_id, event_type);
CREATE INDEX IF NOT EXISTS idx_events_session_uuid ON events(session_id, uuid);
CREATE INDEX IF NOT EXISTS idx_source_files_project_session ON source_files(project_id, session_id);
"""


# ============================================================================
# SQLite Cache Manager
# ============================================================================


class CacheManager:
    """Manages the SQLite cache for session data."""

    def __init__(self, db_path: Path = CACHE_DB_PATH):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def init_schema(self) -> None:
        """Initialize database schema."""
        log.info("Initializing cache schema...")
        self.conn.executescript(SCHEMA_SQL)
        self.conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
            ("created_at", datetime.now(UTC).isoformat()),
        )
        self.conn.commit()
        log.info(f"Cache initialized at {self.db_path}")

    def needs_rebuild(self) -> bool:
        """Check if the schema version requires a rebuild."""
        try:
            row = self.conn.execute(
                "SELECT value FROM cache_metadata WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                return True
            return bool(row[0] != SCHEMA_VERSION)
        except sqlite3.OperationalError:
            # cache_metadata table doesn't exist yet
            return True

    def clear(self) -> None:
        """Clear all cached data. Safe to call even if tables don't exist."""
        log.info("Clearing cache...")
        # Use DELETE FROM with IF EXISTS check via try/except for each table
        tables_to_clear = [
            "event_annotations",  # FK → reflections
            "reflections",
            "event_edges",  # FK → source_files
            "events",
            "sessions",
            "projects",
            "source_files",
            "events_fts",
            "reflections_fts",
        ]
        for table in tables_to_clear:
            try:
                self.conn.execute(f"DELETE FROM {table}")
            except sqlite3.OperationalError:
                # Table doesn't exist yet, that's fine
                pass
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
                ("last_cleared_at", datetime.now(UTC).isoformat()),
            )
        except sqlite3.OperationalError:
            # cache_metadata table doesn't exist yet
            pass
        self.conn.commit()
        log.info("Cache cleared")

    def get_status(self) -> dict[str, Any]:
        """Get cache status information."""
        cursor = self.conn.cursor()

        # Get counts
        file_count = cursor.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
        project_count = cursor.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        session_count = cursor.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        event_count = cursor.execute("SELECT COUNT(*) FROM events").fetchone()[0]

        # Get counts for new tables (with backward compat)
        edge_count = 0
        reflection_count = 0
        annotation_count = 0
        try:
            edge_count = cursor.execute("SELECT COUNT(*) FROM event_edges").fetchone()[0]
            reflection_count = cursor.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
            annotation_count = cursor.execute("SELECT COUNT(*) FROM event_annotations").fetchone()[
                0
            ]
        except sqlite3.OperationalError:
            pass  # Tables may not exist in older schema

        # Get metadata
        created_at = cursor.execute(
            "SELECT value FROM cache_metadata WHERE key = 'created_at'"
        ).fetchone()
        last_update = cursor.execute(
            "SELECT value FROM cache_metadata WHERE key = 'last_update_at'"
        ).fetchone()

        # Get database file size
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "db_path": str(self.db_path),
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / (1024 * 1024), 2),
            "source_files": file_count,
            "projects": project_count,
            "sessions": session_count,
            "events": event_count,
            "event_edges": edge_count,
            "reflections": reflection_count,
            "event_annotations": annotation_count,
            "created_at": created_at[0] if created_at else None,
            "last_update_at": last_update[0] if last_update else None,
        }

    def discover_files(self, projects_path: Path) -> list[dict[str, Any]]:
        """Discover all JSONL files and classify them."""
        files: list[dict[str, Any]] = []

        if not projects_path.exists():
            return files

        for project_dir in projects_path.iterdir():
            if not project_dir.is_dir():
                continue

            project_id = project_dir.name

            for jsonl_file in project_dir.rglob("*.jsonl"):
                rel_path = jsonl_file.relative_to(project_dir)
                parts = rel_path.parts

                file_info = {
                    "filepath": str(jsonl_file),
                    "project_id": project_id,
                    "session_id": None,
                    "file_type": "unknown",
                }

                if len(parts) == 1:
                    # File at project root
                    filename = parts[0]
                    if filename.startswith("agent-"):
                        # Agent file at project root - needs sessionId from content
                        file_info["file_type"] = "agent_root"
                    else:
                        # Main session file
                        session_id = filename.replace(".jsonl", "")
                        file_info["session_id"] = session_id
                        file_info["file_type"] = "main_session"

                elif len(parts) >= 2 and "subagents" in parts:
                    # Subagent file in session subdirectory
                    # Path: {session_id}/subagents/agent-*.jsonl
                    session_id = parts[0]
                    file_info["session_id"] = session_id
                    file_info["file_type"] = "subagent"

                elif len(parts) == 2:
                    # Legacy: {session_id}/*.jsonl (old format)
                    session_id = parts[0]
                    file_info["session_id"] = session_id
                    file_info["file_type"] = "subagent"

                files.append(file_info)

        return files

    def get_files_needing_update(self, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter files to only those that need updating."""
        cursor = self.conn.cursor()
        needs_update: list[dict[str, Any]] = []

        for file_info in files:
            filepath = file_info["filepath"]

            try:
                stat = os.stat(filepath)
                current_mtime = stat.st_mtime
                current_size = stat.st_size
            except OSError:
                continue

            # Check if file is in cache with same mtime
            cached = cursor.execute(
                "SELECT mtime, size_bytes FROM source_files WHERE filepath = ?",
                (filepath,),
            ).fetchone()

            if cached is None:
                # New file
                file_info["mtime"] = current_mtime
                file_info["size_bytes"] = current_size
                file_info["reason"] = "new"
                needs_update.append(file_info)
            elif cached["mtime"] != current_mtime or cached["size_bytes"] != current_size:
                # Modified file
                file_info["mtime"] = current_mtime
                file_info["size_bytes"] = current_size
                file_info["reason"] = "modified"
                needs_update.append(file_info)

        return needs_update

    def ingest_file(self, file_info: dict[str, Any]) -> int:
        """Ingest a single JSONL file into the cache. Returns event count."""
        filepath = file_info["filepath"]
        project_id = file_info["project_id"]
        session_id = file_info.get("session_id")
        file_type = file_info["file_type"]
        mtime = file_info["mtime"]
        size_bytes = file_info["size_bytes"]

        log.debug(f"Ingesting {filepath}")

        cursor = self.conn.cursor()

        # Delete existing data for this file (if re-ingesting)
        existing = cursor.execute(
            "SELECT id FROM source_files WHERE filepath = ?", (filepath,)
        ).fetchone()
        if existing:
            cursor.execute("DELETE FROM event_edges WHERE source_file_id = ?", (existing[0],))
            cursor.execute("DELETE FROM events WHERE source_file_id = ?", (existing[0],))
            cursor.execute("DELETE FROM source_files WHERE id = ?", (existing[0],))

        # Parse file and count lines
        events_data: list[dict[str, Any]] = []
        line_count = 0
        detected_session_id = session_id  # May be updated from file content

        try:
            with open(filepath, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line_count = line_num
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # For agent_root files, extract sessionId from content
                    if file_type == "agent_root" and detected_session_id is None:
                        detected_session_id = raw.get("sessionId")

                    event = self._parse_event_for_cache(
                        raw, project_id, detected_session_id, filepath, line_num
                    )
                    if event:
                        events_data.append(event)

        except (FileNotFoundError, PermissionError) as e:
            log.warning(f"Could not read {filepath}: {e}")
            return 0

        # Insert source file record
        cursor.execute(
            """INSERT INTO source_files
               (filepath, mtime, size_bytes, line_count, last_ingested_at,
                project_id, session_id, file_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                filepath,
                mtime,
                size_bytes,
                line_count,
                datetime.now(UTC).isoformat(),
                project_id,
                detected_session_id,
                file_type,
            ),
        )
        source_file_id = cursor.lastrowid

        # Insert events
        for event in events_data:
            cursor.execute(
                """INSERT INTO events
                   (uuid, parent_uuid, event_type, timestamp, timestamp_local,
                    session_id, project_id, is_sidechain, agent_id, agent_slug,
                    message_role, message_content, message_content_json, model_id,
                    input_tokens, output_tokens, cache_read_tokens,
                    cache_creation_tokens, cache_5m_tokens,
                    source_file_id, line_number, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["uuid"],
                    event["parent_uuid"],
                    event["event_type"],
                    event["timestamp"],
                    event["timestamp_local"],
                    detected_session_id,
                    project_id,
                    event["is_sidechain"],
                    event["agent_id"],
                    event["agent_slug"],
                    event["message_role"],
                    event["message_content"],
                    event["message_content_json"],
                    event["model_id"],
                    event["input_tokens"],
                    event["output_tokens"],
                    event["cache_read_tokens"],
                    event["cache_creation_tokens"],
                    event["cache_5m_tokens"],
                    source_file_id,
                    event["line_number"],
                    event["raw_json"],
                ),
            )

        # Insert event edges for parent-child relationships
        for event in events_data:
            if event["uuid"] and event["parent_uuid"]:
                cursor.execute(
                    """INSERT INTO event_edges
                       (project_id, session_id, event_uuid, parent_event_uuid, source_file_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        project_id,
                        detected_session_id,
                        event["uuid"],
                        event["parent_uuid"],
                        source_file_id,
                    ),
                )

        return len(events_data)

    def _parse_event_for_cache(
        self,
        raw: dict[str, Any],
        project_id: str,
        session_id: str | None,
        filepath: str,
        line_number: int,
    ) -> dict[str, Any] | None:
        """Parse a raw event dict for cache insertion."""
        event_type = raw.get("type", "")

        # Skip file-history-snapshot events
        if event_type == "file-history-snapshot":
            return None

        # Extract fields
        timestamp = raw.get("timestamp")
        uuid = raw.get("uuid")
        parent_uuid = raw.get("parentUuid")
        is_sidechain = raw.get("isSidechain", False)
        agent_id = raw.get("agentId")
        agent_slug = raw.get("slug")

        # Extract message info
        message = raw.get("message", {}) or {}
        message_role = message.get("role") if isinstance(message, dict) else None
        message_content_raw = message.get("content") if isinstance(message, dict) else None
        model_id = message.get("model") if isinstance(message, dict) else None

        # Extract plain text for FTS
        message_content_text = self._extract_text_content(message_content_raw)

        # Extract token usage
        usage = message.get("usage", {}) if isinstance(message, dict) else {}
        input_tokens = usage.get("input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        cache_read_tokens = usage.get("cache_read_input_tokens", 0) or 0
        cache_creation_tokens = usage.get("cache_creation_input_tokens", 0) or 0
        cache_creation = usage.get("cache_creation", {}) or {}
        cache_5m_tokens = cache_creation.get("ephemeral_5m_input_tokens", 0) or 0

        # Compute local timestamp
        timestamp_local = None
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                local_dt = dt.astimezone()
                timestamp_local = local_dt.isoformat()
            except (ValueError, TypeError):
                pass

        return {
            "uuid": uuid,
            "parent_uuid": parent_uuid,
            "event_type": event_type,
            "timestamp": timestamp,
            "timestamp_local": timestamp_local,
            "is_sidechain": 1 if is_sidechain else 0,
            "agent_id": agent_id,
            "agent_slug": agent_slug,
            "message_role": message_role,
            "message_content": message_content_text,
            "message_content_json": json.dumps(message_content_raw)
            if message_content_raw
            else None,
            "model_id": model_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "cache_creation_tokens": cache_creation_tokens,
            "cache_5m_tokens": cache_5m_tokens,
            "line_number": line_number,
            "raw_json": json.dumps(raw),
        }

    def _extract_text_content(self, content: Any) -> str:
        """Extract plain text from message content for FTS."""
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "thinking":
                        parts.append(block.get("thinking", ""))
                    elif block.get("type") == "tool_use":
                        parts.append(f"[tool: {block.get('name', '')}]")
                        inp = block.get("input", {})
                        if isinstance(inp, dict):
                            for v in inp.values():
                                if isinstance(v, str):
                                    parts.append(v[:500])  # Limit tool input text
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(filter(None, parts))

        return ""

    def rebuild_aggregates(self) -> None:
        """Rebuild projects and sessions tables from events."""
        log.info("Rebuilding aggregate tables...")
        cursor = self.conn.cursor()

        # Rebuild projects
        cursor.execute("DELETE FROM projects")
        cursor.execute("""
            INSERT INTO projects (project_id, first_activity, last_activity, session_count, event_count)
            SELECT
                project_id,
                MIN(timestamp) as first_activity,
                MAX(timestamp) as last_activity,
                COUNT(DISTINCT session_id) as session_count,
                COUNT(*) as event_count
            FROM events
            WHERE timestamp IS NOT NULL
            GROUP BY project_id
        """)

        # Rebuild sessions
        cursor.execute("DELETE FROM sessions")
        cursor.execute("""
            INSERT INTO sessions (
                session_id, project_id, first_timestamp, last_timestamp,
                event_count, subagent_count,
                total_input_tokens, total_output_tokens,
                total_cache_read_tokens, total_cache_creation_tokens
            )
            SELECT
                session_id,
                project_id,
                MIN(timestamp) as first_timestamp,
                MAX(timestamp) as last_timestamp,
                COUNT(*) as event_count,
                COUNT(DISTINCT agent_id) - 1 as subagent_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(cache_read_tokens) as total_cache_read_tokens,
                SUM(cache_creation_tokens) as total_cache_creation_tokens
            FROM events
            WHERE session_id IS NOT NULL
            GROUP BY project_id, session_id
        """)

        # Calculate costs per-event using model family pricing
        cursor.execute("""
            UPDATE sessions SET total_cost_usd = (
                SELECT COALESCE(SUM(
                    CASE
                        WHEN e.model_id LIKE '%opus%' THEN
                            (e.input_tokens / 1000000.0) * 15.0 +
                            (e.output_tokens / 1000000.0) * 75.0 +
                            (e.cache_read_tokens / 1000000.0) * 1.5 +
                            (e.cache_creation_tokens / 1000000.0) * 18.75
                        WHEN e.model_id LIKE '%sonnet%' THEN
                            (e.input_tokens / 1000000.0) * 3.0 +
                            (e.output_tokens / 1000000.0) * 15.0 +
                            (e.cache_read_tokens / 1000000.0) * 0.3 +
                            (e.cache_creation_tokens / 1000000.0) * 3.75
                        WHEN e.model_id LIKE '%haiku%' THEN
                            (e.input_tokens / 1000000.0) * 1.0 +
                            (e.output_tokens / 1000000.0) * 5.0 +
                            (e.cache_read_tokens / 1000000.0) * 0.1 +
                            (e.cache_creation_tokens / 1000000.0) * 1.25
                        ELSE
                            (e.input_tokens / 1000000.0) * 15.0 +
                            (e.output_tokens / 1000000.0) * 75.0 +
                            (e.cache_read_tokens / 1000000.0) * 1.5 +
                            (e.cache_creation_tokens / 1000000.0) * 18.75
                    END
                ), 0)
                FROM events e
                WHERE e.session_id = sessions.session_id
                  AND e.project_id = sessions.project_id
            )
        """)

        self.conn.commit()
        log.info("Aggregate tables rebuilt")

    def update(self, projects_path: Path) -> dict[str, Any]:
        """Perform incremental update of the cache. Returns counts."""
        log.info("Starting incremental cache update...")

        # Discover all files
        all_files = self.discover_files(projects_path)
        log.info(f"Discovered {len(all_files)} total files")

        # Find files needing update
        files_to_update = self.get_files_needing_update(all_files)
        log.info(f"Found {len(files_to_update)} files needing update")

        if not files_to_update:
            log.info("Cache is up to date")
            return {"files_updated": 0, "events_added": 0}

        # Ingest updated files
        total_events = 0
        for file_info in files_to_update:
            events_added = self.ingest_file(file_info)
            total_events += events_added
            log.debug(
                f"  {file_info['filepath']}: {events_added} events ({file_info.get('reason', 'new')})"
            )

        self.conn.commit()

        # Rebuild aggregates
        self.rebuild_aggregates()

        # Update metadata
        self.conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
            ("last_update_at", datetime.now(UTC).isoformat()),
        )
        self.conn.commit()

        log.info(f"Updated {len(files_to_update)} files, {total_events} events")
        return {"files_updated": len(files_to_update), "events_added": total_events}


# ============================================================================
# Session Event Data Class (for non-cached operations)
# ============================================================================


@dataclass
class SessionEvent:
    """Represents a single event from a session JSONL file."""

    uuid: str | None
    parent_uuid: str | None
    event_type: str
    timestamp: str | None
    timestamp_local: str | None
    session_id: str | None
    is_sidechain: bool
    agent_id: str | None
    agent_slug: str | None
    message_role: str | None
    message_content: str | list[dict[str, Any]] | None
    model_id: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cache_5m_tokens: int
    filepath: str
    line_number: int
    is_subagent_file: bool
    raw_event: dict[str, Any] = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "uuid": self.uuid,
            "parent_uuid": self.parent_uuid,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "timestamp_local": self.timestamp_local,
            "session_id": self.session_id,
            "is_sidechain": self.is_sidechain,
            "agent_id": self.agent_id,
            "agent_slug": self.agent_slug,
            "message_role": self.message_role,
            "message_content": self.message_content,
            "model_id": self.model_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_5m_tokens": self.cache_5m_tokens,
            "filepath": self.filepath,
            "line_number": self.line_number,
            "is_subagent_file": self.is_subagent_file,
            "message_json": self.raw_event,
        }


# ============================================================================
# Query Functions (using SQLite cache)
# ============================================================================


def ensure_cache(cache: CacheManager, projects_path: Path | None = None) -> None:
    """Ensure cache exists and is initialized."""
    if projects_path is None:
        projects_path = PROJECTS_PATH
    if not cache.db_path.exists():
        log.info("Cache not found, initializing...")
        cache.init_schema()
        cache.update(projects_path)
    elif cache.needs_rebuild():
        log.info("Schema version mismatch, rebuilding cache...")
        cache.init_schema()
        cache.clear()
        cache.update(projects_path)


def cmd_cache_init(cache: CacheManager) -> dict[str, Any]:
    """Initialize the cache database."""
    cache.init_schema()
    return {"status": "initialized", "db_path": str(cache.db_path)}


def cmd_cache_clear(cache: CacheManager) -> dict[str, Any]:
    """Clear all cached data."""
    cache.clear()
    return {"status": "cleared", "db_path": str(cache.db_path)}


def cmd_cache_rebuild(cache: CacheManager, projects_path: Path | None = None) -> dict[str, Any]:
    """Full rebuild of the cache."""
    if projects_path is None:
        projects_path = PROJECTS_PATH
    cache.init_schema()  # Ensure schema exists before clearing
    cache.clear()
    result = cache.update(projects_path)
    result["status"] = "rebuilt"
    return result


def cmd_cache_update(cache: CacheManager, projects_path: Path | None = None) -> dict[str, Any]:
    """Incremental update of the cache."""
    if projects_path is None:
        projects_path = PROJECTS_PATH
    ensure_cache(cache, projects_path)
    result = cache.update(projects_path)
    result["status"] = "updated"
    return result


def cmd_cache_status(cache: CacheManager) -> dict[str, Any]:
    """Get cache status information."""
    if not cache.db_path.exists():
        return {"status": "not_initialized", "db_path": str(cache.db_path)}
    return cache.get_status()


def cmd_projects(cache: CacheManager) -> list[dict[str, Any]]:
    """List all projects with session counts and date ranges."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    results = cursor.execute("""
        SELECT project_id, session_count, first_activity, last_activity, event_count
        FROM projects
        ORDER BY last_activity DESC
    """).fetchall()

    return [dict(row) for row in results]


def cmd_sessions(
    cache: CacheManager,
    project_id: str,
    limit: int = 20,
    since: str | None = None,
) -> list[dict[str, Any]]:
    """List sessions for a project with event counts and time info."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    query = """
        SELECT
            session_id, project_id, first_timestamp, last_timestamp,
            event_count, subagent_count,
            total_input_tokens, total_output_tokens,
            total_cache_read_tokens, total_cache_creation_tokens,
            total_cost_usd
        FROM sessions
        WHERE project_id = ?
    """
    params: list[Any] = [project_id]

    if since:
        since_dt = parse_time_filter(since)
        if since_dt:
            query += " AND last_timestamp >= ?"
            params.append(since_dt.isoformat())

    query += " ORDER BY last_timestamp DESC LIMIT ?"
    params.append(limit)

    results = cursor.execute(query, params).fetchall()
    return [dict(row) for row in results]


def cmd_turns(
    cache: CacheManager,
    session_id: str,
    project_id: str | None = None,
    event_types: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
    offset: int = 0,
    include_content: bool = True,
) -> list[dict[str, Any]]:
    """Get turns (events) for a session with filtering options."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    query = """
        SELECT
            e.uuid, e.parent_uuid, e.event_type, e.timestamp, e.timestamp_local,
            e.message_role, e.message_content, e.message_content_json, e.model_id,
            e.input_tokens, e.output_tokens, e.agent_id, e.agent_slug,
            sf.filepath, e.line_number
        FROM events e
        JOIN source_files sf ON e.source_file_id = sf.id
        WHERE e.session_id = ?
    """
    params: list[Any] = [session_id]

    if project_id:
        query += " AND e.project_id = ?"
        params.append(project_id)

    if event_types:
        placeholders = ",".join("?" * len(event_types))
        query += f" AND e.event_type IN ({placeholders})"
        params.extend(event_types)

    if since:
        since_dt = parse_time_filter(since)
        if since_dt:
            query += " AND e.timestamp >= ?"
            params.append(since_dt.isoformat())

    if until:
        until_dt = parse_time_filter(until)
        if until_dt:
            query += " AND e.timestamp <= ?"
            params.append(until_dt.isoformat())

    query += " ORDER BY e.timestamp LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    results = cursor.execute(query, params).fetchall()

    turns = []
    for i, row in enumerate(results, start=offset + 1):
        turn = {
            "turn_num": i,
            "type": row["event_type"],
            "timestamp": row["timestamp"],
            "model": row["model_id"],
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "uuid": row["uuid"],
            "parent_uuid": row["parent_uuid"],
            "filepath": row["filepath"],
            "line_number": row["line_number"],
        }
        if include_content:
            # Use JSON content if available, else plain text
            if row["message_content_json"]:
                try:
                    turn["content"] = json.loads(row["message_content_json"])
                except json.JSONDecodeError:
                    turn["content"] = row["message_content"]
            else:
                turn["content"] = row["message_content"]
            turn["role"] = row["message_role"]

        turns.append(turn)

    return turns


def cmd_tools(
    cache: CacheManager,
    session_id: str,
    project_id: str | None = None,
    tool_name: str | None = None,
    detail: bool = False,
) -> list[dict[str, Any]]:
    """Get tool usage details for a session."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    # Get assistant events with message content
    query = """
        SELECT e.timestamp, e.message_content_json
        FROM events e
        WHERE e.session_id = ? AND e.event_type = 'assistant'
        AND e.message_content_json IS NOT NULL
    """
    params: list[Any] = [session_id]

    if project_id:
        query += " AND e.project_id = ?"
        params.append(project_id)

    query += " ORDER BY e.timestamp"
    results = cursor.execute(query, params).fetchall()

    # Extract tool calls
    tool_calls: list[dict[str, Any]] = []

    for row in results:
        try:
            content = json.loads(row["message_content_json"])
            if not isinstance(content, list):
                continue

            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if tool_name and tool_name.lower() not in name.lower():
                        continue

                    tool_calls.append(
                        {
                            "timestamp": row["timestamp"],
                            "tool_name": name,
                            "tool_call_id": block.get("id"),
                            "tool_input": block.get("input"),
                        }
                    )
        except json.JSONDecodeError:
            continue

    if detail:
        return tool_calls

    # Summary mode
    summary: dict[str, dict[str, Any]] = {}
    for call in tool_calls:
        name = call["tool_name"]
        if name not in summary:
            summary[name] = {
                "tool_name": name,
                "call_count": 0,
                "first_used": call["timestamp"],
                "last_used": call["timestamp"],
            }
        summary[name]["call_count"] += 1
        summary[name]["last_used"] = call["timestamp"]

    return sorted(summary.values(), key=lambda x: x["call_count"], reverse=True)


def cmd_search(
    cache: CacheManager,
    pattern: str,
    project_id: str | None = None,
    event_types: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Full-text search across sessions using FTS5."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    # Use FTS5 for search
    query = """
        SELECT
            e.project_id, e.session_id, e.event_type, e.timestamp,
            SUBSTR(e.message_content, 1, 200) as content_preview,
            sf.filepath, e.line_number
        FROM events e
        JOIN events_fts fts ON e.id = fts.rowid
        JOIN source_files sf ON e.source_file_id = sf.id
        WHERE events_fts MATCH ?
    """
    params: list[Any] = [pattern]

    if project_id:
        query += " AND e.project_id = ?"
        params.append(project_id)

    if event_types:
        placeholders = ",".join("?" * len(event_types))
        query += f" AND e.event_type IN ({placeholders})"
        params.extend(event_types)

    query += " ORDER BY e.timestamp DESC LIMIT ?"
    params.append(limit)

    results = cursor.execute(query, params).fetchall()
    return [dict(row) for row in results]


def cmd_summary(
    cache: CacheManager,
    session_id: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Get a comprehensive summary of a session."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    # Get session info
    query = """
        SELECT * FROM sessions WHERE session_id = ?
    """
    params: list[Any] = [session_id]
    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)

    session = cursor.execute(query, params).fetchone()
    if not session:
        return {"error": f"Session not found: {session_id}"}

    # Get event type counts
    type_counts = cursor.execute(
        """
        SELECT event_type, COUNT(*) as count
        FROM events
        WHERE session_id = ?
        GROUP BY event_type
    """,
        (session_id,),
    ).fetchall()

    # Get model list
    models = cursor.execute(
        """
        SELECT DISTINCT model_id
        FROM events
        WHERE session_id = ? AND model_id IS NOT NULL
    """,
        (session_id,),
    ).fetchall()

    # Get tool call count
    tool_count = cursor.execute(
        """
        SELECT COUNT(*) as count
        FROM events
        WHERE session_id = ? AND event_type = 'assistant'
        AND message_content LIKE '%[tool:%'
    """,
        (session_id,),
    ).fetchone()

    return {
        "session_id": session["session_id"],
        "project_id": session["project_id"],
        "total_events": session["event_count"],
        "user_messages": sum(t["count"] for t in type_counts if t["event_type"] == "user"),
        "assistant_messages": sum(
            t["count"] for t in type_counts if t["event_type"] == "assistant"
        ),
        "tool_calls": tool_count["count"] if tool_count else 0,
        "started_at": session["first_timestamp"],
        "ended_at": session["last_timestamp"],
        "models_used": [m["model_id"] for m in models],
        "input_tokens": session["total_input_tokens"],
        "output_tokens": session["total_output_tokens"],
        "cache_read_tokens": session["total_cache_read_tokens"],
        "cache_creation_tokens": session["total_cache_creation_tokens"],
        "total_cost_usd": session["total_cost_usd"],
    }


def cmd_cost(
    cache: CacheManager,
    session_id: str,
    project_id: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Estimate cost for a session based on token usage.

    When model is None, auto-detects the dominant model family from the session's
    models_used list. Falls back to 'opus' if no models are detected.
    """
    summary = cmd_summary(cache, session_id, project_id)
    if "error" in summary:
        return summary

    # Auto-detect model family from session if not explicitly provided
    if model is None:
        models_used = summary.get("models_used", [])
        families = [model_family_from_id(m) for m in models_used]
        known = [f for f in families if f != "unknown"]
        model = known[0] if known else "opus"

    pricing = PRICING.get(model.lower(), PRICING["opus"])

    input_tokens = summary["input_tokens"]
    output_tokens = summary["output_tokens"]
    cache_read = summary["cache_read_tokens"]
    cache_creation = summary["cache_creation_tokens"]

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    cache_read_cost = (cache_read / 1_000_000) * pricing["input"] * pricing["cache_read_multiplier"]
    cache_write_cost = (
        (cache_creation / 1_000_000) * pricing["input"] * pricing["cache_write_multiplier"]
    )

    total_cost = input_cost + output_cost + cache_read_cost + cache_write_cost

    return {
        "session_id": session_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "input_cost_usd": round(input_cost, 4),
        "output_cost_usd": round(output_cost, 4),
        "cache_read_cost_usd": round(cache_read_cost, 4),
        "cache_write_cost_usd": round(cache_write_cost, 4),
        "total_cost_usd": round(total_cost, 4),
    }


def cmd_messages(
    cache: CacheManager,
    session_id: str,
    project_id: str | None = None,
    role: str | None = None,
    limit: int = 100,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    """Extract user and/or assistant messages from a session."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    query = """
        SELECT event_type, timestamp, message_content
        FROM events
        WHERE session_id = ?
    """
    params: list[Any] = [session_id]

    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)

    if role == "user":
        query += " AND event_type = 'user'"
    elif role == "assistant":
        query += " AND event_type = 'assistant'"
    else:
        query += " AND event_type IN ('user', 'assistant')"

    if agent_id:
        query += " AND agent_id = ?"
        params.append(agent_id)

    query += " ORDER BY timestamp LIMIT ?"
    params.append(limit)

    results = cursor.execute(query, params).fetchall()

    messages = []
    for row in results:
        content = row["message_content"]
        if content and content.strip():
            messages.append(
                {
                    "role": row["event_type"],
                    "timestamp": row["timestamp"],
                    "content": content[:2000],
                }
            )

    return messages


def cmd_agents(
    cache: CacheManager,
    session_id: str,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all subagents (sidechains) within a session."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    query = """
        SELECT
            agent_id,
            agent_slug,
            MAX(is_sidechain) as is_sidechain,
            MIN(timestamp) as first_event,
            MAX(timestamp) as last_event,
            COUNT(*) as event_count,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read_tokens,
            SUM(cache_creation_tokens) as cache_creation_tokens
        FROM events
        WHERE session_id = ? AND agent_id IS NOT NULL
    """
    params: list[Any] = [session_id]

    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)

    query += " GROUP BY agent_id ORDER BY first_event"

    results = cursor.execute(query, params).fetchall()

    agents = []
    for row in results:
        agent = dict(row)
        agent["total_billable_tokens"] = (
            agent["input_tokens"] + agent["output_tokens"] + agent["cache_creation_tokens"]
        )
        agents.append(agent)

    return agents


def cmd_event(
    cache: CacheManager,
    session_id: str,
    uuid: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Get a specific event by its UUID."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    query = """
        SELECT e.*, sf.filepath
        FROM events e
        JOIN source_files sf ON e.source_file_id = sf.id
        WHERE e.session_id = ? AND e.uuid = ?
    """
    params: list[Any] = [session_id, uuid]

    if project_id:
        query += " AND e.project_id = ?"
        params.append(project_id)

    result = cursor.execute(query, params).fetchone()

    if not result:
        return {"error": f"Event not found: {uuid}"}

    row = dict(result)

    # Parse content JSON if present
    if row.get("message_content_json"):
        try:
            row["message_content"] = json.loads(row["message_content_json"])
        except json.JSONDecodeError:
            pass

    # Parse raw JSON
    if row.get("raw_json"):
        try:
            row["message_json"] = json.loads(row["raw_json"])
        except json.JSONDecodeError:
            row["message_json"] = None

    return row


def cmd_traverse(
    cache: CacheManager,
    session_id: str,
    uuid: str,
    direction: Literal["ancestors", "descendants", "both"] = "both",
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Traverse the event tree from a specific UUID using recursive CTEs on event_edges."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    result_uuids: set[str] = {uuid}

    # Walk ancestors via recursive CTE
    if direction in ("ancestors", "both"):
        ancestor_sql = """
            WITH RECURSIVE ancestor_walk(current_uuid) AS (
                VALUES(?)
                UNION
                SELECT ee.parent_event_uuid
                FROM event_edges ee
                INNER JOIN ancestor_walk aw ON ee.event_uuid = aw.current_uuid
                WHERE ee.session_id = ?
            )
            SELECT current_uuid FROM ancestor_walk
        """
        ancestor_params: list[Any] = [uuid, session_id]
        rows = cursor.execute(ancestor_sql, ancestor_params).fetchall()
        result_uuids.update(row[0] for row in rows)

    # Walk descendants via recursive CTE
    if direction in ("descendants", "both"):
        descendant_sql = """
            WITH RECURSIVE descendant_walk(current_uuid) AS (
                VALUES(?)
                UNION
                SELECT ee.event_uuid
                FROM event_edges ee
                INNER JOIN descendant_walk dw ON ee.parent_event_uuid = dw.current_uuid
                WHERE ee.session_id = ?
            )
            SELECT current_uuid FROM descendant_walk
        """
        descendant_params: list[Any] = [uuid, session_id]
        rows = cursor.execute(descendant_sql, descendant_params).fetchall()
        result_uuids.update(row[0] for row in rows)

    if not result_uuids:
        return []

    # Fetch full event rows for all collected UUIDs
    placeholders = ",".join("?" * len(result_uuids))
    fetch_query = f"""
        SELECT e.*, sf.filepath
        FROM events e
        JOIN source_files sf ON e.source_file_id = sf.id
        WHERE e.uuid IN ({placeholders})
          AND e.session_id = ?
    """
    fetch_params: list[Any] = list(result_uuids) + [session_id]
    if project_id:
        fetch_query += " AND e.project_id = ?"
        fetch_params.append(project_id)
    fetch_query += " ORDER BY e.timestamp"

    event_rows = cursor.execute(fetch_query, fetch_params).fetchall()

    results: list[dict[str, Any]] = []
    for row in event_rows:
        event = dict(row)
        if event.get("raw_json"):
            try:
                event["message_json"] = json.loads(event["raw_json"])
            except json.JSONDecodeError:
                event["message_json"] = None
        results.append(event)

    return results


def cmd_trajectory(
    cache: CacheManager,
    session_id: str,
    project_id: str | None = None,
    start_uuid: str | None = None,
    end_uuid: str | None = None,
    event_types: list[str] | None = None,
    role: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Iterate through a session's event trajectory."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    query = """
        SELECT e.*, sf.filepath
        FROM events e
        JOIN source_files sf ON e.source_file_id = sf.id
        WHERE e.session_id = ?
    """
    params: list[Any] = [session_id]

    if project_id:
        query += " AND e.project_id = ?"
        params.append(project_id)

    if event_types:
        placeholders = ",".join("?" * len(event_types))
        query += f" AND e.event_type IN ({placeholders})"
        params.extend(event_types)

    if role:
        query += " AND e.message_role = ?"
        params.append(role)

    query += " ORDER BY e.timestamp"

    results = cursor.execute(query, params).fetchall()
    events = [dict(row) for row in results]

    # Apply UUID range
    if start_uuid:
        start_idx = next((i for i, e in enumerate(events) if e.get("uuid") == start_uuid), 0)
        events = events[start_idx:]

    if end_uuid:
        end_idx = next(
            (i for i, e in enumerate(events) if e.get("uuid") == end_uuid), len(events) - 1
        )
        events = events[: end_idx + 1]

    if limit:
        events = events[:limit]

    # Parse message JSON
    for event in events:
        if event.get("raw_json"):
            try:
                event["message_json"] = json.loads(event["raw_json"])
            except json.JSONDecodeError:
                event["message_json"] = None

    return events


def cmd_reflect(
    cache: CacheManager,
    session_id: str,
    meta_prompt: str,
    project_id: str | None = None,
    event_types: list[str] | None = None,
    role: str | None = None,
    start_uuid: str | None = None,
    end_uuid: str | None = None,
    limit: int | None = None,
    output_schema: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run meta-prompt evaluation over session events using claude -p.

    Persists reflections and annotations to the database for future querying.
    """
    events = cmd_trajectory(
        cache,
        session_id=session_id,
        project_id=project_id,
        start_uuid=start_uuid,
        end_uuid=end_uuid,
        event_types=event_types,
        role=role,
        limit=limit,
    )

    # Determine effective project_id for persistence
    effective_project_id = project_id
    if not effective_project_id and events:
        effective_project_id = events[0].get("project_id", "unknown")

    # Persist the reflection prompt
    now = datetime.now(UTC).isoformat()
    cursor = cache.conn.cursor()
    cursor.execute(
        "INSERT INTO reflections (project_id, session_id, reflection_prompt, created_at) VALUES (?, ?, ?, ?)",
        (effective_project_id or "unknown", session_id, meta_prompt, now),
    )
    reflection_id = cursor.lastrowid

    results: list[dict[str, Any]] = []

    for event in events:
        content = event.get("message_content", "")
        if not content or not content.strip():
            continue

        # Build prompt with substitutions
        prompt = meta_prompt.replace("{{content}}", content)
        prompt = prompt.replace("{{event_type}}", event.get("event_type", ""))
        prompt = prompt.replace("{{uuid}}", event.get("uuid") or "")
        prompt = prompt.replace("{{timestamp}}", event.get("timestamp") or "")

        if output_schema:
            prompt += f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(output_schema, indent=2)}"

        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                try:
                    analysis = json.loads(result.stdout)
                except json.JSONDecodeError:
                    analysis = {"raw_output": result.stdout}
            else:
                analysis = {
                    "error": f"claude -p failed with code {result.returncode}",
                    "stderr": result.stderr,
                }

        except FileNotFoundError:
            analysis = {"error": "claude command not found"}
        except subprocess.TimeoutExpired:
            analysis = {"error": "Timeout waiting for claude response"}
        except Exception as e:
            analysis = {"error": str(e)}

        # Persist the annotation
        annotation_now = datetime.now(UTC).isoformat()
        cursor.execute(
            """INSERT INTO event_annotations
               (project_id, session_id, event_uuid, reflection_id, annotation_result, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                effective_project_id or "unknown",
                session_id,
                event.get("uuid") or "",
                reflection_id,
                json.dumps(analysis),
                annotation_now,
            ),
        )

        results.append(
            {
                "uuid": event.get("uuid"),
                "event_type": event.get("event_type"),
                "timestamp": event.get("timestamp"),
                "analysis": analysis,
            }
        )

    cache.conn.commit()
    return results


# ============================================================================
# ML Analysis Functions (used by reflect --engine)
# ============================================================================


def truncate_content(text: str, max_chars: int = ML_DEFAULT_MAX_CHARS) -> str:
    """Truncate text at a word boundary to respect model token limits.

    Args:
        text: The input text to truncate.
        max_chars: Maximum character length.

    Returns:
        Truncated text, cut at the last space before max_chars if needed.
    """
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        return truncated[:last_space] + "..."
    return truncated + "..."


def batch_items(items: list[Any], batch_size: int) -> list[list[Any]]:
    """Split a list into batches of the given size.

    Args:
        items: List to split.
        batch_size: Maximum items per batch.

    Returns:
        List of batches (sublists).
    """
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


def load_pipeline(task: str, model: str, device: str = "cpu") -> Any:
    """Load a HuggingFace transformers pipeline.

    This is the ONE exception to the top-level import rule — transformers/torch
    are heavy dependencies (~3s import time) that are only needed for --engine.
    They are injected at runtime by introspect_sessions.sh.

    Args:
        task: HuggingFace task string (e.g. 'sentiment-analysis').
        model: Model identifier (e.g. 'distilbert/distilbert-base-uncased-finetuned-sst-2-english').
        device: Device to run on (default: 'cpu').

    Returns:
        A transformers Pipeline object.
    """
    from transformers import pipeline  # noqa: E402 — deferred import for heavy ML deps

    log.info("Loading pipeline: task=%s model=%s device=%s", task, model, device)
    return pipeline(task, model=model, device=device)


def analyze_sentiment(
    messages: list[dict[str, Any]],
    model: str | None = None,
    batch_size: int = 8,
    max_chars: int = ML_DEFAULT_MAX_CHARS,
) -> list[dict[str, Any]]:
    """Run sentiment analysis on messages.

    Args:
        messages: List of message dicts with 'content' key.
        model: HuggingFace model identifier.
        batch_size: Processing batch size.
        max_chars: Max characters per message for model input.

    Returns:
        Messages enriched with 'analysis' key containing sentiment results.
    """
    if not messages:
        return []

    effective_model = model or ML_DEFAULT_MODELS["sentiment"]
    pipe = load_pipeline(ML_TASK_NAMES["sentiment"], effective_model)

    results: list[dict[str, Any]] = []
    for batch in batch_items(messages, batch_size):
        texts = [truncate_content(m.get("content", ""), max_chars) for m in batch]
        non_empty_indices = [i for i, t in enumerate(texts) if t.strip()]
        non_empty_texts = [texts[i] for i in non_empty_indices]

        predictions: list[dict[str, Any]] = []
        if non_empty_texts:
            predictions = pipe(non_empty_texts)

        pred_idx = 0
        for i, msg in enumerate(batch):
            enriched = dict(msg)
            if i in non_empty_indices:
                pred = predictions[pred_idx]
                enriched["analysis"] = {
                    "task": "sentiment",
                    "model": effective_model,
                    "label": pred["label"],
                    "score": round(pred["score"], 4),
                }
                pred_idx += 1
            else:
                enriched["analysis"] = {
                    "task": "sentiment",
                    "model": effective_model,
                    "label": "UNKNOWN",
                    "score": 0.0,
                }
            results.append(enriched)

    return results


def analyze_zero_shot(
    messages: list[dict[str, Any]],
    labels: list[str],
    model: str | None = None,
    batch_size: int = 8,
    max_chars: int = ML_DEFAULT_MAX_CHARS,
) -> list[dict[str, Any]]:
    """Run zero-shot classification with custom labels.

    Args:
        messages: List of message dicts with 'content' key.
        labels: List of classification labels (min 2).
        model: HuggingFace model identifier.
        batch_size: Processing batch size.
        max_chars: Max characters per message for model input.

    Returns:
        Messages enriched with 'analysis' key containing classification results.
    """
    if not messages:
        return []

    effective_model = model or ML_DEFAULT_MODELS["zero-shot"]
    pipe = load_pipeline(ML_TASK_NAMES["zero-shot"], effective_model)

    results: list[dict[str, Any]] = []
    for batch in batch_items(messages, batch_size):
        texts = [truncate_content(m.get("content", ""), max_chars) for m in batch]

        for msg, text in zip(batch, texts, strict=True):
            enriched = dict(msg)
            if text.strip():
                pred = pipe(text, candidate_labels=labels)
                enriched["analysis"] = {
                    "task": "zero-shot",
                    "model": effective_model,
                    "labels": dict(
                        zip(pred["labels"], [round(s, 4) for s in pred["scores"]], strict=True)
                    ),
                    "top_label": pred["labels"][0],
                    "top_score": round(pred["scores"][0], 4),
                }
            else:
                enriched["analysis"] = {
                    "task": "zero-shot",
                    "model": effective_model,
                    "labels": {},
                    "top_label": "UNKNOWN",
                    "top_score": 0.0,
                }
            results.append(enriched)

    return results


def analyze_ner(
    messages: list[dict[str, Any]],
    model: str | None = None,
    batch_size: int = 8,
    max_chars: int = ML_DEFAULT_MAX_CHARS,
) -> list[dict[str, Any]]:
    """Run Named Entity Recognition on messages.

    Args:
        messages: List of message dicts with 'content' key.
        model: HuggingFace model identifier.
        batch_size: Processing batch size.
        max_chars: Max characters per message for model input.

    Returns:
        Messages enriched with 'analysis' key containing NER entities.
    """
    if not messages:
        return []

    effective_model = model or ML_DEFAULT_MODELS["ner"]
    pipe = load_pipeline(ML_TASK_NAMES["ner"], effective_model)

    results: list[dict[str, Any]] = []
    for batch in batch_items(messages, batch_size):
        texts = [truncate_content(m.get("content", ""), max_chars) for m in batch]

        for msg, text in zip(batch, texts, strict=True):
            enriched = dict(msg)
            if text.strip():
                raw_entities = pipe(text)
                entities = [
                    {
                        "entity": e["entity"],
                        "word": e["word"],
                        "score": round(float(e["score"]), 4),
                        "start": int(e["start"]),
                        "end": int(e["end"]),
                    }
                    for e in raw_entities
                ]
                enriched["analysis"] = {
                    "task": "ner",
                    "model": effective_model,
                    "entities": entities,
                    "entity_count": len(entities),
                }
            else:
                enriched["analysis"] = {
                    "task": "ner",
                    "model": effective_model,
                    "entities": [],
                    "entity_count": 0,
                }
            results.append(enriched)

    return results


def analyze_summarize(
    messages: list[dict[str, Any]],
    model: str | None = None,
    batch_size: int = 8,
    max_chars: int = ML_DEFAULT_MAX_CHARS,
    concatenate: bool = False,
) -> list[dict[str, Any]]:
    """Run text summarization on messages.

    Args:
        messages: List of message dicts with 'content' key.
        model: HuggingFace model identifier.
        batch_size: Processing batch size.
        max_chars: Max characters per message for model input.
        concatenate: If True, concatenate all messages into one summary.

    Returns:
        Messages enriched with 'analysis' key containing summaries.
    """
    if not messages:
        return []

    effective_model = model or ML_DEFAULT_MODELS["summarize"]
    pipe = load_pipeline(ML_TASK_NAMES["summarize"], effective_model)

    if concatenate:
        combined_text = "\n\n".join(
            m.get("content", "") for m in messages if m.get("content", "").strip()
        )
        combined_text = truncate_content(combined_text, max_chars)

        if combined_text.strip():
            pred = pipe(combined_text, max_length=150, min_length=30, do_sample=False)
            summary_text = pred[0]["summary_text"]
        else:
            summary_text = ""

        return [
            {
                "role": "summary",
                "content": combined_text[:200] + "..."
                if len(combined_text) > 200
                else combined_text,
                "message_count": len(messages),
                "analysis": {
                    "task": "summarize",
                    "model": effective_model,
                    "summary": summary_text,
                    "concatenated": True,
                },
            }
        ]

    results: list[dict[str, Any]] = []
    for batch in batch_items(messages, batch_size):
        texts = [truncate_content(m.get("content", ""), max_chars) for m in batch]

        for msg, text in zip(batch, texts, strict=True):
            enriched = dict(msg)
            if text.strip() and len(text.split()) > 10:
                pred = pipe(text, max_length=150, min_length=10, do_sample=False)
                enriched["analysis"] = {
                    "task": "summarize",
                    "model": effective_model,
                    "summary": pred[0]["summary_text"],
                }
            else:
                enriched["analysis"] = {
                    "task": "summarize",
                    "model": effective_model,
                    "summary": text,
                    "note": "too_short_to_summarize",
                }
            results.append(enriched)

    return results


def cmd_reflect_ml(
    cache: CacheManager,
    session_id: str,
    engine: str,
    project_id: str | None = None,
    role: str | None = None,
    limit: int | None = None,
    model: str | None = None,
    batch_size: int = 8,
    max_chars: int = ML_DEFAULT_MAX_CHARS,
    labels: list[str] | None = None,
    concatenate: bool = False,
) -> list[dict[str, Any]]:
    """Run local ML model analysis as a reflect engine.

    Fetches messages from cache, runs through HF pipeline,
    persists to event_annotations, returns results.

    Args:
        cache: CacheManager instance.
        session_id: Session UUID.
        engine: ML engine name (sentiment, zero-shot, ner, summarize).
        project_id: Optional project filter.
        role: Optional role filter (user/assistant).
        limit: Max messages to process.
        model: Override default HuggingFace model.
        batch_size: Batch size for ML processing.
        max_chars: Max chars per message for model input.
        labels: Labels for zero-shot classification.
        concatenate: If True, concatenate for summarize engine.

    Returns:
        List of annotation dicts with uuid, event_type, timestamp, analysis.
    """
    # Fetch messages with uuid/event_type info via trajectory (richer than cmd_messages)
    events = cmd_trajectory(
        cache,
        session_id=session_id,
        project_id=project_id,
        role=role,
        limit=limit,
    )

    if not events:
        log.warning("No events found for session %s", session_id)
        return []

    # Build message dicts with content for the analyze_* functions
    messages: list[dict[str, Any]] = []
    event_map: list[dict[str, Any]] = []  # parallel list to track source events
    for event in events:
        content = event.get("message_content", "")
        if content and content.strip():
            messages.append({"content": content, "role": event.get("event_type", "")})
            event_map.append(event)

    if not messages:
        log.warning("No messages with content found for session %s", session_id)
        return []

    effective_model = model or ML_DEFAULT_MODELS.get(engine, "unknown")

    # Run the appropriate analysis
    if engine == "sentiment":
        analyzed = analyze_sentiment(
            messages, model=model, batch_size=batch_size, max_chars=max_chars
        )
    elif engine == "zero-shot":
        analyzed = analyze_zero_shot(
            messages, labels=labels or [], model=model, batch_size=batch_size, max_chars=max_chars
        )
    elif engine == "ner":
        analyzed = analyze_ner(messages, model=model, batch_size=batch_size, max_chars=max_chars)
    elif engine == "summarize":
        analyzed = analyze_summarize(
            messages,
            model=model,
            batch_size=batch_size,
            max_chars=max_chars,
            concatenate=concatenate,
        )
    else:
        log.error("Unknown ML engine: %s", engine)
        return []

    # Determine effective project_id for persistence
    effective_project_id = project_id
    if not effective_project_id and event_map:
        effective_project_id = event_map[0].get("project_id", "unknown")

    # Persist reflection record
    now = datetime.now(UTC).isoformat()
    cursor = cache.conn.cursor()
    cursor.execute(
        "INSERT INTO reflections (project_id, session_id, reflection_prompt, created_at) VALUES (?, ?, ?, ?)",
        (effective_project_id or "unknown", session_id, f"ml:{engine}:{effective_model}", now),
    )
    reflection_id = cursor.lastrowid

    # Persist annotations and build results
    results: list[dict[str, Any]] = []

    if concatenate and engine == "summarize" and analyzed:
        # Concatenated summarize returns a single result — annotate the first event
        analysis = analyzed[0].get("analysis", {})
        event = event_map[0] if event_map else {}
        annotation_now = datetime.now(UTC).isoformat()
        cursor.execute(
            """INSERT INTO event_annotations
               (project_id, session_id, event_uuid, reflection_id, annotation_result, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                effective_project_id or "unknown",
                session_id,
                event.get("uuid") or "",
                reflection_id,
                json.dumps(analysis),
                annotation_now,
            ),
        )
        results.append(
            {
                "uuid": event.get("uuid"),
                "event_type": "summary",
                "timestamp": event.get("timestamp"),
                "message_count": analyzed[0].get("message_count", len(messages)),
                "analysis": analysis,
            }
        )
    else:
        for analyzed_msg, event in zip(analyzed, event_map, strict=False):
            analysis = analyzed_msg.get("analysis", {})
            annotation_now = datetime.now(UTC).isoformat()
            cursor.execute(
                """INSERT INTO event_annotations
                   (project_id, session_id, event_uuid, reflection_id, annotation_result, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    effective_project_id or "unknown",
                    session_id,
                    event.get("uuid") or "",
                    reflection_id,
                    json.dumps(analysis),
                    annotation_now,
                ),
            )
            results.append(
                {
                    "uuid": event.get("uuid"),
                    "event_type": event.get("event_type"),
                    "timestamp": event.get("timestamp"),
                    "analysis": analysis,
                }
            )

    cache.conn.commit()
    return results


# ============================================================================
# Utility Functions
# ============================================================================


def parse_time_filter(time_str: str) -> datetime | None:
    """Parse a time filter string into a datetime."""
    if not time_str:
        return None

    time_str = time_str.strip()

    match = re.match(r"^(\d+)([mhdw])$", time_str)
    if match:
        value = int(match.group(1))
        unit = match.group(2)

        now = datetime.now(UTC)
        if unit == "m":
            delta = timedelta(minutes=value)
        elif unit == "h":
            delta = timedelta(hours=value)
        elif unit == "d":
            delta = timedelta(days=value)
        elif unit == "w":
            delta = timedelta(weeks=value)
        else:
            return None

        return now - delta

    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_output(data: Any, output_format: str = "table") -> str:
    """Format output data for display."""
    if output_format == "json":
        return json.dumps(data, indent=2, default=str)

    if output_format == "jsonl":
        if isinstance(data, dict):
            return json.dumps(data, default=str)
        return "\n".join(json.dumps(row, default=str) for row in data)

    # Table format
    if not data:
        return "No results found."

    if isinstance(data, dict):
        data = [data]

    if not data:
        return "No results found."

    columns = list(data[0].keys())

    widths = {}
    for col in columns:
        widths[col] = max(
            len(str(col)),
            max(len(str(row.get(col, ""))[:50]) for row in data),
        )

    lines = []
    header = " | ".join(str(col).ljust(widths[col])[:50] for col in columns)
    lines.append(header)
    lines.append("-" * len(header))

    for row in data:
        line = " | ".join(str(row.get(col, ""))[:50].ljust(widths[col]) for col in columns)
        lines.append(line)

    return "\n".join(lines)


# ============================================================================
# CLI Interface
# ============================================================================


def main(
    args: argparse.Namespace,
    cache: CacheManager | None = None,
    projects_path: Path | None = None,
) -> None:
    """Main entry point.

    Args:
        args: Parsed command line arguments.
        cache: Optional CacheManager instance for dependency injection (used in testing).
        projects_path: Optional projects path override (used in testing).
    """
    owns_cache = cache is None
    if owns_cache:
        cache = CacheManager()
    assert cache is not None  # Type narrowing for mypy

    if projects_path is None:
        projects_path = PROJECTS_PATH

    try:
        result: Any = None

        # Handle automatic cache management for non-cache commands
        # Cache commands manage the cache explicitly, so skip auto-update for them
        is_cache_command = args.command == "cache"
        cache_frozen = getattr(args, "cache_frozen", False)
        cache_rebuild = getattr(args, "cache_rebuild", False)

        if not is_cache_command:
            if cache_rebuild:
                # Wipe and rebuild from scratch
                log.info("Rebuilding cache from scratch (--cache-rebuild)...")
                cache.init_schema()
                cache.clear()
                cache.update(projects_path)
            elif not cache_frozen:
                # Default: incremental update (check staleness)
                ensure_cache(cache, projects_path)
                update_result = cache.update(projects_path)
                if update_result.get("files_updated", 0) > 0:
                    log.info(
                        "Cache updated: %d files processed",
                        update_result.get("files_updated", 0),
                    )
            # If cache_frozen, skip all cache updates

        # Cache commands
        if args.command == "cache":
            if args.cache_command == "init":
                result = cmd_cache_init(cache)
            elif args.cache_command == "clear":
                result = cmd_cache_clear(cache)
            elif args.cache_command == "rebuild":
                result = cmd_cache_rebuild(cache, projects_path)
            elif args.cache_command == "update":
                result = cmd_cache_update(cache, projects_path)
            elif args.cache_command == "status":
                result = cmd_cache_status(cache)

        # Query commands
        elif args.command == "projects":
            result = cmd_projects(cache)

        elif args.command == "sessions":
            result = cmd_sessions(
                cache,
                args.project_id,
                limit=args.limit,
                since=args.since,
            )

        elif args.command == "turns":
            result = cmd_turns(
                cache,
                args.session_id,
                project_id=args.project,
                event_types=args.types,
                since=args.since,
                until=args.until,
                limit=args.limit,
                offset=args.offset,
                include_content=not args.no_content,
            )

        elif args.command == "tools":
            result = cmd_tools(
                cache,
                args.session_id,
                project_id=args.project,
                tool_name=args.tool,
                detail=args.detail,
            )

        elif args.command == "search":
            result = cmd_search(
                cache,
                args.pattern,
                project_id=args.project,
                event_types=args.types,
                limit=args.limit,
            )

        elif args.command == "summary":
            result = cmd_summary(
                cache,
                args.session_id,
                project_id=args.project,
            )

        elif args.command == "cost":
            result = cmd_cost(
                cache,
                args.session_id,
                project_id=args.project,
                model=args.model,
            )

        elif args.command == "messages":
            result = cmd_messages(
                cache,
                args.session_id,
                project_id=args.project,
                role=args.role,
                limit=args.limit,
                agent_id=getattr(args, "agent", None),
            )

        elif args.command == "agents":
            result = cmd_agents(
                cache,
                args.session_id,
                project_id=args.project,
            )

        elif args.command == "event":
            result = cmd_event(
                cache,
                args.session_id,
                args.uuid,
                project_id=args.project,
            )

        elif args.command == "traverse":
            result = cmd_traverse(
                cache,
                args.session_id,
                args.uuid,
                direction=args.direction,
                project_id=args.project,
            )

        elif args.command == "trajectory":
            result = cmd_trajectory(
                cache,
                args.session_id,
                project_id=args.project,
                start_uuid=args.start,
                end_uuid=args.end,
                event_types=args.types,
                role=args.role,
                limit=args.limit,
            )

        elif args.command == "reflect":
            engine = getattr(args, "engine", None)
            if engine:
                # ML engine path — local HuggingFace models
                labels = None
                if engine == "zero-shot":
                    if not getattr(args, "labels", None):
                        log.error("--labels required for zero-shot engine")
                        return
                    labels = [lbl.strip() for lbl in args.labels.split(",")]

                result = cmd_reflect_ml(
                    cache,
                    args.session_id,
                    engine=engine,
                    project_id=args.project,
                    role=args.role,
                    limit=args.limit,
                    model=getattr(args, "ml_model", None),
                    batch_size=getattr(args, "batch_size", 8),
                    max_chars=getattr(args, "max_chars", ML_DEFAULT_MAX_CHARS),
                    labels=labels,
                    concatenate=getattr(args, "concatenate", False),
                )
            elif getattr(args, "prompt", None) or getattr(args, "prompt_file", None):
                # Existing claude -p path
                if args.prompt_file:
                    with open(args.prompt_file, encoding="utf-8") as f:
                        meta_prompt = f.read()
                else:
                    meta_prompt = args.prompt

                output_schema = None
                if args.schema:
                    output_schema = json.loads(args.schema)

                result = cmd_reflect(
                    cache,
                    args.session_id,
                    meta_prompt,
                    project_id=args.project,
                    event_types=args.types,
                    role=args.role,
                    start_uuid=args.start,
                    end_uuid=args.end,
                    limit=args.limit,
                    output_schema=output_schema,
                )
            else:
                log.error("Either --engine or --prompt/--prompt-file is required for reflect")
                return

        else:
            log.error(f"Unknown command: {args.command}")
            return

        print(format_output(result, args.format))

    except Exception as e:
        log.exception(f"Error: {e}")
        raise SystemExit(1) from e
    finally:
        if owns_cache:
            cache.close()


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(f"""\
        {SCRIPT_NAME} - Query and analyze Claude Code session logs with SQLite cache.

        Session files are stored at:
            ~/.claude/projects/{{project-path-kebab-cased}}/{{session_uuid}}.jsonl

        Cache is stored at:
            {CACHE_DB_PATH}

        Examples:
            uv run {SCRIPT_NAME}.py cache init             # Initialize cache
            uv run {SCRIPT_NAME}.py cache update           # Incremental update
            uv run {SCRIPT_NAME}.py cache status           # Show cache stats
            uv run {SCRIPT_NAME}.py projects               # List all projects
            uv run {SCRIPT_NAME}.py search "error"         # Full-text search
        """),
    )

    # Global options
    parser.add_argument("-q", "--quiet", action="store_true", help="Show only errors")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "table", "jsonl"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "-p",
        "--project",
        help="Filter to specific project ID (speeds up queries)",
    )

    # Cache control options
    cache_group = parser.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--cache-frozen",
        action="store_true",
        help="Skip automatic cache staleness check and update",
    )
    cache_group.add_argument(
        "--cache-rebuild",
        action="store_true",
        help="Wipe and rebuild cache from scratch before query",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Cache commands
    cache_parser = subparsers.add_parser("cache", help="Manage the SQLite cache")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache commands")
    cache_subparsers.add_parser("init", help="Initialize the cache database")
    cache_subparsers.add_parser("clear", help="Clear all cached data")
    cache_subparsers.add_parser("rebuild", help="Full rebuild of the cache")
    cache_subparsers.add_parser("update", help="Incremental update (only changed files)")
    cache_subparsers.add_parser("status", help="Show cache status and statistics")

    # projects command
    subparsers.add_parser("projects", help="List all projects with session counts")

    # sessions command
    sessions_parser = subparsers.add_parser("sessions", help="List sessions for a project")
    sessions_parser.add_argument("project_id", help="Project ID (kebab-cased path)")
    sessions_parser.add_argument("-n", "--limit", type=int, default=20, help="Max sessions")
    sessions_parser.add_argument("--since", help="Filter since timestamp (ISO or relative)")

    # turns command
    turns_parser = subparsers.add_parser("turns", help="Show turns in a session")
    turns_parser.add_argument("session_id", help="Session UUID")
    turns_parser.add_argument("-t", "--types", nargs="+", help="Filter event types")
    turns_parser.add_argument("--since", help="Filter events since timestamp")
    turns_parser.add_argument("--until", help="Filter events until timestamp")
    turns_parser.add_argument("-n", "--limit", type=int, default=100, help="Max turns")
    turns_parser.add_argument("--offset", type=int, default=0, help="Skip first N turns")
    turns_parser.add_argument("--no-content", action="store_true", help="Exclude content")

    # tools command
    tools_parser = subparsers.add_parser("tools", help="Show tool usage in a session")
    tools_parser.add_argument("session_id", help="Session UUID")
    tools_parser.add_argument("--detail", action="store_true", help="Show all tool calls")
    tools_parser.add_argument("--tool", help="Filter to specific tool name")

    # search command
    search_parser = subparsers.add_parser("search", help="Full-text search across sessions")
    search_parser.add_argument("pattern", help="Search pattern (FTS5 syntax)")
    search_parser.add_argument("-t", "--types", nargs="+", help="Filter event types")
    search_parser.add_argument("-n", "--limit", type=int, default=50, help="Max results")

    # summary command
    summary_parser = subparsers.add_parser("summary", help="Get session summary")
    summary_parser.add_argument("session_id", help="Session UUID")

    # cost command
    cost_parser = subparsers.add_parser("cost", help="Estimate session cost")
    cost_parser.add_argument("session_id", help="Session UUID")
    cost_parser.add_argument("--model", choices=["opus", "sonnet", "haiku"], default=None)

    # messages command
    messages_parser = subparsers.add_parser("messages", help="Extract messages")
    messages_parser.add_argument("session_id", help="Session UUID")
    messages_parser.add_argument("--role", choices=["user", "assistant"])
    messages_parser.add_argument("-n", "--limit", type=int, default=100)
    messages_parser.add_argument("--agent", help="Filter to specific agent ID")

    # agents command
    agents_parser = subparsers.add_parser("agents", help="List subagents")
    agents_parser.add_argument("session_id", help="Session UUID")

    # event command
    event_parser = subparsers.add_parser("event", help="Get event by UUID")
    event_parser.add_argument("session_id", help="Session UUID")
    event_parser.add_argument("uuid", help="Event UUID")

    # traverse command
    traverse_parser = subparsers.add_parser("traverse", help="Traverse event tree")
    traverse_parser.add_argument("session_id", help="Session UUID")
    traverse_parser.add_argument("uuid", help="Starting event UUID")
    traverse_parser.add_argument(
        "--direction", choices=["ancestors", "descendants", "both"], default="both"
    )

    # trajectory command
    trajectory_parser = subparsers.add_parser("trajectory", help="Get event trajectory")
    trajectory_parser.add_argument("session_id", help="Session UUID")
    trajectory_parser.add_argument("--start", help="Start UUID")
    trajectory_parser.add_argument("--end", help="End UUID")
    trajectory_parser.add_argument("-t", "--types", nargs="+")
    trajectory_parser.add_argument("--role", choices=["user", "assistant"])
    trajectory_parser.add_argument("-n", "--limit", type=int)

    # reflect command
    reflect_parser = subparsers.add_parser(
        "reflect", help="Meta-prompt evaluation or local ML analysis"
    )
    reflect_parser.add_argument("session_id", help="Session UUID")
    reflect_parser.add_argument("--prompt", help="Meta-prompt (use {{content}} placeholder)")
    reflect_parser.add_argument("--prompt-file", help="Read prompt from file")
    reflect_parser.add_argument("--start", help="Start UUID")
    reflect_parser.add_argument("--end", help="End UUID")
    reflect_parser.add_argument("-t", "--types", nargs="+")
    reflect_parser.add_argument("--role", choices=["user", "assistant"])
    reflect_parser.add_argument("-n", "--limit", type=int)
    reflect_parser.add_argument("--schema", help="Expected JSON output schema")
    # ML engine options
    reflect_parser.add_argument(
        "--engine",
        choices=["sentiment", "zero-shot", "summarize", "ner"],
        help="Use local ML model instead of claude -p (cheaper, faster)",
    )
    reflect_parser.add_argument(
        "--ml-model",
        help="Override default HuggingFace model for --engine",
    )
    reflect_parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size for ML processing (default: 8)",
    )
    reflect_parser.add_argument(
        "--max-chars",
        type=int,
        default=ML_DEFAULT_MAX_CHARS,
        help=f"Max chars per message for ML models (default: {ML_DEFAULT_MAX_CHARS})",
    )
    reflect_parser.add_argument(
        "--labels",
        help="Comma-separated labels for zero-shot engine",
    )
    reflect_parser.add_argument(
        "--concatenate",
        action="store_true",
        help="Concatenate all messages for summarize engine",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.ERROR if args.quiet else logging.INFO,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not args.command:
        parser.print_help()
    else:
        main(args)
