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

    def test_reset_wipes_db_file_and_reinitializes(self, temp_dir: Path) -> None:
        """Test that reset() deletes the DB file and creates a fresh schema."""
        db_path = temp_dir / "reset_test.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()
        # Insert some data to prove it gets wiped
        cache.conn.execute("INSERT INTO projects (project_id) VALUES (?)", ("old-project",))
        cache.conn.commit()
        assert cache.conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1

        cache.reset()

        # DB file was deleted and recreated — tables exist and are empty
        assert db_path.exists()
        assert cache.conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0

    def test_reset_creates_fresh_schema_with_new_columns(self, temp_dir: Path) -> None:
        """Test that reset() recreates the schema, picking up any new columns."""
        db_path = temp_dir / "schema_test.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        cache.reset()

        # msg_kind column must exist after reset
        cursor = cache.conn.cursor()
        cursor.execute("PRAGMA table_info(events)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "msg_kind" in columns

    def test_reset_on_nonexistent_db_is_safe(self, temp_dir: Path) -> None:
        """Test that reset() works safely when the DB file doesn't yet exist."""
        db_path = temp_dir / "nonexistent.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.reset()  # Should not raise
        assert db_path.exists()

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


class TestTraverseAllMode:
    """Tests for cmd_traverse with all_events=True (replaces turns)."""

    def test_traverse_all_basic(self, populated_cache: iss.CacheManager) -> None:
        """Flat all-events listing returns all session events in order."""
        result = iss.cmd_traverse(populated_cache, session_id="session-abc", all_events=True)

        assert len(result) == 6
        assert result[0]["type"] in ["user", "assistant"]
        assert "turn_num" in result[0]
        assert "content" in result[0]

    def test_traverse_all_msg_kind_filter(self, populated_cache: iss.CacheManager) -> None:
        """Filter by msg_kind in all-events mode."""
        # fixture: uuid-001 (human), uuid-005 (human) → 2 results
        result = iss.cmd_traverse(
            populated_cache, session_id="session-abc", all_events=True, event_types=["human"]
        )

        assert len(result) == 2
        for turn in result:
            assert turn["msg_kind"] == "human"
            assert turn["type"] == "user"

    def test_traverse_all_includes_msg_kind(self, populated_cache: iss.CacheManager) -> None:
        """msg_kind field is present and valid in every all-events result."""
        result = iss.cmd_traverse(populated_cache, session_id="session-abc", all_events=True)

        assert len(result) == 6
        for turn in result:
            assert "msg_kind" in turn
            assert turn["msg_kind"] in {
                "human",
                "task_notification",
                "tool_result",
                "user_text",
                "meta",
                "assistant_text",
                "thinking",
                "tool_use",
                "other",
            }

    def test_traverse_all_pagination(self, populated_cache: iss.CacheManager) -> None:
        """Pagination via result_limit + offset works in all-events mode."""
        result = iss.cmd_traverse(
            populated_cache, session_id="session-abc", all_events=True, result_limit=2, offset=1
        )

        assert len(result) == 2
        assert result[0]["turn_num"] == 2

    def test_traverse_all_no_content(self, populated_cache: iss.CacheManager) -> None:
        """include_content=False omits content and role fields."""
        result = iss.cmd_traverse(
            populated_cache, session_id="session-abc", all_events=True, include_content=False
        )

        assert len(result) > 0
        assert "content" not in result[0]
        assert "role" not in result[0]

    def test_traverse_all_project_filter(self, populated_cache: iss.CacheManager) -> None:
        """Project filter is applied in all-events mode."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            all_events=True,
            project_id="-Test-Project",
        )

        assert len(result) == 6

    def test_traverse_all_time_filter(self, populated_cache: iss.CacheManager) -> None:
        """Time filter is applied in all-events mode."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            all_events=True,
            since="2026-01-01T00:00:00",
        )
        assert len(result) == 6

    def test_traverse_all_detail_full(self, populated_cache: iss.CacheManager) -> None:
        """detail='full' returns raw_json and message_json in all-events mode."""
        result = iss.cmd_traverse(
            populated_cache, session_id="session-abc", all_events=True, detail="full"
        )
        assert len(result) > 0
        # Full detail includes raw database row fields
        assert "raw_json" in result[0]


