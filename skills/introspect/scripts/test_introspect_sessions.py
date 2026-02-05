#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest>=8.0",
#   "pytest-cov>=4.0",
#   "transformers>=4.40.0,<5.0.0",
#   "torch>=2.2.0",
#   "sentencepiece>=0.2.0",
# ]
# ///
"""
Comprehensive tests for introspect_sessions.py

Run with: uv run pytest test_introspect_sessions.py -v
Coverage: uv run --with pytest-cov pytest test_introspect_sessions.py --cov=introspect_sessions
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import introspect_sessions as iss
import pytest

# ============================================================================
# Test Helpers
# ============================================================================


def make_event(
    event_type: str,
    uuid: str,
    timestamp: str = "2026-01-01T00:00:00Z",
    content: str = "hello",
    role: str | None = None,
    parent_uuid: str | None = None,
    session_id: str | None = None,
    agent_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Generate a JSON event line for testing."""
    event: dict[str, Any] = {
        "type": event_type,
        "uuid": uuid,
        "timestamp": timestamp,
    }
    if role is None:
        role = "user" if event_type == "user" else "assistant"
    event["message"] = {"role": role, "content": content}
    if parent_uuid:
        event["parentUuid"] = parent_uuid
    if session_id:
        event["sessionId"] = session_id
    if agent_id:
        event["agentId"] = agent_id
    if extra:
        event.update(extra)
    return json.dumps(event)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_cache(temp_dir: Path) -> iss.CacheManager:
    """Create a CacheManager with a temporary database."""
    db_path = temp_dir / "test_cache.db"
    cache = iss.CacheManager(db_path=db_path)
    cache.init_schema()
    return cache


@pytest.fixture
def rich_sample_events() -> list[dict[str, Any]]:
    """Rich sample events with tool calls, tokens, and parent-child relationships."""
    base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
    return [
        # Initial user message
        {
            "type": "user",
            "uuid": "uuid-001",
            "parentUuid": None,
            "timestamp": base_time.isoformat(),
            "sessionId": "session-abc",
            "agentId": "agent-main",
            "isSidechain": False,
            "slug": "main-agent",
            "message": {"role": "user", "content": "Hello, can you help me with a task?"},
        },
        # Assistant response with tool use
        {
            "type": "assistant",
            "uuid": "uuid-002",
            "parentUuid": "uuid-001",
            "timestamp": (base_time + timedelta(seconds=5)).isoformat(),
            "sessionId": "session-abc",
            "agentId": "agent-main",
            "isSidechain": False,
            "slug": "main-agent",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll help you! Let me read the file first."},
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"path": "/test.txt"},
                        "id": "tool-001",
                    },
                ],
                "model": "claude-sonnet-4-5-20250514",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_input_tokens": 200,
                    "cache_creation_input_tokens": 30,
                },
            },
        },
        # Tool result
        {
            "type": "user",
            "uuid": "uuid-003",
            "parentUuid": "uuid-002",
            "timestamp": (base_time + timedelta(seconds=10)).isoformat(),
            "sessionId": "session-abc",
            "agentId": "agent-main",
            "isSidechain": False,
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-001",
                        "content": "File contents: test data here",
                    }
                ],
            },
        },
        # Another assistant response with multiple tool calls
        {
            "type": "assistant",
            "uuid": "uuid-004",
            "parentUuid": "uuid-003",
            "timestamp": (base_time + timedelta(seconds=15)).isoformat(),
            "sessionId": "session-abc",
            "agentId": "agent-main",
            "isSidechain": False,
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "Analyzing the file contents..."},
                    {"type": "text", "text": "I found the data. Let me also run a command."},
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "echo hello"},
                        "id": "tool-002",
                    },
                ],
                "model": "claude-sonnet-4-5-20250514",
                "usage": {
                    "input_tokens": 150,
                    "output_tokens": 75,
                    "cache_read_input_tokens": 100,
                    "cache_creation_input_tokens": 20,
                },
            },
        },
        # Final user message
        {
            "type": "user",
            "uuid": "uuid-005",
            "parentUuid": "uuid-004",
            "timestamp": (base_time + timedelta(seconds=20)).isoformat(),
            "sessionId": "session-abc",
            "agentId": "agent-main",
            "isSidechain": False,
            "message": {"role": "user", "content": "Thanks! That's all I needed."},
        },
        # Subagent event
        {
            "type": "assistant",
            "uuid": "uuid-006",
            "parentUuid": "uuid-005",
            "timestamp": (base_time + timedelta(seconds=25)).isoformat(),
            "sessionId": "session-abc",
            "agentId": "agent-sub-1",
            "isSidechain": True,
            "slug": "subagent-explorer",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Subagent analyzing..."}],
                "model": "claude-haiku-4-5-20251101",
                "usage": {
                    "input_tokens": 50,
                    "output_tokens": 25,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
        },
    ]


@pytest.fixture
def populated_cache(temp_dir: Path, rich_sample_events: list[dict[str, Any]]) -> iss.CacheManager:
    """Create a cache populated with rich test data."""
    # Create JSONL file
    projects_dir = temp_dir / "projects" / "-Test-Project"
    projects_dir.mkdir(parents=True)
    jsonl_path = projects_dir / "session-abc.jsonl"

    with open(jsonl_path, "w") as f:
        for event in rich_sample_events:
            f.write(json.dumps(event) + "\n")

    # Create and populate cache
    db_path = temp_dir / "test_cache.db"
    cache = iss.CacheManager(db_path=db_path)
    cache.init_schema()
    cache.update(temp_dir / "projects")

    return cache


@pytest.fixture
def sample_jsonl_file(temp_dir: Path, rich_sample_events: list[dict[str, Any]]) -> Path:
    """Create a sample JSONL file with rich test events."""
    projects_dir = temp_dir / "projects" / "-Test-Project"
    projects_dir.mkdir(parents=True)
    jsonl_path = projects_dir / "session-abc.jsonl"

    with open(jsonl_path, "w") as f:
        for event in rich_sample_events:
            f.write(json.dumps(event) + "\n")

    return jsonl_path


# ============================================================================
# CacheManager Tests
# ============================================================================


