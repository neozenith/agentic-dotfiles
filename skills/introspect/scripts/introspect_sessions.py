#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "sqlite-muninn>=0.3.3",
#   "gliner2>=1.2,<2",
#   "huggingface-hub>=0.25",
# ]
# ///
"""
introspect_sessions - Query and analyze Claude Code session logs using pure Python with SQLite cache.

A self-contained CLI for querying session JSONL files stored at:
    ~/.claude/projects/{project-path-kebab-cased}/{session_uuid}.jsonl

Features:
    - SQLite caching with incremental updates based on file mtime
    - FTS5 full-text search on message content
    - No external dependencies (pure Python 3.12+ with sqlite3)
    - Full session event parsing with parent-child relationships
    - UUID-based event lookup and tree traversal
    - Meta-prompt evaluation via claude -p subprocess

Usage:
    uv run introspect_sessions.py cache init              # Initialize cache
    uv run introspect_sessions.py cache update            # Incremental update
    uv run introspect_sessions.py cache rebuild           # Full rebuild
    uv run introspect_sessions.py cache status            # Show cache status
    uv run introspect_sessions.py projects                # List all projects
    uv run introspect_sessions.py search "pattern"        # Full-text search
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import time
import urllib.request

import sqlite_muninn
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from textwrap import dedent
from typing import Any, Literal


# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

CLAUDE_HOME = Path.home() / ".claude"
PROJECTS_PATH = CLAUDE_HOME / "projects"

# Cache stored in home directory's .claude/cache/introspect_sessions.db
CACHE_DIR = CLAUDE_HOME / "cache"
CACHE_DB_PATH = CACHE_DIR / "introspect_sessions.db"

# Logging setup
log = logging.getLogger(__name__)

# v18 (Summariser G2): session_summaries table mirrored from the backend
#   schema so both ingesters share one cache file. The summarisation *logic*
#   parity (producing identical summary rows) is G11; this is the DDL mirror.
# v19 (Summariser G3): rollup_summaries table mirrored from the backend schema
#   (same DDL-mirror rationale as v18).
SCHEMA_VERSION = "20"

# Sentinel key in cache_metadata used to gate the one-shot (session_id, uuid)
# dedupe migration. Mirrors DEDUPE_SESSION_UUID_MIGRATION_KEY in
# src/claude_code_sessions/database/sqlite/cache.py — both scripts write to the
# same DB and read/set the same sentinel, so whichever runs first does the work
# and the other becomes a no-op.
DEDUPE_SESSION_UUID_MIGRATION_KEY = "dedupe_session_uuid_v1"


# ============================================================================
# Pricing Configuration
# ============================================================================

# Verified 2026-07-13. Output is always 5x input. Must stay in sync with the
# package copy in database/sqlite/pricing.py (parity-tested).
PRICING = {
    "fable": {
        "input": 10.0,  # per 1M tokens
        "output": 50.0,
        "cache_read_multiplier": 0.1,  # 90% discount
        "cache_write_multiplier": 1.25,  # 25% premium
    },
    "opus": {
        "input": 5.0,
        "output": 25.0,
        "cache_read_multiplier": 0.1,
        "cache_write_multiplier": 1.25,
    },
    "sonnet": {
        "input": 3.0,
        "output": 15.0,
        "cache_read_multiplier": 0.1,
        "cache_write_multiplier": 1.25,
    },
    "haiku": {
        "input": 1.0,
        "output": 5.0,
        "cache_read_multiplier": 0.1,
        "cache_write_multiplier": 1.25,
    },
}


def model_family_from_id(model_id: str | None) -> str:
    """Extract model family (fable/opus/sonnet/haiku) from a full model ID string."""
    if model_id is None:
        return "unknown"
    model_lower = model_id.lower()
    for family in ("fable", "opus", "sonnet", "haiku"):
        if family in model_lower:
            return family
    return "unknown"


def _compute_event_costs(
    model_id: str | None,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
) -> tuple[float, float, float]:
    """Compute (token_rate, billable_tokens, total_cost_usd) for an event.

    Returns:
        token_rate       — input $/Mtok for this event's model (0.0 if unknown)
        billable_tokens  — weighted input-equivalent:
                           input + output*5 + cache_read*0.1 + cache_write*1.25
        total_cost_usd   — billable_tokens * token_rate / 1_000_000

    All model families share the same relative multipliers (output 5×, cache_read 0.1×,
    cache_write 1.25×), so token_rate alone is sufficient to reconstruct the full cost.
    Events with an unknown model (no model_id) return (0.0, 0.0, 0.0).
    """
    family = model_family_from_id(model_id)
    pricing = PRICING.get(family)

    if pricing is None:
        return 0.0, 0.0, 0.0

    token_rate = pricing["input"]
    output_mult = pricing["output"] / pricing["input"]  # always 5.0
    cache_read_mult = pricing["cache_read_multiplier"]  # always 0.1
    cache_write_mult = pricing["cache_write_multiplier"]  # always 1.25

    billable = (
        input_tokens
        + output_tokens * output_mult
        + cache_read_tokens * cache_read_mult
        + cache_creation_tokens * cache_write_mult
    )
    return token_rate, round(billable, 4), round(billable * token_rate / 1_000_000, 8)


# Curated model_id → advertised context-window size (tokens). Matched by
# substring like model_family(), since model ids carry date suffixes. 1M is
# GA (not beta) on opus-4-6/4-7/4-8 and sonnet-4-6, so the window is a pure
# function of model_id. Unknown / synthetic ids resolve to None (ratio
# undefined). Mirror of pricing.py CONTEXT_WINDOWS in the backend package.
CONTEXT_WINDOWS: dict[str, int] = {
    "opus-4-6": 1_000_000,
    "opus-4-7": 1_000_000,
    "opus-4-8": 1_000_000,
    "sonnet-4-6": 1_000_000,
    "opus-4-5": 200_000,
    "sonnet-4-5": 200_000,
    "haiku-4-5": 200_000,
    "qwen2.5-coder": 32_768,  # native default; YaRN 128k is off by default
    "devstral-small-2": 256_000,
}


def context_window(model_id: str | None) -> int | None:
    """Resolve a model id to its context-window size, or None if unknown."""
    if not model_id:
        return None
    low = model_id.lower()
    # Longest-key-first so a shorter key can't shadow a more specific
    # superstring key (e.g. "opus-4-5" must not win over "opus-4-50").
    for key in sorted(CONTEXT_WINDOWS, key=len, reverse=True):
        if key in low:
            return CONTEXT_WINDOWS[key]
    return None


def context_ratio(tokens: int, window: int | None) -> float | None:
    """Raw context-window utilization: the fraction ``tokens / window``.

    Returns None when the window is unknown/zero (ratio undefined). This is a
    purely quantitative measure — no categorical "smart/caution/danger" zone
    labeling (see the G2 ADR "Quantitative ratio only").
    """
    if not window:
        return None
    return tokens / window


# "Too-fast" reply detection (G5): flag a human reply that arrived faster than
# even a fast skim of the assistant's response could be read. READ_TOKENS_PER_SEC
# ≈ 480 wpm fast-skim (~0.75 words/token); the min-token floor prevents flagging
# instant replies to short outputs. See the G5 ADR for the WPM evidence.
READ_TOKENS_PER_SEC = 8
TOO_FAST_MIN_TOKENS = 200


def _delta_ms(start_iso: str | None, end_iso: str | None) -> int | None:
    """Milliseconds between two ISO-8601 timestamps, or None if either is
    missing/unparseable or the span is negative (clock skew). Shared by the
    response-duration (G4) and turn-timing (G5) passes."""
    if not start_iso or not end_iso:
        return None
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    delta = (end - start).total_seconds() * 1000
    return int(delta) if delta >= 0 else None


def _first_content_block_type(content: Any) -> str | None:
    """Return the shape of a message's content field.

    Returns:
        'string'      — raw string (human-typed prompt)
        'text'        — list whose first block has type='text'
        'tool_use'    — list whose first block has type='tool_use'
        'tool_result' — list whose first block has type='tool_result'
        'thinking'    — list whose first block has type='thinking'
        other str     — first block's type (catch-all)
        None          — content is None or empty list
    """
    if content is None:
        return None
    if isinstance(content, str):
        return "string"
    if isinstance(content, list) and content and isinstance(content[0], dict):
        return content[0].get("type")
    return None


def _message_kind(event_type: str, is_meta: bool, content: Any, is_subagent: bool = False) -> str:
    """Classify an event into one of 9 fine-grained message kinds.

    Kinds:
        human              — user, not meta, string content (actual typed prompts)
        task_notification  — user, not meta, string starting with <task-notification>
        tool_result        — user, not meta, tool_result list
        user_text          — user, not meta, text/other list
        meta               — user, isMeta=true (system-injected context)
        assistant_text     — assistant, text list
        thinking           — assistant, thinking list
        tool_use           — assistant, tool_use list
        other              — progress / system / queue-operation / etc.

    When ``is_subagent`` is true (the event belongs to a subagent context),
    the base kind is prefixed with ``subagent-`` so subagent activity is
    distinguishable from main-thread activity.
    """
    base = _base_message_kind(event_type, is_meta, content)
    return f"subagent-{base}" if is_subagent else base


def _base_message_kind(event_type: str, is_meta: bool, content: Any) -> str:
    """The bare (non-subagent) message kind — one of 9 fine-grained kinds."""
    fct = _first_content_block_type(content)
    if event_type == "user":
        if is_meta:
            return "meta"
        if fct == "string":
            if isinstance(content, str) and content.lstrip().startswith("<task-notification>"):
                return "task_notification"
            return "human"
        if fct == "tool_result":
            return "tool_result"
        return "user_text"
    if event_type == "assistant":
        if fct == "thinking":
            return "thinking"
        if fct == "tool_use":
            return "tool_use"
        return "assistant_text"
    return "other"


# ============================================================================
# event_calls fact-table extraction
# ============================================================================
# Byte-equivalent copy of
# src/claude_code_sessions/database/sqlite/calls.py — keep in lockstep.
# The two are independent files (the skill is a standalone PEP-723 script
# and cannot import from the package) but their extracted call rows must
# match exactly so dashboard queries and introspect queries agree.

# ---------------------------------------------------------------------------
# Regexes — compiled once at import time.
# ---------------------------------------------------------------------------

# Locate <system-reminder>...</system-reminder> blocks (non-greedy, dotall so
# newlines inside the reminder body are consumed).
_SYSTEM_REMINDER_RE = re.compile(
    r"<system-reminder>(.*?)</system-reminder>",
    re.DOTALL,
)

# Extract absolute paths following "Contents of " inside a system-reminder.
# This matches the canonical format used by Claude Code to inject CLAUDE.md
# and .claude/rules/*.md files into the conversation. The character class
# excludes whitespace AND ``:`` so the trailing colon ("Contents of /foo.md:")
# is not captured into the call_name — and neither are quote characters
# from paths embedded inside quoted strings.
_RULE_PATH_RE = re.compile(r"Contents of\s+(/[^\s:'\"]+)")

# Shell separators that start a new command segment in an input.command
# string. Order matters only to the extent that ``re.split`` consumes all
# alternations at once — each alternation must be a distinct literal.
_SHELL_SPLIT_RE = re.compile(r"\|\||&&|;|\|")

# Command "wrappers" whose first positional argument is itself a command.
# We skip past them (and any of their flags) to find the real program head.
_WRAPPERS: frozenset[str] = frozenset(
    {
        "sudo",
        "time",
        "nohup",
        "exec",
        "xargs",
        "env",
        "command",
    }
)

# Bash control-flow keywords that INTRODUCE a command. A segment like
# ``do cmd`` really invokes ``cmd`` — the ``do`` is syntactic scaffolding
# from a surrounding for/while/until loop that survived the segment
# splitter. Unwrapping them behaves like ``_WRAPPERS`` but without flag
# consumption (these keywords don't take ``-flags``).
_SHELL_KEYWORDS_UNWRAP: frozenset[str] = frozenset(
    {
        "if",
        "elif",
        "then",
        "else",
        "do",
        "while",
        "until",
    }
)

# Bash tokens that, when appearing as the first non-env word, mean the
# segment carries no real command — either a loop header (``for i in …``,
# ``case X in``) or a block terminator (``done``, ``fi``, ``esac``).
_SHELL_SEGMENT_REJECT: frozenset[str] = frozenset(
    {
        "for",
        "case",
        "in",
        "done",
        "fi",
        "esac",
    }
)

# GNU make flags that take a following positional argument. When parsing
# ``make <target>`` segments we need to skip past these flag+arg pairs so
# the arg isn't misread as a target name (e.g. ``make -C subproject test``
# has target ``test``, not ``subproject``).
_MAKE_FLAGS_WITH_ARG: frozenset[str] = frozenset(
    {
        "-C",
        "-f",
        "-I",
        "-j",
        "-l",
        "-o",
        "-W",
    }
)

# ``uv run`` flags that take a following positional argument. Needed so
# we don't mistake the argument for the script being invoked — e.g. in
# ``uv run --directory subproject pytest`` the script is ``pytest``.
_UV_RUN_FLAGS_WITH_ARG: frozenset[str] = frozenset(
    {
        "--directory",
        "--with",
        "--with-editable",
        "--with-requirements",
        "--python",
        "-p",
        "--group",
        "--extra",
        "--index-url",
        "--extra-index-url",
        "--find-links",
        "--package",
        "--prerelease",
        "--index-strategy",
        "--resolution",
        "--exclude-newer",
        "--keyring-provider",
        "--refresh-package",
    }
)

# ``bun run`` flags that take a following positional argument.
_BUN_RUN_FLAGS_WITH_ARG: frozenset[str] = frozenset(
    {
        "--cwd",
        "--config",
        "-c",
    }
)


# ---------------------------------------------------------------------------
# CLI head parsing
# ---------------------------------------------------------------------------


def _parse_cli_segments(command: str) -> list[tuple[str, list[str]]]:
    """Parse a shell command into ``(head, post_head_tokens)`` segments.

    Each returned tuple is one sub-command: the program name and the
    remaining tokens (arguments, flags) in order. Wrapper commands like
    ``sudo`` are skipped and the wrapped program is returned as the head.

    Examples
    --------
    >>> _parse_cli_segments("gh pr view 42")
    [('gh', ['pr', 'view', '42'])]
    >>> _parse_cli_segments("aws s3 ls | grep foo")
    [('aws', ['s3', 'ls']), ('grep', ['foo'])]
    >>> _parse_cli_segments("sudo -E make test")
    [('make', ['test'])]
    """
    if not command:
        return []

    out: list[tuple[str, list[str]]] = []
    for segment in _SHELL_SPLIT_RE.split(command):
        tokens = segment.strip().split()
        result = _segment_head_and_rest(tokens)
        if result is not None:
            out.append(result)
    return out


def _parse_cli_heads(command: str) -> list[str]:
    """Return the program-name head(s) of each sub-command in a shell string.

    Thin wrapper over ``_parse_cli_segments`` for callers that only care
    about the heads (backwards compatibility with the original API).
    """
    return [head for head, _rest in _parse_cli_segments(command)]


def _parse_make_targets(tokens_after_make: list[str]) -> list[str]:
    """Extract the target names from tokens appearing after ``make``.

    Skips flags (``-j``, ``-s``, ``--silent``…) and the positional
    arguments consumed by known flag-with-arg pairs (``-C dir``,
    ``-f Makefile``, etc.). Also skips ``VAR=value`` overrides. The rest
    are treated as target names.

    Examples
    --------
    >>> _parse_make_targets(['test'])
    ['test']
    >>> _parse_make_targets(['-C', 'subproject', 'test'])
    ['test']
    >>> _parse_make_targets(['test', 'format'])
    ['test', 'format']
    >>> _parse_make_targets(['CI=true', '-j', '4', 'ci'])
    ['ci']
    >>> _parse_make_targets(['--directory=subproj', 'build'])
    ['build']
    """
    targets: list[str] = []
    i = 0
    while i < len(tokens_after_make):
        tok = tokens_after_make[i]
        if tok.startswith("--"):
            # Long-form flag. `--directory=subproj` is self-contained;
            # `--jobs 4` would need a lookahead, but such forms are rare
            # in practice. Skip a single token either way.
            i += 1
            continue
        if tok in _MAKE_FLAGS_WITH_ARG:
            # Consume the flag plus its argument.
            i += 2
            continue
        if tok.startswith("-"):
            # Other short flag (no arg), e.g. `-s`, `-k`, `-n`.
            i += 1
            continue
        if _is_env_assignment(tok):
            # Make variable override (`CI=true`) — not a target.
            i += 1
            continue
        if _is_shell_redirection(tok):
            # `2>&1`, `&`, `>log`, etc. — shell artifacts that slipped
            # past the segment splitter (common in `make test 2>&1 | tee`).
            # Never a target.
            i += 1
            continue
        targets.append(tok)
        i += 1
    return targets


def _parse_runner_script(
    tokens_after_runner: list[str],
    flags_with_arg: frozenset[str],
) -> str | None:
    """Extract the first positional after a ``<runner> run …`` sequence.

    ``tokens_after_runner`` is the slice of tokens *after* the runner's
    head — e.g. for ``uv run --directory subproj pytest tests/`` it's
    ``['run', '--directory', 'subproj', 'pytest', 'tests/']``. Returns
    the script/target name (basename'd), or ``None`` if:

    - The first token isn't ``run`` (runner is being used for something
      other than invoking a script, e.g. ``uv sync``, ``bun install``).
    - There's no positional after the flags (malformed or truncated).

    Shared between ``uv run`` and ``bun run``; the only per-runner knob
    is the set of flags that consume a following argument.
    """
    if not tokens_after_runner or tokens_after_runner[0] != "run":
        return None

    i = 1  # skip the literal "run"
    while i < len(tokens_after_runner):
        tok = tokens_after_runner[i]
        # `--flag=value` is self-contained — skip one token.
        if tok.startswith("--") and "=" in tok:
            i += 1
            continue
        # Flag that consumes the next positional.
        if tok in flags_with_arg:
            i += 2
            continue
        # Other flags (boolean switches) skip one token.
        if tok.startswith("-"):
            i += 1
            continue
        # Env assignments (common before uv/bun, but usually stripped
        # upstream; belt-and-braces).
        if _is_env_assignment(tok):
            i += 1
            continue
        # Shell redirection artifacts that slipped the splitter.
        if _is_shell_redirection(tok):
            i += 1
            continue
        # First real positional — this is what's being invoked.
        # Strip to basename so absolute paths don't fragment the top-N.
        return tok.rsplit("/", 1)[-1] or None

    return None


def _is_shell_redirection(tok: str) -> bool:
    """True for shell redirection / control tokens like ``2>&1``, ``&``, ``>log``.

    Remaining forms we haven't split on upstream:

    - ``&``                 — background the command
    - ``>``, ``>>``, ``<``  — redirection operators (standalone or ``>file``)
    - ``2>``, ``2>&1``, ``2>>file`` — stderr redirection (fd prefix)
    """
    if not tok:
        return False
    first = tok[0]
    if first in "<>&":
        return True
    # fd-prefixed forms like `1>`, `2>>`, `2>&1`.
    if first.isdigit() and len(tok) > 1 and tok[1] in "<>":
        return True
    return False


def _segment_head_and_rest(tokens: list[str]) -> tuple[str, list[str]] | None:
    """Skip env-var assignments and wrappers, return ``(head, rest)``.

    ``rest`` is the slice of ``tokens`` after the head — i.e. the
    arguments and flags passed to the program. Returns ``None`` when the
    segment is empty, contains only env assignments/wrappers, or begins
    with a bash control-flow token that means "no real command here".
    """
    i = 0

    # Skip KEY=VALUE env assignments at the start of a segment.
    while i < len(tokens) and _is_env_assignment(tokens[i]):
        i += 1

    # Reject segments that are purely bash control structure (loop
    # headers like `for i in LIST`, block terminators like `done`/`fi`).
    # These appear as their own segments after splitting on `;` and
    # have no meaningful command to record.
    if i < len(tokens) and tokens[i] in _SHELL_SEGMENT_REJECT:
        return None

    # Unwrap shell control keywords that INTRODUCE a command:
    # `do cmd`, `then cmd`, `while cond`, etc. The real invocation is
    # whatever comes next. No flag-consumption pass because these
    # keywords don't take options.
    while i < len(tokens) and tokens[i] in _SHELL_KEYWORDS_UNWRAP:
        i += 1

    # Re-check the rejection list after keyword unwrap (handles nested
    # combos like `do done` which would degenerate to nothing).
    if i < len(tokens) and tokens[i] in _SHELL_SEGMENT_REJECT:
        return None

    # Unwrap sudo/time/nohup/xargs/env/... recursively.
    while i < len(tokens) and tokens[i] in _WRAPPERS:
        i += 1
        # Consume wrapper flags (e.g. ``sudo -E``, ``xargs -P 4 -n 1``).
        while i < len(tokens) and tokens[i].startswith("-"):
            i += 1
        # ``env`` can be followed by additional KEY=VALUE assignments.
        while i < len(tokens) and _is_env_assignment(tokens[i]):
            i += 1

    if i >= len(tokens):
        return None

    raw = tokens[i]
    # Strip a leading shell substitution/grouping character like "(".
    raw = raw.lstrip("(")
    # Basename: /usr/bin/gh → gh
    raw = raw.rsplit("/", 1)[-1]
    # Drop trailing shell metacharacters stuck to the word.
    raw = raw.rstrip("();&")
    if not raw:
        return None
    # Reject heads that are pure punctuation — bare quotes, semicolons,
    # and other shell metacharacters that sometimes survive tokenisation
    # of multi-line heredocs or `sh -c "..."` arguments. A real command
    # name always contains at least one letter or digit.
    if not any(c.isalnum() for c in raw):
        return None
    return raw, tokens[i + 1 :]


def _head_of_segment(tokens: list[str]) -> str | None:
    """Return just the head of a segment (kept for internal call sites)."""
    result = _segment_head_and_rest(tokens)
    return result[0] if result else None


def _is_env_assignment(token: str) -> bool:
    """True for tokens of the form ``NAME=value`` (valid env var assignment)."""
    if "=" not in token or token.startswith("-") or token.startswith("="):
        return False
    name, _, _ = token.partition("=")
    if not name:
        return False
    # POSIX env var names: letters, digits, underscore; cannot start with digit.
    if not (name[0].isalpha() or name[0] == "_"):
        return False
    return all(c.isalnum() or c == "_" for c in name)


# ---------------------------------------------------------------------------
# Rule-path parsing
# ---------------------------------------------------------------------------


def _extract_rule_paths(text: str) -> list[str]:
    """Return every rule-file path cited in <system-reminder> blocks in ``text``."""
    paths: list[str] = []
    for reminder in _SYSTEM_REMINDER_RE.findall(text):
        for match in _RULE_PATH_RE.finditer(reminder):
            paths.append(match.group(1))
    return paths


# ---------------------------------------------------------------------------
# Top-level extractor
# ---------------------------------------------------------------------------


def extract_calls(raw: dict[str, Any]) -> list[tuple[int, str, str]]:
    """Return ``(ord, call_type, call_name)`` rows for an event's signals.

    ``ord`` is the position of the source content block (or zero for rule
    rows derived from embedded text). Order within an event is preserved so
    downstream queries can reconstruct the sequence of actions faithfully.
    """
    calls: list[tuple[int, str, str]] = []
    message = raw.get("message") if isinstance(raw, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return calls

    for idx, block in enumerate(content):
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "tool_use":
            calls.extend(_extract_tool_use(idx, block))
        elif block_type == "text":
            text = block.get("text") or ""
            for path in _extract_rule_paths(text):
                calls.append((idx, "rule", path))
    return calls


def _extract_tool_use(idx: int, block: dict[str, Any]) -> list[tuple[int, str, str]]:
    """Extract rows for a single tool_use content block."""
    name = block.get("name") or ""
    raw_input = block.get("input")
    inp: dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}
    rows: list[tuple[int, str, str]] = []

    if name == "Skill":
        skill_val = inp.get("skill")
        skill = skill_val.strip() if isinstance(skill_val, str) else ""
        if skill:
            rows.append((idx, "skill", skill))
        else:
            # Fallback: still count the tool_use even if input is malformed.
            rows.append((idx, "tool", name))
        return rows

    if name == "Agent":
        subagent_val = inp.get("subagent_type")
        subagent = subagent_val.strip() if isinstance(subagent_val, str) else ""
        if subagent:
            rows.append((idx, "subagent", subagent))
        else:
            rows.append((idx, "tool", name))
        return rows

    if name:
        rows.append((idx, "tool", name))

    if name == "Bash":
        command_val = inp.get("command")
        command = command_val if isinstance(command_val, str) else ""
        # Walk each pipeline/chain segment once. For every segment we
        # emit one 'cli' row (the head) plus, when the head is a known
        # runner, additional rows that identify what the runner is
        # actually executing:
        #   - ``make <target>``     → one 'make_target' row per target
        #   - ``uv run <script>``   → one 'uv_script' row
        #   - ``bun run <script>``  → one 'bun_script' row
        # These additional rows augment the 'cli' signal — `uv` still
        # appears in the top-CLIs, but the uv_script dimension lets you
        # slice "what's actually being run under uv".
        for head, rest in _parse_cli_segments(command):
            rows.append((idx, "cli", head))
            if head == "make":
                for target in _parse_make_targets(rest):
                    rows.append((idx, "make_target", target))
            elif head == "uv":
                script = _parse_runner_script(rest, _UV_RUN_FLAGS_WITH_ARG)
                if script:
                    rows.append((idx, "uv_script", script))
            elif head == "bun":
                script = _parse_runner_script(rest, _BUN_RUN_FLAGS_WITH_ARG)
                if script:
                    rows.append((idx, "bun_script", script))

    return rows


# ============================================================================
# SQLite Cache Schema
# ============================================================================

SCHEMA_SQL = """
-- Source files table: tracks all parsed JSONL files
CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    mtime REAL NOT NULL,
    size_bytes INTEGER NOT NULL,
    line_count INTEGER NOT NULL,
    last_ingested_at TEXT NOT NULL,
    project_id TEXT NOT NULL,
    session_id TEXT,  -- NULL for orphan agent files
    file_type TEXT NOT NULL CHECK (file_type IN ('main_session', 'subagent', 'agent_root'))
);