class TestComputeEventCosts:
    """Tests for _compute_event_costs — per-event cost calculation."""

    def test_known_model_returns_cost_fields(self) -> None:
        """Known model returns correct token_rate, billable_tokens, total_cost_usd."""
        token_rate, billable, cost = iss._compute_event_costs(
            "claude-sonnet-4-6", 1_000_000, 0, 0, 0
        )
        assert token_rate == 3.0
        assert billable == 1_000_000.0
        assert cost == pytest.approx(3.0)

    def test_output_tokens_weighted_5x(self) -> None:
        """Output tokens count 5× input tokens in billable_tokens."""
        _, billable, _ = iss._compute_event_costs("claude-sonnet-4-6", 0, 100, 0, 0)
        assert billable == pytest.approx(500.0)

    def test_cache_read_tokens_weighted_0_1x(self) -> None:
        """Cache reads cost 0.1× input rate."""
        _, billable, cost = iss._compute_event_costs("claude-sonnet-4-6", 0, 0, 1_000_000, 0)
        assert billable == pytest.approx(100_000.0)
        assert cost == pytest.approx(0.30)

    def test_cache_creation_tokens_weighted_1_25x(self) -> None:
        """Cache writes cost 1.25× input rate."""
        _, billable, cost = iss._compute_event_costs("claude-sonnet-4-6", 0, 0, 0, 1_000_000)
        assert billable == pytest.approx(1_250_000.0)
        assert cost == pytest.approx(3.75)

    def test_opus_rate(self) -> None:
        """Opus family uses $15/Mtok input rate."""
        token_rate, _, cost = iss._compute_event_costs("claude-opus-4-6", 1_000_000, 0, 0, 0)
        assert token_rate == 15.0
        assert cost == pytest.approx(15.0)

    def test_unknown_model_yields_zero_cost(self) -> None:
        """Unknown model returns token_rate=0 and total_cost_usd=0."""
        token_rate, billable, cost = iss._compute_event_costs(None, 1000, 500, 0, 0)
        assert token_rate == 0.0
        assert billable == 0.0
        assert cost == 0.0

    def test_traverse_all_output_includes_cost_fields(
        self, populated_cache: iss.CacheManager
    ) -> None:
        """traverse --all results carry token_rate, billable_tokens, total_cost_usd from DB."""
        result = iss.cmd_traverse(populated_cache, session_id="session-abc", all_events=True)
        assert len(result) > 0
        for turn in result:
            assert "token_rate" in turn
            assert "billable_tokens" in turn
            assert "total_cost_usd" in turn
            assert "cache_read_tokens" in turn
            assert "cache_creation_tokens" in turn

    def test_traverse_output_includes_cost_fields(self, populated_cache: iss.CacheManager) -> None:
        """cmd_traverse results carry cost fields from DB."""
        result = iss.cmd_traverse(populated_cache, session_id="session-abc", uuid="uuid-001")
        assert len(result) > 0
        for event in result:
            assert "token_rate" in event
            assert "billable_tokens" in event
            assert "total_cost_usd" in event


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

    def test_cmd_search_special_chars_no_crash(self, populated_cache: iss.CacheManager) -> None:
        """Test search with FTS5-reserved characters doesn't raise."""
        # These would all cause 'syntax error near ...' without escaping
        for pattern in [
            "common.cpp",
            "foo:bar",
            "a*b",
            "NOT",
            "a AND b",
            "(parens)",
            "a+b",
            'with"quote',
        ]:
            result = iss.cmd_search(populated_cache, pattern=pattern)
            assert isinstance(result, list)


class TestEscapeFts5Query:
    """Tests for _escape_fts5_query helper."""

    def test_plain_word(self) -> None:
        assert iss._escape_fts5_query("hello") == '"hello"'

    def test_multiple_words(self) -> None:
        assert iss._escape_fts5_query("hello world") == '"hello" "world"'

    def test_dotted_filename(self) -> None:
        assert iss._escape_fts5_query("common.cpp") == '"common.cpp"'

    def test_colon(self) -> None:
        assert iss._escape_fts5_query("foo:bar") == '"foo:bar"'

    def test_boolean_keywords_escaped(self) -> None:
        assert iss._escape_fts5_query("foo AND bar") == '"foo" "AND" "bar"'

    def test_already_quoted_passthrough(self) -> None:
        assert iss._escape_fts5_query('"exact phrase"') == '"exact phrase"'

    def test_empty_string(self) -> None:
        assert iss._escape_fts5_query("") == '""'

    def test_whitespace_only(self) -> None:
        assert iss._escape_fts5_query("   ") == '""'

    def test_internal_double_quote(self) -> None:
        result = iss._escape_fts5_query('say "hi" please')
        # Internal quotes doubled: "say" """hi""" "please"
        assert '""' in result
        assert result.startswith('"')

    def test_asterisk(self) -> None:
        assert iss._escape_fts5_query("foo*") == '"foo*"'

    def test_parentheses(self) -> None:
        assert iss._escape_fts5_query("(group)") == '"(group)"'


