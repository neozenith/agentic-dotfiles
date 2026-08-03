---
name: art-edit
description: "Deterministic, offline image post-processing in two layers: fixed commands (background removal, multi-signal alpha matting, a 'steps' visual debugger, wordmark composition) and a DECLARATIVE PIPELINE that chains any number of transforms in any order — compositing layers, recolouring, healing regions with inpaint, Poisson seamless-clone, feathered face cut-outs, plus escape hatches that call ANY OpenCV 5 function or ANY HuggingFace pipeline by name. Every output gets a JSON sidecar and every pipeline can emit numbered intermediates, so edits are reproducible and their working-out is inspectable. Use when the user wants to composite logos or faces onto an image, remove or recolour part of it, build a matte, debug a transform chain, or otherwise edit without paying for a fresh AI generation. Runs offline (no API key)."
argument-hint: "art_edit.py: remove-bg <img> [--mode model|global]  |  segment <img>  |  steps <img>  |  wordmark <img> --text T  ||  art_pipe.py: run <spec.json> [--steps] [--input i] [--output o]  |  ops"
allowed-tools:
  - Read
  - Glob
  - Bash(uv run .claude/skills/art-edit/scripts/art_edit.py *)
  - Bash(uv run .claude/skills/art-edit/scripts/art_pipe.py *)
user-invocable: true
---

# Context

`art-edit` is the offline, deterministic companion to `art-gen`. Once you have a keeper
image (AI-generated or otherwise), `art-edit` applies reproducible post-processing using
traditional and machine-vision techniques — so you don't burn a paid, non-deterministic
generation just to get a transparent background or add a wordmark.

Five commands:

| Command | What it does |
|---------|--------------|
| `remove-bg` | Background → transparent PNG, auto-cropped to content. `--mode model` (U2-Net semantic segmentation, preserves white subject details) or `--mode global` (threshold distance-from-white, no model download). |
| `segment` | A multi-signal alpha matte — U2-Net **+** colour-distance **+** Scharr-edge signals combined and sigmoid-sharpened — saving every intermediate mask for inspection. |
| `steps` | A **visual debugger** for the matte: for each stage, a mask / this-step / cumulative triple, plus a `README.md` table that renders them side by side. |
| `wordmark` | Compose the icon with a two-tone text wordmark using normalised positioning + anchors. |
| `composite` | Convenience chain: `remove-bg` (model) → `wordmark`. |

# The pipeline (`art_pipe.py`) — arbitrary transform chains

`art_edit.py` gives fixed commands; `art_pipe.py` runs an **ordered spec** so any
combination of transforms composes without new code. Two escape hatches make the surface
open-ended rather than a fixed menu.

| Op | What it does |
|----|--------------|
| `overlay` | Composite a PNG layer at a normalised position, with scale / rotation / opacity |
| `perspective-overlay` | Warp a layer onto a 4-corner quad — a decal on a foreshortened panel (e.g. a logo across a car door in a 3/4 view) |
| `seamless-clone` | Poisson-blend a layer so it inherits the destination's lighting (a decal that looks painted on, not stuck on) |
| `face-align` | Warp a source portrait onto a detected target face by YuNet 5-point landmark similarity, then blend (alpha or seamless). Best on calm frames — a re-synthesising `hf` swap model beats it when the target expression/lighting differ from the source portrait |
| `color-replace` | Recolour every pixel within tolerance of a target RGB; keeps the mask as a buffer |
| `inpaint` | Heal a region (colour-selected or from a buffer) via `cv2.inpaint` |
| `face-crop` | Detect a face (YuNet) or take an explicit box, and cut a feathered oval with alpha |
| `resize` / `crop` | Absolute, scale-factor, or normalised-box geometry |
| **`cv2`** | Call **any** OpenCV 5 function by name — `{"op":"cv2","fn":"bilateralFilter","args":["$image",9,75,75]}` |
| **`hf`** | Run **any** HuggingFace pipeline — `{"op":"hf","task":"image-segmentation","model":"...","into":"mask"}` |

`$image` and `$buf:NAME` inject live pipeline data into any argument, and `"cv2.INTER_CUBIC"`
strings resolve to real OpenCV constants — that indirection is why an arbitrary function can
participate without a hand-written wrapper. Run `art_pipe.py ops` to list the registry.

```bash
# See every available op
uv run .claude/skills/art-edit/scripts/art_pipe.py ops

# Run a chain, writing numbered intermediates + a README contact sheet
uv run .claude/skills/art-edit/scripts/art_pipe.py run pipeline.json --steps --output-dir art/pipe
```

```jsonc
{
  "input": "frame.png", "output": "composed.png", "base_dir": ".",
  "steps": [
    {"op": "inpaint",        "target": [245,158,11], "tolerance": 70, "dilate": 5},
    {"op": "seamless-clone", "layer": "logo.png", "at": [0.42,0.55], "width": 260, "mode": "mixed"},
    {"op": "face-crop",      "box": [820,300,180,220], "feather": 0.3},
    {"op": "cv2",            "fn": "detailEnhance", "args": ["$image", 10, 0.15]}
  ]
}
```

Faces are a two-stage flow: run `face-crop` against a portrait to produce a feathered
cut-out under `derived/`, then `overlay` (crisp) or `seamless-clone` (lighting-matched) that
cut-out onto the target frame.

# Targeting the right region / person (collaboration aids)

Before an edit that must land on a specific spot or person, build a cheap **agreement
artifact** first — it prevents "right edit, wrong place/person" reworks. See
`resources/learned/collaboration_workflows.md` for the full rituals. Two tools support this:

