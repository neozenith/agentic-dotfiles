#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Gate the deck's authored prose on the rules a human can't be trusted to skim for.

WHY THIS EXISTS
---------------
docs/slides/CLAUDE.md distils the global-audience prose standard, and a rule that
lives only in a doc is a rule that decays. This checks the mechanical subset: the
part that is deterministic, free, and objectively decidable. It runs in `make ci`.

It deliberately does NOT judge tone, clause count, or reading grade. Those need a
reader (see CLAUDE.md "Checking it"). A gate that guesses at judgement calls
teaches people to ignore gates, so this one only fails on what it can prove.

WHAT IT CHECKS
--------------
  em-dash       U+2014 anywhere in authored prose. The hard rule.
  US spelling   a small, high-confidence list (organize, color, behavior, ...).
  exclusions    non-inclusive terms with a fitter replacement.

WHAT IT DOES NOT FLAG (deliberate false-positive control):
  - fenced code blocks and inline `code spans`: identifiers are names, not prose,
    so `color: #fff` and `fillColor` are correct as written;
  - the generated progress region, which the deck's own generator owns;
  - a line tagged `prose-check: allow`, for the case where the rule must be named
    (CLAUDE.md has to print an em-dash to ban one).

    uv run scripts/prose_check.py                 # check the deck's markdown
    uv run scripts/prose_check.py --files a.md    # check specific files
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_GLOBS = ("*.md", "assets/*.md")

EM_DASH = "—"
ALLOW = "prose-check: allow"

# Managed regions belong to their generator, not to the author.
GENERATED = re.compile(
    r"<!-- BEGIN GENERATED PROGRESS BAR.*?<!-- END GENERATED PROGRESS BAR -->",
    re.DOTALL,
)
FENCE_BLOCK = re.compile(r"^ {0,3}(`{3,}|~{3,}).*?^ {0,3}\1", re.DOTALL | re.MULTILINE)
CODE_SPAN = re.compile(r"`[^`\n]*`")

# Australian spelling. Kept short and high-confidence on purpose: a long list
# invites false positives on identifiers, and the checker would then be muted.
US_SPELLING = {
    r"\borganiz(e|es|ed|ing|ation)\b": "organis-",
    r"\bcolor(s|ed|ing)?\b": "colour",
    r"\bbehavior(s|al)?\b": "behaviour",
    r"\bnormaliz(e|es|ed|ing|ation)\b": "normalis-",
    r"\bprioritiz(e|es|ed|ing)\b": "prioritis-",
    r"\brecogniz(e|es|ed|ing)\b": "recognis-",
    r"\banalyz(e|es|ed|ing)\b": "analys-",
    r"\bcatalog(s|ed)?\b": "catalogue",
    r"\bjudgment\b": "judgement",
}

NON_INCLUSIVE = {
    r"\bwhitelist(s|ed|ing)?\b": "allow list",
    r"\bblacklist(s|ed|ing)?\b": "deny list",
    r"\bsanity check\b": "quick check",
    r"\bdummy (value|data)\b": "placeholder",
    r"\bmaster (branch|node)\b": "primary / main",
}


def strip_uncheckable(text: str) -> str:
    """Blank out what is not authored prose, preserving line numbers.

    Replacing with same-length runs of spaces (newlines kept) means a hit's line
    number still points at the real line. Deleting the regions would shift every
    number after them, and a checker that misreports a location is worse than no
    checker: it sends the reader to the wrong place.
    """

    def blank(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    text = GENERATED.sub(blank, text)
    text = FENCE_BLOCK.sub(blank, text)
    return CODE_SPAN.sub(blank, text)


def check(path: Path) -> list[tuple[int, str, str]]:
    """Return [(line_no, rule, detail)] for one file."""
    raw = path.read_text(encoding="utf-8")
    prose = strip_uncheckable(raw)
    raw_lines = raw.split("\n")
    hits: list[tuple[int, str, str]] = []

    for i, line in enumerate(prose.split("\n"), 1):
        if ALLOW in raw_lines[i - 1]:
            continue
        if EM_DASH in line:
            hits.append((i, "em-dash", "use a comma, a colon, parentheses, or split the sentence"))
        for pattern, fix in US_SPELLING.items():
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                hits.append((i, "US spelling", f"{m.group(0)!r} -> {fix}"))
        for pattern, fix in NON_INCLUSIVE.items():
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                hits.append((i, "non-inclusive", f"{m.group(0)!r} -> {fix}"))
    return hits


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--files", nargs="*", help="explicit files (default: the deck's markdown)")
    args = p.parse_args()

    here = Path(__file__).resolve().parent.parent
    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        paths = sorted({q for g in DEFAULT_GLOBS for q in here.glob(g)})

    missing = [q for q in paths if not q.exists()]
    if missing:
        print(f"error: no such file(s): {[str(m) for m in missing]}", file=sys.stderr)
        return 1

    total = 0
    for path in paths:
        for line_no, rule, detail in check(path):
            total += 1
            rel = path.relative_to(here) if path.is_relative_to(here) else path
            print(f"  {rel}:{line_no}: {rule}: {detail}", file=sys.stderr)

    if total:
        print(
            f"\n  {total} prose violation(s). The rules and their reasons are in CLAUDE.md.\n"
            f"  A line that must name a banned form can carry `{ALLOW}`.",
            file=sys.stderr,
        )
        return 1
    print(f"  prose: {len(paths)} file(s) clean", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
