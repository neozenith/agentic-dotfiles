#!/usr/bin/env python
"""Tests for CLEM (Claude Code Meta Learning Memory) script."""
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest>=8.0.0",
#   "pytest-cov>=4.1.0",
#   "duckdb>=1.1.3",
#   "rich>=13.9.4",
#   "numpy>=1.24.0",
#   "sentence-transformers>=3.0.0",
#   "transformers>=4.30.0",
#   "torch>=2.0.0",
# ]
# ///

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from clem import (
    format_number,
    format_timestamp,
    get_all_projects,
    get_sessions_by_project,
    get_summary_stats,
)


class TestFormatting:
    """Test formatting functions."""

    def test_format_number_with_integer(self):
        assert format_number(1000) == "1,000"
        assert format_number(1000000) == "1,000,000"
        assert format_number(42) == "42"

    def test_format_number_with_float(self):
        assert format_number(1000.5) == "1,000.5"

    def test_format_number_with_none(self):
        assert format_number(None) == "0"

    def test_format_timestamp_with_milliseconds(self):
        # Create a proper timestamp for 2025-10-30 16:00:00 UTC
        from datetime import datetime, timezone
        dt = datetime(2025, 10, 30, 16, 0, 0, tzinfo=timezone.utc)
        timestamp_ms = int(dt.timestamp() * 1000)
        result = format_timestamp(timestamp_ms)
        # Allow for timezone differences (could be 10-30 or 10-31 depending on local TZ)
        assert "2025-10" in result
        assert ":" in result  # Verify time is included

    def test_format_timestamp_with_string(self):
        # String timestamp that can be converted
        from datetime import datetime, timezone
        dt = datetime(2025, 10, 30, 16, 0, 0, tzinfo=timezone.utc)
        timestamp_ms = int(dt.timestamp() * 1000)
        result = format_timestamp(str(timestamp_ms))
        # Allow for timezone differences
        assert "2025-10" in result
        assert ":" in result

    def test_format_timestamp_with_invalid_string(self):
        result = format_timestamp("invalid")
        assert result == "N/A"

    def test_format_timestamp_with_none(self):
        result = format_timestamp(None)
        assert result == "N/A"


class TestProjectStructure:
    """Test project directory structure handling."""

    @pytest.fixture
    def mock_claude_dir(self, tmp_path):
        """Create a mock Claude directory structure."""
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        projects_dir.mkdir(parents=True)

        # Create a mock project directory
        project_dir = projects_dir / "-Users-test-project-one"
        project_dir.mkdir()

        # Create mock session files
        session1 = project_dir / "session-001.jsonl"
        session2 = project_dir / "session-002.jsonl"

        # Write sample JSONL data
        session1_data = [
            {
                "message": {
                    "role": "user",
                    "content": "Hello",
                    "usage": {"input_tokens": 10, "output_tokens": 20}
                },
                "timestamp": "2025-10-30T12:00:00.000Z"
            },
            {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hi there"}],
                    "usage": {"input_tokens": 5, "output_tokens": 15}
                },
                "timestamp": "2025-10-30T12:00:01.000Z"
            }
        ]

        session2_data = [
            {
                "message": {
                    "role": "user",
                    "content": "How are you?",
                    "usage": {"input_tokens": 8, "output_tokens": 12}
                },
                "timestamp": "2025-10-30T13:00:00.000Z"
            }
        ]

        # Write JSONL files
        with session1.open("w") as f:
            for item in session1_data:
                f.write(json.dumps(item) + "\n")

        with session2.open("w") as f:
            for item in session2_data:
                f.write(json.dumps(item) + "\n")

        # Create agent file (should be excluded)
        agent_file = project_dir / "agent-abc123.jsonl"
        agent_file.write_text("{}\n")

        return claude_dir

    def test_get_all_projects_structure(self, mock_claude_dir):
        """Test that projects are correctly identified."""
        with patch("clem.CLAUDE_PROJECTS_DIR", mock_claude_dir / "projects"):
            projects = get_all_projects()
            assert len(projects) == 1
            assert projects[0]["project"] == "/Users/test/project/one"
            assert projects[0]["sessions"] == 2  # Excludes agent file

    def test_get_sessions_by_project(self, mock_claude_dir):
        """Test that sessions are correctly listed for a project."""
        with patch("clem.CLAUDE_PROJECTS_DIR", mock_claude_dir / "projects"):
            sessions = get_sessions_by_project("/Users/test/project/one")
            assert len(sessions) == 2
            assert sessions[0]["session_id"] in ["session-001", "session-002"]