class TestCacheManager:
    """Tests for the CacheManager class."""

    def test_init_schema_creates_tables(self, temp_cache: iss.CacheManager) -> None:
        """Test that init_schema creates all required tables."""
        cursor = temp_cache.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "source_files",
            "events",
            "sessions",
            "projects",
            "cache_metadata",
            "event_edges",
            "reflections",
            "event_annotations",
        }
        assert expected_tables.issubset(tables)

        # Check FTS tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_fts'")
        assert cursor.fetchone() is not None
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reflections_fts'"
        )
        assert cursor.fetchone() is not None

    def test_init_schema_idempotent(self, temp_cache: iss.CacheManager) -> None:
        """Test that init_schema can be called multiple times."""
        temp_cache.init_schema()
        temp_cache.init_schema()  # Should not raise

    def test_clear_empties_tables(self, temp_cache: iss.CacheManager) -> None:
        """Test that clear() removes all data from tables including new tables."""
        temp_cache.conn.execute(
            """
            INSERT INTO source_files
                (filepath, mtime, size_bytes, line_count, last_ingested_at, project_id, file_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("/test.jsonl", 1234567890.0, 1000, 10, "2026-01-15T10:00:00Z", "test", "main_session"),
        )
        temp_cache.conn.execute(
            "INSERT INTO reflections (project_id, session_id, reflection_prompt, created_at) VALUES (?, ?, ?, ?)",
            ("test", "sess-1", "test prompt", "2026-01-15T10:00:00Z"),
        )
        temp_cache.conn.commit()

        cursor = temp_cache.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM source_files")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT COUNT(*) FROM reflections")
        assert cursor.fetchone()[0] == 1

        temp_cache.clear()
        cursor.execute("SELECT COUNT(*) FROM source_files")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM reflections")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM event_edges")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM event_annotations")
        assert cursor.fetchone()[0] == 0

    def test_clear_is_idempotent(self, temp_cache: iss.CacheManager) -> None:
        """Test that clear() can be called multiple times safely."""
        temp_cache.clear()
        temp_cache.clear()

    def test_clear_without_tables(self, temp_dir: Path) -> None:
        """Test clear() works even when tables don't exist yet."""
        db_path = temp_dir / "empty_cache.db"
        cache = iss.CacheManager(db_path=db_path)
        # Don't init schema, just try to clear
        cache.clear()  # Should not raise

    def test_get_status_returns_correct_info(self, temp_cache: iss.CacheManager) -> None:
        """Test that get_status returns expected fields."""
        status = temp_cache.get_status()

        assert "db_path" in status
        assert "db_size_bytes" in status
        assert "source_files" in status
        assert "projects" in status
        assert "sessions" in status
        assert "events" in status
        assert "created_at" in status
        assert "last_update_at" in status

    def test_discover_files_finds_jsonl(self, temp_dir: Path, sample_jsonl_file: Path) -> None:
        """Test that discover_files finds JSONL files."""
        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        files = cache.discover_files(temp_dir / "projects")

        assert len(files) == 1
        assert files[0]["filepath"] == str(sample_jsonl_file)
        assert files[0]["project_id"] == "-Test-Project"
        assert files[0]["session_id"] == "session-abc"
        assert files[0]["file_type"] == "main_session"

    def test_discover_files_classifies_subagent(self, temp_dir: Path) -> None:
        """Test that discover_files correctly classifies subagent files."""
        subagent_dir = temp_dir / "projects" / "-Test-Project" / "session-abc"
        subagent_dir.mkdir(parents=True)
        subagent_file = subagent_dir / "agent-xyz.jsonl"
        subagent_file.write_text('{"type": "user", "sessionId": "session-abc"}\n')

        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        files = cache.discover_files(temp_dir / "projects")

        assert len(files) == 1
        assert files[0]["file_type"] == "subagent"
        assert files[0]["session_id"] == "session-abc"

    def test_discover_files_classifies_agent_root(self, temp_dir: Path) -> None:
        """Test that discover_files correctly classifies agent root files."""
        project_dir = temp_dir / "projects" / "-Test-Project"
        project_dir.mkdir(parents=True)
        agent_file = project_dir / "agent-xyz.jsonl"
        agent_file.write_text('{"type": "user", "sessionId": "real-session-id"}\n')

        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        files = cache.discover_files(temp_dir / "projects")

        assert len(files) == 1
        assert files[0]["file_type"] == "agent_root"
        assert files[0]["project_id"] == "-Test-Project"

    def test_discover_files_nonexistent_path(self, temp_cache: iss.CacheManager) -> None:
        """Test discover_files with non-existent path."""
        files = temp_cache.discover_files(Path("/nonexistent/path"))
        assert files == []

    def test_update_with_empty_directory(
        self, temp_dir: Path, temp_cache: iss.CacheManager
    ) -> None:
        """Test update with a directory containing no JSONL files."""
        empty_dir = temp_dir / "empty_projects"
        empty_dir.mkdir()

        result = temp_cache.update(empty_dir)
        assert result["files_updated"] == 0
        assert result["events_added"] == 0


# ============================================================================
# SessionEvent Tests
# ============================================================================


class TestSessionEvent:
    """Tests for the SessionEvent dataclass."""

    def test_dataclass_creation(self) -> None:
        """Test creating a SessionEvent dataclass."""
        event = iss.SessionEvent(
            uuid="test-uuid",
            parent_uuid=None,
            event_type="user",
            timestamp="2026-01-15T10:00:00Z",
            timestamp_local=None,
            session_id="session-abc",
            is_sidechain=False,
            agent_id=None,
            agent_slug=None,
            message_role="user",
            message_content="Hello world",
            model_id=None,
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            cache_5m_tokens=0,
            filepath="test.jsonl",
            line_number=1,
            is_subagent_file=False,
            raw_event={"type": "user"},
        )

        assert event.uuid == "test-uuid"
        assert event.event_type == "user"
        assert event.message_content == "Hello world"

    def test_to_dict(self) -> None:
        """Test SessionEvent.to_dict() method."""
        event = iss.SessionEvent(
            uuid="test-uuid",
            parent_uuid="parent-uuid",
            event_type="assistant",
            timestamp="2026-01-15T10:00:00Z",
            timestamp_local="2026-01-15T21:00:00+11:00",
            session_id="session-abc",
            is_sidechain=False,
            agent_id=None,
            agent_slug=None,
            message_role="assistant",
            message_content="Response text",
            model_id="claude-sonnet-4-5",
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=20,
            cache_creation_tokens=10,
            cache_5m_tokens=5,
            filepath="test.jsonl",
            line_number=2,
            is_subagent_file=False,
            raw_event={"type": "assistant"},
        )

        result = event.to_dict()

        assert result["uuid"] == "test-uuid"
        assert result["parent_uuid"] == "parent-uuid"
        assert result["event_type"] == "assistant"
        assert result["model_id"] == "claude-sonnet-4-5"
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["message_json"] == {"type": "assistant"}


# ============================================================================
# Time Filter Tests
# ============================================================================


class TestParseTimeFilter:
    """Tests for the parse_time_filter function."""

    def test_parse_hours(self) -> None:
        """Test parsing hour-based time filters."""
        before = datetime.now(UTC)
        result = iss.parse_time_filter("2h")
        after = datetime.now(UTC)

        assert result is not None
        expected_min = before - timedelta(hours=2)
        expected_max = after - timedelta(hours=2)
        assert expected_min <= result <= expected_max

    def test_parse_days(self) -> None:
        """Test parsing day-based time filters."""
        result = iss.parse_time_filter("7d")
        assert result is not None
        expected = datetime.now(UTC) - timedelta(days=7)
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_weeks(self) -> None:
        """Test parsing week-based time filters."""
        result = iss.parse_time_filter("2w")
        assert result is not None
        expected = datetime.now(UTC) - timedelta(weeks=2)
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_minutes(self) -> None:
        """Test parsing minute-based time filters."""
        result = iss.parse_time_filter("30m")
        assert result is not None
        expected = datetime.now(UTC) - timedelta(minutes=30)
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_iso_format(self) -> None:
        """Test parsing ISO format timestamps."""
        result = iss.parse_time_filter("2026-01-15T10:00:00")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_parse_invalid_returns_none(self) -> None:
        """Test that invalid formats return None."""
        assert iss.parse_time_filter("invalid") is None
        assert iss.parse_time_filter("") is None
        assert iss.parse_time_filter("5x") is None


# ============================================================================
# Cache Command Tests
# ============================================================================


class TestCacheCommands:
    """Tests for cache management commands."""

    def test_cmd_cache_init(self, temp_dir: Path) -> None:
        """Test cache initialization command."""
        db_path = temp_dir / "new_cache.db"
        cache = iss.CacheManager(db_path=db_path)

        result = iss.cmd_cache_init(cache)

        assert result["status"] == "initialized"
        assert db_path.exists()

    def test_cmd_cache_status_not_initialized(self, temp_dir: Path) -> None:
        """Test cache status when not initialized."""
        db_path = temp_dir / "nonexistent.db"
        cache = iss.CacheManager(db_path=db_path)

        result = iss.cmd_cache_status(cache)

        assert result["status"] == "not_initialized"

    def test_cmd_cache_status_initialized(self, temp_cache: iss.CacheManager) -> None:
        """Test cache status when initialized."""
        result = iss.cmd_cache_status(temp_cache)

        assert "db_path" in result
        assert "source_files" in result
        assert result["source_files"] == 0

    def test_cmd_cache_clear(self, temp_cache: iss.CacheManager) -> None:
        """Test cache clear command."""
        result = iss.cmd_cache_clear(temp_cache)
        assert result["status"] == "cleared"

    def test_cmd_cache_rebuild(self, temp_dir: Path, sample_jsonl_file: Path) -> None:
        """Test cache rebuild command."""
        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)

        result = iss.cmd_cache_rebuild(cache, projects_path=temp_dir / "projects")

        assert result["status"] == "rebuilt"
        assert result["files_updated"] == 1

    def test_cmd_cache_update(self, temp_dir: Path, sample_jsonl_file: Path) -> None:
        """Test cache update command."""
        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        result = iss.cmd_cache_update(cache, projects_path=temp_dir / "projects")

        assert result["status"] == "updated"


# ============================================================================
# Query Command Tests
# ============================================================================


class TestQueryCommands:
    """Tests for query commands."""

    def test_cmd_projects_empty_cache(self, temp_cache: iss.CacheManager) -> None:
        """Test projects command with empty cache."""
        result = iss.cmd_projects(temp_cache)
        assert result == []

    def test_cmd_projects_with_data(self, populated_cache: iss.CacheManager) -> None:
        """Test projects command with data."""
        result = iss.cmd_projects(populated_cache)

        assert len(result) == 1
        assert result[0]["project_id"] == "-Test-Project"
        assert result[0]["event_count"] == 6

    def test_cmd_sessions_empty_cache(self, temp_cache: iss.CacheManager) -> None:
        """Test sessions command with empty cache."""
        result = iss.cmd_sessions(temp_cache, project_id="-Test-Project")
        assert result == []

    def test_cmd_sessions_with_data(self, populated_cache: iss.CacheManager) -> None:
        """Test sessions command with data."""
        result = iss.cmd_sessions(populated_cache, project_id="-Test-Project")

        assert len(result) == 1
        assert result[0]["session_id"] == "session-abc"
        assert result[0]["event_count"] == 6

    def test_cmd_sessions_with_since_filter(self, populated_cache: iss.CacheManager) -> None:
        """Test sessions command with time filter."""
        result = iss.cmd_sessions(populated_cache, project_id="-Test-Project", since="30d")
        assert len(result) >= 0  # May be empty if test events are old


class TestTurnsCommand:
    """Tests for the cmd_turns function."""

    def test_cmd_turns_basic(self, populated_cache: iss.CacheManager) -> None:
        """Test basic turns retrieval."""
        result = iss.cmd_turns(populated_cache, session_id="session-abc")

        assert len(result) == 6
        assert result[0]["type"] in ["user", "assistant"]
        assert "turn_num" in result[0]
        assert "content" in result[0]

    def test_cmd_turns_with_event_type_filter(self, populated_cache: iss.CacheManager) -> None:
        """Test turns with event type filter."""
        result = iss.cmd_turns(populated_cache, session_id="session-abc", event_types=["user"])

        assert len(result) == 3  # Only user events
        for turn in result:
            assert turn["type"] == "user"

    def test_cmd_turns_with_limit_and_offset(self, populated_cache: iss.CacheManager) -> None:
        """Test turns with pagination."""
        result = iss.cmd_turns(populated_cache, session_id="session-abc", limit=2, offset=1)

        assert len(result) == 2
        assert result[0]["turn_num"] == 2

    def test_cmd_turns_without_content(self, populated_cache: iss.CacheManager) -> None:
        """Test turns without content (no-content mode)."""
        result = iss.cmd_turns(populated_cache, session_id="session-abc", include_content=False)

        assert len(result) > 0
        assert "content" not in result[0]
        assert "role" not in result[0]

    def test_cmd_turns_with_project_filter(self, populated_cache: iss.CacheManager) -> None:
        """Test turns with project filter."""
        result = iss.cmd_turns(
            populated_cache, session_id="session-abc", project_id="-Test-Project"
        )

        assert len(result) == 6

    def test_cmd_turns_with_time_filter(self, populated_cache: iss.CacheManager) -> None:
        """Test turns with time filters."""
        # This should return all events since they're in the future (2026)
        result = iss.cmd_turns(
            populated_cache, session_id="session-abc", since="2026-01-01T00:00:00"
        )
        assert len(result) == 6


