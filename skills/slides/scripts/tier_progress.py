#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Derive a deck's audience-tier progress bar from per-slide `@tier` markers.

A deck aimed at layered audiences (each dropping off after their section) wants a
bar showing which tier is being addressed and how far through it the deck is.
Hand-maintaining that means a fraction per slide, retuned whenever a slide moves.
It rots silently: the deck still renders, the bar just lies.

So each slide carries ONE marker naming its audience, an HTML comment wrapping
`@tier <name>`, and this derives the rest. It writes a managed <style> block into
the deck (between BEGIN/END sentinels) holding:

  * one `--p` rule per slide, where
        p = (tier_index + (i + 1) / n) / tier_count
    for the i-th (0-based) slide of a tier holding n slides;
  * the segmented gradient that paints the bar, computed for the CONFIGURED tier
    count. The theme owns the bar's geometry; this owns its segments. That split
    is what lets a project pick its own tiers without editing any CSS.

Rules key on `section[id="N"]`: Marp numbers slides in document order and emits
that id. The attribute selector is required because an id starting with a digit
is not a valid CSS ident (`section#3` would need escaping as `#\\33 `).

Writing back into the deck (rather than a separate CSS file) keeps the deck a
self-contained artifact: plain `marp deck.md` renders the bar with no plumbing,
and the committed block means a fresh clone is correct before anything is run.

Validation is loud: an unknown tier, tiers out of declared order, tiers
interleaved, or two markers on one slide are errors. A progress bar over a
non-monotonic deck is a lie, so no bar is emitted for one.

    uv run tier_progress.py --deck slides.md
    uv run tier_progress.py --deck slides.md --check    # writes nothing; exit 1 if stale
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path
from typing import TextIO

# ── Configuration ───────────────────────────────────────────────────────

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem

DEFAULT_DECK = "slides.md"
DEFAULT_TIERS = "tiers.toml"

# Managed-region sentinels. Everything between them is generated and overwritten;
# everything outside is hand-authored and never touched.
BEGIN = "<!-- BEGIN GENERATED PROGRESS BAR: `make progress` writes this; do not hand-edit -->"
END = "<!-- END GENERATED PROGRESS BAR -->"

_FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
_SLIDE_BREAK = re.compile(r"---[ \t]*\r?$")
# A fence opener/closer: up to 3 spaces of indent, then >=3 backticks or tildes.
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
# The marker. Deliberately NOT `key: value` shaped: Marp parses a comment like
# `<!-- tier: exec -->` as a (bogus) directive, so `@name value` stays inert.
_TIER_MARKER = re.compile(r"<!--\s*@tier\s+([A-Za-z0-9_-]+)\s*-->")

# Gap between segments, as a percentage of the bar's width.
SEGMENT_GAP = 2.0


class DeckError(ValueError):
    """A deck or tier-config problem the author must fix."""


# ── Tier config ──────────────────────────────────────────────────────────


def load_tiers(path: Path) -> list[dict[str, str]]:
    """Read the ordered tier table. Order in the file IS the deck's running order."""
    if not path.exists():
        raise DeckError(
            f"no tier config at {path}. It declares the deck's audiences, in the order the "
            f"deck addresses them, e.g.\n\n"
            f'  [[tier]]\n  name = "exec"\n  label = "Executives: the business case"\n'
            f'  colour = "#ef8e65"\n'
        )
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    tiers: list[dict[str, str]] = data.get("tier", [])
    if not tiers:
        raise DeckError(f"{path} declares no [[tier]] entries")
    for i, t in enumerate(tiers, 1):
        missing = [k for k in ("name", "label", "colour") if k not in t]
        if missing:
            raise DeckError(f"{path}: tier {i} is missing {missing}")
    names = [t["name"] for t in tiers]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise DeckError(f"{path}: duplicate tier name(s) {sorted(dupes)}")
    return tiers


# ── Deck parsing ─────────────────────────────────────────────────────────


def strip_managed(deck_text: str) -> str:
    """Drop the generated region so it can never be parsed as authoring input.

    The block lives inside slide 1, so anything it says about markers would be read
    back as a marker on that slide: output poisoning input. Removing it first makes
    the generator idempotent by construction rather than by careful wording. The
    block holds no `---` breaks, so slide numbering is unaffected.
    """
    return re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", deck_text, count=1, flags=re.DOTALL)


