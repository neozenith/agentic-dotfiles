#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest>=8.0",
#   "pytest-cov>=4.0",
#   "Pillow>=10.1.0",
#   "numpy>=1.26.0",
#   "opencv-python>=5.0.0.93",
# ]
# ///
"""Tests for art_pipe.

``opencv-python`` IS a test dependency here (unlike ``rembg`` in the sibling test file):
it is a deterministic, offline library with no model download, so the cv2-backed ops are
tested against the real thing rather than a stand-in. HuggingFace stays out — that
resolver is exercised through an injected real fake.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import art_pipe
import numpy as np
import pytest
from PIL import Image


# ── Fakes (real objects passed through documented seams) ───────────────────
class _FakeHFPipeline:
    """A real callable standing in for a HuggingFace pipeline."""

    def __init__(self, task: str, model: str) -> None:
        self.task, self.model = task, model

    def __call__(self, image: Image.Image, **_: object) -> list[dict[str, Image.Image]]:
        arr = np.asarray(image)
        mask = np.zeros(arr.shape[:2], dtype=np.uint8)
        mask[: arr.shape[0] // 2] = 255
        return [{"mask": Image.fromarray(mask)}]


def _fake_hf_factory():  # noqa: ANN202 - returns the pipeline factory itself
    def _factory(task: str, model: str, **_: object) -> _FakeHFPipeline:
        return _FakeHFPipeline(task, model)

    return _factory


def _cv2():  # noqa: ANN202
    import cv2

    return cv2


def _no_faces(rgb: np.ndarray, params: object, ctx: object) -> list[list[int]]:
    """A real detector that finds nothing — exercises the empty-result path."""
    return []


def _fixed_face(rgb: np.ndarray, params: object, ctx: object) -> list[list[int]]:
    """A real detector returning one known box, so the crop maths is asserted exactly."""
    return [[60, 50, 80, 100]]


def _two_faces(rgb: np.ndarray, params: object, ctx: object) -> list[list[int]]:
    return [[10, 10, 20, 20], [100, 100, 30, 30]]


def _ctx(tmp_path: Path, face_detector: object = None, landmark_detector: object = None) -> art_pipe.OpContext:
    return art_pipe.OpContext(
        base_dir=tmp_path,
        cv2_resolver=_cv2,
        hf_resolver=_fake_hf_factory,
        output_dir=tmp_path / "steps",
        face_detector=face_detector,  # type: ignore[arg-type]
        landmark_detector=landmark_detector,  # type: ignore[arg-type]
    )


def _solid(h: int, w: int, rgba: tuple[int, int, int, int]) -> np.ndarray:
    return np.tile(np.asarray(rgba, dtype=np.uint8), (h, w, 1))


# ── to_rgba ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "arr,expected_alpha",
    [
        (np.zeros((4, 4), dtype=np.uint8), 255),
        (np.zeros((4, 4, 3), dtype=np.uint8), 255),
        (np.full((4, 4, 4), 7, dtype=np.uint8), 7),
    ],
)
def test_to_rgba_normalises_shape(arr: np.ndarray, expected_alpha: int) -> None:
    out = art_pipe.to_rgba(arr)
    assert out.shape == (4, 4, 4)
    assert out.dtype == np.uint8
    assert out[0, 0, 3] == expected_alpha


def test_to_rgba_scales_float_masks() -> None:
    out = art_pipe.to_rgba(np.ones((2, 2), dtype=np.float32))
    assert out[0, 0, 0] == 255


def test_to_rgba_clips_out_of_range_floats() -> None:
    out = art_pipe.to_rgba(np.full((2, 2), 300.0, dtype=np.float32))
    assert out[0, 0, 0] == 255


# ── colour selection ───────────────────────────────────────────────────────
def test_color_distance_is_zero_at_target() -> None:
    arr = _solid(2, 2, (10, 20, 30, 255))
    assert art_pipe.color_distance_to(arr, (10, 20, 30))[0, 0] == pytest.approx(0.0)


def test_color_mask_selects_within_tolerance() -> None:
    arr = _solid(2, 4, (245, 158, 11, 255))
    arr[:, 2:] = (14, 14, 16, 255)
    mask = art_pipe.color_mask(arr, (245, 158, 11), 30)
    assert mask[0, 0] == 255 and mask[0, 3] == 0


# ── geometry ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "anchor,expected",
    [
        ("center", (40, 40)),
        ("top_left", (50, 50)),
        ("bottom_right", (30, 30)),
    ],
)
def test_resolve_anchor_box(anchor: str, expected: tuple[int, int]) -> None:
    assert art_pipe.resolve_anchor_box((100, 100), (20, 20), (0.5, 0.5), anchor) == expected


def test_resolve_anchor_box_unknown_anchor_defaults_to_center() -> None:
    assert art_pipe.resolve_anchor_box((100, 100), (20, 20), (0.5, 0.5), "nonsense") == (40, 40)


def test_alpha_paste_blends_opaque_layer() -> None:
    base = _solid(10, 10, (0, 0, 0, 255))
    layer = _solid(4, 4, (255, 0, 0, 255))
    out = art_pipe.alpha_paste(base, layer, 3, 3)
    assert tuple(out[4, 4, :3]) == (255, 0, 0)
    assert tuple(out[0, 0, :3]) == (0, 0, 0)


def test_alpha_paste_honours_opacity() -> None:
    base = _solid(6, 6, (0, 0, 0, 255))
    layer = _solid(2, 2, (255, 255, 255, 255))
    out = art_pipe.alpha_paste(base, layer, 2, 2, opacity=0.5)
    assert 120 <= int(out[2, 2, 0]) <= 135


def test_alpha_paste_clips_fully_offcanvas_layer() -> None:
    base = _solid(5, 5, (1, 2, 3, 255))
    out = art_pipe.alpha_paste(base, _solid(2, 2, (9, 9, 9, 255)), 50, 50)
    assert tuple(out[0, 0, :3]) == (1, 2, 3)


def test_feather_ellipse_mask_is_opaque_centre_transparent_corner() -> None:
    mask = art_pipe.feather_ellipse_mask(21, 21, 0.2)
    assert mask[10, 10] == 255
    assert mask[0, 0] == 0


def test_feather_ellipse_at_tracks_an_offset_centre() -> None:
    """The opaque zone follows the requested centre, not the box centre."""
    mask = art_pipe.feather_ellipse_at(40, 40, cx=8, cy=8, rx=6, ry=6, feather=0.25)
    assert mask[8, 8] == 255  # opaque at the requested centre
    assert mask[8, 34] == 0  # far side of the box is transparent


# ── placeholder / constant resolution ──────────────────────────────────────
def test_resolve_placeholders_substitutes_image_and_buffers() -> None:
    frame = art_pipe.Frame(_solid(3, 3, (1, 1, 1, 255)), {"m": np.ones((3, 3), np.uint8)})
    out = art_pipe.resolve_placeholders({"a": "$image", "b": ["$buf:m", 5], "c": "plain"}, frame)
    assert out["a"].shape == (3, 3, 3)
    assert out["b"][0].shape == (3, 3)
    assert out["b"][1] == 5 and out["c"] == "plain"


def test_resolve_placeholders_unknown_buffer_raises() -> None:
    frame = art_pipe.Frame(_solid(2, 2, (0, 0, 0, 255)))
    with pytest.raises(KeyError, match="unknown buffer"):
        art_pipe.resolve_placeholders("$buf:missing", frame)


def test_resolve_constants_maps_cv2_names() -> None:
    cv2 = _cv2()
    assert art_pipe.resolve_constants("cv2.INTER_CUBIC", cv2) == cv2.INTER_CUBIC
    assert art_pipe.resolve_constants(["cv2.INTER_CUBIC"], cv2) == [cv2.INTER_CUBIC]
    assert art_pipe.resolve_constants({"k": "cv2.INTER_CUBIC"}, cv2) == {"k": cv2.INTER_CUBIC}
    assert art_pipe.resolve_constants(7, cv2) == 7


def test_resolve_constants_unknown_name_raises() -> None:
    with pytest.raises(AttributeError, match="no constant"):
        art_pipe.resolve_constants("cv2.NOT_A_REAL_FLAG", _cv2())


# ── Frame ──────────────────────────────────────────────────────────────────
def test_frame_with_rgb_preserves_alpha() -> None:
    frame = art_pipe.Frame(_solid(3, 3, (0, 0, 0, 128)))
    out = frame.with_rgb(_solid(3, 3, (5, 6, 7, 255))[:, :, :3])
    assert tuple(out.image[0, 0]) == (5, 6, 7, 128)
    assert out.alpha[0, 0] == 128


# ── registry ───────────────────────────────────────────────────────────────
def test_registry_contains_dynamic_and_curated_ops() -> None:
    for name in (
        "cv2",
        "hf",
        "overlay",
        "inpaint",
        "face-crop",
        "color-replace",
        "seamless-clone",
        "perspective-overlay",
        "face-align",
    ):
        assert name in art_pipe.OPS


def test_list_ops_renders_every_registered_op() -> None:
    text = art_pipe.list_ops()
    assert all(name in text for name in art_pipe.OPS)


# ── curated ops ────────────────────────────────────────────────────────────
def test_color_replace_recolours_and_stores_mask(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(4, 4, (245, 158, 11, 255)))
    out = art_pipe.OPS["color-replace"][1](
        frame, {"target": [245, 158, 11], "to": [14, 14, 16], "tolerance": 20}, _ctx(tmp_path)
    )
    assert tuple(out.image[0, 0, :3]) == (14, 14, 16)
    assert out.buffers["color_mask"][0, 0] == 255


def test_overlay_scales_and_places_layer(tmp_path: Path) -> None:
    layer = tmp_path / "layer.png"
    Image.fromarray(_solid(20, 20, (255, 0, 0, 255))).save(layer)
    frame = art_pipe.Frame(_solid(100, 100, (0, 0, 0, 255)))
    out = art_pipe.OPS["overlay"][1](frame, {"layer": "layer.png", "at": [0.5, 0.5], "scale": 0.5}, _ctx(tmp_path))
    assert tuple(out.image[50, 50, :3]) == (255, 0, 0)
    assert tuple(out.image[5, 5, :3]) == (0, 0, 0)


def test_overlay_rotation_and_width_from_buffer(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(60, 60, (0, 0, 0, 255)), {"lay": _solid(10, 10, (0, 255, 0, 255))})
    out = art_pipe.OPS["overlay"][1](
        frame, {"buffer": "lay", "at": [0.5, 0.5], "width": 20, "rotate": 45.0}, _ctx(tmp_path)
    )
    assert out.image[30, 30, 1] == 255


def test_resize_by_scale_and_absolute(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(10, 20, (1, 1, 1, 255)))
    assert art_pipe.OPS["resize"][1](frame, {"scale": 0.5}, _ctx(tmp_path)).image.shape[:2] == (5, 10)
    assert art_pipe.OPS["resize"][1](frame, {"width": 4, "height": 3}, _ctx(tmp_path)).image.shape[:2] == (3, 4)


def test_crop_pixel_and_normalised(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(20, 20, (1, 1, 1, 255)))
    assert art_pipe.OPS["crop"][1](frame, {"box": [2, 2, 5, 5]}, _ctx(tmp_path)).image.shape[:2] == (5, 5)
    out = art_pipe.OPS["crop"][1](frame, {"box": [0, 0, 0.5, 0.5], "normalized": True}, _ctx(tmp_path))
    assert out.image.shape[:2] == (10, 10)


def test_inpaint_heals_a_colour_region(tmp_path: Path) -> None:
    arr = _solid(40, 40, (30, 30, 30, 255))
    arr[18:22, 18:22] = (245, 158, 11, 255)
    out = art_pipe.OPS["inpaint"][1](art_pipe.Frame(arr), {"target": [245, 158, 11], "tolerance": 30}, _ctx(tmp_path))
    assert int(out.image[20, 20, 0]) < 120  # the orange block was healed toward the surround
    assert out.buffers["inpaint_mask"].shape == (40, 40)


def test_inpaint_from_explicit_buffer_and_ns_algo(tmp_path: Path) -> None:
    arr = _solid(40, 40, (30, 30, 30, 255))
    arr[18:22, 18:22] = (250, 250, 250, 255)
    mask = np.zeros((40, 40), np.uint8)
    mask[18:22, 18:22] = 255
    out = art_pipe.OPS["inpaint"][1](
        art_pipe.Frame(arr, {"m": mask}), {"buffer": "m", "algo": "ns", "dilate": 0}, _ctx(tmp_path)
    )
    assert int(out.image[20, 20, 0]) < 200


def test_seamless_clone_transfers_layer_texture(tmp_path: Path) -> None:
    """Poisson blending copies GRADIENTS, so this asserts texture, not colour.

    A flat patch cloned onto a flat background correctly leaves the pixels unchanged;
    asserting a colour shift there would be asserting the algorithm is broken.
    """
    textured = _solid(20, 20, (200, 40, 40, 255))
    textured[::2, :] = (40, 200, 40, 255)  # stripes give the clone a gradient to carry
    layer = tmp_path / "l.png"
    Image.fromarray(textured).save(layer)
    frame = art_pipe.Frame(_solid(80, 80, (30, 30, 30, 255)))
    out = art_pipe.OPS["seamless-clone"][1](
        frame, {"layer": "l.png", "at": [0.5, 0.5], "mode": "normal"}, _ctx(tmp_path)
    )
    assert out.image[35:45, 35:45, :3].astype(int).std() > 5, "clone should carry the stripes"
    assert tuple(out.image[2, 2, :3]) == (30, 30, 30), "outside the clone must be untouched"


def test_seamless_clone_scales_layer(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(80, 80, (30, 30, 30, 255)), {"l": _solid(40, 40, (200, 40, 40, 255))})
    out = art_pipe.OPS["seamless-clone"][1](frame, {"buffer": "l", "at": [0.5, 0.5], "scale": 0.5}, _ctx(tmp_path))
    assert out.image.shape[:2] == (80, 80)


def test_face_crop_raises_when_detector_finds_nothing(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(64, 64, (10, 10, 10, 255)))
    with pytest.raises(RuntimeError, match="no faces"):
        art_pipe.OPS["face-crop"][1](frame, {}, _ctx(tmp_path, face_detector=_no_faces))


def test_face_crop_cuts_a_feathered_oval(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(200, 200, (200, 180, 170, 255)))
    out = art_pipe.OPS["face-crop"][1](frame, {"pad": 0.1, "feather": 0.3}, _ctx(tmp_path, _fixed_face))
    assert out.meta["faces"] == [[60, 50, 80, 100]]
    assert out.image[0, 0, 3] == 0  # corner feathered away
    assert out.image[out.image.shape[0] // 2, out.image.shape[1] // 2, 3] == 255


def test_face_crop_accepts_an_explicit_box(tmp_path: Path) -> None:
    """An explicit box bypasses detection entirely — the manual escape hatch."""
    frame = art_pipe.Frame(_solid(120, 120, (10, 200, 10, 255)))
    out = art_pipe.OPS["face-crop"][1](frame, {"box": [20, 20, 40, 40], "pad": 0.0}, _ctx(tmp_path))
    assert out.image.shape[:2] == (40, 40)


def test_face_crop_index_selects_among_several(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(200, 200, (200, 180, 170, 255)))
    out = art_pipe.OPS["face-crop"][1](frame, {"index": 1, "pad": 0.0}, _ctx(tmp_path, _two_faces))
    assert out.image.shape[:2] == (30, 30)


def test_face_crop_keeps_face_opaque_when_box_clamps_to_edge(tmp_path: Path) -> None:
    """A face against the frame edge must still yield an opaque head with a feathered rim.

    Regression: a box-filling ellipse drifts off an edge-clamped crop, giving a hard-edged,
    background-bleeding cut-out (seen on a portrait where the face filled the frame).
    """
    frame = art_pipe.Frame(_solid(200, 200, (200, 180, 170, 255)))
    # Face box hard against the top-left corner; pad will clamp on two sides.
    detector = lambda rgb, params, ctx: [[0, 0, 90, 110]]  # noqa: E731
    out = art_pipe.OPS["face-crop"][1](frame, {"pad": 0.5, "feather": 0.3}, _ctx(tmp_path, detector))
    # Centre of the detected face stays fully opaque...
    assert out.image[55, 45, 3] == 255
    # ...and the padded far corner of the cut feathers toward transparent.
    assert out.image[-1, -1, 3] < 128


def test_face_crop_index_clamps_past_the_end(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(200, 200, (200, 180, 170, 255)))
    out = art_pipe.OPS["face-crop"][1](frame, {"index": 99, "pad": 0.0}, _ctx(tmp_path, _two_faces))
    assert out.image.shape[:2] == (30, 30)


# ── perspective-overlay ─────────────────────────────────────────────────────
def test_perspective_overlay_warps_layer_onto_quad(tmp_path: Path) -> None:
    layer = tmp_path / "l.png"
    Image.fromarray(_solid(40, 40, (255, 0, 0, 255))).save(layer)
    frame = art_pipe.Frame(_solid(200, 200, (0, 0, 0, 255)))
    # A quad in the upper-left region; the red layer should land inside it, black outside.
    out = art_pipe.OPS["perspective-overlay"][1](
        frame, {"layer": "l.png", "dst": [[20, 20], [120, 30], [110, 120], [30, 110]]}, _ctx(tmp_path)
    )
    assert tuple(out.image[65, 65, :3]) == (255, 0, 0)
    assert tuple(out.image[180, 180, :3]) == (0, 0, 0)


# ── face-align ───────────────────────────────────────────────────────────────
def _landmarks(cx: float, cy: float, s: float = 20.0) -> list[list[float]]:
    """Five plausible face landmarks around a centre (eyes, nose, mouth corners)."""
    return [[cx - s, cy - s], [cx + s, cy - s], [cx, cy], [cx - s, cy + s], [cx + s, cy + s]]


def test_face_align_warps_source_onto_target(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    face = _solid(120, 120, (20, 200, 40, 255))
    Image.fromarray(face).save(src)

    def detector(rgb, params, ctx):  # noqa: ANN001, ANN202
        # Source portrait: face centred; target frame: face lower-right — distinct poses.
        if rgb.shape[0] == 120:
            return [{"box": [30, 30, 60, 60], "landmarks": _landmarks(60, 60, 15)}]
        return [{"box": [120, 120, 80, 80], "landmarks": _landmarks(160, 160, 22)}]

    frame = art_pipe.Frame(_solid(240, 240, (0, 0, 30, 255)))
    out = art_pipe.OPS["face-align"][1](
        frame, {"source": "src.png", "blend": "alpha"}, _ctx(tmp_path, landmark_detector=detector)
    )
    # The green source face should now sit near the target centre (160,160)...
    assert out.image[160, 160, 1] > 120
    # ...and the far corner stays the original background.
    assert tuple(out.image[5, 5, :3]) == (0, 0, 30)


def test_face_align_seamless_blend_path(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    Image.fromarray(_solid(120, 120, (210, 180, 160, 255))).save(src)

    def detector(rgb, params, ctx):  # noqa: ANN001, ANN202
        if rgb.shape[0] == 120:
            return [{"box": [30, 30, 60, 60], "landmarks": _landmarks(60, 60, 15)}]
        return [{"box": [80, 80, 80, 80], "landmarks": _landmarks(120, 120, 20)}]

    frame = art_pipe.Frame(_solid(240, 240, (40, 40, 40, 255)))
    out = art_pipe.OPS["face-align"][1](
        frame,
        {"source": "src.png", "blend": "seamless", "near": [0.5, 0.5]},
        _ctx(tmp_path, landmark_detector=detector),
    )
    assert out.image.shape == (240, 240, 4)


def test_face_align_raises_without_target(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    Image.fromarray(_solid(60, 60, (1, 2, 3, 255))).save(src)
    frame = art_pipe.Frame(_solid(100, 100, (0, 0, 0, 255)))
    out_detector = lambda rgb, params, ctx: []  # noqa: E731
    with pytest.raises(RuntimeError, match="no target face"):
        art_pipe.OPS["face-align"][1](frame, {"source": "src.png"}, _ctx(tmp_path, landmark_detector=out_detector))


def test_face_align_raises_without_source_face(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    Image.fromarray(_solid(60, 60, (1, 2, 3, 255))).save(src)

    def detector(rgb, params, ctx):  # noqa: ANN001, ANN202
        return [{"box": [10, 10, 20, 20], "landmarks": _landmarks(20, 20, 5)}] if rgb.shape[0] == 100 else []

    frame = art_pipe.Frame(_solid(100, 100, (0, 0, 0, 255)))
    with pytest.raises(RuntimeError, match="no face found in source"):
        art_pipe.OPS["face-align"][1](frame, {"source": "src.png"}, _ctx(tmp_path, landmark_detector=detector))


def test_pick_target_by_index_and_near() -> None:
    targets = [{"box": [0, 0, 20, 20]}, {"box": [100, 100, 20, 20]}]
    assert art_pipe._pick_target(targets, {"index": 1}, (200, 200))["box"][0] == 100
    assert art_pipe._pick_target(targets, {"near": [0.05, 0.05]}, (200, 200))["box"][0] == 0


# ── annotate-faces / quad-handles (folded in from repeated tmp helpers) ─────
def test_annotate_faces_draws_boxes_and_names(tmp_path: Path) -> None:
    def detector(rgb, params, ctx):  # noqa: ANN001, ANN202
        return [
            {"box": [20, 20, 40, 40], "landmarks": _landmarks(40, 40, 8)},
            {"box": [120, 30, 40, 40], "landmarks": _landmarks(140, 50, 8)},
        ]

    frame = art_pipe.Frame(_solid(200, 200, (10, 10, 10, 255)))
    out = art_pipe.OPS["annotate-faces"][1](
        frame, {"names": ["Ada", "Grace"]}, _ctx(tmp_path, landmark_detector=detector)
    )
    assert out.meta["faces"] == [[20, 20, 40, 40], [120, 30, 40, 40]]
    # The two faces get DIFFERENT palette colours, so identity reads at a glance.
    assert out.image[20, 40, 0] != out.image[30, 140, 0] or out.image[20, 40, 2] != out.image[30, 140, 2]
    # Something was drawn over the flat base.
    assert out.image[:, :, :3].std() > 1.0


def test_annotate_faces_without_names_falls_back_to_index(tmp_path: Path) -> None:
    detector = lambda rgb, params, ctx: [{"box": [10, 10, 30, 30], "landmarks": _landmarks(25, 25, 5)}]  # noqa: E731
    frame = art_pipe.Frame(_solid(100, 100, (0, 0, 0, 255)))
    out = art_pipe.OPS["annotate-faces"][1](frame, {}, _ctx(tmp_path, landmark_detector=detector))
    assert out.meta["faces"] == [[10, 10, 30, 30]]


def test_quad_handles_marks_every_corner(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(200, 200, (0, 0, 0, 255)))
    quad = [[40, 40], [160, 50], [150, 150], [30, 140]]
    out = art_pipe.OPS["quad-handles"][1](frame, {"quad": quad, "label": "LOGO"}, _ctx(tmp_path))
    # Each named corner carries a filled handle dot in the accent colour.
    for x, y in quad:
        assert out.image[y, x, 0] > 100, f"no handle drawn at {(x, y)}"


# ── dynamic ops ────────────────────────────────────────────────────────────
def test_cv2_op_calls_arbitrary_function(tmp_path: Path) -> None:
    arr = _solid(20, 20, (0, 0, 0, 255))
    arr[10, 10] = (255, 255, 255, 255)
    out = art_pipe.OPS["cv2"][1](
        art_pipe.Frame(arr), {"fn": "GaussianBlur", "args": ["$image", [5, 5], 0]}, _ctx(tmp_path)
    )
    assert 0 < int(out.image[10, 11, 0]) < 255  # the spike was spread into its neighbour


def test_cv2_op_into_buffer_and_tuple_result(tmp_path: Path) -> None:
    arr = _solid(10, 10, (200, 200, 200, 255))
    out = art_pipe.OPS["cv2"][1](
        art_pipe.Frame(arr),
        {"fn": "threshold", "args": ["$image", 100, 255, "cv2.THRESH_BINARY"], "into": "t"},
        _ctx(tmp_path),
    )
    assert "t" in out.buffers


def test_cv2_op_unknown_function_raises(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(4, 4, (0, 0, 0, 255)))
    with pytest.raises(AttributeError, match="no callable"):
        art_pipe.OPS["cv2"][1](frame, {"fn": "definitelyNotAnOpenCVFunction"}, _ctx(tmp_path))


def test_cv2_op_result_of_different_size_replaces_frame(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(20, 20, (10, 10, 10, 255)))
    out = art_pipe.OPS["cv2"][1](
        art_pipe.Frame(frame.image), {"fn": "resize", "args": ["$image", [8, 6]]}, _ctx(tmp_path)
    )
    assert out.image.shape[:2] == (6, 8)


def test_hf_op_runs_pipeline_and_absorbs_mask(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(8, 8, (0, 0, 0, 255)))
    out = art_pipe.OPS["hf"][1](
        frame, {"task": "image-segmentation", "model": "fake/model", "into": "seg"}, _ctx(tmp_path)
    )
    assert out.buffers["seg"].shape == (8, 8)
    assert out.buffers["seg"][0, 0] == 255


def test_hf_payload_indexes_list_and_key() -> None:
    payload = [{"mask": 1}, {"mask": 2}]
    assert art_pipe._hf_payload(payload, {"index": 1, "key": "mask"}) == 2


def test_first_array_picks_the_image_from_a_multi_return() -> None:
    """cv2.threshold returns (level, image); element 0 is a scalar, not the picture."""
    img = np.zeros((3, 3), np.uint8)
    assert art_pipe._first_array((100.0, img)) is img
    assert art_pipe._first_array(img) is img
    assert art_pipe._first_array((1.0, 2.0)) == 1.0


# ── engine ─────────────────────────────────────────────────────────────────
def test_run_pipeline_applies_steps_in_order(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(10, 10, (245, 158, 11, 255)))
    steps = [
        {"op": "color-replace", "target": [245, 158, 11], "to": [0, 0, 0], "tolerance": 20},
        {"op": "resize", "scale": 0.5},
    ]
    out, record = art_pipe.run_pipeline(frame, steps, _ctx(tmp_path))
    assert tuple(out.image[0, 0, :3]) == (0, 0, 0)
    assert out.image.shape[:2] == (5, 5)
    assert [e["op"] for e in record] == ["color-replace", "resize"]


def test_run_pipeline_emits_intermediates(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    frame = art_pipe.Frame(_solid(8, 8, (1, 2, 3, 255)))
    _, record = art_pipe.run_pipeline(frame, [{"op": "resize", "scale": 0.5}], ctx, emit_steps=True)
    assert (ctx.output_dir / "00_input.png").exists()
    assert (ctx.output_dir / "01_resize.png").exists()
    readme = art_pipe.write_steps_readme(ctx.output_dir, record)
    assert "01_resize.png" in readme.read_text(encoding="utf-8")


def test_run_pipeline_unknown_op_names_the_registry(tmp_path: Path) -> None:
    frame = art_pipe.Frame(_solid(4, 4, (0, 0, 0, 255)))
    with pytest.raises(ValueError, match="unknown op"):
        art_pipe.run_pipeline(frame, [{"op": "teleport"}], _ctx(tmp_path))


def test_write_steps_readme_truncates_long_params(tmp_path: Path) -> None:
    record = [{"index": 1, "op": "x", "params": {"k": "y" * 400}, "file": "a.png"}]
    text = art_pipe.write_steps_readme(tmp_path, record).read_text(encoding="utf-8")
    assert "..." in text


# ── spec + IO ──────────────────────────────────────────────────────────────
def test_load_spec_reads_valid_file(tmp_path: Path) -> None:
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"input": "a.png", "steps": []}), encoding="utf-8")
    assert art_pipe.load_spec(spec)["steps"] == []


@pytest.mark.parametrize("payload", ['{"input": "a.png"}', '{"steps": {}}', "[]"])
def test_load_spec_rejects_malformed(tmp_path: Path, payload: str) -> None:
    spec = tmp_path / "s.json"
    spec.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        art_pipe.load_spec(spec)


def test_load_and_save_image_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "a.png"
    art_pipe.save_image(_solid(4, 4, (9, 8, 7, 255)), path)
    assert tuple(art_pipe.load_image(path)[0, 0]) == (9, 8, 7, 255)


def test_write_sidecar_records_payload(tmp_path: Path) -> None:
    path = art_pipe.write_sidecar(tmp_path / "s.json", {"command": "pipeline"})
    assert json.loads(path.read_text(encoding="utf-8"))["command"] == "pipeline"


def test_timestamp_now_is_sortable() -> None:
    assert len(art_pipe.timestamp_now()) == 15


# ── CLI ────────────────────────────────────────────────────────────────────
def test_main_ops_lists_registry(capsys: pytest.CaptureFixture[str]) -> None:
    ns = argparse.Namespace(command="ops")
    assert art_pipe.main(ns, cv2_resolver=_cv2, hf_resolver=_fake_hf_factory) == 0
    assert "overlay" in capsys.readouterr().out


def test_main_run_executes_spec(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "in.png"
    art_pipe.save_image(_solid(20, 20, (245, 158, 11, 255)), src)
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "input": str(src),
                "output": str(tmp_path / "out.png"),
                "base_dir": str(tmp_path),
                "steps": [{"op": "color-replace", "target": [245, 158, 11], "to": [0, 0, 0], "tolerance": 20}],
            }
        ),
        encoding="utf-8",
    )
    ns = argparse.Namespace(
        command="run",
        spec=spec,
        input=None,
        output=None,
        steps=True,
        output_dir=tmp_path / "steps",
        verbose=False,
        quiet=False,
    )
    assert art_pipe.main(ns, cv2_resolver=_cv2, hf_resolver=_fake_hf_factory) == 0
    out = capsys.readouterr().out
    assert "saved:" in out and "steps:" in out
    assert tuple(art_pipe.load_image(tmp_path / "out.png")[0, 0, :3]) == (0, 0, 0)
    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))["command"] == "pipeline"


def test_main_run_honours_cli_overrides(tmp_path: Path) -> None:
    src = tmp_path / "in.png"
    art_pipe.save_image(_solid(8, 8, (1, 1, 1, 255)), src)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"input": "missing.png", "steps": []}), encoding="utf-8")
    ns = argparse.Namespace(
        command="run",
        spec=spec,
        input=src,
        output=tmp_path / "o.png",
        steps=False,
        output_dir=tmp_path / "steps",
        verbose=False,
        quiet=False,
    )
    assert art_pipe.main(ns, cv2_resolver=_cv2, hf_resolver=_fake_hf_factory) == 0
    assert (tmp_path / "o.png").exists()


def test_build_parser_run_defaults() -> None:
    ns = art_pipe.build_parser().parse_args(["run", "spec.json"])
    assert ns.command == "run" and ns.steps is False
    assert ns.output_dir == art_pipe.DEFAULT_OUTPUT_DIR


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
