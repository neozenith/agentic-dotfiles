#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""rollout — long-trajectory eval harness for the plan-gap state machine.

Protocol: a real initiative is first driven to completion once (by any means —
typically the original planning skill) on a *gold* feature branch of a real
repo. `gold-extract` derives a milestone set from `base...gold` (the changed
file set). Prototype rollouts then run in detached git worktrees off `base` —
one per (model × variant) — looping: compose prompt (pgsm) → one headless agent
turn (_evalkit) → evaluate evidence gates (pgsm next) → checkpoint against the
gold milestones. The gold branch is never checked out in a rollout worktree; it
is a hidden correctness check. Early-abandon gates kill a rollout that is not
tracking (low milestone recall, stalled state machine, high tool-failure rate)
before it burns the budget. Every turn appends a JSONL record; every run
appends a summary to results.jsonl so effectiveness is trackable over time.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pgsm
import trajectory

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT = Path(__file__)
SCRIPT_DIR = SCRIPT.parent.resolve()
EVALKIT_DIR = SCRIPT_DIR.parent.parent / "_evalkit"
DEFAULT_RUNS_ROOT = Path("tmp") / "evals" / "rollouts"

# The shared eval harness lives one skill over; pin it on sys.path before import.
# A missing _evalkit is a hard failure for the whole harness — crash at load, not mid-run.
sys.path.insert(0, str(EVALKIT_DIR))
import evalkit  # noqa: E402

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return proc.stdout


@dataclass(frozen=True)
class AbandonPolicy:
    grace_turns: int = 6
    min_tracking_score: float = 0.2
    max_stalled_turns: int = 8  # a turn "progresses" via a state transition OR a newly-done ticket
    max_tool_failure_rate: float = 0.5


@dataclass(frozen=True)
class RolloutConfig:
    repo: Path
    base_ref: str
    gold_ref: str
    plan_dir: str
    brief: str
    models: tuple[str, ...]
    max_turns: int
    turn_budget_usd: float
    turn_timeout_s: int
    runs_root: Path
    answer_policy: str  # "human" | "self"
    abandon: AbandonPolicy
    machine_path: Path


def load_config(path: Path) -> RolloutConfig:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    rollout = raw.get("rollout")
    if not isinstance(rollout, dict):
        raise ValueError(f"{path}: missing [rollout] table")
    abandon_raw = raw.get("abandon", {})
    repo = Path(str(rollout["repo"])).expanduser().resolve()
    if not (repo / ".git").exists():
        raise ValueError(f"{path}: rollout.repo is not a git repository: {repo}")
    return RolloutConfig(
        repo=repo,
        base_ref=str(rollout["base_ref"]),
        gold_ref=str(rollout["gold_ref"]),
        plan_dir=str(rollout["plan_dir"]),
        brief=str(rollout.get("brief", "")),
        models=tuple(str(m) for m in rollout.get("models", ["claude-haiku-4-5"])),
        max_turns=int(rollout.get("max_turns", 40)),
        turn_budget_usd=float(rollout.get("turn_budget_usd", 0.5)),
        turn_timeout_s=int(rollout.get("turn_timeout_s", 1200)),
        runs_root=Path(str(rollout.get("runs_root", DEFAULT_RUNS_ROOT))),
        answer_policy=str(rollout.get("answer_policy", "self")),
        abandon=AbandonPolicy(
            grace_turns=int(abandon_raw.get("grace_turns", 6)),
            min_tracking_score=float(abandon_raw.get("min_tracking_score", 0.2)),
            max_stalled_turns=int(abandon_raw.get("max_stalled_turns", 8)),
            max_tool_failure_rate=float(abandon_raw.get("max_tool_failure_rate", 0.5)),
        ),
        machine_path=Path(str(rollout.get("machine", pgsm.DEFAULT_MACHINE))),
    )


# ── Gold milestones (the hidden correctness check) ───────────────────────────
@dataclass(frozen=True)
class GoldMilestones:
    files: frozenset[str]
    commit_count: int

    def as_dict(self) -> dict[str, Any]:
        return {"files": sorted(self.files), "commit_count": self.commit_count}


def gold_extract(repo: Path, base_ref: str, gold_ref: str) -> GoldMilestones:
    """Derive the milestone set from the gold branch without ever checking it out."""
    files = _git(repo, "diff", "--name-only", f"{base_ref}...{gold_ref}").split()
    if not files:
        raise ValueError(f"{base_ref}...{gold_ref} changes no files — wrong refs, or gold == base")
    commits = _git(repo, "rev-list", "--count", f"{base_ref}..{gold_ref}").strip()
    return GoldMilestones(files=frozenset(files), commit_count=int(commits))


# ── Worktrees ────────────────────────────────────────────────────────────────
def add_worktree(repo: Path, ref: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "--detach", str(dest), ref)
    return dest


def remove_worktree(repo: Path, dest: Path) -> None:
    _git(repo, "worktree", "remove", "--force", str(dest))


