#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "Pillow>=10.1.0",
#   "numpy>=1.26.0",
#   "rembg>=2.0.0",
#   "onnxruntime>=1.17.0",
# ]
#
# [tool.uv]
# override-dependencies = ["numba>=0.60.0"]
# ///
"""art-edit — deterministic, offline image post-processing.

Takes an image (e.g. one produced by the ``art-gen`` skill) and applies reproducible
edits with traditional + machine-vision techniques — no API key, no network:

  remove-bg   Background removal → transparent PNG. ``--mode model`` uses a U2-Net
              segmentation model (via rembg); ``--mode global`` thresholds distance
              from white (no model download).
  segment     Multi-signal alpha matte: U2-Net + colour-distance + Scharr-edge signals
              combined and sigmoid-sharpened, with every intermediate saved for
              inspection.
  steps       Pipeline visualisation: for each stage, a mask / this-step / cumulative
              triple plus a README table — a visual debugger for the matte.
  wordmark    Compose the icon with a two-tone text wordmark using normalised
              positioning and anchors.
  composite   Convenience chain: remove-bg (model) → wordmark.

Sidecars:
  Every command writes a ``<output>.json`` (or ``steps.json`` for the ``steps`` dir)
  recording the command, input, and the exact settings used — so any edit, including
  the intermediate-steps visualisation, can be reproduced.

Auth:
  None. Runs entirely offline. The first ``--mode model`` run downloads the U2-Net
  weights (~170 MB) to the rembg cache; subsequent runs are offline.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── Configuration ──────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

# A segmenter maps an RGB(A) image to an RGBA image whose alpha is the foreground matte.
# Injected so the (heavy, model-backed) default can be swapped for a fake in tests.
Segmenter = Callable[[Image.Image], Image.Image]

# Neutral, brand-agnostic defaults. Override via a --config JSON file.
DEFAULT_WORDMARK: dict[str, Any] = {
    "text": "BRAND",
    "split_at": 3,
    "position": [0.55, 0.5],
    "anchor": "center_left",
    "font": None,
    "font_size_ratio": 0.25,
    "font_weight": None,
    "color_left": [40, 40, 40],
    "color_right": [200, 120, 60],
    "stroke_width": 0,
    "stroke_color": None,
}
DEFAULT_ICON: dict[str, Any] = {"position": [0.05, 0.5], "anchor": "center_left", "scale": 0.9}
DEFAULT_CANVAS: dict[str, Any] = {"width": 2048, "height": 1024}
DEFAULT_BACKGROUND = [255, 255, 255, 0]

# Cross-platform font fallback chain for the wordmark.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

ANCHORS: dict[str, tuple[float, float]] = {
    "top_left": (0.0, 0.0),
    "top_center": (0.5, 0.0),
    "top_right": (1.0, 0.0),
    "center_left": (0.0, 0.5),
    "center": (0.5, 0.5),
    "center_right": (1.0, 0.5),
    "bottom_left": (0.0, 1.0),
    "bottom_center": (0.5, 1.0),
    "bottom_right": (1.0, 1.0),
}


# ── Sidecar / config / timestamp ───────────────────────────────────────────
def timestamp_now() -> str:
    """Filesystem-sortable local timestamp, e.g. ``20260601_143501``."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_sidecar(
    sidecar_path: Path, *, command: str, input_path: Path, params: dict[str, Any], outputs: Sequence[str] | None = None
) -> Path:
    """Write a JSON sidecar capturing the settings needed to reproduce an edit."""
    payload: dict[str, Any] = {
        "command": command,
        "input": str(input_path),
        "timestamp": timestamp_now(),
        "params": params,
    }
    if outputs is not None:
        payload["outputs"] = list(outputs)
    sidecar_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Wrote sidecar: %s", sidecar_path)
    return sidecar_path


def load_config(config_path: Path | None) -> dict[str, Any]:
    """Load a JSON config, or return ``{}`` to fall back to built-in defaults."""
    if config_path is None:
        return {}
    cfg: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    log.info("Loaded config from %s", config_path)
    return cfg


