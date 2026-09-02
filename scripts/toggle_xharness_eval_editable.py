#!/usr/bin/env -S uv run --no-sync python
"""Toggle pytest-xharness-eval between its PyPI release and the local editable checkout.

The script owns the block in pyproject.toml delimited by the BEGIN/END markers below.
`local` uncomments every line inside the block (activating `[tool.uv.sources]`);
`pypi` comments them out. Both are idempotent: re-running in the current state is a
no-op that exits 0. After each write the file is re-parsed with tomllib and the
presence/absence of the source entry is asserted, so a botched edit fails loudly
rather than being discovered by `uv sync`.

Stdlib only (Tier B) -- it must run before `uv sync` has any environment to offer.

Usage:
    uv run --no-sync scripts/toggle_xharness_eval_editable.py local
    uv run --no-sync scripts/toggle_xharness_eval_editable.py pypi
    uv run --no-sync scripts/toggle_xharness_eval_editable.py status
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

PACKAGE = "pytest-xharness-eval"
BEGIN = "# --- BEGIN xharness-eval-source (managed) ---"
END = "# --- END xharness-eval-source (managed) ---"
COMMENT = "# "

# Scripts live in <repo>/scripts/; pyproject.toml is one level up.
DEFAULT_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


class ToggleError(RuntimeError):
    """Raised when pyproject.toml is not in a shape this script can manage."""


def _split(text: str) -> tuple[list[str], list[str], list[str]]:
    """Split file lines into (before, managed, after) around the marker pair.

    Markers are excluded from `managed` and re-emitted by `_join`.
    """
    lines = text.splitlines(keepends=True)
    begins = [i for i, line in enumerate(lines) if line.rstrip("\n") == BEGIN]
    ends = [i for i, line in enumerate(lines) if line.rstrip("\n") == END]
    if len(begins) != 1 or len(ends) != 1:
        raise ToggleError(
            f"expected exactly one BEGIN and one END marker, found {len(begins)} and {len(ends)}"
        )
    b, e = begins[0], ends[0]
    if e <= b:
        raise ToggleError("END marker appears before BEGIN marker")
    return lines[: b + 1], lines[b + 1 : e], lines[e:]


def _join(before: list[str], managed: list[str], after: list[str]) -> str:
    return "".join(before) + "".join(managed) + "".join(after)


def _is_commented(line: str) -> bool:
    return line.startswith(COMMENT) or line.rstrip("\n") == COMMENT.rstrip()


def _comment(line: str) -> str:
    if line.strip() == "" or _is_commented(line):
        return line
    return COMMENT + line


def _uncomment(line: str) -> str:
    if line.startswith(COMMENT):
        return line[len(COMMENT) :]
    return line


def current_state(text: str) -> str:
    """Return 'local' if the managed block is active, 'pypi' if fully commented out."""
    _, managed, _ = _split(text)
    content = [line for line in managed if line.strip()]
    if not content:
        raise ToggleError("managed block is empty")
    if all(_is_commented(line) for line in content):
        return "pypi"
    if not any(_is_commented(line) for line in content):
        return "local"
    raise ToggleError("managed block is partially commented; fix it by hand")


def _verify(text: str, expect: str) -> None:
    """Parse the TOML and assert the source entry matches the intended state."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as err:
        raise ToggleError(f"pyproject.toml no longer parses: {err}") from err
    sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    entry = sources.get(PACKAGE)
    if expect == "local":
        if not (isinstance(entry, dict) and entry.get("editable") is True and "path" in entry):
            raise ToggleError(f"expected an editable path source for {PACKAGE}, got {entry!r}")
    elif entry is not None:
        raise ToggleError(f"expected no source for {PACKAGE}, got {entry!r}")


def toggle(path: Path, target: str) -> bool:
    """Rewrite `path` so the managed block is in `target` state. Returns True if changed."""
    text = path.read_text(encoding="utf-8")
    if current_state(text) == target:
        _verify(text, target)
        return False
    before, managed, after = _split(text)
    transform = _uncomment if target == "local" else _comment
    new_text = _join(before, [transform(line) for line in managed], after)
    _verify(new_text, target)
    path.write_text(new_text, encoding="utf-8")
    return True


def cmd_toggle(args: argparse.Namespace) -> None:
    changed = toggle(args.pyproject, args.target)
    verb = "switched to" if changed else "already"
    print(f"{PACKAGE}: {verb} {args.target} ({args.pyproject})")


def cmd_status(args: argparse.Namespace) -> None:
    state = current_state(args.pyproject.read_text(encoding="utf-8"))
    print(state)


def build_parser() -> argparse.ArgumentParser:
    def _help(p: argparse.ArgumentParser):
        def _print_help(_: argparse.Namespace) -> None:
            p.print_help()

        return _print_help

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=DEFAULT_PYPROJECT,
        help=f"pyproject.toml to edit (default: {DEFAULT_PYPROJECT})",
    )
    parser.set_defaults(func=_help(parser))
    sub = parser.add_subparsers(dest="cmd", required=False)

    local = sub.add_parser("local", help="Use the editable ../pytest-xharness-eval checkout")
    local.set_defaults(func=cmd_toggle, target="local")

    pypi = sub.add_parser("pypi", help="Use the published PyPI release")
    pypi.set_defaults(func=cmd_toggle, target="pypi")

    sub.add_parser("status", help="Print 'local' or 'pypi'").set_defaults(func=cmd_status)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except (ToggleError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
