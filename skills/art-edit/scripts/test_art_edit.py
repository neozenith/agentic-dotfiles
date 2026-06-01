#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest>=8.0",
#   "pytest-cov>=4.0",
#   "Pillow>=10.1.0",
#   "numpy>=1.26.0",
# ]
# ///
"""Tests for art_edit.

The machine-vision math is pure and tested directly on tiny synthetic arrays. The
model-backed orchestrators (remove-bg/segment/steps/composite) are tested by injecting a
real *fake segmenter* through the documented seam — no ``unittest.mock``, no ~170 MB
U2-Net download. An opt-in integration test (``ART_EDIT_RUN_MODEL=1``) runs the real
rembg segmenter end-to-end.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import art_edit
import numpy as np
import pytest
from PIL import Image


# ── Fakes & fixtures (real objects, not mocks) ─────────────────────────────
def _fake_segmenter(img: Image.Image) -> Image.Image:
    """A deterministic stand-in for U2-Net: keep the centre quadrant as foreground."""
    arr = np.array(img.convert("RGBA"))
    h, w = arr.shape[:2]
    alpha = np.zeros((h, w), dtype=np.uint8)
    alpha[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4] = 255
    arr[:, :, 3] = alpha
    return Image.fromarray(arr)


def _sample_array(n: int = 40) -> np.ndarray:
    """White RGBA canvas with a dark square and a warm (amber) stripe — exercises every signal."""
    arr = np.full((n, n, 4), 255, dtype=np.uint8)
    arr[10:30, 10:30, :3] = (30, 32, 46)  # dark charcoal block (darkness + edges)
    arr[15:20, 32:38, :3] = (244, 162, 97)  # amber stripe (warmth)
    return arr


@pytest.fixture
def sample_png(tmp_path: Path) -> Path:
    path = tmp_path / "in.png"
    Image.fromarray(_sample_array()).save(path)
    return path


# ── Pure primitives ────────────────────────────────────────────────────────
def test_auto_crop_trims_to_content() -> None:
    arr = np.zeros((20, 20, 4), dtype=np.uint8)
    arr[8:12, 8:12, 3] = 255
    cropped = art_edit.auto_crop(arr, pad=1)
    assert cropped.shape[0] < 20 and cropped.shape[1] < 20


def test_auto_crop_all_transparent_returns_input() -> None:
    arr = np.zeros((10, 10, 4), dtype=np.uint8)
    assert art_edit.auto_crop(arr).shape == (10, 10, 4)


def test_color_distance_white_and_black() -> None:
    arr = np.zeros((1, 2, 4), dtype=np.uint8)
    arr[0, 0, :3] = 255  # white → 0
    arr[0, 1, :3] = 0  # black → 255
    dist = art_edit.color_distance(arr)
    assert dist[0, 0] == 0 and dist[0, 1] == 255


def test_color_signal_ramp() -> None:
    max_dist = np.array([[0.0, 100.0]], dtype=np.float32)
    sig = art_edit.color_signal(max_dist, white_tolerance=15, edge_softness=2)
    assert sig[0, 0] == 0.0 and sig[0, 1] == 1.0


def test_scharr_edges_flat_vs_edge() -> None:
    flat = np.full((8, 8, 4), 200, dtype=np.uint8)
    assert float(art_edit.scharr_edges(flat).max()) == 0.0
    edged = _sample_array(20)
    assert float(art_edit.scharr_edges(edged).max()) > 0.0


def test_dilate_edge_mask_grows_region() -> None:
    edge = np.zeros((20, 20), dtype=np.float32)
    edge[10, 10] = 1.0
    mask = art_edit.dilate_edge_mask(edge, threshold=0.5, size=5)
    assert mask.sum() > 1.0  # dilation expanded the single hot pixel


def test_element_alpha_channels() -> None:
    arr = _sample_array(40)
    max_dist = art_edit.color_distance(arr)
    alpha = art_edit.element_alpha(arr, max_dist, grey_reference=30)
    assert alpha[0, 0] == 0.0  # white corner
    assert alpha[20, 20] > 0.5  # dark block (darkness)
    assert alpha[17, 34] > 0.5  # amber stripe (warmth)


def test_sigmoid_sharpen_off_and_on() -> None:
    mask = np.array([[0.2, 0.45, 0.55, 0.8]], dtype=np.float32)
    assert np.array_equal(art_edit.sigmoid_sharpen(mask, 0), mask)
    sharp = art_edit.sigmoid_sharpen(mask, 12)
    assert sharp.min() <= 0.05 and sharp.max() >= 0.95


def test_combined_matte_keys() -> None:
    arr = _sample_array(40)
    u2 = np.zeros(arr.shape[:2], dtype=np.float32)
    union, signals = art_edit.combined_matte(arr, u2, white_tolerance=15, edge_softness=2, grey_reference=30)
    assert set(signals) == {"u2net", "color", "edge_scharr", "edge_dilated", "edge_refined", "combined"}
    assert union.shape == arr.shape[:2]


# ── Positioning + text ─────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "anchor,expected",
    [("top_left", (0, 0)), ("center", (50 - 10, 50 - 5)), ("bottom_right", (100 - 20, 100 - 10))],
)
def test_resolve_position(anchor: str, expected: tuple[int, int]) -> None:
    pos = {"top_left": (0.0, 0.0), "center": (0.5, 0.5), "bottom_right": (1.0, 1.0)}[anchor]
    assert art_edit.resolve_position(pos, anchor, 100, 100, 20, 10) == expected


def test_load_font_and_render_text() -> None:
    font = art_edit.load_font(None, 16)
    img = art_edit.render_text("AB", font, (10, 20, 30, 255))
    assert img.mode == "RGBA" and img.width > 0 and img.height > 0


# ── sidecar / config ───────────────────────────────────────────────────────
def test_write_sidecar(tmp_path: Path) -> None:
    side = art_edit.write_sidecar(
        tmp_path / "x.json",
        command="remove-bg",
        input_path=tmp_path / "in.png",
        params={"mode": "global"},
        outputs=["x.png"],
    )
    data = json.loads(side.read_text(encoding="utf-8"))
    assert data["command"] == "remove-bg" and data["params"]["mode"] == "global" and data["outputs"] == ["x.png"]


def test_load_config(tmp_path: Path) -> None:
    assert art_edit.load_config(None) == {}
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps({"wordmark": {"text": "HELLO"}}), encoding="utf-8")
    assert art_edit.load_config(cfg_path)["wordmark"]["text"] == "HELLO"


# ── remove-bg ──────────────────────────────────────────────────────────────
def test_remove_bg_model_with_fake(sample_png: Path, tmp_path: Path) -> None:
    out = art_edit.remove_background(sample_png, tmp_path / "o.png", mode="model", segmenter=_fake_segmenter)
    assert out.exists()
    side = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert side["command"] == "remove-bg" and side["params"]["mode"] == "model"
    assert np.array(Image.open(out))[:, :, 3].min() == 0  # has transparency


def test_remove_bg_global(sample_png: Path, tmp_path: Path) -> None:
    out = art_edit.remove_background(sample_png, tmp_path / "g.png", mode="global", tolerance=20)
    assert out.exists() and out.with_suffix(".json").exists()


def test_remove_bg_default_output_path(sample_png: Path) -> None:
    out = art_edit.remove_background(sample_png, mode="global")
    assert out.name == "in_nobg.png" and out.exists()


def test_remove_bg_unknown_mode(sample_png: Path) -> None:
    with pytest.raises(ValueError, match="Unknown mode"):
        art_edit.remove_background(sample_png, mode="bogus")


# ── segment / steps ────────────────────────────────────────────────────────
def test_segment_layers(sample_png: Path, tmp_path: Path) -> None:
    final = art_edit.segment_layers(sample_png, tmp_path / "seg", segmenter=_fake_segmenter)
    assert final.name == "final.png" and final.exists()
    assert (tmp_path / "seg" / "segment.json").exists()
    assert (tmp_path / "seg" / "mask_combined.png").exists()


def test_generate_pipeline_steps(sample_png: Path, tmp_path: Path) -> None:
    readme = art_edit.generate_pipeline_steps(sample_png, tmp_path / "steps", sharpen=12, segmenter=_fake_segmenter)
    assert readme.name == "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "Image Processing Pipeline" in text and "Cumulative" in text
    assert (tmp_path / "steps" / "steps.json").exists()
    assert (tmp_path / "steps" / "01_mask_u2net.png").exists()
    assert (tmp_path / "steps" / "08_result_final.png").exists()


def test_steps_sharpen_off(sample_png: Path, tmp_path: Path) -> None:
    readme = art_edit.generate_pipeline_steps(sample_png, tmp_path / "s0", sharpen=0, segmenter=_fake_segmenter)
    assert readme.exists()


# ── wordmark / composite ───────────────────────────────────────────────────
def test_add_wordmark(sample_png: Path, tmp_path: Path) -> None:
    out = art_edit.add_wordmark(sample_png, tmp_path / "wm.png", text="ABCDEF", split_at=3, canvas_size=(80, 40))
    assert out.exists()
    side = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert side["command"] == "wordmark" and side["params"]["text"] == "ABCDEF"


def test_add_wordmark_with_config(sample_png: Path, tmp_path: Path) -> None:
    cfg = {"wordmark": {"text": "ZZ", "split_at": 1}, "canvas": {"width": 60, "height": 30}}
    out = art_edit.add_wordmark(sample_png, tmp_path / "wm2.png", config=cfg)
    assert out.exists()


def test_composite_pipeline(sample_png: Path, tmp_path: Path) -> None:
    out = art_edit.composite_pipeline(sample_png, tmp_path / "final.png", text="ABCDEF", segmenter=_fake_segmenter)
    assert out.exists() and out.with_suffix(".json").exists()


# ── main dispatch + parser ─────────────────────────────────────────────────
def _ns(**kw: object) -> argparse.Namespace:
    base: dict[str, object] = {"input": Path("."), "output": None, "config": None, "verbose": False, "quiet": False}
    base.update(kw)
    return argparse.Namespace(**base)


def test_main_remove_bg(sample_png: Path, tmp_path: Path) -> None:
    ns = _ns(
        command="remove-bg", input=sample_png, output=tmp_path / "m.png", mode="global", tolerance=30, edge_softness=2
    )
    assert art_edit.main(ns) == 0 and (tmp_path / "m.png").exists()


def test_main_segment_default_dir(sample_png: Path) -> None:
    ns = _ns(command="segment", input=sample_png, white_tolerance=15, grey_ref=30, sharpen=12, output_dir=None)
    assert art_edit.main(ns, segmenter=_fake_segmenter) == 0
    assert sample_png.with_name("in_segment").is_dir()


def test_main_steps(sample_png: Path, tmp_path: Path) -> None:
    ns = _ns(command="steps", input=sample_png, white_tolerance=15, grey_ref=30, sharpen=12, output_dir=tmp_path / "st")
    assert art_edit.main(ns, segmenter=_fake_segmenter) == 0
    assert (tmp_path / "st" / "README.md").exists()


def test_main_wordmark(sample_png: Path, tmp_path: Path) -> None:
    ns = _ns(
        command="wordmark",
        input=sample_png,
        output=tmp_path / "w.png",
        text="ABCDEF",
        font=None,
        font_size=None,
        split_at=3,
        canvas=(70.0, 35.0),
    )
    assert art_edit.main(ns) == 0 and (tmp_path / "w.png").exists()


def test_main_composite(sample_png: Path, tmp_path: Path) -> None:
    ns = _ns(command="composite", input=sample_png, output=tmp_path / "f.png", text="ABCDEF")
    assert art_edit.main(ns, segmenter=_fake_segmenter) == 0 and (tmp_path / "f.png").exists()


def test_main_missing_input(tmp_path: Path) -> None:
    ns = _ns(command="remove-bg", input=tmp_path / "nope.png", mode="global", tolerance=30, edge_softness=2)
    with pytest.raises(FileNotFoundError):
        art_edit.main(ns)


def test_parse_pos_ok_and_bad() -> None:
    assert art_edit._parse_pos("0.5,0.25") == (0.5, 0.25)
    with pytest.raises(argparse.ArgumentTypeError):
        art_edit._parse_pos("0.5")


def test_build_parser_remove_bg() -> None:
    ns = art_edit.build_parser().parse_args(["remove-bg", "in.png", "--mode", "global"])
    assert ns.command == "remove-bg" and ns.mode == "global"


# NOTE: Real-model (U2-Net via rembg) validation is performed via the CLI (see README.md),
# NOT via pytest. The test PEP-723 deps intentionally exclude rembg/onnxruntime (the fake
# segmenter covers the model path here); running the real model is a CLI concern.
# See CLAUDE.md ADR-010.


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