# ── Pure machine-vision primitives (unit-tested on tiny synthetic arrays) ──
def auto_crop(arr: np.ndarray, pad: int = 4) -> np.ndarray:
    """Crop an RGBA array to the bounding box of non-transparent pixels (+pad)."""
    h, w = arr.shape[:2]
    alpha = arr[:, :, 3]
    fg_rows = np.any(alpha > 10, axis=1)
    fg_cols = np.any(alpha > 10, axis=0)
    if not (np.any(fg_rows) and np.any(fg_cols)):
        return arr
    rmin, rmax = np.where(fg_rows)[0][[0, -1]]
    cmin, cmax = np.where(fg_cols)[0][[0, -1]]
    rmin, rmax = max(0, int(rmin) - pad), min(h - 1, int(rmax) + pad)
    cmin, cmax = max(0, int(cmin) - pad), min(w - 1, int(cmax) + pad)
    return arr[rmin : rmax + 1, cmin : cmax + 1]


def color_distance(arr: np.ndarray) -> np.ndarray:
    """Per-pixel Chebyshev distance from pure white (0 = white, 255 = black)."""
    rgb = arr[:, :, :3].astype(np.float32)
    return cast(np.ndarray, np.max(255.0 - rgb, axis=2).astype(np.float32))


def color_signal(max_dist: np.ndarray, white_tolerance: int, edge_softness: int) -> np.ndarray:
    """Smooth 0→1 ramp: 0 at/below tolerance, 1 once clearly non-white."""
    transition = max(float(edge_softness * 5), 1.0)
    return np.clip((max_dist - float(white_tolerance)) / transition, 0.0, 1.0).astype(np.float32)


def scharr_edges(arr: np.ndarray) -> np.ndarray:
    """Scharr gradient magnitude, normalised to 0–1 (better rotational symmetry than Sobel)."""
    gray = np.mean(arr[:, :, :3], axis=2).astype(np.float32)
    h, w = gray.shape
    kx = np.array([[-3, 0, 3], [-10, 0, 10], [-3, 0, 3]], dtype=np.float32)
    ky = np.array([[-3, -10, -3], [0, 0, 0], [3, 10, 3]], dtype=np.float32)
    padded = np.pad(gray, 1, mode="edge")
    dx = sum(kx[i, j] * padded[i : i + h, j : j + w] for i in range(3) for j in range(3))
    dy = sum(ky[i, j] * padded[i : i + h, j : j + w] for i in range(3) for j in range(3))
    mag = np.sqrt(dx**2 + dy**2)
    peak = float(mag.max()) if mag.max() > 0 else 1.0
    return cast(np.ndarray, (mag / peak).astype(np.float32))


def dilate_edge_mask(edge_norm: np.ndarray, threshold: float = 0.02, size: int = 5) -> np.ndarray:
    """Threshold the edge map, then dilate with a MaxFilter into a spatial envelope."""
    binary = (edge_norm > threshold).astype(np.uint8) * 255
    dilated = Image.fromarray(binary, mode="L").filter(ImageFilter.MaxFilter(size=size))
    return (np.array(dilated).astype(np.float32) / 255.0).astype(np.float32)


def element_alpha(arr: np.ndarray, max_dist: np.ndarray, grey_reference: int) -> np.ndarray:
    """Per-pixel opacity from max(grey, warmth, darkness) — rescues anti-aliased edges.

    grey   = distance-from-white (neutral lines); warmth = R−B (gold/amber edges);
    darkness = inverted brightness (dark outlines). Each catches AA pixels the others miss.
    """
    rgb = arr[:, :, :3].astype(np.float32)
    grey = np.clip(max_dist / float(grey_reference), 0.0, 1.0)
    warmth = np.clip((rgb[:, :, 0] - rgb[:, :, 2]) / 40.0, 0.0, 1.0)
    darkness = np.clip((220.0 - np.mean(rgb, axis=2)) / 150.0, 0.0, 1.0)
    return cast(np.ndarray, np.maximum(np.maximum(grey, warmth), darkness).astype(np.float32))