CREATE INDEX IF NOT EXISTS idx_source_files_project ON source_files(project_id);
CREATE INDEX IF NOT EXISTS idx_source_files_session ON source_files(session_id);
CREATE INDEX IF NOT EXISTS idx_source_files_mtime ON source_files(mtime);

-- Projects table: aggregated project metadata
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT UNIQUE NOT NULL,
    first_activity TEXT,
    last_activity TEXT,
    session_count INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_projects_last_activity ON projects(last_activity);

-- Sessions table: aggregated session metadata
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    first_timestamp TEXT,
    last_timestamp TEXT,
    event_count INTEGER DEFAULT 0,
    subagent_count INTEGER DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cache_read_tokens INTEGER DEFAULT 0,
    total_cache_creation_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    avg_tps REAL,
    total_idle_ms INTEGER DEFAULT 0,
    total_active_ms INTEGER DEFAULT 0,
    peak_context_ratio REAL,
    UNIQUE(project_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last_timestamp ON sessions(last_timestamp);

-- Events table: all parsed events
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT,
    parent_uuid TEXT,
    prompt_id TEXT,
    event_type TEXT NOT NULL,
    msg_kind TEXT,
    timestamp TEXT,
    timestamp_local TEXT,
    session_id TEXT,
    project_id TEXT NOT NULL,
    is_sidechain INTEGER DEFAULT 0,
    agent_id TEXT,
    agent_slug TEXT,
    message_role TEXT,
    message_content TEXT,  -- Plain text for FTS
    message_content_json TEXT,  -- Original JSON structure
    model_id TEXT,
    request_id TEXT,
    stop_reason TEXT,
    is_response_head INTEGER DEFAULT 1,
    context_tokens INTEGER DEFAULT 0,
    context_window INTEGER,
    context_ratio REAL,
    response_duration_ms INTEGER,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_creation_tokens INTEGER DEFAULT 0,
    cache_5m_tokens INTEGER DEFAULT 0,
    token_rate REAL DEFAULT 0.0,
    billable_tokens REAL DEFAULT 0.0,
    total_cost_usd REAL DEFAULT 0.0,
    source_file_id INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_uuid ON events(uuid);
CREATE INDEX IF NOT EXISTS idx_events_request_id ON events(request_id);
CREATE INDEX IF NOT EXISTS idx_events_parent_uuid ON events(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_events_prompt_id ON events(prompt_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_msg_kind ON events(msg_kind);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_source_file ON events(source_file_id);
CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events(session_id, timestamp);

-- FTS5 virtual table for full-text search on message content
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    message_content,
    content='events',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
    INSERT INTO events_fts(rowid, message_content) VALUES (new.id, new.message_content);
END;

CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
    INSERT INTO events_fts(events_fts, rowid, message_content) VALUES('delete', old.id, old.message_content);
END;

CREATE TRIGGER IF NOT EXISTS events_au AFTER UPDATE ON events BEGIN
    INSERT INTO events_fts(events_fts, rowid, message_content) VALUES('delete', old.id, old.message_content);
    INSERT INTO events_fts(rowid, message_content) VALUES (new.id, new.message_content);
END;

-- Cache metadata table
CREATE TABLE IF NOT EXISTS cache_metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Event edges table: parent-child relationships for graph traversal
CREATE TABLE IF NOT EXISTS event_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_uuid TEXT NOT NULL,
    parent_event_uuid TEXT NOT NULL,
    source_file_id INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_event_edges_forward ON event_edges(project_id, session_id, event_uuid);
CREATE INDEX IF NOT EXISTS idx_event_edges_reverse ON event_edges(project_id, session_id, parent_event_uuid);
CREATE INDEX IF NOT EXISTS idx_event_edges_source_file ON event_edges(source_file_id);

-- =====================================================================
-- event_calls — raw fact table for tool/skill/subagent/cli/rule calls
-- =====================================================================
-- One row per observed "call" inside an event. An assistant message may
-- carry N parallel tool_use blocks, a Bash command may invoke several
-- CLI heads, and a user message may inject many <system-reminder> rule
-- blocks — each contributes its own row.
--
-- call_type discriminator:
--   'tool'        - generic tool_use (Read, Edit, Grep, Write, ...). Bash
--                   also emits one 'tool' row plus N 'cli' rows.
--   'skill'       - tool_use with name=="Skill"; call_name = input.skill
--   'subagent'    - tool_use with name=="Agent"; call_name = input.subagent_type
--   'cli'         - command head parsed from Bash input.command
--   'rule'        - .claude/rules/... path parsed from <system-reminder> text
--   'make_target' - target arg(s) parsed from `make <target> ...` segments
--
-- timestamp/project_id/session_id are denormalized off `events` so
-- dashboard-style time/project filters don't need a join.
-- =====================================================================
CREATE TABLE IF NOT EXISTS event_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    ord INTEGER NOT NULL DEFAULT 0,
    call_type TEXT NOT NULL CHECK (
        call_type IN (
            'tool', 'skill', 'subagent', 'cli', 'rule',
            'make_target', 'uv_script', 'bun_script'
        )
    ),
    call_name TEXT NOT NULL,
    timestamp TEXT,
    project_id TEXT NOT NULL,
    session_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_calls_event ON event_calls(event_id);
CREATE INDEX IF NOT EXISTS idx_event_calls_type_name ON event_calls(call_type, call_name);
CREATE INDEX IF NOT EXISTS idx_event_calls_timestamp ON event_calls(timestamp);
CREATE INDEX IF NOT EXISTS idx_event_calls_project_session
    ON event_calls(project_id, session_id);


-- Composite indexes on existing tables for common query patterns
CREATE INDEX IF NOT EXISTS idx_events_project_session ON events(project_id, session_id);
CREATE INDEX IF NOT EXISTS idx_events_session_type ON events(session_id, event_type);
CREATE INDEX IF NOT EXISTS idx_events_session_uuid ON events(session_id, uuid);
CREATE INDEX IF NOT EXISTS idx_source_files_project_session ON source_files(project_id, session_id);

-- Covering index for analytical GROUP BY queries
CREATE INDEX IF NOT EXISTS idx_events_covering ON events(
    timestamp, project_id, session_id, model_id,
    input_tokens, output_tokens,
    cache_read_tokens, cache_creation_tokens, total_cost_usd
);

-- =====================================================================
-- Dimensional aggregation tables (star schema)
-- =====================================================================
-- Pre-aggregated measures at hourly/daily/weekly/monthly granularity.
-- Maintained incrementally via refresh_aggregates_for_range() after each
-- ingest batch. See claude-code-sessions docs/engine-performance-analysis.md
-- for the design rationale.
-- Grain: (time_bucket, project_id, session_id, model_id)
-- session_id / model_id use '' sentinel for NULL (SQLite PK treats NULLs
-- as non-equal which would break uniqueness).
-- =====================================================================

CREATE TABLE IF NOT EXISTS agg (
    granularity TEXT NOT NULL,  -- 'hourly', 'daily', 'weekly', 'monthly'
    time_bucket TEXT NOT NULL,
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    event_count INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost_usd REAL NOT NULL DEFAULT 0.0,
    billable_tokens REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (granularity, time_bucket, project_id, session_id, model_id)
);
CREATE INDEX IF NOT EXISTS idx_agg_granularity_time
    ON agg(granularity, time_bucket);
CREATE INDEX IF NOT EXISTS idx_agg_granularity_project_time
    ON agg(granularity, project_id, time_bucket);

-- =====================================================================
-- event_message_chunks — paragraph-sized splits of event content for
-- vector embedding. Populated by the dashboard backend's wave pipeline
-- (src/claude_code_sessions/database/sqlite/embeddings.py). The
-- companion HNSW virtual table ``chunks_vec`` is created at backend
-- runtime via the sqlite-muninn extension. This script only declares
-- the schema so SELECTs work; it does not write to these tables.
-- FK CASCADE on event_id → events.id wipes stale chunks when an event
-- is re-ingested.
-- =====================================================================

CREATE TABLE IF NOT EXISTS event_message_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    chunk_offset INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_chunks_event_id
    ON event_message_chunks(event_id);

CREATE VIRTUAL TABLE IF NOT EXISTS event_message_chunks_fts
    USING fts5(text, content=event_message_chunks, content_rowid=chunk_id);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON event_message_chunks BEGIN
    INSERT INTO event_message_chunks_fts(rowid, text)
        VALUES (new.chunk_id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON event_message_chunks BEGIN
    INSERT INTO event_message_chunks_fts(event_message_chunks_fts, rowid, text)
        VALUES('delete', old.chunk_id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON event_message_chunks BEGIN
    INSERT INTO event_message_chunks_fts(event_message_chunks_fts, rowid, text)
        VALUES('delete', old.chunk_id, old.text);
    INSERT INTO event_message_chunks_fts(rowid, text)
        VALUES (new.chunk_id, new.text);
END;

-- =====================================================================
-- Knowledge-graph layer (schema v13)
-- =====================================================================
-- Mirrors src/claude_code_sessions/database/sqlite/schema.py — keep in sync.
-- The HNSW virtual table ``entities_vec`` is created at runtime by the
-- entity-embeddings phase (requires the sqlite-muninn extension to be
-- loaded first).
-- =====================================================================

CREATE TABLE IF NOT EXISTS entities (
    entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entity_type TEXT,
    source TEXT NOT NULL,
    chunk_id INTEGER REFERENCES event_message_chunks(chunk_id) ON DELETE CASCADE,
    confidence REAL DEFAULT 1.0
);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_chunk ON entities(chunk_id);

CREATE TABLE IF NOT EXISTS ner_chunks_log (
    chunk_id INTEGER PRIMARY KEY,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relations (
    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    rel_type TEXT,
    weight REAL DEFAULT 1.0,
    chunk_id INTEGER,
    source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_relations_src ON relations(src);
CREATE INDEX IF NOT EXISTS idx_relations_dst ON relations(dst);

CREATE TABLE IF NOT EXISTS re_chunks_log (
    chunk_id INTEGER PRIMARY KEY,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_vec_map (
    rowid INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS entity_clusters (
    name TEXT PRIMARY KEY,
    canonical TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    entity_type TEXT,
    mention_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS edges (
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    rel_type TEXT,
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (src, dst, rel_type)
);

CREATE TABLE IF NOT EXISTS leiden_communities (
    node TEXT NOT NULL,
    resolution REAL NOT NULL,
    community_id INTEGER NOT NULL,
    modularity REAL,
    PRIMARY KEY (node, resolution)
);
CREATE INDEX IF NOT EXISTS idx_leiden_communities_resolution
    ON leiden_communities(resolution, community_id);

CREATE TABLE IF NOT EXISTS entity_cluster_labels (
    canonical TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    member_count INTEGER NOT NULL,
    model TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_labels (
    resolution REAL NOT NULL,
    community_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    member_count INTEGER NOT NULL,
    model TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (resolution, community_id)
);

-- Summariser layer (schema v18) — mirrored from the backend schema so both
-- ingesters coexist on one cache file. One row per (session, model).
CREATE TABLE IF NOT EXISTS session_summaries (
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    model TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    task_summary TEXT NOT NULL,
    patterns TEXT NOT NULL,
    decisions_values TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    human_event_count INTEGER NOT NULL,
    PRIMARY KEY (project_id, session_id, model)
);
CREATE INDEX IF NOT EXISTS idx_session_summaries_model
    ON session_summaries(model);

-- Roll-up layer (schema v19) — mirrored from the backend schema. One row per
-- merged scope×grain×bucket per (strategy, model).
CREATE TABLE IF NOT EXISTS rollup_summaries (
    strategy TEXT NOT NULL,
    model TEXT NOT NULL,
    scope_path TEXT NOT NULL,
    scope_depth INTEGER NOT NULL,
    time_granularity TEXT NOT NULL,
    time_bucket TEXT NOT NULL,
    task_summary TEXT NOT NULL,
    patterns TEXT NOT NULL,
    decisions_values TEXT NOT NULL,
    child_count INTEGER NOT NULL,
    source_hash TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (strategy, model, scope_path, time_granularity, time_bucket)
);
CREATE INDEX IF NOT EXISTS idx_rollup_summaries_scope
    ON rollup_summaries(strategy, model, scope_path);
"""


# ============================================================================
# Embedding pipeline (byte-equivalent copy of
# src/claude_code_sessions/database/sqlite/embeddings.py — keep in lockstep)
# ============================================================================
# ---------------------------------------------------------------------------
# Constants — sized for NomicEmbed v1.5 Q8_0 quantised GGUF
# ---------------------------------------------------------------------------

# Registration name used inside ``temp.muninn_models`` — arbitrary but
# must match between ``setup_embedding_runtime()`` and ``sync_embeddings()``.
GGUF_MODEL_NAME = "NomicEmbed"

# HuggingFace-hosted GGUF file. Downloading via plain urllib keeps us off
# the huggingface_hub dependency chain.
GGUF_MODEL_FILENAME = "nomic-embed-text-v1.5.Q8_0.gguf"
GGUF_MODEL_URL = (
    "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/" + GGUF_MODEL_FILENAME
)

# Output vector dimensionality for NomicEmbed v1.5 — matches the HNSW
# ``dimensions=`` virtual-table parameter. Changing this requires a
# different model and a cache rebuild.
GGUF_EMBEDDING_DIM = 768

# Local cache of downloaded models. Shared across all tools that use the
# same SQLite cache (the main app + the introspect skill script).
MODELS_DIR = CLAUDE_HOME / "cache" / "models"

# Chunk sizing — empirical from the sessions_demo reference. Code-heavy
# content averages ~3.1 chars/token, so 1200 chars ≈ 400 tokens per
# chunk, safely under the 2048-token model context. Chunks below
# CHUNK_MIN_CHARS are absorbed into an adjacent chunk rather than emitted
# as noise.
CHUNK_MAX_CHARS = 1200
CHUNK_MIN_CHARS = 100

# Hard ceiling on text passed to ``muninn_embed()`` — guards against
# oversized chunks (shouldn't happen given CHUNK_MAX_CHARS, but the
# stored chunk text is unconstrained). Truncation is at the front; we
# keep the beginning as the highest-signal content for embeddings.
EMBED_MAX_CHARS = 1500

# Only user-typed prompts are embedded for now. Keeps the index small
# and the semantic search focused on "what the user asked about" rather
# than assistant output or tool results.
EMBEDDED_MSG_KINDS: tuple[str, ...] = ("human",)


# ---------------------------------------------------------------------------
# Schema fragment — tables created at schema init time. The HNSW virtual
# table is NOT here because it requires sqlite_muninn.load() first; it's
# created lazily at runtime.
# ---------------------------------------------------------------------------

CHUNKS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS event_message_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    chunk_offset INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_chunks_event_id
    ON event_message_chunks(event_id);

CREATE VIRTUAL TABLE IF NOT EXISTS event_message_chunks_fts
    USING fts5(text, content=event_message_chunks, content_rowid=chunk_id);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON event_message_chunks BEGIN
    INSERT INTO event_message_chunks_fts(rowid, text)
        VALUES (new.chunk_id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON event_message_chunks BEGIN
    INSERT INTO event_message_chunks_fts(event_message_chunks_fts, rowid, text)
        VALUES('delete', old.chunk_id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON event_message_chunks BEGIN
    INSERT INTO event_message_chunks_fts(event_message_chunks_fts, rowid, text)
        VALUES('delete', old.chunk_id, old.text);
    INSERT INTO event_message_chunks_fts(rowid, text)
        VALUES (new.chunk_id, new.text);
END;
"""


# ---------------------------------------------------------------------------
# Model download
# ---------------------------------------------------------------------------


def ensure_model_downloaded(*, force: bool = False) -> Path:
    """Return the local path to the GGUF model, downloading on first use.

    The model is ~150 MB (Q8_0 quant); download runs once per machine.
    Subsequent calls are a file-existence check. ``force=True`` re-downloads.

    Raises ``URLError`` / ``HTTPError`` on network failure — fail loud,
    since without the model the embedding phase cannot run.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    target = MODELS_DIR / GGUF_MODEL_FILENAME
    if target.exists() and not force:
        log.info(
            "  GGUF model already present: %s (%.1f MiB)",
            target,
            target.stat().st_size / (1024 * 1024),
        )
        return target

    log.info("  downloading GGUF model %s → %s", GGUF_MODEL_URL, target)
    # User-Agent required: HuggingFace rejects Python's default "Python-urllib/X".
    req = urllib.request.Request(
        GGUF_MODEL_URL,
        headers={"User-Agent": "claude-code-sessions/1.0"},
    )
    t0 = time.monotonic()
    # Write to a .partial file then rename — an interrupted download
    # leaves a stub that won't be mistaken for a completed model.
    partial = target.with_suffix(target.suffix + ".partial")
    with urllib.request.urlopen(req) as resp, partial.open("wb") as out:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        last_log = t0
        chunk_bytes = 1024 * 1024  # 1 MiB read unit
        while True:
            chunk = resp.read(chunk_bytes)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            now = time.monotonic()
            if now - last_log >= 5.0:
                pct = f"{100 * downloaded / total:.1f}%" if total else "?%"
                rate_mb_s = (downloaded / (now - t0)) / (1024 * 1024) if now > t0 else 0
                log.info(
                    "  downloaded %.1f MiB / %.1f MiB (%s, %.1f MiB/s)",
                    downloaded / (1024 * 1024),
                    total / (1024 * 1024) if total else 0,
                    pct,
                    rate_mb_s,
                )
                last_log = now
    partial.rename(target)
    log.info(
        "Downloaded GGUF model (%.1f MiB in %.1f s)",
        target.stat().st_size / (1024 * 1024),
        time.monotonic() - t0,
    )
    return target


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------


def chunk_text(text: str) -> list[tuple[str, int]]:
    """Split ``text`` into paragraph-based chunks of (chunk_text, char_offset).

    Algorithm (mirrors sessions_demo.phases.chunks._split_into_chunks):
      1. Split on double-newline paragraphs.
      2. Greedy-pack paragraphs into a running chunk until adding the next
         one would exceed ``CHUNK_MAX_CHARS`` — emit then, start fresh.
      3. Chunks below ``CHUNK_MIN_CHARS`` are absorbed into the preceding
         chunk rather than emitted standalone.
      4. Very short texts (below ``CHUNK_MIN_CHARS`` total) become a single
         chunk rather than being dropped.

    ``char_offset`` is the start position of the chunk in the original
    text — useful if we later want to highlight the exact matched region.
    """
    if not text:
        return []
    if len(text) < CHUNK_MIN_CHARS:
        return [(text, 0)]

    chunks: list[tuple[str, int]] = []
    paragraphs = text.split("\n\n")

    offset = 0
    current_chunk = ""
    current_offset = 0

    for i, raw_para in enumerate(paragraphs):
        para = raw_para.strip()
        if not para:
            # Preserve the \n\n separator in the running offset so later
            # chunks' char_offset still maps into the original string.
            offset += 2
            continue

        if not current_chunk:
            current_chunk = para
            current_offset = offset
        elif len(current_chunk) + len(para) + 2 <= CHUNK_MAX_CHARS:
            current_chunk += "\n\n" + para
        else:
            if len(current_chunk) >= CHUNK_MIN_CHARS:
                chunks.append((current_chunk, current_offset))
            current_chunk = para
            current_offset = offset

        offset += len(para) + (2 if i < len(paragraphs) - 1 else 0)

    if current_chunk:
        if len(current_chunk) >= CHUNK_MIN_CHARS or not chunks:
            chunks.append((current_chunk, current_offset))
        else:
            # Tail chunk is too short — merge into the previous one.
            prev_text, prev_offset = chunks[-1]
            chunks[-1] = (prev_text + "\n\n" + current_chunk, prev_offset)

    return chunks


# ---------------------------------------------------------------------------
# Sync — runs at the tail of CacheManager.update()
# ---------------------------------------------------------------------------


def sync_chunks(conn: sqlite3.Connection) -> int:
    """Chunk any human-message events that don't yet have chunks.

    Returns the number of chunks inserted this run. Safe to call
    repeatedly — it only processes events that aren't already covered.

    We scope to ``msg_kind = 'human'`` for now (see ``EMBEDDED_MSG_KINDS``):
    that's the most useful signal for semantic search and keeps the
    index size modest.
    """
    kinds_placeholders = ",".join("?" * len(EMBEDDED_MSG_KINDS))
    # Count first so we can log an estimate. This is the same query as
    # the fetch below, just with COUNT(*). Cheap — it's an indexed scan.
    total = conn.execute(
        f"""
        SELECT COUNT(*) FROM events e
        WHERE e.message_content IS NOT NULL
          AND e.message_content != ''
          AND e.msg_kind IN ({kinds_placeholders})
          AND e.id NOT IN (SELECT DISTINCT event_id FROM event_message_chunks)
        """,
        EMBEDDED_MSG_KINDS,
    ).fetchone()[0]
    if total == 0:
        return 0

    log.info("  chunking %d events (kinds=%s)", total, ",".join(EMBEDDED_MSG_KINDS))
    t0 = time.monotonic()

    cursor = conn.execute(
        f"""
        SELECT e.id, e.message_content
        FROM events e
        WHERE e.message_content IS NOT NULL
          AND e.message_content != ''
          AND e.msg_kind IN ({kinds_placeholders})
          AND e.id NOT IN (SELECT DISTINCT event_id FROM event_message_chunks)
        """,
        EMBEDDED_MSG_KINDS,
    )

    total_chunks = 0
    events_processed = 0
    for row in cursor:
        event_id = row[0]
        text = row[1]
        for chunk, chunk_offset in chunk_text(text):
            conn.execute(
                "INSERT INTO event_message_chunks (event_id, text, chunk_offset) VALUES (?, ?, ?)",
                (event_id, chunk, chunk_offset),
            )
            total_chunks += 1
        events_processed += 1
        if events_processed % 500 == 0:
            log.info(
                "    chunked %d/%d events (%d chunks so far)",
                events_processed,
                total,
                total_chunks,
            )

    conn.commit()
    log.info(
        "  created %d chunks from %d events (%.1f s)",
        total_chunks,
        events_processed,
        time.monotonic() - t0,
    )
    return total_chunks


def setup_embedding_runtime(conn: sqlite3.Connection, model_path: Path) -> None:
    """Load muninn, register the GGUF model, and ensure the HNSW VT exists.

    Idempotent: safe to call on every connection open. The expensive
    part (creating the HNSW VT) is a no-op after the first call.
    """
    conn.enable_load_extension(True)
    sqlite_muninn.load(conn)
    conn.enable_load_extension(False)

    # ``temp.muninn_models`` is a per-connection registry. An
    # ``INSERT OR IGNORE`` doesn't work here because the value comes
    # from ``muninn_embed_model()``; we instead check existence first.
    row = conn.execute(
        "SELECT name FROM temp.muninn_models WHERE name = ?",
        (GGUF_MODEL_NAME,),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO temp.muninn_models(name, model) SELECT ?, muninn_embed_model(?)",
            (GGUF_MODEL_NAME, str(model_path)),
        )
        log.debug("Registered GGUF model %s → %s", GGUF_MODEL_NAME, model_path)

    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec "
        f"USING hnsw_index(dimensions={GGUF_EMBEDDING_DIM}, metric='cosine')"
    )
    conn.commit()


def sync_embeddings(conn: sqlite3.Connection) -> int:
    """Embed any chunks that don't yet have a vector in ``chunks_vec``.

    Uses ``chunks_vec_nodes`` (the shadow table — a regular SQLite table)
    to detect "not yet embedded" rows. A direct scan of ``chunks_vec``
    (the HNSW virtual table) returns no rows in muninn's implementation,
    so staleness checks MUST go through the shadow table.

    Prerequisite: ``setup_embedding_runtime(conn, model_path)`` must
    have been called on this connection already.

    Returns the number of vectors inserted.
    """
    total = conn.execute(
        """
        SELECT COUNT(*) FROM event_message_chunks c
        WHERE c.chunk_id NOT IN (SELECT id FROM chunks_vec_nodes)
        """,
    ).fetchone()[0]
    if total == 0:
        return 0

    log.info("  embedding %d chunks (dim=%d, model=%s)", total, GGUF_EMBEDDING_DIM, GGUF_MODEL_NAME)
    t0 = time.monotonic()

    cursor = conn.execute(
        """
        SELECT c.chunk_id, c.text
        FROM event_message_chunks c
        WHERE c.chunk_id NOT IN (SELECT id FROM chunks_vec_nodes)
        """,
    )

    total_embedded = 0
    failed = 0
    last_log = t0
    for row in cursor:
        chunk_id, text = row[0], row[1]
        try:
            embed_text = text[:EMBED_MAX_CHARS]
            result = conn.execute(
                "SELECT muninn_embed(?, ?)",
                (GGUF_MODEL_NAME, embed_text),
            ).fetchone()
            if result and result[0]:
                conn.execute(
                    "INSERT INTO chunks_vec(rowid, vector) VALUES (?, ?)",
                    (chunk_id, result[0]),
                )
                total_embedded += 1
        except sqlite3.OperationalError as e:
            # One bad chunk shouldn't abort the whole pass. Log and
            # continue — the next run picks up any rows we skipped.
            log.warning("Failed to embed chunk %d: %s", chunk_id, e)
            failed += 1

        now = time.monotonic()
        if now - last_log >= 30.0:
            elapsed = now - t0
            rate = total_embedded / elapsed if elapsed > 0 else 0
            remaining = total - total_embedded
            eta_s = remaining / rate if rate > 0 else 0
            log.info(
                "    embedded %d/%d chunks (%.1f chunks/s, elapsed %.0f s, eta %.0f s)",
                total_embedded,
                total,
                rate,
                elapsed,
                eta_s,
            )
            last_log = now

    conn.commit()
    log.info(
        "  embedded %d/%d chunks (%d failed, %.1f s)",
        total_embedded,
        total,
        failed,
        time.monotonic() - t0,
    )
    return total_embedded


# ============================================================================
# Knowledge-graph pipeline (byte-equivalent inline copy of
# src/claude_code_sessions/database/sqlite/kg/*.py — keep in lockstep)
# ============================================================================

# --- KG imports (union of all kg/* module imports, project-internal stripped)
from collections import defaultdict
from datetime import UTC, datetime
from gliner2 import GLiNER2
from huggingface_hub import snapshot_download
from pathlib import Path
from typing import Any
from typing import TypedDict
import json
import logging
import os
import sqlite3
import time
import urllib.request


# ---------------------------------------------------------------------------
# kg/runtime.py
# ---------------------------------------------------------------------------
"""Runtime configuration for the KG pipeline — chat model + label registry.

The KG pipeline drives the published ``sqlite-muninn`` extension via SQL
primitives. Two model artifacts are needed:

* The **chat model** (a llama.cpp-compatible GGUF) that backs
  ``muninn_extract_ner_re()`` and ``muninn_label_groups``. Default is a
  4B-parameter Qwen3.5 Instruct quant (~2.6 GiB on disk).
* The **embedding model** — already managed by
  ``claude_code_sessions.database.sqlite.embeddings`` for chunk vectors. We
  re-use the same ``GGUF_MODEL_NAME`` registration there for entity
  embeddings.

Per ``/escalators-not-stairs``: missing chat model → fail loud with the
search paths printed and a remediation hint, never a silent skip.

## Chat-model resolution order

1. ``CLAUDE_SESSIONS_KG_CHAT_MODEL_PATH`` env var (absolute path; if set
   but missing, raises immediately — does not fall back).
2. Cached default at ``~/.claude/cache/models/Qwen3.5-4B-Q4_K_M.gguf``.
3. The sqlite-muninn benchmark models directory at
   ``~/play/sqlite-vector-graph/models/Qwen3.5-4B-Q4_K_M.gguf`` — picked
   up automatically when the developer already maintains a copy there
   (avoids re-downloading 2.6 GiB).
4. None of the above → download from ``CHAT_MODEL_URL_DEFAULT`` into the
   cache directory in (2).
"""

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chat model — drives muninn_extract_ner_re() and muninn_label_groups
# ---------------------------------------------------------------------------

CHAT_MODEL_NAME = "kg_chat"
# gemma-4-E2B-it is a 2-billion-parameter instruction-tuned model that
# produces direct short labels in ~3-4 seconds per call on CPU. Larger
# alternatives like Qwen3.5-4B can take 60×+ longer because they emit
# extended `<think>` reasoning traces before answering — disastrous for
# a phase that needs hundreds of inferences per build.
CHAT_MODEL_FILENAME_DEFAULT = "gemma-4-E2B-it-Q4_K_M.gguf"
CHAT_MODEL_URL_DEFAULT = (
    "https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf"
)

MODELS_DIR = Path.home() / ".claude" / "cache" / "models"

# Other locations searched before downloading. The first existing match
# wins. These are *opportunistic*: they let a developer who already has
# the GGUF on disk skip the download without having to symlink or set
# env vars.
_FALLBACK_SEARCH_PATHS: tuple[Path, ...] = (
    Path.home() / "play" / "sqlite-vector-graph" / "models" / CHAT_MODEL_FILENAME_DEFAULT,
)


def _env_override_path() -> Path | None:
    raw = os.environ.get("CLAUDE_SESSIONS_KG_CHAT_MODEL_PATH", "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(
            f"CLAUDE_SESSIONS_KG_CHAT_MODEL_PATH={p} does not exist. "
            f"Either point it at an existing GGUF chat model or unset it "
            f"so the pipeline falls back to the cached default."
        )
    return p


def _existing_chat_model() -> Path | None:
    """Return the first chat-model path that exists, in priority order."""
    cache_target = MODELS_DIR / CHAT_MODEL_FILENAME_DEFAULT
    if cache_target.exists():
        return cache_target
    for candidate in _FALLBACK_SEARCH_PATHS:
        if candidate.exists():
            return candidate
    return None


def ensure_chat_model_downloaded(*, force: bool = False) -> Path:
    """Return the local path to the KG chat GGUF, downloading on first use.

    Resolution order: env override → cache → fallback search paths →
    download. ``force=True`` skips every existing-file check and re-downloads
    into the cache directory.

    Raises ``URLError``/``HTTPError`` on network failure — fail loud, since
    without the chat model the NER+RE and community-naming phases cannot run.
    """
    override = _env_override_path()
    if override is not None:
        log.info("  KG chat model: %s (env override)", override)
        return override

    if not force:
        existing = _existing_chat_model()
        if existing is not None:
            log.info(
                "  KG chat model already present: %s (%.1f GiB)",
                existing,
                existing.stat().st_size / (1024**3),
            )
            return existing

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    target = MODELS_DIR / CHAT_MODEL_FILENAME_DEFAULT

    log.info("  downloading KG chat model %s → %s", CHAT_MODEL_URL_DEFAULT, target)
    req = urllib.request.Request(
        CHAT_MODEL_URL_DEFAULT,
        headers={"User-Agent": "claude-code-sessions/1.0"},
    )
    t0 = time.monotonic()
    partial = target.with_suffix(target.suffix + ".partial")
    with urllib.request.urlopen(req) as resp, partial.open("wb") as out:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        last_log = t0
        chunk_bytes = 1024 * 1024
        while True:
            chunk = resp.read(chunk_bytes)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            now = time.monotonic()
            if now - last_log >= 5.0:
                pct = f"{100 * downloaded / total:.1f}%" if total else "?%"
                rate = (downloaded / (now - t0)) / (1024 * 1024) if now > t0 else 0
                log.info(
                    "  downloaded %.1f MiB / %.1f MiB (%s, %.1f MiB/s)",
                    downloaded / (1024 * 1024),
                    total / (1024 * 1024) if total else 0,
                    pct,
                    rate,
                )
                last_log = now
    partial.rename(target)
    log.info(
        "  KG chat model downloaded (%.1f GiB in %.1f s)",
        target.stat().st_size / (1024**3),
        time.monotonic() - t0,
    )
    return target


def register_chat_model(conn: sqlite3.Connection, model_path: Path) -> None:
    """Register the GGUF chat model in ``temp.muninn_chat_models``.

    The registration is idempotent: re-registering with the same name is a
    no-op (sqlite-muninn raises an OperationalError saying "already loaded"
    that we treat as success).
    """
    try:
        conn.execute(
            "INSERT INTO temp.muninn_chat_models(name, model) SELECT ?, muninn_chat_model(?)",
            (CHAT_MODEL_NAME, str(model_path)),
        )
        log.info("  registered KG chat model in temp.muninn_chat_models: %s", CHAT_MODEL_NAME)
    except sqlite3.OperationalError as exc:
        if "already loaded" not in str(exc).lower():
            raise


# ---------------------------------------------------------------------------
# Label vocabularies — domain-tuned for Claude Code session content.
# ---------------------------------------------------------------------------

NER_LABELS: tuple[str, ...] = (
    "tool",
    "file_path",
    "model",
    "concept",
    "error",
    "person",
    "organization",
    "library",
    "command",
)

RE_LABELS: tuple[str, ...] = (
    "uses",
    "calls",
    "imports",
    "depends_on",
    "modifies",
    "reads",
    "writes",
    "instance_of",
    "part_of",
)


# ---------------------------------------------------------------------------
# Leiden resolutions — coarse / medium / fine community structure.
# ---------------------------------------------------------------------------

LEIDEN_RESOLUTIONS: tuple[float, ...] = (0.25, 1.0, 3.0)
DEFAULT_RESOLUTION = 0.25


# ---------------------------------------------------------------------------
# kg/gliner2_loader.py
# ---------------------------------------------------------------------------
"""Shared GLiNER2 model cache — loads once per process.

Both NER and RE use the same model instance via this loader. The cache
ensures the ~205 MB DeBERTa weights are mmaped at most once even when
both phases run sequentially.

Offline loading: ``snapshot_download`` returns the cached local path;
``GLiNER2.from_pretrained(local_dir)`` short-circuits to local file
access via ``os.path.isdir()`` — no ``HF_HUB_OFFLINE`` patching required.
"""

log = logging.getLogger(__name__)

DEFAULT_GLINER2_MODEL = "fastino/gliner2-base-v1"

_cache: dict[str, GLiNER2] = {}


def get_gliner2(model_name: str = DEFAULT_GLINER2_MODEL) -> GLiNER2:
    """Return a cached GLiNER2 instance.

    First call resolves the model in the local HF cache (without a
    network round-trip — ``snapshot_download(local_files_only=True)``).
    The weights live under ``~/.cache/huggingface/hub/...``; if they
    aren't present we re-issue the call WITHOUT ``local_files_only`` so
    the missing files are downloaded once. This keeps warm starts
    instant while still bootstrapping a fresh machine.

    Subsequent calls with the same ``model_name`` return the cached
    instance with no additional memory or disk I/O.
    """
    if model_name not in _cache:
        log.info("  loading GLiNER2 weights: %s", model_name)
        try:
            local_path = snapshot_download(model_name, local_files_only=True)
        except Exception:
            log.info("  GLiNER2 weights not in HF cache — downloading from HF Hub")
            local_path = snapshot_download(model_name)
        _cache[model_name] = GLiNER2.from_pretrained(local_path)
    return _cache[model_name]


# ---------------------------------------------------------------------------
# kg/entity_resolution.py
# ---------------------------------------------------------------------------
"""Entity-resolution phase — collapse synonyms into canonical clusters.

Uses ``muninn_extract_er(vec_table, name_col, k, dist_threshold, jw_weight,
borderline_delta, eb_threshold_or_null, type_filter, type_filter_col)`` —
sqlite-muninn's all-in-one ER pipeline that does HNSW blocking →
Jaro-Winkler + cosine scoring → Leiden clustering → edge-betweenness
cleanup, returning a JSON cluster map.

Outputs:
  - ``entity_clusters(name, canonical)`` — synonym → canonical mapping
  - ``nodes(node_id, name, entity_type, mention_count)`` — canonical entities
  - ``edges(src, dst, rel_type, weight)`` — coalesced canonical relations

This phase is non-incremental: it ALWAYS rebuilds nodes/edges from
scratch when run, because ER is a global optimization. It is only
*invoked* when entity_embeddings has produced new vectors, so the
no-op case is "skip the rebuild altogether."
"""

log = logging.getLogger(__name__)


_DEFAULT_K = 10
_DEFAULT_DIST_THRESHOLD = 0.15
_DEFAULT_JW_WEIGHT = 0.3
_DEFAULT_BORDERLINE_DELTA = 0.0


def _has_new_entities(conn: sqlite3.Connection) -> bool:
    """True if entity_vec_map has rows whose names are missing from entity_clusters."""
    cluster_count = int(conn.execute("SELECT count(*) FROM entity_clusters").fetchone()[0])
    name_count = int(conn.execute("SELECT count(*) FROM entity_vec_map").fetchone()[0])
    return cluster_count < name_count


def sync_entity_clusters(conn: sqlite3.Connection) -> tuple[int, int]:
    """Run muninn_extract_er and rebuild nodes/edges.

    Returns ``(num_nodes, num_edges)``.
    """
    if not _has_new_entities(conn):
        log.info("  entity-resolution: clusters already up to date")
        return (
            int(conn.execute("SELECT count(*) FROM nodes").fetchone()[0]),
            int(conn.execute("SELECT count(*) FROM edges").fetchone()[0]),
        )

    t0 = time.monotonic()

    # Drop the rebuildable tables (entity_clusters / nodes / edges /
    # _match_edges). entity_vec_map and entities_vec are upstream and
    # preserved so re-running the ER doesn't force a full re-embed.
    conn.execute("DROP TABLE IF EXISTS _match_edges")
    conn.execute("DELETE FROM entity_clusters")
    conn.execute("DELETE FROM nodes")
    conn.execute("DELETE FROM edges")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('nodes', 'edge')")

    # Bridge schema: muninn_extract_er expects a ``temp.entities`` view-like
    # table with (entity_id, name, source) columns. Build it from
    # entity_vec_map joined to the dominant entity_type per name.
    conn.execute("DROP TABLE IF EXISTS temp.entities")
    conn.execute("CREATE TEMP TABLE entities(entity_id TEXT, name TEXT, source TEXT)")
    conn.execute(
        """
        INSERT INTO temp.entities(entity_id, name, source)
        SELECT m.name, m.name, COALESCE(t.entity_type, '')
        FROM entity_vec_map m
        LEFT JOIN (
            SELECT name, entity_type
            FROM main.entities
            GROUP BY name
        ) t ON t.name = m.name
        """
    )

    log.info(
        "  entity-resolution: muninn_extract_er(k=%d, dist=%.2f, jw=%.2f)",
        _DEFAULT_K,
        _DEFAULT_DIST_THRESHOLD,
        _DEFAULT_JW_WEIGHT,
    )
    result_row = conn.execute(
        "SELECT muninn_extract_er(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "entities_vec",
            "name",
            _DEFAULT_K,
            _DEFAULT_DIST_THRESHOLD,
            _DEFAULT_JW_WEIGHT,
            _DEFAULT_BORDERLINE_DELTA,
            None,
            None,
            "diff_type",
        ),
    ).fetchone()
    if result_row is None or result_row[0] is None:
        raise RuntimeError("muninn_extract_er returned NULL")

    conn.execute("DROP TABLE IF EXISTS temp.entities")

    parsed = json.loads(result_row[0])
    clusters: dict[str, int] = parsed.get("clusters", {})
    if not clusters:
        log.warning("  entity-resolution: muninn_extract_er produced 0 clusters")

    # Group cluster members and pick the highest-mention name as canonical.
    name_to_count: dict[str, int] = {
        str(r[0]): int(r[1])
        for r in conn.execute("SELECT name, count(*) FROM entities GROUP BY name").fetchall()
    }
    name_to_type: dict[str, str | None] = {
        str(r[0]): (r[1] if r[1] else None)
        for r in conn.execute("SELECT name, entity_type FROM entities GROUP BY name").fetchall()
    }

    members_by_cluster: dict[int, list[str]] = {}
    for name, cluster_id in clusters.items():
        members_by_cluster.setdefault(int(cluster_id), []).append(str(name))

    name_to_canonical: dict[str, str] = {}
    for members in members_by_cluster.values():
        canonical = max(members, key=lambda n: name_to_count.get(n, 0))
        for member in members:
            name_to_canonical[member] = canonical
    # Singletons: any entity name not in the cluster map maps to itself.
    for name in name_to_count:
        name_to_canonical.setdefault(name, name)

    log.info(
        "  entity-resolution: %d entities → %d clusters",
        len(name_to_canonical),
        len(members_by_cluster) or len(name_to_canonical),
    )

    conn.executemany(
        "INSERT INTO entity_clusters (name, canonical) VALUES (?, ?)",
        list(name_to_canonical.items()),
    )

    # Build nodes from canonical roll-up.
    canonical_stats: dict[str, dict[str, str | int | None]] = {}
    for name, count in name_to_count.items():
        canonical = name_to_canonical[name]
        slot_default: dict[str, str | int | None] = {
            "entity_type": name_to_type.get(canonical) or name_to_type.get(name),
            "mention_count": 0,
        }
        slot = canonical_stats.setdefault(canonical, slot_default)
        slot["mention_count"] = int(slot.get("mention_count", 0) or 0) + count

    for canonical in sorted(canonical_stats):
        stats = canonical_stats[canonical]
        conn.execute(
            "INSERT OR IGNORE INTO nodes (name, entity_type, mention_count) VALUES (?, ?, ?)",
            (canonical, stats.get("entity_type"), stats.get("mention_count", 0)),
        )
    num_nodes = int(conn.execute("SELECT count(*) FROM nodes").fetchone()[0])
    log.info("  entity-resolution: %d canonical nodes", num_nodes)

    # Coalesce relations into edges keyed on canonical names.
    edge_agg: dict[tuple[str, str, str], float] = {}
    for src, dst, rel_type, weight in conn.execute(
        "SELECT src, dst, rel_type, weight FROM relations"
    ).fetchall():
        c_src = name_to_canonical.get(str(src), str(src))
        c_dst = name_to_canonical.get(str(dst), str(dst))
        if c_src == c_dst:
            continue
        key = (c_src, c_dst, str(rel_type or ""))
        edge_agg[key] = edge_agg.get(key, 0.0) + float(weight or 0.0)

    if edge_agg:
        conn.executemany(
            "INSERT OR IGNORE INTO edges (src, dst, rel_type, weight) VALUES (?, ?, ?, ?)",
            [(s, d, rt, w) for (s, d, rt), w in edge_agg.items()],
        )
    num_edges = int(conn.execute("SELECT count(*) FROM edges").fetchone()[0])
    log.info("  entity-resolution: %d coalesced edges", num_edges)

    conn.commit()
    log.info(
        "  entity-resolution: complete in %.1f s",
        time.monotonic() - t0,
    )
    return num_nodes, num_edges


# ---------------------------------------------------------------------------
# kg/ner_re.py
# ---------------------------------------------------------------------------
"""NER + RE phase — GLiNER2 (fastino/gliner2-base-v1).

The 205 MB DeBERTa-v3-base GLiNER2 model handles both named-entity
recognition and zero-shot relation extraction. It is roughly 20× faster
than running NER+RE through a 4 B chat model (e.g. Qwen3.5-4B) on CPU
and yields more consistent label boundaries because the network was
trained on token-aligned NER targets rather than free-form generation.

Incremental: tracks completed chunks in ``ner_chunks_log`` and
``re_chunks_log``. Re-runs only process new chunks.

Per ``/escalators-not-stairs``: a chunk that produces zero entities is
still logged as processed — that is success, not failure. A chunk that
errors out propagates the exception; we never silently skip.
"""

log = logging.getLogger(__name__)

# Outer loop: chunks committed to SQLite per batch. Smaller values mean
# more frequent visibility for the web app at the cost of slightly more
# commit overhead.
_OUTER_BATCH = 8
# Inner GLiNER2 batch size — fits comfortably in CPU memory.
_GLINER2_BATCH = 8

# GLiNER2's DeBERTa-v3-base encoder has a 512 token window (~1500 chars
# for code-dense content at ~3 chars/token). Larger inputs either get
# silently truncated internally or send the relation extractor into an
# N² pair-scoring loop that can take *minutes* per chunk. We truncate
# defensively at the boundary so the chunker's edge cases (rare
# multi-thousand-char single-paragraph prompts) can't stall the
# pipeline. Truncation is at the END — entities near the start of long
# prompts are usually the most informative anyway.
_MAX_TEXT_CHARS = 1500


def _safe_text(text: str) -> str:
    if len(text) <= _MAX_TEXT_CHARS:
        return text
    return text[:_MAX_TEXT_CHARS]


def _per_run_limit() -> int:
    """Optional per-run chunk cap.

    ``CLAUDE_SESSIONS_KG_NER_RE_BATCH=N`` processes at most N chunks per
    server start, then the next start picks up from the next un-logged
    chunk. Default ``0`` means "process every unprocessed chunk in one
    run" — the production behavior the user explicitly requested under
    ``/escalators-not-stairs`` (no skipping the first-time encoding).

    The cap is purely operational pacing for very large corpora; it
    never causes the pipeline to *skip* work, only to spread it across
    multiple runs.
    """
    raw = os.environ.get("CLAUDE_SESSIONS_KG_NER_RE_BATCH", "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


_NER_INSERT_SQL = (
    "INSERT INTO entities (name, entity_type, source, chunk_id, confidence) VALUES (?, ?, ?, ?, ?)"
)
_RE_INSERT_SQL = (
    "INSERT INTO relations (src, dst, rel_type, weight, chunk_id, source) VALUES (?, ?, ?, ?, ?, ?)"
)


def _unprocessed_chunks(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """Return (chunk_id, text) tuples whose chunk_id is missing from ner_chunks_log."""
    rows = conn.execute(
        """
        SELECT chunk_id, text
        FROM event_message_chunks
        WHERE chunk_id NOT IN (SELECT chunk_id FROM ner_chunks_log)
        ORDER BY chunk_id
        """
    ).fetchall()
    return [(int(r[0]), str(r[1])) for r in rows]


def _extract_entities_for_batch(
    model: Any,
    texts: list[str],
    chunk_ids: list[int],
) -> list[tuple[str, str, str, int, float]]:
    """Run GLiNER2 NER over a batch and flatten to insert-tuples.

    Returns ``(name, entity_type, source, chunk_id, confidence)`` rows.
    """
    results = model.batch_extract_entities(
        texts,
        list(NER_LABELS),
        batch_size=_GLINER2_BATCH,
        include_confidence=True,
    )
    rows: list[tuple[str, str, str, int, float]] = []
    for chunk_id, result in zip(chunk_ids, results, strict=True):
        for label, ents in (result or {}).get("entities", {}).items():
            for ent in ents:
                name = (ent.get("text") or "").strip()
                if not name:
                    continue
                rows.append(
                    (
                        name,
                        label,
                        "gliner2",
                        chunk_id,
                        float(ent.get("confidence", 1.0)),
                    )
                )
    return rows


def _extract_relations_for_batch(
    model: Any,
    texts: list[str],
    chunk_ids: list[int],
) -> list[tuple[str, str, str, float, int, str]]:
    """Run GLiNER2 RE over a batch and flatten to insert-tuples.

    Returns ``(src, dst, rel_type, weight, chunk_id, source)`` rows.
    """
    results = model.batch_extract_relations(
        texts,
        list(RE_LABELS),
        batch_size=_GLINER2_BATCH,
        include_confidence=True,
    )
    rows: list[tuple[str, str, str, float, int, str]] = []
    for chunk_id, result in zip(chunk_ids, results, strict=True):
        for rel_type, rels in (result or {}).get("relation_extraction", {}).items():
            for rel in rels:
                head = (rel.get("head", {}).get("text") or "").strip()
                tail = (rel.get("tail", {}).get("text") or "").strip()
                if not head or not tail or head == tail:
                    continue
                head_conf = float(rel.get("head", {}).get("confidence", 1.0))
                tail_conf = float(rel.get("tail", {}).get("confidence", 1.0))
                weight = (head_conf + tail_conf) / 2.0
                rows.append((head, tail, rel_type, weight, chunk_id, "gliner2"))
    return rows


def sync_ner_re(conn: sqlite3.Connection) -> tuple[int, int]:
    """Extract entities + relations from every unprocessed chunk via GLiNER2.

    Returns ``(entities_added, relations_added)``.
    """
    chunks = _unprocessed_chunks(conn)
    if not chunks:
        log.info("  NER+RE: no new chunks to process")
        return 0, 0

    cap = _per_run_limit()
    if cap and cap < len(chunks):
        log.info(
            "  NER+RE: per-run cap=%d (CLAUDE_SESSIONS_KG_NER_RE_BATCH); "
            "remaining %d chunks will run on subsequent server starts",
            cap,
            len(chunks) - cap,
        )
        chunks = chunks[:cap]

    log.info(
        "  NER+RE processing %d chunks via GLiNER2 (fastino/gliner2-base-v1)",
        len(chunks),
    )
    log.info("    entity labels: %s", list(NER_LABELS))
    log.info("    relation labels: %s", list(RE_LABELS))

    model = get_gliner2()
    ts = datetime.now(UTC).isoformat()
    total_entities = 0
    total_relations = 0
    t0 = time.monotonic()
    last_log = t0

    for batch_start in range(0, len(chunks), _OUTER_BATCH):
        batch = chunks[batch_start : batch_start + _OUTER_BATCH]
        chunk_ids = [cid for cid, _ in batch]
        texts = [_safe_text(text) for _, text in batch]

        ner_rows = _extract_entities_for_batch(model, texts, chunk_ids)
        if ner_rows:
            conn.executemany(_NER_INSERT_SQL, ner_rows)
            total_entities += len(ner_rows)

        re_rows = _extract_relations_for_batch(model, texts, chunk_ids)
        if re_rows:
            conn.executemany(_RE_INSERT_SQL, re_rows)
            total_relations += len(re_rows)

        conn.executemany(
            "INSERT OR IGNORE INTO ner_chunks_log (chunk_id, processed_at) VALUES (?, ?)",
            [(cid, ts) for cid in chunk_ids],
        )
        conn.executemany(
            "INSERT OR IGNORE INTO re_chunks_log (chunk_id, processed_at) VALUES (?, ?)",
            [(cid, ts) for cid in chunk_ids],
        )
        conn.commit()

        processed = min(batch_start + len(batch), len(chunks))
        now = time.monotonic()
        if now - last_log >= 3.0 or processed == len(chunks):
            rate = processed / (now - t0) if now > t0 else 0
            eta = (len(chunks) - processed) / rate if rate > 0 else 0
            log.info(
                "  NER+RE progress: %d/%d (%.1f chunks/s, ETA %.0f s, %d ents, %d rels)",
                processed,
                len(chunks),
                rate,
                eta,
                total_entities,
                total_relations,
            )
            last_log = now

    log.info(
        "  NER+RE complete: %d entities + %d relations from %d chunks in %.1f s",
        total_entities,
        total_relations,
        len(chunks),
        time.monotonic() - t0,
    )
    return total_entities, total_relations


# ---------------------------------------------------------------------------
# kg/entity_embeddings.py
# ---------------------------------------------------------------------------
"""Entity-embeddings phase — embed unique entity names into HNSW.

Uses ``muninn_embed()`` with the same NomicEmbed GGUF that
``embeddings.sync_embeddings()`` uses for chunks. The HNSW virtual table
``entities_vec`` is created here at runtime (it requires the
``sqlite-muninn`` extension to be loaded first, so it can't live in the
static ``SCHEMA_SQL``).

Incremental: only entity names not yet present in ``entity_vec_map`` are
embedded. Re-running with no new entities is a no-op.
"""

log = logging.getLogger(__name__)


def _ensure_entities_vec(conn: sqlite3.Connection) -> None:
    """Create the HNSW virtual table for entity embeddings if missing."""
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS entities_vec USING hnsw_index("
        f"  dimensions={GGUF_EMBEDDING_DIM}, metric='cosine', m=16, ef_construction=200"
        f")"
    )


def sync_entity_embeddings(conn: sqlite3.Connection) -> int:
    """Embed every entity name not already in ``entity_vec_map``.

    Returns the count of newly inserted vectors.
    """
    _ensure_entities_vec(conn)

    new_names = [
        str(r[0])
        for r in conn.execute(
            """
            SELECT DISTINCT name FROM entities
            WHERE name NOT IN (SELECT name FROM entity_vec_map)
            ORDER BY name
            """
        ).fetchall()
    ]
    if not new_names:
        log.info("  entity-embeddings: all %d entity names already embedded", _name_count(conn))
        return 0

    log.info("  entity-embeddings: embedding %d new entity names", len(new_names))
    t0 = time.monotonic()

    max_rowid_row = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM entity_vec_map").fetchone()
    max_rowid = int(max_rowid_row[0]) if max_rowid_row else 0
    inserted = 0

    for offset, name in enumerate(new_names, start=1):
        rowid = max_rowid + offset
        vec_row = conn.execute("SELECT muninn_embed(?, ?)", (GGUF_MODEL_NAME, name)).fetchone()
        if vec_row is None or vec_row[0] is None:
            raise RuntimeError(f"muninn_embed returned NULL for entity name {name!r}")
        conn.execute(
            "INSERT INTO entities_vec (rowid, vector) VALUES (?, ?)",
            (rowid, vec_row[0]),
        )
        conn.execute(
            "INSERT INTO entity_vec_map (rowid, name) VALUES (?, ?)",
            (rowid, name),
        )
        inserted += 1
        if offset % 200 == 0:
            conn.commit()

    conn.commit()
    log.info(
        "  entity-embeddings: inserted %d vectors in %.1f s (total %d)",
        inserted,
        time.monotonic() - t0,
        _name_count(conn),
    )
    return inserted


def _name_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT count(*) FROM entity_vec_map").fetchone()[0])


# ---------------------------------------------------------------------------
# kg/communities.py
# ---------------------------------------------------------------------------
"""Community-detection phase — Leiden communities at multiple resolutions.

Uses sqlite-muninn's ``graph_leiden`` virtual-table module. The community
membership is queried via SELECT against ``graph_leiden`` with the edge
table parameters embedded as WHERE-clause column filters (this is the
sqlite-muninn convention for table-valued functions).

The graph is built off the canonical ``edges`` table. Multi-resolution
output gives the cytoscape page coarse / medium / fine views with one
SQL pass per resolution.
"""

log = logging.getLogger(__name__)


def sync_communities(conn: sqlite3.Connection) -> int:
    """Recompute Leiden communities at every configured resolution.

    Returns total assignment rows written across all resolutions.
    """
    edge_count = int(conn.execute("SELECT count(*) FROM edges").fetchone()[0])
    if edge_count == 0:
        log.info("  communities: edges table empty — nothing to cluster")
        conn.execute("DELETE FROM leiden_communities")
        conn.commit()
        return 0

    have_resolutions = {
        float(r[0])
        for r in conn.execute("SELECT DISTINCT resolution FROM leiden_communities").fetchall()
    }
    expected_resolutions = set(LEIDEN_RESOLUTIONS)
    nodes_now = int(conn.execute("SELECT count(*) FROM nodes").fetchone()[0])

    # If every resolution is already populated AND the graph hasn't changed
    # (membership row count == node count × resolution count), skip.
    if have_resolutions >= expected_resolutions:
        existing_total = int(conn.execute("SELECT count(*) FROM leiden_communities").fetchone()[0])
        if existing_total >= nodes_now * len(LEIDEN_RESOLUTIONS):
            log.info(
                "  communities: %d resolutions already current — skip",
                len(have_resolutions),
            )
            return 0

    conn.execute("DELETE FROM leiden_communities")
    t0 = time.monotonic()
    total = 0
    for resolution in LEIDEN_RESOLUTIONS:
        rows = conn.execute(
            """
            SELECT node, community_id, modularity
            FROM graph_leiden
            WHERE edge_table = 'edges'
              AND src_col = 'src'
              AND dst_col = 'dst'
              AND direction = 'both'
              AND resolution = ?
            """,
            (resolution,),
        ).fetchall()

        if not rows:
            log.warning("  communities: resolution=%.2f produced 0 rows", resolution)
            continue

        n_communities = len({int(r[1]) for r in rows})
        modularity = float(rows[0][2]) if rows[0][2] is not None else 0.0
        conn.executemany(
            "INSERT INTO leiden_communities (node, resolution, community_id, modularity) "
            "VALUES (?, ?, ?, ?)",
            [(str(r[0]), float(resolution), int(r[1]), float(r[2] or 0.0)) for r in rows],
        )
        total += len(rows)
        log.info(
            "  communities: resolution=%.2f — %d nodes → %d communities (Q=%.4f)",
            resolution,
            len(rows),
            n_communities,
            modularity,
        )

    conn.commit()
    log.info(
        "  communities: %d total assignments across %d resolutions in %.1f s",
        total,
        len(LEIDEN_RESOLUTIONS),
        time.monotonic() - t0,
    )
    return total


# ---------------------------------------------------------------------------
# kg/community_naming.py
# ---------------------------------------------------------------------------
"""Community-naming phase — LLM-generated labels for clusters and communities.

Calls ``muninn_chat()`` once per group (entity cluster, then Leiden community
at each resolution), assembling a small prompt with the group's member names
and committing each label as soon as it lands. This keeps memory bounded
and makes the phase resumable: a crash at row N means the next run starts
at row N (already-labelled groups are skipped).

Earlier versions used the bulk ``muninn_label_groups`` TVF which ran the
entire phase as one atomic INSERT … SELECT. That approach OOM-killed the
process on large corpora (~40 k clusters) because the TVF and SQLite both
held intermediate state until the transaction committed. The per-row
approach trades a small amount of throughput for crash-resilience and
visible progress.
"""

log = logging.getLogger(__name__)


_MIN_GROUP_SIZE = 3
_MAX_MEMBERS_IN_PROMPT = 10
_LABEL_PROMPT = "Output ONLY a concise label (3-8 words). No explanation."
_COMMIT_EVERY = 10

# The cytoscape page reads ``community_labels`` filtered by the active
# resolution. We label communities at the default page resolution ONLY,
# because labelling all three resolutions of a 40k-node graph means
# tens of thousands of LLM calls (24+ hours on a 4B GGUF). Other
# resolutions fall back to ``community #N`` placeholders, which the
# frontend already handles. ``DEFAULT_RESOLUTION`` mirrors
# ``payload.py``'s default; keep them in sync.
_LABEL_RESOLUTION = 0.25

# Skip entity_cluster_labels entirely — they are not consumed by the
# current cytoscape page. Re-enabling is a one-line change here if a
# future UI surfaces them.
_LABEL_ENTITY_CLUSTERS = False


def sync_community_labels(conn: sqlite3.Connection) -> tuple[int, int]:
    """Rebuild community_labels (Leiden) — and entity_cluster_labels last.

    Returns ``(entity_cluster_label_count, community_label_count)``.

    Lazily registers the chat-model GGUF on first use. Resumable: if a
    previous run stopped mid-phase, this skips groups that already have
    a label.

    Order matters: the cytoscape page consumes ``community_labels`` for
    its community-parent compound boxes, so we name those FIRST. The
    ``entity_cluster_labels`` table is internal (synonym-group labels)
    and not displayed by the current UI; we still build it but only after
    the user-visible labels are committed.
    """
    if not _has_groups_to_label(conn):
        log.info("  community-naming: nothing to label — skipping chat model load")
        return 0, 0

    chat_path = ensure_chat_model_downloaded()
    register_chat_model(conn, chat_path)

    now = datetime.now(UTC).isoformat()
    t0 = time.monotonic()
    cl_count = _label_leiden_communities(conn, now)
    if _LABEL_ENTITY_CLUSTERS:
        ecl_count = _label_entity_clusters(conn, now)
    else:
        ecl_count = int(conn.execute("SELECT count(*) FROM entity_cluster_labels").fetchone()[0])
        log.info("  community-naming: skipping entity_cluster_labels (UI does not use)")
    log.info(
        "  community-naming: %d community labels + %d cluster labels in %.1f s",
        cl_count,
        ecl_count,
        time.monotonic() - t0,
    )
    return ecl_count, cl_count


def _has_groups_to_label(conn: sqlite3.Connection) -> bool:
    """True if any cluster or Leiden community needs labelling."""
    try:
        cluster_rows = int(conn.execute("SELECT count(*) FROM entity_clusters").fetchone()[0])
        leiden_rows = int(conn.execute("SELECT count(*) FROM leiden_communities").fetchone()[0])
    except sqlite3.OperationalError:
        return False
    return (cluster_rows + leiden_rows) > 0


def _label_one(conn: sqlite3.Connection, members: list[str]) -> str:
    """Run muninn_chat on a member list and return the cleaned label.

    ``muninn_chat`` is a 2-arg SQL function: ``(model_name, prompt)``.
    A third argument is interpreted as a GBNF grammar by llama.cpp,
    so we fold the system instruction into a single prompt string.
    """
    sample = members[:_MAX_MEMBERS_IN_PROMPT]
    member_block = "\n".join(f"- {m}" for m in sample)
    prompt = f"{_LABEL_PROMPT}\n\nGroup members\n{member_block}\n\nLabel:"
    row = conn.execute(
        "SELECT muninn_chat(?, ?)",
        (CHAT_MODEL_NAME, prompt),
    ).fetchone()
    raw = (row[0] if row and row[0] else "").strip()
    # Strip leading bullet/quote chars, take first line.
    first_line = raw.splitlines()[0] if raw else ""
    return first_line.strip(" \"'`*-•") or "(unlabelled)"


def _label_entity_clusters(conn: sqlite3.Connection, now: str) -> int:
    """Label every entity cluster with ≥3 members. Resumable."""
    # Build {canonical: [member_name_with_type, ...]} from entity_clusters.
    # We only consider clusters with ≥3 members to match the legacy TVF
    # behaviour and avoid wasting LLM calls on singletons.
    rows = conn.execute(
        """
        SELECT ec.canonical,
               ec.name || ' (' || COALESCE(n.entity_type, 'unknown') || ')' AS member
        FROM entity_clusters ec
        LEFT JOIN nodes n ON n.name = ec.canonical
        """
    ).fetchall()
    grouped: dict[str, list[str]] = defaultdict(list)
    for canonical, member in rows:
        grouped[str(canonical)].append(str(member))

    eligible = [(c, ms) for c, ms in grouped.items() if len(ms) >= _MIN_GROUP_SIZE]
    if not eligible:
        log.info(
            "  community-naming: no entity clusters with >= %d members",
            _MIN_GROUP_SIZE,
        )
        return int(conn.execute("SELECT count(*) FROM entity_cluster_labels").fetchone()[0])

    # Resume support — skip canonicals we've already labelled.
    already = {
        str(r[0]) for r in conn.execute("SELECT canonical FROM entity_cluster_labels").fetchall()
    }
    todo = [(c, ms) for c, ms in eligible if c not in already]
    log.info(
        "  community-naming: %d entity clusters need labels (%d already done, %d eligible total)",
        len(todo),
        len(already),
        len(eligible),
    )
    if not todo:
        return int(conn.execute("SELECT count(*) FROM entity_cluster_labels").fetchone()[0])

    t0 = time.monotonic()
    last_log = t0
    for i, (canonical, members) in enumerate(todo, start=1):
        label = _label_one(conn, members)
        conn.execute(
            "INSERT OR REPLACE INTO entity_cluster_labels"
            " (canonical, label, member_count, model, generated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (canonical, label, len(members), CHAT_MODEL_NAME, now),
        )
        if i % _COMMIT_EVERY == 0:
            conn.commit()

        now_t = time.monotonic()
        if now_t - last_log >= 10.0 or i == len(todo):
            rate = i / (now_t - t0) if now_t > t0 else 0
            eta = (len(todo) - i) / rate if rate > 0 else 0
            log.info(
                "  community-naming/clusters: %d/%d (%.2f labels/s, ETA %.0f s)",
                i,
                len(todo),
                rate,
                eta,
            )
            last_log = now_t

    conn.commit()
    return int(conn.execute("SELECT count(*) FROM entity_cluster_labels").fetchone()[0])


def _label_leiden_communities(conn: sqlite3.Connection, now: str) -> int:
    """Label every Leiden community with ≥3 members at the page resolution. Resumable.

    Restricts to ``_LABEL_RESOLUTION`` (the cytoscape page's default) so
    the LLM workload is bounded — labelling all three resolutions on a
    40k-node graph would be tens of thousands of inferences.
    """
    rows = conn.execute(
        """
        SELECT lc.resolution,
               lc.community_id,
               lc.node || ' (' || COALESCE(n.entity_type, 'unknown') || ')' AS member
        FROM leiden_communities lc
        LEFT JOIN nodes n ON n.name = lc.node
        WHERE lc.resolution = ?
        """,
        (_LABEL_RESOLUTION,),
    ).fetchall()
    if not rows:
        return 0

    grouped: dict[tuple[float, int], list[str]] = defaultdict(list)
    for resolution, community_id, member in rows:
        grouped[(float(resolution), int(community_id))].append(str(member))

    eligible = [(k, ms) for k, ms in grouped.items() if len(ms) >= _MIN_GROUP_SIZE]
    if not eligible:
        log.info(
            "  community-naming: no Leiden communities with >= %d members",
            _MIN_GROUP_SIZE,
        )
        return int(conn.execute("SELECT count(*) FROM community_labels").fetchone()[0])

    already_rows = conn.execute("SELECT resolution, community_id FROM community_labels").fetchall()
    already = {(float(r[0]), int(r[1])) for r in already_rows}
    todo = [(k, ms) for k, ms in eligible if k not in already]
    log.info(
        "  community-naming: %d Leiden communities to label (%d done, %d eligible)",
        len(todo),
        len(already),
        len(eligible),
    )
    if not todo:
        return int(conn.execute("SELECT count(*) FROM community_labels").fetchone()[0])

    t0 = time.monotonic()
    last_log = t0
    for i, ((resolution, community_id), members) in enumerate(todo, start=1):
        label = _label_one(conn, members)
        conn.execute(
            "INSERT OR REPLACE INTO community_labels"
            " (resolution, community_id, label, member_count, model, generated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (resolution, community_id, label, len(members), CHAT_MODEL_NAME, now),
        )
        if i % _COMMIT_EVERY == 0:
            conn.commit()

        now_t = time.monotonic()
        if now_t - last_log >= 10.0 or i == len(todo):
            rate = i / (now_t - t0) if now_t > t0 else 0
            eta = (len(todo) - i) / rate if rate > 0 else 0
            log.info(
                "  community-naming/leiden: %d/%d (%.2f labels/s, ETA %.0f s)",
                i,
                len(todo),
                rate,
                eta,
            )
            last_log = now_t

    conn.commit()
    return int(conn.execute("SELECT count(*) FROM community_labels").fetchone()[0])


# ---------------------------------------------------------------------------
# kg/pipeline.py
# ---------------------------------------------------------------------------
"""KG pipeline orchestrator — sync_kg().

Called from ``CacheManager.update()`` after ``sync_embeddings()`` on every
server start. Each phase is incremental, so warm starts are O(1).

Phase order:
  1. NER + RE          — extract entities and relations from new chunks
                         using the GLiNER2 zero-shot model (DeBERTa, ~205 MB)
  2. entity_embeddings — embed unique entity names into HNSW (NomicEmbed)
  3. entity_resolution — collapse synonyms via muninn_extract_er
  4. communities       — Leiden community detection at multiple resolutions
  5. community_naming  — LLM-generated labels (the only phase that needs a
                         chat-model GGUF; loaded lazily inside that phase)
"""

log = logging.getLogger(__name__)


class KGSyncResult(TypedDict):
    entities_added: int
    relations_added: int
    entity_embeddings_added: int
    nodes: int
    edges: int
    leiden_assignments: int
    cluster_labels: int
    community_labels: int


def sync_kg(conn: sqlite3.Connection) -> KGSyncResult:
    """Run every KG phase against ``conn``.

    GLiNER2 weights download on first call (~205 MB). The chat-model GGUF
    needed by ``community_naming`` is loaded inside that phase only —
    server starts that have nothing new to label avoid the 2.6 GiB memory
    cost entirely.

    Per ``/escalators-not-stairs``: this function never silently skips a
    phase. If a phase fails, the exception propagates and the cache stays
    in a known-stale state for the next run.
    """
    log.info("──────── kg pipeline ────────")
    t0 = time.monotonic()

    # 1. NER + RE via GLiNER2.
    entities_added, relations_added = sync_ner_re(conn)

    # 2. Entity embeddings (uses the same NomicEmbed GGUF as chunk embeddings).
    entity_embeddings_added = sync_entity_embeddings(conn)

    # 3. Entity resolution (rebuild nodes/edges).
    nodes, edges = sync_entity_clusters(conn)

    # 4. Communities (Leiden, multi-resolution).
    leiden_assignments = sync_communities(conn)

    # 5. Community naming — registers the chat-model GGUF lazily.
    cluster_labels, community_labels = sync_community_labels(conn)

    log.info(
        "──── kg pipeline complete in %.1f s "
        "(ents +%d, rels +%d, ent-vecs +%d, nodes %d, edges %d, "
        "leiden %d, cluster-labels %d, community-labels %d) ────",
        time.monotonic() - t0,
        entities_added,
        relations_added,
        entity_embeddings_added,
        nodes,
        edges,
        leiden_assignments,
        cluster_labels,
        community_labels,
    )
    return KGSyncResult(
        entities_added=entities_added,
        relations_added=relations_added,
        entity_embeddings_added=entity_embeddings_added,
        nodes=nodes,
        edges=edges,
        leiden_assignments=leiden_assignments,
        cluster_labels=cluster_labels,
        community_labels=community_labels,
    )


# ============================================================================
# SQLite Cache Manager
# ============================================================================


class CacheManager:
    """Manages the SQLite cache for session data."""

    def __init__(self, db_path: Path = CACHE_DB_PATH):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def init_schema(self) -> None:
        """Initialize database schema."""
        log.info("Initializing cache schema...")
        self.conn.executescript(SCHEMA_SQL)
        self.conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
            ("created_at", datetime.now(UTC).isoformat()),
        )
        self.conn.commit()
        log.info(f"Cache initialized at {self.db_path}")

    def needs_rebuild(self) -> bool:
        """Check if the schema version requires a rebuild."""
        try:
            row = self.conn.execute(
                "SELECT value FROM cache_metadata WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                return True
            return bool(row[0] != SCHEMA_VERSION)
        except sqlite3.OperationalError:
            # cache_metadata table doesn't exist yet
            return True

    def reset(self) -> None:
        """Wipe the database file entirely and reinitialize the schema.

        Use this for schema migrations. DELETE FROM leaves the table structure
        intact, so CREATE TABLE IF NOT EXISTS becomes a no-op and new columns
        never appear. Deleting the file guarantees a clean slate.
        """
        log.info("Resetting cache database...")
        self.close()
        if self.db_path.exists():
            self.db_path.unlink()
        self.init_schema()

    def clear(self) -> None:
        """Clear all cached data. Safe to call even if tables don't exist."""
        log.info("Clearing cache...")
        # Use DELETE FROM with IF EXISTS check via try/except for each table
        tables_to_clear = [
            "event_edges",  # FK → source_files
            "event_calls",  # FK → events (must precede `events`)
            "events",
            "sessions",
            "projects",
            "source_files",
            "events_fts",
        ]
        for table in tables_to_clear:
            try:
                self.conn.execute(f"DELETE FROM {table}")
            except sqlite3.OperationalError:
                # Table doesn't exist yet, that's fine
                pass
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
                ("last_cleared_at", datetime.now(UTC).isoformat()),
            )
        except sqlite3.OperationalError:
            # cache_metadata table doesn't exist yet
            pass
        self.conn.commit()
        log.info("Cache cleared")

    def get_status(self) -> dict[str, Any]:
        """Get cache status information."""
        cursor = self.conn.cursor()

        # Get counts
        file_count = cursor.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
        project_count = cursor.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        session_count = cursor.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        event_count = cursor.execute("SELECT COUNT(*) FROM events").fetchone()[0]

        # Get counts for new tables (with backward compat)
        edge_count = 0
        try:
            edge_count = cursor.execute("SELECT COUNT(*) FROM event_edges").fetchone()[0]
        except sqlite3.OperationalError:
            pass  # Tables may not exist in older schema

        # Get metadata
        created_at = cursor.execute(
            "SELECT value FROM cache_metadata WHERE key = 'created_at'"
        ).fetchone()
        last_update = cursor.execute(
            "SELECT value FROM cache_metadata WHERE key = 'last_update_at'"
        ).fetchone()

        # Get database file size
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "db_path": str(self.db_path),
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / (1024 * 1024), 2),
            "source_files": file_count,
            "projects": project_count,
            "sessions": session_count,
            "events": event_count,
            "event_edges": edge_count,
            "created_at": created_at[0] if created_at else None,
            "last_update_at": last_update[0] if last_update else None,
        }

    def discover_files(self, projects_path: Path) -> list[dict[str, Any]]:
        """Discover all JSONL files and classify them."""
        files: list[dict[str, Any]] = []

        if not projects_path.exists():
            return files

        for project_dir in projects_path.iterdir():
            if not project_dir.is_dir():
                continue

            project_id = project_dir.name

            for jsonl_file in project_dir.rglob("*.jsonl"):
                rel_path = jsonl_file.relative_to(project_dir)
                parts = rel_path.parts

                file_info = {
                    "filepath": str(jsonl_file),
                    "project_id": project_id,
                    "session_id": None,
                    "file_type": "unknown",
                }

                if len(parts) == 1:
                    # File at project root
                    filename = parts[0]
                    if filename.startswith("agent-"):
                        # Agent file at project root - needs sessionId from content
                        file_info["file_type"] = "agent_root"
                    else:
                        # Main session file
                        session_id = filename.replace(".jsonl", "")
                        file_info["session_id"] = session_id
                        file_info["file_type"] = "main_session"

                elif len(parts) >= 2 and "subagents" in parts:
                    # Subagent file in session subdirectory
                    # Path: {session_id}/subagents/agent-*.jsonl
                    session_id = parts[0]
                    file_info["session_id"] = session_id
                    file_info["file_type"] = "subagent"

                elif len(parts) == 2:
                    # Legacy: {session_id}/*.jsonl (old format)
                    session_id = parts[0]
                    file_info["session_id"] = session_id
                    file_info["file_type"] = "subagent"

                files.append(file_info)

        return files

    def get_files_needing_update(self, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter files to only those that need updating."""
        cursor = self.conn.cursor()
        needs_update: list[dict[str, Any]] = []

        for file_info in files:
            filepath = file_info["filepath"]

            try:
                stat = os.stat(filepath)
                current_mtime = stat.st_mtime
                current_size = stat.st_size
            except OSError:
                continue

            # Check if file is in cache with same mtime
            cached = cursor.execute(
                "SELECT mtime, size_bytes FROM source_files WHERE filepath = ?",
                (filepath,),
            ).fetchone()

            if cached is None:
                # New file
                file_info["mtime"] = current_mtime
                file_info["size_bytes"] = current_size
                file_info["reason"] = "new"
                needs_update.append(file_info)
            elif cached["mtime"] != current_mtime or cached["size_bytes"] != current_size:
                # Modified file
                file_info["mtime"] = current_mtime
                file_info["size_bytes"] = current_size
                file_info["reason"] = "modified"
                needs_update.append(file_info)

        return needs_update

    def ingest_file(self, file_info: dict[str, Any]) -> int:
        """Ingest a single JSONL file into the cache. Returns event count."""
        filepath = file_info["filepath"]
        project_id = file_info["project_id"]
        session_id = file_info.get("session_id")
        file_type = file_info["file_type"]
        mtime = file_info["mtime"]
        size_bytes = file_info["size_bytes"]

        log.debug(f"Ingesting {filepath}")

        cursor = self.conn.cursor()

        # Delete existing data for this file (if re-ingesting)
        existing = cursor.execute(
            "SELECT id FROM source_files WHERE filepath = ?", (filepath,)
        ).fetchone()
        if existing:
            cursor.execute("DELETE FROM event_edges WHERE source_file_id = ?", (existing[0],))
            # event_calls rows are removed via ON DELETE CASCADE when the
            # parent event row is deleted, so no explicit sweep is needed.
            cursor.execute("DELETE FROM events WHERE source_file_id = ?", (existing[0],))
            cursor.execute("DELETE FROM source_files WHERE id = ?", (existing[0],))

        # Parse file and count lines
        events_data: list[dict[str, Any]] = []
        line_count = 0
        detected_session_id = session_id  # May be updated from file content

        try:
            with open(filepath, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line_count = line_num
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # For agent_root files, extract sessionId from content
                    if file_type == "agent_root" and detected_session_id is None:
                        detected_session_id = raw.get("sessionId")

                    event = self._parse_event_for_cache(
                        raw, project_id, detected_session_id, filepath, line_num, file_type
                    )
                    if event:
                        events_data.append(event)

        except (FileNotFoundError, PermissionError) as e:
            log.warning(f"Could not read {filepath}: {e}")
            return 0

        # Mark response heads + zero duplicated multi-block usage, and stamp
        # response_duration_ms on each head. Must run before the rows are
        # written so the per-event columns reflect the deduped values.
        self._annotate_responses(events_data)

        # Insert source file record
        cursor.execute(
            """INSERT INTO source_files
               (filepath, mtime, size_bytes, line_count, last_ingested_at,
                project_id, session_id, file_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                filepath,
                mtime,
                size_bytes,
                line_count,
                datetime.now(UTC).isoformat(),
                project_id,
                detected_session_id,
                file_type,
            ),
        )
        source_file_id = cursor.lastrowid

        # Insert events — append-if-not-exists on canonical (session_id, uuid).
        # When the same JSONL is ingested via a second filepath (e.g. an rsync
        # mirror) the event already lives in the cache — reuse its id and skip
        # the dependent edges/calls writes below so we don't duplicate them
        # either. Backed by idx_events_session_uuid.
        for event in events_data:
            existing_id: int | None = None
            if event["uuid"] is not None:
                row = cursor.execute(
                    "SELECT id FROM events WHERE session_id IS ? AND uuid = ?",
                    (detected_session_id, event["uuid"]),
                ).fetchone()
                if row is not None:
                    existing_id = row[0]

            if existing_id is not None:
                event["_db_id"] = existing_id
                event["_dedup_skip"] = True
                continue

            cursor.execute(
                """INSERT INTO events
                   (uuid, parent_uuid, prompt_id, event_type, msg_kind, timestamp, timestamp_local,
                    session_id, project_id, is_sidechain, agent_id, agent_slug,
                    message_role, message_content, message_content_json, model_id,
                    request_id, stop_reason, is_response_head,
                    context_tokens, context_window, context_ratio,
                    response_duration_ms,
                    input_tokens, output_tokens, cache_read_tokens,
                    cache_creation_tokens, cache_5m_tokens,
                    token_rate, billable_tokens, total_cost_usd,
                    source_file_id, line_number, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event["uuid"],
                    event["parent_uuid"],
                    event["prompt_id"],
                    event["event_type"],
                    event["msg_kind"],
                    event["timestamp"],
                    event["timestamp_local"],
                    detected_session_id,
                    project_id,
                    event["is_sidechain"],
                    event["agent_id"],
                    event["agent_slug"],
                    event["message_role"],
                    event["message_content"],
                    event["message_content_json"],
                    event["model_id"],
                    event["request_id"],
                    event["stop_reason"],
                    event["is_response_head"],
                    event["context_tokens"],
                    event["context_window"],
                    event["context_ratio"],
                    event["response_duration_ms"],
                    event["input_tokens"],
                    event["output_tokens"],
                    event["cache_read_tokens"],
                    event["cache_creation_tokens"],
                    event["cache_5m_tokens"],
                    event["token_rate"],
                    event["billable_tokens"],
                    event["total_cost_usd"],
                    source_file_id,
                    event["line_number"],
                    event["raw_json"],
                ),
            )
            # Capture the rowid so the event_calls insert below can
            # reference each event's primary key without a second lookup.
            event["_db_id"] = cursor.lastrowid

        # Insert event edges for parent-child relationships
        for event in events_data:
            if event.get("_dedup_skip"):
                continue
            if event["uuid"] and event["parent_uuid"]:
                cursor.execute(
                    """INSERT INTO event_edges
                       (project_id, session_id, event_uuid, parent_event_uuid, source_file_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        project_id,
                        detected_session_id,
                        event["uuid"],
                        event["parent_uuid"],
                        source_file_id,
                    ),
                )

        # Fact-table rows for tool/skill/subagent/cli/rule calls. The calls
        # list was attached during _parse_event_for_cache so we're just
        # fanning out the already-parsed content-block signals here.
        for event in events_data:
            if event.get("_dedup_skip"):
                continue
            event_db_id = event.get("_db_id")
            if not event_db_id:
                continue
            for ord_, call_type, call_name in event.get("_calls", ()):
                cursor.execute(
                    """INSERT INTO event_calls
                       (event_id, ord, call_type, call_name,
                        timestamp, project_id, session_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event_db_id,
                        ord_,
                        call_type,
                        call_name,
                        event["timestamp"],
                        project_id,
                        detected_session_id,
                    ),
                )

        return len(events_data)

    # Additive per-event usage measures that downstream SUM()s read. A
    # multi-block response repeats these on every content block, so the
    # post-pass keeps them on the head and zeroes them on the non-heads.
    _USAGE_COLS: tuple[str, ...] = (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_creation_tokens",
        "cache_5m_tokens",
        "billable_tokens",
        "total_cost_usd",
    )

    def _annotate_responses(self, events: list[dict[str, Any]]) -> None:
        """Mark one head event per ``requestId`` and zero duplicated usage.

        A single model response is logged as N content-block events that
        each repeat the same request-level usage. Summing per event would
        over-count N-fold. We keep the usage on exactly one **head** — the
        last block, which carries the final ``stop_reason`` and timestamp —
        and zero it on the continuation blocks, so every downstream
        ``SUM()`` is correct with no query rewrites.

        Operates in place on the already-ordered per-file event list.
        """
        groups: dict[str, list[int]] = {}
        order: list[str] = []
        for i, e in enumerate(events):
            rid = e.get("request_id")
            if e["event_type"] != "assistant" or rid is None:
                e["is_response_head"] = 1  # its own head (synthetic / non-assistant)
                continue
            if rid not in groups:
                groups[rid] = []
                order.append(rid)
            groups[rid].append(i)
        for rid in order:
            idxs = groups[rid]
            head = idxs[-1]  # last block carries stop_reason + final timestamp
            for j in idxs:
                events[j]["is_response_head"] = 1 if j == head else 0
                if j != head:
                    for c in self._USAGE_COLS:
                        events[j][c] = 0
            # Response duration = triggering (preceding) event → head timestamp,
            # falling back to the first block's ts when there is no preceding
            # event. The JSONL has no per-assistant durationMs, so we derive it.
            first = idxs[0]
            start_ts = events[first - 1]["timestamp"] if first > 0 else events[first]["timestamp"]
            events[head]["response_duration_ms"] = _delta_ms(start_ts, events[head]["timestamp"])

    def _parse_event_for_cache(
        self,
        raw: dict[str, Any],
        project_id: str,
        session_id: str | None,
        filepath: str,
        line_number: int,
        file_type: str = "main_session",
    ) -> dict[str, Any] | None:
        """Parse a raw event dict for cache insertion."""
        event_type = raw.get("type", "")

        # Skip file-history-snapshot events
        if event_type == "file-history-snapshot":
            return None

        # Extract fields
        timestamp = raw.get("timestamp")
        uuid = raw.get("uuid")
        parent_uuid = raw.get("parentUuid")
        prompt_id = raw.get("promptId")
        is_sidechain = raw.get("isSidechain", False)
        agent_id = raw.get("agentId")
        agent_slug = raw.get("slug")
        request_id = raw.get("requestId")

        # Extract message info
        is_meta = raw.get("isMeta", False)
        message = raw.get("message", {}) or {}
        message_role = message.get("role") if isinstance(message, dict) else None
        stop_reason = message.get("stop_reason") if isinstance(message, dict) else None
        message_content_raw = message.get("content") if isinstance(message, dict) else None
        model_id = message.get("model") if isinstance(message, dict) else None

        # Sanitize: drop `signature` from thinking blocks (large base64 token, useless for analytics)
        if isinstance(message_content_raw, list):
            message_content_raw = [
                {k: v for k, v in block.items() if k != "signature"}
                if isinstance(block, dict)
                and block.get("type") == "thinking"
                and "signature" in block
                else block
                for block in message_content_raw
            ]

        # Subagent context: per-event sidechain flag OR the file's type
        # (belt-and-braces union per the G3 ADR). Prefixes the kind so
        # subagent activity is distinguishable from the main thread.
        is_subagent = bool(is_sidechain) or file_type in ("subagent", "agent_root")
        # Classify into one of the 9 fine-grained message kinds
        msg_kind = _message_kind(
            event_type, bool(is_meta), message_content_raw, is_subagent=is_subagent
        )

        # Extract plain text for FTS
        message_content_text = self._extract_text_content(message_content_raw)

        # Extract token usage
        usage = message.get("usage", {}) if isinstance(message, dict) else {}
        input_tokens = usage.get("input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        cache_read_tokens = usage.get("cache_read_input_tokens", 0) or 0
        cache_creation_tokens = usage.get("cache_creation_input_tokens", 0) or 0
        cache_creation = usage.get("cache_creation", {}) or {}
        cache_5m_tokens = cache_creation.get("ephemeral_5m_input_tokens", 0) or 0

        # Compute cost fields at ingestion time so they are stored in the DB
        token_rate, billable_tokens, total_cost_usd = _compute_event_costs(
            model_id, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens
        )

        # Live context-window occupancy: the full prompt sent for an assistant
        # response (input + cache_read + cache_creation). Only assistant events
        # carry a meaningful occupancy/window/ratio; others stay 0/None.
        if event_type == "assistant":
            ctx_tokens = input_tokens + cache_read_tokens + cache_creation_tokens
        else:
            ctx_tokens = 0
        ctx_window = context_window(model_id)
        ctx_ratio = context_ratio(ctx_tokens, ctx_window)

        # Compute local timestamp
        timestamp_local = None
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                local_dt = dt.astimezone()
                timestamp_local = local_dt.isoformat()
            except (ValueError, TypeError):
                pass

        return {
            "uuid": uuid,
            "parent_uuid": parent_uuid,
            "prompt_id": prompt_id,
            "event_type": event_type,
            "msg_kind": msg_kind,
            "timestamp": timestamp,
            "timestamp_local": timestamp_local,
            "is_sidechain": 1 if is_sidechain else 0,
            "agent_id": agent_id,
            "agent_slug": agent_slug,
            "message_role": message_role,
            "message_content": message_content_text,
            "message_content_json": json.dumps(message_content_raw)
            if message_content_raw
            else None,
            "model_id": model_id,
            "request_id": request_id,
            "stop_reason": stop_reason,
            # Default to its own head; _annotate_responses (a per-file
            # post-pass) demotes the duplicated continuation blocks of a
            # multi-block response to is_response_head=0 and zeroes their usage.
            "is_response_head": 1,
            "context_tokens": ctx_tokens,
            "context_window": ctx_window,
            "context_ratio": ctx_ratio,
            # Stamped on the response head by _annotate_responses; None elsewhere.
            "response_duration_ms": None,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "cache_creation_tokens": cache_creation_tokens,
            "cache_5m_tokens": cache_5m_tokens,
            "token_rate": token_rate,
            "billable_tokens": billable_tokens,
            "total_cost_usd": total_cost_usd,
            "line_number": line_number,
            # raw_json is intentionally empty — the source-of-truth for the
            # raw payload is the JSONL file on disk (see source_files.filepath
            # + line_number). Storing a duplicate copy here was costing 2+ GB
            # and leaking thinking-block signatures into the cache. Read paths
            # that previously did `json.loads(row["raw_json"])` already handle
            # JSONDecodeError by returning None.
            "raw_json": "",
            # Fact-table rows for tool/skill/subagent/cli/rule calls. Parsed
            # once here so ingest_file() can fan them out to event_calls
            # after the event row's primary key is known.
            "_calls": extract_calls(raw),
        }

    def _extract_text_content(self, content: Any) -> str:
        """Extract plain text from message content for FTS."""
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "thinking":
                        parts.append(block.get("thinking", ""))
                    elif block.get("type") == "tool_use":
                        parts.append(f"[tool: {block.get('name', '')}]")
                        inp = block.get("input", {})
                        if isinstance(inp, dict):
                            for v in inp.values():
                                if isinstance(v, str):
                                    parts.append(v[:500])  # Limit tool input text
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(filter(None, parts))

        return ""

    # ------------------------------------------------------------------
    # Dimensional aggregates (agg_{hourly,daily,weekly,monthly})
    # ------------------------------------------------------------------
    #
    # These tables are pre-aggregated measures at four time granularities.
    # Schema matches the sibling claude-code-sessions SQLite backend so both
    # tools maintain a consistent view. Grain: (time_bucket, project_id,
    # session_id, model_id). NULL session_id/model_id are stored as '' so
    # the composite PRIMARY KEY enforces uniqueness correctly.

    _AGG_BUCKET_EXPRS: dict[str, str] = {
        "hourly": "strftime('%Y-%m-%dT%H:00:00', timestamp)",
        "daily": "date(timestamp)",
        "weekly": "date(timestamp, 'weekday 0', '-6 days')",
        "monthly": "strftime('%Y-%m-01', timestamp)",
    }

    def refresh_aggregates_for_range(
        self,
        start_bucket: str | None = None,
        end_bucket: str | None = None,
    ) -> dict[str, int]:
        """Refresh the agg table for all granularities in a time range (or fully)."""
        cursor = self.conn.cursor()
        counts: dict[str, int] = {}
        for granularity, bucket_expr in self._AGG_BUCKET_EXPRS.items():
            if start_bucket is None or end_bucket is None:
                cursor.execute("DELETE FROM agg WHERE granularity = ?", (granularity,))
                range_clause = ""
                range_params: tuple[str, ...] = ()
            else:
                cursor.execute(
                    "DELETE FROM agg WHERE granularity = ? AND time_bucket >= ? AND time_bucket <= ?",
                    (granularity, start_bucket, end_bucket),
                )
                range_clause = f"AND {bucket_expr} BETWEEN ? AND ?"
                range_params = (start_bucket, end_bucket)

            cursor.execute(
                f"""
                INSERT INTO agg (
                    granularity, time_bucket, project_id, session_id, model_id,
                    event_count,
                    input_tokens, output_tokens,
                    cache_read_tokens, cache_creation_tokens,
                    total_cost_usd, billable_tokens
                )
                SELECT
                    '{granularity}',
                    {bucket_expr} AS time_bucket,
                    project_id,
                    COALESCE(session_id, ''),
                    COALESCE(model_id, ''),
                    COUNT(*),
                    COALESCE(SUM(input_tokens), 0),
                    COALESCE(SUM(output_tokens), 0),
                    COALESCE(SUM(cache_read_tokens), 0),
                    COALESCE(SUM(cache_creation_tokens), 0),
                    COALESCE(SUM(total_cost_usd), 0.0),
                    COALESCE(SUM(billable_tokens), 0.0)
                FROM events
                WHERE timestamp IS NOT NULL
                  {range_clause}
                GROUP BY {bucket_expr}, project_id,
                         COALESCE(session_id, ''), COALESCE(model_id, '')
            """,
                range_params,
            )
            counts[granularity] = cursor.rowcount
        self.conn.commit()
        return counts

    def rebuild_aggregates(self) -> None:
        """Rebuild projects and sessions tables from events."""
        log.info("Rebuilding aggregate tables...")
        cursor = self.conn.cursor()

        # Rebuild projects
        cursor.execute("DELETE FROM projects")
        cursor.execute("""
            INSERT INTO projects (project_id, first_activity, last_activity, session_count, event_count)
            SELECT
                project_id,
                MIN(timestamp) as first_activity,
                MAX(timestamp) as last_activity,
                COUNT(DISTINCT session_id) as session_count,
                COUNT(*) as event_count
            FROM events
            WHERE timestamp IS NOT NULL
            GROUP BY project_id
        """)

        # Rebuild sessions
        cursor.execute("DELETE FROM sessions")
        cursor.execute("""
            INSERT INTO sessions (
                session_id, project_id, first_timestamp, last_timestamp,
                event_count, subagent_count,
                total_input_tokens, total_output_tokens,
                total_cache_read_tokens, total_cache_creation_tokens
            )
            SELECT
                session_id,
                project_id,
                MIN(timestamp) as first_timestamp,
                MAX(timestamp) as last_timestamp,
                COUNT(*) as event_count,
                COUNT(DISTINCT agent_id) - 1 as subagent_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(cache_read_tokens) as total_cache_read_tokens,
                SUM(cache_creation_tokens) as total_cache_creation_tokens
            FROM events
            WHERE session_id IS NOT NULL
            GROUP BY project_id, session_id
        """)

        # Sum per-event cost from events.total_cost_usd, which was
        # populated at ingest by _compute_event_costs(). The events column
        # is the single source of truth so rollup matches the dashboard
        # backend's rebuild_aggregates() — see
        # src/claude_code_sessions/database/sqlite/cache.py.
        cursor.execute("""
            UPDATE sessions SET total_cost_usd = (
                SELECT COALESCE(SUM(e.total_cost_usd), 0)
                FROM events e
                WHERE e.session_id = sessions.session_id
                  AND e.project_id = sessions.project_id
            )
        """)

        self._compute_session_timing(cursor)

        self.conn.commit()
        log.info("Aggregate tables rebuilt")

    def _compute_session_timing(self, cursor: sqlite3.Cursor) -> None:
        """Populate the per-session timing/throughput rollups on the sessions
        table: avg_tps, peak_context_ratio, total_idle_ms, total_active_ms.

        Called inside rebuild_aggregates once the sessions rows exist, so the
        hot sessions-list read serves precomputed values instead of windowing
        over events per request. Idle/active use the same main-thread turn walk
        as get_session_metrics (LEAD for idle; running-max human ts for active).
        Timestamps are UTC 'Z'; stripping the suffix lets julianday parse the
        naive form — the delta is unaffected.
        """
        # avg_tps + peak_context_ratio: correlated subqueries over the heads.
        cursor.execute("""
            UPDATE sessions SET
                peak_context_ratio = (
                    SELECT MAX(e.context_ratio) FROM events e
                    WHERE e.session_id = sessions.session_id
                      AND e.project_id = sessions.project_id
                ),
                avg_tps = (
                    SELECT CASE WHEN SUM(e.response_duration_ms) > 0
                                THEN ROUND(SUM(e.output_tokens) * 1000.0
                                           / SUM(e.response_duration_ms), 4)
                                ELSE NULL END
                    FROM events e
                    WHERE e.session_id = sessions.session_id
                      AND e.project_id = sessions.project_id
                      AND e.is_response_head = 1 AND e.event_type = 'assistant'
                      AND e.response_duration_ms > 0
                )
        """)
        # idle/active: one windowed turn walk, summed per (project, session).
        cursor.execute("""
            UPDATE sessions SET
                total_idle_ms = COALESCE(tt.idle_ms, 0),
                total_active_ms = COALESCE(tt.active_ms, 0)
            FROM (
                WITH walk AS (
                    SELECT project_id, session_id, event_type, stop_reason,
                           is_response_head, timestamp,
                           LEAD(timestamp) OVER w AS next_ts,
                           MAX(CASE WHEN msg_kind = 'human' THEN timestamp END) OVER (
                               PARTITION BY session_id ORDER BY timestamp
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                           ) AS last_human
                    FROM events
                    WHERE is_sidechain = 0
                    WINDOW w AS (PARTITION BY session_id ORDER BY timestamp)
                )
                SELECT project_id, session_id,
                       CAST(ROUND(SUM(CASE WHEN next_ts IS NOT NULL THEN MAX(0,
                           (julianday(REPLACE(next_ts, 'Z', ''))
                            - julianday(REPLACE(timestamp, 'Z', ''))) * 86400000)
                           ELSE 0 END)) AS INTEGER) AS idle_ms,
                       CAST(ROUND(SUM(CASE WHEN last_human IS NOT NULL THEN MAX(0,
                           (julianday(REPLACE(timestamp, 'Z', ''))
                            - julianday(REPLACE(last_human, 'Z', ''))) * 86400000)
                           ELSE 0 END)) AS INTEGER) AS active_ms
                FROM walk
                WHERE event_type = 'assistant' AND is_response_head = 1
                  AND stop_reason = 'end_turn'
                GROUP BY project_id, session_id
            ) AS tt
            WHERE sessions.session_id = tt.session_id
              AND sessions.project_id = tt.project_id
        """)

    def migrate_dedupe_session_uuid(self) -> dict[str, int] | None:
        """Prune (session_id, uuid) duplicates left behind by rsync-mirror
        ingestion that predates append-if-not-exists semantics in
        ``ingest_file``.

        Mirrors ``CacheManager.migrate_dedupe_session_uuid`` in the
        ``claude_code_sessions`` package — same sentinel, same SQL, same
        cascade strategy. See that docstring for the full rationale.
        Idempotent — returns None when the sentinel is already set.
        """
        cursor = self.conn.cursor()
        row = cursor.execute(
            "SELECT value FROM cache_metadata WHERE key = ?",
            (DEDUPE_SESSION_UUID_MIGRATION_KEY,),
        ).fetchone()
        if row is not None and row[0] == "1":
            return None

        t0 = time.monotonic()
        log.info("════════════════════════════════════════════════════════")
        log.info(" Dedupe migration: (session_id, uuid) prune")
        log.info("════════════════════════════════════════════════════════")

        events_before = cursor.execute("SELECT COUNT(*) FROM events").fetchone()[0]

        cursor.execute(
            """
            DELETE FROM events
            WHERE uuid IS NOT NULL
              AND id NOT IN (
                SELECT MIN(id) FROM events
                WHERE uuid IS NOT NULL
                GROUP BY session_id, uuid
              )
            """
        )
        events_deleted = cursor.rowcount

        cursor.execute(
            """
            DELETE FROM event_edges
            WHERE id NOT IN (
                SELECT MIN(id) FROM event_edges
                GROUP BY project_id, session_id, event_uuid, parent_event_uuid
            )
            """
        )
        edges_deleted = cursor.rowcount

        cursor.execute(
            """
            DELETE FROM source_files
            WHERE id NOT IN (
                    SELECT DISTINCT source_file_id FROM events
                    WHERE source_file_id IS NOT NULL
                )
              AND id NOT IN (
                    SELECT DISTINCT source_file_id FROM event_edges
                    WHERE source_file_id IS NOT NULL
                )
            """
        )
        source_files_deleted = cursor.rowcount

        cursor.execute(
            "DELETE FROM ner_chunks_log WHERE chunk_id NOT IN "
            "(SELECT chunk_id FROM event_message_chunks)"
        )
        ner_log_deleted = cursor.rowcount
        cursor.execute(
            "DELETE FROM re_chunks_log WHERE chunk_id NOT IN "
            "(SELECT chunk_id FROM event_message_chunks)"
        )
        re_log_deleted = cursor.rowcount

        cursor.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
            (DEDUPE_SESSION_UUID_MIGRATION_KEY, "1"),
        )
        self.conn.commit()

        events_after = cursor.execute("SELECT COUNT(*) FROM events").fetchone()[0]

        log.info(
            "  pruned: events %d → %d (-%d), edges -%d, source_files -%d, ner_log -%d, re_log -%d",
            events_before,
            events_after,
            events_deleted,
            edges_deleted,
            source_files_deleted,
            ner_log_deleted,
            re_log_deleted,
        )

        self.rebuild_aggregates()
        self.refresh_aggregates_for_range()

        log.info(
            "  dedupe migration complete in %.1f s (run VACUUM separately to reclaim disk space)",
            time.monotonic() - t0,
        )

        return {
            "events_deleted": events_deleted,
            "edges_deleted": edges_deleted,
            "source_files_deleted": source_files_deleted,
            "ner_log_deleted": ner_log_deleted,
            "re_log_deleted": re_log_deleted,
        }

    def build_cross_agent_edges(self, session_id: str, project_id: str) -> int:
        """Create synthetic bridge edges from subagent first events to parent tool_use events.

        Subagent JSONL first events have ``parentUuid=null`` — they are roots of their own
        conversation thread with no direct pointer back to the parent session.

        **Join key — ``promptId``:** Claude Code writes the same ``promptId`` to both:

        - The subagent's first event (the ``user`` message injected as its initial context).
        - The parent session's ``tool_result`` event that delivers the agent's response.

        The parent ``tool_result`` itself has ``parentUuid`` pointing to the ``tool_use``
        event that spawned the agent.  So the bridge walks:

            subagent_first.prompt_id == tool_result.prompt_id
            → tool_result.parent_uuid == tool_use.uuid
            → bridge edge: (subagent_first_uuid, tool_use_uuid)

        Bridge edges use the subagent's ``source_file_id`` so they are automatically cleaned
        up and recreated whenever the subagent file is re-ingested.

        Returns the number of new edges inserted.
        """
        cursor = self.conn.cursor()

        # Find all subagent "root" events: null parentUuid + non-null agentId + is_sidechain
        # and a non-null promptId (the join key)
        subagent_starts = cursor.execute(
            """
            SELECT e.uuid, e.prompt_id, e.agent_id, e.source_file_id
            FROM events e
            WHERE e.session_id = ?
              AND e.parent_uuid IS NULL
              AND e.agent_id IS NOT NULL
              AND e.is_sidechain = 1
              AND e.prompt_id IS NOT NULL
            """,
            (session_id,),
        ).fetchall()

        created = 0
        for start in subagent_starts:
            # Skip if any bridge edge for this event_uuid already exists
            exists = cursor.execute(
                "SELECT 1 FROM event_edges WHERE session_id = ? AND event_uuid = ?",
                (session_id, start["uuid"]),
            ).fetchone()
            if exists:
                continue

            # Find the tool_use that spawned this agent via prompt_id:
            #   subagent_first.prompt_id == tool_result.prompt_id
            #   tool_result.parent_uuid  == tool_use.uuid
            parent_tool_use = cursor.execute(
                """
                SELECT tool_result.parent_uuid AS tool_use_uuid
                FROM events tool_result
                WHERE tool_result.session_id = ?
                  AND tool_result.agent_id IS NULL
                  AND tool_result.msg_kind = 'tool_result'
                  AND tool_result.prompt_id = ?
                  AND tool_result.parent_uuid IS NOT NULL
                LIMIT 1
                """,
                (session_id, start["prompt_id"]),
            ).fetchone()

            if parent_tool_use and parent_tool_use["tool_use_uuid"]:
                cursor.execute(
                    """
                    INSERT INTO event_edges
                        (project_id, session_id, event_uuid, parent_event_uuid, source_file_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        session_id,
                        start["uuid"],
                        parent_tool_use["tool_use_uuid"],
                        start["source_file_id"],
                    ),
                )
                created += 1
                log.debug(
                    "bridge edge: %s → %s (agent_id=%s, prompt_id=%s)",
                    start["uuid"],
                    parent_tool_use["tool_use_uuid"],
                    start["agent_id"],
                    start["prompt_id"],
                )

        if created:
            self.conn.commit()
        return created

    def update(self, projects_path: Path) -> dict[str, Any]:
        """Perform incremental update of the cache. Returns counts."""
        log.info("Starting incremental cache update...")

        # Discover all files
        all_files = self.discover_files(projects_path)
        log.info(f"Discovered {len(all_files)} total files")

        # Find files needing update
        files_to_update = self.get_files_needing_update(all_files)
        log.info(f"Found {len(files_to_update)} files needing update")

        if not files_to_update:
            log.info("Cache is up to date")
            # Still run downstream syncs — chunks / HNSW may be behind
            # the events table after a schema version bump. Both calls
            # are incremental and cheap no-ops when everything is in
            # step.
            chunks_added = sync_chunks(self.conn)
            embeddings_added = 0
            if os.environ.get(
                "CLAUDE_SESSIONS_DISABLE_EMBEDDINGS",
                "",
            ).strip().lower() not in {"1", "true", "yes", "on"}:
                model_path = ensure_model_downloaded()
                setup_embedding_runtime(self.conn, model_path)
                embeddings_added = sync_embeddings(self.conn)
                # KG phase mirrors the backend's wave-pipeline phase 7.
                # Incremental + heavy on first run (GLiNER2 weights ~205 MB
                # download). Same disable-knob as embeddings, since KG
                # depends on the embedding HNSW being live.
                sync_kg(self.conn)
            return {
                "files_updated": 0,
                "events_added": 0,
                "chunks_added": chunks_added,
                "embeddings_added": embeddings_added,
            }

        # Ingest updated files, tracking which sessions were touched
        total_events = 0
        affected_sessions: dict[str, str] = {}  # session_id → project_id
        for file_info in files_to_update:
            events_added = self.ingest_file(file_info)
            total_events += events_added
            log.debug(
                f"  {file_info['filepath']}: {events_added} events ({file_info.get('reason', 'new')})"
            )
            sid = file_info.get("session_id")
            if sid:
                affected_sessions[sid] = file_info["project_id"]

        self.conn.commit()

        # Build cross-agent bridge edges for every touched session
        total_bridges = 0
        for sid, pid in affected_sessions.items():
            total_bridges += self.build_cross_agent_edges(sid, pid)
        if total_bridges:
            log.info(f"Created {total_bridges} cross-agent bridge edges")

        # Rebuild aggregates (projects + sessions — cheap)
        self.rebuild_aggregates()

        # Dimensional agg table — full rebuild when empty, otherwise
        # incremental by the timestamp window of ingested sessions.
        agg_empty = self.conn.execute("SELECT COUNT(*) FROM agg").fetchone()[0] == 0
        if agg_empty:
            log.info("Dimensional aggregates empty — doing full cold rebuild")
            self.refresh_aggregates_for_range()
        elif affected_sessions:
            # Scope the refresh to just the sessions we touched
            session_ids = list(affected_sessions.keys())
            placeholders = ",".join("?" * len(session_ids))
            row = self.conn.execute(
                f"""
                SELECT MIN(timestamp), MAX(timestamp)
                FROM events
                WHERE timestamp IS NOT NULL
                  AND session_id IN ({placeholders})
                """,
                tuple(session_ids),
            ).fetchone()
            if row and row[0]:
                self.refresh_aggregates_for_range(str(row[0]), str(row[1]))

        # Chunking + embeddings. Incremental; no-op when nothing is stale.
        # First-run embedding downloads ~150 MB GGUF model and processes
        # the backlog — takes minutes. Set the env var to skip in tests
        # or when the introspect script is only used for its other
        # subcommands.
        chunks_added = sync_chunks(self.conn)
        embeddings_added = 0
        if os.environ.get(
            "CLAUDE_SESSIONS_DISABLE_EMBEDDINGS",
            "",
        ).strip().lower() not in {"1", "true", "yes", "on"}:
            model_path = ensure_model_downloaded()
            setup_embedding_runtime(self.conn, model_path)
            embeddings_added = sync_embeddings(self.conn)
            sync_kg(self.conn)

        # Update metadata
        self.conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
            ("last_update_at", datetime.now(UTC).isoformat()),
        )
        self.conn.commit()

        log.info(
            f"Updated {len(files_to_update)} files, {total_events} events, "
            f"{chunks_added} chunks, {embeddings_added} embeddings"
        )
        return {
            "files_updated": len(files_to_update),
            "events_added": total_events,
            "chunks_added": chunks_added,
            "embeddings_added": embeddings_added,
        }


# ============================================================================
# Session Event Data Class (for non-cached operations)
# ============================================================================


@dataclass
class SessionEvent:
    """Represents a single event from a session JSONL file."""

    uuid: str | None
    parent_uuid: str | None
    event_type: str
    timestamp: str | None
    timestamp_local: str | None
    session_id: str | None
    is_sidechain: bool
    agent_id: str | None
    agent_slug: str | None
    message_role: str | None
    message_content: str | list[dict[str, Any]] | None
    model_id: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cache_5m_tokens: int
    filepath: str
    line_number: int
    is_subagent_file: bool
    raw_event: dict[str, Any] = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "uuid": self.uuid,
            "parent_uuid": self.parent_uuid,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "timestamp_local": self.timestamp_local,
            "session_id": self.session_id,
            "is_sidechain": self.is_sidechain,
            "agent_id": self.agent_id,
            "agent_slug": self.agent_slug,
            "message_role": self.message_role,
            "message_content": self.message_content,
            "model_id": self.model_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_5m_tokens": self.cache_5m_tokens,
            "filepath": self.filepath,
            "line_number": self.line_number,
            "is_subagent_file": self.is_subagent_file,
            "message_json": self.raw_event,
        }


# ============================================================================
# Query Functions (using SQLite cache)
# ============================================================================


def infer_project_id(cache: CacheManager, cwd: Path | None = None) -> str | None:
    """Infer the project_id from the current working directory.

    Converts the CWD to Claude Code's project ID format (each '/' replaced with '-')
    and checks whether it exists in the projects table.  Returns the matching
    project_id, or None if no match is found.
    """
    candidate = str(cwd or Path.cwd()).replace("/", "-")
    cursor = cache.conn.cursor()
    row = cursor.execute(
        "SELECT project_id FROM projects WHERE project_id = ? LIMIT 1",
        (candidate,),
    ).fetchone()
    return str(row["project_id"]) if row else None


def ensure_cache(cache: CacheManager, projects_path: Path | None = None) -> None:
    """Ensure cache exists and is initialized."""
    if projects_path is None:
        projects_path = PROJECTS_PATH
    if not cache.db_path.exists():
        log.info("Cache not found, initializing...")
        cache.init_schema()
        cache.update(projects_path)
    elif cache.needs_rebuild():
        log.info("Schema version mismatch, rebuilding cache...")
        cache.reset()
        cache.update(projects_path)
    else:
        # One-shot data migrations on an existing, current-schema cache.
        # Sentinel-gated in cache_metadata so it's a no-op after first run.
        cache.migrate_dedupe_session_uuid()


def resolve_project_id(cache: CacheManager, session_id: str) -> str | None:
    """Look up the project_id for a given session_id from the cache."""
    cursor = cache.conn.cursor()
    row = cursor.execute(
        "SELECT project_id FROM sessions WHERE session_id = ? LIMIT 1",
        (session_id,),
    ).fetchone()
    if row:
        return str(row["project_id"])
    # Fallback: check the events table directly
    row = cursor.execute(
        "SELECT project_id FROM events WHERE session_id = ? LIMIT 1",
        (session_id,),
    ).fetchone()
    return str(row["project_id"]) if row else None


def cmd_project_id(cache: CacheManager, session_id: str) -> dict[str, str]:
    """Resolve the project_id for a session_id."""
    ensure_cache(cache)
    pid = resolve_project_id(cache, session_id)
    if not pid:
        return {"error": f"No project found for session {session_id}"}
    return {"project_id": pid}


def cmd_cache_init(cache: CacheManager) -> dict[str, Any]:
    """Initialize the cache database."""
    cache.init_schema()
    return {"status": "initialized", "db_path": str(cache.db_path)}


def cmd_cache_clear(cache: CacheManager) -> dict[str, Any]:
    """Clear all cached data."""
    cache.clear()
    return {"status": "cleared", "db_path": str(cache.db_path)}


def cmd_cache_rebuild(cache: CacheManager, projects_path: Path | None = None) -> dict[str, Any]:
    """Full rebuild of the cache."""
    if projects_path is None:
        projects_path = PROJECTS_PATH
    cache.reset()
    result = cache.update(projects_path)
    result["status"] = "rebuilt"
    return result


def cmd_cache_update(cache: CacheManager, projects_path: Path | None = None) -> dict[str, Any]:
    """Incremental update of the cache."""
    if projects_path is None:
        projects_path = PROJECTS_PATH
    ensure_cache(cache, projects_path)
    result = cache.update(projects_path)
    result["status"] = "updated"
    return result


def cmd_cache_status(cache: CacheManager) -> dict[str, Any]:
    """Get cache status information."""
    if not cache.db_path.exists():
        return {"status": "not_initialized", "db_path": str(cache.db_path)}
    return cache.get_status()


def cmd_projects(cache: CacheManager) -> list[dict[str, Any]]:
    """List all projects with session counts and date ranges."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    results = cursor.execute("""
        SELECT project_id, session_count, first_activity, last_activity, event_count
        FROM projects
        ORDER BY last_activity DESC
    """).fetchall()

    return [dict(row) for row in results]


def cmd_sessions(
    cache: CacheManager,
    project_id: str,
    limit: int = 20,
    since: str | None = None,
) -> list[dict[str, Any]]:
    """List sessions for a project with event counts and time info."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    query = """
        SELECT
            session_id, project_id, first_timestamp, last_timestamp,
            event_count, subagent_count,
            total_input_tokens, total_output_tokens,
            total_cache_read_tokens, total_cache_creation_tokens,
            total_cost_usd
        FROM sessions
        WHERE project_id = ?
    """
    params: list[Any] = [project_id]

    if since:
        since_dt = parse_time_filter(since)
        if since_dt:
            query += " AND last_timestamp >= ?"
            params.append(since_dt.isoformat())

    query += " ORDER BY last_timestamp DESC LIMIT ?"
    params.append(limit)

    results = cursor.execute(query, params).fetchall()
    return [dict(row) for row in results]


def _escape_fts5_query(pattern: str) -> str:
    """Escape a plain-text search string for safe use in FTS5 MATCH.

    FTS5 query syntax reserves characters like . : * + - ^ ( ) " and
    keywords AND/OR/NOT/NEAR.  Wrapping each whitespace-delimited token
    in double-quotes forces FTS5 to pass them through the tokenizer as
    literals rather than interpreting them as operators.

    Examples:
        common.cpp       -> "common.cpp"
        foo AND bar      -> "foo" "AND" "bar"
        hello world      -> "hello" "world"
        "already quoted"  -> "already quoted"  (pass-through)
    """
    stripped = pattern.strip()
    if not stripped:
        return '""'
    # If the user already wrapped the whole thing in double quotes, pass through
    if stripped.startswith('"') and stripped.endswith('"') and stripped.count('"') == 2:
        return stripped
    # Split on whitespace, wrap each token in double-quotes.
    # Internal double-quotes are escaped by doubling them (FTS5 convention).
    tokens = stripped.split()
    escaped = " ".join(f'"{tok.replace(chr(34), chr(34) + chr(34))}"' for tok in tokens)
    return escaped


def cmd_search(
    cache: CacheManager,
    pattern: str,
    project_id: str | None = None,
    event_types: list[str] | None = None,
    limit: int = 50,
    since: str | None = None,
) -> list[dict[str, Any]]:
    """Full-text search across sessions using FTS5."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    # Escape plain-text pattern for FTS5 query syntax
    fts_pattern = _escape_fts5_query(pattern)

    # Use FTS5 for search
    query = """
        SELECT
            e.uuid, e.project_id, e.session_id, e.event_type, e.timestamp,
            SUBSTR(e.message_content, 1, 200) as content_preview,
            sf.filepath, e.line_number
        FROM events e
        JOIN events_fts fts ON e.id = fts.rowid
        JOIN source_files sf ON e.source_file_id = sf.id
        WHERE events_fts MATCH ?
    """
    params: list[Any] = [fts_pattern]

    if project_id:
        query += " AND e.project_id = ?"
        params.append(project_id)

    if event_types:
        placeholders = ",".join("?" * len(event_types))
        query += f" AND e.msg_kind IN ({placeholders})"
        params.extend(event_types)

    if since:
        since_dt = parse_time_filter(since)
        if since_dt:
            query += " AND e.timestamp >= ?"
            params.append(since_dt.strftime("%Y-%m-%dT%H:%M:%S"))

    query += " ORDER BY e.timestamp DESC LIMIT ?"
    params.append(limit)

    results = cursor.execute(query, params).fetchall()
    return [dict(row) for row in results]


def cmd_event(
    cache: CacheManager,
    session_id: str,
    uuid: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Get a specific event by its UUID."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    query = """
        SELECT e.*, sf.filepath
        FROM events e
        JOIN source_files sf ON e.source_file_id = sf.id
        WHERE e.session_id = ? AND e.uuid = ?
    """
    params: list[Any] = [session_id, uuid]

    if project_id:
        query += " AND e.project_id = ?"
        params.append(project_id)

    result = cursor.execute(query, params).fetchone()

    if not result:
        return {"error": f"Event not found: {uuid}"}

    row = dict(result)

    # Parse content JSON if present
    if row.get("message_content_json"):
        try:
            row["message_content"] = json.loads(row["message_content_json"])
        except json.JSONDecodeError:
            pass

    # Parse raw JSON
    if row.get("raw_json"):
        try:
            row["message_json"] = json.loads(row["raw_json"])
        except json.JSONDecodeError:
            row["message_json"] = None

    return row


def cmd_traverse(
    cache: CacheManager,
    session_id: str,
    uuid: str | None = None,
    direction: Literal["ancestors", "descendants", "both"] = "both",
    project_id: str | None = None,
    depth_limit: int = 3,
    event_types: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    result_limit: int | None = None,
    detail: Literal["normal", "full"] = "normal",
    all_events: bool = False,
    summary: bool = False,
    offset: int = 0,
    include_content: bool = True,
) -> list[dict[str, Any]]:
    """Retrieve and traverse session events.

    Three modes of operation:
    - **summary** (``summary=True``): Per-agent/subagent aggregated stats — event counts,
      token totals, and accurate costs via ``SUM(billable_tokens)`` / ``SUM(total_cost_usd)``.
      Includes both the main session (``agent_id=NULL``) and all subagents.
    - **all** (``all_events=True``): Flat chronological listing of all events in the session,
      including subagent events.  Supports ``offset``, ``result_limit``, ``event_types``,
      ``since``/``until``, ``detail``, and ``include_content``.
    - **graph traversal** (default): Walk the ``event_edges`` ancestor/descendant tree from a
      starting UUID.  When ``uuid`` is omitted, defaults to the most recent event so traversal
      walks backwards through recent history.

    Args:
        uuid: Starting UUID for graph traversal. Defaults to most-recent event when omitted.
        depth_limit: Max hops from starting UUID. 0 = unlimited. Default 3.
        event_types: Filter results by msg_kind (applied after traversal or in WHERE clause).
        since / until: ISO or relative time bounds.
        result_limit: Cap the number of events returned.
        detail: "normal" returns key fields only; "full" adds raw_json and message_json.
        all_events: Bypass graph traversal; return all session events chronologically.
        summary: Return per-agent aggregated stats instead of individual events.
        offset: Skip first N events (used with all_events mode).
        include_content: Include message content and role in all_events normal-detail output.
    """
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    # --- SUMMARY MODE: per-agent aggregated stats ---
    if summary:
        agg_query = """
            SELECT
                agent_id,
                agent_slug,
                MAX(is_sidechain) as is_sidechain,
                MIN(timestamp) as first_event,
                MAX(timestamp) as last_event,
                COUNT(*) as event_count,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(cache_read_tokens) as cache_read_tokens,
                SUM(cache_creation_tokens) as cache_creation_tokens,
                SUM(billable_tokens) as total_billable_tokens,
                SUM(total_cost_usd) as total_cost_usd
            FROM events
            WHERE session_id = ?
        """
        agg_params: list[Any] = [session_id]
        if project_id:
            agg_query += " AND project_id = ?"
            agg_params.append(project_id)
        agg_query += " GROUP BY agent_id ORDER BY first_event"
        return [dict(row) for row in cursor.execute(agg_query, agg_params).fetchall()]

    # --- ALL-EVENTS MODE: flat chronological listing ---
    if all_events:
        flat_query = """
            SELECT
                e.uuid, e.parent_uuid, e.event_type, e.msg_kind, e.timestamp, e.timestamp_local,
                e.message_role, e.message_content, e.message_content_json, e.model_id,
                e.input_tokens, e.output_tokens, e.cache_read_tokens, e.cache_creation_tokens,
                e.token_rate, e.billable_tokens, e.total_cost_usd,
                e.agent_id, e.agent_slug, sf.filepath, e.line_number, e.raw_json
            FROM events e
            JOIN source_files sf ON e.source_file_id = sf.id
            WHERE e.session_id = ?
        """
        flat_params: list[Any] = [session_id]
        if project_id:
            flat_query += " AND e.project_id = ?"
            flat_params.append(project_id)
        if event_types:
            placeholders = ",".join("?" * len(event_types))
            flat_query += f" AND e.msg_kind IN ({placeholders})"
            flat_params.extend(event_types)
        if since:
            since_dt = parse_time_filter(since)
            if since_dt:
                flat_query += " AND e.timestamp >= ?"
                flat_params.append(since_dt.isoformat())
        if until:
            until_dt = parse_time_filter(until)
            if until_dt:
                flat_query += " AND e.timestamp <= ?"
                flat_params.append(until_dt.isoformat())
        limit_val = result_limit if result_limit is not None else -1
        flat_query += f" ORDER BY e.timestamp LIMIT {limit_val} OFFSET {offset}"
        flat_rows = cursor.execute(flat_query, flat_params).fetchall()

        turns: list[dict[str, Any]] = []
        for i, row in enumerate(flat_rows, start=offset + 1):
            if detail == "full":
                ev: dict[str, Any] = dict(row)
                if ev.get("raw_json"):
                    try:
                        ev["message_json"] = json.loads(ev["raw_json"])
                    except json.JSONDecodeError:
                        ev["message_json"] = None
                turns.append(ev)
            else:
                turn: dict[str, Any] = {
                    "turn_num": i,
                    "type": row["event_type"],
                    "msg_kind": row["msg_kind"],
                    "timestamp": row["timestamp"],
                    "model_id": row["model_id"],
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "cache_read_tokens": row["cache_read_tokens"],
                    "cache_creation_tokens": row["cache_creation_tokens"],
                    "token_rate": row["token_rate"],
                    "billable_tokens": row["billable_tokens"],
                    "total_cost_usd": row["total_cost_usd"],
                    "uuid": row["uuid"],
                    "parent_uuid": row["parent_uuid"],
                    "agent_id": row["agent_id"],
                    "agent_slug": row["agent_slug"],
                    "filepath": row["filepath"],
                    "line_number": row["line_number"],
                }
                if include_content:
                    if row["message_content_json"]:
                        try:
                            turn["content"] = json.loads(row["message_content_json"])
                        except json.JSONDecodeError:
                            turn["content"] = row["message_content"]
                    else:
                        turn["content"] = row["message_content"]
                    turn["role"] = row["message_role"]
                turns.append(turn)
        return turns

    # --- GRAPH TRAVERSAL MODE ---
    # Resolve UUID — default to most recent event in this session
    if uuid is None:
        row = cursor.execute(
            "SELECT uuid FROM events WHERE session_id = ? ORDER BY timestamp DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if row is None:
            return []
        uuid = str(row["uuid"])
        log.info("traverse: defaulting to most recent event %s", uuid)

    result_uuids: set[str] = {uuid}
    depth_clause = f"AND aw.depth < {depth_limit}" if depth_limit > 0 else ""

    # Walk ancestors via recursive CTE
    if direction in ("ancestors", "both"):
        ancestor_sql = f"""
            WITH RECURSIVE ancestor_walk(current_uuid, depth) AS (
                SELECT ?, 0
                UNION
                SELECT ee.parent_event_uuid, aw.depth + 1
                FROM event_edges ee
                INNER JOIN ancestor_walk aw ON ee.event_uuid = aw.current_uuid
                WHERE ee.session_id = ? {depth_clause}
            )
            SELECT current_uuid FROM ancestor_walk
        """
        ancestor_params: list[Any] = [uuid, session_id]
        rows = cursor.execute(ancestor_sql, ancestor_params).fetchall()
        result_uuids.update(row[0] for row in rows)

    depth_clause = f"AND dw.depth < {depth_limit}" if depth_limit > 0 else ""

    # Walk descendants via recursive CTE
    if direction in ("descendants", "both"):
        descendant_sql = f"""
            WITH RECURSIVE descendant_walk(current_uuid, depth) AS (
                SELECT ?, 0
                UNION
                SELECT ee.event_uuid, dw.depth + 1
                FROM event_edges ee
                INNER JOIN descendant_walk dw ON ee.parent_event_uuid = dw.current_uuid
                WHERE ee.session_id = ? {depth_clause}
            )
            SELECT current_uuid FROM descendant_walk
        """
        descendant_params: list[Any] = [uuid, session_id]
        rows = cursor.execute(descendant_sql, descendant_params).fetchall()
        result_uuids.update(row[0] for row in rows)

    if not result_uuids:
        return []

    # Fetch event rows for all collected UUIDs, applying optional filters
    placeholders = ",".join("?" * len(result_uuids))
    fetch_query = f"""
        SELECT e.*, sf.filepath
        FROM events e
        JOIN source_files sf ON e.source_file_id = sf.id
        WHERE e.uuid IN ({placeholders})
          AND e.session_id = ?
    """
    fetch_params: list[Any] = list(result_uuids) + [session_id]

    if project_id:
        fetch_query += " AND e.project_id = ?"
        fetch_params.append(project_id)
    if event_types:
        et_placeholders = ",".join("?" * len(event_types))
        fetch_query += f" AND e.msg_kind IN ({et_placeholders})"
        fetch_params.extend(event_types)
    if since:
        since_dt = parse_time_filter(since)
        if since_dt:
            fetch_query += " AND e.timestamp >= ?"
            fetch_params.append(since_dt.isoformat())
    if until:
        until_dt = parse_time_filter(until)
        if until_dt:
            fetch_query += " AND e.timestamp <= ?"
            fetch_params.append(until_dt.isoformat())

    fetch_query += " ORDER BY e.timestamp"
    if result_limit is not None:
        fetch_query += f" LIMIT {result_limit}"

    event_rows = cursor.execute(fetch_query, fetch_params).fetchall()

    results: list[dict[str, Any]] = []
    for row in event_rows:
        if detail == "full":
            event: dict[str, Any] = dict(row)
            if event.get("raw_json"):
                try:
                    event["message_json"] = json.loads(event["raw_json"])
                except json.JSONDecodeError:
                    event["message_json"] = None
        else:
            # "normal": return key fields only — no raw_json, no message_content_json
            r = row
            content: Any = r["message_content"]
            if r["message_content_json"]:
                try:
                    content = json.loads(r["message_content_json"])
                except json.JSONDecodeError:
                    pass
            event = {
                "uuid": r["uuid"],
                "parent_uuid": r["parent_uuid"],
                "event_type": r["event_type"],
                "msg_kind": r["msg_kind"],
                "timestamp": r["timestamp"],
                "model_id": r["model_id"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "cache_read_tokens": r["cache_read_tokens"],
                "cache_creation_tokens": r["cache_creation_tokens"],
                "token_rate": r["token_rate"],
                "billable_tokens": r["billable_tokens"],
                "total_cost_usd": r["total_cost_usd"],
                "role": r["message_role"],
                "content": content,
                "agent_id": r["agent_id"],
                "agent_slug": r["agent_slug"],
                "filepath": r["filepath"],
                "line_number": r["line_number"],
            }
        results.append(event)

    return results


def cmd_trajectory(
    cache: CacheManager,
    session_id: str,
    project_id: str | None = None,
    start_uuid: str | None = None,
    end_uuid: str | None = None,
    event_types: list[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Iterate through a session's event trajectory."""
    ensure_cache(cache)
    cursor = cache.conn.cursor()

    query = """
        SELECT e.*, sf.filepath
        FROM events e
        JOIN source_files sf ON e.source_file_id = sf.id
        WHERE e.session_id = ?
    """
    params: list[Any] = [session_id]

    if project_id:
        query += " AND e.project_id = ?"
        params.append(project_id)

    if event_types:
        placeholders = ",".join("?" * len(event_types))
        query += f" AND e.msg_kind IN ({placeholders})"
        params.extend(event_types)

    query += " ORDER BY e.timestamp"

    results = cursor.execute(query, params).fetchall()
    events = [dict(row) for row in results]

    # Apply UUID range
    if start_uuid:
        start_idx = next((i for i, e in enumerate(events) if e.get("uuid") == start_uuid), 0)
        events = events[start_idx:]

    if end_uuid:
        end_idx = next(
            (i for i, e in enumerate(events) if e.get("uuid") == end_uuid), len(events) - 1
        )
        events = events[: end_idx + 1]

    if limit:
        events = events[:limit]

    # Parse message JSON and enrich with cost fields
    for event in events:
        if event.get("raw_json"):
            try:
                event["message_json"] = json.loads(event["raw_json"])
            except json.JSONDecodeError:
                event["message_json"] = None

    return events


# ============================================================================
# Utility Functions
# ============================================================================


def parse_time_filter(time_str: str) -> datetime | None:
    """Parse a time filter string into a datetime."""
    if not time_str:
        return None

    time_str = time_str.strip()

    match = re.match(r"^(\d+)([mhdw])$", time_str)
    if match:
        value = int(match.group(1))
        unit = match.group(2)

        now = datetime.now(UTC)
        if unit == "m":
            delta = timedelta(minutes=value)
        elif unit == "h":
            delta = timedelta(hours=value)
        elif unit == "d":
            delta = timedelta(days=value)
        elif unit == "w":
            delta = timedelta(weeks=value)
        else:
            return None

        return now - delta

    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_output(data: Any, output_format: str = "table") -> str:
    """Format output data for display."""
    if output_format == "json":
        return json.dumps(data, indent=2, default=str)

    if output_format == "jsonl":
        if isinstance(data, dict):
            return json.dumps(data, default=str)
        return "\n".join(json.dumps(row, default=str) for row in data)

    # Table format
    if not data:
        return "No results found."

    if isinstance(data, dict):
        data = [data]

    if not data:
        return "No results found."

    columns = list(data[0].keys())

    widths = {}
    for col in columns:
        widths[col] = max(
            len(str(col)),
            max(len(str(row.get(col, ""))[:50]) for row in data),
        )

    lines = []
    header = " | ".join(str(col).ljust(widths[col])[:50] for col in columns)
    lines.append(header)
    lines.append("-" * len(header))

    for row in data:
        line = " | ".join(str(row.get(col, ""))[:50].ljust(widths[col]) for col in columns)
        lines.append(line)

    return "\n".join(lines)


# ============================================================================
# CLI Interface
# ============================================================================


def main(
    args: argparse.Namespace,
    cache: CacheManager | None = None,
    projects_path: Path | None = None,
    _cwd: Path | None = None,
) -> None:
    """Main entry point.

    Args:
        args: Parsed command line arguments.
        cache: Optional CacheManager instance for dependency injection (used in testing).
        projects_path: Optional projects path override (used in testing).
        _cwd: Override for current working directory (used in testing).
    """
    owns_cache = cache is None
    if owns_cache:
        cache = CacheManager()
    assert cache is not None  # Type narrowing for mypy

    if projects_path is None:
        projects_path = PROJECTS_PATH

    try:
        result: Any = None

        # Handle automatic cache management for non-cache commands
        # Cache commands manage the cache explicitly, so skip auto-update for them
        is_cache_command = args.command == "cache"
        cache_frozen = getattr(args, "cache_frozen", False)
        cache_rebuild = getattr(args, "cache_rebuild", False)

        if not is_cache_command:
            if cache_rebuild:
                # Wipe and rebuild from scratch
                log.info("Rebuilding cache from scratch (--cache-rebuild)...")
                cache.init_schema()
                cache.clear()
                cache.update(projects_path)
            elif not cache_frozen:
                # Default: incremental update (check staleness)
                ensure_cache(cache, projects_path)
                update_result = cache.update(projects_path)
                if update_result.get("files_updated", 0) > 0:
                    log.info(
                        "Cache updated: %d files processed",
                        update_result.get("files_updated", 0),
                    )
            # If cache_frozen, skip all cache updates

        # Infer --project from CWD when not explicitly specified.
        # Skip for cache commands: they manage the schema itself and don't filter by project.
        if args.command != "cache" and not getattr(args, "project", None):
            inferred = infer_project_id(cache, cwd=_cwd)
            if inferred:
                log.info("Inferred project_id from CWD: %s", inferred)
                args.project = inferred

        # Cache commands
        if args.command == "cache":
            if args.cache_command == "init":
                result = cmd_cache_init(cache)
            elif args.cache_command == "clear":
                result = cmd_cache_clear(cache)
            elif args.cache_command == "rebuild":
                result = cmd_cache_rebuild(cache, projects_path)
            elif args.cache_command == "update":
                result = cmd_cache_update(cache, projects_path)
            elif args.cache_command == "status":
                result = cmd_cache_status(cache)

        # Query commands
        elif args.command == "projects":
            result = cmd_projects(cache)

        elif args.command == "project-id":
            result = cmd_project_id(cache, args.session_id)

        elif args.command == "sessions":
            sessions_project_id = args.project_id or args.project
            if not sessions_project_id:
                log.error(
                    "sessions requires a project_id. "
                    "Provide it as a positional argument or run from the project directory."
                )
                raise SystemExit(1)
            result = cmd_sessions(
                cache,
                sessions_project_id,
                limit=args.limit,
                since=args.since,
            )

        elif args.command == "search":
            result = cmd_search(
                cache,
                args.pattern,
                project_id=args.project,
                event_types=args.types,
                limit=args.limit,
                since=getattr(args, "since", None),
            )

        elif args.command == "traverse":
            result = cmd_traverse(
                cache,
                args.session_id,
                getattr(args, "uuid", None),
                direction=args.direction,
                project_id=args.project,
                depth_limit=args.depth,
                event_types=getattr(args, "types", None),
                since=getattr(args, "since", None),
                until=getattr(args, "until", None),
                result_limit=args.limit,
                detail=args.detail,
                all_events=args.all,
                summary=args.summary,
                offset=getattr(args, "offset", 0),
                include_content=not getattr(args, "no_content", False),
            )

        else:
            log.error(f"Unknown command: {args.command}")
            return

        print(format_output(result, args.format))

    except Exception as e:
        log.exception(f"Error: {e}")
        raise SystemExit(1) from e
    finally:
        if owns_cache:
            cache.close()


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(f"""\
        {SCRIPT_NAME} - Query and analyze Claude Code session logs with SQLite cache.

        Session files are stored at:
            ~/.claude/projects/{{project-path-kebab-cased}}/{{session_uuid}}.jsonl

        Cache is stored at:
            {CACHE_DB_PATH}

        Examples:
            uv run {SCRIPT_NAME}.py cache init             # Initialize cache
            uv run {SCRIPT_NAME}.py cache update           # Incremental update
            uv run {SCRIPT_NAME}.py cache status           # Show cache stats
            uv run {SCRIPT_NAME}.py projects               # List all projects
            uv run {SCRIPT_NAME}.py search "error"         # Full-text search
        """),
    )

    # Global options
    parser.add_argument(
        "-q",
        "--quiet",
        action="count",
        default=None,
        help="Reduce verbosity (-q ERROR, -qq CRITICAL/silent)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=None,
        help="Increase verbosity (-v INFO, -vv DEBUG)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "table", "jsonl"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "-p",
        "--project",
        help="Filter to specific project ID (speeds up queries)",
    )

    # Cache control options
    cache_group = parser.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--cache-frozen",
        action="store_true",
        help="Skip automatic cache staleness check and update",
    )
    cache_group.add_argument(
        "--cache-rebuild",
        action="store_true",
        help="Wipe and rebuild cache from scratch before query",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Cache commands
    cache_parser = subparsers.add_parser("cache", help="Manage the SQLite cache")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache commands")
    cache_subparsers.add_parser("init", help="Initialize the cache database")
    cache_subparsers.add_parser("clear", help="Clear all cached data")
    cache_subparsers.add_parser("rebuild", help="Full rebuild of the cache")
    cache_subparsers.add_parser("update", help="Incremental update (only changed files)")
    cache_subparsers.add_parser("status", help="Show cache status and statistics")

    # projects command
    subparsers.add_parser("projects", help="List all projects with session counts")

    # project-id command
    pid_parser = subparsers.add_parser("project-id", help="Resolve project ID from session ID")
    pid_parser.add_argument("session_id", help="Session UUID")

    # sessions command
    sessions_parser = subparsers.add_parser("sessions", help="List sessions for a project")
    sessions_parser.add_argument(
        "project_id",
        nargs="?",
        default=None,
        help="Project ID (kebab-cased path). Inferred from CWD when omitted.",
    )
    sessions_parser.add_argument("-n", "--limit", type=int, default=20, help="Max sessions")
    sessions_parser.add_argument("--since", help="Filter since timestamp (ISO or relative)")

    # search command
    search_parser = subparsers.add_parser("search", help="Full-text search across sessions")
    search_parser.add_argument("pattern", help="Search pattern (FTS5 syntax)")
    search_parser.add_argument(
        "-t",
        "--types",
        nargs="+",
        metavar="MSG_KIND",
        help=(
            "Filter by msg_kind. Valid values: "
            "human task_notification tool_result user_text meta "
            "assistant_text thinking tool_use other"
        ),
    )
    search_parser.add_argument("-n", "--limit", type=int, default=50, help="Max results")
    search_parser.add_argument(
        "--since", help="Filter since timestamp (ISO or relative like '30m', '1h')"
    )

    # traverse command
    traverse_parser = subparsers.add_parser("traverse", help="Traverse event tree from a UUID")
    traverse_parser.add_argument("session_id", help="Session UUID")
    traverse_parser.add_argument(
        "uuid",
        nargs="?",
        default=None,
        help="Starting event UUID (default: most recent event in session)",
    )
    traverse_parser.add_argument(
        "--direction", choices=["ancestors", "descendants", "both"], default="both"
    )
    traverse_parser.add_argument(
        "--depth",
        type=int,
        default=3,
        help="Max traversal depth (hops). 0 = unlimited. Default: 3",
    )
    traverse_parser.add_argument(
        "-t",
        "--types",
        nargs="+",
        metavar="MSG_KIND",
        help=(
            "Filter results by msg_kind: "
            "human task_notification tool_result user_text meta "
            "assistant_text thinking tool_use other"
        ),
    )
    traverse_parser.add_argument(
        "--since", help="Only events after TIME (ISO or relative: 1h, 30m)"
    )
    traverse_parser.add_argument("--until", help="Only events before TIME")
    traverse_parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=None,
        help="Max events to return (default: all)",
    )
    traverse_parser.add_argument(
        "--detail",
        choices=["normal", "full"],
        default="normal",
        help="normal=key fields only (default); full=includes raw_json and message_json",
    )
    traverse_parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help=(
            "Return all events in the session chronologically (bypasses graph traversal). "
            "Includes subagent events. Supports --types, --since, --until, -n, --offset, "
            "--detail, and --no-content."
        ),
    )
    traverse_parser.add_argument(
        "--summary",
        action="store_true",
        default=False,
        help=(
            "Return per-agent aggregated stats (event counts, token totals, accurate costs). "
            "Includes the main session (agent_id=null) and all subagents."
        ),
    )
    traverse_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip first N events (used with --all, default: 0)",
    )
    traverse_parser.add_argument(
        "--no-content",
        action="store_true",
        help="Exclude message content and role from --all output",
    )

    args = parser.parse_args()

    _net = (args.verbose or 0) - (args.quiet or 0)
    _level = (
        logging.DEBUG
        if _net >= 2
        else logging.INFO
        if _net == 1
        else logging.WARNING
        if _net == 0
        else logging.ERROR
        if _net == -1
        else logging.CRITICAL
    )
    logging.basicConfig(
        level=_level,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not args.command:
        parser.print_help()
    else:
        main(args)
