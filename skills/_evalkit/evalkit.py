#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Shared eval harness for Claude Code skills.

Stdlib-only. Builds hermetic git fixtures, drives `claude -p` (and
`codex exec`) against them, and parses the session logs for tool calls and
tokens. Contract: .claude/rules/claude_skills/evals.md. Offline self-tests:
test_evalkit.py (run via `make -C .claude/skills/_evalkit test`).

Auth (claude): runs inherit the caller's environment, so either
ANTHROPIC_API_KEY (API billing) or the logged-in subscription (OAuth/keychain)
works — ideal for rapid prototyping on lower-tier models before wiring an API
key. We deliberately do NOT pass `--bare`: verified 2026-06, --bare never
reads OAuth/keychain AND does not load the fixture project's .claude/skills
("Unknown command: /<skill>", 0 turns, $0). Isolation comes from
`--setting-sources project` instead: only the fixture's own project settings
and skills load — the user's user/local settings, hooks, and MCP stay out.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Identity flags so fixture commits work on machines with no git config.
GIT_ID = ["-c", "user.email=evals@example.invalid", "-c", "user.name=evalkit"]


def cwd_slug(path: Path) -> str:
    """Claude Code's transcript-directory slug: abs path with / and . -> -."""
    return str(path.resolve()).replace("/", "-").replace(".", "-")


def find_transcript(
    session_id: str, cwd: Path, projects_dir: Path | None = None
) -> Path | None:
    """Locate a session transcript: slug path first, then glob by session id.

    The slug scheme is Claude Code internal and has drifted (verified 2026-06:
    an `@` in the cwd produced a directory our slug didn't predict, yielding
    silently-empty traces). The session UUID is unique, so a glob fallback
    across all project dirs is exact.
    """
    if projects_dir is None:
        projects_dir = Path.home() / ".claude" / "projects"
    direct = projects_dir / cwd_slug(cwd) / f"{session_id}.jsonl"
    if direct.is_file():
        return direct
    if projects_dir.is_dir():
        matches = list(projects_dir.glob(f"*/{session_id}.jsonl"))
        if matches:
            return matches[0]
    return None


def make_fixture(template: Path, dest: Path, skill_dir: Path) -> Path:
    """Build a hermetic fixture project at dest.

    Copies template/_base, commits it, overlays template/_head as the
    uncommitted working tree, and injects the skill under test into the
    fixture's .claude/skills/ (excluding scripts/ to avoid eval recursion).
    """
    if dest.exists():
        shutil.rmtree(dest)
    base = template / "_base"
    shutil.copytree(base if base.is_dir() else template, dest)
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    subprocess.run(["git", *GIT_ID, "add", "-A"], cwd=dest, check=True)
    subprocess.run(["git", *GIT_ID, "commit", "-q", "-m", "base"], cwd=dest, check=True)
    head = template / "_head"
    if head.is_dir():
        shutil.copytree(head, dest, dirs_exist_ok=True)
    skill_dest = dest / ".claude" / "skills" / skill_dir.name
    shutil.copytree(skill_dir, skill_dest, ignore=shutil.ignore_patterns("scripts"))
    return dest