def sigmoid_sharpen(mask: np.ndarray, k: int, *, midpoint: float = 0.5) -> np.ndarray:
    """Push a soft alpha matte toward 0/1 with a sigmoid, then a 0.5px anti-alias pass.

    ``k`` is steepness: 0 = no change, 12 = crisp, 30+ = near-binary. Returns the matte
    unchanged when ``k <= 0``.
    """
    if k <= 0:
        return mask.astype(np.float32)
    sharp = 1.0 / (1.0 + np.exp(-k * (mask - midpoint)))
    lo, hi = float(sharp.min()), float(sharp.max())
    if hi > lo:
        sharp = (sharp - lo) / (hi - lo)
    img = Image.fromarray((sharp * 255).astype(np.uint8), mode="L").filter(ImageFilter.GaussianBlur(radius=0.5))
    return (np.array(img).astype(np.float32) / 255.0).astype(np.float32)


def combined_matte(
    arr: np.ndarray, u2net_alpha: np.ndarray, *, white_tolerance: int, edge_softness: int, grey_reference: int
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Combine semantic + colour + edge signals into one matte (pre-sharpen).

    Returns the union matte and a dict of the intermediate signals for visualisation.
    """
    max_dist = color_distance(arr)
    color = color_signal(max_dist, white_tolerance, edge_softness)
    edge_norm = scharr_edges(arr)
    edge_mask = dilate_edge_mask(edge_norm)
    edge = edge_mask * element_alpha(arr, max_dist, grey_reference)
    union = np.maximum(np.maximum(u2net_alpha, color), edge).astype(np.float32)
    signals = {
        "u2net": u2net_alpha,
        "color": color,
        "edge_scharr": edge_norm,
        "edge_dilated": edge_mask,
        "edge_refined": edge,
        "combined": union,
    }
    return union, signals


# ── Positioning + text ─────────────────────────────────────────────────────
def resolve_position(
    pos: tuple[float, float], anchor: str, canvas_w: int, canvas_h: int, content_w: int, content_h: int
) -> tuple[int, int]:
    """Normalised (0–1) position + anchor → absolute top-left pixel coordinates."""
    ax, ay = ANCHORS.get(anchor, (0.0, 0.0))
    return (int(pos[0] * canvas_w) - int(ax * content_w), int(pos[1] * canvas_h) - int(ay * content_h))


def load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font from a fallback chain, or PIL's bitmap default."""
    for path in ([font_path] if font_path else []) + FONT_CANDIDATES:
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:  # pragma: no cover - corrupt/unsupported font file
                continue
    # Size-aware default (Pillow >= 10.1) returns a FreeType-backed font that supports
    # getbbox at any size — works cross-platform with no system fonts installed.
    log.warning("No system TrueType font found; using Pillow's bundled default")
    return ImageFont.load_default(size)


def render_text(
    text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, color: tuple[int, int, int, int]
) -> Image.Image:
    """Render text to a tightly-cropped transparent RGBA image."""
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    pad = 4
    img = Image.new("RGBA", ((right - left) + pad * 2, (bottom - top) + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad - left, pad - top), text, font=font, fill=color)
    return img


# ── Segmenter seam ─────────────────────────────────────────────────────────
def _default_segmenter() -> Segmenter:  # pragma: no cover - heavy ML import (rembg/onnxruntime)
    from rembg import remove as rembg_remove

    return cast(Segmenter, rembg_remove)


def _u2net_alpha(img: Image.Image, segmenter: Segmenter) -> np.ndarray:
    """Run the segmenter and return its foreground alpha as a float32 0–1 matte."""
    result = segmenter(img)
    return np.array(result.convert("RGBA"))[:, :, 3].astype(np.float32) / 255.0


# ── remove-bg ──────────────────────────────────────────────────────────────
def remove_background(
    input_path: Path,
    output_path: Path | None = None,
    *,
    mode: str = "model",
    tolerance: int = 30,
    edge_softness: int = 2,
    segmenter: Segmenter | None = None,
) -> Path:
    """Remove the background and write a transparent PNG plus a reproducibility sidecar.

    ``mode='model'`` uses U2-Net semantic segmentation (preserves white subject details);
    ``mode='global'`` thresholds distance from white (fast, no model, removes all white).
    """
    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]

    if mode == "model":
        if segmenter is None:
            segmenter = _default_segmenter()  # pragma: no cover - live ML path
        alpha = (_u2net_alpha(img, segmenter) * 255).astype(np.uint8)
        if edge_softness > 0:
            alpha = np.array(Image.fromarray(alpha, mode="L").filter(ImageFilter.GaussianBlur(radius=edge_softness)))
        arr[:, :, 3] = alpha
    elif mode == "global":
        max_dist = color_distance(arr)
        alpha_f = color_signal(max_dist, tolerance, edge_softness)
        alpha = (alpha_f * 255).astype(np.uint8)
        if edge_softness > 0:
            alpha = np.array(Image.fromarray(alpha, mode="L").filter(ImageFilter.GaussianBlur(radius=edge_softness)))
        arr[:, :, 3] = alpha
    else:
        raise ValueError(f"Unknown mode: {mode!r} (choose 'model' or 'global')")

    arr = auto_crop(arr)
    out = output_path or input_path.with_stem(input_path.stem + "_nobg")
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(out)
    log.info("Saved %s (%dx%d, %d input px)", out, arr.shape[1], arr.shape[0], h * w)
    write_sidecar(
        out.with_suffix(".json"),
        command="remove-bg",
        input_path=input_path,
        params={"mode": mode, "tolerance": tolerance, "edge_softness": edge_softness},
        outputs=[out.name],
    )
    return out