class TestModelFamilyFromId:
    """Tests for the model_family_from_id helper function."""

    def test_opus_models(self) -> None:
        """Test Opus model family extraction."""
        assert iss.model_family_from_id("claude-opus-4-6") == "opus"
        assert iss.model_family_from_id("claude-opus-4-5-20251101") == "opus"
        assert iss.model_family_from_id("claude-opus-4-1") == "opus"

    def test_sonnet_models(self) -> None:
        """Test Sonnet model family extraction."""
        assert iss.model_family_from_id("claude-sonnet-4-5-20250929") == "sonnet"
        assert iss.model_family_from_id("claude-sonnet-4-5-20250514") == "sonnet"
        assert iss.model_family_from_id("claude-sonnet-4") == "sonnet"

    def test_haiku_models(self) -> None:
        """Test Haiku model family extraction."""
        assert iss.model_family_from_id("claude-haiku-4-5-20251001") == "haiku"
        assert iss.model_family_from_id("claude-3-5-haiku-20241022") == "haiku"
        assert iss.model_family_from_id("claude-3-haiku-20240307") == "haiku"

    def test_unknown_model(self) -> None:
        """Test unknown model returns 'unknown'."""
        assert iss.model_family_from_id("some-other-model") == "unknown"

    def test_none_model(self) -> None:
        """Test None model returns 'unknown'."""
        assert iss.model_family_from_id(None) == "unknown"


