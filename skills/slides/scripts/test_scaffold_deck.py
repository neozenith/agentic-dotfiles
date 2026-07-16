#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for scaffold_deck.

Names are resolved through the module object (`sd.scaffold`, `sd.ScaffoldError`)
rather than bound at import time: conftest's coverage reload rebinds every
attribute, and an exception class captured before the reload would never match.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pytest

import scaffold_deck as sd
import tier_progress as tp

TOKENS = {
    "defaultTheme": "light",
    "themes": {
        "dark": {"bg": "#000102", "accent": "#0a0b0c", "radius": "4px"},
        "light": {"bg": "#fefefe"},
    },
    "fonts": {"display": "Inter, sans-serif", "mono": "Fira Code, monospace"},
}


def write_tokens(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "design-tokens.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ── read_tokens ──────────────────────────────────────────────────────────


def test_read_tokens_without_a_path_uses_the_placeholder_palette() -> None:
    palette, provenance = sd.read_tokens(None)
    assert palette == sd.FALLBACK_TOKENS
    assert provenance == "placeholder palette (no --tokens given)"
    palette["bg"] = "mutated"
    assert sd.FALLBACK_TOKENS["bg"] != "mutated"  # the default must not be aliased


def test_read_tokens_prefers_the_dark_theme_and_fonts(tmp_path: Path) -> None:
    path = write_tokens(tmp_path, TOKENS)
    palette, provenance = sd.read_tokens(path)
    assert palette["bg"] == "#000102"
    assert palette["accent"] == "#0a0b0c"
    assert palette["radius"] == "4px"
    assert palette["fontDisplay"] == "Inter, sans-serif"
    assert palette["fontMono"] == "Fira Code, monospace"
    assert palette["fg"] == sd.FALLBACK_TOKENS["fg"]  # keys the tokens omit keep the default
    assert str(path) in provenance


def test_read_tokens_falls_back_to_the_default_theme_when_no_dark(tmp_path: Path) -> None:
    path = write_tokens(tmp_path, {"defaultTheme": "light", "themes": {"light": {"bg": "#fefefe"}}})
    palette, _ = sd.read_tokens(path)
    assert palette["bg"] == "#fefefe"


def test_read_tokens_missing_file_is_loud(tmp_path: Path) -> None:
    """A named tokens file that cannot be read must never degrade to placeholders."""
    with pytest.raises(sd.ScaffoldError, match="no design tokens at"):
        sd.read_tokens(tmp_path / "nope.json")


def test_read_tokens_without_a_usable_theme_block_is_loud(tmp_path: Path) -> None:
    path = write_tokens(tmp_path, {"themes": {"solarized": {"bg": "#000"}}})
    with pytest.raises(sd.ScaffoldError, match="has no themes.dark"):
        sd.read_tokens(path)


# ── render_template / mapping_for ────────────────────────────────────────


def test_render_template_substitutes_every_placeholder() -> None:
    out = sd.render_template("theme: {{DECK_NAME}} bg: {{TOKEN_BG}}", {"DECK_NAME": "pitch", "TOKEN_BG": "#000"})
    assert out == "theme: pitch bg: #000"


def test_render_template_rejects_an_unresolved_placeholder() -> None:
    with pytest.raises(sd.ScaffoldError, match="unresolved placeholders"):
        sd.render_template("{{MISSING}}", {"DECK_NAME": "pitch"})


def test_mapping_for_upcases_token_keys() -> None:
    mapping = sd.mapping_for("pitch", {"bg": "#000", "onAccent": "#fff"}, "placeholder palette")
    assert mapping["DECK_NAME"] == "pitch"
    assert mapping["THEME_NAME"] == "pitch"
    assert mapping["PALETTE_PROVENANCE"] == "placeholder palette"
    assert mapping["TOKEN_BG"] == "#000"
    assert mapping["TOKEN_ONACCENT"] == "#fff"


# ── scaffold ─────────────────────────────────────────────────────────────


def test_scaffold_writes_a_complete_deck(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    log = io.StringIO()
    assert sd.scaffold(out, "pitch", None, log=log) == 0

    assert (out / "slides.md").exists()
    assert (out / "master-template.md").exists()
    assert (out / "tiers.toml").exists()
    assert (out / "Makefile").exists()
    # theme.css is renamed for the deck so two decks can coexist in Marp's registry
    assert (out / "themes" / "pitch.css").exists()
    assert not (out / "themes" / "theme.css").exists()
    assert "placeholder palette" in log.getvalue()


def test_scaffold_leaves_no_unresolved_placeholders(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    sd.scaffold(out, "pitch", None, log=io.StringIO())
    rendered = [p for p in out.rglob("*") if p.is_file() and p.parent.name != "scripts"]
    assert rendered
    for path in rendered:
        text = path.read_text(encoding="utf-8")
        assert not ("{{" in text and "}}" in text), f"{path} still holds a placeholder"


def test_scaffold_renders_the_deck_name_and_palette_into_the_theme(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    sd.scaffold(out, "pitch", write_tokens(tmp_path, TOKENS), log=io.StringIO())
    css = (out / "themes" / "pitch.css").read_text(encoding="utf-8")
    assert "@theme pitch" in css
    assert "#000102" in css
    assert "design-tokens.json" in css
    assert "theme: pitch" in (out / "slides.md").read_text(encoding="utf-8")


def test_scaffold_copies_the_helper_scripts(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    sd.scaffold(out, "pitch", None, log=io.StringIO())
    for helper in sd.HELPER_SCRIPTS:
        copied = out / "scripts" / helper
        assert copied.exists()
        assert copied.read_text(encoding="utf-8") == (Path(__file__).parent / helper).read_text(encoding="utf-8")


def test_scaffolded_deck_is_born_green(tmp_path: Path) -> None:
    """Every generated deck's tier block must already pass a --check."""
    out = tmp_path / "slides"
    sd.scaffold(out, "pitch", None, log=io.StringIO())
    decks = sorted(out.glob("*.md"))
    assert decks
    for deck in decks:
        report = io.StringIO()
        assert tp.build(deck, out / "tiers.toml", check=True, out=report) == 0, report.getvalue()


def test_scaffold_refuses_a_non_empty_target_without_force(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    out.mkdir()
    (out / "keep.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(sd.ScaffoldError, match="exists and is not empty"):
        sd.scaffold(out, "pitch", None, log=io.StringIO())


def test_scaffold_accepts_an_empty_target_dir(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    out.mkdir()
    assert sd.scaffold(out, "pitch", None, log=io.StringIO()) == 0


def test_scaffold_force_overwrites_a_non_empty_target(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    out.mkdir()
    (out / "slides.md").write_text("stale", encoding="utf-8")
    assert sd.scaffold(out, "pitch", None, force=True, log=io.StringIO()) == 0
    assert "stale" not in (out / "slides.md").read_text(encoding="utf-8")


def test_scaffold_with_a_missing_tokens_path_is_loud_and_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    with pytest.raises(sd.ScaffoldError, match="no design tokens at"):
        sd.scaffold(out, "pitch", tmp_path / "nope.json", log=io.StringIO())
    assert not out.exists()


def test_scaffold_is_loud_when_the_template_is_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sd, "DECK_TEMPLATE", tmp_path / "absent")
    with pytest.raises(sd.ScaffoldError, match="deck template missing at"):
        sd.scaffold(tmp_path / "slides", "pitch", None, log=io.StringIO())


def test_scaffold_is_loud_when_a_helper_script_is_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sd, "SCRIPT_DIR", tmp_path / "no-scripts")
    with pytest.raises(sd.ScaffoldError, match="is missing from the skill"):
        sd.scaffold(tmp_path / "slides", "pitch", None, log=io.StringIO())


# ── retag_deck / --tiers ─────────────────────────────────────────────────

THREE_TIERS = """
[[tier]]
name = "board"
label = "Board"
colour = "#111111"

[[tier]]
name = "eng"
label = "Engineers"
colour = "#222222"

[[tier]]
name = "ops"
label = "Operators"
colour = "#333333"
"""


def write_tiers(tmp_path: Path, text: str = THREE_TIERS, name: str = "custom-tiers.toml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_retag_deck_spreads_markers_evenly_across_the_declared_tiers(tmp_path: Path) -> None:
    deck = tmp_path / "d.md"
    deck.write_text("\n".join(f"<!-- @tier old{i} -->" for i in range(6)), encoding="utf-8")
    sd.retag_deck(deck, ["a", "b", "c"])
    assert tp._TIER_MARKER.findall(deck.read_text(encoding="utf-8")) == ["a", "a", "b", "b", "c", "c"]


def test_retag_deck_keeps_the_declared_order(tmp_path: Path) -> None:
    deck = tmp_path / "d.md"
    deck.write_text("<!-- @tier x -->\n<!-- @tier y -->\n<!-- @tier z -->", encoding="utf-8")
    sd.retag_deck(deck, ["first", "second"])
    names = tp._TIER_MARKER.findall(deck.read_text(encoding="utf-8"))
    assert names == sorted(names, key=["first", "second"].index)


def test_retag_deck_is_a_noop_on_an_unmarked_deck(tmp_path: Path) -> None:
    deck = tmp_path / "d.md"
    deck.write_text("# no markers here\n", encoding="utf-8")
    sd.retag_deck(deck, ["a", "b"])
    assert deck.read_text(encoding="utf-8") == "# no markers here\n"


def test_scaffold_with_custom_tiers_installs_them_and_stays_green(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    assert sd.scaffold(out, "pitch", None, tiers=write_tiers(tmp_path), log=io.StringIO()) == 0

    installed = (out / "tiers.toml").read_text(encoding="utf-8")
    assert 'name = "board"' in installed
    assert "exec" not in installed

    decks = sorted(out.glob("*.md"))
    assert decks
    for deck in decks:
        used = set(tp._TIER_MARKER.findall(deck.read_text(encoding="utf-8")))
        assert used <= {"board", "eng", "ops"}, f"{deck} still carries template tier names"
        report = io.StringIO()
        assert tp.build(deck, out / "tiers.toml", check=True, out=report) == 0, report.getvalue()


def test_scaffold_with_a_missing_tiers_path_is_loud(tmp_path: Path) -> None:
    with pytest.raises(sd.ScaffoldError, match="no tier config at"):
        sd.scaffold(tmp_path / "slides", "pitch", None, tiers=tmp_path / "nope.toml", log=io.StringIO())


def test_scaffold_validates_custom_tiers_before_overwriting_the_default(tmp_path: Path) -> None:
    """A broken config must not replace the working default it was meant to improve."""
    bad = write_tiers(tmp_path, '[[tier]]\nname = "board"\nlabel = "Board"\n')
    out = tmp_path / "slides"
    with pytest.raises(tp.DeckError, match="is missing"):
        sd.scaffold(out, "pitch", None, tiers=bad, log=io.StringIO())
    assert 'name = "exec"' in (out / "tiers.toml").read_text(encoding="utf-8")


def test_main_passes_a_tiers_path_through(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    args = argparse.Namespace(out=str(out), name="pitch", tokens=None, tiers=str(write_tiers(tmp_path)), force=False)
    assert sd.main(args) == 0
    assert 'name = "board"' in (out / "tiers.toml").read_text(encoding="utf-8")


# ── main ─────────────────────────────────────────────────────────────────


def test_main_scaffolds(tmp_path: Path) -> None:
    out = tmp_path / "slides"
    args = argparse.Namespace(out=str(out), name="pitch", tokens=None, tiers=None, force=False)
    assert sd.main(args) == 0
    assert (out / "slides.md").exists()


def test_main_reports_a_scaffold_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        out=str(tmp_path / "slides"), name="pitch", tokens=str(tmp_path / "nope.json"), tiers=None, force=False
    )
    assert sd.main(args) == 1
    assert "error: no design tokens at" in capsys.readouterr().err


def test_main_reports_malformed_tokens_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "tokens.json"
    bad.write_text("{not json", encoding="utf-8")
    args = argparse.Namespace(out=str(tmp_path / "slides"), name="pitch", tokens=str(bad), tiers=None, force=False)
    assert sd.main(args) == 1
    assert "error:" in capsys.readouterr().err


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