# ── segment (multi-signal matte with intermediates) ────────────────────────
def segment_layers(
    input_path: Path,
    output_dir: Path,
    *,
    white_tolerance: int = 15,
    edge_softness: int = 2,
    grey_reference: int = 30,
    sharpen: int = 12,
    segmenter: Segmenter | None = None,
) -> Path:
    """Produce a multi-signal transparent PNG and save every intermediate signal."""
    if segmenter is None:
        segmenter = _default_segmenter()  # pragma: no cover - live ML path
    output_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img)

    u2net_alpha = _u2net_alpha(img, segmenter)
    union, signals = combined_matte(
        arr, u2net_alpha, white_tolerance=white_tolerance, edge_softness=edge_softness, grey_reference=grey_reference
    )
    for name, sig in signals.items():
        _save_mask(output_dir / f"mask_{name}.png", sig)

    sharpened = sigmoid_sharpen(union, sharpen)
    _save_mask(output_dir / "mask_sharpened.png", sharpened)

    final = arr.copy()
    final[:, :, 3] = (sharpened * 255).astype(np.uint8)
    final = auto_crop(final)
    final_path = output_dir / "final.png"
    Image.fromarray(final).save(final_path)
    log.info("Saved %s (%dx%d)", final_path, final.shape[1], final.shape[0])

    write_sidecar(
        output_dir / "segment.json",
        command="segment",
        input_path=input_path,
        params={
            "white_tolerance": white_tolerance,
            "edge_softness": edge_softness,
            "grey_reference": grey_reference,
            "sharpen": sharpen,
        },
        outputs=sorted(p.name for p in output_dir.glob("*.png")),
    )
    return final_path


