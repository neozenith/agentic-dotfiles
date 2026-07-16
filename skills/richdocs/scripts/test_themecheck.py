#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for themecheck.py — the gate that stops an unreadable brandpack shipping."""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest
import themecheck


def test_contrast_matches_known_wcag_values() -> None:
    assert round(themecheck.contrast("#000000", "#ffffff"), 2) == 21.0
    assert round(themecheck.contrast("#ffc000", "#ffffff"), 2) == 1.64  # the yellow
    assert round(themecheck.contrast("#000000", "#ffc000"), 2) == 12.79


def test_roles_apply_the_same_fallbacks_as_the_viewer() -> None:
    r = themecheck.roles({"bg": "#fff", "accent": "#123456"})
    assert r["onAccent"] == "#fff"  # text on the fill defaults to the canvas
    assert r["link"] == "#123456"  # text-safe accent defaults to the fill


def test_every_installed_theme_is_compliant() -> None:
    """The gate itself. A failure here means a shipped brand renders unreadable text."""
    for name in themecheck.available_themes():
        pack = json.loads(
            (themecheck.THEMES_DIR / name / "design-tokens.json").read_text("utf-8")
        )
        assert themecheck.check_theme(name, pack) == []


def test_the_original_bug_would_now_be_caught() -> None:
    """REGRESSION: one `accent` doing three jobs shipped a yellow that cannot be text.

    Faced with an impossible token the pack silently substituted a colour the brand
    does not own, and every check passed because nothing checked this pairing.
    """
    pack = json.loads(
        (themecheck.THEMES_DIR / "v2ai" / "design-tokens.json").read_text("utf-8")
    )
    naive = json.loads(json.dumps(pack))
    for mode in ("light", "dark"):
        naive["themes"][mode].pop("link", None)  # collapse the three roles
        naive["themes"][mode].pop("onAccent", None)
        naive["themes"][mode]["accent"] = "#ffc000"

    failures = themecheck.check_theme("naive", naive)
    assert any("heading / link" in f for f in failures)
    assert any("text on accent fill" in f for f in failures)


def test_invisible_chart_series_is_caught() -> None:
    """A mark you cannot see against its own plot surface is not a mark."""
    pack = json.loads(
        (themecheck.THEMES_DIR / "v2ai" / "design-tokens.json").read_text("utf-8")
    )
    pack["canvas"]["plotly"]["light"]["series"][0] = "#fefefe"  # white-on-white
    pack["canvas"]["plotly"]["light"]["plot"] = "#ffffff"
    failures = themecheck.check_theme("x", pack)
    assert any("series 1" in f for f in failures)


def test_series_contrast_waiver_is_honoured_but_cvd_is_not() -> None:
    """A documented `waivers.seriesContrast` skips ONLY mark-contrast, ONLY for the
    primary series. CVD adjacency is never waivable — colour-never-alone reinforces a
    distinguishable palette, it cannot rescue an indistinguishable one (ADR-016)."""
    pack = json.loads(
        (themecheck.THEMES_DIR / "v2ai" / "design-tokens.json").read_text("utf-8")
    )
    pack["canvas"]["plotly"]["light"]["plot"] = "#ffffff"
    pack["canvas"]["plotly"]["light"]["series"] = [
        "#eeeeee"
    ] * 8  # low-contrast AND no CVD sep
    # No waiver → the strict 3:1 rule fails, for every pack.
    assert any(
        "series 1" in f and "#ffffff" in f for f in themecheck.check_theme("x", pack)
    )
    # With a documented waiver → the contrast failures are gone...
    pack["waivers"] = {"seriesContrast": "deliberate low-contrast identity palette"}
    failures = themecheck.check_theme("x", pack)
    assert not any("#ffffff" in f for f in failures)
    # ...but identical greys are still not distinguishable, and THAT is never waived.
    assert any("under deuteranopia" in f for f in failures)


def test_unreadable_graph_node_label_is_caught() -> None:
    pack = json.loads(
        (themecheck.THEMES_DIR / "v2ai" / "design-tokens.json").read_text("utf-8")
    )
    pack["canvas"]["cytoscape"]["dark"]["nodeLabel"] = "#111111"
    pack["canvas"]["cytoscape"]["dark"]["nodeFill"] = "#000000"
    failures = themecheck.check_theme("x", pack)
    assert any("graph node label" in f for f in failures)


def test_main_reports_and_exits_on_a_failing_theme(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The gate must FAIL the build, not print a warning and carry on."""
    pack_path = themecheck.THEMES_DIR / "v2ai" / "design-tokens.json"
    original = pack_path.read_text("utf-8")
    broken = json.loads(original)
    for mode in ("light", "dark"):
        broken["themes"][mode].pop("link", None)
        broken["themes"][mode]["accent"] = "#ffc000"
    try:
        pack_path.write_text(json.dumps(broken), encoding="utf-8")
        with pytest.raises(SystemExit) as excinfo:
            themecheck.main(Namespace(theme="v2ai"))
        assert excinfo.value.code == 1
        out = capsys.readouterr()
        assert "[FAIL] v2ai" in out.out
        assert "do NOT loosen the check" in out.err
    finally:
        pack_path.write_text(original, encoding="utf-8")


# ── the ramps a brand ships beyond its categorical series ───────────────────


def test_a_hue_at_the_diverging_midpoint_is_rejected() -> None:
    """A coloured zero makes "no change" look like a value."""
    pack = json.loads(
        (themecheck.THEMES_DIR / "osakanights" / "design-tokens.json").read_text(
            "utf-8"
        )
    )
    pack["canvas"]["plotly"]["dark"]["diverging"]["zero"] = "#3a7a20"  # green midpoint
    assert any("not neutral" in f for f in themecheck.check_theme("x", pack))


def test_non_monotone_sequential_ramp_is_rejected() -> None:
    """Sequential encodes magnitude. Unrankable steps make it decoration."""
    pack = json.loads(
        (themecheck.THEMES_DIR / "osakanights" / "design-tokens.json").read_text(
            "utf-8"
        )
    )
    pack["canvas"]["plotly"]["dark"]["sequential"] = [
        "#ffffff",
        "#111111",
        "#eeeeee",
        "#222222",
        "#dddddd",
    ]
    assert any("not monotone" in f for f in themecheck.check_theme("x", pack))


def test_status_without_a_label_is_rejected() -> None:
    """Colour may never carry meaning alone."""
    pack = json.loads(
        (themecheck.THEMES_DIR / "osakanights" / "design-tokens.json").read_text(
            "utf-8"
        )
    )
    pack["status"]["dark"]["labels"].pop("critical")
    assert any("no label" in f for f in themecheck.check_theme("x", pack))


def test_every_theme_ships_the_full_dataviz_palette() -> None:
    """REGRESSION: the schema once held only `series`, so five sixths of a brand's
    documented palette had nowhere to live and silently never rendered."""
    for name in themecheck.available_themes():
        pack = json.loads(
            (themecheck.THEMES_DIR / name / "design-tokens.json").read_text("utf-8")
        )
        assert "status" in pack, f"{name} ships no status tier"
        for mode in ("light", "dark"):
            plot = pack["canvas"]["plotly"][mode]
            for key in ("series", "muted", "sequential", "diverging"):
                assert key in plot, f"{name}/{mode} is missing `{key}`"
            div = plot["diverging"]
            assert set(div) >= {"good", "zero", "bad"}


def test_main_exits_nonzero_on_an_unknown_theme(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        themecheck.main(Namespace(theme="nope"))


def test_main_passes_for_installed_themes(capsys: pytest.CaptureFixture[str]) -> None:
    themecheck.main(Namespace(theme=None))
    assert "compliant" in capsys.readouterr().out


def test_build_parser_defaults() -> None:
    assert themecheck.build_parser().parse_args([]).theme is None


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    sys.exit(
        pytest.main(
            [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="] + sys.argv[1:]
        )
    )