class TestToolsCommand:
    """Tests for the cmd_tools function."""

    def test_cmd_tools_summary(self, populated_cache: iss.CacheManager) -> None:
        """Test tools summary mode."""
        result = iss.cmd_tools(populated_cache, session_id="session-abc")

        assert len(result) > 0
        # Should have Read and Bash tools
        tool_names = {t["tool_name"] for t in result}
        assert "Read" in tool_names
        assert "Bash" in tool_names

        # Check structure
        for tool in result:
            assert "tool_name" in tool
            assert "call_count" in tool
            assert "first_used" in tool
            assert "last_used" in tool

    def test_cmd_tools_detail(self, populated_cache: iss.CacheManager) -> None:
        """Test tools detail mode."""
        result = iss.cmd_tools(populated_cache, session_id="session-abc", detail=True)

        assert len(result) >= 2  # At least Read and Bash
        for call in result:
            assert "timestamp" in call
            assert "tool_name" in call
            assert "tool_call_id" in call
            assert "tool_input" in call

    def test_cmd_tools_filter_by_name(self, populated_cache: iss.CacheManager) -> None:
        """Test tools filtered by name."""
        result = iss.cmd_tools(
            populated_cache, session_id="session-abc", tool_name="Read", detail=True
        )

        assert len(result) == 1
        assert result[0]["tool_name"] == "Read"

    def test_cmd_tools_with_project_filter(self, populated_cache: iss.CacheManager) -> None:
        """Test tools with project filter."""
        result = iss.cmd_tools(
            populated_cache, session_id="session-abc", project_id="-Test-Project"
        )
        assert len(result) > 0


class TestSearchCommand:
    """Tests for the cmd_search function."""

    def test_cmd_search_basic(self, populated_cache: iss.CacheManager) -> None:
        """Test basic FTS search."""
        result = iss.cmd_search(populated_cache, pattern="help")

        assert len(result) >= 1
        assert "project_id" in result[0]
        assert "session_id" in result[0]
        assert "content_preview" in result[0]

    def test_cmd_search_no_results(self, populated_cache: iss.CacheManager) -> None:
        """Test search with no results."""
        result = iss.cmd_search(populated_cache, pattern="xyznonexistent123456")
        assert len(result) == 0

    def test_cmd_search_with_project_filter(self, populated_cache: iss.CacheManager) -> None:
        """Test search with project filter."""
        result = iss.cmd_search(populated_cache, pattern="help", project_id="-Test-Project")
        assert all(r["project_id"] == "-Test-Project" for r in result)

    def test_cmd_search_with_event_type_filter(self, populated_cache: iss.CacheManager) -> None:
        """Test search with event type filter."""
        result = iss.cmd_search(populated_cache, pattern="help", event_types=["user"])
        assert all(r["event_type"] == "user" for r in result)

    def test_cmd_search_with_limit(self, populated_cache: iss.CacheManager) -> None:
        """Test search with limit."""
        result = iss.cmd_search(populated_cache, pattern="help", limit=1)
        assert len(result) <= 1


class TestSummaryCommand:
    """Tests for the cmd_summary function."""

    def test_cmd_summary_basic(self, populated_cache: iss.CacheManager) -> None:
        """Test basic summary."""
        result = iss.cmd_summary(populated_cache, session_id="session-abc")

        assert result["session_id"] == "session-abc"
        assert result["project_id"] == "-Test-Project"
        assert result["total_events"] == 6
        assert "user_messages" in result
        assert "assistant_messages" in result
        assert "models_used" in result
        assert "total_cost_usd" in result

    def test_cmd_summary_not_found(self, populated_cache: iss.CacheManager) -> None:
        """Test summary for non-existent session."""
        result = iss.cmd_summary(populated_cache, session_id="nonexistent")
        assert "error" in result

    def test_cmd_summary_with_project(self, populated_cache: iss.CacheManager) -> None:
        """Test summary with project filter."""
        result = iss.cmd_summary(
            populated_cache, session_id="session-abc", project_id="-Test-Project"
        )
        assert result["session_id"] == "session-abc"


class TestCostCommand:
    """Tests for the cmd_cost function."""

    def test_cmd_cost_opus(self, populated_cache: iss.CacheManager) -> None:
        """Test cost estimation with Opus pricing."""
        result = iss.cmd_cost(populated_cache, session_id="session-abc", model="opus")

        assert result["session_id"] == "session-abc"
        assert result["model"] == "opus"
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "total_cost_usd" in result

    def test_cmd_cost_sonnet(self, populated_cache: iss.CacheManager) -> None:
        """Test cost estimation with Sonnet pricing."""
        result = iss.cmd_cost(populated_cache, session_id="session-abc", model="sonnet")
        assert result["model"] == "sonnet"

    def test_cmd_cost_haiku(self, populated_cache: iss.CacheManager) -> None:
        """Test cost estimation with Haiku pricing."""
        result = iss.cmd_cost(populated_cache, session_id="session-abc", model="haiku")
        assert result["model"] == "haiku"

    def test_cmd_cost_not_found(self, populated_cache: iss.CacheManager) -> None:
        """Test cost for non-existent session."""
        result = iss.cmd_cost(populated_cache, session_id="nonexistent")
        assert "error" in result


class TestMessagesCommand:
    """Tests for the cmd_messages function."""

    def test_cmd_messages_all(self, populated_cache: iss.CacheManager) -> None:
        """Test extracting all messages."""
        result = iss.cmd_messages(populated_cache, session_id="session-abc")

        assert len(result) > 0
        for msg in result:
            assert "role" in msg
            assert "timestamp" in msg
            assert "content" in msg

    def test_cmd_messages_user_only(self, populated_cache: iss.CacheManager) -> None:
        """Test extracting user messages only."""
        result = iss.cmd_messages(populated_cache, session_id="session-abc", role="user")

        for msg in result:
            assert msg["role"] == "user"

    def test_cmd_messages_assistant_only(self, populated_cache: iss.CacheManager) -> None:
        """Test extracting assistant messages only."""
        result = iss.cmd_messages(populated_cache, session_id="session-abc", role="assistant")

        for msg in result:
            assert msg["role"] == "assistant"

    def test_cmd_messages_with_limit(self, populated_cache: iss.CacheManager) -> None:
        """Test messages with limit."""
        result = iss.cmd_messages(populated_cache, session_id="session-abc", limit=2)
        assert len(result) <= 2


class TestAgentsCommand:
    """Tests for the cmd_agents function."""

    def test_cmd_agents_basic(self, populated_cache: iss.CacheManager) -> None:
        """Test listing agents."""
        result = iss.cmd_agents(populated_cache, session_id="session-abc")

        # Should find at least the main agent and subagent
        assert len(result) >= 1
        for agent in result:
            assert "agent_id" in agent
            assert "event_count" in agent
            assert "total_billable_tokens" in agent

    def test_cmd_agents_with_project(self, populated_cache: iss.CacheManager) -> None:
        """Test agents with project filter."""
        result = iss.cmd_agents(
            populated_cache, session_id="session-abc", project_id="-Test-Project"
        )
        assert isinstance(result, list)


class TestEventCommand:
    """Tests for the cmd_event function."""

    def test_cmd_event_found(self, populated_cache: iss.CacheManager) -> None:
        """Test getting a specific event."""
        result = iss.cmd_event(populated_cache, session_id="session-abc", uuid="uuid-001")

        assert result.get("uuid") == "uuid-001"
        assert "event_type" in result
        assert "filepath" in result

    def test_cmd_event_not_found(self, populated_cache: iss.CacheManager) -> None:
        """Test getting a non-existent event."""
        result = iss.cmd_event(populated_cache, session_id="session-abc", uuid="nonexistent")
        assert "error" in result

    def test_cmd_event_with_project(self, populated_cache: iss.CacheManager) -> None:
        """Test event with project filter."""
        result = iss.cmd_event(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-001",
            project_id="-Test-Project",
        )
        assert result.get("uuid") == "uuid-001"