def inject_agents_md(fixture: Path, skill_dir: Path) -> Path:
    """Codex variant of skill injection: SKILL.md becomes the fixture's AGENTS.md.

    Codex does not read .claude/skills; AGENTS.md is its instruction surface.
    """
    target = fixture / "AGENTS.md"
    target.write_text(
        (skill_dir / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return target


def git_status(cwd: Path) -> str:
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout


def _agent_env() -> dict[str, str]:
    """Inherit the caller's env (subscription OAuth needs it); strip model bleed."""
    env = dict(os.environ)
    env.pop(
        "ANTHROPIC_MODEL", None
    )  # --model / -m flags are the single source of truth
    return env


@dataclass
class RunTrace:
    """Forensics extracted from a session log (.jsonl)."""

    tool_calls: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    assistant_turns: int = 0


def parse_transcript(path: Path) -> RunTrace:
    """Permissive parse of Claude Code's internal session jsonl.

    The format is undocumented and unversioned — extract only what the
    metrics need, tolerate everything else.
    """
    trace = RunTrace()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant":
            continue
        trace.assistant_turns += 1
        message = entry.get("message") or {}
        usage = message.get("usage") or {}
        trace.input_tokens += int(usage.get("input_tokens") or 0)
        trace.output_tokens += int(usage.get("output_tokens") or 0)
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                trace.tool_calls.append(str(block.get("name", "?")))
    return trace


def parse_codex_rollout(path: Path) -> tuple[RunTrace, dict]:
    """Permissive parse of a Codex rollout jsonl.

    Returns (trace, meta) where meta carries model/sandbox facts from
    turn_context (e.g. meta["network_access"] for no-network assertions).
    """
    trace = RunTrace()
    meta: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = entry.get("type")
        payload = entry.get("payload") or {}
        if kind == "turn_context":
            meta["model"] = payload.get("model", meta.get("model"))
            sandbox = payload.get("sandbox_policy") or {}
            if isinstance(sandbox, dict) and "network_access" in sandbox:
                meta["network_access"] = sandbox["network_access"]
        elif kind == "response_item":
            ptype = payload.get("type")
            if ptype == "function_call":
                trace.tool_calls.append(str(payload.get("name", "?")))
            elif ptype == "message" and payload.get("role") == "assistant":
                trace.assistant_turns += 1
        elif kind == "event_msg" and payload.get("type") == "token_count":
            totals = (
                (payload.get("info") or {}).get("total_token_usage")
                or payload.get("total_token_usage")
                or {}
            )
            trace.input_tokens = int(totals.get("input_tokens") or trace.input_tokens)
            trace.output_tokens = int(
                totals.get("output_tokens") or trace.output_tokens
            )
    return trace, meta


@dataclass
class RunResult:
    returncode: int
    result_text: str
    total_cost_usd: float
    session_id: str
    transcript_path: Path
    trace: RunTrace
    raw_stdout: str
    raw_stderr: str
    meta: dict = field(default_factory=dict)


def run_claude_skill(
    prompt: str,
    cwd: Path,
    model: str,
    max_budget_usd: float,
    timeout_s: int = 600,
) -> RunResult:
    """One headless run: claude -p in the fixture cwd, project-only settings."""
    session_id = str(uuid.uuid4())
    cmd = [
        "claude",
        "-p",
        prompt,
        "--setting-sources",
        "project",
        "--model",
        model,
        "--session-id",
        session_id,
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
        "--max-budget-usd",
        str(max_budget_usd),
    ]
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=_agent_env(),
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    result_text, cost = "", 0.0
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
            result_text = str(payload.get("result", ""))
            cost = float(payload.get("total_cost_usd") or 0.0)
        except json.JSONDecodeError:
            result_text = proc.stdout
    transcript = find_transcript(session_id, Path(cwd))
    trace = parse_transcript(transcript) if transcript else RunTrace()
    return RunResult(
        proc.returncode,
        result_text,
        cost,
        session_id,
        transcript or Path(),
        trace,
        proc.stdout,
        proc.stderr,
    )


def run_codex_skill(
    prompt: str,
    cwd: Path,
    model: str,
    timeout_s: int = 600,
) -> RunResult:
    """Codex equivalent: codex exec in the fixture cwd, workspace-write sandbox.

    Inject skill instructions first via inject_agents_md(fixture, skill_dir) —
    codex reads AGENTS.md, not .claude/skills. Cost is not reported by codex
    (total_cost_usd stays 0.0); tokens land in trace via the rollout.
    """
    last_msg = Path(cwd) / ".codex-last-message.txt"
    cmd = [
        "codex",
        "exec",
        prompt,
        "-m",
        model,
        "-C",
        str(cwd),
        "-s",
        "workspace-write",
        "--skip-git-repo-check",
        "--json",
        "-o",
        str(last_msg),
    ]
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=_agent_env(),
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    result_text = (
        last_msg.read_text(encoding="utf-8") if last_msg.is_file() else proc.stdout
    )
    if last_msg.is_file():
        last_msg.unlink()  # keep the fixture tree clean for files_unchanged checks
    rollout = _newest_codex_rollout(since=started)
    trace, meta = parse_codex_rollout(rollout) if rollout else (RunTrace(), {})
    return RunResult(
        proc.returncode,
        result_text,
        0.0,
        rollout.stem if rollout else "",
        rollout or Path(),
        trace,
        proc.stdout,
        proc.stderr,
        meta,
    )


def _newest_codex_rollout(since: float) -> Path | None:
    """Locate the rollout jsonl written after `since` (newest wins)."""
    sessions = Path.home() / ".codex" / "sessions"
    if not sessions.is_dir():
        return None
    candidates = [
        p for p in sessions.rglob("rollout-*.jsonl") if p.stat().st_mtime >= since - 1
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime, default=None)
