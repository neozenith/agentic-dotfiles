#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""trajectory — forensics over a Claude Code session transcript (.jsonl).

Answers, from the real log and not from model claims: which files were actually
loaded into context (every Read tool_use, with timestamp and size-derived token
weight), what the turn/token/time costs were, how many tool calls failed, and —
when pointed at a plan's .pgsm/prompts/ directory — whether each prompt the
state machine emitted byte-for-byte reached the session (sha256 containment
check against user-turn text).

The session jsonl schema is internal and unversioned: parsing is permissive,
but the fields the report depends on fail loudly when absent.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT = Path(__file__)
SCRIPT_DIR = SCRIPT.parent.resolve()
BYTES_PER_TOKEN = 4  # coarse size→token proxy for file loads

log = logging.getLogger(__name__)


# ── Parsing ──────────────────────────────────────────────────────────────────
@dataclass
class FileLoad:
    at: str
    path: str
    sidechain: bool
    approx_tokens: int


@dataclass
class ToolCall:
    at: str
    name: str
    sidechain: bool


@dataclass
class Trajectory:
    transcript: str
    started_at: str | None = None
    ended_at: str | None = None
    models: list[str] = field(default_factory=list)
    assistant_turns: int = 0
    sidechain_events: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_errors: int = 0
    file_loads: list[FileLoad] = field(default_factory=list)
    user_texts: list[str] = field(default_factory=list)

    @property
    def wall_seconds(self) -> float:
        if not self.started_at or not self.ended_at:
            return 0.0
        start = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.ended_at.replace("Z", "+00:00"))
        return (end - start).total_seconds()

    @property
    def tool_failure_rate(self) -> float:
        return self.tool_errors / len(self.tool_calls) if self.tool_calls else 0.0


