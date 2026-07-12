#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Generate/update the examples README.md from .mmd + .png pairs.

For each {stem}.mmd in the examples directory (sorted alphabetically), emits:
  - ## {stem} heading
  - ### Code fence (text, for copy-paste)
  - ### Mermaid fence (live-rendered by GitHub/GitLab)
  - ### Image (PNG) link

A static footer section for Mermaid version debugging is appended after all examples.

Run from project root:
    uv run .claude/skills/mermaidjs_diagrams/scripts/_update_examples_readme.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from textwrap import dedent

log = logging.getLogger(__name__)

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

EXAMPLES_DIR = SCRIPT_DIR.parent / "resources" / "examples"
README = EXAMPLES_DIR / "README.md"

HEADER = """\
# Examples

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->
<!--TOC-->
</details>

---

"""

FOOTER = """\
## Mermaid Version Information Debugging

### Code


````
```mermaid
    info
```
````


### Mermaid

```mermaid
  info
```"""


def build_section(stem: str, content: str) -> str:
    return (
        f"## {stem}\n"
        f"\n"
        f"### Code\n"
        f"\n"
        f"```text\n{content}```\n"
        f"\n"
        f"### Mermaid\n"
        f"\n"
        f"```mermaid\n{content}```\n"
        f"\n"
        f"### Image (PNG)\n"
        f"\n"
        f"![{stem}]({stem}.png)\n"
    )


def build_readme(examples_dir: Path = EXAMPLES_DIR) -> str:
    mmds = sorted(examples_dir.glob("*.mmd"), key=lambda p: p.stem)
    if not mmds:
        raise RuntimeError(f"No .mmd files found in {examples_dir}")

    sections = [
        build_section(mmd.stem, mmd.read_text(encoding="utf-8")) for mmd in mmds
    ]
    body = "\n---\n\n".join(sections)
    return HEADER + body + "\n---\n" + FOOTER


# ============================================================================
# CLI Interface
# ============================================================================


def main(
    args: argparse.Namespace, readme: Path = README, examples_dir: Path = EXAMPLES_DIR
) -> int:
    """Regenerate the examples README from .mmd + .png pairs."""
    content = build_readme(examples_dir)
    if args.dry_run:
        log.info("DRY RUN: would write %s (%d bytes)", readme, len(content))
        return 0
    readme.write_text(content, encoding="utf-8")
    log.info("Updated %s", readme)
    return 0


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(f"""\
        {SCRIPT_NAME} — regenerate examples README from .mmd + .png pairs.

        SOURCE: {EXAMPLES_DIR}
        OUTPUT: {README}
        """),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Errors only")
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be written without writing",
    )
    parsed = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG
        if parsed.verbose
        else logging.ERROR
        if parsed.quiet
        else logging.INFO,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    sys.exit(main(parsed))
