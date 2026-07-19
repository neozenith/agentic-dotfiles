#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Scaffold a self-contained Marp deck: build automation, theme, and reference deck.

The deck it writes depends on nothing outside its own directory. The three helper
scripts are COPIED in beside it rather than referenced here, so the deck keeps
building after this skill is gone, and a consumer can edit them without editing a
skill. That is the whole point of the layout, not an implementation detail.

Theme colours come from a design-tokens JSON when the project has one, so the deck
and the product read as one system. Without `--tokens`, a neutral placeholder
palette is written and the deck says so.

    uv run scaffold_deck.py --out docs/slides
    uv run scaffold_deck.py --out docs/slides --tokens frontend/src/design-tokens.json
    uv run scaffold_deck.py --out docs/slides --tiers my-tiers.toml
    uv run scaffold_deck.py --out docs/slides --name product-pitch --force
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
from pathlib import Path
from typing import TextIO

import tier_progress

# ── Configuration ───────────────────────────────────────────────────────

SCRIPT = Path(__file__)
SCRIPT_DIR = SCRIPT.parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent
DECK_TEMPLATE = SKILL_DIR / "assets" / "deck"

# Copied into the scaffolded deck's scripts/. These are the skill's own tools AND
# the deck's: one source, so a fix here reaches both.
HELPER_SCRIPTS = ("tier_progress.py", "slide_durations.py", "prose_check.py")

# Placeholder palette, used when no design tokens are supplied. Deliberately
# obvious: a reader must see that it is a default, not a brand.
FALLBACK_TOKENS = {
    "bg": "#1b1b1f",
    "surface": "#26262b",
    "border": "#3c3c44",
    "fg": "#e8e8ea",
    "muted": "#9b9ba3",
    "accent": "#7aa2f7",
    "onAccent": "#1b1b1f",
    "radius": "12px",
    "fontDisplay": "system-ui, sans-serif",
    "fontMono": "ui-monospace, monospace",
}


class ScaffoldError(RuntimeError):
    """A precondition the caller must fix."""


# ── Core ─────────────────────────────────────────────────────────────────