def changed_files(worktree: Path, base_ref: str) -> frozenset[str]:
    """Everything the rollout touched relative to base: committed, staged, dirty, untracked."""
    committed = _git(worktree, "diff", "--name-only", base_ref, "HEAD").split()
    dirty = _git(worktree, "diff", "--name-only", "HEAD").split()
    staged = _git(worktree, "diff", "--name-only", "--cached").split()
    untracked = _git(worktree, "ls-files", "--others", "--exclude-standard").split()
    return frozenset(committed) | frozenset(dirty) | frozenset(staged) | frozenset(untracked)


# ── Tracking score + abandon gate (pure, $0-testable) ────────────────────────
@dataclass(frozen=True)
class TrackingScore:
    recall: float
    precision: float
    jaccard: float
    touched: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "recall": self.recall,
            "precision": self.precision,
            "jaccard": self.jaccard,
            "touched": self.touched,
        }


def tracking_score(touched: frozenset[str], gold: GoldMilestones) -> TrackingScore:
    overlap = touched & gold.files
    union = touched | gold.files
    return TrackingScore(
        recall=len(overlap) / len(gold.files) if gold.files else 0.0,
        precision=len(overlap) / len(touched) if touched else 0.0,
        jaccard=len(overlap) / len(union) if union else 0.0,
        touched=len(touched),
    )


def decide_abandon(
    policy: AbandonPolicy,
    turn: int,
    score: TrackingScore,
    stalled_turns: int,
    tool_failure_rate: float,
) -> str | None:
    """Return the abandon reason, or None to continue. No gate fires inside the grace window."""
    if turn <= policy.grace_turns:
        return None
    if score.recall < policy.min_tracking_score:
        return f"tracking recall {score.recall:.2f} < {policy.min_tracking_score} after turn {turn}"
    if stalled_turns > policy.max_stalled_turns:
        return f"{stalled_turns} turns without progress (max {policy.max_stalled_turns})"
    if tool_failure_rate > policy.max_tool_failure_rate:
        return f"tool failure rate {tool_failure_rate:.1%} > {policy.max_tool_failure_rate:.1%}"
    return None


# ── Agent seam (injectable; production = _evalkit headless claude) ───────────
@dataclass
class AgentTurn:
    returncode: int
    cost_usd: float
    session_id: str
    transcript_path: Path | None
    tool_calls: int = 0
    tool_errors: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


AgentFn = Callable[[str, Path, str, "RolloutConfig"], AgentTurn]


def agent_turn_from_result(result: Any) -> AgentTurn:
    """Convert an _evalkit RunResult into an AgentTurn, enriched from the real transcript."""
    transcript_path = Path(result.transcript_path) if str(result.transcript_path) else None
    turn = AgentTurn(
        returncode=result.returncode,
        cost_usd=result.total_cost_usd,
        session_id=result.session_id,
        transcript_path=transcript_path,
    )
    if turn.transcript_path and turn.transcript_path.is_file():
        traj = trajectory.parse_transcript(turn.transcript_path)
        turn.tool_calls = len(traj.tool_calls)
        turn.tool_errors = traj.tool_errors
        turn.input_tokens = traj.input_tokens
        turn.output_tokens = traj.output_tokens
    return turn


def claude_agent(prompt: str, cwd: Path, model: str, config: RolloutConfig) -> AgentTurn:
    """One real headless turn via the shared _evalkit harness."""
    result = evalkit.run_claude_skill(
        prompt,
        cwd=cwd,
        model=model,
        max_budget_usd=config.turn_budget_usd,
        timeout_s=config.turn_timeout_s,
    )
    return agent_turn_from_result(result)


SELF_ANSWER_BLOCK = (
    "\n\n## Eval answer policy (no human available)\n\n"
    "This is an unattended evaluation run. When the state instructions say to ask the user a "
    "question and stop, instead: adopt your top-ranked researched recommendation as the Decision, "
    "record it in the ADR with **Why** naming it as the self-selected default, and continue working "
    "this turn. Never leave a question pending for a human.\n"
)