# ── steps (pipeline visualisation) ─────────────────────────────────────────
def generate_pipeline_steps(
    input_path: Path,
    output_dir: Path,
    *,
    white_tolerance: int = 15,
    edge_softness: int = 2,
    grey_reference: int = 30,
    sharpen: int = 12,
    segmenter: Segmenter | None = None,
) -> Path:
    """Save mask/this-step/cumulative triples per stage + a README; return the README path."""
    if segmenter is None:
        segmenter = _default_segmenter()  # pragma: no cover - live ML path
    output_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]

    u2net_alpha = _u2net_alpha(img, segmenter)
    union, signals = combined_matte(
        arr, u2net_alpha, white_tolerance=white_tolerance, edge_softness=edge_softness, grey_reference=grey_reference
    )
    sharpened = sigmoid_sharpen(union, sharpen)

    stages: list[tuple[str, str, np.ndarray]] = [
        ("u2net", "U2-Net semantic segmentation — model identifies the foreground subject", signals["u2net"]),
        ("color_distance", "Colour distance from white — pixels far from white are kept", signals["color"]),
        ("edge_scharr", "Scharr edge magnitude — gradient reveals structural edges", signals["edge_scharr"]),
        ("edge_dilated", "Edge dilation — threshold + MaxFilter creates a spatial envelope", signals["edge_dilated"]),
        ("edge_refined", "Edge refinement — envelope × max(grey, warmth, darkness) alpha", signals["edge_refined"]),
        ("combined", "Combined matte — pixel-wise max of semantic, colour, and edge", signals["combined"]),
        ("sharpened", f"Sigmoid sharpening (k={sharpen}) — pushes soft alpha toward 0/1", sharpened),
    ]

    steps_meta: list[dict[str, Any]] = [
        {
            "num": 0,
            "slug": "original",
            "description": "Original input image",
            "mask_file": None,
            "result_file": "00_original.png",
            "cumulative_file": None,
        }
    ]
    img.save(output_dir / "00_original.png")
    cumulative = np.zeros((h, w), dtype=np.float32)
    for i, (slug, desc, mask) in enumerate(stages, start=1):
        cumulative = mask if slug in ("combined", "sharpened") else np.maximum(cumulative, mask)
        steps_meta.append(_save_step(output_dir, i, slug, desc, mask, arr, cumulative))

    final = arr.copy()
    final[:, :, 3] = (sharpened * 255).astype(np.uint8)
    final = auto_crop(final)
    Image.fromarray(final).save(output_dir / "08_result_final.png")
    steps_meta.append(
        {
            "num": 8,
            "slug": "final",
            "description": "Final result — matte applied and auto-cropped",
            "mask_file": None,
            "result_file": "08_result_final.png",
            "cumulative_file": None,
        }
    )

    readme = _write_steps_readme(output_dir, steps_meta, input_path.name)
    write_sidecar(
        output_dir / "steps.json",
        command="steps",
        input_path=input_path,
        params={
            "white_tolerance": white_tolerance,
            "edge_softness": edge_softness,
            "grey_reference": grey_reference,
            "sharpen": sharpen,
        },
        outputs=[s["result_file"] for s in steps_meta if s["result_file"]],
    )
    return readme


def _save_mask(path: Path, mask_f32: np.ndarray) -> None:
    Image.fromarray((np.clip(mask_f32, 0, 1) * 255).astype(np.uint8), mode="L").save(path)


