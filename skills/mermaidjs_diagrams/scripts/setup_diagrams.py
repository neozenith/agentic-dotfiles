#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Universal diagram infrastructure setup for Mermaid.js diagrams.
Works for ANY project - creates standard structure.

Usage:
    python .claude/skills/mermaidjs_diagrams/scripts/setup_diagrams.py
    uv run .claude/skills/mermaidjs_diagrams/scripts/setup_diagrams.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# =============================================================================
# Script Metadata
# =============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

MAKEFILE_TEMPLATE = """# Flowchart diagrams use Font Awesome icons (fa:fa-icon syntax) — no icon packs needed.
# Only set ICON_PACKS if you are rendering architecture-beta diagrams with Iconify icons.
# Override at the command line: make diagrams ICON_PACKS="@iconify-json/logos @iconify-json/mdi"
ICON_PACKS ?=

# Build the --iconPacks flag only when ICON_PACKS is non-empty
ICON_PACK_FLAG = $(if $(strip $(ICON_PACKS)),--iconPacks $(ICON_PACKS),)

# When a MermaidJS source file (*.mmd) is updated, generate a corresponding PNG file.
%.png: %.mmd
\tnpx -p @mermaid-js/mermaid-cli mmdc \\
\t\t--input $< \\
\t\t--output $@ \\
\t\t--theme default \\
\t\t--backgroundColor white \\
\t\t--scale 4 \\
\t\t$(ICON_PACK_FLAG)

# A top level target to mark that all diagrams have a corresponding png that should exist if it doesn't already.
diagrams: $(patsubst %.mmd,%.png,$(wildcard *.mmd))

all: diagrams

.PHONY: diagrams all
"""

GITATTRIBUTES_CONTENT = """# Treat PNG diagrams as binary files
*.png binary
"""

README_TEMPLATE = """# Project Diagrams

This directory contains Mermaid.JS source files and generated PNG diagrams.

## Generating Diagrams

Generate all diagrams:

```bash
make diagrams
```
Or when running from project root:

```bash
make -C docs/diagrams diagrams
# OR simply
make -C docs/diagrams # Defaults to 'all' target which depends on 'diagrams'
```

Generate a specific diagram:
```bash
make diagram-name.png
```

## Maintenance

When updating diagrams:
1. Edit the `.mmd` source file
2. Run `make diagrams` to regenerate PNGs
3. Commit both `.mmd` and `.png` files

The diagrams use Mermaid.JS flowchart syntax. See [Mermaid documentation](https://mermaid.js.org/intro/) for reference.
"""


def create_file_from_template(path: Path, content: str, description: str | None = None) -> bool:
    """Create file from template if it doesn't exist. Returns True if created."""
    name = description or path.name
    if not path.exists():
        path.write_text(content)
        print(f"✅ Created {name}")
        return True
    else:
        print(f"✓  {name} already exists")
        return False


def setup_diagrams_infrastructure(target_folder: Path | None = None) -> tuple[list[Path], Path]:
    """Create diagram infrastructure if missing.

    Returns list of existing .mmd files or empty list for new setup.
    """
    # Create directory
    diagrams_dir = target_folder or Path("docs/diagrams")
    if not diagrams_dir.exists():
        diagrams_dir.mkdir(parents=True)
        print(f"✅ Created directory: {diagrams_dir}")
    else:
        print(f"✓  Directory exists: {diagrams_dir}")

    # Create files from templates
    create_file_from_template(diagrams_dir / "Makefile", MAKEFILE_TEMPLATE)
    create_file_from_template(diagrams_dir / ".gitattributes", GITATTRIBUTES_CONTENT)
    create_file_from_template(diagrams_dir / "README.md", README_TEMPLATE)

    # Verify tabs in Makefile
    makefile_content = (diagrams_dir / "Makefile").read_text()
    if "\tnpx" not in makefile_content:
        print("⚠️  Warning: Makefile may not have proper tabs (should use \\t not spaces)")

    print(f"\n✅ Setup complete! Diagram directory: {diagrams_dir}")
    print("\nNext steps:")
    # List existing diagrams
    mmd_files = list(diagrams_dir.glob("*.mmd"))
    if mmd_files:
        print("\t1. You should check each diagram is an up-to-date depiction of your project.")
        for mmd_file in sorted(mmd_files):
            print(f"\t\t- {mmd_file.name}")

    else:
        print("\n📊 No existing .mmd diagrams found")
        print("\t1. Create .mmd files in docs/diagrams/ depicting your project's architecture to get started")

    print("2. Run 'make -C docs/diagrams diagrams' to (re)generate PNGs")
    return mmd_files, diagrams_dir


def main() -> int:
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Set up Mermaid.js diagram infrastructure.")
    parser.add_argument(
        "--target-folder",
        type=Path,
        default=None,
        help="Target directory to create (default: docs/diagrams)",
    )
    args = parser.parse_args()

    print("🚀 Setting up Mermaid.js diagram infrastructure...\n")

    try:
        mmd_files, diagrams_dir = setup_diagrams_infrastructure(args.target_folder)
        return 0
    except Exception as e:
        print(f"\n❌ Error during setup: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
