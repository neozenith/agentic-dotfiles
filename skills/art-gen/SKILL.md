---
name: art-gen
description: "Generate images from curated prompt files via Google's GenAI image models (Gemini 'Nano Banana' + Imagen 4). Each image is written with a JSON sidecar recording the exact prompt and settings, so runs are reproducible and the next prompt can be curated from prior ones. Supports fan-out across multiple prompt files in one invocation. Use when the user wants to generate, explore, or iterate on logos, icons, illustrations, or other AI imagery from text prompts. Requires either a non-empty GOOGLE_API_KEY or gcloud application-default credentials (Vertex AI)."
argument-hint: "generate --prompt-file <file.md> [--prompt-file <file2.md> ...] [--backend gemini|imagen] [--model flash|pro|standard|ultra|fast] [--aspect 1:1] [--size 1K|2K|4K] [--count N] [--ref <img>] [--out-dir <dir>] [--auth auto|api-key|adc] [--project <gcp-project>] [--location <region>]  |  history --out-dir <dir>"
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

| Backend | `--model` alias → API id | Best for |
|---------|--------------------------|----------|
| `gemini` (default) | `pro` → `gemini-3-pro-image` (Nano Banana Pro) | 4K, best text rendering, complex layouts |
| | `flash` → `gemini-3.1-flash-image` (Nano Banana 2) | Cheap high-volume iteration; 0.5K–4K |
| | `flash-2.5` → `gemini-2.5-flash-image` (Nano Banana) | The original; fast/cheap |
| `imagen` | `standard`/`ultra`/`fast` → `imagen-4.0-*-generate-001` | Photoreal standalone batches (`--count`), 1K/2K |

A raw model id can be passed to `--model` and is forwarded verbatim. Model ids are pinned
to GA releases (captured 2026-06-01); they churn, so re-verify against
`ai.google.dev/gemini-api/docs/models` when updating. Aspect ratios include wide/panoramic
options (`21:9`, `4:1`, `8:1`, `1:4`, `1:8`) for gemini; imagen supports only `1:1/3:4/4:3/9:16/16:9`.

# Requirements

- **Credentials — either mode works.** `--auth` selects one; the default `auto` prefers
  the API key, falls back to ADC, and logs which it chose. If neither is usable the run
  fails fast, naming both remedies.

  | `--auth` | Needs | Endpoint |
  |----------|-------|----------|
  | `api-key` | non-empty `GOOGLE_API_KEY` | Gemini Developer API |
  | `adc` | `gcloud auth application-default login` + a resolvable project | Vertex AI |
  | `auto` (default) | either of the above | whichever it picked (announced) |

  For `adc`, the project resolves `--project` → `GOOGLE_CLOUD_PROJECT` → the ADC file's
  `quota_project_id`, and the location `--location` → `GOOGLE_CLOUD_LOCATION` → `global`.
  `CLOUDSDK_CONFIG` is honoured when locating the ADC file, so per-project gcloud configs
  work. The chosen mode is recorded in every sidecar under `auth`.
- **`uv`** in `PATH`. The script declares its deps via PEP 723 inline metadata
  (`google-genai`, `Pillow`); `uv` materialises the venv on first run.
- **Internet access** for the GenAI API call.

# Before you spend: the pre-flight checklist

Generation costs money and prompts fail in **recurring, learnable ways** (naming a word you
don't want rendered makes the model draw it; "four people" yields three; generic objects grow
real brand badges). Before sending any request, read and apply
`.claude/skills/art-gen/resources/learned/prompt_checklist.md` — a self-curated list of real
failures, each written as a quick check. Treat its entries as already-decided.

**When a run comes back wrong, append the case to that file in the same session** (Symptom /
Case-with-date / Why / Check). That is how the checklist accumulates — the fix for a failure
mode is a durable entry, not a one-off reword.

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

# Force Vertex AI via application-default credentials (no API key involved)
uv run .claude/skills/art-gen/scripts/art_gen.py generate \
    --auth adc --project my-gcp-project --prompt-file prompt.md

# Review prior prompts/metadata to curate the next one (oldest → newest)
uv run .claude/skills/art-gen/scripts/art_gen.py history --out-dir art/gen
```

# Video clips (`art_vid.py` — Veo)

The video sibling, same contract: curated prompt file in, media out, JSON sidecar as a
**complete revision snapshot** (exact prompt sent, model id, every parameter, keyframes,
estimated cost) — so the next revision is a minimal delta from a known point.

```bash
# One clip pinned between two exact keyframes, with the shared story arc prepended
uv run .claude/skills/art-gen/scripts/art_vid.py generate \
    --prompt-file clips/01/prompt.md --story-arc clips/STORY.md \
    --start-frame keyframes/01.png --end-frame keyframes/02.png \
    --out-dir clips/01 --name clip01 \
    --model fast --resolution 1080p --duration 8 --location us-central1

uv run .claude/skills/art-gen/scripts/art_vid.py generate ... --dry-run   # prompt + cost, no spend
uv run .claude/skills/art-gen/scripts/art_vid.py frames clips/01/clip01.mp4   # re-extract first/last
uv run .claude/skills/art-gen/scripts/art_vid.py history --out-dir clips      # clips + running cost
```

| Concept | What it does |
|---------|--------------|
| **Story arc** (`--story-arc`) | A macro narrative prepended (labelled) to every clip prompt so an 8s fragment is generated knowing the whole film. Stored in each sidecar — changing it changes every clip. |
| **Keyframe pair** (`--start-frame` / `--end-frame`) | Veo first-frame + `last_frame` interpolation, so consecutive clips cut together. |
| **Frame extraction** | ffmpeg writes `<clip>.first.png` / `<clip>.last.png`. **Chain from the rendered last frame**, not the requested keyframe — the model never lands exactly on the request. |
| **Negative prompt** | Defaults to excluding dialogue/voiceover/captions/music, so clips stay diegetic-only. |

**Model ids are backend-specific** (`--backend`): Vertex/ADC serves GA `veo-3.1-*-generate-001`;
the Gemini API serves `veo-3.1-*-generate-preview`. Using the wrong set 404s. Veo is also
**region-restricted** — `--location us-central1`, never `global`.

Cost is **per second** (audio included): standard $0.40 (720p/1080p) / $0.60 (4k);
fast $0.10–$0.30; lite $0.05–$0.08. An 8s fast 1080p clip ≈ **$0.96**; standard ≈ **$3.20**.
Always `--dry-run` first.

# Output & Sidecars

Each image is written as `art_<YYYYMMDD_HHMMSS>_<index>.png` with a matching
`art_<...>.json` sidecar:

```json
{
  "prompt": "…the exact text sent…",
  "model": "gemini-3-pro-image",
  "backend": "gemini",
  "timestamp": "20260601_120000",
  "index": 0,
  "dimensions": "1024x1024",
  "aspect": "1:1",
  "requested_size": null,
  "estimated_cost_usd": 0.134,
  "prompt_file": "prompt.md"
}
```

`estimated_cost_usd` is a budgeting estimate derived from the model id and the actual
output resolution (gemini is resolution-tiered, imagen is flat per image); it is `null`
for an unrecognised model. The `history` subcommand sums these into a running total with a
per-model breakdown. Because filenames are timestamped, `ls` reads chronologically and the
sidecars preserve the full provenance — and cost — of the sweep.

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