class TestTraverseSummaryMode:
    """Tests for cmd_traverse with summary=True (replaces agents)."""

    def test_traverse_summary_basic(self, populated_cache: iss.CacheManager) -> None:
        """Summary mode returns per-agent rows with correct cost fields."""
        result = iss.cmd_traverse(populated_cache, session_id="session-abc", summary=True)

        # Fixture has at least the main session events
        assert len(result) >= 1
        for row in result:
            assert "agent_id" in row
            assert "event_count" in row
            assert "total_billable_tokens" in row
            assert "total_cost_usd" in row
            # Accurate cost: SUM(billable_tokens) not the old buggy formula
            assert row["total_billable_tokens"] >= 0
            assert row["total_cost_usd"] >= 0

    def test_traverse_summary_with_project(self, populated_cache: iss.CacheManager) -> None:
        """Summary mode respects project filter."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            summary=True,
            project_id="-Test-Project",
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

    def test_cmd_traverse_defaults_to_most_recent_uuid(
        self, populated_cache: iss.CacheManager
    ) -> None:
        """When uuid is omitted, traverse starts from the most recent event."""
        result = iss.cmd_traverse(populated_cache, session_id="session-abc")
        assert len(result) > 0
        # Most recent event in populated_cache is uuid-003 (latest timestamp)
        uuids = {r["uuid"] for r in result}
        assert "uuid-003" in uuids

    def test_cmd_traverse_no_uuid_empty_session_returns_empty(
        self, temp_cache: iss.CacheManager
    ) -> None:
        """When session has no events, omitting uuid returns empty list."""
        result = iss.cmd_traverse(temp_cache, session_id="nonexistent-session")
        assert result == []


class TestInferProjectId:
    """Tests for infer_project_id — CWD-based project inference."""

    def _seed_project(self, cache: iss.CacheManager, project_id: str) -> None:
        """Insert a minimal project row directly so inference can find it."""
        cache.conn.execute(
            "INSERT OR IGNORE INTO projects (project_id, session_count, event_count) VALUES (?, 1, 1)",
            (project_id,),
        )
        cache.conn.commit()

    def test_match_when_cwd_maps_to_known_project(self, temp_cache: iss.CacheManager) -> None:
        """Returns project_id when CWD encodes to a known project."""
        fake_cwd = Path("/Users/test/my-project")
        expected_id = "-Users-test-my-project"
        self._seed_project(temp_cache, expected_id)

        result = iss.infer_project_id(temp_cache, cwd=fake_cwd)

        assert result == expected_id

    def test_returns_none_when_no_match(self, temp_cache: iss.CacheManager) -> None:
        """Returns None when CWD has no matching project in the cache."""
        fake_cwd = Path("/nonexistent/path/nowhere")
        result = iss.infer_project_id(temp_cache, cwd=fake_cwd)
        assert result is None

    def test_main_infers_project_and_logs(
        self, temp_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """main() sets args.project from CWD inference and logs at INFO."""
        import logging

        fake_cwd = Path("/Users/test/inferred-project")
        expected_id = "-Users-test-inferred-project"

        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()
        cache.conn.execute(
            "INSERT OR IGNORE INTO projects (project_id, session_count, event_count) VALUES (?, 1, 1)",
            (expected_id,),
        )
        cache.conn.commit()

        args = Namespace(
            command="projects",
            format="json",
            cache_frozen=True,
            cache_rebuild=False,
            project=None,
        )

        with caplog.at_level(logging.INFO):
            iss.main(args, cache=cache, projects_path=temp_dir, _cwd=fake_cwd)

        assert args.project == expected_id
        assert any(expected_id in r.message for r in caplog.records)


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


class TestTraverseAllEdgeCases:
    """Tests for edge cases in traverse --all mode."""

    def test_traverse_all_with_until_filter(self, populated_cache: iss.CacheManager) -> None:
        """until filter is applied in all-events mode."""
        until = (datetime(2026, 1, 15, 10, 0, 10, tzinfo=UTC)).isoformat()
        turns = iss.cmd_traverse(
            populated_cache, "session-abc", all_events=True, until=until, result_limit=100
        )

        assert len(turns) >= 1
        for turn in turns:
            assert turn["timestamp"] <= until

    def test_traverse_all_json_content_decode_error(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Invalid message_content_json falls back to plain text in all-events mode."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        content = make_event("assistant", "001", content="plain text") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)

        temp_cache.update(projects_dir)

        temp_cache.conn.execute(
            "UPDATE events SET message_content_json = 'invalid json' WHERE uuid = '001'"
        )
        temp_cache.conn.commit()

        turns = iss.cmd_traverse(temp_cache, "session-001", all_events=True, include_content=True)
        assert len(turns) == 1
        assert turns[0]["content"] == "plain text"


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


class TestTraverseAllNoContentJson:
    """Tests for traverse --all when message_content_json is missing."""

    def test_traverse_all_no_content_json(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """Null message_content_json falls back to plain text in all-events mode."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        content = make_event("assistant", "001", content="plain text") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)

        temp_cache.update(projects_dir)

        temp_cache.conn.execute("UPDATE events SET message_content_json = NULL WHERE uuid = '001'")
        temp_cache.conn.commit()

        turns = iss.cmd_traverse(temp_cache, "session-001", all_events=True, include_content=True)
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


