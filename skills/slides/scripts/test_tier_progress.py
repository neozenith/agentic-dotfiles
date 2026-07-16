#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for tier_progress.

Names are resolved through the module object (`tp.build`, `tp.DeckError`) rather
than bound at import time: conftest's coverage reload rebinds every attribute, and
an exception class captured before the reload would never match the one raised.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import pytest

import tier_progress as tp

FRONTMATTER = "---\nmarp: true\ntheme: deck\n---\n"

TIERS_TOML = """
[[tier]]
name = "exec"
label = "Executives"
colour = "#ef8e65"

[[tier]]
name = "ic"
label = "Individual contributors"
colour = "#a78bfa"
"""


def write_tiers(tmp_path: Path, text: str = TIERS_TOML) -> Path:
    path = tmp_path / "tiers.toml"
    path.write_text(text, encoding="utf-8")
    return path


def deck_text(*slides: str) -> str:
    return FRONTMATTER + "\n---\n".join(slides)


def write_deck(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "slides.md"
    path.write_text(text, encoding="utf-8")
    return path


# ── load_tiers ───────────────────────────────────────────────────────────


def test_load_tiers_reads_declared_order(tmp_path: Path) -> None:
    tiers = tp.load_tiers(write_tiers(tmp_path))
    assert [t["name"] for t in tiers] == ["exec", "ic"]
    assert tiers[0]["colour"] == "#ef8e65"


def test_load_tiers_missing_file_is_loud(tmp_path: Path) -> None:
    with pytest.raises(tp.DeckError, match="no tier config at"):
        tp.load_tiers(tmp_path / "nope.toml")


def test_load_tiers_empty_table_is_loud(tmp_path: Path) -> None:
    with pytest.raises(tp.DeckError, match=r"declares no \[\[tier\]\] entries"):
        tp.load_tiers(write_tiers(tmp_path, "# nothing here\n"))


def test_load_tiers_missing_key_is_loud(tmp_path: Path) -> None:
    text = '[[tier]]\nname = "exec"\nlabel = "Executives"\n'
    with pytest.raises(tp.DeckError, match=r"tier 1 is missing \['colour'\]"):
        tp.load_tiers(write_tiers(tmp_path, text))


def test_load_tiers_duplicate_names_are_loud(tmp_path: Path) -> None:
    text = TIERS_TOML + '\n[[tier]]\nname = "exec"\nlabel = "Again"\ncolour = "#fff"\n'
    with pytest.raises(tp.DeckError, match=r"duplicate tier name\(s\) \['exec'\]"):
        tp.load_tiers(write_tiers(tmp_path, text))


# ── strip_managed / split_slides ─────────────────────────────────────────


def test_strip_managed_removes_generated_block_so_it_is_not_reparsed() -> None:
    text = f"# one\n{tp.BEGIN}\nanything at all\n{tp.END}\n# two\n"
    stripped = tp.strip_managed(text)
    assert tp.BEGIN not in stripped
    assert "anything at all" not in stripped
    assert "# one" in stripped and "# two" in stripped


def test_strip_managed_is_a_noop_without_a_block() -> None:
    assert tp.strip_managed("# plain\n") == "# plain\n"


def test_split_slides_drops_frontmatter_and_splits_on_rules() -> None:
    slides = tp.split_slides(deck_text("# a\n", "# b\n", "# c\n"))
    assert len(slides) == 3
    assert "marp: true" not in slides[0]


def test_split_slides_ignores_a_rule_inside_a_fenced_code_block() -> None:
    """A `---` inside a fence is content: Marp resolves fences before rules."""
    deck = deck_text("# a\n\n```md\n---\nnot a break\n---\n```\n", "# b\n")
    slides = tp.split_slides(deck)
    assert len(slides) == 2
    assert "not a break" in slides[0]


def test_split_slides_tilde_fence_is_not_closed_by_backticks() -> None:
    deck = deck_text("~~~\n```\n---\n~~~\n", "# b\n")
    assert len(tp.split_slides(deck)) == 2


def test_split_slides_trailing_whitespace_rule_is_a_break() -> None:
    assert len(tp.split_slides(FRONTMATTER + "# a\n\n--- \n# b\n")) == 2


def test_split_slides_rule_with_trailing_text_is_not_a_break() -> None:
    assert len(tp.split_slides(deck_text("# a\n\n--- not a break\n"))) == 1


# ── slide_tiers / validate ───────────────────────────────────────────────


def test_slide_tiers_maps_markers_and_none() -> None:
    slides = tp.split_slides(deck_text("# title\n", "<!-- @tier exec -->\n# a\n"))
    assert tp.slide_tiers(slides) == [None, "exec"]


def test_slide_tiers_rejects_two_markers_on_one_slide() -> None:
    slides = tp.split_slides(deck_text("<!-- @tier exec -->\n<!-- @tier ic -->\n# a\n"))
    with pytest.raises(tp.DeckError, match="slide 1: 2 @tier markers"):
        tp.slide_tiers(slides)


def test_validate_rejects_unknown_tier() -> None:
    with pytest.raises(tp.DeckError, match=r"unknown tier\(s\) \['boss'\]"):
        tp.validate(["boss"], ["exec", "ic"])


def test_validate_rejects_out_of_declared_order() -> None:
    with pytest.raises(tp.DeckError, match="out of the declared order"):
        tp.validate(["ic", "exec"], ["exec", "ic"])


def test_validate_rejects_interleaved_tiers() -> None:
    with pytest.raises(tp.DeckError, match="resumes after"):
        tp.validate(["exec", "ic", "exec"], ["exec", "ic"])


def test_validate_accepts_contiguous_ordered_tiers_with_gaps() -> None:
    tp.validate([None, "exec", "exec", None, "ic"], ["exec", "ic"])


# ── progress ─────────────────────────────────────────────────────────────


def test_progress_fractions_end_each_tier_at_its_boundary() -> None:
    rows = tp.progress(["exec", "exec", "ic"], ["exec", "ic"])
    assert rows == [(1, "exec", 0.25), (2, "exec", 0.5), (3, "ic", 1.0)]


def test_progress_skips_untiered_slides() -> None:
    rows = tp.progress([None, "exec"], ["exec", "ic"])
    assert [r[0] for r in rows] == [2]


# ── gradient ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("n", [2, 5])
def test_gradient_emits_one_segment_per_configured_tier(n: int) -> None:
    """Tier count is configuration, not a hard-coded four."""
    defs = [{"name": f"t{i}", "label": "l", "colour": f"#00000{i}"} for i in range(n)]
    css = tp.gradient(defs)
    assert css.startswith("linear-gradient(90deg, ")
    for i in range(n):
        assert f"#00000{i}" in css
        assert f"var(--p) * {n} - {i}" in css


def test_gradient_gaps_only_between_segments() -> None:
    two = tp.gradient([{"name": "a", "label": "l", "colour": "#111"}, {"name": "b", "label": "l", "colour": "#222"}])
    assert two.count("transparent") == 2  # one gap for two tiers
    one = tp.gradient([{"name": "a", "label": "l", "colour": "#111"}])
    assert "transparent" not in one


# ── render_block / splice ────────────────────────────────────────────────


def test_render_block_never_writes_a_literal_marker() -> None:
    defs = [{"name": "exec", "label": "Executives", "colour": "#ef8e65"}]
    block = tp.render_block(tp.progress(["exec"], ["exec"]), ["exec"], defs)
    assert "@tier exec" not in block
    assert 'section[id="1"] { --p: 1.0000; }' in block
    assert block.startswith(tp.BEGIN) and block.endswith(tp.END)


def test_render_block_one_comment_per_tier_run() -> None:
    defs = [
        {"name": "exec", "label": "Executives", "colour": "#ef8e65"},
        {"name": "ic", "label": "ICs", "colour": "#a78bfa"},
    ]
    tiers: list[str | None] = ["exec", "exec", "ic"]
    block = tp.render_block(tp.progress(tiers, ["exec", "ic"]), tiers, defs)
    assert block.count("/* exec */") == 1
    assert block.count("/* ic */") == 1


def test_splice_inserts_after_frontmatter_when_absent() -> None:
    out = tp.splice(deck_text("# a\n"), "BLOCK")
    assert out.startswith(FRONTMATTER + "\nBLOCK\n")


def test_splice_replaces_an_existing_region() -> None:
    text = FRONTMATTER + f"\n{tp.BEGIN}\nold\n{tp.END}\n# a\n"
    out = tp.splice(text, f"{tp.BEGIN}\nnew\n{tp.END}")
    assert "old" not in out and "new" in out


def test_splice_rejects_a_lone_sentinel() -> None:
    with pytest.raises(tp.DeckError, match="only one of the BEGIN/END"):
        tp.splice(FRONTMATTER + f"\n{tp.BEGIN}\n# a\n", "BLOCK")


def test_splice_rejects_a_deck_with_no_frontmatter() -> None:
    with pytest.raises(tp.DeckError, match="no YAML frontmatter"):
        tp.splice("# a\n", "BLOCK")


# ── build ────────────────────────────────────────────────────────────────


def test_build_writes_then_reports_already_current(tmp_path: Path) -> None:
    """Idempotence: the second run must write nothing."""
    deck = write_deck(tmp_path, deck_text("<!-- @tier exec -->\n# a\n", "<!-- @tier ic -->\n# b\n"))
    tiers = write_tiers(tmp_path)

    first = io.StringIO()
    assert tp.build(deck, tiers, out=first) == 0
    assert "wrote progress block" in first.getvalue()
    after_first = deck.read_text(encoding="utf-8")

    second = io.StringIO()
    assert tp.build(deck, tiers, out=second) == 0
    assert "already current (no write)" in second.getvalue()
    assert deck.read_text(encoding="utf-8") == after_first


def test_build_check_exits_zero_when_current_and_one_when_stale(tmp_path: Path) -> None:
    deck = write_deck(tmp_path, deck_text("<!-- @tier exec -->\n# a\n", "<!-- @tier ic -->\n# b\n"))
    tiers = write_tiers(tmp_path)
    tp.build(deck, tiers, out=io.StringIO())

    current = io.StringIO()
    assert tp.build(deck, tiers, check=True, out=current) == 0
    assert "progress block is current" in current.getvalue()

    deck.write_text(deck.read_text(encoding="utf-8") + "\n---\n\n<!-- @tier ic -->\n# c\n", encoding="utf-8")
    stale = io.StringIO()
    assert tp.build(deck, tiers, check=True, out=stale) == 1
    assert "STALE" in stale.getvalue()


def test_build_check_writes_nothing_when_stale(tmp_path: Path) -> None:
    deck = write_deck(tmp_path, deck_text("<!-- @tier exec -->\n# a\n", "<!-- @tier ic -->\n# b\n"))
    before = deck.read_text(encoding="utf-8")
    assert tp.build(deck, write_tiers(tmp_path), check=True, out=io.StringIO()) == 1
    assert deck.read_text(encoding="utf-8") == before


def test_build_reports_error_for_a_deck_without_markers(tmp_path: Path) -> None:
    deck = write_deck(tmp_path, deck_text("# a\n"))
    out = io.StringIO()
    assert tp.build(deck, write_tiers(tmp_path), out=out) == 1
    assert "no `@tier` markers found" in out.getvalue()


def test_build_reports_error_for_an_unknown_tier(tmp_path: Path) -> None:
    deck = write_deck(tmp_path, deck_text("<!-- @tier boss -->\n# a\n"))
    out = io.StringIO()
    assert tp.build(deck, write_tiers(tmp_path), out=out) == 1
    assert "unknown tier(s) ['boss']" in out.getvalue()


def test_build_report_lists_untiered_slides(tmp_path: Path) -> None:
    deck = write_deck(tmp_path, deck_text("# title\n", "<!-- @tier exec -->\n# a\n", "<!-- @tier ic -->\n# b\n"))
    out = io.StringIO()
    assert tp.build(deck, write_tiers(tmp_path), out=out) == 0
    assert "untiered: [1]" in out.getvalue()
    assert "2 tiered slides across 2/2 tiers" in out.getvalue()


def test_build_survives_a_fenced_rule_in_the_deck(tmp_path: Path) -> None:
    """The fence-aware split keeps slide ids aligned with Marp's numbering."""
    deck = write_deck(
        tmp_path,
        deck_text("<!-- @tier exec -->\n# a\n\n```md\n---\n```\n", "<!-- @tier ic -->\n# b\n"),
    )
    assert tp.build(deck, write_tiers(tmp_path), out=io.StringIO()) == 0
    text = deck.read_text(encoding="utf-8")
    assert 'section[id="2"] { --p: 1.0000; }' in text
    assert 'section[id="3"]' not in text


def test_main_dispatches_to_build(tmp_path: Path) -> None:
    deck = write_deck(tmp_path, deck_text("<!-- @tier exec -->\n# a\n", "<!-- @tier ic -->\n# b\n"))
    tiers = write_tiers(tmp_path)
    args = argparse.Namespace(deck=str(deck), tiers=str(tiers), check=False)
    assert tp.main(args) == 0
    assert tp.BEGIN in deck.read_text(encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
