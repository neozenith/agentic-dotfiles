# hooks/

`PreToolUse` hooks that keep an agent's working state visible and auditable.

One hook ships here: **`tool_coach.py`**. It reads the PreToolUse event on
stdin and, when a tool call breaks one of this repo's working agreements,
returns a `deny` decision whose *reason* is a coaching message saying what to
do instead. A plain "permission denied" teaches nothing and invites the model
to retry near-miss variants; a redirect ends the loop in one turn.

## Install

```jsonc
// .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit|NotebookEdit|Read",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/tool_coach.py\"",
            "timeout": 10,
            "statusMessage": "Checking the call against this project's working agreements…"
          }
        ]
      }
    ]
  }
}
```

Stdlib only, so there is nothing to install and no virtualenv to resolve on
every call.

## What it checks

| Check | Kind | Applies to |
|-------|------|------------|
| No deletions | structural | Bash |
| No out-of-project scratch space | structural | Bash, Write, Edit, NotebookEdit, Read |
| Tool-choice coaching | pattern rules | Bash |

**Structural checks** live in `tool_coach.py`. They parse the command into
argv segments with `shlex`, so they still fire on wrapped and indirect forms a
regex misses: `sudo`, `xargs`, an absolute `/bin/` path, an env-var prefix, a
pipeline, `git rm`, `find -delete`.

- *No deletions.* A deleted file leaves no evidence of what was discarded or
  why. The redirect is to move it under the project-local `tmp/_archived/`.
- *No out-of-project scratch space.* System temp roots and any `scratchpad/`
  outside the project cannot be inspected or diffed alongside the change they
  support. The redirect is the project-local `tmp/`. Ordinary system paths
  (`/usr/bin/env`, `/dev/null`) are left alone.

**Pattern rules** live in `tool_coach_rules.json`: a list of `{name, pattern,
message}` objects, matched in order against the Bash command, first match
wins. Add or edit a rule there; no code change needed. The shipped set covers
inline `-c` snippets, bare interpreters, manual import-path injection and the
wall-clock timer binary. Each redirects to the `uv` or Bash-tool equivalent.

## Heredoc bodies are not scanned

A heredoc body is data being written, not a command being run. Scanning it
produces pure false positives: writing *documentation about* a blocked command
gets blocked by the very rule the documentation describes, which is exactly
what happened while authoring this directory. `strip_heredocs()` removes those
bodies before any check runs.

Command lines around and after a heredoc are still checked.

## Failure behaviour

Fail **loud**, never open. A missing or malformed rules file prints one line
to stderr and exits 1, which the hook contract treats as a non-blocking error:
the model sees the message, the call proceeds, and the breakage stays visible
until it is fixed. A guard that silently disables itself is worse than no
guard.

## Tests

```sh
make hooks-test
```

52 cases, no mocks, real payloads through the real decision path. Some command
fixtures are written as two adjacent string literals that Python concatenates
(`"echo x |" " rm y"`) so that authoring the test file does not trip the hook
it tests. Those comments are load-bearing; do not tidy them away.
