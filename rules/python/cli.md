# Python CLI Conventions

Rules for building argparse-based CLIs in this project.

## Library Choice

Use **`argparse`** (stdlib). Do not introduce `click` or `typer`.

## Subcommand Structure

Every command group that has subcommands uses the same three-line pattern:

```python
group_parser = parent_sub.add_parser("group", help="...")
group_parser.set_defaults(func=_help(group_parser))   # show help when no subcommand given
group_sub = group_parser.add_subparsers(dest="group_cmd", required=False)
```

Key rules:
- `required=False` — allows `parse_args()` to return without a subcommand, so the help handler fires instead of argparse printing an error and exiting.
- `set_defaults(func=_help(group_parser))` — the fallback handler for when no subcommand is chosen. It is automatically overridden by any leaf subcommand's own `set_defaults(func=real_handler)`.
- This pattern applies to every level of nesting, including the top-level parser.

## The `_help` Closure

Define `_help` as a local function inside `build_parser`. It captures the specific parser by reference so each group prints its own relevant help, not the top-level help.

```python
def _help(p: argparse.ArgumentParser):
    """Return a handler that prints help for parser p (used as the default func)."""

    def _print_help(_: argparse.Namespace) -> None:
        p.print_help()

    return _print_help
```

## Leaf Subcommand Registration

Every leaf command binds its handler via `set_defaults(func=...)`. This overrides any `_help` default inherited from parent parsers.

```python
sub = group_sub.add_parser("action", help="...")
sub.add_argument("--foo", ...)
sub.set_defaults(func=cmd_action)
```

## Dispatch in `main()`

`main()` calls `args.func(args)` unconditionally. This works because:
- Leaf subcommands set `func` to a real handler.
- Incomplete paths set `func` to `_help(parser)` via the parent's `set_defaults`.
- The top-level parser also has `set_defaults(func=_help(parser))` so `cli --env dev` (no command) shows top-level help.

```python
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    # ... logging setup ...
    args.func(args)
```

## Visibility Verb Convention

Read-only subcommands that display current state use **`status`** as their subcommand name (not `show`, `stats`, `info`, etc.):

```python
group_sub.add_parser("status", help="Show current state of X").set_defaults(func=cmd_X_status)
```

Destructive or write subcommands use imperative verbs: `reset`, `init`, `set`, `seed`, `enable`, `disable`.

## Module Layout

```
cli/
├── app.py              # build_parser() + main() only — no business logic
├── commands/
│   ├── dynamodb.py     # DynamoDB-backed commands (watermarks, jobs, config, dedup, tokens)
│   ├── scheduler.py    # EventBridge Scheduler commands
│   ├── s3.py           # S3 data plane commands
│   ├── s3_completeness.py
│   ├── invoke.py       # Lambda invocation
│   ├── logs.py         # CloudWatch log tailing
│   └── backfiller.py   # Bulk backfill orchestration
├── config.py           # CODE_DEFAULTS and CLI-level config helpers
├── formatting.py       # date_arg, datetime_or_date_arg, display helpers
└── logging_formatter.py
```

`app.py` imports command functions and wires them to parsers. All business logic lives in `commands/`.
