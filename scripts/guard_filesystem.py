#!/usr/bin/env python3
"""PreToolUse guard: never delete, never work outside the project.

Two rules, both about keeping an agent's working state visible and auditable:

1. **No deletions.** `rm`, `rmdir`, `unlink`, `git rm`, and `find -delete`
   destroy evidence. Move the path into the project-local `tmp/` instead, so a
   human can see what was discarded and restore it.
2. **No out-of-project scratch space.** `/tmp`, `/private/tmp`, `/var/folders`,
   and any `scratchpad/` outside the project are invisible to the person
   reviewing the work. Hands above the table: scratch files live in the
   project-local `tmp/`.

Tier B by the skill-environment rules: stdlib only, single file, so it starts
fast and cannot break on a missing dependency.

Contract: reads the PreToolUse payload on stdin, writes a permission decision
on stdout. A deny reason is shown to the model as the instruction for what to
do instead. Any internal error allows the call through, because a broken guard
must not wedge the session.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

# Commands whose whole purpose is to remove a path.
DELETE_COMMANDS = {"rm", "rmdir", "unlink", "shred"}

# Wrappers that may precede the real command.
COMMAND_PREFIXES = {"sudo", "time", "command", "builtin", "nohup", "xargs", "env"}

# Absolute roots that live outside any project checkout.
FORBIDDEN_ROOTS = ("/private/tmp", "/private/var/folders", "/var/folders", "/tmp", "/var/tmp")

TOOLS_WITH_PATHS = {"Write", "Edit", "NotebookEdit", "Read"}

DELETE_GUIDANCE = """\
Deleting is not allowed in this project. Never remove a file; move it aside so it stays auditable.

Use the project-local tmp/ instead:

    mkdir -p tmp/trash/<short-reason>
    mv <path> tmp/trash/<short-reason>/

Why: a deleted file leaves no evidence of what was discarded or why, and it cannot be reviewed or restored. A moved file can be both. Keep your hands above the table.

If the intent was to replace a file, write the new content over it directly. That is an edit, not a delete, and it needs no move."""

SCRATCH_GUIDANCE = """\
Working outside the project directory is not allowed. That path is invisible to the person reviewing this work.

Use the project-local tmp/ instead:

    mkdir -p tmp/
    # then write scratch files, intermediate output and helper scripts under tmp/

Why: scratch files under /tmp, /private/tmp, /var/folders or an out-of-project scratchpad cannot be inspected, diffed or audited alongside the change they support. Keep your hands above the table.

tmp/ is already gitignored, so nothing scratch will be committed."""


def allow() -> None:
    """Emit no decision, which leaves the normal permission flow untouched."""
    sys.exit(0)


def deny(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def project_root(payload: dict) -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(raw).resolve()


def split_segments(command: str) -> list[list[str]]:
    """Split a shell command into argv lists, one per pipeline/list segment.

    Uses shlex so quoted paths survive intact. Falls back to a naive split when
    the command has unbalanced quotes, because a guard that crashes on odd
    input is worse than one that over-approximates.
    """
    try:
        tokens = shlex.split(command, comments=True)
    except ValueError:
        tokens = command.split()

    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in {"&&", "||", "|", ";", "&"}:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def head_of(segment: list[str]) -> str | None:
    """The command word of a segment, skipping env assignments and wrappers."""
    for token in segment:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token):
            continue  # FOO=bar prefix
        if token in COMMAND_PREFIXES:
            continue
        return token
    return None


def find_delete_verb(command: str) -> str | None:
    """Return the deletion verb this command would run, or None."""
    for segment in split_segments(command):
        head = head_of(segment)
        if head is None:
            continue
        name = Path(head).name  # /bin/rm -> rm
        if name in DELETE_COMMANDS:
            return name
        if name == "git" and "rm" in segment[: segment.index(head) + 4]:
            return "git rm"
        if name == "find":
            if "-delete" in segment:
                return "find -delete"
            if "-exec" in segment and any(Path(t).name in DELETE_COMMANDS for t in segment):
                return "find -exec rm"
    return None


def outside_paths(command: str, root: Path) -> list[str]:
    """Absolute paths in the command that sit outside the project."""
    hits: list[str] = []
    for token in re.findall(r"[^\s'\"`]+", command):
        if not token.startswith("/"):
            continue
        if is_outside(token, root):
            hits.append(token)
    return hits


def is_outside(raw: str, root: Path) -> bool:
    candidate = Path(raw)
    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate

    if resolved == root or root in resolved.parents:
        return False  # inside the project, always fine

    text = str(resolved)
    if any(text == r or text.startswith(r + "/") for r in FORBIDDEN_ROOTS):
        return True
    return "scratchpad" in resolved.parts


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        allow()

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    root = project_root(payload)

    if tool == "Bash":
        command = tool_input.get("command", "") or ""

        verb = find_delete_verb(command)
        if verb is not None:
            deny(f"Blocked: `{verb}` deletes a path.\n\n{DELETE_GUIDANCE}")

        strays = outside_paths(command, root)
        if strays:
            shown = "\n".join(f"  {p}" for p in sorted(set(strays))[:5])
            deny(f"Blocked: this command touches paths outside the project:\n{shown}\n\n{SCRATCH_GUIDANCE}")

    elif tool in TOOLS_WITH_PATHS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if target and is_outside(target, root):
            deny(f"Blocked: `{target}` is outside the project.\n\n{SCRATCH_GUIDANCE}")

    allow()


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - a broken guard must never wedge the session
        allow()
