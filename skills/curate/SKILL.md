---
name: curate
description: "Split and trim a single source video into multiple chapter mp4s via a hand-edited JSON spec (edits.json). Uses ffmpeg for frame-accurate cuts and configurable output filenames. Use when the user wants to chapter a long recording, trim sections out of a video, or produce per-chapter mp4s from one source with custom naming conventions."
argument-hint: "[--config <path>] [--probe|--dry-run] [--only <Ch07,intro,...>] [--input <file.mp4>] [--no-yaml]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(.claude/skills/curate/scripts/curate.py *)
  - Bash(ffmpeg *)
  - Bash(ffprobe *)
user-invocable: true
---

# Context

A reproducible video chaptering pipeline. The user hand-edits a JSON spec
(`edits.json`) that declares chapter windows and intra-chapter cuts; the
script consumes the spec and emits one mp4 per chapter via ffmpeg. The
source video is **never** modified — reruns overwrite the chapter outputs.

This pattern is for recordings that need an iterative edit cycle: live
sessions, talks, meetings, tutorials. The spec is the source of truth; the
videos are derivations. Re-running after a timestamp tweak takes the same time
as the first run (no incremental build), but the trade-off is total
reproducibility and a tiny git-friendly text file (`edits.json`) instead of an
opaque NLE project file.

# Requirements

- **ffmpeg + ffprobe** in `PATH`. The encode uses libx264 CRF 20 with `-preset fast` —
  about 15-17× realtime on modern CPUs.
- **Node 18+** (uses native fetch and modern ESM). No npm dependencies.
- A **single source mp4** in `<project>/originals/` (or specify `"source"` in
  config). The script auto-detects when exactly one .mp4 is present and warns
  if there are multiple.

# Project Layout

```
<project>/
├── edits.json          # hand-edited spec (source of truth)
├── edits.yaml          # AUTO-derived review doc — do NOT hand-edit
├── originals/          # drop the source video here (single .mp4)
│   └── source.mp4
└── curated/            # output chapter mp4s land here (overwritten on each run)
    ├── Ch01-intro-04m55s.mp4
    └── Ch02-deep-dive-12m30s.mp4
```

`originals/` and `curated/` are the convention; override via the `originals_dir`
and `output_dir` config keys if needed.

# Config Schema (`edits.json`)

```json
{
  "project":       "myproject",                             // optional; substitutes into {project} in naming
  "naming":        "{project}-Ch{n}-{title}-{dur}.mp4",     // optional; default "Ch{n}-{title}-{dur}.mp4"
  "source":        "originals/source.mp4",                  // optional; auto-detected if exactly one .mp4 in originals/
  "originals_dir": "originals",                             // optional; default "originals"
  "output_dir":    "curated",                               // optional; default "curated"
  "chapters": [
    {
      "name":      "introduction",                          // slug; substitutes into {title}
      "start_ts":  "00:01:00",                              // window start in source video
      "end_ts":    "00:05:55",                              // window end (exclusive)
      "cuts": [                                             // optional intra-chapter trims
        { "start_ts": "00:03:00", "end_ts": "00:03:10", "notes": "filler" }
      ],
      "notes":     "optional chapter notes (carried into edits.yaml only)"
    }
  ]
}
```

## Naming-template tokens

| Token       | Substitution                                          |
|-------------|-------------------------------------------------------|
| `{project}` | `config.project` (empty string if not set)            |
| `{n}`       | 1-indexed chapter number, zero-padded to 2 digits     |
| `{title}`   | `chapter.name` (the slug)                             |
| `{dur}`     | final chapter duration as `MMmSSs` (e.g. `09m34s`)    |
| `{start}`   | chapter window start as `MMmSSs`                      |
| `{end}`     | chapter window end as `MMmSSs`                        |

Defaults to `Ch{n}-{title}-{dur}.mp4`. The `{dur}` token reflects the **final**
duration (window minus cuts), so the filename matches what a player will show
on the timeline.

# Workflow

1. **Scaffold.** From the desired project directory:
   ```bash
   mkdir -p originals curated
   # Drop your source video into originals/
   # Create edits.json with at minimum a "chapters" array
   ```

2. **First draft of `edits.json`.** Define chapter `start_ts`/`end_ts` from your
   notes. Leave `cuts: []` until you've reviewed the output.

3. **Probe (no encoding).** Validate the chapter math:
   ```bash
   .claude/skills/curate/scripts/curate.py --probe
   ```
   Reports each chapter's window, keep-segments, and any gap/overlap warnings
   between consecutive chapters. Gaps are NOT errors — content in a gap is
   simply excluded from all outputs.

4. **Encode.** Run without `--probe` to produce the chapter mp4s. Subset with
   `--only Ch07,intro` (matches the Ch## tag, title slug, or full filename).

5. **Review with `edits.yaml`.** The auto-generated YAML beside `edits.json`
   contains computed durations, cut percentages, and **`output_join_ts`** — the
   timestamp inside the curated mp4 where each splice lands. Open the chapter
   in a player and seek to `output_join_ts` to audit join quality.

6. **Iterate.** Tweak `edits.json`, re-run. Repeat until satisfied.

# Examples

```bash
# Probe only — print chapter math, no encoding
.claude/skills/curate/scripts/curate.py --probe

# Encode every chapter
.claude/skills/curate/scripts/curate.py

# Re-encode just chapters 7 and 10
.claude/skills/curate/scripts/curate.py --only Ch07,Ch10

# Re-encode by title slug
.claude/skills/curate/scripts/curate.py --only introduction

# Dry-run: print the ffmpeg commands without executing
.claude/skills/curate/scripts/curate.py --dry-run

# Use an explicit config (when not running from the project dir)
.claude/skills/curate/scripts/curate.py --config /path/to/project/edits.json
```

# Steps for the agent

1. **Locate the project root.** Either cwd contains an `edits.json`, or the
   user names a directory. If neither exists, scaffold one and ask what the
   source video and chapters are.
2. **Validate the config schema.** If `edits.json` is a bare array (a legacy
   pre-config format), migrate it to the object form: wrap chapters in
   `{ "chapters": [...] }` and add `project` + `naming` if the user wants a
   custom filename pattern.
3. **Run `--probe` first** to surface gap/overlap warnings before encoding.
   Encoding an hour of video takes ~3-5 minutes; probe is instant.
4. **Encode**, then report wall-clock time, output paths, and any warnings.
5. **Show the user `edits.yaml`** for review — point them at `output_join_ts`
   for verifying splice quality on chapters with cuts.

# Caveats

- **Single-source assumption.** The pipeline is designed for one source video
  producing N chapters. Multi-source projects need a separate `edits.json` per
  source video (run the script with `--config <each one>`).
- **Encoder is fixed** at libx264 CRF 20 / aac 160k. If you need a different
  codec/quality, edit the `ffmpegArgs` array in `curate.py` — there's no
  config knob for this yet (YAGNI until a real use case appears).
- **Re-runs always overwrite.** No incremental build, no `--force` guard. The
  spec is the source of truth and outputs are derivations, so this is by
  design — but it means hand-editing a curated mp4 is futile.
- **`originals/foo--subbed.mp4`** is ignored by the source auto-detect (skipped
  by suffix), so you can keep subtitled copies alongside the original without
  ambiguity.
- **Cuts that overlap** are merged with a warning. Cuts that extend beyond the
  chapter window are clamped with a warning. Both are surfaced in `edits.yaml`
  under `warnings:` so you don't miss them.