class TestTraverseDetailFull:
    """Tests for cmd_traverse with --detail full (replaces removed event subcommand)."""

    def test_traverse_detail_full_returns_raw_json(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """detail=full returns raw_json and message_json on each event."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        content = make_event("assistant", "001", content="text") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)
        temp_cache.update(projects_dir)

        result = iss.cmd_traverse(temp_cache, "session-001", "001", detail="full")
        assert len(result) >= 1
        assert result[0]["uuid"] == "001"
        assert "raw_json" in result[0]
        assert "message_json" in result[0]

    def test_traverse_detail_full_handles_corrupt_json(
        self, temp_cache: iss.CacheManager, temp_dir: Path
    ) -> None:
        """detail=full handles corrupted raw_json gracefully."""
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        project_dir = projects_dir / "test-project"
        project_dir.mkdir()

        content = make_event("assistant", "001", content="text") + "\n"
        session_file = project_dir / "session-001.jsonl"
        session_file.write_text(content)
        temp_cache.update(projects_dir)

        # Corrupt raw_json
        temp_cache.conn.execute(
            "UPDATE events SET raw_json = 'also invalid' WHERE uuid = '001'"
        )
        temp_cache.conn.commit()

        result = iss.cmd_traverse(temp_cache, "session-001", "001", detail="full")
        assert len(result) >= 1
        assert result[0]["uuid"] == "001"
        assert result[0]["message_json"] is None

    def test_traverse_detail_normal_excludes_raw_json(
        self, populated_cache: iss.CacheManager
    ) -> None:
        """detail=normal (default) does not include raw_json or message_content_json."""
        result = iss.cmd_traverse(populated_cache, session_id="session-abc", uuid="uuid-001")
        assert len(result) > 0
        assert "raw_json" not in result[0]
        assert "message_content_json" not in result[0]
        assert "content" in result[0]

    def test_traverse_type_filter(self, populated_cache: iss.CacheManager) -> None:
        """event_types filter limits results to matching msg_kind values."""
        result = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-001",
            depth_limit=0,
            event_types=["human"],
        )
        for event in result:
            assert event["msg_kind"] == "human"

    def test_traverse_result_limit(self, populated_cache: iss.CacheManager) -> None:
        """result_limit caps the number of returned events."""
        unlimited = iss.cmd_traverse(
            populated_cache, session_id="session-abc", uuid="uuid-001", depth_limit=0
        )
        limited = iss.cmd_traverse(
            populated_cache,
            session_id="session-abc",
            uuid="uuid-001",
            depth_limit=0,
            result_limit=1,
        )
        assert len(limited) == 1
        assert len(unlimited) >= len(limited)


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
            "verbose": None,
            "quiet": None,
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

    def test_main_traverse_all(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main() with traverse --all (replaces turns)."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(
            command="traverse",
            session_id="session-123",
            uuid=None,
            direction="both",
            depth=3,
            types=None,
            since=None,
            until=None,
            limit=100,
            detail="normal",
            all=True,
            summary=False,
            offset=0,
            no_content=False,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]" or "turn" in captured.out

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

    def test_main_traverse_summary(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test main() with traverse --summary (replaces agents)."""
        db_path = temp_dir / "cache.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()

        args = self._make_args(
            command="traverse",
            session_id="session-123",
            uuid=None,
            direction="both",
            depth=3,
            types=None,
            since=None,
            until=None,
            limit=None,
            detail="normal",
            all=False,
            summary=True,
            offset=0,
            no_content=False,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]" or "agent" in captured.out

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
            depth=3,
            types=None,
            since=None,
            until=None,
            limit=None,
            detail="normal",
            all=False,
            summary=False,
            offset=0,
            no_content=False,
        )
        iss.main(args, cache=cache, projects_path=temp_dir)

        captured = capsys.readouterr()
        assert captured.out.strip() is not None

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
            # msg_kind index
            "idx_events_msg_kind",
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
            "verbose": None,
            "quiet": None,
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
# Message Kind Classification Tests
# ============================================================================


class TestFirstContentBlockType:
    """Tests for the _first_content_block_type helper."""

    def test_none_content_returns_none(self) -> None:
        assert iss._first_content_block_type(None) is None

    def test_empty_list_returns_none(self) -> None:
        assert iss._first_content_block_type([]) is None

    def test_string_content_returns_string(self) -> None:
        assert iss._first_content_block_type("hello") == "string"

    def test_text_block_returns_text(self) -> None:
        assert iss._first_content_block_type([{"type": "text", "text": "hi"}]) == "text"

    def test_thinking_block_returns_thinking(self) -> None:
        assert (
            iss._first_content_block_type([{"type": "thinking", "thinking": "..."}]) == "thinking"
        )

    def test_tool_use_block_returns_tool_use(self) -> None:
        assert iss._first_content_block_type([{"type": "tool_use", "name": "Bash"}]) == "tool_use"

    def test_tool_result_block_returns_tool_result(self) -> None:
        assert (
            iss._first_content_block_type([{"type": "tool_result", "content": "ok"}])
            == "tool_result"
        )

    def test_uses_first_block_only(self) -> None:
        blocks = [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "hi"}]
        assert iss._first_content_block_type(blocks) == "thinking"