- **`grid.py`** — overlay a labelled grid (columns A, B, C…; rows 1, 2, 3…), then name any
  region as a spreadsheet range and resolve it to a pixel box + quad for a pipeline spec:
  ```bash
  uv run .claude/skills/art-edit/scripts/grid.py overlay frame.png -o frame_grid.png --cell 200
  uv run .claude/skills/art-edit/scripts/grid.py resolve C5:F6 --cell 200   # → box + TL/TR/BR/BL quad
  ```
  The `quad` drops straight into a `perspective-overlay` `dst`; the `box` into a `crop`.
- **Identity annotation** — for face work, first emit a colour-coded, named face map
  (box + landmarks, one stable colour per person) and confirm it, disambiguating look-alikes
  by fixed features (glasses, greying) and seating role (driver at the wheel, navigator with
  the notes). Swap only with a confirmed name→source mapping — never a low-confidence
  embedding auto-match.

# Requirements

- **`uv`** in `PATH`. Deps (`Pillow`, `numpy`, `opencv-python` ≥ 5, and for `art_edit.py`
  also `rembg`/`onnxruntime`) are declared via PEP 723 inline metadata and materialised on
  first run. The `hf` op additionally needs `transformers` available.
- **OpenCV 5 removed Haar cascades**, so `face-crop` uses the YuNet ONNX model
  (~350 KB, fetched once into `tmp/models/`). Pass an explicit `box` to skip detection
  entirely and stay fully offline.
- **No API key, no network** for the deterministic paths. The first `--mode model` /
  `segment` / `steps` run downloads the U2-Net weights (~170 MB) into the rembg cache;
  every run after that is fully offline.

# Sidecars (reproducible edits)

Every command writes a JSON sidecar next to its output capturing the command, input, and
exact settings — including the `steps` visualisation. Re-applying an edit is just reading
the sidecar back.

```jsonc
// remove-bg → o.json
{ "command": "remove-bg", "input": "in.png", "timestamp": "20260601_120500",
  "params": { "mode": "model", "tolerance": 30, "edge_softness": 2 }, "outputs": ["o.png"] }

// steps → steps.json
{ "command": "steps", "input": "in.png", "timestamp": "20260601_120730",
  "params": { "white_tolerance": 15, "edge_softness": 2, "grey_reference": 30, "sharpen": 12 },
  "outputs": ["00_original.png", "01_result_u2net.png", "…", "08_result_final.png"] }
```

# Usage

```bash
# Transparent PNG via the U2-Net model (best quality), auto-cropped
uv run .claude/skills/art-edit/scripts/art_edit.py remove-bg art/gen/art_…_0.png -o logo.png

# Fast, model-free background removal (thresholds distance from white)
uv run .claude/skills/art-edit/scripts/art_edit.py remove-bg in.png --mode global -o out.png

# Multi-signal matte with every intermediate mask saved for inspection
uv run .claude/skills/art-edit/scripts/art_edit.py segment in.png --output-dir art/seg --sharpen 12

# Pipeline VISUAL DEBUGGER → mask/result/cumulative triples + a README table
uv run .claude/skills/art-edit/scripts/art_edit.py steps in.png --output-dir art/steps
# then open art/steps/README.md

# Two-tone wordmark beside the icon (defaults are brand-neutral; override via --config)
uv run .claude/skills/art-edit/scripts/art_edit.py wordmark logo.png \
    --text MYBRAND --split-at 3 --config .claude/skills/art-edit/reference/config.example.json

# Full chain: remove-bg (model) → wordmark
uv run .claude/skills/art-edit/scripts/art_edit.py composite in.png --text MYBRAND -o final.png
```

# The Matte Pipeline (what `segment` / `steps` compute)

The matte combines three signals so it keeps faint, structural, and white-subject detail
that any single method drops:

1. **U2-Net semantic mask** — finds the foreground subject (keeps white details like eyes
   a colour threshold would erase).
2. **Colour distance from white** — keeps any clearly non-white content.
3. **Scharr edges → dilated envelope × `max(grey, warmth, darkness)` alpha** — rescues
   anti-aliased boundary pixels of neutral lines, warm/amber edges, and dark outlines.

`final alpha = sigmoid_sharpen(max(semantic, colour, edge))`, then auto-crop. `--sharpen`
controls the sigmoid steepness (`0` off, `12` crisp, `30+` near-binary) for a clean
rotoscoped edge. Use `steps` first to *see* each signal, then tune `--white-tolerance`,
`--grey-ref`, and `--sharpen` on `segment`.

# Configuration

`wordmark` / `composite` read an optional `--config` JSON (canvas size, background,
icon placement, two-tone colours, split point, font). Positions are normalised `0.0–1.0`
with an anchor: `(0.0,0.0)` = top-left, `(0.5,0.5)` = centre, `(1.0,1.0)` = bottom-right.
A neutral starting config is at
`.claude/skills/art-edit/reference/config.example.json`. CLI flags override config values.

# Notes

- Pair with `art-gen`: generate → pick a keeper → `art-edit` for transparency/crop/wordmark.
- Maintainers: the gate is `make -C .claude/skills/art-edit/scripts ci` (format-check,
  lint, mypy --strict, ≥90% coverage). Offline tests inject a fake segmenter through the
  documented seam. Real-model (U2-Net) validation is done via the CLI (run a real
  `remove-bg --mode model`), not via pytest. See `CLAUDE.md` ADR-010.