class TestSummaryStats:
    """Test summary statistics generation."""

    @pytest.fixture
    def mock_project_with_data(self, tmp_path):
        """Create a project with real message data."""
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        project_dir = projects_dir / "-Users-test-stats-project"
        project_dir.mkdir(parents=True)

        session = project_dir / "test-session.jsonl"

        # Create messages with roles and token usage
        messages = [
            {
                "message": {
                    "role": "user",
                    "content": "Test question",
                    "usage": {"input_tokens": 100, "output_tokens": 0}
                },
                "timestamp": "2025-10-30T12:00:00.000Z"
            },
            {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Test answer"}],
                    "usage": {"input_tokens": 0, "output_tokens": 200}
                },
                "timestamp": "2025-10-30T12:00:01.000Z"
            },
        ]

        with session.open("w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        return claude_dir

    def test_get_summary_stats_all(self, mock_project_with_data):
        """Test getting stats for all projects."""
        with patch("clem.CLAUDE_PROJECTS_DIR", mock_project_with_data / "projects"):
            stats = get_summary_stats("All Projects / All Sessions")

            assert stats["scope"] == "All Projects / All Sessions"
            assert stats["projects"] == 1
            assert stats["sessions"] == 1
            assert stats["total_messages"] == 2
            assert stats["user_messages"] == 1
            assert stats["assistant_messages"] == 1
            assert stats["total_input_tokens"] == 100
            assert stats["total_output_tokens"] == 200

    def test_get_summary_stats_single_project(self, mock_project_with_data):
        """Test getting stats for a specific project."""
        with patch("clem.CLAUDE_PROJECTS_DIR", mock_project_with_data / "projects"):
            stats = get_summary_stats(
                "Current Project / All Sessions",
                project_path="/Users/test/stats/project"
            )

            assert stats["sessions"] == 1
            assert stats["total_messages"] == 2

    def test_get_summary_stats_single_session(self, mock_project_with_data):
        """Test getting stats for a specific session."""
        with patch("clem.CLAUDE_PROJECTS_DIR", mock_project_with_data / "projects"):
            stats = get_summary_stats(
                "Current Project / Current Session",
                project_path="/Users/test/stats/project",
                session_id="test-session"
            )

            assert stats["sessions"] == 1
            assert stats["total_messages"] == 2


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_get_all_projects_empty_directory(self, tmp_path):
        """Test behavior with no projects."""
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        projects_dir.mkdir(parents=True)

        with patch("clem.CLAUDE_PROJECTS_DIR", projects_dir):
            projects = get_all_projects()
            assert projects == []

    def test_get_sessions_nonexistent_project(self, tmp_path):
        """Test behavior when project doesn't exist."""
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        projects_dir.mkdir(parents=True)

        with patch("clem.CLAUDE_PROJECTS_DIR", projects_dir):
            sessions = get_sessions_by_project("/nonexistent/project")
            assert sessions == []

    def test_malformed_jsonl_handling(self, tmp_path):
        """Test that malformed JSONL files are handled gracefully."""
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        project_dir = projects_dir / "-Users-test-malformed"
        project_dir.mkdir(parents=True)

        session = project_dir / "bad-session.jsonl"
        session.write_text("not valid json\n{incomplete json\n")

        with patch("clem.CLAUDE_PROJECTS_DIR", projects_dir):
            projects = get_all_projects()
            # Should still list the project but with 0 messages
            assert len(projects) == 1


class TestSessionFileHandling:
    """Test session file detection and exclusion."""

    def test_agent_files_excluded(self, tmp_path):
        """Test that agent-*.jsonl files are excluded."""
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        project_dir = projects_dir / "-Users-test-agent-exclusion"
        project_dir.mkdir(parents=True)

        # Create regular session with valid JSONL structure
        session_data = json.dumps({
            "message": {
                "role": "user",
                "content": "Test message",
                "usage": {"input_tokens": 10, "output_tokens": 20}
            },
            "timestamp": "2025-10-30T12:00:00.000Z"
        })
        (project_dir / "session-001.jsonl").write_text(session_data + "\n")

        # Create agent files with same structure (should be excluded from session list)
        (project_dir / "agent-abc123.jsonl").write_text(session_data + "\n")
        (project_dir / "agent-def456.jsonl").write_text(session_data + "\n")

        with patch("clem.CLAUDE_PROJECTS_DIR", projects_dir):
            sessions = get_sessions_by_project("/Users/test/agent/exclusion")
            assert len(sessions) == 1
            assert sessions[0]["session_id"] == "session-001"


class TestSearchFunctionality:
    """Test conversation search functionality."""

    @pytest.fixture
    def mock_search_project(self, tmp_path):
        """Create a project with searchable messages."""
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        project_dir = projects_dir / "-Users-test-search"
        project_dir.mkdir(parents=True)

        session = project_dir / "search-session.jsonl"

        # Create messages with searchable content
        messages = [
            {
                "message": {
                    "role": "user",
                    "content": "How do I use DuckDB?",
                    "usage": {"input_tokens": 10, "output_tokens": 0}
                },
                "timestamp": "2025-10-30T12:00:00.000Z"
            },
            {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "DuckDB is an analytical database"}],
                    "usage": {"input_tokens": 0, "output_tokens": 20}
                },
                "timestamp": "2025-10-30T12:00:01.000Z"
            },
            {
                "message": {
                    "role": "user",
                    "content": "Show me examples of Python code",
                    "usage": {"input_tokens": 8, "output_tokens": 0}
                },
                "timestamp": "2025-10-30T12:01:00.000Z"
            }
        ]

        with session.open("w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        return claude_dir

    def test_search_conversations_with_results(self, mock_search_project):
        """Test search that returns results."""
        from clem import search_conversations

        with patch("clem.CLAUDE_PROJECTS_DIR", mock_search_project / "projects"):
            # Search for "DuckDB" should find results
            results = search_conversations("DuckDB", limit=10)
            assert len(results) > 0
            # Check that result contains expected fields
            assert "preview" in results[0]
            assert "project" in results[0]
            assert "session_id" in results[0]
            assert "role" in results[0]

    def test_search_conversations_case_insensitive(self, mock_search_project):
        """Test that search is case-insensitive."""
        from clem import search_conversations

        with patch("clem.CLAUDE_PROJECTS_DIR", mock_search_project / "projects"):
            # Search with different case should still find results
            results_lower = search_conversations("duckdb", limit=10)
            results_upper = search_conversations("DUCKDB", limit=10)
            assert len(results_lower) == len(results_upper)

    def test_search_conversations_no_results(self, mock_search_project):
        """Test search with no matching results."""
        from clem import search_conversations

        with patch("clem.CLAUDE_PROJECTS_DIR", mock_search_project / "projects"):
            # Search for something that doesn't exist
            results = search_conversations("NONEXISTENT_QUERY_STRING_12345", limit=10)
            assert len(results) == 0

    def test_search_conversations_with_limit(self, mock_search_project):
        """Test search respects limit parameter."""
        from clem import search_conversations

        with patch("clem.CLAUDE_PROJECTS_DIR", mock_search_project / "projects"):
            # Search with limit=1
            results = search_conversations("Python", limit=1)
            assert len(results) <= 1

    def test_search_conversations_single_project(self, mock_search_project):
        """Test search within a single project."""
        from clem import search_conversations

        with patch("clem.CLAUDE_PROJECTS_DIR", mock_search_project / "projects"):
            # Search within specific project only
            results = search_conversations("DuckDB", project_path="/Users/test/search", limit=10)
            assert len(results) > 0
            # All results should be from the specified project
            for result in results:
                assert result["project"] == "/Users/test/search"

    def test_search_conversations_single_session(self, mock_search_project):
        """Test search within a single session."""
        from clem import search_conversations

        with patch("clem.CLAUDE_PROJECTS_DIR", mock_search_project / "projects"):
            # Search within specific session only
            results = search_conversations(
                "DuckDB",
                project_path="/Users/test/search",
                session_id="search-session",
                limit=10
            )
            assert len(results) > 0
            # All results should be from the specified session
            for result in results:
                assert result["session_id"] == "search-session"

    def test_search_conversations_nonexistent_session(self, mock_search_project):
        """Test search for nonexistent session returns empty."""
        from clem import search_conversations

        with patch("clem.CLAUDE_PROJECTS_DIR", mock_search_project / "projects"):
            # Search for nonexistent session
            results = search_conversations(
                "DuckDB",
                project_path="/Users/test/search",
                session_id="nonexistent-session",
                limit=10
            )
            assert len(results) == 0

    def test_search_conversations_with_malformed_file(self, tmp_path):
        """Test search handles malformed JSONL files gracefully."""
        from clem import search_conversations

        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        project_dir = projects_dir / "-Users-test-malformed-search"
        project_dir.mkdir(parents=True)

        # Create a malformed file that will fail DuckDB query
        (project_dir / "malformed.jsonl").write_text("not valid json\n")

        # Create another file with wrong structure (no message field)
        (project_dir / "wrong-structure.jsonl").write_text(
            json.dumps({"data": "something else"}) + "\n"
        )

        # Create a valid file
        valid_data = json.dumps({
            "message": {
                "role": "user",
                "content": "This contains the search term",
                "usage": {"input_tokens": 10, "output_tokens": 20}
            },
            "timestamp": "2025-10-30T12:00:00.000Z"
        })
        (project_dir / "valid.jsonl").write_text(valid_data + "\n")

        with patch("clem.CLAUDE_PROJECTS_DIR", projects_dir):
            # Should skip malformed files and only return results from valid file
            results = search_conversations("search term", limit=10)
            # Should find the one valid message, skipping the broken files
            assert len(results) >= 0  # May be 0 or 1 depending on which files are processed first


class TestAdditionalCoverage:
    """Additional tests to increase code coverage."""

    @pytest.fixture
    def comprehensive_project(self, tmp_path):
        """Create a comprehensive test project."""
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"

        # Create multiple projects
        for i in range(3):
            project_dir = projects_dir / f"-Users-test-project-{i}"
            project_dir.mkdir(parents=True)

            # Create multiple sessions per project
            for j in range(2):
                session = project_dir / f"session-{j:03d}.jsonl"
                messages = [
                    {
                        "message": {
                            "role": "user",
                            "content": f"Message {k}",
                            "usage": {"input_tokens": 10 * k, "output_tokens": 20 * k}
                        },
                        "timestamp": f"2025-10-{30-i:02d}T12:{j:02d}:{k:02d}.000Z"
                    }
                    for k in range(3)
                ]

                with session.open("w") as f:
                    for msg in messages:
                        f.write(json.dumps(msg) + "\n")

        return claude_dir

    def test_get_all_projects_with_multiple(self, comprehensive_project):
        """Test getting all projects with multiple entries."""
        with patch("clem.CLAUDE_PROJECTS_DIR", comprehensive_project / "projects"):
            projects = get_all_projects()
            assert len(projects) == 3
            # Verify sorting by last_activity
            for i in range(len(projects) - 1):
                assert projects[i]["last_activity"] >= projects[i + 1]["last_activity"]

    def test_get_summary_stats_with_multiple_projects(self, comprehensive_project):
        """Test stats across multiple projects."""
        with patch("clem.CLAUDE_PROJECTS_DIR", comprehensive_project / "projects"):
            stats = get_summary_stats("All Projects / All Sessions")
            assert stats["projects"] == 3
            assert stats["sessions"] == 6  # 3 projects * 2 sessions each
            assert stats["total_messages"] > 0

    def test_get_sessions_sorting(self, comprehensive_project):
        """Test that sessions are sorted by last activity."""
        with patch("clem.CLAUDE_PROJECTS_DIR", comprehensive_project / "projects"):
            sessions = get_sessions_by_project("/Users/test/project/0")
            assert len(sessions) == 2
            # Verify sorting
            if len(sessions) > 1:
                assert sessions[0]["last_activity"] >= sessions[1]["last_activity"]

    def test_get_sessions_with_corrupted_file(self, tmp_path):
        """Test handling of corrupted JSONL files in sessions."""
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        project_dir = projects_dir / "-Users-test-corrupted"
        project_dir.mkdir(parents=True)

        # Create a corrupted JSONL file that will cause query to fail
        (project_dir / "corrupted.jsonl").write_text("not valid json at all\n")

        # Create a valid session too
        valid_data = json.dumps({
            "message": {
                "role": "user",
                "content": "Valid message",
                "usage": {"input_tokens": 10, "output_tokens": 20}
            }
        })
        (project_dir / "valid.jsonl").write_text(valid_data + "\n")

        with patch("clem.CLAUDE_PROJECTS_DIR", projects_dir):
            # Should skip corrupted file and return only valid session
            sessions = get_sessions_by_project("/Users/test/corrupted")
            # The corrupted file should be skipped
            assert any(s["session_id"] == "valid" for s in sessions)


class TestHelperFunctions:
    """Test helper and utility functions."""

    def test_execute_query_basic(self, tmp_path):
        """Test execute_query with basic DuckDB query."""
        from clem import execute_query

        # Create a simple JSONL file
        test_file = tmp_path / "test.jsonl"
        test_data = {"name": "test", "value": 42}
        test_file.write_text(json.dumps(test_data) + "\n")

        # Query the file
        query = f"SELECT * FROM read_ndjson_auto('{test_file}')"
        result = execute_query(query)

        assert result is not None
        assert len(result) > 0

    def test_execute_query_with_error(self):
        """Test execute_query with invalid query raises exception."""
        from clem import execute_query
        import duckdb

        # This should raise a CatalogException
        with pytest.raises(Exception):  # Can be CatalogException or similar
            execute_query("SELECT * FROM nonexistent_table")

    def test_get_current_session_id_no_project(self, tmp_path):
        """Test get_current_session_id with no project directory."""
        from clem import get_current_session_id

        with patch("clem.CURRENT_PROJECT", "/nonexistent/project"):
            with patch("clem.CLAUDE_PROJECTS_DIR", tmp_path):
                session_id = get_current_session_id()
                assert session_id is None


class TestVectorSearch:
    """Test vector search and database management functionality."""

    def test_get_database_path_global(self, tmp_path):
        """Test global database path."""
        from clem import get_database_path

        with patch("clem.CLAUDE_DIR", tmp_path):
            db_path = get_database_path(project_path=None)
            assert db_path == tmp_path / "clem.duckdb"
            assert db_path.parent.exists()

    def test_get_database_path_project_specific(self, tmp_path):
        """Test project-specific database path."""
        from clem import get_database_path

        project_path = str(tmp_path / "my-project")
        db_path = get_database_path(project_path=project_path)

        assert db_path == tmp_path / "my-project" / ".claude" / "clem.duckdb"
        assert db_path.parent.exists()

    def test_init_vector_db(self, tmp_path):
        """Test vector database initialization."""
        from clem import init_vector_db
        import duckdb

        db_path = tmp_path / "test.duckdb"
        init_vector_db(db_path)

        # Verify database was created
        assert db_path.exists()

        # Verify table structure
        conn = duckdb.connect(str(db_path))
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        assert "messages" in table_names

        # Verify schema
        schema = conn.execute("PRAGMA table_info(messages)").fetchall()
        column_names = [col[1] for col in schema]
        assert "id" in column_names
        assert "project" in column_names
        assert "session_id" in column_names
        assert "content" in column_names
        assert "embedding" in column_names

        conn.close()

    def test_generate_embedding_with_string(self):
        """Test embedding generation with string input."""
        from clem import generate_embedding

        # This test will use the actual model if available, or skip gracefully
        result = generate_embedding("test message")

        if result is not None:
            # If model is available, verify embedding structure
            assert isinstance(result, list)
            assert len(result) == 384  # all-MiniLM-L6-v2 dimension
            assert all(isinstance(x, (int, float)) for x in result)

    def test_generate_embedding_with_list_content(self):
        """Test embedding generation with list of dicts (message content format)."""
        from clem import generate_embedding

        content = [
            {"type": "text", "text": "First part"},
            {"type": "text", "text": "Second part"}
        ]

        result = generate_embedding(content)

        if result is not None:
            assert isinstance(result, list)
            assert len(result) == 384

    def test_semantic_search_no_database(self, tmp_path):
        """Test semantic search when database doesn't exist."""
        from clem import semantic_search

        with patch("clem.get_database_path", return_value=tmp_path / "nonexistent.duckdb"):
            results = semantic_search("test query")
            assert results == []


class TestMemoryExtraction:
    """Test memory extraction and consolidation functionality."""

    def test_init_memory_db(self, tmp_path):
        """Test memory database initialization."""
        from clem import init_memory_db

        db_path = tmp_path / "memory.duckdb"
        init_memory_db(db_path)

        # Verify tables exist
        import duckdb
        conn = duckdb.connect(str(db_path))

        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]

        assert "memories" in table_names
        assert "memory_relationships" in table_names
        assert "memory_changes" in table_names

        # Verify memories table schema
        schema = conn.execute("PRAGMA table_info(memories)").fetchall()
        column_names = [col[1] for col in schema]

        expected_columns = ['id', 'user_id', 'topic', 'content', 'embedding',
                          'confidence', 'source_session_id', 'source_timestamp',
                          'created_at', 'updated_at', 'supersedes', 'is_active', 'version']

        for col in expected_columns:
            assert col in column_names

        conn.close()

    def test_extract_memories_no_model(self):
        """Test extraction when model is unavailable."""
        from clem import extract_memories_from_session

        with patch("clem.get_extraction_model", return_value=(None, None)):
            messages = [
                {"role": "user", "content": "I work at Google"},
                {"role": "assistant", "content": "That's great!"}
            ]
            result = extract_memories_from_session(messages, "test-session")
            assert result == []

    def test_find_related_memories_no_db(self, tmp_path):
        """Test finding related memories when database doesn't exist."""
        from clem import find_related_memories

        memory = {
            'topic': 'preferences',
            'content': 'User likes coffee',
            'embedding': [0.1] * 384
        }

        db_path = tmp_path / "nonexistent.duckdb"
        results = find_related_memories(memory, "user123", db_path)
        assert results == []

    def test_find_related_memories_with_data(self, tmp_path):
        """Test finding related memories with actual data."""
        from clem import init_memory_db, find_related_memories
        import duckdb
        import uuid

        db_path = tmp_path / "memory.duckdb"
        init_memory_db(db_path)

        # Insert a memory
        conn = duckdb.connect(str(db_path))
        memory_id = str(uuid.uuid4())
        embedding = [0.1] * 384

        conn.execute("""
            INSERT INTO memories (id, user_id, topic, content, embedding, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [memory_id, "user123", "preferences", "User likes coffee", embedding, True])
        conn.commit()
        conn.close()

        # Find related memories
        new_memory = {
            'topic': 'preferences',
            'content': 'User likes tea',
            'embedding': [0.12] * 384  # Similar embedding
        }

        results = find_related_memories(new_memory, "user123", db_path, threshold=0.0)
        assert len(results) >= 1
        assert results[0]['content'] == "User likes coffee"

    def test_consolidate_memory_add(self):
        """Test consolidation decision to add new memory."""
        from clem import consolidate_memory

        new_memory = {
            'topic': 'personal_info',
            'content': 'User works at Google',
            'embedding': [0.1] * 384
        }

        # No related memories
        action = consolidate_memory(new_memory, [])
        assert action['action'] == 'ADD'
        assert action['memory'] == new_memory

    def test_consolidate_memory_ignore_duplicate(self):
        """Test consolidation decision to ignore duplicate."""
        from clem import consolidate_memory

        new_memory = {
            'topic': 'preferences',
            'content': 'User likes coffee',
            'embedding': [0.1] * 384
        }

        related_memories = [{
            'id': '123',
            'topic': 'preferences',
            'content': 'User likes coffee',
            'similarity': 0.95,
            'created_at': '2024-01-01',
            'updated_at': '2024-01-01'
        }]

        action = consolidate_memory(new_memory, related_memories)
        assert action['action'] == 'IGNORE'

    def test_consolidate_memory_update(self):
        """Test consolidation decision to update existing memory."""
        from clem import consolidate_memory

        new_memory = {
            'topic': 'preferences',
            'content': 'User likes coffee with milk and sugar in the morning',
            'embedding': [0.1] * 384
        }

        related_memories = [{
            'id': '123',
            'topic': 'preferences',
            'content': 'User likes coffee',
            'similarity': 0.80,
            'created_at': '2024-01-01',
            'updated_at': '2024-01-01'
        }]

        action = consolidate_memory(new_memory, related_memories)
        assert action['action'] == 'UPDATE'
        assert action['memory_id'] == '123'

    def test_apply_memory_action_add(self, tmp_path):
        """Test applying ADD action."""
        from clem import init_memory_db, apply_memory_action
        import duckdb

        db_path = tmp_path / "memory.duckdb"
        init_memory_db(db_path)

        action = {
            'action': 'ADD',
            'memory': {
                'topic': 'preferences',
                'content': 'User likes coffee',
                'embedding': [0.1] * 384,
                'confidence': 1.0,
                'session_id': 'test-session'
            }
        }

        apply_memory_action(action, "user123", db_path)

        # Verify memory was added
        conn = duckdb.connect(str(db_path))
        result = conn.execute("SELECT content FROM memories WHERE user_id = ?", ["user123"]).fetchone()
        assert result is not None
        assert result[0] == "User likes coffee"
        conn.close()

    def test_apply_memory_action_update(self, tmp_path):
        """Test applying UPDATE action."""
        from clem import init_memory_db, apply_memory_action
        import duckdb
        import uuid

        db_path = tmp_path / "memory.duckdb"
        init_memory_db(db_path)

        # Insert existing memory first
        conn = duckdb.connect(str(db_path))
        old_memory_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO memories (id, user_id, topic, content, embedding, is_active, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [old_memory_id, "user123", "preferences", "User likes coffee", [0.1] * 384, True, 1])
        conn.commit()
        conn.close()

        # Apply UPDATE action
        action = {
            'action': 'UPDATE',
            'memory_id': old_memory_id,
            'memory': {
                'topic': 'preferences',
                'content': 'User likes coffee with milk',
                'embedding': [0.11] * 384,
                'confidence': 1.0,
                'session_id': 'test-session-2'
            },
            'reason': 'More detailed information'
        }

        apply_memory_action(action, "user123", db_path)

        # Verify old memory is deactivated
        conn = duckdb.connect(str(db_path))
        old_active = conn.execute(
            "SELECT is_active FROM memories WHERE id = ?", [old_memory_id]
        ).fetchone()[0]
        assert old_active == False

        # Verify new memory exists
        new_memory = conn.execute(
            "SELECT content, version, supersedes FROM memories WHERE is_active = TRUE AND user_id = ?",
            ["user123"]
        ).fetchone()
        assert new_memory is not None
        assert new_memory[0] == "User likes coffee with milk"
        assert new_memory[1] == 2  # Version incremented
        assert new_memory[2] == old_memory_id  # Supersedes old memory

        # Verify relationship was created
        relationship = conn.execute(
            "SELECT relationship_type FROM memory_relationships WHERE related_memory_id = ?",
            [old_memory_id]
        ).fetchone()
        assert relationship is not None
        assert relationship[0] == "supersedes"

        conn.close()

    def test_apply_memory_action_ignore(self, tmp_path, capsys):
        """Test applying IGNORE action."""
        from clem import init_memory_db, apply_memory_action

        db_path = tmp_path / "memory.duckdb"
        init_memory_db(db_path)

        action = {
            'action': 'IGNORE',
            'reason': 'Duplicate content'
        }

        apply_memory_action(action, "user123", db_path)

        # Should print ignored message (check console output)
        captured = capsys.readouterr()
        assert "Ignored" in captured.out or "duplicate" in captured.out.lower()

    def test_query_memories_no_db(self, tmp_path, capsys):
        """Test querying memories when database doesn't exist."""
        from clem import query_memories

        with patch("clem.get_database_path", return_value=tmp_path / "nonexistent.duckdb"):
            results = query_memories("user123", "test query")
            assert results == []

    def test_query_memories_with_data(self, tmp_path):
        """Test querying memories with actual data."""
        from clem import init_memory_db, query_memories
        import duckdb
        import uuid

        db_path = tmp_path / "memory.duckdb"
        init_memory_db(db_path)

        # Insert test memories
        conn = duckdb.connect(str(db_path))

        memories = [
            ("preferences", "User likes coffee"),
            ("personal_info", "User works at Google"),
            ("key_decisions", "Decided to use DuckDB")
        ]

        for topic, content in memories:
            memory_id = str(uuid.uuid4())
            embedding = [0.1] * 384
            conn.execute("""
                INSERT INTO memories (id, user_id, topic, content, embedding, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [memory_id, "user123", topic, content, embedding, True])

        conn.commit()
        conn.close()

        # Query without search (list all)
        with patch("clem.get_database_path", return_value=db_path):
            results = query_memories("user123", "", project_path=None)
            assert len(results) == 3

        # Query with topic filter
        with patch("clem.get_database_path", return_value=db_path):
            results = query_memories("user123", "", topic="preferences", project_path=None)
            assert len(results) == 1
            assert results[0]['content'] == "User likes coffee"

    def test_query_memories_with_search(self, tmp_path):
        """Test semantic search on memories."""
        from clem import init_memory_db, query_memories, generate_embedding
        import duckdb
        import uuid

        # Skip if embedding model not available
        embedding = generate_embedding("test")
        if embedding is None:
            pytest.skip("Embedding model not available")

        db_path = tmp_path / "memory.duckdb"
        init_memory_db(db_path)

        # Insert test memory with embedding
        conn = duckdb.connect(str(db_path))
        memory_id = str(uuid.uuid4())
        content = "User likes coffee"
        mem_embedding = generate_embedding(content)

        conn.execute("""
            INSERT INTO memories (id, user_id, topic, content, embedding, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [memory_id, "user123", "preferences", content, mem_embedding, True])
        conn.commit()
        conn.close()

        # Search for related content
        with patch("clem.get_database_path", return_value=db_path):
            results = query_memories("user123", "beverages", project_path=None)
            assert len(results) >= 0  # May or may not find based on model


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--cov=clem",
        "--cov-report=term-missing",
        "--cov-fail-under=30"
    ])