# ── The rollout loop ─────────────────────────────────────────────────────────
def run_rollout(
    config: RolloutConfig,
    model: str,
    run_dir: Path,
    agent_fn: AgentFn,
    keep_worktree: bool = False,
) -> dict[str, Any]:
    gold = gold_extract(config.repo, config.base_ref, config.gold_ref)
    worktree = add_worktree(config.repo, config.base_ref, run_dir / "worktree")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "gold.json").write_text(
        json.dumps(gold.as_dict(), indent=2) + "\n", encoding="utf-8"
    )
    turns_log = run_dir / "turns.jsonl"
    machine = pgsm.load_machine(config.machine_path)
    plan = worktree / config.plan_dir
    plan.mkdir(parents=True, exist_ok=True)
    pgsm.init_state(plan, machine, brief=config.brief, force=True)

    status, reason = "exhausted", f"hit max_turns={config.max_turns}"
    total_cost, stalled_turns, turn = 0.0, 0, 0
    started = time.time()
    for turn in range(1, config.max_turns + 1):
        state = pgsm.load_state(plan)
        if state.state in machine.terminal:
            status, reason = "complete", f"terminal state {state.state!r} at turn {turn - 1}"
            break
        prompt = pgsm.build_prompt(plan, machine, state)
        if config.answer_policy == "self" and state.state == "refinement":
            prompt += SELF_ANSWER_BLOCK
        pgsm.log_prompt(state, prompt, session_id=None)
        done_before = sum(1 for t in pgsm.load_tickets(plan) if t.done)
        agent = agent_fn(prompt, worktree, model, config)
        total_cost += agent.cost_usd
        advanced = pgsm.advance(plan, machine, pgsm.load_state(plan))
        done_after = sum(1 for t in pgsm.load_tickets(plan) if t.done)
        progressed = bool(advanced["transitioned"]) or done_after > done_before
        stalled_turns = 0 if progressed else stalled_turns + 1
        touched = changed_files(worktree, config.base_ref)
        score = tracking_score(touched, gold)
        failure_rate = agent.tool_errors / agent.tool_calls if agent.tool_calls else 0.0
        record = {
            "turn": turn,
            "at": _now(),
            "model": model,
            "state_before": state.state,
            "transitioned_to": advanced.get("to"),
            "done_tickets": done_after,
            "session_id": agent.session_id,
            "cost_usd": agent.cost_usd,
            "input_tokens": agent.input_tokens,
            "output_tokens": agent.output_tokens,
            "tool_calls": agent.tool_calls,
            "tool_errors": agent.tool_errors,
            "tracking": score.as_dict(),
        }
        with turns_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        abandon_reason = decide_abandon(config.abandon, turn, score, stalled_turns, failure_rate)
        if abandon_reason:
            status, reason = "abandoned", abandon_reason
            break
    final_state = pgsm.load_state(plan).state
    final_score = tracking_score(changed_files(worktree, config.base_ref), gold)
    summary = {
        "at": _now(),
        "model": model,
        "machine": machine.name,
        "repo": str(config.repo),
        "base_ref": config.base_ref,
        "status": status,
        "reason": reason,
        "final_state": final_state,
        "turns": turn,
        "wall_seconds": round(time.time() - started, 1),
        "total_cost_usd": round(total_cost, 4),
        "tracking": final_score.as_dict(),
        "run_dir": str(run_dir),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    results = config.runs_root / "results.jsonl"
    results.parent.mkdir(parents=True, exist_ok=True)
    with results.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    if not keep_worktree and status == "complete":
        remove_worktree(config.repo, worktree)
    return summary


def run_matrix(
    config: RolloutConfig, agent_fn: AgentFn, keep_worktree: bool = False
) -> list[dict[str, Any]]:
    """One rollout per model, isolated worktrees, results appended per run."""
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    summaries = []
    for model in config.models:
        run_dir = config.runs_root / run_id / model
        log.info("rollout %s / %s → %s", run_id, model, run_dir)
        summaries.append(run_rollout(config, model, run_dir, agent_fn, keep_worktree=keep_worktree))
    return summaries


# ── CLI ──────────────────────────────────────────────────────────────────────
def cmd_gold_extract(args: argparse.Namespace) -> None:
    repo = Path(args.repo).expanduser().resolve()
    gold = gold_extract(repo, args.base, args.gold)
    print(json.dumps(gold.as_dict(), indent=2))


def cmd_run(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    if args.model:
        config = RolloutConfig(**{**config.__dict__, "models": (args.model,)})
    if args.max_turns:
        config = RolloutConfig(**{**config.__dict__, "max_turns": args.max_turns})
    summaries = run_matrix(config, claude_agent, keep_worktree=args.keep_worktree)
    print(json.dumps(summaries, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    results = Path(args.runs_root) / "results.jsonl"
    if not results.is_file():
        print(f"no results at {results}")
        return
    for line in results.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        tracking = row.get("tracking", {})
        print(
            f"{row['at']}  {row['model']:<24} {row['status']:<10} state={row['final_state']:<14} "
            f"turns={row['turns']:<3} recall={tracking.get('recall', 0):.2f} "
            f"cost=${row.get('total_cost_usd', 0):.2f}  {row['reason']}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rollout", description="Long-trajectory rollout harness for plan-gap-sm"
    )

    def _help(p: argparse.ArgumentParser) -> Any:
        def _print_help(_: argparse.Namespace) -> None:
            p.print_help()

        return _print_help

    parser.set_defaults(func=_help(parser))
    sub = parser.add_subparsers(dest="cmd", required=False)

    p_gold = sub.add_parser(
        "gold-extract", help="Derive milestone set from base...gold (never checks gold out)"
    )
    p_gold.add_argument("--repo", required=True)
    p_gold.add_argument("--base", required=True)
    p_gold.add_argument("--gold", required=True)
    p_gold.set_defaults(func=cmd_gold_extract)

    p_run = sub.add_parser("run", help="Run the rollout matrix from a TOML config")
    p_run.add_argument("--config", required=True)
    p_run.add_argument("--model", default=None, help="Override: run only this model")
    p_run.add_argument("--max-turns", type=int, default=None)
    p_run.add_argument(
        "--keep-worktree", action="store_true", help="Keep worktrees even on completion"
    )
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Show rollout effectiveness history (results.jsonl)")
    p_status.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