def split_slides(deck_text: str) -> list[str]:
    """Split a Marp deck into slide bodies, matching Marp's own break rules.

    Drops the YAML frontmatter, then splits on lines that are exactly `---`,
    EXCEPT inside a fenced code block. The fence tracking is load-bearing: Marp
    resolves fences before horizontal rules, so a `---` inside a fence is content.
    Without this, a deck that documents its own syntax counts a phantom slide, and
    since the rules key on Marp's slide id, every later fraction lands on the wrong
    slide. Nothing warns you; the deck still builds.
    """
    body = _FRONTMATTER.sub("", deck_text, count=1)
    slides: list[str] = []
    current: list[str] = []
    fence: str | None = None

    for line in body.split("\n"):
        m = _FENCE.match(line)
        if m:
            char = m.group(1)[0]
            if fence is None:
                fence = char
            elif fence == char:  # a ``` never closes a ~~~ block, and vice versa
                fence = None
        elif fence is None and _SLIDE_BREAK.fullmatch(line):
            slides.append("\n".join(current))
            current = []
            continue
        current.append(line)

    slides.append("\n".join(current))
    return slides


def slide_tiers(slides: list[str]) -> list[str | None]:
    """Each slide's tier name, None where the slide carries no marker."""
    out: list[str | None] = []
    for i, slide in enumerate(slides, 1):
        found = _TIER_MARKER.findall(slide)
        if len(found) > 1:
            raise DeckError(f"slide {i}: {len(found)} @tier markers ({', '.join(found)}); expected at most 1")
        out.append(found[0] if found else None)
    return out


def validate(tiers: list[str | None], names: list[str]) -> None:
    """Reject decks whose tier layout would make the progress bar lie."""
    unknown = {t for t in tiers if t is not None and t not in names}
    if unknown:
        raise DeckError(f"unknown tier(s) {sorted(unknown)}; the tier config declares {names}")

    seen: list[str] = []
    for i, t in enumerate(tiers, 1):
        if t is None:
            continue
        if not seen or seen[-1] != t:
            if t in seen:
                raise DeckError(
                    f"slide {i}: tier '{t}' resumes after '{seen[-1]}'. Tiers must be contiguous "
                    f"(all '{t}' slides together). Reorder the deck."
                )
            if seen and names.index(t) < names.index(seen[-1]):
                raise DeckError(
                    f"slide {i}: tier '{t}' follows '{seen[-1]}', out of the declared order {names}. "
                    f"The deck runs top-down; reorder the slides."
                )
            seen.append(t)


def progress(tiers: list[str | None], names: list[str]) -> list[tuple[int, str, float]]:
    """Map each tiered slide to (slide_number, tier, p) with p in (0, 1]."""
    counts = {n: tiers.count(n) for n in names}
    within = dict.fromkeys(names, 0)
    rows: list[tuple[int, str, float]] = []
    for num, t in enumerate(tiers, 1):
        if t is None:  # untiered (e.g. a title card): no rule, bar reads empty
            continue
        within[t] += 1
        rows.append((num, t, (names.index(t) + within[t] / counts[t]) / len(names)))
    return rows


# ── Rendering ────────────────────────────────────────────────────────────


def gradient(tier_defs: list[dict[str, str]]) -> str:
    """The segmented bar, computed for the configured tier count.

    Each tier k owns the span [k/N, (k+1)/N] of the bar, minus a gap. Its local
    fill is lp_k = clamp(0, p*N - k, 1): zero before the tier is reached, growing
    through it, one once complete. So earlier tiers read full, the current tier
    fills proportionally, and later tiers stay dim.

    Computing this (rather than hard-coding four segments in the theme) is what
    keeps the tier list a project's choice: N tiers need no CSS edit.
    """
    n = len(tier_defs)
    width = 100.0 / n
    stops: list[str] = []
    for k, tier in enumerate(tier_defs):
        start = k * width + (SEGMENT_GAP / 2 if k > 0 else 0)
        end = (k + 1) * width - (SEGMENT_GAP / 2 if k < n - 1 else 0)
        span = end - start
        colour = tier["colour"]
        fill = f"calc({start:.3f}% + {span:.3f}% * clamp(0, calc(var(--p) * {n} - {k}), 1))"
        if k > 0:  # the gap shows the slide background through the bar
            stops.append(f"transparent {k * width - SEGMENT_GAP / 2:.3f}%")
            stops.append(f"transparent {start:.3f}%")
        stops.append(f"{colour} {start:.3f}%")
        stops.append(f"{colour} {fill}")
        stops.append(f"var(--bar-track) {fill}")
        stops.append(f"var(--bar-track) {end:.3f}%")
    return "linear-gradient(90deg, " + ", ".join(stops) + ")"