def read_tokens(path: Path | None) -> tuple[dict[str, str], str]:
    """Return (palette, provenance). A named tokens file that cannot be read is fatal.

    Silently falling back to placeholders would ship a deck in the wrong brand and
    look deliberate. The caller asked for these tokens; failing loudly is the only
    honest answer.
    """
    if path is None:
        return dict(FALLBACK_TOKENS), "placeholder palette (no --tokens given)"
    if not path.exists():
        raise ScaffoldError(f"no design tokens at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    themes = data.get("themes", {})
    theme = themes.get("dark") or themes.get(data.get("defaultTheme", "light")) or {}
    if not theme:
        raise ScaffoldError(f"{path} has no themes.dark or themes.<defaultTheme> block to read")
    fonts = data.get("fonts", {})
    palette = dict(FALLBACK_TOKENS)
    for key in ("bg", "surface", "border", "fg", "muted", "accent", "onAccent", "radius"):
        if key in theme:
            palette[key] = theme[key]
    if "display" in fonts:
        palette["fontDisplay"] = fonts["display"]
    if "mono" in fonts:
        palette["fontMono"] = fonts["mono"]
    return palette, f"design tokens from {path}"


def render_template(text: str, mapping: dict[str, str]) -> str:
    """Substitute {{KEY}} placeholders. An unresolved placeholder is a bug, not a gap."""
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    left = [line for line in text.split("\n") if "{{" in line and "}}" in line]
    if left:
        raise ScaffoldError(f"template still holds unresolved placeholders: {left[:3]}")
    return text


def mapping_for(name: str, palette: dict[str, str], provenance: str) -> dict[str, str]:
    # TOKEN_FONTDISPLAY_BARE exists for Mermaid's `init` block, and only for that.
    # A font token is normally written `'Family', fallback` and carries its own
    # quotes, which CSS and SVG both accept. Mermaid's init parser is not strict
    # JSON: the nested quotes end the string early, it discards the ENTIRE init,
    # and the diagram renders in default colours while reporting success. Verified
    # by rendering, because nothing in the toolchain says a word about it.
    bare_font = palette["fontDisplay"].replace("'", "").replace('"', "")
    return {
        "DECK_NAME": name,
        "THEME_NAME": name,
        "PALETTE_PROVENANCE": provenance,
        "TOKEN_FONTDISPLAY_BARE": bare_font,
        **{f"TOKEN_{k.upper()}": v for k, v in palette.items()},
    }


def retag_deck(path: Path, names: list[str]) -> None:
    """Rewrite a starter deck's @tier markers to span the configured tiers.

    Both starter decks ship tagged with the template's own tier names, which are
    wrong the moment a project declares different audiences. Their markers exist
    only to demonstrate the bar, so the names carry no meaning and are derivable:
    spread the slides evenly across whatever the tier config declares, in order.

    Without this, a project that supplies its own tiers gets two decks that fail
    their own build before it has written a slide.
    """
    markers = list(tier_progress._TIER_MARKER.finditer(path.read_text(encoding="utf-8")))
    if not markers:
        return
    text = path.read_text(encoding="utf-8")
    # Rewrite right-to-left so earlier match offsets stay valid.
    for i, m in reversed(list(enumerate(markers))):
        tier = names[i * len(names) // len(markers)]
        text = text[: m.start()] + f"<!-- @tier {tier} -->" + text[m.end() :]
    path.write_text(text, encoding="utf-8")


def scaffold(
    out: Path,
    name: str,
    tokens: Path | None,
    tiers: Path | None = None,
    force: bool = False,
    log: TextIO = sys.stderr,
) -> int:
    if not DECK_TEMPLATE.is_dir():
        raise ScaffoldError(f"deck template missing at {DECK_TEMPLATE}")
    if out.exists() and any(out.iterdir()) and not force:
        raise ScaffoldError(f"{out} exists and is not empty. Pass --force to overwrite its files.")

    palette, provenance = read_tokens(tokens)
    mapping = mapping_for(name, palette, provenance)

    written: list[Path] = []
    for src in sorted(p for p in DECK_TEMPLATE.rglob("*") if p.is_file()):
        rel = src.relative_to(DECK_TEMPLATE)
        # theme.css is named for the deck so a project can hold two decks without
        # their themes colliding in Marp's registry.
        dest = out / (rel.parent / f"{name}.css" if rel.name == "theme.css" else rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render_template(src.read_text(encoding="utf-8"), mapping), encoding="utf-8")
        written.append(dest)

    scripts_dir = out / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for helper in HELPER_SCRIPTS:
        source = SCRIPT_DIR / helper
        if not source.exists():
            raise ScaffoldError(f"helper script {source} is missing from the skill")
        shutil.copy2(source, scripts_dir / helper)
        written.append(scripts_dir / helper)

    for path in written:
        print(f"  wrote {path}", file=log)

    # Generate each deck's progress bar now, so the scaffold is born green. The
    # deck's own `make ci` asserts the committed block matches the markers, and a
    # scaffold that fails that gate on its first run teaches the consumer to
    # distrust the gate before they have written a single slide.
    tiers_file = out / "tiers.toml"
    if tiers is not None:
        # A project that knows its audiences supplies them here, and BOTH starter
        # decks are retagged to match. Editing tiers.toml after the fact instead
        # means retagging the markers by hand: the names are the deck's own text.
        if not tiers.exists():
            raise ScaffoldError(f"no tier config at {tiers}")
        tier_progress.load_tiers(tiers)  # validate before overwriting the default
        shutil.copy2(tiers, tiers_file)
    names = [t["name"] for t in tier_progress.load_tiers(tiers_file)]
    for deck in sorted(out.glob("*.md")):
        retag_deck(deck, names)
    for deck in sorted(out.glob("*.md")):
        if tier_progress.build(deck, tiers_file, out=io.StringIO()) != 0:
            raise ScaffoldError(f"generated deck {deck} failed its own tier check; the template is broken")

    print(
        f"\n  {len(written)} files, both decks tier-synced. Theme palette: {provenance}."
        f"\n  Next: make -C {out} template   # the layout reference"
        f"\n        make -C {out} html       # build the deck",
        file=log,
    )
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────


def main(args: argparse.Namespace) -> int:
    try:
        return scaffold(
            Path(args.out),
            args.name,
            Path(args.tokens) if args.tokens else None,
            tiers=Path(args.tiers) if args.tiers else None,
            force=args.force,
        )
    except (ScaffoldError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="directory to scaffold the deck into (e.g. docs/slides)")
    parser.add_argument("--name", default="deck", help="artifact basename and theme name (default: deck)")
    parser.add_argument("--tokens", help="design-tokens JSON to take the palette from")
    parser.add_argument("--tiers", help="tier config to use instead of the default (retags both starter decks)")
    parser.add_argument("--force", action="store_true", help="overwrite files in a non-empty target")
    raise SystemExit(main(parser.parse_args()))
