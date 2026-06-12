#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for rollout.py — real fixture git repos + an injected scripted agent. No mocks, no LLM calls."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pgsm
import pytest
import rollout
from test_pgsm import DISCOVERY, INDEX_DRAFTED, ticket_md

GIT_ID = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *GIT_ID, *args], capture_output=True, text=True, check=True
    ).stdout


PLAN_REL = "docs/plans/demo"
GOLD_FILES = [
    f"{PLAN_REL}/README.md",
    f"{PLAN_REL}/G1.md",
    "src/feature.py",
    "tests/test_feature.py",
]


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    """A real repo: main holds the base app; the gold branch holds the finished initiative."""
    repo = tmp_path / "target"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("APP = 1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "checkout", "-q", "-b", "gold")
    for rel in GOLD_FILES:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"gold content for {rel}\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "finished initiative")
    git(repo, "checkout", "-q", "main")
    return repo


def write_config(tmp_path: Path, repo: Path, **overrides: object) -> Path:
    abandon = overrides.pop("abandon", "")
    body = (
        "[rollout]\n"
        f'repo = "{repo}"\n'
        'base_ref = "main"\n'
        'gold_ref = "gold"\n'
        f'plan_dir = "{PLAN_REL}"\n'
        'brief = "demo initiative"\n'
        'models = ["fake-model"]\n'
        f"max_turns = {overrides.pop('max_turns', 12)}\n"
        f'runs_root = "{tmp_path / "runs"}"\n'
        f"{''.join(f'{k} = {v}' + chr(10) for k, v in overrides.items())}"
        f"{abandon}"
    )
    path = tmp_path / "rollout.toml"
    path.write_text(body, encoding="utf-8")
    return path


# ── Config ───────────────────────────────────────────────────────────────────
def test_load_config(tmp_path: Path, target_repo: Path) -> None:
    config = rollout.load_config(
        write_config(tmp_path, target_repo, abandon="[abandon]\ngrace_turns = 2\n")
    )
    assert config.repo == target_repo.resolve()
    assert config.models == ("fake-model",)
    assert config.abandon.grace_turns == 2
    assert config.answer_policy == "self"


def test_load_config_rejects_non_git_repo(tmp_path: Path) -> None:
    not_repo = tmp_path / "plain"
    not_repo.mkdir()
    with pytest.raises(ValueError, match="not a git repository"):
        rollout.load_config(write_config(tmp_path, not_repo))


def test_load_config_missing_table(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("[other]\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"missing \[rollout\]"):
        rollout.load_config(path)


# ── Gold milestones ──────────────────────────────────────────────────────────
def test_gold_extract(target_repo: Path) -> None:
    gold = rollout.gold_extract(target_repo, "main", "gold")
    assert gold.files == frozenset(GOLD_FILES)
    assert gold.commit_count == 1


def test_gold_extract_no_diff_crashes(target_repo: Path) -> None:
    with pytest.raises(ValueError, match="changes no files"):
        rollout.gold_extract(target_repo, "main", "main")


# ── Worktrees + changed files ────────────────────────────────────────────────
def test_worktree_lifecycle_and_changed_files(target_repo: Path, tmp_path: Path) -> None:
    worktree = rollout.add_worktree(target_repo, "main", tmp_path / "wt")
    assert (worktree / "src" / "app.py").is_file()
    assert rollout.changed_files(worktree, "main") == frozenset()
    (worktree / "src" / "app.py").write_text("APP = 2\n", encoding="utf-8")  # dirty
    (worktree / "new_untracked.py").write_text("x\n", encoding="utf-8")  # untracked
    git(worktree, "add", "new_untracked.py")  # staged
    (worktree / "src" / "feature.py").write_text("y\n", encoding="utf-8")
    git(worktree, "add", "src/feature.py")
    git(worktree, "commit", "-q", "-m", "feature")  # committed
    touched = rollout.changed_files(worktree, "main")
    assert touched == {"src/app.py", "new_untracked.py", "src/feature.py"}
    rollout.remove_worktree(target_repo, worktree)
    assert not worktree.exists()


# ── Scoring + abandon gates (pure) ───────────────────────────────────────────
def test_tracking_score_math() -> None:
    gold = rollout.GoldMilestones(files=frozenset({"a", "b", "c", "d"}), commit_count=1)
    score = rollout.tracking_score(frozenset({"a", "b", "x"}), gold)
    assert score.recall == 0.5 and score.precision == pytest.approx(2 / 3)
    assert score.jaccard == pytest.approx(2 / 5) and score.touched == 3
    empty = rollout.tracking_score(frozenset(), gold)
    assert empty.recall == 0.0 and empty.precision == 0.0 and empty.jaccard == 0.0


@pytest.mark.parametrize(
    "turn,recall,stalled,failure_rate,expect",
    [
        (1, 0.0, 99, 1.0, None),  # grace window absorbs everything
        (7, 0.1, 0, 0.0, "tracking recall"),
        (7, 0.9, 9, 0.0, "without progress"),
        (7, 0.9, 0, 0.6, "tool failure rate"),
        (7, 0.9, 0, 0.0, None),
    ],
)
def test_decide_abandon(
    turn: int, recall: float, stalled: int, failure_rate: float, expect: str | None
) -> None:
    policy = rollout.AbandonPolicy(
        grace_turns=6, min_tracking_score=0.2, max_stalled_turns=8, max_tool_failure_rate=0.5
    )
    score = rollout.TrackingScore(recall=recall, precision=1.0, jaccard=recall, touched=1)
    reason = rollout.decide_abandon(policy, turn, score, stalled, failure_rate)
    if expect is None:
        assert reason is None
    else:
        assert reason is not None and expect in reason


# ── Scripted agent: drives the machine to complete, no LLM ───────────────────
def scripted_agent(
    prompt: str, worktree: Path, model: str, config: rollout.RolloutConfig
) -> rollout.AgentTurn:
    """Plays a competent agent: reads the state from the prompt header and stages real evidence."""
    plan = worktree / config.plan_dir
    if "state: bootstrap" in prompt:
        (plan / "README.md").write_text(INDEX_DRAFTED, encoding="utf-8")
        (plan / "DISCOVERY.md").write_text(DISCOVERY, encoding="utf-8")
        (plan / "G1.md").write_text(
            "# G1: First\n\n## Outputs\n\n| File | Change |\n", encoding="utf-8"
        )
    elif "state: refinement" in prompt:
        assert (
            "Eval answer policy" in prompt
        )  # self-answer block must be injected on refinement turns
    elif "state: validation" in prompt:
        receipt = plan / ".pgsm" / "receipts" / "validation.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text('{"requirement_integrity": "pass"}\n', encoding="utf-8")
    elif "state: decomposition" in prompt:
        (plan / "G1-T1.1.md").write_text(ticket_md("T1.1", []), encoding="utf-8")
        (plan / "README.md").write_text(
            INDEX_DRAFTED.replace("<!-- TODO: pending decomposition -->", "populated"),
            encoding="utf-8",
        )
    elif "state: execution" in prompt:
        (plan / "G1-T1.1.md").write_text(ticket_md("T1.1", [], done=True), encoding="utf-8")
        for rel in ("src/feature.py", "tests/test_feature.py"):
            path = worktree / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("real implementation\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(worktree), *GIT_ID, "add", "-A"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(worktree), *GIT_ID, "commit", "-q", "-m", "T1.1: done"],
            check=True,
            capture_output=True,
        )
    return rollout.AgentTurn(
        returncode=0, cost_usd=0.01, session_id=f"fake-{model}", transcript_path=None, tool_calls=4
    )


def noop_agent(
    prompt: str, worktree: Path, model: str, config: rollout.RolloutConfig
) -> rollout.AgentTurn:
    return rollout.AgentTurn(returncode=0, cost_usd=0.01, session_id="noop", transcript_path=None)


def test_run_rollout_to_complete(tmp_path: Path, target_repo: Path) -> None:
    config = rollout.load_config(
        write_config(
            tmp_path, target_repo, abandon="[abandon]\ngrace_turns = 10\nmin_tracking_score = 0.0\n"
        )
    )
    summary = rollout.run_rollout(config, "fake-model", tmp_path / "run", scripted_agent)
    assert summary["status"] == "complete"
    assert summary["final_state"] == "complete"
    assert summary["tracking"]["recall"] >= 0.5  # plan files land at gold paths + real src files
    assert summary["total_cost_usd"] > 0
    turns = [
        json.loads(line)
        for line in (tmp_path / "run" / "turns.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    states = [t["state_before"] for t in turns]
    assert states[0] == "bootstrap" and "execution" in states
    assert (tmp_path / "run" / "gold.json").is_file()
    results = (tmp_path / "runs" / "results.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(results) == 1
    assert not (tmp_path / "run" / "worktree").exists()  # cleaned on completion


def test_run_rollout_abandons_when_not_tracking(tmp_path: Path, target_repo: Path) -> None:
    config = rollout.load_config(
        write_config(
            tmp_path, target_repo, abandon="[abandon]\ngrace_turns = 1\nmin_tracking_score = 0.5\n"
        )
    )
    summary = rollout.run_rollout(config, "fake-model", tmp_path / "run", noop_agent)
    assert summary["status"] == "abandoned"
    assert "tracking recall" in summary["reason"]
    assert (tmp_path / "run" / "worktree").exists()  # kept for inspection on abandon
    rollout.remove_worktree(target_repo, tmp_path / "run" / "worktree")


def test_run_rollout_exhausts_max_turns(tmp_path: Path, target_repo: Path) -> None:
    config = rollout.load_config(
        write_config(tmp_path, target_repo, max_turns=2, abandon="[abandon]\ngrace_turns = 99\n")
    )
    summary = rollout.run_rollout(config, "fake-model", tmp_path / "run", noop_agent)
    assert summary["status"] == "exhausted" and summary["turns"] == 2
    rollout.remove_worktree(target_repo, tmp_path / "run" / "worktree")


def test_run_matrix_one_dir_per_model(tmp_path: Path, target_repo: Path) -> None:
    config = rollout.load_config(
        write_config(tmp_path, target_repo, max_turns=1, abandon="[abandon]\ngrace_turns = 99\n")
    )
    summaries = rollout.run_matrix(config, noop_agent)
    assert len(summaries) == 1 and summaries[0]["model"] == "fake-model"
    run_dir = Path(summaries[0]["run_dir"])
    assert run_dir.parent.name == "fake-model" or run_dir.name == "fake-model"
    rollout.remove_worktree(target_repo, run_dir / "worktree")


# ── Agent-turn conversion from a real RunResult-shaped object ────────────────
def test_agent_turn_from_transcript(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "timestamp": "2026-06-13T10:00:00Z",
                "message": {
                    "model": "m",
                    "usage": {"input_tokens": 7, "output_tokens": 3},
                    "content": [{"type": "tool_use", "name": "Bash", "input": {}}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(rollout.EVALKIT_DIR))
    import evalkit

    result = evalkit.RunResult(
        returncode=0,
        result_text="ok",
        total_cost_usd=0.12,
        session_id="s",
        transcript_path=transcript,
        trace=evalkit.RunTrace(),
        raw_stdout="",
        raw_stderr="",
    )
    turn = rollout.agent_turn_from_result(result)
    assert turn.cost_usd == 0.12 and turn.tool_calls == 1
    assert turn.input_tokens == 7 and turn.output_tokens == 3


# ── CLI ──────────────────────────────────────────────────────────────────────
def test_cli_gold_extract(target_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rollout.main(["gold-extract", "--repo", str(target_repo), "--base", "main", "--gold", "gold"])
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["files"]) == set(GOLD_FILES)


def test_cli_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    row = {
        "at": "2026-06-13T10:00:00+00:00",
        "model": "fake-model",
        "status": "complete",
        "final_state": "complete",
        "turns": 6,
        "total_cost_usd": 0.06,
        "tracking": {"recall": 0.8},
        "reason": "terminal",
    }
    (runs_root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    rollout.main(["status", "--runs-root", str(runs_root)])
    out = capsys.readouterr().out
    assert "fake-model" in out and "recall=0.80" in out
    rollout.main(["status", "--runs-root", str(tmp_path / "nope")])
    assert "no results" in capsys.readouterr().out


def test_cli_no_subcommand_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    rollout.main([])
    assert "usage: rollout" in capsys.readouterr().out


def test_machine_state_assertion_helper() -> None:
    assert pgsm.DEFAULT_MACHINE.is_file()


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
