#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest>=8.0",
#   "pytest-cov>=4.0",
#   "Pillow>=10.0.0",
# ]
# ///
"""Tests for art_vid.

Offline by construction: the Veo call and ffmpeg are both boundaries, exercised through
injected real fakes (a fake client, a recording subprocess runner). No API key, no network,
no paid request — consistent with ADR-008, secrets never pass through pytest.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import art_vid
import pytest


# ── Fakes (real objects through documented seams) ──────────────────────────
class _RecordingRunner:
    """Stands in for subprocess.run, recording ffmpeg invocations and touching outputs."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **kwargs: object) -> object:
        self.calls.append(cmd)
        Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(cmd[-1]).write_bytes(b"\x89PNG")
        return object()


# ── prompt loading ─────────────────────────────────────────────────────────
def test_load_prompt_file_strips_comments(tmp_path: Path) -> None:
    pf = tmp_path / "p.md"
    pf.write_text("# heading\n<!-- note -->\nThe car slides.\nDust rises.\n", encoding="utf-8")
    assert art_vid.load_prompt_file(pf) == "The car slides.\nDust rises."


def test_load_prompt_file_empty_raises(tmp_path: Path) -> None:
    pf = tmp_path / "p.md"
    pf.write_text("# only comments\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        art_vid.load_prompt_file(pf)


# ── model catalogue ────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "alias,backend,expected",
    [
        (None, "vertex", "veo-3.1-fast-generate-001"),
        ("standard", "vertex", "veo-3.1-generate-001"),
        ("lite", "vertex", "veo-3.1-lite-generate-001"),
        (None, "gemini", "veo-3.1-fast-generate-preview"),
        ("standard", "gemini", "veo-3.1-generate-preview"),
        ("veo-custom-id", "vertex", "veo-custom-id"),
    ],
)
def test_resolve_model_is_backend_aware(alias: str | None, backend: str, expected: str) -> None:
    """Vertex serves GA `-001` ids; the Gemini API serves `-preview`. Mixing them 404s."""
    assert art_vid.resolve_model(alias, backend) == expected


def test_resolve_model_unknown_backend_falls_back_to_default_table() -> None:
    assert art_vid.resolve_model("standard", "nonsense") == "veo-3.1-generate-001"


def test_model_catalogue_is_all_veo_3_1() -> None:
    """Veo 3.0 is superseded; offering it would sell an older model."""
    for table in art_vid.VEO_MODELS_BY_BACKEND.values():
        assert all("veo-3.1" in mid for mid in table.values())


@pytest.mark.parametrize(
    "model,family",
    [
        ("veo-3.1-generate-001", "standard"),
        ("veo-3.1-generate-preview", "standard"),
        ("veo-3.1-fast-generate-001", "fast"),
        ("veo-3.1-lite-generate-preview", "lite"),
        ("not-a-video-model", None),
    ],
)
def test_veo_family_classifies_both_id_schemes(model: str, family: str | None) -> None:
    assert art_vid.veo_family(model) == family


# ── story arc composition ──────────────────────────────────────────────────
def test_compose_prompt_puts_arc_before_shot() -> None:
    out = art_vid.compose_prompt("The car lands.", "Four friends race.")
    assert out.index("Four friends race.") < out.index("The car lands.")
    assert "STORY CONTEXT" in out and "THIS SHOT" in out


@pytest.mark.parametrize("arc", [None, "", "   "])
def test_compose_prompt_without_arc_is_just_the_shot(arc: str | None) -> None:
    assert art_vid.compose_prompt("  The car lands.  ", arc) == "The car lands."


# ── cost ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "model,res,secs,expected",
    [
        ("veo-3.1-generate-001", "1080p", 8, 3.20),
        ("veo-3.1-generate-001", "4k", 8, 4.80),
        ("veo-3.1-fast-generate-001", "1080p", 8, 0.96),
        ("veo-3.1-lite-generate-001", "720p", 4, 0.20),
        ("veo-3.1-lite-generate-001", "4k", 8, None),  # lite has no 4k tier
        ("unknown-model", "1080p", 8, None),
    ],
)
def test_estimate_video_cost(model: str, res: str, secs: int, expected: float | None) -> None:
    assert art_vid.estimate_video_cost(model, res, secs) == expected


# ── metadata (the revision snapshot) ───────────────────────────────────────
def test_build_metadata_is_a_complete_snapshot(tmp_path: Path) -> None:
    meta = art_vid.build_metadata(
        prompt="ARC\n\nSHOT",
        model="veo-3.1-fast-generate-001",
        timestamp="T",
        duration_seconds=8,
        resolution="1080p",
        aspect="16:9",
        story_arc="ARC",
        story_arc_file=tmp_path / "story.md",
        clip_prompt="SHOT",
        prompt_file=tmp_path / "clip.md",
        start_frame=tmp_path / "a.png",
        end_frame=tmp_path / "b.png",
        negative_prompt="dialogue",
        extra={"config": {"resolution": "1080p"}},
    )
    # The exact text sent AND its two components are all retained, so a revision can
    # change the arc or the shot independently.
    assert meta["prompt"] == "ARC\n\nSHOT"
    assert meta["clip_prompt"] == "SHOT" and meta["story_arc"] == "ARC"
    assert meta["start_frame"].endswith("a.png") and meta["end_frame"].endswith("b.png")
    assert meta["estimated_cost_usd"] == 0.96
    assert meta["kind"] == "video" and meta["config"]["resolution"] == "1080p"


def test_build_metadata_omits_absent_optionals() -> None:
    meta = art_vid.build_metadata(
        prompt="p", model="m", timestamp="T", duration_seconds=8, resolution="720p", aspect="16:9"
    )
    for key in ("story_arc", "prompt_file", "start_frame", "end_frame", "clip_prompt"):
        assert key not in meta
    assert meta["estimated_cost_usd"] is None


# ── config assembly ────────────────────────────────────────────────────────
def test_build_video_config_kwargs_only_includes_what_is_set() -> None:
    kw = art_vid.build_video_config_kwargs(duration_seconds=8, resolution="1080p")
    assert kw == {"number_of_videos": 1, "duration_seconds": 8, "resolution": "1080p"}
    assert "aspect_ratio" not in kw and "negative_prompt" not in kw


def test_build_video_config_kwargs_marks_end_frame() -> None:
    kw = art_vid.build_video_config_kwargs(aspect="16:9", negative_prompt="music", has_end_frame=True)
    assert kw["aspect_ratio"] == "16:9" and kw["negative_prompt"] == "music"
    assert kw["_needs_last_frame"] is True


# ── paths ──────────────────────────────────────────────────────────────────
def test_clip_paths_share_one_stem(tmp_path: Path) -> None:
    paths = art_vid.clip_paths(tmp_path, "clip01")
    assert paths["video"].name == "clip01.mp4"
    assert paths["sidecar"].name == "clip01.json"
    assert paths["first"].name == "clip01.first.png"
    assert paths["last"].name == "clip01.last.png"


# ── ffmpeg extraction (fake runner) ────────────────────────────────────────
def test_extract_frames_runs_two_ffmpeg_passes(tmp_path: Path) -> None:
    if not art_vid.ffmpeg_available():
        pytest.skip("ffmpeg not installed on this host")
    runner = _RecordingRunner()
    video = tmp_path / "c.mp4"
    video.write_bytes(b"fake")
    out = art_vid.extract_frames(video, tmp_path / "c.first.png", tmp_path / "c.last.png", runner=runner)
    assert len(runner.calls) == 2
    assert "-sseof" in runner.calls[1], "last frame must seek from the end"
    assert out["first"].exists() and out["last"].exists()


# ── history ────────────────────────────────────────────────────────────────
def test_read_and_format_history(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "clip01.json").write_text(
        json.dumps(
            {
                "kind": "video",
                "clip_prompt": "slide",
                "model": "veo-3.1-fast-generate-001",
                "estimated_cost_usd": 0.96,
                "duration_seconds": 8,
                "resolution": "1080p",
            }
        ),
        encoding="utf-8",
    )
    # An image sidecar in the same tree must be ignored — the trees are shared.
    (tmp_path / "img.json").write_text(json.dumps({"prompt": "a picture"}), encoding="utf-8")
    items = art_vid.read_history(tmp_path)
    assert len(items) == 1
    text = art_vid.format_history(items)
    assert "$0.96" in text and "Total (1 clips)" in text


def test_format_history_empty() -> None:
    assert art_vid.format_history([]) == "No prior clips found."


def test_format_history_marks_unpriced() -> None:
    text = art_vid.format_history([{"kind": "video", "prompt": "x", "model": "?"}])
    assert "$?" in text and "without a price estimate" in text


# ── CLI ────────────────────────────────────────────────────────────────────
def _gen_ns(**kw: object) -> argparse.Namespace:
    base: dict[str, object] = dict(
        command="generate",
        prompt=None,
        prompt_file=None,
        story_arc=None,
        start_frame=None,
        end_frame=None,
        model=None,
        duration=8,
        resolution="1080p",
        aspect="16:9",
        negative_prompt="dialogue",
        out_dir=Path("clips"),
        name=None,
        dry_run=True,
        verbose=False,
        quiet=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_main_dry_run_composes_and_prices(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    clip = tmp_path / "clip.md"
    clip.write_text("# note\nThe car drifts through the corner.\n", encoding="utf-8")
    arc = tmp_path / "story.md"
    arc.write_text("# arc\nFour friends race a rally car.\n", encoding="utf-8")
    rc = art_vid.main(_gen_ns(prompt_file=clip, story_arc=arc, out_dir=tmp_path, name="clip01"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "$0.96" in out  # fast @1080p x8s
    assert "Four friends race" in out and "drifts through the corner" in out
    assert "STORY CONTEXT" in out


def test_main_requires_a_prompt(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No prompt provided"):
        art_vid.main(_gen_ns(out_dir=tmp_path))


def test_main_inline_prompt_wins(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    clip = tmp_path / "clip.md"
    clip.write_text("from the file\n", encoding="utf-8")
    art_vid.main(_gen_ns(prompt="inline text", prompt_file=clip, out_dir=tmp_path))
    assert "inline text" in capsys.readouterr().out


def test_main_history_dispatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ns = argparse.Namespace(command="history", out_dir=tmp_path, verbose=False, quiet=False)
    assert art_vid.main(ns) == 0
    assert "No prior clips" in capsys.readouterr().out


def test_build_parser_generate_defaults() -> None:
    ns = art_vid.build_parser().parse_args(["generate", "--prompt-file", "p.md"])
    assert ns.command == "generate" and ns.duration == 8 and ns.resolution == "1080p"
    assert "dialogue" in ns.negative_prompt and "music" in ns.negative_prompt


def test_build_parser_keyframe_pair() -> None:
    ns = art_vid.build_parser().parse_args(
        ["generate", "--prompt-file", "p.md", "--start-frame", "a.png", "--end-frame", "b.png", "--model", "standard"]
    )
    assert ns.start_frame == Path("a.png") and ns.end_frame == Path("b.png") and ns.model == "standard"


# NOTE: the live Veo path (generate_clip / _load_image) is a paid network boundary and is
# validated by running the CLI, never from pytest — see art-gen CLAUDE.md ADR-008.

if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))


class _InlineVideo:
    """Vertex-style video: bytes arrive inline on the object."""

    def __init__(self, data: bytes) -> None:
        self.video_bytes = data


def test_save_generated_video_writes_inline_bytes(tmp_path: Path) -> None:
    """Vertex path: bytes are already present, so no download call is needed."""
    out = tmp_path / "c.mp4"
    art_vid.save_generated_video(object(), _InlineVideo(b"MP4DATA"), out)
    assert out.read_bytes() == b"MP4DATA"