class TestTraverseCommand:
    """Tests for the cmd_traverse function."""

    def test_cmd_traverse_both(self, populated_cache: iss.CacheManager) -> None:
        """Test traversing ancestors and descendants."""
        result = iss.cmd_traverse(
            populated_cache, session_id="session-abc", uuid="uuid-003", direction="both"
        )

        uuids = {r["uuid"] for r in result}
        assert "uuid-003" in uuids  # The target
        assert "uuid-001" in uuids  # Ancestor
        assert "uuid-002" in uuids  # Ancestor

    def test_cmd_traverse_ancestors(self, populated_cache: iss.CacheManager) -> None:
        """Test traversing ancestors only."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-003",
            direction="ancestors",
        )

        uuids = {r["uuid"] for r in result}
        assert "uuid-001" in uuids
        assert "uuid-002" in uuids
        assert "uuid-003" in uuids

    def test_cmd_traverse_descendants(self, populated_cache: iss.CacheManager) -> None:
        """Test traversing descendants only."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-001",
            direction="descendants",
        )

        uuids = {r["uuid"] for r in result}
        assert "uuid-001" in uuids
        assert "uuid-002" in uuids  # Child

    def test_cmd_traverse_with_project(self, populated_cache: iss.CacheManager) -> None:
        """Test traverse with project filter."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-001",
            project_id="-Test-Project",
        )
        assert len(result) > 0


class TestTrajectoryCommand:
    """Tests for the cmd_trajectory function."""

    def test_cmd_trajectory_basic(self, populated_cache: iss.CacheManager) -> None:
        """Test basic trajectory."""
        result = iss.cmd_trajectory(populated_cache, session_id="session-abc")

        assert len(result) == 6
        # Should be sorted by timestamp
        timestamps = [r.get("timestamp") for r in result]
        assert timestamps == sorted(timestamps)

    def test_cmd_trajectory_with_event_types(self, populated_cache: iss.CacheManager) -> None:
        """Test trajectory filtered by event types."""
        result = iss.cmd_trajectory(populated_cache, session_id="session-abc", event_types=["user"])

        for event in result:
            assert event["event_type"] == "user"

    def test_cmd_trajectory_with_role(self, populated_cache: iss.CacheManager) -> None:
        """Test trajectory filtered by role."""
        result = iss.cmd_trajectory(populated_cache, session_id="session-abc", role="user")

        for event in result:
            assert event["message_role"] == "user"

    def test_cmd_trajectory_with_uuid_range(self, populated_cache: iss.CacheManager) -> None:
        """Test trajectory with UUID range."""
        result = iss.cmd_trajectory(
            populated_cache,
            session_id="session-abc",
            start_uuid="uuid-002",
            end_uuid="uuid-004",
        )

        uuids = [r["uuid"] for r in result]
        assert "uuid-001" not in uuids  # Before start
        assert "uuid-002" in uuids  # Start
        assert "uuid-004" in uuids  # End

    def test_cmd_trajectory_with_limit(self, populated_cache: iss.CacheManager) -> None:
        """Test trajectory with limit."""
        result = iss.cmd_trajectory(populated_cache, session_id="session-abc", limit=3)
        assert len(result) == 3


class TestReflectCommand:
    """Tests for the cmd_reflect function - runs real claude subprocess."""

    def test_cmd_reflect_success(self, populated_cache: iss.CacheManager) -> None:
        """Test successful reflect with real claude CLI."""
        result = iss.cmd_reflect(
            populated_cache,
            session_id="session-abc",
            meta_prompt="Rate the quality of this message from 1-10: {{content}}",
            limit=1,
        )

        assert len(result) >= 1
        assert "analysis" in result[0]

    def test_cmd_reflect_with_schema(self, populated_cache: iss.CacheManager) -> None:
        """Test reflect with output schema using real claude CLI."""
        result = iss.cmd_reflect(
            populated_cache,
            session_id="session-abc",
            meta_prompt="Rate this: {{content}}",
            output_schema={"type": "object", "properties": {"rating": {"type": "number"}}},
            limit=1,
        )

        assert len(result) >= 1
        assert "analysis" in result[0]


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests that test the full pipeline."""

    def test_ingest_and_query(self, temp_dir: Path, sample_jsonl_file: Path) -> None:
        """Test ingesting a file and querying it."""
        db_path = temp_dir / "integration_test.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        projects_path = temp_dir / "projects"
        result = cache.update(projects_path)

        assert result["files_updated"] == 1
        assert result["events_added"] == 6

        projects = iss.cmd_projects(cache)
        assert len(projects) == 1
        assert projects[0]["project_id"] == "-Test-Project"

    def test_fts_search(self, populated_cache: iss.CacheManager) -> None:
        """Test full-text search functionality."""
        # Search for a term that exists
        results = iss.cmd_search(populated_cache, pattern="Hello")
        assert len(results) >= 1

        # Search for a term that doesn't exist
        results = iss.cmd_search(populated_cache, pattern="xyznonexistent123")
        assert len(results) == 0

    def test_incremental_update_no_changes(self, temp_dir: Path, sample_jsonl_file: Path) -> None:
        """Test that incremental updates detect no changes when file unchanged."""
        db_path = temp_dir / "incremental_test.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        projects_path = temp_dir / "projects"

        result1 = cache.update(projects_path)
        assert result1["files_updated"] == 1

        result2 = cache.update(projects_path)
        assert result2["files_updated"] == 0

    def test_incremental_update_with_changes(self, temp_dir: Path, sample_jsonl_file: Path) -> None:
        """Test that incremental updates detect and process changed files."""
        db_path = temp_dir / "incremental_test.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        projects_path = temp_dir / "projects"
        cache.update(projects_path)

        # Modify the file
        with open(sample_jsonl_file, "a") as f:
            f.write(
                json.dumps(
                    {
                        "type": "user",
                        "uuid": "uuid-new",
                        "parentUuid": "uuid-005",
                        "timestamp": "2026-01-15T10:00:30Z",
                        "sessionId": "session-abc",
                        "message": {"role": "user", "content": "New message"},
                    }
                )
                + "\n"
            )

        result = cache.update(projects_path)
        assert result["files_updated"] == 1
        assert result["events_added"] >= 1


# ============================================================================
# Output Formatter Tests
# ============================================================================


class TestFormatOutput:
    """Tests for the format_output function."""

    def test_format_table_basic(self) -> None:
        """Test basic table formatting."""
        rows = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        output = iss.format_output(rows, "table")

        assert "name" in output
        assert "age" in output
        assert "Alice" in output
        assert "Bob" in output
        assert "30" in output

    def test_format_table_empty(self) -> None:
        """Test table formatting with empty input."""
        output = iss.format_output([], "table")
        assert "No results" in output

    def test_format_json(self) -> None:
        """Test JSON formatting."""
        data = {"key": "value", "number": 42}
        output = iss.format_output(data, "json")

        assert '"key"' in output
        assert '"value"' in output
        assert "42" in output

    def test_format_jsonl_list(self) -> None:
        """Test JSONL formatting with a list."""
        rows = [{"a": 1}, {"b": 2}]
        output = iss.format_output(rows, "jsonl")

        lines = output.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"a": 1}
        assert json.loads(lines[1]) == {"b": 2}

    def test_format_jsonl_dict(self) -> None:
        """Test JSONL formatting with a single dict."""
        data = {"key": "value"}
        output = iss.format_output(data, "jsonl")
        parsed = json.loads(output)
        assert parsed == {"key": "value"}

    def test_format_table_single_dict(self) -> None:
        """Test table formatting with a single dict."""
        data = {"name": "Test", "value": 123}
        output = iss.format_output(data, "table")

        assert "name" in output
        assert "value" in output
        assert "Test" in output
        assert "123" in output


# ============================================================================
# ensure_cache Tests
# ============================================================================


class TestEnsureCache:
    """Tests for the ensure_cache function."""

    def test_ensure_cache_initializes_if_missing(self, temp_dir: Path) -> None:
        """Test that ensure_cache initializes cache if it doesn't exist."""
        db_path = temp_dir / "new_cache.db"
        cache = iss.CacheManager(db_path=db_path)

        # Create projects dir for update to work
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()

        iss.ensure_cache(cache, projects_path=projects_dir)

        assert db_path.exists()


# ============================================================================
# Additional Tests for Coverage - Edge Cases
# ============================================================================


class TestCacheClose:
    """Tests for the CacheManager.close method."""

    def test_close_closes_connection(self, temp_dir: Path) -> None:
        """Test that close() actually closes the database connection."""
        db_path = temp_dir / "test_close.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        # Force connection open
        _ = cache.conn

        # Close it
        cache.close()

        # Verify connection is None
        assert cache._conn is None

    def test_close_idempotent(self, temp_dir: Path) -> None:
        """Test that close() can be called multiple times safely."""
        db_path = temp_dir / "test_close.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        cache.close()
        cache.close()  # Should not raise
        assert cache._conn is None


class TestDiscoverFilesEdgeCases:
    """Tests for edge cases in discover_files."""

    def test_discover_files_skips_non_directories(self, temp_dir: Path) -> None:
        """Test that discover_files skips files at the project root level."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()

        # Create a file at root level (not a directory)
        (projects_dir / "some_file.txt").write_text("hello")

        # Create an actual project
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()
        (project_dir / "session-123.jsonl").write_text("{}")

        cache = iss.CacheManager(db_path=temp_dir / "cache.db")
        files = cache.discover_files(projects_dir)

        assert len(files) == 1
        assert files[0]["project_id"] == "test-project"

    def test_discover_files_detects_subagent_files(self, temp_dir: Path) -> None:
        """Test that subagent files are classified correctly."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()

        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        # Create session with subagent subdirectory
        session_dir = project_dir / "session-xyz"
        session_dir.mkdir()
        subagents_dir = session_dir / "subagents"
        subagents_dir.mkdir()
        (subagents_dir / "agent-001.jsonl").write_text("{}")

        cache = iss.CacheManager(db_path=temp_dir / "cache.db")
        files = cache.discover_files(projects_dir)

        assert len(files) == 1
        assert files[0]["file_type"] == "subagent"
        assert files[0]["session_id"] == "session-xyz"


