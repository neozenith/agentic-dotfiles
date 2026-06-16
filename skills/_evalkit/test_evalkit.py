#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0"]
# ///
"""Offline self-tests for the shared eval harness. No LLM calls — $0 tier."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from evalkit import (  # noqa: E402
    cwd_slug,
    find_transcript,
    git_status,
    inject_agents_md,
    make_fixture,
    parse_codex_rollout,
    parse_transcript,
)


def test_cwd_slug() -> None:
    assert cwd_slug(Path("/Users/dev/my.proj")) == "-Users-dev-my-proj"


def test_parse_transcript_extracts_tools_and_tokens(tmp_path: Path) -> None:
    lines = [
        {"type": "user", "message": {}},
        {"type": "system", "subtype": "init"},
        {
            "type": "assistant",
            "message": {
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "content": [
                    {"type": "text", "text": "hi"},
                    {"type": "tool_use", "name": "Read", "input": {}},
                ],
            },
        },
        "not json at all",
    ]
    p = tmp_path / "session.jsonl"
    p.write_text(
        "\n".join(x if isinstance(x, str) else json.dumps(x) for x in lines),
        encoding="utf-8",
    )
    trace = parse_transcript(p)
    assert trace.tool_calls == ["Read"]
    assert trace.assistant_turns == 1
    assert trace.input_tokens == 10
    assert trace.output_tokens == 5


def test_make_fixture_commits_base_overlays_head_injects_skill(tmp_path: Path) -> None:
    template = tmp_path / "template"
    (template / "_base").mkdir(parents=True)
    (template / "_base" / "a.txt").write_text("base\n")
    (template / "_head").mkdir()
    (template / "_head" / "a.txt").write_text("head\n")
    skill = tmp_path / "myskill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: myskill\n---\n")
    (skill / "scripts" / "junk.txt").write_text("excluded")

    dest = make_fixture(template, tmp_path / "run" / "case", skill)

    assert (dest / "a.txt").read_text() == "head\n", "head overlay not applied"
    assert (dest / ".claude" / "skills" / "myskill" / "SKILL.md").is_file()
    assert not (dest / ".claude" / "skills" / "myskill" / "scripts").exists()
    assert "a.txt" in git_status(dest), "overlay should be uncommitted"
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=dest,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "base" in log.stdout


def test_find_transcript_falls_back_to_session_id_glob(tmp_path: Path) -> None:
    # Claude's slug scheme is internal and has drifted (the @-in-cwd incident);
    # the glob-by-session-id fallback must find the file under ANY slug.
    projects = tmp_path / "projects"
    weird_slug_dir = projects / "-some-unpredicted-slug-variant"
    weird_slug_dir.mkdir(parents=True)
    session = "11111111-2222-3333-4444-555555555555"
    (weird_slug_dir / f"{session}.jsonl").write_text("{}\n")

    found = find_transcript(session, tmp_path / "fixture.cwd", projects_dir=projects)

    assert found is not None and found.name == f"{session}.jsonl"
    assert find_transcript("not-a-session", tmp_path, projects_dir=projects) is None


def test_parse_codex_rollout_extracts_tools_tokens_meta(tmp_path: Path) -> None:
    lines = [
        {"type": "session_meta", "payload": {"id": "x"}},
        {
            "type": "turn_context",
            "payload": {
                "model": "gpt-5.5",
                "sandbox_policy": {"network_access": False},
            },
        },
        {
            "type": "response_item",
            "payload": {"type": "function_call", "name": "shell"},
        },
        {"type": "response_item", "payload": {"type": "message", "role": "assistant"}},
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"input_tokens": 100, "output_tokens": 7}
                },
            },
        },
    ]
    p = tmp_path / "rollout-2026-06-13.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    trace, meta = parse_codex_rollout(p)
    assert trace.tool_calls == ["shell"]
    assert trace.assistant_turns == 1
    assert trace.input_tokens == 100 and trace.output_tokens == 7
    assert meta == {"model": "gpt-5.5", "network_access": False}


def test_inject_agents_md(tmp_path: Path) -> None:
    skill = tmp_path / "myskill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: myskill\n---\nDo the thing.\n")
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    target = inject_agents_md(fixture, skill)
    assert target.name == "AGENTS.md"
    assert "Do the thing." in target.read_text()


def test_make_fixture_without_head_is_clean(tmp_path: Path) -> None:
    template = tmp_path / "template"
    (template / "_base").mkdir(parents=True)
    (template / "_base" / "a.txt").write_text("only\n")
    skill = tmp_path / "s"
    skill.mkdir()
    (skill / "SKILL.md").write_text("x")

    dest = make_fixture(template, tmp_path / "run2" / "case", skill)

    # The injected .claude/ dir is the only uncommitted content.
    assert all(".claude" in line for line in git_status(dest).splitlines())


if __name__ == "__main__":  # pragma: no cover
    here = str(Path(__file__).parent.resolve())
    sys.exit(
        pytest.main(
            [__file__, "-v", "--rootdir", here, "-o", "addopts="] + sys.argv[1:]
        )
    )
