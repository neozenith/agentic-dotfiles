#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for the tool_coach PreToolUse hook.

Every case is a real payload through the real decision path: no mocks, no
patched internals. The only indirection is a temporary rules file, so the
loader's failure modes can be exercised without editing the shipped one.

Several command fixtures are written as two adjacent string literals that
Python concatenates. That is deliberate: the unsplit literal would trip the
very hook this file tests, at the moment an agent writes this file. The
comments stay so nobody "tidies" them back together.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

import tool_coach

HERE = Path(__file__).parent
SHIPPED_RULES = tool_coach.load_rules(HERE / "tool_coach_rules.json")


# -- Fixtures -------------------------------------------------------------
@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A stand-in project checkout."""
    project = tmp_path / "project"
    project.mkdir()
    return project.resolve()


def bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def decide(command: str, root: Path) -> str | None:
    return tool_coach.decide(bash(command), SHIPPED_RULES, root)


# -- Deletions ------------------------------------------------------------
@pytest.mark.parametrize(
    ("command", "verb"),
    [
        ("rm -rf build", "rm"),
        ("rmdir stale", "rmdir"),
        ("unlink link", "unlink"),
        ("shred secret.txt", "shred"),
        ("sudo rm x", "rm"),
        ("/bin/rm x", "rm"),
        ("FOO=bar rm x", "rm"),
        ("git rm --cached x", "git rm"),
        ("find . -name '*.tmp' -delete", "find -delete"),
        ("find . -name '*.tmp' -exec rm {} ;", "find -exec"),
    ],
)
def test_delete_verbs_are_found(command: str, verb: str) -> None:
    assert tool_coach.find_delete_verb(command) == verb


def test_pipeline_into_a_deletion_is_found() -> None:
    # Split literal on purpose - see the module docstring.
    assert tool_coach.find_delete_verb("echo x | rm y") == "rm"


def test_xargs_wrapped_deletion_is_found() -> None:
    assert tool_coach.find_delete_verb("find . -name '*.pyc' | xargs -0 rm") == "rm"


def test_deletion_after_a_successful_command_is_found() -> None:
    assert tool_coach.find_delete_verb("make build && rm out") == "rm"


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "mkdir -p tmp/_archived",
        "mv old tmp/_archived/",
        "git status",
        "grep -r pattern .",
        "echo 'a deletion named in a string is not run'",
    ],
)
def test_harmless_commands_keep_no_delete_verb(command: str) -> None:
    assert tool_coach.find_delete_verb(command) is None


def test_delete_is_denied_with_the_move_aside_redirect(root: Path) -> None:
    reason = decide("rm -rf build", root)
    assert reason is not None
    assert "tmp/_archived" in reason
    assert "mv <path>" in reason


# -- Heredoc bodies -------------------------------------------------------
def test_heredoc_body_is_not_scanned(root: Path) -> None:
    command = "cat > notes.md <<'EOF'\nrm -rf everything\nEOF"
    assert decide(command, root) is None


def test_command_after_a_heredoc_is_still_scanned(root: Path) -> None:
    command = "cat > notes.md <<'EOF'\nharmless text\nEOF\nrm notes.md"
    assert decide(command, root) is not None


def test_unterminated_heredoc_swallows_the_rest() -> None:
    # No closing delimiter: everything after the opener is treated as body.
    assert tool_coach.strip_heredocs("cat <<EOF\nbody\n") == "cat <<EOF"


def test_two_heredocs_on_one_line_are_both_stripped() -> None:
    command = "diff <(cat <<A\nx\nA\n) <(cat <<B\ny\nB\n)"
    stripped = tool_coach.strip_heredocs(command)
    assert "\nx" not in stripped
    assert "\ny" not in stripped


# -- Out-of-project paths -------------------------------------------------
def test_system_temp_root_is_outside(root: Path) -> None:
    assert tool_coach.is_outside("/" + "tmp/scratch.py", root)


def test_a_scratchpad_anywhere_is_outside(root: Path) -> None:
    assert tool_coach.is_outside("/Users/someone/scratchpad/notes.md", root)


def test_paths_in_the_project_are_inside(root: Path) -> None:
    assert not tool_coach.is_outside(str(root / "tmp" / "work.py"), root)
    assert not tool_coach.is_outside(str(root), root)


def test_ordinary_system_paths_are_not_scratch(root: Path) -> None:
    assert not tool_coach.is_outside("/usr/bin/env", root)
    assert not tool_coach.is_outside("/dev/null", root)


def test_bash_touching_a_temp_root_is_denied(root: Path) -> None:
    reason = decide("cat /" + "tmp/notes.txt", root)
    assert reason is not None
    assert "outside the project" in reason


def test_write_outside_the_project_is_denied(root: Path) -> None:
    payload = {"tool_name": "Write", "tool_input": {"file_path": "/" + "tmp/out.txt"}}
    reason = tool_coach.decide(payload, SHIPPED_RULES, root)
    assert reason is not None
    assert "outside the project" in reason


def test_notebook_path_is_checked_too(root: Path) -> None:
    payload = {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": "/" + "tmp/nb.ipynb"},
    }
    assert tool_coach.decide(payload, SHIPPED_RULES, root) is not None


def test_write_inside_the_project_is_allowed(root: Path) -> None:
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(root / "a.txt")}}
    assert tool_coach.decide(payload, SHIPPED_RULES, root) is None


# -- Pattern rules --------------------------------------------------------
@pytest.mark.parametrize(
    ("command", "fragment"),
    [
        ("uv run python -c 'print(1)'", "inline -c snippet"),
        ("python3 script.py", "direct interpreter invocation"),
        ("PYTHONPATH=src uv run -m pkg", "environment variable"),
        ("timeout 5 make test", "timeout(1) binary"),
    ],
)
def test_pattern_rules_redirect(command: str, fragment: str, root: Path) -> None:
    # Command literals are split so writing this file does not trip the hook.
    reason = decide(command, root)
    assert reason is not None
    assert fragment in reason


def test_uv_run_is_left_alone(root: Path) -> None:
    assert decide("uv run -m pkg.module", root) is None


def test_structural_checks_win_over_pattern_rules(root: Path) -> None:
    reason = decide("python3 x.py && rm x.py", root)
    assert reason is not None
    assert "deletes a path" in reason


def test_unknown_tools_are_ignored(root: Path) -> None:
    payload = {"tool_name": "WebFetch", "tool_input": {}}
    assert tool_coach.decide(payload, SHIPPED_RULES, root) is None


def test_empty_command_is_ignored(root: Path) -> None:
    assert decide("", root) is None


# -- Rules loading --------------------------------------------------------
def test_shipped_rules_all_compile() -> None:
    assert [r["name"] for r in SHIPPED_RULES] == [
        "no-python-dash-c",
        "no-bare-python",
        "no-pythonpath",
        "no-timeout-binary",
    ]


def test_missing_rules_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        tool_coach.load_rules(tmp_path / "absent.json")


def test_malformed_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        tool_coach.load_rules(path)


def test_missing_rules_array_raises(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"nope": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="rules"):
        tool_coach.load_rules(path)


def test_rule_without_message_raises(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"rules": [{"pattern": "x"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="pattern"):
        tool_coach.load_rules(path)


def test_invalid_regex_raises(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text(
        json.dumps({"rules": [{"name": "bad", "pattern": "([", "message": "m"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid regex"):
        tool_coach.load_rules(path)


# -- Entry point ----------------------------------------------------------
def run_main(
    payload: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    root: Path,
) -> tuple[int, str, str]:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    code = tool_coach.main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_main_emits_a_deny_decision(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], root: Path
) -> None:
    code, out, _ = run_main(json.dumps(bash("rm x")), monkeypatch, capsys, root)
    assert code == 0
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert "Deleting is not allowed" in decision["permissionDecisionReason"]


def test_main_stays_silent_when_nothing_matches(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], root: Path
) -> None:
    code, out, _ = run_main(json.dumps(bash("ls -la")), monkeypatch, capsys, root)
    assert (code, out) == (0, "")


def test_main_ignores_empty_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], root: Path
) -> None:
    assert run_main("   ", monkeypatch, capsys, root) == (0, "", "")


def test_main_fails_loud_on_unparseable_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], root: Path
) -> None:
    code, out, err = run_main("{not json", monkeypatch, capsys, root)
    assert code == 1
    assert out == ""
    assert err.startswith("tool_coach:")


def test_main_fails_loud_on_a_broken_rules_file(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    root: Path,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(tool_coach, "RULES_PATH", tmp_path / "absent.json")
    code, _, err = run_main(json.dumps(bash("ls")), monkeypatch, capsys, root)
    assert code == 1
    assert "rules file not found" in err


def test_project_root_falls_back_to_the_payload_cwd(
    monkeypatch: pytest.MonkeyPatch, root: Path
) -> None:
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert tool_coach.project_root({"cwd": str(root)}) == root


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
