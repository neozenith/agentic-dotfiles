#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "Pillow>=10.1.0",
#   "numpy>=1.26.0",
#   "opencv-python>=5.0.0.93",
# ]
# ///
"""art-pipe — a declarative, extensible transform pipeline for images.

Where ``art_edit.py`` offers a fixed set of commands, this runs an ordered **spec** of
named ops over one image, so any combination of transforms can be composed without new
code. The design goal is reach, not a curated menu:

  curated ops   overlay, color-replace, inpaint, face-crop, resize, crop, alpha-matte …
  ``cv2`` op    calls ANY function in the OpenCV (5.x) namespace by name
  ``hf`` op     runs ANY HuggingFace pipeline by task + model id

Every run can emit numbered intermediate PNGs plus a README table (``--steps``), and
writes a JSON sidecar containing the exact spec, so a pipeline is reproducible and its
working-out is inspectable.

Spec format (JSON)::

    {"input": "a.png", "output": "b.png", "steps": [
        {"op": "color-replace", "target": [245, 158, 11], "to": [14, 14, 16]},
        {"op": "overlay", "layer": "logo.png", "at": [0.4, 0.55], "scale": 0.2},
        {"op": "cv2", "fn": "GaussianBlur", "args": ["$image", [3, 3], 0]}
    ]}

``$image`` and ``$buf:NAME`` inside ``cv2`` arguments are placeholders resolved to the
current frame and to named buffers — that indirection is what lets an arbitrary OpenCV
function participate without a hand-written wrapper.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ── Configuration ──────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

DEFAULT_OUTPUT_DIR = Path("art/pipe")
IMAGE_REF = "$image"
BUFFER_PREFIX = "$buf:"

# A module resolver is injected so the dynamic ops can be exercised offline with a real
# stand-in module. Production passes the genuine `cv2` / transformers pipeline factory.
ModuleResolver = Callable[[], Any]
FaceDetector = Callable[[np.ndarray, Mapping[str, Any], "OpContext"], list[list[int]]]
# Richer detector used by face-align: each face is {"box": [x,y,w,h], "landmarks": [[x,y]*5]}.
FaceLandmarkDetector = Callable[[np.ndarray, Mapping[str, Any], "OpContext"], list[dict[str, Any]]]

# OpenCV 5.0 removed the Haar cascades, so face detection is YuNet (a small ONNX model).
YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
DEFAULT_YUNET_PATH = Path("tmp/models/face_detection_yunet_2023mar.onnx")

# Stable, high-contrast per-person colours for identity annotation (RGB).
ANNOTATE_PALETTE = [(34, 211, 238), (244, 114, 182), (74, 222, 128), (253, 224, 71), (248, 113, 113)]
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


# ── Frame: the value that flows through a pipeline ─────────────────────────
@dataclass
class Frame:
    """The pipeline's working state.

    ``image`` is always RGBA uint8 so every op has one predictable layout. ``buffers``
    holds named side-products (masks, extracted layers) that a later op can reference,
    and ``meta`` holds non-image results such as detected boxes.
    """

    image: np.ndarray
    buffers: dict[str, np.ndarray] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def rgb(self) -> np.ndarray:
        """The colour channels only — what most OpenCV functions expect."""
        return self.image[:, :, :3]

    @property
    def alpha(self) -> np.ndarray:
        return self.image[:, :, 3]

    def with_rgb(self, rgb: np.ndarray) -> Frame:
        """A new frame carrying replacement colour channels, alpha preserved."""
        out = self.image.copy()
        out[:, :, :3] = np.asarray(rgb, dtype=np.uint8)[:, :, :3]
        return Frame(out, dict(self.buffers), dict(self.meta))


# ── Pure helpers (no IO, no cv2 — fully unit-tested) ───────────────────────
def timestamp_now() -> str:
    """Filesystem-sortable timestamp, e.g. ``20260601_143501``."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def to_rgba(arr: np.ndarray) -> np.ndarray:
    """Coerce any 2-D mask / RGB / RGBA array to RGBA uint8.

    Normalising once at the boundary means no op has to branch on channel count —
    the single most common source of shape bugs in a chain of image transforms.
    """
    a = np.asarray(arr)
    if a.dtype != np.uint8:
        a = np.clip(a, 0, 255).astype(np.uint8) if a.max() > 1.0 else (a * 255).astype(np.uint8)
    if a.ndim == 2:
        a = np.dstack([a, a, a])
    if a.shape[2] == 3:
        a = np.dstack([a, np.full(a.shape[:2], 255, dtype=np.uint8)])
    return np.ascontiguousarray(a[:, :, :4])


def color_distance_to(arr: np.ndarray, target: Sequence[int]) -> np.ndarray:
    """Per-pixel Euclidean RGB distance to ``target`` — the basis of colour selection."""
    rgb = np.asarray(arr, dtype=np.float32)[:, :, :3]
    tgt = np.asarray(target, dtype=np.float32)[:3]
    return np.sqrt(((rgb - tgt) ** 2).sum(axis=2)).astype(np.float32)