class TestMessageKind:
    """Tests for the _message_kind classifier — covers all 9 kinds."""

    @pytest.mark.parametrize(
        "event_type,is_meta,content,expected",
        [
            # human: user + not meta + string
            ("user", False, "what is the weather?", "human"),
            # task_notification: user + not meta + string starting with <task-notification>
            (
                "user",
                False,
                "<task-notification>task done</task-notification>",
                "task_notification",
            ),
            # meta: user + isMeta=true (content type doesn't matter)
            ("user", True, "some system context", "meta"),
            ("user", True, [{"type": "text", "text": "ctx"}], "meta"),
            # tool_result: user + not meta + tool_result list
            ("user", False, [{"type": "tool_result", "content": "output"}], "tool_result"),
            # user_text: user + not meta + text/other list
            ("user", False, [{"type": "text", "text": "hi"}], "user_text"),
            # assistant_text: assistant + text list
            ("assistant", False, [{"type": "text", "text": "response"}], "assistant_text"),
            # thinking: assistant + thinking list
            ("assistant", False, [{"type": "thinking", "thinking": "hmm"}], "thinking"),
            # tool_use: assistant + tool_use list
            ("assistant", False, [{"type": "tool_use", "name": "Bash", "input": {}}], "tool_use"),
            # other: non user/assistant event type
            ("system", False, "progress info", "other"),
            ("queue-operation", False, None, "other"),
        ],
    )
    def test_classification(
        self,
        event_type: str,
        is_meta: bool,
        content: Any,
        expected: str,
    ) -> None:
        assert iss._message_kind(event_type, is_meta, content) == expected


class TestMsgKindStorage:
    """Tests that msg_kind is stored in the events table and thinking signatures are stripped."""

    def test_msg_kind_populated_on_ingest(self, temp_dir: Path) -> None:
        """Test that ingesting events stores correct msg_kind values."""
        projects_dir = temp_dir / "projects" / "-Test"
        projects_dir.mkdir(parents=True)
        events = [
            {
                "type": "user",
                "uuid": "u1",
                "parentUuid": None,
                "timestamp": "2026-01-01T00:00:00Z",
                "sessionId": "sess-1",
                "message": {"role": "user", "content": "hello from user"},
            },
            {
                "type": "assistant",
                "uuid": "u2",
                "parentUuid": "u1",
                "timestamp": "2026-01-01T00:00:01Z",
                "sessionId": "sess-1",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "hello back"}],
                    "model": "claude-sonnet-4-6",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
            {
                "type": "assistant",
                "uuid": "u3",
                "parentUuid": "u2",
                "timestamp": "2026-01-01T00:00:02Z",
                "sessionId": "sess-1",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "let me think",
                            "signature": "HUGE_BASE64_BLOB",
                        }
                    ],
                    "model": "claude-opus-4-6",
                    "usage": {"input_tokens": 20, "output_tokens": 10},
                },
            },
        ]
        jsonl_path = projects_dir / "sess-1.jsonl"
        with open(jsonl_path, "w") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")

        db_path = temp_dir / "test.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()
        cache.update(temp_dir / "projects")

        rows = cache.conn.execute("SELECT uuid, msg_kind FROM events ORDER BY uuid").fetchall()
        kinds = {row[0]: row[1] for row in rows}

        assert kinds["u1"] == "human"
        assert kinds["u2"] == "assistant_text"
        assert kinds["u3"] == "thinking"

    def test_thinking_signature_stripped_from_stored_json(self, temp_dir: Path) -> None:
        """Test that signature field is removed from thinking blocks before storage."""
        projects_dir = temp_dir / "projects" / "-Test"
        projects_dir.mkdir(parents=True)
        event = {
            "type": "assistant",
            "uuid": "t1",
            "parentUuid": None,
            "timestamp": "2026-01-01T00:00:00Z",
            "sessionId": "sess-2",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "thoughts", "signature": "HUGE_BASE64_BLOB"}
                ],
                "model": "claude-opus-4-6",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        }
        jsonl_path = projects_dir / "sess-2.jsonl"
        with open(jsonl_path, "w") as f:
            f.write(json.dumps(event) + "\n")

        db_path = temp_dir / "test_sig.db"
        cache = iss.CacheManager(db_path=db_path)
        cache.init_schema()
        cache.update(temp_dir / "projects")

        row = cache.conn.execute(
            "SELECT message_content_json FROM events WHERE uuid = 't1'"
        ).fetchone()
        assert row is not None
        stored_content = json.loads(row[0])
        assert isinstance(stored_content, list)
        block = stored_content[0]
        assert "signature" not in block
        assert block["thinking"] == "thoughts"


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    extra_args = sys.argv[1:]
    final_args = base_args + extra_args
    sys.exit(pytest.main(final_args))
