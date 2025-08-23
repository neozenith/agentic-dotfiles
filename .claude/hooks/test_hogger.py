#!/usr/bin/env python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest",
#   "pytest-cov",
#   "psutil",
# ]
# ///

import json
import pytest
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the module under test
import hogger


class TestHogger:
    """Test suite for hogger.py Claude hook functionality."""
    
    def setup_method(self):
        """Set up mock objects for each test."""
        self.mock_current_process = MagicMock()
        self.mock_current_process.pid = 12345
        self.mock_claude_process = MagicMock()
        self.mock_claude_process.pid = 54321

    def test_structured_log_with_valid_json(self, caplog):
        """Test structured_log with valid JSON input."""
        # Given
        test_data = {
            "hook_event_name": "user-prompt-submit-hook",
            "session_id": "test-session-123",
            "tool_name": "Read",
            "additional_data": {"key": "value"},
        }

        # When
        with caplog.at_level(logging.INFO):
            hogger.structured_log(json.dumps(test_data), self.mock_current_process, self.mock_claude_process)

        # Then
        assert len(caplog.records) == 1
        log_record = caplog.records[0]
        assert "user-prompt-submit-hook" in log_record.message
        assert "test-session-123" in log_record.message
        assert "Read" in log_record.message

    def test_structured_log_extracts_correct_fields(self, caplog):
        """Test that structured_log correctly extracts and logs expected fields."""
        # Given
        test_data = {
            "hook_event_name": "tool-result",
            "session_id": "session-456",
            "tool_name": "Bash",
            "tool_args": {"command": "ls -la"},
        }

        # When
        with caplog.at_level(logging.INFO):
            hogger.structured_log(json.dumps(test_data), self.mock_current_process, self.mock_claude_process)

        # Then
        log_message = caplog.records[0].message
        logged_json = json.loads(log_message.split("::", 1)[1])

        assert logged_json["event"] == "tool-result"
        assert logged_json["session_id"] == "session-456"
        assert logged_json["tool_name"] == "Bash"
        assert logged_json["hook_data"]["tool_args"]["command"] == "ls -la"

    def test_structured_log_handles_missing_fields(self, caplog):
        """Test that structured_log handles missing optional fields gracefully."""
        # Given
        test_data = {}  # Empty data

        # When
        with caplog.at_level(logging.INFO):
            hogger.structured_log(json.dumps(test_data), self.mock_current_process, self.mock_claude_process)

        # Then
        log_message = caplog.records[0].message
        logged_json = json.loads(log_message.split("::", 1)[1])

        assert logged_json["event"] == "Unknown"
        assert logged_json["session_id"] == "Unknown"
        assert logged_json["tool_name"] == "N/A"

    def test_structured_log_includes_git_info(self, caplog):
        """Test that structured_log includes git repository information."""
        # Given
        test_data = {"hook_event_name": "test-event"}

        # When
        with caplog.at_level(logging.INFO):
            hogger.structured_log(json.dumps(test_data), self.mock_current_process, self.mock_claude_process)

        # Then
        log_message = caplog.records[0].message
        logged_json = json.loads(log_message.split("::", 1)[1])

        assert "git_super_project" in logged_json
        assert "repo" in logged_json
        assert "is_worktree" in logged_json
        assert isinstance(logged_json["is_worktree"], bool)

    def test_structured_log_includes_process_info(self, caplog):
        """Test that structured_log includes process information."""
        # Given
        test_data = {"hook_event_name": "process-test"}

        # When
        with caplog.at_level(logging.INFO):
            hogger.structured_log(json.dumps(test_data), self.mock_current_process, self.mock_claude_process)

        # Then
        log_message = caplog.records[0].message
        logged_json = json.loads(log_message.split("::", 1)[1])

        assert "pid" in logged_json
        assert logged_json["pid"] == 12345
        assert "claude_pid" in logged_json
        assert logged_json["claude_pid"] == 54321

    @patch('sys.stdin')
    def test_main_with_valid_stdin(self, mock_stdin, caplog):
        """Test main function with valid JSON from stdin."""
        # Given
        test_data = {"hook_event_name": "stdin-test", "session_id": "stdin-session"}
        mock_stdin.read.return_value = json.dumps(test_data)

        # When
        with caplog.at_level(logging.INFO):
            hogger.main([], self.mock_current_process, self.mock_claude_process)

        # Then
        assert len(caplog.records) == 1
        assert "stdin-test" in caplog.records[0].message

    @patch('sys.stdin')
    def test_main_with_invalid_json(self, mock_stdin, caplog):
        """Test main function handles invalid JSON gracefully."""
        # Given
        mock_stdin.read.return_value = "invalid json"

        # When
        with caplog.at_level(logging.DEBUG):  # Capture all log levels
            hogger.main(["test", "args"], self.mock_current_process, self.mock_claude_process)

        # Then
        error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
        info_logs = [r for r in caplog.records if r.levelname == "INFO"]

        assert len(error_logs) == 1
        assert "Failed to parse hook data" in error_logs[0].message
        assert len(info_logs) == 1
        assert "Running with args" in info_logs[0].message

    @patch('sys.stdin')
    def test_main_with_stdin_exception(self, mock_stdin, caplog):
        """Test main function handles stdin reading exceptions."""
        # Given
        mock_stdin.read.side_effect = Exception("Stdin read error")

        # When
        with caplog.at_level(logging.DEBUG):  # Capture all log levels
            hogger.main(["fallback", "args"], self.mock_current_process, self.mock_claude_process)

        # Then
        error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
        info_logs = [r for r in caplog.records if r.levelname == "INFO"]

        assert len(error_logs) == 1
        assert "Failed to parse hook data" in error_logs[0].message
        assert len(info_logs) == 1
        assert "fallback" in info_logs[0].message