def color_mask(arr: np.ndarray, target: Sequence[int], tolerance: float) -> np.ndarray:
    """Binary uint8 mask (0/255) of pixels within ``tolerance`` of ``target``."""
    return (color_distance_to(arr, target) <= float(tolerance)).astype(np.uint8) * 255


def resolve_anchor_box(
    base_shape: tuple[int, int],
    layer_shape: tuple[int, int],
    at: Sequence[float],
    anchor: str = "center",
) -> tuple[int, int]:
    """Top-left pixel where a layer lands, from a normalised position + anchor.

    Normalised coordinates keep a spec resolution-independent: the same pipeline runs
    against a 1K draft and a 4K master without editing a single number.
    """
    bh, bw = base_shape[:2]
    lh, lw = layer_shape[:2]
    cx, cy = float(at[0]) * bw, float(at[1]) * bh
    fx, fy = {
        "center": (0.5, 0.5),
        "top_left": (0.0, 0.0),
        "top_right": (1.0, 0.0),
        "bottom_left": (0.0, 1.0),
        "bottom_right": (1.0, 1.0),
    }.get(anchor, (0.5, 0.5))
    return int(round(cx - lw * fx)), int(round(cy - lh * fy))


def alpha_paste(base: np.ndarray, layer: np.ndarray, x: int, y: int, opacity: float = 1.0) -> np.ndarray:
    """Alpha-composite ``layer`` onto ``base`` at (x, y), clipped to the canvas.

    Clipping rather than erroring is deliberate: a spec written against one frame is
    routinely reused on a differently-cropped one, and a partly off-canvas decal is a
    normal outcome, not a failure.
    """
    out = to_rgba(base).copy()
    lay = to_rgba(layer)
    bh, bw = out.shape[:2]
    lh, lw = lay.shape[:2]

    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(bw, x + lw), min(bh, y + lh)
    if x0 >= x1 or y0 >= y1:
        return out

    sub = lay[y0 - y : y1 - y, x0 - x : x1 - x]
    a = (sub[:, :, 3:4].astype(np.float32) / 255.0) * float(opacity)
    region = out[y0:y1, x0:x1]
    out[y0:y1, x0:x1, :3] = (sub[:, :, :3] * a + region[:, :, :3] * (1 - a)).astype(np.uint8)
    out[y0:y1, x0:x1, 3] = np.maximum(region[:, :, 3], (sub[:, :, 3] * float(opacity)).astype(np.uint8))
    return out


def feather_ellipse_at(h: int, w: int, cx: float, cy: float, rx: float, ry: float, feather: float = 0.15) -> np.ndarray:
    """A soft-edged elliptical alpha (uint8) centred at (cx, cy) with radii (rx, ry).

    Positioning the ellipse explicitly — rather than assuming it fills the box — is what
    keeps the opaque zone on the **face** when the padded crop box was clamped to the image
    edge. A box-filling ellipse drifts off a face that sits near the source frame's border,
    which is exactly the case that produced a hard-edged, background-bleeding cut-out.
    """
    yy, xx = np.mgrid[0:h, 0:w]
    ny = (yy - cy) / max(1e-6, ry)
    nx = (xx - cx) / max(1e-6, rx)
    r = np.sqrt(nx**2 + ny**2)
    f = max(1e-6, float(feather))
    alpha = np.clip((1.0 - r) / f, 0.0, 1.0)
    return (alpha * 255).astype(np.uint8)


def feather_ellipse_mask(h: int, w: int, feather: float = 0.15) -> np.ndarray:
    """A soft-edged elliptical alpha (uint8) filling an h×w box (centred, box-sized radii)."""
    return feather_ellipse_at(h, w, (w - 1) / 2.0, (h - 1) / 2.0, (w - 1) / 2.0, (h - 1) / 2.0, feather)


def resolve_placeholders(value: Any, frame: Frame) -> Any:
    """Substitute ``$image`` / ``$buf:NAME`` anywhere inside a spec argument tree.

    This is the seam that makes the ``cv2`` op universal: the spec names an arbitrary
    function and marks which of its arguments should receive live pipeline data.
    """
    if isinstance(value, str):
        if value == IMAGE_REF:
            return frame.rgb
        if value.startswith(BUFFER_PREFIX):
            key = value[len(BUFFER_PREFIX) :]
            if key not in frame.buffers:
                raise KeyError(f"pipeline references unknown buffer {key!r}")
            return frame.buffers[key]
        return value
    if isinstance(value, list):
        return [resolve_placeholders(v, frame) for v in value]
    if isinstance(value, dict):
        return {k: resolve_placeholders(v, frame) for k, v in value.items()}
    return value