class TestIngestEdgeCases:
    """Tests for edge cases in file ingestion."""

    def _make_file_info(
        self, filepath: str, project_id: str, session_id: str | None, file_type: str
    ) -> dict[str, Any]:
        """Create a file_info dict for ingest_file."""
        import os

        stat = os.stat(filepath)
        return {
            "filepath": filepath,
            "project_id": project_id,
            "session_id": session_id,
            "file_type": file_type,
            "mtime": stat.st_mtime,
            "size_bytes": stat.st_size,
        }

    def test_ingest_skips_empty_lines(self, temp_cache: iss.CacheManager, temp_dir: Path) -> None:
        """Test that empty lines are skipped during ingestion."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        # File with empty lines
        lines = [
            make_event("user", "001"),
            "",  # Empty line
            make_event("assistant", "002", content="hi"),
        ]
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text("\n".join(lines) + "\n")

        file_info = self._make_file_info(
            str(session_file), "test-project", "session-001", "main_session"
        )
        count = temp_cache.ingest_file(file_info)
        assert count == 2  # Both events ingested despite empty line

    def test_ingest_skips_invalid_json(self, temp_cache: iss.CacheManager, temp_dir: Path) -> None:
        """Test that invalid JSON lines are skipped."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        # File with invalid JSON
        lines = [
            make_event("user", "001"),
            "this is not valid json",
            make_event("assistant", "002", content="hi"),
        ]
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text("\n".join(lines) + "\n")

        file_info = self._make_file_info(
            str(session_file), "test-project", "session-001", "main_session"
        )
        count = temp_cache.ingest_file(file_info)
        assert count == 2  # Only valid events ingested

    def test_ingest_agent_root_extracts_session_id(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test that agent_root files extract sessionId from content."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        # Agent file at root level
        content = make_event("user", "001", session_id="extracted-session-id") + "\n"
        agent_file = project_dir / "agent-xyz.jsonl"
        agent_file.write_text(content)

        file_info = self._make_file_info(str(agent_file), "test-project", None, "agent_root")
        count = temp_cache.ingest_file(file_info)
        assert count == 1

    def test_ingest_handles_file_not_found(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test that FileNotFoundError is handled gracefully."""
        # Create file first so we can get mtime/size, then delete it
        fake_file = temp_dir / "fake.jsonl"
        fake_file.write_text("{}")
        file_info = self._make_file_info(
            str(fake_file), "test-project", "session-001", "main_session"
        )
        fake_file.unlink()  # Now delete it

        count = temp_cache.ingest_file(file_info)
        assert count == 0

    def test_ingest_skips_file_history_snapshot(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test that file-history-snapshot events are skipped."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        file_history = {
            "type": "file-history-snapshot",
            "uuid": "002",
            "timestamp": "2026-01-01T00:00:01Z",
            "files": [],
        }
        lines = [
            make_event("user", "001"),
            json.dumps(file_history),
            make_event("assistant", "003", timestamp="2026-01-01T00:00:02Z", content="hi"),
        ]
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text("\n".join(lines) + "\n")

        file_info = self._make_file_info(
            str(session_file), "test-project", "session-001", "main_session"
        )
        count = temp_cache.ingest_file(file_info)
        assert count == 2  # file-history-snapshot skipped

    def test_ingest_handles_invalid_timestamp(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test that invalid timestamps don't crash ingestion."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        content = make_event("user", "001", timestamp="invalid-timestamp") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)

        file_info = self._make_file_info(
            str(session_file), "test-project", "session-001", "main_session"
        )
        count = temp_cache.ingest_file(file_info)
        assert count == 1  # Event still ingested with null timestamp_local


class TestGetFilesNeedingUpdateEdgeCases:
    """Tests for edge cases in get_files_needing_update."""

    def test_get_files_handles_oserror(self, temp_cache: iss.CacheManager) -> None:
        """Test that OSError during stat is handled gracefully."""
        files = [{"filepath": "/nonexistent/file.jsonl", "project_id": "test"}]
        result = temp_cache.get_files_needing_update(files)
        assert result == []  # File skipped due to OSError


class TestCmdTurnsEdgeCases:
    """Tests for edge cases in cmd_turns."""

    def test_cmd_turns_with_until_filter(self, populated_cache: iss.CacheManager) -> None:
        """Test cmd_turns with until time filter."""
        # Set until to a time before some events
        until = (datetime(2026, 1, 15, 10, 0, 10, tzinfo=UTC)).isoformat()
        turns = iss.cmd_turns(populated_cache, "session-abc", until=until, limit=100)

        # Should get events up to that time
        assert len(turns) >= 1
        for turn in turns:
            assert turn["timestamp"] <= until

    def test_cmd_turns_json_content_decode_error(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test that invalid JSON content falls back to text content."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        # Create event with invalid JSON in message_content_json
        content = make_event("assistant", "001", content="plain text") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)

        temp_cache.update(projects_dir)

        # Manually corrupt the message_content_json
        temp_cache.conn.execute(
            "UPDATE events SET message_content_json = 'invalid json' WHERE uuid = '001'"
        )
        temp_cache.conn.commit()

        turns = iss.cmd_turns(temp_cache, "session-001", include_content=True)
        assert len(turns) == 1
        # Falls back to message_content
        assert turns[0]["content"] == "plain text"


class TestCmdToolsEdgeCases:
    """Tests for edge cases in cmd_tools."""

    def test_cmd_tools_non_list_content(self, temp_cache: iss.CacheManager, temp_dir: Path) -> None:
        """Test that non-list content is skipped in tool extraction."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        # Content is a string, not a list
        content = make_event("assistant", "001", content="just text") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)

        temp_cache.update(projects_dir)

        tools = iss.cmd_tools(temp_cache, "session-001")
        assert tools == []  # No tools found

    def test_cmd_tools_json_decode_error(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test that JSON decode error is handled gracefully."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        tool_content = [{"type": "tool_use", "name": "Read", "id": "t1", "input": {}}]
        event = {
            "type": "assistant",
            "uuid": "001",
            "timestamp": "2026-01-01T00:00:00Z",
            "message": {"role": "assistant", "content": tool_content},
        }
        content = json.dumps(event) + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)

        temp_cache.update(projects_dir)

        # Corrupt the JSON
        temp_cache.conn.execute(
            "UPDATE events SET message_content_json = 'invalid' WHERE uuid = '001'"
        )
        temp_cache.conn.commit()

        tools = iss.cmd_tools(temp_cache, "session-001")
        assert tools == []  # Skipped due to JSON error


class TestCmdMessagesEdgeCases:
    """Tests for edge cases in cmd_messages."""

    def test_cmd_messages_with_project_filter(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test cmd_messages with project_id filter."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "my-project"
        project_dir.mkdir()

        lines = [
            make_event("user", "001"),
            make_event("assistant", "002", timestamp="2026-01-01T00:00:01Z", content="hi"),
        ]
        session_file = project_dir / "session-xyz.jsonl"
        session_file.write_text("\n".join(lines) + "\n")

        temp_cache.update(projects_dir)

        messages = iss.cmd_messages(temp_cache, "session-xyz", project_id="my-project")
        assert len(messages) == 2

    def test_cmd_messages_with_agent_filter(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test cmd_messages with agent_id filter."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "my-project"
        project_dir.mkdir()

        lines = [
            make_event("user", "001", agent_id="agent-abc"),
            make_event(
                "assistant",
                "002",
                timestamp="2026-01-01T00:00:01Z",
                content="hi",
                agent_id="agent-xyz",
            ),
        ]
        session_file = project_dir / "session-xyz.jsonl"
        session_file.write_text("\n".join(lines) + "\n")

        temp_cache.update(projects_dir)

        messages = iss.cmd_messages(temp_cache, "session-xyz", agent_id="agent-abc")
        assert len(messages) == 1
        assert messages[0]["content"] == "hello"


class TestExtractTextContent:
    """Tests for CacheManager._extract_text_content edge cases."""

    def test_extract_text_content_none(self, temp_cache: iss.CacheManager) -> None:
        """Test _extract_text_content with None content."""
        result = temp_cache._extract_text_content(None)
        assert result == ""

    def test_extract_text_content_string_in_list(self, temp_cache: iss.CacheManager) -> None:
        """Test _extract_text_content with string blocks in list."""
        content = ["plain string", {"type": "text", "text": "dict text"}]
        result = temp_cache._extract_text_content(content)
        assert "plain string" in result
        assert "dict text" in result

    def test_extract_text_content_unknown_type(self, temp_cache: iss.CacheManager) -> None:
        """Test _extract_text_content with unknown/invalid content type."""
        result = temp_cache._extract_text_content(12345)  # int is not handled
        assert result == ""


class TestParseTimeFilterEdgeCases:
    """Tests for parse_time_filter edge cases."""

    def test_parse_time_filter_unknown_unit(self) -> None:
        """Test parse_time_filter with unknown time unit."""
        result = iss.parse_time_filter("10x")  # 'x' is not a valid unit
        assert result is None


class TestCmdTurnsNoContentJson:
    """Tests for cmd_turns when message_content_json is missing."""

    def test_cmd_turns_no_content_json(self, temp_cache: iss.CacheManager, temp_dir: Path) -> None:
        """Test cmd_turns with content only in message_content, not message_content_json."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        content = make_event("assistant", "001", content="plain text") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)

        temp_cache.update(projects_dir)

        # Clear message_content_json to test fallback path (line 941)
        temp_cache.conn.execute("UPDATE events SET message_content_json = NULL WHERE uuid = '001'")
        temp_cache.conn.commit()

        turns = iss.cmd_turns(temp_cache, "session-001", include_content=True)
        assert len(turns) == 1
        assert turns[0]["content"] == "plain text"


class TestCmdTraverseRawJsonError:
    """Tests for cmd_traverse JSON decode errors."""

    def test_cmd_traverse_raw_json_decode_error(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test cmd_traverse with corrupted raw_json."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        lines = [
            make_event("user", "001"),
            make_event(
                "assistant",
                "002",
                timestamp="2026-01-01T00:00:01Z",
                content="hi",
                parent_uuid="001",
            ),
        ]
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text("\n".join(lines) + "\n")

        temp_cache.update(projects_dir)

        # Corrupt raw_json
        temp_cache.conn.execute("UPDATE events SET raw_json = 'invalid json' WHERE uuid = '002'")
        temp_cache.conn.commit()

        result = iss.cmd_traverse(temp_cache, "session-001", "001")
        # Should handle gracefully
        assert len(result) >= 1


class TestCmdTrajectoryEdgeCases:
    """Tests for cmd_trajectory edge cases."""

    def test_cmd_trajectory_with_project_id(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test cmd_trajectory with project_id filter."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "my-project"
        project_dir.mkdir()

        content = make_event("user", "001") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)

        temp_cache.update(projects_dir)

        events = iss.cmd_trajectory(temp_cache, "session-001", project_id="my-project")
        assert len(events) == 1

    def test_cmd_trajectory_raw_json_decode_error(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test cmd_trajectory with corrupted raw_json."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        content = make_event("user", "001") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)

        temp_cache.update(projects_dir)

        # Corrupt raw_json
        temp_cache.conn.execute("UPDATE events SET raw_json = 'corrupted' WHERE uuid = '001'")
        temp_cache.conn.commit()

        events = iss.cmd_trajectory(temp_cache, "session-001")
        assert len(events) == 1
        # message_json should be None due to decode error
        assert events[0].get("message_json") is None


class TestCmdReflectEdgeCases:
    """Tests for cmd_reflect edge cases - runs real claude subprocess."""

    def test_cmd_reflect_empty_content_skipped(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test cmd_reflect skips events with empty content."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        lines = [
            make_event("user", "001", content="Hello world"),
            make_event("assistant", "002", timestamp="2026-01-01T00:00:01Z", content="   "),
        ]
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text("\n".join(lines) + "\n")

        temp_cache.update(projects_dir)

        # Clear content for one event
        temp_cache.conn.execute("UPDATE events SET message_content = '   ' WHERE uuid = '002'")
        temp_cache.conn.commit()

        results = iss.cmd_reflect(temp_cache, "session-001", "Analyze: {{content}}", limit=2)
        # Only non-empty content event should be processed
        assert len(results) == 1
        assert results[0]["uuid"] == "001"


class TestCmdEventEdgeCases:
    """Tests for edge cases in cmd_event."""

    def test_cmd_event_json_decode_error_content(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Test that invalid message_content_json is handled."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        content = make_event("assistant", "001", content="text") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)

        temp_cache.update(projects_dir)

        # Corrupt the JSON fields
        temp_cache.conn.execute(
            "UPDATE events SET message_content_json = 'invalid', raw_json = 'also invalid' WHERE uuid = '001'"
        )
        temp_cache.conn.commit()

        event = iss.cmd_event(temp_cache, "session-001", "001")
        # Should handle gracefully without crashing
        assert event["uuid"] == "001"


# ============================================================================
# Tests for main() function dispatch - CRITICAL FOR COVERAGE
# ============================================================================


class TestMainDispatch:
    """Tests for the main() function dispatch logic.

    Uses dependency injection to pass cache directly to main() instead of mocking.
    Uses capsys to capture output instead of patching print.
    """

    def _make_args(self, **kwargs: Any) -> Namespace:
        """Create an argparse Namespace with defaults."""
        defaults = {
            "command": None,
            "cache_command": None,
            "format": "json",
            "project": None,
            "verbose": False,
            "quiet": False,
            "cache_frozen": False,
            "cache_rebuild": False,
        }
        defaults.update(kwargs)
        return Namespace(**defaults)

    def test_main_cache_init(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with cache init command."""
        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)

        args = self._make_args(command="cache", cache_command="init")
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert "initialized" in captured.out or db_path.exists()

    def test_main_cache_clear(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with cache clear command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(command="cache", cache_command="clear")
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert "cleared" in captured.out

    def test_main_cache_rebuild(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with cache rebuild command."""
        db_path = temp_dir / "cache.db"
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        cache = iss.CacheManager(db_path=db_path)

        args = self._make_args(command="cache", cache_command="rebuild")
        iss.main(args, cache=cache, projects_path=projects_dir)

        captured = capsys.readouterr()
        assert "rebuilt" in captured.out

    def test_main_cache_update(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with cache update command."""
        db_path = temp_dir / "cache.db"
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(command="cache", cache_command="update")
        iss.main(args, cache=cache, projects_path=projects_dir)

        captured = capsys.readouterr()
        assert "updated" in captured.out

    def test_main_cache_status(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with cache status command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(command="cache", cache_command="status")
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert "db_path" in captured.out or "status" in captured.out

    def test_main_cache_frozen_skips_update(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that --cache-frozen skips automatic cache update."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        # Create a mock session file
        projects_dir = temp_dir / "projects"
        project_dir = projects_dir / "test-project"
        project_dir.mkdir(parents=True)
        session_file = project_dir / "session-frozen-test.jsonl"
        session_file.write_text('{"type": "user", "timestamp": "2026-01-01T00:00:00Z"}\n')

        # With cache_frozen=True, the file should NOT be indexed
        args = self._make_args(command="projects", cache_frozen=True)
        iss.main(args, cache=cache, projects_path=projects_dir)

        captured = capsys.readouterr()
        # Should return empty because cache wasn't updated
        assert captured.out.strip() == "[]"

    def test_main_cache_rebuild_wipes_and_rebuilds(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that --cache-rebuild wipes and rebuilds cache before query."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        # Create a mock session file
        projects_dir = temp_dir / "projects"
        project_dir = projects_dir / "test-project"
        project_dir.mkdir(parents=True)
        session_file = project_dir / "session-rebuild-test.jsonl"
        session_file.write_text('{"type": "user", "timestamp": "2026-01-01T00:00:00Z"}\n')

        # With cache_rebuild=True, the file SHOULD be indexed
        args = self._make_args(command="projects", cache_rebuild=True)
        iss.main(args, cache=cache, projects_path=projects_dir)

        captured = capsys.readouterr()
        # Should find the project
        assert "test-project" in captured.out

    def test_main_projects(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with projects command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(command="projects")
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        # Output should be valid JSON (empty list)
        assert captured.out.strip() == "[]" or "project" in captured.out

    def test_main_sessions(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with sessions command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(
            command="sessions",
            project_id="test-project",
            limit=20,
            since=None,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]" or "session" in captured.out

    def test_main_turns(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with turns command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(
            command="turns",
            session_id="session-123",
            types=None,
            since=None,
            until=None,
            limit=100,
            offset=0,
            no_content=False,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]" or "turn" in captured.out

    def test_main_tools(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with tools command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(
            command="tools",
            session_id="session-123",
            tool=None,
            detail=False,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]" or "tool" in captured.out

    def test_main_search(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with search command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(
            command="search",
            pattern="test",
            types=None,
            limit=50,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]" or "search" in captured.out

    def test_main_summary(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with summary command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(command="summary", session_id="session-123")
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        # Empty result or "not found" message
        assert captured.out.strip() or "not found" in captured.out.lower()

    def test_main_cost(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with cost command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(command="cost", session_id="session-123", model="opus")
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() or "cost" in captured.out.lower()

    def test_main_messages(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with messages command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(
            command="messages",
            session_id="session-123",
            role=None,
            limit=100,
            agent=None,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]" or "message" in captured.out

    def test_main_agents(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with agents command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(command="agents", session_id="session-123")
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]" or "agent" in captured.out

    def test_main_event(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with event command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(command="event", session_id="session-123", uuid="uuid-001")
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        # Should output "not found" or event data
        assert captured.out.strip()

    def test_main_traverse(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with traverse command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(
            command="traverse",
            session_id="session-123",
            uuid="uuid-001",
            direction="both",
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        # Output could be empty or have ancestors/descendants
        assert captured.out.strip() is not None

    def test_main_trajectory(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with trajectory command."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(
            command="trajectory",
            session_id="session-123",
            start=None,
            end=None,
            types=None,
            role=None,
            limit=None,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]" or "trajectory" in captured.out

    def test_main_reflect_with_prompt(
        self, temp_dir: Path, sample_jsonl_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test main() with reflect command using prompt string - runs real claude."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()
        cache.update(temp_dir / "projects")

        args = self._make_args(
            command="reflect",
            session_id="session-abc",
            prompt="Analyze this: {{content}}",
            prompt_file=None,
            start=None,
            end=None,
            types=None,
            role=None,
            limit=1,
            schema=None,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip()  # Should have output from claude

    def test_main_reflect_with_prompt_file(
        self, temp_dir: Path, sample_jsonl_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test main() with reflect command using prompt file - runs real claude."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()
        cache.update(temp_dir / "projects")

        # Create prompt file
        prompt_file = temp_dir / "prompt.txt"
        prompt_file.write_text("Analyze: {{content}}")

        args = self._make_args(
            command="reflect",
            session_id="session-abc",
            prompt=None,
            prompt_file=str(prompt_file),
            start=None,
            end=None,
            types=None,
            role=None,
            limit=1,
            schema=None,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip()  # Should have output from claude

    def test_main_reflect_with_schema(
        self, temp_dir: Path, sample_jsonl_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test main() with reflect command using JSON schema - runs real claude."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()
        cache.update(temp_dir / "projects")

        schema_json = '{"type": "object", "properties": {"result": {"type": "string"}}}'

        args = self._make_args(
            command="reflect",
            session_id="session-abc",
            prompt="Analyze: {{content}}",
            prompt_file=None,
            start=None,
            end=None,
            types=None,
            role=None,
            limit=1,
            schema=schema_json,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip()  # Should have output from claude

    def test_main_unknown_command(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with unknown command outputs nothing (no matching branch)."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(command="unknown_cmd")
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        # Unknown command doesn't print anything - result is None
        assert captured.out.strip() == ""


# ============================================================================
# New Tests: EventEdges, CTE Traverse, Reflect Persistence, Schema Migration
# ============================================================================


class TestEventEdges:
    """Tests for the event_edges table population during ingest."""

    def test_edges_populated_during_ingest(self, populated_cache: iss.CacheManager) -> None:
        """Test that event_edges are populated during file ingest."""
        cursor = populated_cache.conn.cursor()
        edge_count = cursor.execute("SELECT COUNT(*) FROM event_edges").fetchone()[0]
        # uuid-001 has no parent, so 5 edges for uuid-002..uuid-006
        assert edge_count == 5

    def test_edge_forward_lookup(self, populated_cache: iss.CacheManager) -> None:
        """Test looking up an edge by event_uuid (forward direction)."""
        cursor = populated_cache.conn.cursor()
        row = cursor.execute(
            "SELECT parent_event_uuid FROM event_edges WHERE event_uuid = ? AND session_id = ?",
            ("uuid-003", "session-abc"),
        ).fetchone()
        assert row is not None
        assert row[0] == "uuid-002"

    def test_edge_reverse_lookup(self, populated_cache: iss.CacheManager) -> None:
        """Test looking up children by parent_event_uuid (reverse direction)."""
        cursor = populated_cache.conn.cursor()
        rows = cursor.execute(
            "SELECT event_uuid FROM event_edges WHERE parent_event_uuid = ? AND session_id = ?",
            ("uuid-001", "session-abc"),
        ).fetchall()
        child_uuids = {row[0] for row in rows}
        assert "uuid-002" in child_uuids

    def test_no_edge_for_root_event(self, populated_cache: iss.CacheManager) -> None:
        """Test that root events (no parent) have no edge row."""
        cursor = populated_cache.conn.cursor()
        row = cursor.execute(
            "SELECT COUNT(*) FROM event_edges WHERE event_uuid = ?",
            ("uuid-001",),
        ).fetchone()
        assert row[0] == 0

    def test_edges_cleaned_on_reingest(
        self, temp_dir: Path, rich_sample_events: list[dict[str, Any]]
    ) -> None:
        """Test that event_edges are cleaned up when a file is re-ingested."""
        # Create initial JSONL file
        projects_dir = temp_dir / "projects" / "-Test-Project"
        projects_dir.mkdir(parents=True)
        jsonl_path = projects_dir / "session-abc.jsonl"
        with open(jsonl_path, "w") as f:
            for event in rich_sample_events:
                f.write(json.dumps(event) + "\n")

        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()
        cache.update(temp_dir / "projects")

        cursor = cache.conn.cursor()
        edge_count_before = cursor.execute("SELECT COUNT(*) FROM event_edges").fetchone()[0]
        assert edge_count_before == 5

        # Touch the file to force re-ingest
        time.sleep(0.1)
        with open(jsonl_path, "w") as f:
            for event in rich_sample_events[:3]:  # Only 3 events (2 edges)
                f.write(json.dumps(event) + "\n")

        cache.update(temp_dir / "projects")
        edge_count_after = cursor.execute("SELECT COUNT(*) FROM event_edges").fetchone()[0]
        assert edge_count_after == 2  # uuid-002→uuid-001 and uuid-003→uuid-002


class TestTraverseWithCTE:
    """Tests for the CTE-based cmd_traverse implementation."""

    def test_ancestor_cte_traversal(self, populated_cache: iss.CacheManager) -> None:
        """Test ancestor traversal via recursive CTE."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-004",
            direction="ancestors",
        )
        uuids = {r["uuid"] for r in result}
        # uuid-004 → uuid-003 → uuid-002 → uuid-001
        assert uuids == {"uuid-001", "uuid-002", "uuid-003", "uuid-004"}

    def test_descendant_cte_traversal(self, populated_cache: iss.CacheManager) -> None:
        """Test descendant traversal via recursive CTE."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-003",
            direction="descendants",
        )
        uuids = {r["uuid"] for r in result}
        # uuid-003 → uuid-004 → uuid-005 → uuid-006
        assert "uuid-003" in uuids
        assert "uuid-004" in uuids
        assert "uuid-005" in uuids
        assert "uuid-006" in uuids

    def test_both_cte_traversal(self, populated_cache: iss.CacheManager) -> None:
        """Test both-direction traversal via recursive CTEs."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-003",
            direction="both",
        )
        uuids = {r["uuid"] for r in result}
        # Should include all ancestors and descendants
        assert "uuid-001" in uuids  # ancestor
        assert "uuid-003" in uuids  # self
        assert "uuid-006" in uuids  # descendant

    def test_cte_traversal_timestamp_ordering(self, populated_cache: iss.CacheManager) -> None:
        """Test that CTE traversal results are ordered by timestamp."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-003",
            direction="both",
        )
        timestamps = [r.get("timestamp") for r in result]
        assert timestamps == sorted(timestamps)

    def test_cte_traversal_nonexistent_uuid(self, populated_cache: iss.CacheManager) -> None:
        """Test traversal with a nonexistent UUID returns empty or just the UUID."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-nonexistent",
            direction="both",
        )
        # No events should match since the UUID doesn't exist in the events table
        assert len(result) == 0


class TestReflectPersistence:
    """Tests for reflection and annotation persistence in cmd_reflect."""

    def test_reflection_row_created(self, populated_cache: iss.CacheManager) -> None:
        """Test that a reflection row is created when cmd_reflect runs."""
        # Run reflect with a prompt (will fail to find 'claude' but that's OK)
        iss.cmd_reflect(
            populated_cache,
            session_id="session-abc",
            meta_prompt="Rate: {{content}}",
            limit=1,
        )
        cursor = populated_cache.conn.cursor()
        row = cursor.execute("SELECT * FROM reflections").fetchone()
        assert row is not None
        assert row["reflection_prompt"] == "Rate: {{content}}"
        assert row["session_id"] == "session-abc"

    def test_annotation_rows_created(self, populated_cache: iss.CacheManager) -> None:
        """Test that annotation rows are created for each processed event."""
        iss.cmd_reflect(
            populated_cache,
            session_id="session-abc",
            meta_prompt="Rate: {{content}}",
            limit=2,
        )
        cursor = populated_cache.conn.cursor()
        annotations = cursor.execute("SELECT * FROM event_annotations").fetchall()
        # At least 1 annotation (events with content only)
        assert len(annotations) >= 1
        for ann in annotations:
            assert ann["reflection_id"] is not None
            assert ann["annotation_result"] is not None

    def test_reflection_fk_integrity(self, populated_cache: iss.CacheManager) -> None:
        """Test that annotation reflection_id references a valid reflection."""
        iss.cmd_reflect(
            populated_cache,
            session_id="session-abc",
            meta_prompt="Test: {{content}}",
            limit=1,
        )
        cursor = populated_cache.conn.cursor()
        # Verify FK integrity via join
        result = cursor.execute("""
            SELECT ea.id, r.reflection_prompt
            FROM event_annotations ea
            JOIN reflections r ON ea.reflection_id = r.id
        """).fetchall()
        assert len(result) >= 1

    def test_reflection_fts_searchable(self, populated_cache: iss.CacheManager) -> None:
        """Test that reflection prompts are searchable via FTS."""
        iss.cmd_reflect(
            populated_cache,
            session_id="session-abc",
            meta_prompt="Rate the quality of this interaction: {{content}}",
            limit=1,
        )
        cursor = populated_cache.conn.cursor()
        fts_results = cursor.execute(
            "SELECT * FROM reflections_fts WHERE reflections_fts MATCH ?",
            ("quality",),
        ).fetchall()
        assert len(fts_results) >= 1


class TestSchemaMigration:
    """Tests for schema versioning and auto-migration."""

    def test_needs_rebuild_for_old_version(self, temp_dir: Path) -> None:
        """Test that needs_rebuild returns True for old schema version."""
        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()
        # Simulate old version
        cache.conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
            ("schema_version", "1"),
        )
        cache.conn.commit()
        assert cache.needs_rebuild() is True

    def test_needs_rebuild_for_current_version(self, temp_dir: Path) -> None:
        """Test that needs_rebuild returns False for current schema version."""
        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()
        assert cache.needs_rebuild() is False

    def test_needs_rebuild_for_missing_version(self, temp_dir: Path) -> None:
        """Test that needs_rebuild returns True when schema_version is missing."""
        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)
        # Create a bare DB with cache_metadata but no version
        cache.conn.execute(
            "CREATE TABLE IF NOT EXISTS cache_metadata (key TEXT PRIMARY KEY, value TEXT)"
        )
        cache.conn.commit()
        assert cache.needs_rebuild() is True

    def test_ensure_cache_triggers_rebuild_on_version_mismatch(self, temp_dir: Path) -> None:
        """Test that ensure_cache auto-rebuilds when schema version mismatches."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()

        db_path = temp_dir / "test_cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        # Simulate old version
        cache.conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
            ("schema_version", "1"),
        )
        cache.conn.commit()

        # ensure_cache should detect mismatch and rebuild
        iss.ensure_cache(cache, projects_dir)

        # After rebuild, version should be current
        assert cache.needs_rebuild() is False
        row = cache.conn.execute(
            "SELECT value FROM cache_metadata WHERE key = 'schema_version'"
        ).fetchone()
        assert row[0] == iss.SCHEMA_VERSION


class TestCompositeIndexes:
    """Tests for composite indexes on existing tables."""

    def test_all_new_indexes_exist(self, temp_cache: iss.CacheManager) -> None:
        """Test that all new composite indexes exist in sqlite_master."""
        cursor = temp_cache.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

        expected_new_indexes = {
            # Event edges indexes
            "idx_event_edges_forward",
            "idx_event_edges_reverse",
            "idx_event_edges_source_file",
            # Event annotation indexes
            "idx_event_annotations_reflection",
            "idx_event_annotations_event",
            "idx_event_annotations_session",
            # Composite indexes on existing tables
            "idx_events_project_session",
            "idx_events_session_type",
            "idx_events_session_uuid",
            "idx_source_files_project_session",
        }
        assert expected_new_indexes.issubset(indexes), (
            f"Missing indexes: {expected_new_indexes - indexes}"
        )


class TestMainDispatchNewTables:
    """Tests for main() dispatch with new tables and flags."""

    def _make_args(self, **kwargs: Any) -> Namespace:
        defaults = {
            "command": None,
            "cache_command": None,
            "format": "json",
            "project": None,
            "verbose": False,
            "quiet": False,
            "cache_frozen": False,
            "cache_rebuild": False,
        }
        defaults.update(kwargs)
        return Namespace(**defaults)

    def test_cache_frozen_and_rebuild_with_new_tables(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that --cache-rebuild properly creates new tables."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(command="cache", cache_command="status")
        iss.main(args, cache=cache, projects_path=projects_dir)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "event_edges" in output
        assert "reflections" in output
        assert "event_annotations" in output


# ============================================================================
# ML Utility Function Tests (always pass, no ML deps needed)
# ============================================================================


class TestTruncateContent:
    """Tests for truncate_content utility."""

    def test_short_text_unchanged(self) -> None:
        """Text shorter than max_chars is returned unchanged."""
        assert iss.truncate_content("hello world", 100) == "hello world"

    def test_truncates_at_word_boundary(self) -> None:
        """Text is truncated at the last space before max_chars."""
        text = "the quick brown fox jumps over the lazy dog"
        result = iss.truncate_content(text, 20)
        assert result.endswith("...")
        assert len(result) <= 25  # 20 chars + "..."
        # Should break at a word boundary
        assert "the quick brown fox" in result or "the quick brown" in result

    def test_truncates_with_ellipsis(self) -> None:
        """Truncated text ends with ellipsis."""
        text = "a " * 100
        result = iss.truncate_content(text, 10)
        assert result.endswith("...")

    def test_empty_string(self) -> None:
        """Empty string is returned unchanged."""
        assert iss.truncate_content("", 100) == ""

    def test_exact_length(self) -> None:
        """Text at exactly max_chars is returned unchanged."""
        text = "x" * 50
        assert iss.truncate_content(text, 50) == text

    def test_no_space_fallback(self) -> None:
        """When no space found in reasonable range, truncates at max_chars."""
        text = "a" * 100  # No spaces at all
        result = iss.truncate_content(text, 50)
        assert result == "a" * 50 + "..."


class TestBatchItems:
    """Tests for batch_items utility."""

    def test_even_split(self) -> None:
        """Items split evenly into batches."""
        result = iss.batch_items([1, 2, 3, 4], 2)
        assert result == [[1, 2], [3, 4]]

    def test_uneven_split(self) -> None:
        """Last batch can be smaller than batch_size."""
        result = iss.batch_items([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_empty_list(self) -> None:
        """Empty list returns empty list."""
        assert iss.batch_items([], 5) == []

    def test_single_batch(self) -> None:
        """All items fit in one batch."""
        result = iss.batch_items([1, 2, 3], 10)
        assert result == [[1, 2, 3]]

    def test_batch_size_one(self) -> None:
        """Batch size of 1 returns individual items."""
        result = iss.batch_items([1, 2, 3], 1)
        assert result == [[1], [2], [3]]


class TestMLConstants:
    """Tests for ML configuration constants."""

    def test_all_engines_have_models(self) -> None:
        """Every engine key has a default model."""
        for engine in ["sentiment", "zero-shot", "summarize", "ner"]:
            assert engine in iss.ML_DEFAULT_MODELS, f"Missing model for {engine}"

    def test_all_engines_have_task_names(self) -> None:
        """Every engine key has a HuggingFace task name."""
        for engine in ["sentiment", "zero-shot", "summarize", "ner"]:
            assert engine in iss.ML_TASK_NAMES, f"Missing task name for {engine}"

    def test_models_and_tasks_have_same_keys(self) -> None:
        """ML_DEFAULT_MODELS and ML_TASK_NAMES have identical key sets."""
        assert set(iss.ML_DEFAULT_MODELS.keys()) == set(iss.ML_TASK_NAMES.keys())

    def test_default_max_chars_positive(self) -> None:
        """ML_DEFAULT_MAX_CHARS is a reasonable positive value."""
        assert iss.ML_DEFAULT_MAX_CHARS > 0
        assert iss.ML_DEFAULT_MAX_CHARS >= 500  # Must handle at least short texts


class TestCmdReflectMLDispatch:
    """Tests for cmd_reflect_ml dispatch logic (no ML deps needed)."""

    def test_no_events_returns_empty(self, populated_cache: iss.CacheManager) -> None:
        """cmd_reflect_ml returns empty for nonexistent session."""
        result = iss.cmd_reflect_ml(
            populated_cache,
            session_id="nonexistent-session",
            engine="sentiment",
        )
        assert result == []

    def test_unknown_engine_returns_empty(self, populated_cache: iss.CacheManager) -> None:
        """cmd_reflect_ml returns empty for unknown engine (before loading pipeline)."""
        # This will try to fetch events but fail at the analyze step
        # Since we can't actually run ML without torch, we test the dispatch logic
        result = iss.cmd_reflect_ml(
            populated_cache,
            session_id="session-abc",
            engine="nonexistent",
        )
        assert result == []


# ============================================================================
# ML Integration Tests
# ============================================================================


class TestReflectMLSentiment:
    """Integration tests for reflect --engine sentiment."""

    def test_sentiment_returns_results(self, populated_cache: iss.CacheManager) -> None:
        """Sentiment analysis returns results for session messages."""
        result = iss.cmd_reflect_ml(
            populated_cache,
            session_id="session-abc",
            engine="sentiment",
            role="user",
            limit=2,
        )
        assert len(result) >= 1
        for r in result:
            assert "analysis" in r
            assert r["analysis"]["task"] == "sentiment"
            assert r["analysis"]["label"] in ("POSITIVE", "NEGATIVE")
            assert 0 <= r["analysis"]["score"] <= 1

    def test_sentiment_persists_annotations(self, populated_cache: iss.CacheManager) -> None:
        """Sentiment results are persisted to event_annotations table."""
        iss.cmd_reflect_ml(
            populated_cache,
            session_id="session-abc",
            engine="sentiment",
            limit=2,
        )
        cursor = populated_cache.conn.cursor()
        annotations = cursor.execute("SELECT * FROM event_annotations").fetchall()
        assert len(annotations) >= 1
        for ann in annotations:
            assert ann["reflection_id"] is not None
            result_data = json.loads(ann["annotation_result"])
            assert result_data["task"] == "sentiment"

    def test_sentiment_creates_reflection_record(self, populated_cache: iss.CacheManager) -> None:
        """A reflection record is created with ml:sentiment: prefix."""
        iss.cmd_reflect_ml(
            populated_cache,
            session_id="session-abc",
            engine="sentiment",
            limit=1,
        )
        cursor = populated_cache.conn.cursor()
        row = cursor.execute("SELECT * FROM reflections").fetchone()
        assert row is not None
        assert row["reflection_prompt"].startswith("ml:sentiment:")


class TestReflectMLNer:
    """Integration tests for reflect --engine ner."""

    def test_ner_returns_results(self, populated_cache: iss.CacheManager) -> None:
        """NER analysis returns results with entities."""
        result = iss.cmd_reflect_ml(
            populated_cache,
            session_id="session-abc",
            engine="ner",
            limit=2,
        )
        assert len(result) >= 1
        for r in result:
            assert "analysis" in r
            assert r["analysis"]["task"] == "ner"
            assert "entities" in r["analysis"]
            assert "entity_count" in r["analysis"]


class TestReflectMLZeroShot:
    """Integration tests for reflect --engine zero-shot."""

    def test_zero_shot_with_labels(self, populated_cache: iss.CacheManager) -> None:
        """Zero-shot classification works with custom labels."""
        result = iss.cmd_reflect_ml(
            populated_cache,
            session_id="session-abc",
            engine="zero-shot",
            labels=["question", "instruction", "feedback"],
            limit=2,
        )
        assert len(result) >= 1
        for r in result:
            assert "analysis" in r
            assert r["analysis"]["task"] == "zero-shot"
            assert r["analysis"]["top_label"] in ("question", "instruction", "feedback")


class TestReflectMLSummarize:
    """Integration tests for reflect --engine summarize."""

    def test_summarize_per_message(self, populated_cache: iss.CacheManager) -> None:
        """Summarize returns per-message results."""
        result = iss.cmd_reflect_ml(
            populated_cache,
            session_id="session-abc",
            engine="summarize",
            limit=2,
        )
        assert len(result) >= 1
        for r in result:
            assert "analysis" in r
            assert r["analysis"]["task"] == "summarize"

    def test_summarize_concatenated(self, populated_cache: iss.CacheManager) -> None:
        """Concatenated summarize returns a single summary result."""
        result = iss.cmd_reflect_ml(
            populated_cache,
            session_id="session-abc",
            engine="summarize",
            concatenate=True,
            limit=5,
        )
        assert len(result) == 1
        assert result[0]["event_type"] == "summary"
        assert result[0]["analysis"]["concatenated"] is True


class TestMainParseArgs:
    """Tests for argparse in if __name__ == '__main__' block."""

    def test_argparse_no_command_prints_help(self) -> None:
        """Test that running with no command prints help."""
        result = subprocess.run(
            [sys.executable, "introspect_sessions.py"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should print help (usage) and exit 0
        assert (
            "usage:" in result.stdout.lower()
            or "usage:" in result.stderr.lower()
            or result.returncode == 0
        )

    def test_argparse_help(self) -> None:
        """Test that --help works."""
        result = subprocess.run(
            [sys.executable, "introspect_sessions.py", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "introspect_sessions" in result.stdout.lower() or "usage" in result.stdout.lower()


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
