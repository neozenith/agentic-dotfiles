#!/usr/bin/env python3
"""
Universal diagram infrastructure setup for Mermaid.js diagrams.
Works for ANY project - creates standard structure.

Usage:
    python .claude/scripts/setup_diagrams.py
    uv run .claude/scripts/setup_diagrams.py
"""

import sys
from pathlib import Path

MAKEFILE_TEMPLATE = """# When a MermaidJS source file (*.mmd) is updated, generate a corresponding PNG file.
%.png: %.mmd
\tnpx -p @mermaid-js/mermaid-cli mmdc --input $< --output $@ --theme default --backgroundColor white --scale 4

# A top level target to mark that all diagrams have a correpsonding png that should exist if it doesn't already.
diagrams: $(patsubst %.mmd,%.png,$(wildcard *.mmd))
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


def setup_diagrams_infrastructure():
    """Create docs/diagrams infrastructure if missing. 
    
    Returns list of existing .mmd files or empty list for new setup.
    """
    # Create directory
    diagrams_dir = Path("docs/diagrams")
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


def main():
    """Main entry point"""
    print("🚀 Setting up Mermaid.js diagram infrastructure...\n")

    try:
        mmd_files, diagrams_dir = setup_diagrams_infrastructure()
        return 0
    except Exception as e:
        print(f"\n❌ Error during setup: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
