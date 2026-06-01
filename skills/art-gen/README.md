# art-gen

Generate images from curated text prompts using Google's GenAI image models, with a
JSON sidecar recording exactly how each image was made — so an exploration is
reproducible and the next prompt can be curated from the prompts that worked.

`art-gen` is the **online, non-deterministic** half of an image workflow. Its companion,
[`art-edit`](../art-edit/README.md), is the **offline, deterministic** post-processor
(background removal, matting, wordmark). Generate with `art-gen`; refine with `art-edit`
so you don't pay for a fresh generation every time you only need a transparent
background or a text overlay.

## Requirements

| Need | Why |
|------|-----|
| `GOOGLE_API_KEY` (non-empty) | The only supported auth. This skill uses the API-key path — **not** Vertex AI or application-default credentials. Missing/blank → it fails fast. |
| `uv` on `PATH` | The script declares its deps inline (PEP 723: `google-genai`, `Pillow`); `uv` builds the venv on first run. |
| Internet access | For the GenAI API call. |

```bash
export GOOGLE_API_KEY='…'
```

## Backends

| Backend | `--model` aliases | Best for |
|---------|-------------------|----------|
| `gemini` (default) | `flash`, `pro` | Iteration, prompt **+ reference image** conditioning, 4K |
| `imagen` | `standard`, `ultra`, `fast` | High-fidelity standalone batches (`--count`), 1K/2K |

A raw model id passed to `--model` is forwarded verbatim.

## Quickstart

```bash
# 1. Write a prompt file (see reference/prompt_template.md for a starting point)
# 2. Generate
uv run .claude/skills/art-gen/scripts/art_gen.py generate --prompt-file prompt.md

# Review the output
ls art/gen/
#   art_20260601_120000_0.png   art_20260601_120000_0.json
```

## The prompt file (maximise every token)

The prompt is the product. Write it in a markdown file. **Lines that begin with `#` (a
markdown heading) or `<!--` (an HTML comment) are stripped before the prompt is sent** —
use them to document concept and iteration history above the curated prompt body without
spending tokens on them.

```markdown
# My Subject — icon only (no text)
# CONCEPT: <what this is and why>
# STYLE NOTES (from iteration): <reinforce / avoid>

<the full curated prompt: subject, pose, style, exact palette with hex codes,
composition, and what to exclude — every word is signal>
```

Copy `reference/prompt_template.md` to start.

## Command reference

### `generate`

| Flag | Default | Description |
|------|---------|-------------|
| `--prompt TEXT` | — | Inline prompt (wins over `--prompt-file`) |
| `--prompt-file FILE` | — | Prompt markdown file; **repeatable** to fan out variants in one run |
| `--backend {gemini,imagen}` | `gemini` | Generation backend |
| `--model ALIAS` | backend default | `flash`/`pro` or `standard`/`ultra`/`fast`, or a raw model id |
| `--aspect RATIO` | `1:1` | One of `1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9` |
| `--size {1K,2K,4K}` | model default | 4K is gemini-only; imagen clamps to 1K/2K |
| `--count N` | `1` | Variants per prompt (imagen only) |
| `--ref IMG` | — | Reference image (repeatable; gemini only) |
| `--out-dir DIR` | `art/gen` | Output directory |

### `history`

Prints prior prompts/metadata oldest→newest from the sidecars in `--out-dir`, so you can
curate the next prompt from the ones that worked.

```bash
uv run .claude/skills/art-gen/scripts/art_gen.py history --out-dir art/gen
```

## Examples

```bash
# Fan out: one image per prompt file in a single run (e.g. pose variants)
uv run .claude/skills/art-gen/scripts/art_gen.py generate \
    --prompt-file pose_a.md --prompt-file pose_b.md --prompt-file pose_c.md --out-dir art/gen

# Imagen, 4 variants of one prompt at 2K
uv run .claude/skills/art-gen/scripts/art_gen.py generate \
    --backend imagen --model ultra --count 4 --size 2K --prompt-file prompt.md

# Gemini conditioned on a reference image
uv run .claude/skills/art-gen/scripts/art_gen.py generate \
    --prompt-file refine.md --ref art/gen/art_20260601_120000_0.png

# Inline one-shot (no file)
uv run .claude/skills/art-gen/scripts/art_gen.py generate \
    --prompt "A flat-vector compass rose, charcoal on white, no text."
```

## Output & sidecars

Each image is `art_<YYYYMMDD_HHMMSS>_<index>.png` with a matching `.json`:

```json
{
  "prompt": "…the exact text sent…",
  "model": "gemini-3-pro-image-preview",
  "backend": "gemini",
  "timestamp": "20260601_120000",
  "index": 0,
  "dimensions": "1024x1024",
  "aspect": "1:1",
  "requested_size": null,
  "prompt_file": "prompt.md"
}
```

Timestamped filenames sort chronologically, and the sidecars preserve the full
provenance of a sweep.

## The iteration loop

1. **Generate** a small fan-out of prompt-file variants.
2. **Look** at the PNGs; decide what worked.
3. Run **`history`** to re-read the exact prompts behind the good frames.
4. **Curate the next prompt** by grafting the strongest phrasing from one or more prior
   prompts into a new file (keep discarded ideas in `#` comments as a record).
5. Repeat. Hand the keeper to [`art-edit`](../art-edit/README.md) for a transparent
   background, crop, and any text/wordmark overlay.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `GOOGLE_API_KEY is not set (or is empty)` | Export a non-empty key. Vertex AI / ADC is intentionally not supported. |
| `Prompt file is empty after stripping comments` | Every line started with `#`/`<!--`; add a prompt body. |
| 4K rejected on imagen | 4K is gemini-only; use `--size 2K`. |

## For maintainers

The development contract and the design rationale (ADRs) live in
[`CLAUDE.md`](./CLAUDE.md). The gate is `make -C .claude/skills/art-gen/scripts ci`.