def render_block(rows: list[tuple[int, str, float]], tiers: list[str | None], tier_defs: list[dict[str, str]]) -> str:
    """Build the managed block, documented for whoever reads the deck.

    This block must never contain a literal `@tier <name>`: it lives inside slide 1,
    so the parser would read it back as a real marker, and a nested `-->` would end
    the comment early and leak text onto the slide.
    """
    counts = {t["name"]: tiers.count(t["name"]) for t in tier_defs}
    n = len(tier_defs)
    lines = [
        BEGIN,
        "<!--",
        "Derived from the @tier marker on each slide by scripts/tier_progress.py.",
        "Edit the markers (or tiers.toml), then run `make progress`.",
        "",
        f"  p = (tier_index + (i + 1) / n) / {n}   for slide i (0-based) of a tier of n",
        "",
        "Slides with no marker get no rule: --p stays 0 and the bar reads empty.",
        "",
        "Tiers, in the order the deck addresses them:",
    ]
    for i, t in enumerate(tier_defs):
        lines.append(f"  {i + 1}. {t['name']:<8} n={counts[t['name']]:<3} {t['label']}")
    lines += ["-->", "<style>", f"section::before {{ background: {gradient(tier_defs)}; }}"]

    current: str | None = None
    for num, tier, p in rows:
        if tier != current:  # one comment per tier run, not per slide
            lines.append(f"/* {tier} */")
            current = tier
        lines.append(f'section[id="{num}"] {{ --p: {p:.4f}; }}')
    lines += ["</style>", END]
    return "\n".join(lines)


def splice(deck_text: str, block: str) -> str:
    """Replace the managed region, or insert it after the frontmatter if absent."""
    if BEGIN in deck_text and END in deck_text:
        pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
        return pattern.sub(lambda _: block, deck_text, count=1)
    if BEGIN in deck_text or END in deck_text:
        raise DeckError(
            "the deck has only one of the BEGIN/END progress sentinels. Refusing to guess where "
            "the managed region ends: restore both, or delete both to regenerate."
        )
    m = _FRONTMATTER.search(deck_text)
    if not m:
        raise DeckError("the deck has no YAML frontmatter, so the progress block has nowhere to go")
    return deck_text[: m.end()] + "\n" + block + "\n" + deck_text[m.end() :]


def report(
    rows: list[tuple[int, str, float]], tiers: list[str | None], names: list[str], out: TextIO = sys.stderr
) -> None:
    """Print what each slide's bar will show. Structure's answer to a pacing table."""
    counts = {n: tiers.count(n) for n in names}
    print("\n  slide  tier      progress  bar", file=out)
    print("  -----  --------  --------  --------------------", file=out)
    for num, tier, p in rows:
        filled = round(p * 20)
        print(f"  {num:>5}  {tier:<8}  {p * 100:>6.1f}%  {'#' * filled}{'.' * (20 - filled)}", file=out)
    untiered = [i for i, t in enumerate(tiers, 1) if t is None]
    print("  -----  --------  --------", file=out)
    print(
        f"  {len(rows)} tiered slides across {len([c for c in counts.values() if c])}/{len(names)} tiers "
        f"({', '.join(f'{n}={counts[n]}' for n in names)})" + (f"; untiered: {untiered}" if untiered else ""),
        file=out,
    )


# ── Core ─────────────────────────────────────────────────────────────────


def build(deck: Path, tiers_file: Path, check: bool = False, out: TextIO = sys.stderr) -> int:
    """Regenerate (or verify) the deck's progress block. Returns an exit code."""
    try:
        tier_defs = load_tiers(tiers_file)
        names = [t["name"] for t in tier_defs]
        text = deck.read_text(encoding="utf-8")
        slides = split_slides(strip_managed(text))
        tiers = slide_tiers(slides)
        validate(tiers, names)
        rows = progress(tiers, names)
        if not rows:
            raise DeckError(
                f"no `@tier` markers found. Tag each slide with its audience ({'/'.join(names)}); "
                f"the progress bar is derived from them."
            )
        updated = splice(text, render_block(rows, tiers, tier_defs))
    except DeckError as e:
        print(f"error: {deck}: {e}", file=out)
        return 1

    report(rows, tiers, names, out=out)

    if check:
        if updated != text:
            print(f"\n  error: {deck}'s progress block is STALE. Run `make progress` and commit.", file=out)
            return 1
        print(f"\n  {deck}: progress block is current", file=out)
        return 0
    if updated == text:
        print(f"\n  {deck}: progress block already current (no write)", file=out)
        return 0
    deck.write_text(updated, encoding="utf-8")
    print(f"\n  wrote progress block -> {deck}", file=out)
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────


def main(args: argparse.Namespace) -> int:
    return build(Path(args.deck), Path(args.tiers), check=args.check)


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--deck", default=DEFAULT_DECK, help=f"Marp deck source (default: {DEFAULT_DECK})")
    parser.add_argument("--tiers", default=DEFAULT_TIERS, help=f"tier config (default: {DEFAULT_TIERS})")
    parser.add_argument("--check", action="store_true", help="verify the block is current; write nothing")
    raise SystemExit(main(parser.parse_args()))