def resolve_constants(value: Any, module: Any) -> Any:
    """Turn ``"cv2.INTER_CUBIC"``-style strings into the module's real constant.

    Spec files are JSON, which has no way to express an enum; without this, every
    OpenCV flag would have to be hand-copied as a magic integer into the spec.
    """
    if isinstance(value, str) and value.startswith("cv2."):
        name = value.split(".", 1)[1]
        if not hasattr(module, name):
            raise AttributeError(f"cv2 has no constant {name!r}")
        return getattr(module, name)
    if isinstance(value, list):
        return [resolve_constants(v, module) for v in value]
    if isinstance(value, dict):
        return {k: resolve_constants(v, module) for k, v in value.items()}
    return value


# ── Op registry ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class OpContext:
    """Everything an op needs besides the frame itself.

    The three collaborators are injected rather than imported at use-site so the whole
    op surface can run offline against real stand-ins (see ADR-003's lens).
    """

    base_dir: Path
    cv2_resolver: ModuleResolver
    hf_resolver: ModuleResolver
    output_dir: Path
    face_detector: FaceDetector | None = None
    landmark_detector: FaceLandmarkDetector | None = None


OpHandler = Callable[[Frame, Mapping[str, Any], OpContext], Frame]
OPS: dict[str, tuple[str, OpHandler]] = {}


def op(name: str, summary: str) -> Callable[[OpHandler], OpHandler]:
    """Register a pipeline op under ``name``.

    A registry (rather than an if/elif ladder) is what makes the surface extensible:
    adding a transform is one decorated function, and ``list_ops`` documents it for free.
    """

    def _register(fn: OpHandler) -> OpHandler:
        OPS[name] = (summary, fn)
        return fn

    return _register


def list_ops() -> str:
    """Render the registry as a table so the dynamic surface is discoverable."""
    width = max(len(n) for n in OPS)
    lines = [f"{'op':<{width}}  description", f"{'-' * width}  {'-' * 11}"]
    lines += [f"{name:<{width}}  {OPS[name][0]}" for name in sorted(OPS)]
    return "\n".join(lines)


