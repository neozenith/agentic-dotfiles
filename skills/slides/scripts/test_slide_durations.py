#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for slide_durations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

from slide_durations import build, main, readable_words, slide_seconds, split_slides

FRONTMATTER = "---\nmarp: true\n---\n"

DEFAULTS = {"wpm": 180.0, "base": 1.2, "min": 2.5, "max": 12.0}


def deck_text(*slides: str) -> str:
    return FRONTMATTER + "\n---\n".join(slides)


def make_args(tmp_path: Path, deck: str, frames: int, **over: object) -> argparse.Namespace:
    deck_path = tmp_path / "slides.md"
    deck_path.write_text(deck, encoding="utf-8")
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir(exist_ok=True)
    for i in range(1, frames + 1):
        (frames_dir / f"slide.{i:03d}.png").write_bytes(b"\x89PNG")
    kwargs = dict(DEFAULTS)
    kwargs.update(over)
    return argparse.Namespace(
        deck=str(deck_path),
        frames_dir=str(frames_dir),
        out=str(tmp_path / "build" / "durations.concat"),
        **kwargs,
    )


# ── split_slides ─────────────────────────────────────────────────────────


def test_split_slides_drops_frontmatter_and_splits() -> None:
    slides = split_slides(deck_text("# a\n", "# b\n"))
    assert len(slides) == 2
    assert "marp: true" not in slides[0]


def test_split_slides_ignores_a_rule_inside_a_fenced_code_block() -> None:
    """Must agree with tier_progress: a `---` in a fence is content, not a break."""
    slides = split_slides(deck_text("# a\n\n```md\n---\nstill slide one\n---\n```\n", "# b\n"))
    assert len(slides) == 2
    assert "still slide one" in slides[0]


def test_split_slides_tilde_fence_is_not_closed_by_backticks() -> None:
    assert len(split_slides(deck_text("~~~\n```\n---\n~~~\n", "# b\n"))) == 2


def test_split_slides_rule_with_trailing_text_is_not_a_break() -> None:
    assert len(split_slides(deck_text("# a\n\n--- not a break\n"))) == 1


# ── readable_words ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", 0),
        ("# Three word heading", 3),
        ("<!-- @tier exec -->\nhello world", 2),
        ("<style>section { color: red; }</style>\nhello", 1),
        ("![w:1120](assets/x.png)", 0),
        ("see [the docs](https://example.com/x)", 3),  # link text is read, the URL is not
        ('<div class="box">two words</div>', 2),
        ("**bold** _em_ `code`", 3),
        ("- - -", 0),
    ],
)
def test_readable_words_counts_only_prose(text: str, expected: int) -> None:
    assert readable_words(text) == expected


# ── slide_seconds ────────────────────────────────────────────────────────


def test_slide_seconds_uses_the_wpm_model_between_the_clamps() -> None:
    secs, flag = slide_seconds(30, wpm=180.0, base=1.2, lo=2.5, hi=12.0)
    assert secs == pytest.approx(1.2 + 10.0)
    assert flag == ""


def test_slide_seconds_flags_the_floor() -> None:
    assert slide_seconds(0, wpm=180.0, base=1.2, lo=2.5, hi=12.0) == (2.5, "MIN")


def test_slide_seconds_flags_the_cap() -> None:
    assert slide_seconds(1000, wpm=180.0, base=1.2, lo=2.5, hi=12.0) == (12.0, "MAX")


# ── build ────────────────────────────────────────────────────────────────


def test_build_writes_a_concat_playlist_with_the_last_frame_repeated(tmp_path: Path) -> None:
    args = make_args(tmp_path, deck_text("# a\n", "# b\n"), frames=2)
    assert build(args) == 0
    lines = Path(args.out).read_text(encoding="utf-8").strip().split("\n")
    assert lines[0] == "ffconcat version 1.0"
    assert lines.count("file '" + str((tmp_path / "frames" / "slide.002.png").resolve()) + "'") == 2
    assert lines[-1].endswith("slide.002.png'")  # bare repeat: the demuxer drops the last duration
    assert sum(1 for line in lines if line.startswith("duration ")) == 2


def test_build_refuses_when_frames_and_slides_disagree(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = make_args(tmp_path, deck_text("# a\n", "# b\n", "# c\n"), frames=2)
    assert build(args) == 1
    assert "frame/slide mismatch" in capsys.readouterr().err
    assert not Path(args.out).exists()


def test_build_refuses_when_there_are_no_frames(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = make_args(tmp_path, deck_text("# a\n"), frames=0)
    assert build(args) == 1
    assert "no frames found" in capsys.readouterr().err


def test_build_counts_a_fenced_rule_as_content_not_a_slide(tmp_path: Path) -> None:
    """A phantom slide from a fenced `---` would surface here as a mismatch."""
    args = make_args(tmp_path, deck_text("# a\n\n```md\n---\n```\n", "# b\n"), frames=2)
    assert build(args) == 0


def test_build_pacing_table_flags_clamped_rows(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    deck = deck_text("# a\n", "word " * 400)
    args = make_args(tmp_path, deck, frames=2)
    assert build(args) == 0
    err = capsys.readouterr().err
    assert "held to floor" in err
    assert "capped" in err
    assert "@ 180 wpm, base 1.2s, clamp [2.5,12]s" in err


def test_main_reads_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = make_args(tmp_path, deck_text("# a\n"), frames=1)
    monkeypatch.setattr(
        sys,
        "argv",
        ["slide_durations.py", "--deck", args.deck, "--frames-dir", args.frames_dir, "--out", args.out],
    )
    assert main() == 0
    assert Path(args.out).exists()


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
