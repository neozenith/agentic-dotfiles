#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for prose_check."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from prose_check import ALLOW, EM_DASH, check, main, strip_uncheckable


def write(tmp_path: Path, text: str, name: str = "doc.md") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ── strip_uncheckable ────────────────────────────────────────────────────


def test_strip_uncheckable_blanks_a_fence_but_keeps_line_numbers() -> None:
    text = "one\n```\ncolor\n```\nfive\n"
    out = strip_uncheckable(text)
    assert out.split("\n") == ["one", "   ", "     ", "   ", "five", ""]


def test_strip_uncheckable_blanks_code_spans_in_place() -> None:
    out = strip_uncheckable("use `color` here")
    assert out == "use   " + " " * 5 + " here"
    assert "color" not in out


def test_strip_uncheckable_blanks_the_generated_progress_region() -> None:
    text = (
        "intro\n"
        "<!-- BEGIN GENERATED PROGRESS BAR: do not hand-edit -->\n"
        "section::before { background: color; }\n"
        "<!-- END GENERATED PROGRESS BAR -->\n"
        "outro\n"
    )
    out = strip_uncheckable(text)
    assert "background" not in out
    assert out.split("\n")[0] == "intro"
    assert out.split("\n")[4] == "outro"


# ── check ────────────────────────────────────────────────────────────────


def test_check_clean_file_has_no_hits(tmp_path: Path) -> None:
    assert check(write(tmp_path, "A clean line, with a comma.\n")) == []


def test_check_flags_an_em_dash(tmp_path: Path) -> None:
    hits = check(write(tmp_path, f"a line {EM_DASH} with a dash\n"))
    assert hits == [(1, "em-dash", "use a comma, a colon, parentheses, or split the sentence")]


@pytest.mark.parametrize(
    "line,fix",
    [
        ("we organize things", "organis-"),
        ("the color of it", "colour"),
        ("odd behavior here", "behaviour"),
        ("normalize the data", "normalis-"),
        ("prioritize the work", "prioritis-"),
        ("recognize the risk", "recognis-"),
        ("analyze the log", "analys-"),
        ("a catalog of parts", "catalogue"),
        ("a judgment call", "judgement"),
    ],
)
def test_check_flags_us_spellings(tmp_path: Path, line: str, fix: str) -> None:
    hits = check(write(tmp_path, line + "\n"))
    assert [(h[1], h[2].split(" -> ")[1]) for h in hits] == [("US spelling", fix)]


@pytest.mark.parametrize(
    "line,fix",
    [
        ("the whitelist of hosts", "allow list"),
        ("a blacklist entry", "deny list"),
        ("a sanity check first", "quick check"),
        ("a dummy value there", "placeholder"),
        ("the master branch", "primary / main"),
    ],
)
def test_check_flags_non_inclusive_terms(tmp_path: Path, line: str, fix: str) -> None:
    hits = check(write(tmp_path, line + "\n"))
    assert [(h[1], h[2].split(" -> ")[1]) for h in hits] == [("non-inclusive", fix)]


def test_check_reports_accurate_line_numbers_past_a_blanked_fence(tmp_path: Path) -> None:
    """Blanking (not deleting) is what keeps this number honest."""
    text = "intro\n```\ncolor: #fff\nwhitelist\n```\nreal color here\n"
    assert check(write(tmp_path, text)) == [(6, "US spelling", "'color' -> colour")]


def test_check_ignores_code_spans_but_not_the_prose_around_them(tmp_path: Path) -> None:
    assert check(write(tmp_path, "the `fillColor` token\n")) == []
    hits = check(write(tmp_path, "the `fillColor` token has a color\n"))
    assert [h[1] for h in hits] == ["US spelling"]


def test_check_ignores_the_generated_region(tmp_path: Path) -> None:
    text = "clean\n<!-- BEGIN GENERATED PROGRESS BAR -->\nbackground: color;\n<!-- END GENERATED PROGRESS BAR -->\n"
    assert check(write(tmp_path, text)) == []


def test_check_honours_an_allow_tag(tmp_path: Path) -> None:
    assert check(write(tmp_path, f"never write {EM_DASH} like this <!-- {ALLOW} -->\n")) == []


def test_check_reports_every_rule_a_line_breaks(tmp_path: Path) -> None:
    hits = check(write(tmp_path, f"organize the whitelist {EM_DASH} now\n"))
    assert sorted(h[1] for h in hits) == ["US spelling", "em-dash", "non-inclusive"]


# ── main ─────────────────────────────────────────────────────────────────


def test_main_returns_zero_for_clean_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, "All good here.\n")
    monkeypatch.setattr(sys, "argv", ["prose_check.py", "--files", str(path)])
    assert main() == 0
    assert "1 file(s) clean" in capsys.readouterr().err


def test_main_returns_one_and_prints_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, f"ok\nthe color {EM_DASH} here\n")
    monkeypatch.setattr(sys, "argv", ["prose_check.py", "--files", str(path)])
    assert main() == 1
    err = capsys.readouterr().err
    assert ":2: em-dash" in err
    assert ":2: US spelling" in err
    assert "2 prose violation(s)" in err


def test_main_is_loud_about_a_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["prose_check.py", "--files", str(tmp_path / "nope.md")])
    assert main() == 1
    assert "no such file(s)" in capsys.readouterr().err


def test_main_defaults_to_the_decks_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no --files, the globs are relative to the script's parent directory."""
    import prose_check

    deck_dir = tmp_path / "deck"
    (deck_dir / "scripts").mkdir(parents=True)
    write(deck_dir, "the color of it\n", "slides.md")
    monkeypatch.setattr(prose_check, "__file__", str(deck_dir / "scripts" / "prose_check.py"))
    monkeypatch.setattr(sys, "argv", ["prose_check.py"])
    assert main() == 1
    assert "slides.md:1: US spelling" in capsys.readouterr().err


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