# ── Curated ops ────────────────────────────────────────────────────────────
@op("color-replace", "Recolour every pixel within tolerance of a target RGB")
def _op_color_replace(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    target = params["target"]
    to = params["to"]
    tolerance = float(params.get("tolerance", 60))
    mask = color_mask(frame.image, target, tolerance)
    out = frame.image.copy()
    out[mask > 0, :3] = np.asarray(to, dtype=np.uint8)[:3]
    result = Frame(out, dict(frame.buffers), dict(frame.meta))
    result.buffers[str(params.get("into", "color_mask"))] = mask
    return result


@op("overlay", "Composite a PNG layer at a normalised position, with scale/rotation")
def _op_overlay(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    layer = _load_layer(frame, params, ctx)
    scale = float(params.get("scale", 1.0))
    if scale != 1.0 or "width" in params:
        target_w = int(params["width"]) if "width" in params else max(1, int(layer.shape[1] * scale))
        ratio = target_w / max(1, layer.shape[1])
        layer = _resize_rgba(layer, target_w, max(1, int(layer.shape[0] * ratio)))
    rotate = float(params.get("rotate", 0.0))
    if rotate:
        layer = to_rgba(np.asarray(Image.fromarray(layer).rotate(rotate, expand=True, resample=Image.BICUBIC)))
    at = params.get("at", [0.5, 0.5])
    x, y = resolve_anchor_box(frame.image.shape[:2], layer.shape[:2], at, str(params.get("anchor", "center")))
    return Frame(
        alpha_paste(frame.image, layer, x, y, float(params.get("opacity", 1.0))),
        dict(frame.buffers),
        dict(frame.meta),
    )


@op("resize", "Resize the frame to an absolute width/height or a scale factor")
def _op_resize(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    h, w = frame.image.shape[:2]
    if "scale" in params:
        w, h = max(1, int(w * float(params["scale"]))), max(1, int(h * float(params["scale"])))
    else:
        w, h = int(params.get("width", w)), int(params.get("height", h))
    return Frame(_resize_rgba(frame.image, w, h), dict(frame.buffers), dict(frame.meta))


@op("crop", "Crop to a pixel box [x, y, w, h] or a normalised box")
def _op_crop(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    h, w = frame.image.shape[:2]
    box = params["box"]
    if bool(params.get("normalized", False)):
        x, y, bw, bh = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
    else:
        x, y, bw, bh = (int(v) for v in box)
    x, y = max(0, x), max(0, y)
    return Frame(frame.image[y : min(h, y + bh), x : min(w, x + bw)].copy(), dict(frame.buffers), dict(frame.meta))


@op("inpaint", "Heal a region using cv2.inpaint, masked by colour or an explicit buffer")
def _op_inpaint(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    cv2 = ctx.cv2_resolver()
    if "buffer" in params:
        mask = frame.buffers[str(params["buffer"])]
    else:
        mask = color_mask(frame.image, params["target"], float(params.get("tolerance", 60)))
    dilate = int(params.get("dilate", 3))
    if dilate > 0:
        mask = cv2.dilate(mask, np.ones((dilate, dilate), np.uint8), iterations=1)
    algo = cv2.INPAINT_TELEA if str(params.get("algo", "telea")) == "telea" else cv2.INPAINT_NS
    healed = cv2.inpaint(
        np.ascontiguousarray(frame.rgb), np.ascontiguousarray(mask), float(params.get("radius", 3)), algo
    )
    result = frame.with_rgb(healed)
    result.buffers[str(params.get("into", "inpaint_mask"))] = mask
    return result


@op("seamless-clone", "Poisson-blend a layer onto the frame so it inherits local lighting")
def _op_seamless_clone(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    cv2 = ctx.cv2_resolver()
    layer = _load_layer(frame, params, ctx)
    if "width" in params or "scale" in params:
        target_w = int(params["width"]) if "width" in params else max(1, int(layer.shape[1] * float(params["scale"])))
        ratio = target_w / max(1, layer.shape[1])
        layer = _resize_rgba(layer, target_w, max(1, int(layer.shape[0] * ratio)))

    at = params.get("at", [0.5, 0.5])
    h, w = frame.image.shape[:2]
    centre = (int(float(at[0]) * w), int(float(at[1]) * h))
    mode = {"normal": cv2.NORMAL_CLONE, "mixed": cv2.MIXED_CLONE, "mono": cv2.MONOCHROME_TRANSFER}[
        str(params.get("mode", "mixed"))
    ]
    mask = np.where(layer[:, :, 3] > 8, 255, 0).astype(np.uint8)
    blended = cv2.seamlessClone(
        np.ascontiguousarray(layer[:, :, :3]), np.ascontiguousarray(frame.rgb), mask, centre, mode
    )
    return frame.with_rgb(blended)


@op("perspective-overlay", "Warp a layer onto a 4-corner quad (a decal on a foreshortened panel)")
def _op_perspective_overlay(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    """Map a rectangular layer onto an arbitrary quad on the base via a homography.

    A flat ``overlay`` looks pasted-on when the target surface (a car door in a 3/4 view)
    recedes; warping the decal to the door's actual four corners makes it sit *in* the
    scene. ``dst`` is the destination quad in TL, TR, BR, BL order, in base pixels.
    """
    cv2 = ctx.cv2_resolver()
    layer = _load_layer(frame, params, ctx)
    lh, lw = layer.shape[:2]
    src = np.asarray([[0, 0], [lw, 0], [lw, lh], [0, lh]], dtype=np.float32)
    dst = np.asarray(params["dst"], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    h, w = frame.image.shape[:2]
    warped = cv2.warpPerspective(
        np.ascontiguousarray(layer), matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0)
    )
    out = alpha_paste(frame.image, warped, 0, 0, float(params.get("opacity", 1.0)))
    return Frame(out, dict(frame.buffers), dict(frame.meta))


@op("face-align", "Warp a source portrait onto a target face by 5-point landmark similarity")
def _op_face_align(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    """Landmark-align a source face onto a detected target face, then blend.

    YuNet returns five landmarks (eyes, nose, mouth corners) alongside each box, so a
    partial-affine (rotation + uniform scale + translation) fit maps the source portrait
    onto the target's pose without any extra model. The warped face is composited only
    inside a feathered ellipse over the target box, so hair and background stay native.
    """
    cv2 = ctx.cv2_resolver()
    detect = ctx.landmark_detector or _yunet_faces_full
    targets = detect(frame.rgb, params, ctx)
    if not targets:
        raise RuntimeError("face-align: no target face detected in the frame")
    tgt = _pick_target(targets, params, frame.image.shape[:2])

    source_rgba = load_image(ctx.base_dir / str(params["source"]))
    sources = detect(source_rgba[:, :, :3], params, ctx)
    if not sources:
        raise RuntimeError(f"face-align: no face found in source {params['source']!r}")
    src_lmk = np.asarray(sources[0]["landmarks"], dtype=np.float32)
    dst_lmk = np.asarray(tgt["landmarks"], dtype=np.float32)

    matrix, _ = cv2.estimateAffinePartial2D(src_lmk, dst_lmk)
    if matrix is None:
        raise RuntimeError("face-align: could not fit a transform between the landmark sets")
    h, w = frame.image.shape[:2]
    warped = cv2.warpAffine(np.ascontiguousarray(source_rgba), matrix, (w, h))

    bx, by, bw, bh = tgt["box"]
    grow = float(params.get("grow", 0.15))
    oval = feather_ellipse_at(
        h,
        w,
        bx + bw / 2.0,
        by + bh / 2.0,
        bw / 2.0 * (1 + grow),
        bh / 2.0 * (1 + grow),
        float(params.get("feather", 0.4)),
    )
    warped[:, :, 3] = (warped[:, :, 3].astype(np.float32) * (oval / 255.0)).astype(np.uint8)

    if str(params.get("blend", "seamless")) == "seamless":
        mask = np.where(warped[:, :, 3] > 8, 255, 0).astype(np.uint8)
        if int(mask.sum()) == 0:
            return frame
        centre = (int(bx + bw / 2), int(by + bh / 2))
        blended = cv2.seamlessClone(
            np.ascontiguousarray(warped[:, :, :3]), np.ascontiguousarray(frame.rgb), mask, centre, cv2.NORMAL_CLONE
        )
        return frame.with_rgb(blended)
    return Frame(alpha_paste(frame.image, warped, 0, 0), dict(frame.buffers), dict(frame.meta))


def _pick_target(
    targets: Sequence[Mapping[str, Any]], params: Mapping[str, Any], shape: tuple[int, int]
) -> Mapping[str, Any]:
    """Choose which detected face to replace: an explicit near-point, else an index."""
    if "near" in params:
        h, w = shape
        px, py = float(params["near"][0]) * w, float(params["near"][1]) * h
        return min(
            targets, key=lambda t: (t["box"][0] + t["box"][2] / 2 - px) ** 2 + (t["box"][1] + t["box"][3] / 2 - py) ** 2
        )
    ordered = sorted(targets, key=lambda t: t["box"][0])
    return ordered[min(int(params.get("index", 0)), len(ordered) - 1)]


@op("face-crop", "Detect faces (YuNet) and emit a feathered oval cut-out")
def _op_face_crop(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    detector = ctx.face_detector or _yunet_faces
    boxes = [[int(v) for v in params["box"]]] if "box" in params else detector(frame.rgb, params, ctx)
    if not boxes:
        raise RuntimeError("face-crop found no faces; lower 'score_threshold' or pass an explicit 'box'")

    pad = float(params.get("pad", 0.35))
    feather = float(params.get("feather", 0.25))
    h, w = frame.image.shape[:2]
    index = int(params.get("index", 0))
    x, y, fw, fh = boxes[min(index, len(boxes) - 1)]
    px, py = int(fw * pad), int(fh * pad)
    x0, y0 = max(0, x - px), max(0, y - py)
    x1, y1 = min(w, x + fw + px), min(h, y + fh + py)

    cut = to_rgba(frame.image[y0:y1, x0:x1]).copy()
    # Centre the oval on the FACE within the (possibly edge-clamped) cut, not on the cut box.
    # Radii span the face plus its requested padding, so the whole head stays opaque and only
    # the padding margin feathers — correct even when one side of the box was clamped away.
    oval = feather_ellipse_at(
        cut.shape[0],
        cut.shape[1],
        cx=x + fw / 2.0 - x0,
        cy=y + fh / 2.0 - y0,
        rx=fw / 2.0 + px,
        ry=fh / 2.0 + py,
        feather=feather,
    )
    cut[:, :, 3] = (cut[:, :, 3].astype(np.float32) * (oval / 255.0)).astype(np.uint8)
    result = Frame(cut, dict(frame.buffers), dict(frame.meta))
    result.meta["faces"] = boxes
    return result


@op("annotate-faces", "Draw detected faces (box + landmarks + name) — the identity-agreement artifact")
def _op_annotate_faces(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    """Overlay each detected face with a box, its 5 landmarks, and a per-person label.

    This is the *agreement* artifact from `resources/learned/collaboration_workflows.md`:
    emit it and have the human confirm who is who **before** any face edit. ``names`` maps
    the left-to-right detection order to people; each gets a stable colour so the mapping
    reads at a glance across every frame.
    """
    detect = ctx.landmark_detector or _yunet_faces_full
    faces = sorted(detect(frame.rgb, params, ctx), key=lambda f: f["box"][0])
    names = [str(n) for n in params.get("names", [])]
    palette = [tuple(c) for c in params.get("colors", [])] or ANNOTATE_PALETTE

    img = Image.fromarray(to_rgba(frame.image)).convert("RGB")
    draw = ImageDraw.Draw(img)
    size = max(14, int(img.height * 0.022))
    font = _load_font(size)
    for i, face in enumerate(faces):
        colour = tuple(int(v) for v in palette[i % len(palette)])
        x, y, w, h = (int(v) for v in face["box"])
        draw.rectangle([x, y, x + w, y + h], outline=colour, width=max(2, size // 8))
        for lx, ly in face.get("landmarks", []):
            r = max(3, size // 5)
            draw.ellipse([lx - r, ly - r, lx + r, ly + r], fill=colour, outline=(0, 0, 0))
        label = f"{i}:{names[i]}" if i < len(names) else str(i)
        draw.text((x + 4, max(0, y - size - 8)), label, fill=colour, font=font, stroke_width=3, stroke_fill=(0, 0, 0))

    result = Frame(to_rgba(np.asarray(img)), dict(frame.buffers), dict(frame.meta))
    result.meta["faces"] = [f["box"] for f in faces]
    return result


@op("quad-handles", "Draw a placement quad with labelled TL/TR/BR/BL corners + centre")
def _op_quad_handles(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    """Preview a placement quad with named handles, so alignment can be nudged by corner.

    Gives the human concrete things to reference — "pull TR down", "rotate -4°" — instead of
    dictating raw perspective coordinates (see the nudge vocabulary in the learned notes).
    """
    quad = [[int(p[0]), int(p[1])] for p in params["quad"]]
    colour = tuple(int(v) for v in params.get("color", (240, 150, 40)))
    img = Image.fromarray(to_rgba(frame.image)).convert("RGB")
    draw = ImageDraw.Draw(img)
    size = max(14, int(img.height * 0.02))
    font = _load_font(size)

    draw.polygon([tuple(p) for p in quad], outline=colour, width=max(2, size // 7))
    cx = sum(p[0] for p in quad) // 4
    cy = sum(p[1] for p in quad) // 4
    draw.line([(cx - size, cy), (cx + size, cy)], fill=colour, width=3)
    draw.line([(cx, cy - size), (cx, cy + size)], fill=colour, width=3)
    for point, name in zip(quad, ("TL", "TR", "BR", "BL")):
        r = max(4, size // 3)
        draw.ellipse([point[0] - r, point[1] - r, point[0] + r, point[1] + r], fill=colour, outline=(0, 0, 0))
        draw.text(
            (point[0] + r + 2, point[1] - size), name, fill=colour, font=font, stroke_width=3, stroke_fill=(0, 0, 0)
        )
    if params.get("label"):
        draw.text((cx, cy + size), str(params["label"]), fill=colour, font=font, stroke_width=3, stroke_fill=(0, 0, 0))
    return Frame(to_rgba(np.asarray(img)), dict(frame.buffers), dict(frame.meta))


@op("cv2", "Call ANY OpenCV function by name; $image / $buf:NAME inject live data")
def _op_cv2(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    cv2 = ctx.cv2_resolver()
    fn_name = str(params["fn"])
    fn = getattr(cv2, fn_name, None)
    if fn is None or not callable(fn):
        raise AttributeError(f"cv2 has no callable {fn_name!r}")
    args = resolve_constants(resolve_placeholders(list(params.get("args", [IMAGE_REF])), frame), cv2)
    kwargs = resolve_constants(resolve_placeholders(dict(params.get("kwargs", {})), frame), cv2)
    result = fn(*args, **kwargs)
    return _absorb_result(frame, _first_array(result), params)


@op("hf", "Run ANY HuggingFace pipeline by task + model id")
def _op_hf(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> Frame:
    factory = ctx.hf_resolver()
    pipe = factory(task=str(params["task"]), model=str(params["model"]), **dict(params.get("init", {})))
    result = pipe(Image.fromarray(to_rgba(frame.image)), **dict(params.get("call", {})))
    return _absorb_result(frame, _hf_payload(result, params), params)


def _hf_payload(result: Any, params: Mapping[str, Any]) -> Any:
    """Pull the image/mask out of a HuggingFace pipeline's varied return shapes.

    Task outputs differ wildly (a list of dicts for segmentation, a bare image for
    depth), so the spec may name a ``key``/``index`` rather than the skill guessing.
    """
    if isinstance(result, list):
        result = result[int(params.get("index", 0))]
    if isinstance(result, dict):
        result = result[str(params.get("key", "mask"))]
    return result


def _first_array(result: Any) -> Any:
    """Pick the image out of an OpenCV multi-return.

    Many cv2 functions return ``(scalar, image)`` — ``threshold`` returns the chosen
    level first, ``findContours`` returns contours first. Taking element 0 blindly hands
    a scalar to the compositor, so select the first genuinely array-shaped member.
    """
    if not isinstance(result, tuple):
        return result
    for item in result:
        arr = np.asarray(item)
        if arr.ndim >= 2:
            return item
    return result[0]


def _absorb_result(frame: Frame, result: Any, params: Mapping[str, Any]) -> Frame:
    """Route an op's raw output into the frame image or into a named buffer."""
    arr = np.asarray(result if not isinstance(result, Image.Image) else np.asarray(result))
    into = params.get("into")
    if into:
        buffers = dict(frame.buffers)
        buffers[str(into)] = arr if arr.ndim == 2 else arr[:, :, 0]
        return Frame(frame.image.copy(), buffers, dict(frame.meta))
    if arr.ndim == 2:
        return Frame(to_rgba(arr), dict(frame.buffers), dict(frame.meta))
    if arr.shape[:2] != frame.image.shape[:2]:
        return Frame(to_rgba(arr), dict(frame.buffers), dict(frame.meta))
    return frame.with_rgb(arr)


# ── Small IO/shape utilities ───────────────────────────────────────────────
def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """A truetype face if the host has one, else Pillow's built-in — labels must always draw."""
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:  # pragma: no cover - depends on host fonts
            continue
    return ImageFont.load_default(size)  # pragma: no cover - only on a font-less host


def _resize_rgba(arr: np.ndarray, width: int, height: int) -> np.ndarray:
    """Pillow-based resize so the core needs no cv2 for the common path."""
    img = Image.fromarray(to_rgba(arr)).resize((max(1, width), max(1, height)), Image.LANCZOS)
    return to_rgba(np.asarray(img))


def _load_layer(frame: Frame, params: Mapping[str, Any], ctx: OpContext) -> np.ndarray:
    """Resolve an op's layer from a file path or a named buffer."""
    if "buffer" in params:
        return to_rgba(frame.buffers[str(params["buffer"])])
    return load_image(ctx.base_dir / str(params["layer"]))


def ensure_yunet_model(dest: Path) -> Path:  # pragma: no cover - network fetch, validated via the CLI
    """Download the YuNet face-detection ONNX (~350 KB) if it isn't cached yet.

    OpenCV 5.0 removed ``CascadeClassifier`` outright, so YuNet is the supported
    detector — and unlike Haar it is a model file, which must be fetched once. A missing
    model is a loud failure, never a silent fall back to "no faces found".
    """
    if dest.is_file():
        return dest
    import urllib.request

    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("fetching YuNet face model → %s", dest)
    with urllib.request.urlopen(YUNET_URL) as resp:
        if resp.status != 200:
            raise RuntimeError(f"fetching {YUNET_URL}: HTTP {resp.status}")
        dest.write_bytes(resp.read())
    return dest


def _yunet_faces(  # pragma: no cover - needs the real model; validated via the CLI
    rgb: np.ndarray, params: Mapping[str, Any], ctx: OpContext
) -> list[list[int]]:
    """Detect faces with OpenCV 5's YuNet, returning ``[x, y, w, h]`` boxes."""
    cv2 = ctx.cv2_resolver()
    model = ensure_yunet_model(Path(str(params.get("model", DEFAULT_YUNET_PATH))))
    h, w = rgb.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(model), "", (w, h), float(params.get("score_threshold", 0.7)), 0.3, 5000)
    _, faces = detector.detect(np.ascontiguousarray(rgb[:, :, ::-1]))
    if faces is None:
        return []
    return [[int(f[0]), int(f[1]), int(f[2]), int(f[3])] for f in faces]


def _yunet_faces_full(  # pragma: no cover - needs the real model; validated via the CLI
    rgb: np.ndarray, params: Mapping[str, Any], ctx: OpContext
) -> list[dict[str, Any]]:
    """Detect faces AND their five landmarks with YuNet, sorted largest-first.

    Each YuNet row is ``[x, y, w, h, (lx, ly)×5, score]``; the landmarks are right eye,
    left eye, nose tip, right mouth corner, left mouth corner — exactly the anchor set a
    partial-affine face alignment needs, at no extra model cost.
    """
    cv2 = ctx.cv2_resolver()
    model = ensure_yunet_model(Path(str(params.get("model", DEFAULT_YUNET_PATH))))
    h, w = rgb.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(model), "", (w, h), float(params.get("score_threshold", 0.6)), 0.3, 5000)
    _, faces = detector.detect(np.ascontiguousarray(rgb[:, :, ::-1]))
    if faces is None:
        return []
    out: list[dict[str, Any]] = []
    for f in sorted(faces, key=lambda r: -(r[2] * r[3])):
        out.append(
            {
                "box": [int(f[0]), int(f[1]), int(f[2]), int(f[3])],
                "landmarks": [[float(f[4 + 2 * i]), float(f[5 + 2 * i])] for i in range(5)],
            }
        )
    return out


def load_image(path: Path) -> np.ndarray:
    """Read any image file as RGBA uint8."""
    with Image.open(path) as img:
        return to_rgba(np.asarray(img.convert("RGBA")))


def save_image(arr: np.ndarray, path: Path) -> Path:
    """Write an RGBA array as PNG, creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(to_rgba(arr)).save(path)
    return path


def write_sidecar(path: Path, payload: Mapping[str, Any]) -> Path:
    """Record how an output was produced, next to the output."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


# ── Default resolvers (the only heavy imports; deferred per ADR-004) ───────
def _default_cv2() -> Any:  # pragma: no cover - import boundary, validated via the CLI
    import cv2

    return cv2


def _default_hf() -> Any:  # pragma: no cover - import boundary, validated via the CLI
    from transformers import pipeline

    return pipeline


# ── The engine ─────────────────────────────────────────────────────────────
def run_pipeline(
    frame: Frame,
    steps: Sequence[Mapping[str, Any]],
    ctx: OpContext,
    *,
    emit_steps: bool = False,
) -> tuple[Frame, list[dict[str, Any]]]:
    """Apply every step in order, optionally writing each intermediate to disk.

    The step log is returned rather than printed so the caller owns presentation — and
    so a failing step can be reported with its index and params intact.
    """
    record: list[dict[str, Any]] = []
    if emit_steps:
        save_image(frame.image, ctx.output_dir / "00_input.png")
        record.append({"index": 0, "op": "input", "file": "00_input.png"})

    for i, step in enumerate(steps, start=1):
        name = str(step.get("op", ""))
        if name not in OPS:
            raise ValueError(f"step {i}: unknown op {name!r}. Known ops: {', '.join(sorted(OPS))}")
        params = {k: v for k, v in step.items() if k != "op"}
        log.info("step %d: %s %s", i, name, json.dumps(params, default=str)[:160])
        frame = OPS[name][1](frame, params, ctx)
        entry: dict[str, Any] = {"index": i, "op": name, "params": params}
        if emit_steps:
            fname = f"{i:02d}_{name.replace('-', '_')}.png"
            save_image(frame.image, ctx.output_dir / fname)
            entry["file"] = fname
        record.append(entry)
    return frame, record


def write_steps_readme(output_dir: Path, record: Sequence[Mapping[str, Any]]) -> Path:
    """A markdown contact sheet of the intermediates — the pipeline's working-out."""
    lines = ["# Pipeline steps", "", "| # | op | preview | params |", "|---|----|---------|--------|"]
    for entry in record:
        preview = f"![]({entry['file']})" if entry.get("file") else ""
        params = json.dumps(entry.get("params", {}), default=str)
        params = params if len(params) <= 120 else params[:117] + "..."
        lines.append(f"| {entry['index']} | `{entry['op']}` | {preview} | `{params}` |")
    path = output_dir / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_spec(path: Path) -> dict[str, Any]:
    """Read and validate a pipeline spec file."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or "steps" not in spec:
        raise ValueError(f"{path}: spec must be an object with a 'steps' list")
    if not isinstance(spec["steps"], list):
        raise ValueError(f"{path}: 'steps' must be a list")
    return spec


# ── CLI ────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="art_pipe.py",
        description="Run a declarative pipeline of image transforms (OpenCV + HuggingFace).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.set_defaults(func=None)
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Execute a pipeline spec against an image")
    run.add_argument("spec", type=Path, help="Pipeline spec JSON")
    run.add_argument("--input", type=Path, default=None, help="Override the spec's input image")
    run.add_argument("--output", type=Path, default=None, help="Override the spec's output image")
    run.add_argument("--steps", action="store_true", help="Write numbered intermediates + README table")
    run.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Step dir (default: {DEFAULT_OUTPUT_DIR})"
    )

    sub.add_parser("ops", help="List every available op")

    for q in (run,):
        q.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
        q.add_argument("-q", "--quiet", action="store_true", help="Errors only")
    return p


def main(
    args: argparse.Namespace,
    *,
    cv2_resolver: ModuleResolver = _default_cv2,
    hf_resolver: ModuleResolver = _default_hf,
) -> int:
    """Dispatch a parsed command. Resolvers are injected so tests run without cv2/HF."""
    if args.command == "ops":
        sys.stdout.write(list_ops() + "\n")
        return 0

    spec = load_spec(args.spec)
    input_path = Path(args.input) if args.input else Path(str(spec["input"]))
    output_path = Path(args.output) if args.output else Path(str(spec.get("output", "out.png")))
    ctx = OpContext(
        base_dir=Path(str(spec.get("base_dir", "."))),
        cv2_resolver=cv2_resolver,
        hf_resolver=hf_resolver,
        output_dir=Path(args.output_dir),
    )

    frame = Frame(load_image(input_path))
    frame, record = run_pipeline(frame, spec["steps"], ctx, emit_steps=bool(args.steps))
    save_image(frame.image, output_path)
    write_sidecar(
        output_path.with_suffix(".json"),
        {
            "command": "pipeline",
            "input": str(input_path),
            "timestamp": timestamp_now(),
            "spec": str(args.spec),
            "steps": spec["steps"],
            "outputs": [str(output_path)],
        },
    )
    if args.steps:
        readme = write_steps_readme(ctx.output_dir, record)
        sys.stdout.write(f"  steps: {readme}\n")
    sys.stdout.write(f"  saved: {output_path}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    parser = build_parser()
    ns = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG
        if getattr(ns, "verbose", False)
        else logging.ERROR
        if getattr(ns, "quiet", False)
        else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        raise SystemExit(main(ns))
    except (RuntimeError, ValueError, KeyError, AttributeError) as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc
