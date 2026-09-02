#!/usr/bin/env python3
"""PreToolUse coaching hook for Claude Code.

Reads the PreToolUse event JSON on stdin and, when a tool call breaks one of
this repo's working agreements, emits a `deny` decision whose *reason* is a
coaching message telling the model what to do INSTEAD. That turns a dead-end
denial into a redirect, so the model stops retrying near-miss variants of a
blocked command.

Two kinds of check, in this order:

1. **Structural checks** (this file). Derived from the command's argv rather
   than from a regex, because they need shell structure to be accurate:
   - *No deletions.* Commands that unlink a path destroy evidence. Move the
     path into the project-local tmp/ instead.
   - *No out-of-project scratch space.* System temp roots and any `scratchpad/`
     outside the project are invisible to the person reviewing the work.
     Applies to Bash commands and to the path arguments of `Write` / `Edit` /
     `NotebookEdit` / `Read`.
2. **Pattern rules** (`tool_coach_rules.json`). Regexes matched against the
   Bash command string, for tool-choice coaching: inline interpreter snippets,
   bare interpreters, manual import-path injection, the timeout binary. Edit
   that file to add a rule; no code change needed.

Heredoc bodies are stripped before every command check. A heredoc body is data
being written, not a command being run, so scanning it produces pure false
positives: writing a *document about* a blocked command would otherwise be
blocked by the very rule the document describes.

Contract (Claude Code hooks):
  exit 0 + JSON body  -> decision applied (we emit deny + reason).
  exit 0 + no output  -> no opinion; normal permission flow proceeds.
  exit 1              -> non-blocking error; the first stderr line is shown to
      the model and execution continues.

We FAIL LOUD, never open: a broken rules file surfaces on every call until it
is fixed, rather than silently disabling the guard. exit 1 is non-blocking by
the contract above, so a broken hook cannot wedge the session either way.

Stdlib only (json, os, re, shlex, sys, pathlib) so it has zero install/venv
dependencies and starts fast on every call.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

# -- Configuration --------------------------------------------------------
RULES_PATH = Path(__file__).with_name("tool_coach_rules.json")

# Commands whose whole purpose is to remove a path.
DELETE_COMMANDS = {"rm", "rmdir", "unlink", "shred"}

# Wrappers that may precede the real command word.
COMMAND_PREFIXES = {
    "sudo",
    "time",
    "command",
    "builtin",
    "nohup",
    "xargs",
    "env",
    "exec",
}

# Shell operators that end one command segment and start the next.
SEGMENT_SEPARATORS = {"&&", "||", "|", "&", ";", "(", ")", "{", "}", "\n"}

# Absolute roots that live outside any project checkout. Held as relative names
# and prefixed below so this file stays editable through its own guard, which
# would otherwise flag its own configuration as an out-of-project path.
FORBIDDEN_ROOTS = tuple(
    "/" + name
    for name in ("private/tmp", "private/var/folders", "var/folders", "tmp", "var/tmp")
)

# Tools that name a filesystem path in their input rather than a shell command.
TOOLS_WITH_PATHS = {"Write", "Edit", "NotebookEdit", "Read"}

HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

DELETE_GUIDANCE = """\
Deleting is not allowed in this project. Never remove a file; move it aside so it stays auditable.

Use the project-local tmp/ instead:

    mkdir -p tmp/_archived/<short-reason>
    mv <path> tmp/_archived/<short-reason>/

Why: a deleted file leaves no evidence of what was discarded or why, and it cannot be reviewed or restored. A moved file can be both. Keep your hands above the table.

If the intent was to replace a file, write the new content over it directly. That is an edit, not a delete, and it needs no move.
If the intent was to clear build or cache output, prefer the project's `make` clean target.
If the file was already staged for deletion, run `git restore --staged --worktree <path>` first, then move it."""

SCRATCH_GUIDANCE = """\
Working outside the project directory is not allowed. That path is invisible to the person reviewing this work.

Use the project-local tmp/ instead:

    mkdir -p tmp/
    # then write scratch files, intermediate output and helper scripts under tmp/

Why: scratch files under a system temp root or an out-of-project scratchpad cannot be inspected, diffed or audited alongside the change they support. Keep your hands above the table.

tmp/ is already gitignored, so nothing scratch will be committed."""


# -- Hook I/O -------------------------------------------------------------
def fail(msg: str) -> int:
    """Print one actionable line to stderr and signal a non-blocking error."""
    print(f"tool_coach: {msg}", file=sys.stderr)
    return 1


def deny(reason: str) -> None:
    """Emit the deny decision. The reason is what the model reads and acts on."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


# -- Pattern rules --------------------------------------------------------
def load_rules(rules_path: Path) -> list[dict]:
    """Parse and compile the pattern rules, raising on anything malformed."""
    if not rules_path.exists():
        raise FileNotFoundError(
            f"rules file not found at {rules_path} - create it or remove the "
            f"tool_coach hook from settings.json"
        )
    try:
        data = json.loads(rules_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{rules_path} is not valid JSON: {exc}") from exc

    rules = data.get("rules")
    if not isinstance(rules, list):
        raise ValueError(f'{rules_path} must contain a top-level "rules" array')

    for i, rule in enumerate(rules):
        if not isinstance(rule, dict) or "pattern" not in rule or "message" not in rule:
            raise ValueError(
                f'rule #{i} in {rules_path} must be an object with "pattern" and "message" keys'
            )
        # Compile eagerly so a bad regex fails loud here, not silently at match time.
        try:
            rule["_compiled"] = re.compile(rule["pattern"])
        except re.error as exc:
            raise ValueError(
                f"rule '{rule.get('name', i)}' has an invalid regex {rule['pattern']!r}: {exc}"
            ) from exc
    return rules


def match_rule(command: str, rules: list[dict]) -> dict | None:
    """The first pattern rule this command trips, or None. Order matters."""
    for rule in rules:
        if rule["_compiled"].search(command):
            return rule
    return None


# -- Shell parsing --------------------------------------------------------
def strip_heredocs(command: str) -> str:
    """Remove heredoc bodies, keeping the command lines that surround them.

    Everything between a heredoc's opening line and its closing delimiter is
    data written to a file or a pipe, not a command the shell will execute, so
    no check should read it.
    """
    lines = command.split("\n")
    kept: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        delimiters = [m.group(2) for m in HEREDOC_START.finditer(line)]
        i += 1
        for delimiter in delimiters:
            while i < len(lines) and lines[i].strip() != delimiter:
                i += 1
            i += 1  # skip the closing delimiter line itself
    return "\n".join(kept)


def split_segments(command: str) -> list[list[str]]:
    """Split a shell command into argv lists, one per pipeline/list segment.

    `shlex` with punctuation_chars keeps quoted paths intact while still
    tokenising the shell operators as their own words, so a pipeline into a
    deletion is seen as two segments. Lines are split first, because shlex
    treats a newline as plain whitespace and would otherwise let a command on
    its own line hide inside the previous one. Falls back to a naive split on
    unbalanced quotes, because a guard that over-approximates beats one that
    crashes on odd input.
    """
    tokens: list[str] = []
    for line in command.split("\n"):
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            tokens.extend(lexer)
        except ValueError:
            tokens.extend(line.split())
        tokens.append("\n")

    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in SEGMENT_SEPARATORS:
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
    seen_prefix = False
    for token in segment:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token):
            continue  # FOO=bar prefix
        if Path(token).name in COMMAND_PREFIXES:
            seen_prefix = True
            continue
        if seen_prefix and token.startswith("-"):
            continue  # a wrapper's own flags, for example xargs -0
        return token
    return None


def find_delete_verb(command: str) -> str | None:
    """Return the deletion verb this command would run, or None."""
    for segment in split_segments(command):
        head = head_of(segment)
        if head is None:
            continue
        name = Path(head).name  # an absolute path collapses to its basename
        if name in DELETE_COMMANDS:
            return name
        rest = segment[segment.index(head) + 1 :]
        if name == "git" and "rm" in rest[:3]:
            return "git rm"
        if name == "find":
            if "-delete" in rest:
                return "find -delete"
            if "-exec" in rest and any(Path(t).name in DELETE_COMMANDS for t in rest):
                return "find -exec"
    return None


# -- Out-of-project paths -------------------------------------------------
def project_root(payload: dict) -> Path:
    """Where the project lives: the harness env var, else the call's cwd."""
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(raw).resolve()


def is_outside(raw: str, root: Path) -> bool:
    """True when this path is scratch space the reviewer cannot see."""
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


def outside_paths(command: str, root: Path) -> list[str]:
    """Absolute paths in the command that sit outside the project."""
    return [
        token
        for token in re.findall(r"[^\s'\"`]+", command)
        if token.startswith("/") and is_outside(token, root)
    ]


# -- Decision -------------------------------------------------------------
def decide(payload: dict, rules: list[dict], root: Path) -> str | None:
    """The deny reason for this tool call, or None to stay out of the way."""
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool == "Bash":
        command = strip_heredocs(tool_input.get("command", "") or "")
        if not command.strip():
            return None

        verb = find_delete_verb(command)
        if verb is not None:
            return f"Blocked: `{verb}` deletes a path.\n\n{DELETE_GUIDANCE}"

        strays = outside_paths(command, root)
        if strays:
            shown = "\n".join(f"  {p}" for p in sorted(set(strays))[:5])
            return f"Blocked: this command touches paths outside the project:\n{shown}\n\n{SCRATCH_GUIDANCE}"

        rule = match_rule(command, rules)
        if rule is not None:
            return str(rule["message"])

    elif tool in TOOLS_WITH_PATHS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if target and is_outside(target, root):
            return f"Blocked: `{target}` is outside the project.\n\n{SCRATCH_GUIDANCE}"

    return None


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0  # nothing to inspect

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return fail(f"could not parse hook stdin as JSON: {exc}")

    try:
        rules = load_rules(RULES_PATH)
    except (FileNotFoundError, ValueError) as exc:
        return fail(str(exc))

    reason = decide(payload, rules, project_root(payload))
    if reason is not None:
        deny(reason)
    return 0  # exit 0 either way: with JSON => applied, without => no opinion


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