def _block_text(content: Any) -> str:
    """Flatten a message content field (str or block list) to text."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block, dict) and isinstance(block.get("content"), (str, list)):
                parts.append(_block_text(block["content"]))
    return "\n".join(parts)


def parse_transcript(path: Path) -> Trajectory:
    traj = Trajectory(transcript=str(path))
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = entry.get("type")
        at = str(entry.get("timestamp", ""))
        sidechain = bool(entry.get("isSidechain", False))
        if at:
            traj.started_at = traj.started_at or at
            traj.ended_at = at
        if sidechain:
            traj.sidechain_events += 1
        message = entry.get("message") or {}
        if kind == "assistant":
            traj.assistant_turns += 1
            model = message.get("model")
            if isinstance(model, str) and model not in traj.models:
                traj.models.append(model)
            usage = message.get("usage") or {}
            traj.input_tokens += int(usage.get("input_tokens") or 0)
            traj.output_tokens += int(usage.get("output_tokens") or 0)
            traj.cache_read_tokens += int(usage.get("cache_read_input_tokens") or 0)
            traj.cache_creation_tokens += int(usage.get("cache_creation_input_tokens") or 0)
            for block in message.get("content") or []:
                if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                    continue
                name = str(block.get("name", "?"))
                traj.tool_calls.append(ToolCall(at=at, name=name, sidechain=sidechain))
                file_path = (block.get("input") or {}).get("file_path")
                if name == "Read" and isinstance(file_path, str):
                    size = Path(file_path).stat().st_size if Path(file_path).is_file() else 0
                    traj.file_loads.append(
                        FileLoad(
                            at=at,
                            path=file_path,
                            sidechain=sidechain,
                            approx_tokens=size // BYTES_PER_TOKEN,
                        )
                    )
        elif kind == "user":
            content = message.get("content")
            text = _block_text(content)
            if text:
                traj.user_texts.append(text)
            if isinstance(content, list):
                traj.tool_errors += sum(
                    1
                    for block in content
                    if isinstance(block, dict)
                    and block.get("type") == "tool_result"
                    and block.get("is_error")
                )
    return traj


def find_transcript(session_id: str, projects_dir: Path) -> Path:
    """Locate a transcript by session UUID across all project slug dirs. Loud on miss."""
    matches = sorted(projects_dir.glob(f"*/{session_id}.jsonl"))
    if not matches:
        raise FileNotFoundError(f"no transcript for session {session_id!r} under {projects_dir}")
    return matches[0]


# ── Prompt verification (pgsm cross-check) ───────────────────────────────────
@dataclass
class PromptCheck:
    prompt_file: str
    delivered: bool


def verify_prompts(traj: Trajectory, prompts_dir: Path) -> list[PromptCheck]:
    """Did each .pgsm/prompts/ file reach the session verbatim? Containment in user-turn text."""
    checks: list[PromptCheck] = []
    for prompt_path in sorted(prompts_dir.glob("*.md")):
        text = prompt_path.read_text(encoding="utf-8").strip()
        delivered = any(text in user_text for user_text in traj.user_texts)
        checks.append(PromptCheck(prompt_file=prompt_path.name, delivered=delivered))
    return checks


# ── Reporting ────────────────────────────────────────────────────────────────
def build_report(traj: Trajectory, watch: str | None, checks: list[PromptCheck]) -> dict[str, Any]:
    loads = [fl for fl in traj.file_loads if watch is None or fl.path.startswith(watch)]
    return {
        "transcript": traj.transcript,
        "started_at": traj.started_at,
        "ended_at": traj.ended_at,
        "wall_seconds": traj.wall_seconds,
        "models": traj.models,
        "assistant_turns": traj.assistant_turns,
        "sidechain_events": traj.sidechain_events,
        "tokens": {
            "input": traj.input_tokens,
            "output": traj.output_tokens,
            "cache_read": traj.cache_read_tokens,
            "cache_creation": traj.cache_creation_tokens,
        },
        "tool_calls": len(traj.tool_calls),
        "tool_errors": traj.tool_errors,
        "tool_failure_rate": round(traj.tool_failure_rate, 4),
        "file_loads": [
            {
                "at": fl.at,
                "path": fl.path,
                "sidechain": fl.sidechain,
                "approx_tokens": fl.approx_tokens,
            }
            for fl in loads
        ],
        "prompt_checks": [{"prompt_file": c.prompt_file, "delivered": c.delivered} for c in checks],
    }


def print_human(report: dict[str, Any]) -> None:
    tokens = report["tokens"]
    print(f"transcript:  {report['transcript']}")
    print(
        f"window:      {report['started_at']} → {report['ended_at']}  ({report['wall_seconds']:.0f}s)"
    )
    print(f"models:      {', '.join(report['models']) or '(none)'}")
    print(
        f"turns:       {report['assistant_turns']} assistant, {report['sidechain_events']} sidechain events"
    )
    print(
        f"tokens:      in={tokens['input']} out={tokens['output']} "
        f"cache_read={tokens['cache_read']} cache_creation={tokens['cache_creation']}"
    )
    print(
        f"tool calls:  {report['tool_calls']} total, {report['tool_errors']} failed "
        f"(rate {report['tool_failure_rate']:.1%})"
    )
    if report["file_loads"]:
        print("\nfile loads (Read tool, real log evidence):")
        for entry in report["file_loads"]:
            side = " [sidechain]" if entry["sidechain"] else ""
            print(f"  {entry['at']}  ~{entry['approx_tokens']:>6} tok  {entry['path']}{side}")
    if report["prompt_checks"]:
        print("\nemitted-prompt delivery (pgsm .pgsm/prompts/ vs user turns):")
        for check in report["prompt_checks"]:
            mark = "DELIVERED" if check["delivered"] else "NOT FOUND"
            print(f"  [{mark}] {check['prompt_file']}")


# ── CLI ──────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    parser = argparse.ArgumentParser(
        prog="trajectory", description="Session-log forensics for plan-gap-sm runs"
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--transcript", help="Path to a session .jsonl")
    src.add_argument("--session-id", help="Session UUID to locate under the projects dir")
    parser.add_argument(
        "--projects-dir",
        default=str(Path.home() / ".claude" / "projects"),
        help="Claude Code projects dir (transcript lookup root)",
    )
    parser.add_argument(
        "--watch", default=None, help="Only report file loads whose path starts with this prefix"
    )
    parser.add_argument(
        "--prompts-dir", default=None, help="A plan's .pgsm/prompts/ dir to verify delivery against"
    )
    parser.add_argument("--json", action="store_true", help="Emit the full JSON report")
    args = parser.parse_args(argv)

    path = (
        Path(args.transcript)
        if args.transcript
        else find_transcript(args.session_id, Path(args.projects_dir))
    )
    if not path.is_file():
        raise SystemExit(f"error: transcript not found: {path}")
    traj = parse_transcript(path)
    checks = verify_prompts(traj, Path(args.prompts_dir)) if args.prompts_dir else []
    report = build_report(traj, args.watch, checks)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":  # pragma: no cover
    main()
