---
name: art-gen
description: "Generate images from curated prompt files via Google's GenAI image models (Gemini 'Nano Banana' + Imagen 4). Each image is written with a JSON sidecar recording the exact prompt and settings, so runs are reproducible and the next prompt can be curated from prior ones. Supports fan-out across multiple prompt files in one invocation. Use when the user wants to generate, explore, or iterate on logos, icons, illustrations, or other AI imagery from text prompts. Requires a non-empty GOOGLE_API_KEY."
argument-hint: "generate --prompt-file <file.md> [--prompt-file <file2.md> ...] [--backend gemini|imagen] [--model flash|pro|standard|ultra|fast] [--aspect 1:1] [--size 1K|2K|4K] [--count N] [--ref <img>] [--out-dir <dir>]  |  history --out-dir <dir>"
allowed-tools:
  - Read
  - Glob
  - Bash(uv run .claude/skills/art-gen/scripts/art_gen.py *)
user-invocable: true
---

# Context

`art-gen` turns a **curated text prompt** into image(s) using Google's GenAI image
models, and records *how* each image was made so the exploration is reproducible and
iterable. It is the online, non-deterministic half of an image workflow; its companion
`art-edit` is the offline, deterministic post-processor (background removal, masking,
text overlays). Generate with `art-gen`, then refine with `art-edit` to avoid paying for
a fresh generation every time you only need a transparent background or a wordmark.

Two backends:

| Backend | Models (`--model`) | Best for |
|---------|--------------------|----------|
| `gemini` (default) | `flash`, `pro` | Iteration, prompt+reference-image conditioning, 4K |
| `imagen` | `standard`, `ultra`, `fast` | High-fidelity standalone batches (`--count`), 1K/2K |

A raw model id can be passed to `--model` and is forwarded verbatim.

# Requirements

- **`GOOGLE_API_KEY`** exported and **non-empty**. This skill uses the API-key path
  only — it does **not** use Vertex AI or application-default credentials. If the key
  is missing or blank, generation fails fast with a clear error.
- **`uv`** in `PATH`. The script declares its deps via PEP 723 inline metadata
  (`google-genai`, `Pillow`); `uv` materialises the venv on first run.
- **Internet access** for the GenAI API call.

# The Prompt File (maximise every token)

The prompt is the product. Write it in a markdown file and pass it with `--prompt-file`.
Lines whose first non-space character begins a markdown heading (`#`) or an HTML comment
(`<!--`) are **stripped before sending** — use them to document intent, concept notes,
and refinement history above the curated prompt body, without spending tokens on them.

```markdown
# My Subject — icon only (no text)
# Lines starting with # are stripped before the model sees them.
#
# CONCEPT: <what this is and why>
# STYLE NOTES (from iteration): <what to reinforce / avoid>

<the full curated prompt goes here — every word counts: subject, pose,
style, exact palette with hex codes, composition, what to exclude>
```

A starter you can copy lives at
`.claude/skills/art-gen/reference/prompt_template.md`.

# Usage

```bash
# Generate from a single prompt file (gemini/pro, 1:1)
uv run .claude/skills/art-gen/scripts/art_gen.py generate --prompt-file prompt.md

# Fan out: one image per prompt file in a single run (e.g. pose variants)
uv run .claude/skills/art-gen/scripts/art_gen.py generate \
    --prompt-file pose_perch.md --prompt-file pose_dive.md --prompt-file pose_land.md \
    --out-dir art/gen

# Imagen, 4 variants of one prompt at 2K
uv run .claude/skills/art-gen/scripts/art_gen.py generate \
    --backend imagen --model ultra --count 4 --size 2K --prompt-file prompt.md

# Gemini conditioned on a reference image (repeatable)
uv run .claude/skills/art-gen/scripts/art_gen.py generate \
    --prompt-file refine.md --ref art/gen/art_20260601_120000_0.png

# Inline one-shot (no file)
uv run .claude/skills/art-gen/scripts/art_gen.py generate \
    --prompt "A flat-vector compass rose, charcoal on white, no text."

# Review prior prompts/metadata to curate the next one (oldest → newest)
uv run .claude/skills/art-gen/scripts/art_gen.py history --out-dir art/gen
```

# Output & Sidecars

Each image is written as `art_<YYYYMMDD_HHMMSS>_<index>.png` with a matching
`art_<...>.json` sidecar:

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

Because filenames are timestamped, `ls` reads chronologically and the sidecars preserve
the full provenance of the sweep.

# The Iteration Loop (how to actually use this)

1. **Generate** a small fan-out of prompt-file variants.
2. **Look** at the PNGs; decide what worked.
3. Run **`history`** to re-read the exact prompts that produced the good frames.
4. **Curate the next prompt** by grafting the strongest phrasing from one or more
   prior prompts into a new prompt file (keep the discarded ideas in `#` comments as a
   record of what was tried).
5. Repeat. When a frame is the keeper, hand it to **`art-edit`** for transparent
   background, cropping, and any text/wordmark overlay.

# Notes

- 4K is gemini-only; imagen requests are clamped to 1K/2K.
- `--ref` and multi-turn conditioning apply to the gemini backend only.
- Maintainers: the quality gate is `make -C .claude/skills/art-gen/scripts ci`
  (format-check, lint, typecheck, ≥90% coverage). Offline tests inject fakes through
  the client/config seams. Live, real-credential validation is done via the CLI (run a
  real `generate`), **not** via pytest — routing a key through pytest can leak it in a
  traceback. See `CLAUDE.md` ADR-008.
