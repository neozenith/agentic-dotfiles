---
name: art-edit
description: "Deterministic, offline image post-processing — background removal (U2-Net or distance-from-white), multi-signal alpha matting, a 'steps' pipeline visualiser that emits intermediate masks for visual debugging, and two-tone wordmark composition. Every output gets a JSON sidecar recording the exact settings so any edit is reproducible. Use when the user wants to make a generated image's background transparent, crop to content, build a matte, debug a segmentation pipeline, or add a text wordmark — without paying for a fresh AI generation. Runs entirely offline (no API key)."
argument-hint: "remove-bg <img> [--mode model|global] [-o out.png]  |  segment <img> [--output-dir d] [--sharpen 12]  |  steps <img> [--output-dir d]  |  wordmark <img> [--text T --split-at N --config c.json]  |  composite <img> [--text T]"
allowed-tools:
  - Read
  - Glob
  - Bash(uv run .claude/skills/art-edit/scripts/art_edit.py *)
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

# Requirements

- **`uv`** in `PATH`. Deps (`Pillow`, `numpy`, `rembg`, `onnxruntime`) are declared via
  PEP 723 inline metadata and materialised on first run.
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
