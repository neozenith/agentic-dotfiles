#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Compute per-slide display durations from a Marp deck's readable word count.

Pipeline role (see ../Makefile): Marp emits one PNG per slide; this script reads
the SAME deck source, counts the words a viewer actually reads on each slide, and
writes an ffmpeg *concat demuxer* playlist pairing each frame with its own
`duration`. The `video` target feeds that playlist to ffmpeg instead of a single
global framerate, so dense slides hold longer than sparse title cards.

Duration model (all knobs are CLI/Make overridable):

    seconds = clamp(BASE + words / WPM * 60, MIN, MAX)

BASE is fixed visual-acquisition/transition dwell every slide gets even with zero
words (title/lead cards). The clamp bounds pacing so one dense slide can't run for
a minute and an empty lead card isn't a subliminal flash. When the WPM-derived time
is overridden by MIN or MAX, the row is flagged in the table so the pacing decision
is visible, not silent (escalators-not-stairs: announce, don't hide).

Tier B / stdlib-only by design (../.claude rules): no third-party imports, so it
runs anywhere `python3` exists; `uv run` is just the ergonomic launcher.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --- deck parsing ---------------------------------------------------------

_FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
_SLIDE_BREAK = re.compile(r"---[ \t]*\r?$")
# A fence opener/closer: up to 3 spaces of indent, then >=3 backticks or tildes.
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")

# Stripping stages, applied in order. Each removes syntax a viewer does NOT read
# as words, leaving prose behind. Order matters: kill comments/style/images before
# generic tag stripping so their contents don't leak through.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_STYLE_BLOCK = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")  # ![w:1120](assets/x.png) -> gone
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")  # [text](url) -> text
_HTML_TAG = re.compile(r"<[^>]+>")  # <div class="box"> -> space
_MARKERS = re.compile(r"[*_`#>|~]")  # emphasis/heading/quote/pipe/code
_HAS_ALNUM = re.compile(r"[A-Za-z0-9]")


def split_slides(deck_text: str) -> list[str]:
    """Split a Marp deck into slide bodies, matching Marp's own break rules.

    Drops the YAML frontmatter block, then splits on lines that are exactly `---`
    (optionally trailed by whitespace). A `---` with other text on the line (e.g.
    inside a prose HTML comment) is NOT a break, which is why the match anchors the
    whole line. A `---` inside a fenced code block is NOT a break either: Marp's
    parser resolves fences before horizontal rules, so it is content. Without the
    fence tracking, a deck that documents its own syntax counts a phantom slide —
    here that surfaces as a frame/slide mismatch (caught below), but the same bug
    silently mis-numbers the tier bar, so scripts/tier_progress.py carries an
    identical splitter. THE TWO MUST AGREE.
    """
    body = _FRONTMATTER.sub("", deck_text, count=1)
    slides: list[str] = []
    current: list[str] = []
    fence: str | None = None  # the char (` or ~) of the open fence, else None

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


def readable_words(slide_text: str) -> int:
    """Count the words a viewer reads on a slide, ignoring non-prose syntax."""
    t = _HTML_COMMENT.sub(" ", slide_text)
    t = _STYLE_BLOCK.sub(" ", t)
    t = _IMAGE.sub(" ", t)
    t = _MD_LINK.sub(r"\1", t)
    t = _HTML_TAG.sub(" ", t)
    t = _MARKERS.sub(" ", t)
    return sum(1 for tok in t.split() if _HAS_ALNUM.search(tok))


# --- duration model -------------------------------------------------------


def slide_seconds(words: int, *, wpm: float, base: float, lo: float, hi: float) -> tuple[float, str]:
    """Return (seconds, flag) where flag marks a clamp override for the table."""
    raw = base + words / wpm * 60.0
    if raw < lo:
        return lo, "MIN"
    if raw > hi:
        return hi, "MAX"
    return raw, ""


def build(args: argparse.Namespace) -> int:
    deck = Path(args.deck)
    frames = sorted(Path(args.frames_dir).glob("slide.*.png"))
    slides = split_slides(deck.read_text(encoding="utf-8"))

    if not frames:
        print(f"error: no frames found in {args.frames_dir} (run `make frames` first)", file=sys.stderr)
        return 1
    if len(frames) != len(slides):
        print(
            f"error: frame/slide mismatch — {len(frames)} PNGs but {len(slides)} slides parsed "
            f"from {deck}. The deck's slide breaks and the rendered frames disagree; refusing to "
            f"emit a misaligned playlist.",
            file=sys.stderr,
        )
        return 1

    rows = []
    total = 0.0
    for frame, slide in zip(frames, slides):
        words = readable_words(slide)
        secs, flag = slide_seconds(words, wpm=args.wpm, base=args.base, lo=args.min, hi=args.max)
        total += secs
        rows.append((frame, words, secs, flag))

    # Emit the concat playlist. The demuxer drops the LAST entry's duration, so the
    # final frame is listed twice (once timed, once bare) to hold it for real.
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["ffconcat version 1.0"]
    for frame, _, secs, _ in rows:
        # frame paths are relative to the concat file's directory when it lives
        # beside build/; use an absolute path so ffmpeg resolves them regardless of cwd.
        lines.append(f"file '{frame.resolve()}'")
        lines.append(f"duration {secs:.3f}")
    lines.append(f"file '{rows[-1][0].resolve()}'")  # repeat last frame (duration quirk)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Human-readable pacing table -> stderr (stdout stays clean for scripting).
    print("\n  slide  words   seconds  note", file=sys.stderr)
    print("  -----  -----   -------  ----", file=sys.stderr)
    for i, (_, words, secs, flag) in enumerate(rows, 1):
        note = {"MIN": "held to floor", "MAX": "capped", "": ""}[flag]
        print(f"  {i:>5}  {words:>5}   {secs:>6.2f}  {note}", file=sys.stderr)
    print("  -----  -----   -------", file=sys.stderr)
    tot_words = sum(r[1] for r in rows)
    print(
        f"  total  {tot_words:>5}   {total:>6.2f}s  ({total / 60:.1f} min) "
        f"@ {args.wpm:g} wpm, base {args.base:g}s, clamp [{args.min:g},{args.max:g}]s",
        file=sys.stderr,
    )
    print(f"\n  wrote {out}", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--deck", default="slides.md", help="Marp deck source (default: slides.md)")
    p.add_argument("--frames-dir", default="build/frames", help="dir of slide.NNN.png frames")
    p.add_argument("--out", default="build/durations.concat", help="ffmpeg concat playlist to write")
    p.add_argument(
        "--wpm", type=float, default=180.0, help="reading speed, words per minute (default: 180 — bullet-glance pace)"
    )
    p.add_argument("--base", type=float, default=1.2, help="fixed dwell seconds every slide gets (default: 1.2)")
    p.add_argument("--min", type=float, default=2.5, help="minimum seconds per slide (default: 2.5)")
    p.add_argument("--max", type=float, default=12.0, help="maximum seconds per slide (default: 12.0)")
    return build(p.parse_args())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
