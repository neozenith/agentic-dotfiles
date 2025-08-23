#!/usr/bin/env python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "psutil",
# ]
# ///

import json
import logging
import sys
from pathlib import Path
import subprocess
from shlex import split

import psutil

_run = lambda cmd: subprocess.check_output(split(cmd), text=True).strip()  # noqa: E731

GIT_ROOT = Path(_run("git rev-parse --show-toplevel"))
GIT_SUPER_PROJECT = Path(_run("git rev-parse --show-superproject-working-tree")).resolve()
IS_WORKTREE = GIT_ROOT != GIT_SUPER_PROJECT
CLAUDE_ROOT = Path(__file__).parent.parent.resolve()

log = logging.getLogger(str(GIT_ROOT))

def find_processes():
    current_process = psutil.Process()
    for p in current_process.parents():
        if p.pid != 1 and p.cmdline() and p.cmdline()[0] == "claude":
            return current_process, p
    return current_process, None

def log_file_location(claude_pid = None):
    if claude_pid:
        log_file = CLAUDE_ROOT / "logs" / str(claude_pid) / "claude_hooks.log"
    else:
        log_file = CLAUDE_ROOT / "logs" / "claude_hooks.log"
    return log_file

def main(args, current_process, claude_process):

    # Read hook context from stdin
    try:
        input_data = sys.stdin.read()
        structured_log(input_data, current_process, claude_process)
    except (json.JSONDecodeError, Exception) as e:
        log.error(f"CLAUDE HOOKS::ERROR::Failed to parse hook data: {e}")
        log.info(f"CLAUDE HOOKS::FALLBACK::Running with args: {args}")

def structured_log(input_data, current_process, claude_process):
    hook_data = json.loads(input_data)
    hook_event = hook_data.get("hook_event_name", "Unknown")
    session_id = hook_data.get("session_id", "Unknown")
    tool_name = hook_data.get("tool_name", "N/A")

    # Log detailed Claude process information
    log_data = {
        "event": hook_event,
        "session_id": session_id,
        "tool_name": tool_name,
        "git_super_project": str(GIT_SUPER_PROJECT),
        "repo": str(GIT_ROOT),
        "is_worktree": IS_WORKTREE,
        "claude_pid": claude_process.pid if claude_process else None,
        "pid": current_process.pid,
        "hook_data": hook_data
    }
    log.info(f"{hook_event}::{json.dumps(log_data)}")

if __name__ == "__main__":  # pragma: no cover
    current_process, claude_process = find_processes()
    claude_process_id = claude_process.pid if claude_process else None
    log_file = log_file_location(claude_pid=claude_process_id)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="a"),  # Append to file
            logging.StreamHandler(),  # Also output to console
        ],
    )

    main(sys.argv[1:], current_process, claude_process)