def _apply_matte(original: np.ndarray, mask_f32: np.ndarray) -> Image.Image:
    out = original.copy()
    out[:, :, 3] = (np.clip(mask_f32, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(out)


def _save_step(
    output_dir: Path,
    num: int,
    slug: str,
    description: str,
    mask: np.ndarray,
    original: np.ndarray,
    cumulative: np.ndarray,
) -> dict[str, Any]:
    mask_file, result_file, cumul_file = (
        f"{num:02d}_mask_{slug}.png",
        f"{num:02d}_result_{slug}.png",
        f"{num:02d}_cumulative_{slug}.png",
    )
    _save_mask(output_dir / mask_file, mask)
    _apply_matte(original, mask).save(output_dir / result_file)
    _apply_matte(original, cumulative).save(output_dir / cumul_file)
    return {
        "num": num,
        "slug": slug,
        "description": description,
        "mask_file": mask_file,
        "result_file": result_file,
        "cumulative_file": cumul_file,
    }


def _write_steps_readme(output_dir: Path, steps: Sequence[dict[str, Any]], input_name: str) -> Path:
    lines = [
        "# Image Processing Pipeline",
        "",
        f"Source image: `{input_name}`",
        "",
        "Each row shows a pipeline stage with three views:",
        "",
        "- **Mask / Filter** — the greyscale signal computed at this step",
        "- **This Step** — original with only this step's mask as transparency",
        "- **Cumulative** — original with all filters combined up to this point",
        "",
        "| # | Step | Mask / Filter | This Step | Cumulative |",
        "|--:|------|:-------------:|:---------:|:----------:|",
    ]
    for s in steps:
        mask = f"![mask]({s['mask_file']})" if s["mask_file"] else ""
        result = f"![result]({s['result_file']})" if s["result_file"] else ""
        cumul = f"![cumulative]({s['cumulative_file']})" if s["cumulative_file"] else ""
        lines.append(f"| {s['num']} | {s['description']} | {mask} | {result} | {cumul} |")
    lines += ["", "---", "", "*Generated by `art_edit.py steps`*", ""]
    readme = output_dir / "README.md"
    readme.write_text("\n".join(lines), encoding="utf-8")
    log.info("Saved %s", readme)
    return readme


# ── wordmark ───────────────────────────────────────────────────────────────
def add_wordmark(
    icon_path: Path,
    output_path: Path | None = None,
    *,
    config: dict[str, Any] | None = None,
    text: str | None = None,
    font_path: str | None = None,
    font_size: int | None = None,
    split_at: int | None = None,
    canvas_size: tuple[int, int] | None = None,
) -> Path:
    """Compose icon + two-tone wordmark on a canvas using normalised positioning."""
    cfg = config or {}
    wm = {**DEFAULT_WORDMARK, **cfg.get("wordmark", {})}
    icon_cfg = {**DEFAULT_ICON, **cfg.get("icon", {})}
    canvas_cfg = {**DEFAULT_CANVAS, **cfg.get("canvas", {})}

    text = text if text is not None else wm["text"]
    split_at = split_at if split_at is not None else wm["split_at"]
    color_left = tuple(wm["color_left"])
    color_right = tuple(wm["color_right"])

    icon = Image.open(icon_path).convert("RGBA")
    cw, ch = canvas_size if canvas_size else (canvas_cfg["width"], canvas_cfg["height"])
    bg = tuple(cfg.get("background", DEFAULT_BACKGROUND))

    scaled_h = int(ch * icon_cfg["scale"])
    scale = scaled_h / icon.height
    scaled_w = int(icon.width * scale)
    icon_scaled = icon.resize((scaled_w, scaled_h), Image.LANCZOS)

    # Clamp to a renderable minimum: FreeType raises on sub-~8px sizes, and a wordmark
    # that small is illegible anyway.
    size = max(font_size if font_size is not None else int(ch * wm["font_size_ratio"]), 16)
    font = load_font(font_path or wm["font"], size)

    img_left = render_text(text[:split_at], font, (*color_left, 255))
    img_right = render_text(text[split_at:], font, (*color_right, 255))
    text_w, text_h = img_left.width + img_right.width, max(img_left.height, img_right.height)
    text_combined = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
    text_combined.paste(img_left, (0, 0), img_left)
    text_combined.paste(img_right, (img_left.width, 0), img_right)

    canvas = Image.new("RGBA", (cw, ch), bg)
    ix, iy = resolve_position(tuple(icon_cfg["position"]), icon_cfg["anchor"], cw, ch, scaled_w, scaled_h)
    canvas.paste(icon_scaled, (ix, iy), icon_scaled)
    tx, ty = resolve_position(tuple(wm["position"]), wm["anchor"], cw, ch, text_w, text_h)
    canvas.paste(text_combined, (tx, ty), text_combined)

    out = output_path or icon_path.with_stem(icon_path.stem + "_wordmark")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    log.info("Saved %s (%dx%d)", out, canvas.width, canvas.height)
    write_sidecar(
        out.with_suffix(".json"),
        command="wordmark",
        input_path=icon_path,
        params={
            "text": text,
            "split_at": split_at,
            "canvas": [cw, ch],
            "color_left": list(color_left),
            "color_right": list(color_right),
            "icon": icon_cfg,
            "wordmark_position": wm["position"],
            "font": font_path or wm["font"],
        },
        outputs=[out.name],
    )
    return out


# ── composite ──────────────────────────────────────────────────────────────
def composite_pipeline(
    icon_path: Path,
    output_path: Path | None = None,
    *,
    config: dict[str, Any] | None = None,
    text: str | None = None,
    segmenter: Segmenter | None = None,
) -> Path:
    """Convenience chain: remove-bg (model) → wordmark."""
    nobg = remove_background(
        icon_path, icon_path.with_stem(icon_path.stem + "_nobg"), mode="model", segmenter=segmenter
    )
    out = output_path or icon_path.with_stem(icon_path.stem + "_final")
    return add_wordmark(nobg, out, config=config, text=text)


# ── CLI ────────────────────────────────────────────────────────────────────
def _parse_pos(s: str) -> tuple[float, float]:
    parts = s.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"Position must be 'x,y' (got {s!r})")
    return (float(parts[0]), float(parts[1]))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="art_edit.py",
        description="Deterministic, offline image post-processing (background removal, matting, wordmark).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("input", type=Path, help="Input image path")
    shared.add_argument("-o", "--output", type=Path, default=None, help="Output path")
    shared.add_argument("--config", type=Path, default=None, help="JSON config file (wordmark/icon/canvas)")
    shared.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    shared.add_argument("-q", "--quiet", action="store_true", help="Errors only")

    bg = sub.add_parser("remove-bg", parents=[shared], help="Remove background → transparent PNG")
    bg.add_argument("--mode", choices=["model", "global"], default="model", help="Segmentation mode (default: model)")
    bg.add_argument("--tolerance", type=int, default=30, help="(global) distance-from-white threshold (default: 30)")
    bg.add_argument("--edge-softness", type=int, default=2, help="Alpha-edge blur radius in px (default: 2)")

    for name in ("segment", "steps"):
        sp = sub.add_parser(
            name,
            parents=[shared],
            help="Multi-signal matte with intermediates"
            if name == "segment"
            else "Pipeline visualisation with mask/result/cumulative triples + README",
        )
        sp.add_argument("--white-tolerance", type=int, default=15, help="Distance-from-white background (default: 15)")
        sp.add_argument("--grey-ref", type=int, default=30, help="Distance mapping to full opacity (default: 30)")
        sp.add_argument("--sharpen", type=int, default=12, help="Sigmoid steepness (0=off, 12=crisp; default: 12)")
        sp.add_argument("--output-dir", type=Path, default=None, help=f"Output dir (default: <input>_{name})")

    wm = sub.add_parser("wordmark", parents=[shared], help="Add a two-tone wordmark next to the icon")
    wm.add_argument("--text", default=None, help="Wordmark text (default from config)")
    wm.add_argument("--font", default=None, help="Path to a .ttf/.otf font")
    wm.add_argument("--font-size", type=int, default=None, help="Font size in px")
    wm.add_argument("--split-at", type=int, default=None, help="Character index where the two colours split")
    wm.add_argument("--canvas", type=_parse_pos, default=None, help="Canvas 'width,height' in px")

    comp = sub.add_parser("composite", parents=[shared], help="Chain: remove-bg (model) → wordmark")
    comp.add_argument("--text", default=None, help="Wordmark text")
    return p


def main(args: argparse.Namespace, *, segmenter: Segmenter | None = None) -> int:
    """Dispatch a parsed command. ``segmenter`` is injected by tests; production builds it lazily."""
    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")
    cfg = load_config(args.config)

    if args.command == "remove-bg":
        remove_background(
            args.input,
            args.output,
            mode=args.mode,
            tolerance=args.tolerance,
            edge_softness=args.edge_softness,
            segmenter=segmenter,
        )
    elif args.command == "segment":
        out_dir = args.output_dir or args.input.with_name(args.input.stem + "_segment")
        segment_layers(
            args.input,
            out_dir,
            white_tolerance=args.white_tolerance,
            grey_reference=args.grey_ref,
            sharpen=args.sharpen,
            segmenter=segmenter,
        )
    elif args.command == "steps":
        out_dir = args.output_dir or args.input.with_name(args.input.stem + "_steps")
        generate_pipeline_steps(
            args.input,
            out_dir,
            white_tolerance=args.white_tolerance,
            grey_reference=args.grey_ref,
            sharpen=args.sharpen,
            segmenter=segmenter,
        )
    elif args.command == "wordmark":
        canvas = (int(args.canvas[0]), int(args.canvas[1])) if args.canvas else None
        add_wordmark(
            args.input,
            args.output,
            config=cfg,
            text=args.text,
            font_path=args.font,
            font_size=args.font_size,
            split_at=args.split_at,
            canvas_size=canvas,
        )
    elif args.command == "composite":
        composite_pipeline(args.input, args.output, config=cfg, text=args.text, segmenter=segmenter)
    return 0


if __name__ == "__main__":  # pragma: no cover
    parser = build_parser()
    ns = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if ns.verbose else logging.ERROR if ns.quiet else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        raise SystemExit(main(ns))
    except (FileNotFoundError, ValueError) as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc
