#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for trajectory.py — synthesized session jsonl fixtures, no mocks."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import trajectory


def assistant_line(
    at: str, *, blocks: list[dict[str, Any]] | None = None, sidechain: bool = False
) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": at,
            "isSidechain": sidechain,
            "message": {
                "model": "claude-haiku-4-5",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_input_tokens": 10,
                    "cache_creation_input_tokens": 5,
                },
                "content": blocks or [],
            },
        }
    )


def user_line(at: str, content: Any) -> str:
    return json.dumps({"type": "user", "timestamp": at, "message": {"content": content}})


@pytest.fixture
def transcript(tmp_path: Path) -> Path:
    """A realistic-shaped session log: reads, a tool failure, sidechain traffic, junk lines."""
    read_target = tmp_path / "plan" / "README.md"
    read_target.parent.mkdir()
    read_target.write_text("x" * 400, encoding="utf-8")  # ~100 tokens
    lines = [
        user_line(
            "2026-06-13T10:00:00Z", "# plan-gap state machine — state: bootstrap\n\nDo the work."
        ),
        assistant_line(
            "2026-06-13T10:00:05Z",
            blocks=[{"type": "tool_use", "name": "Read", "input": {"file_path": str(read_target)}}],
        ),
        user_line(
            "2026-06-13T10:00:06Z",
            [{"type": "tool_result", "content": "file contents", "is_error": False}],
        ),
        assistant_line(
            "2026-06-13T10:00:10Z",
            blocks=[{"type": "tool_use", "name": "Bash", "input": {"command": "false"}}],
        ),
        user_line(
            "2026-06-13T10:00:11Z", [{"type": "tool_result", "content": "boom", "is_error": True}]
        ),
        assistant_line(
            "2026-06-13T10:00:20Z",
            blocks=[
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/nonexistent/file.md"}}
            ],
            sidechain=True,
        ),
        "not json at all",
        json.dumps({"type": "system", "timestamp": "2026-06-13T10:00:30Z"}),
        "",
    ]
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_parse_transcript_core_metrics(transcript: Path) -> None:
    traj = trajectory.parse_transcript(transcript)
    assert traj.assistant_turns == 3
    assert traj.models == ["claude-haiku-4-5"]
    assert traj.input_tokens == 300 and traj.output_tokens == 150
    assert traj.cache_read_tokens == 30 and traj.cache_creation_tokens == 15
    assert [c.name for c in traj.tool_calls] == ["Read", "Bash", "Read"]
    assert traj.tool_errors == 1
    assert traj.tool_failure_rate == pytest.approx(1 / 3)
    assert traj.sidechain_events == 1
    assert traj.wall_seconds == 30.0


def test_file_loads_with_size_proxy_and_sidechain_flag(transcript: Path) -> None:
    traj = trajectory.parse_transcript(transcript)
    assert len(traj.file_loads) == 2
    first, second = traj.file_loads
    assert first.path.endswith("plan/README.md") and first.approx_tokens == 100
    assert not first.sidechain
    assert second.path == "/nonexistent/file.md" and second.approx_tokens == 0
    assert second.sidechain


def test_verify_prompts_delivered_and_missing(transcript: Path, tmp_path: Path) -> None:
    traj = trajectory.parse_transcript(transcript)
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "0001-bootstrap.md").write_text(
        "# plan-gap state machine — state: bootstrap\n\nDo the work.", encoding="utf-8"
    )
    (prompts / "0002-refinement.md").write_text("never delivered text", encoding="utf-8")
    checks = trajectory.verify_prompts(traj, prompts)
    assert [(c.prompt_file, c.delivered) for c in checks] == [
        ("0001-bootstrap.md", True),
        ("0002-refinement.md", False),
    ]


def test_build_report_watch_filter(transcript: Path) -> None:
    traj = trajectory.parse_transcript(transcript)
    report = trajectory.build_report(traj, watch="/nonexistent", checks=[])
    assert len(report["file_loads"]) == 1
    assert report["file_loads"][0]["path"] == "/nonexistent/file.md"
    unfiltered = trajectory.build_report(traj, watch=None, checks=[])
    assert len(unfiltered["file_loads"]) == 2


def test_find_transcript_by_session_id(tmp_path: Path) -> None:
    projects = tmp_path / "projects"
    slug = projects / "-Users-someone-proj"
    slug.mkdir(parents=True)
    target = slug / "abc-123.jsonl"
    target.write_text("", encoding="utf-8")
    assert trajectory.find_transcript("abc-123", projects) == target
    with pytest.raises(FileNotFoundError, match="no transcript"):
        trajectory.find_transcript("ghost", projects)


def test_cli_json_report(
    transcript: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir(exist_ok=True)
    (prompts / "0001-bootstrap.md").write_text(
        "# plan-gap state machine — state: bootstrap\n\nDo the work.", encoding="utf-8"
    )
    trajectory.main(
        [
            "--transcript",
            str(transcript),
            "--json",
            "--prompts-dir",
            str(prompts),
            "--watch",
            str(tmp_path),
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert report["assistant_turns"] == 3
    assert report["tokens"]["input"] == 300
    assert report["prompt_checks"] == [{"prompt_file": "0001-bootstrap.md", "delivered": True}]
    assert len(report["file_loads"]) == 1  # watch filter keeps only tmp_path reads


def test_cli_human_report(transcript: Path, capsys: pytest.CaptureFixture[str]) -> None:
    trajectory.main(["--transcript", str(transcript)])
    out = capsys.readouterr().out
    assert "tool calls:  3 total, 1 failed" in out
    assert "file loads" in out and "README.md" in out


def test_cli_session_id_lookup(
    tmp_path: Path, transcript: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    projects = tmp_path / "projects"
    slug = projects / "-slug"
    slug.mkdir(parents=True)
    (slug / "sess-9.jsonl").write_text(transcript.read_text(encoding="utf-8"), encoding="utf-8")
    trajectory.main(["--session-id", "sess-9", "--projects-dir", str(projects), "--json"])
    assert json.loads(capsys.readouterr().out)["assistant_turns"] == 3


def test_cli_missing_transcript_errors(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="not found"):
        trajectory.main(["--transcript", str(tmp_path / "ghost.jsonl")])


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