class TestHoggerNewFunctions:
    """Test suite for the new functions in hogger.py."""

    def test_find_processes_returns_current_process(self):
        """Test that find_processes returns current process."""
        # When
        current_process, claude_process = hogger.find_processes()
        
        # Then
        assert hasattr(current_process, 'pid')
        assert isinstance(current_process.pid, int)
        # claude_process may be None if no Claude parent found
        assert claude_process is None or hasattr(claude_process, 'pid')

    def test_log_file_location_with_claude_pid(self):
        """Test log_file_location with Claude PID."""
        # Given
        test_pid = 12345
        
        # When
        log_file = hogger.log_file_location(claude_pid=test_pid)
        
        # Then
        assert isinstance(log_file, Path)
        assert str(test_pid) in str(log_file)
        assert "claude_hooks.log" in str(log_file)

    def test_log_file_location_without_claude_pid(self):
        """Test log_file_location without Claude PID."""
        # When
        log_file = hogger.log_file_location()
        
        # Then
        assert isinstance(log_file, Path)
        assert "claude_hooks.log" in str(log_file)
        assert "logs" in str(log_file)


class TestHoggerIntegration:
    """Integration tests for hogger.py functionality."""

    def test_git_constants_are_paths(self):
        """Test that git-related constants are valid Path objects."""
        # Then
        assert isinstance(hogger.GIT_ROOT, Path)
        assert isinstance(hogger.GIT_SUPER_PROJECT, Path)
        assert isinstance(hogger.IS_WORKTREE, bool)

    def test_claude_root_is_path(self):
        """Test that CLAUDE_ROOT is a valid Path object."""
        assert isinstance(hogger.CLAUDE_ROOT, Path)

    def test_module_constants_defined(self):
        """Test that module-level constants are properly defined."""
        # Test that lambda helper is callable
        assert callable(hogger._run)
        
        # Test current_process is psutil.Process
        current_process, _ = hogger.find_processes()
        assert hasattr(current_process, 'pid')
        assert hasattr(current_process, 'parents')


# Test data for parameterized testing
HOOK_EVENT_TEST_DATA = [
    ("user-prompt-submit-hook", "session-1", "Read"),
    ("tool-result", "session-2", "Bash"),
    ("tool-call", "session-3", "Write"),
    ("session-start", "session-4", "N/A"),
]


class TestHoggerParameterized:
    """Parameterized tests for various hook events."""
    
    def setup_method(self):
        """Set up mock objects for each test."""
        self.mock_current_process = MagicMock()
        self.mock_current_process.pid = 12345
        self.mock_claude_process = MagicMock()
        self.mock_claude_process.pid = 54321

    @pytest.mark.parametrize("event,session,tool", HOOK_EVENT_TEST_DATA)
    def test_various_hook_events(self, event, session, tool, caplog):
        """Test logging of various hook event types."""
        # Given
        test_data = {"hook_event_name": event, "session_id": session, "tool_name": tool}

        # When
        with caplog.at_level(logging.INFO):
            hogger.structured_log(json.dumps(test_data), self.mock_current_process, self.mock_claude_process)

        # Then
        log_message = caplog.records[0].message
        logged_json = json.loads(log_message.split("::", 1)[1])

        assert logged_json["event"] == event
        assert logged_json["session_id"] == session
        assert logged_json["tool_name"] == tool


if __name__ == "__main__":
    module = str(Path(__file__).stem.replace('test_', ''))
    pytest.main([__file__, "-v", f"--cov={module}", "--cov-report=term-missing"])