---
name: transcribe
description: "Local Whisper speech-to-text via mlx-whisper (Apple Silicon native). Produces an SRT subtitle file from any audio or video file ffmpeg can decode. Use when the user wants to transcribe audio, generate subtitles, or produce a verification copy of an existing transcript."
argument-hint: "<audio-or-video-file> [--model large-v3|large-v3-turbo|medium] [--language en|auto|...] [--out <srt-path>] [--force]"
allowed-tools:
  - Read
  - Bash(.claude/skills/transcribe/scripts/transcribe.py *)
user-invocable: true
---

# Context

Runs OpenAI's Whisper speech-to-text model **locally** via Apple's MLX framework
(`mlx-whisper`). Produces a standard SRT subtitle file you can:

- Embed into an mp4 with `ffmpeg -c:s mov_text` (soft subtitles, viewer toggles them).
- Burn into a video with `ffmpeg -vf subtitles=...` (re-encodes; universal display).
- Diff against an existing transcript (e.g. a meeting-notes app export) as a verification copy.
- Use directly in players that support sidecar SRT (VLC, mpv, IINA).

**Why mlx-whisper specifically?** On Apple Silicon it's the fastest Whisper runtime
that preserves reference-quality output — roughly 3x faster than `whisper.cpp` and
5x faster than the original `openai-whisper`. On non-Apple-Silicon hardware this
skill will not work — use `faster-whisper` (CTranslate2) instead.

**Note on Ollama:** Ollama does NOT serve Whisper or any STT model. It's
LLM-only. Don't try to route this through Ollama.

# Requirements

- **Apple Silicon Mac** (M1/M2/M3/M4 series). MLX is Apple-only.
- **ffmpeg** in `PATH`. mlx-whisper shells out to ffmpeg to decode audio. The
  script aborts with a clear error if ffmpeg is missing.
- **uv** in `PATH`. The script uses PEP 723 inline metadata — `uv` materialises
  the venv automatically on first invocation.
- **Internet access** on first run of each model size (HuggingFace download to
  `~/.cache/huggingface/`). Subsequent runs are offline.

# Usage

```bash
# Transcribe an audio file, write <stem>.srt next to it (default model: large-v3)
.claude/skills/transcribe/scripts/transcribe.py path/to/audio.mp3

# Video file — ffmpeg decodes the audio stream automatically
.claude/skills/transcribe/scripts/transcribe.py path/to/meeting.mp4

# Faster model for a first look
.claude/skills/transcribe/scripts/transcribe.py interview.wav --model large-v3-turbo

# Auto-detect language; write SRT to a custom path
.claude/skills/transcribe/scripts/transcribe.py talk.mp3 --language auto --out tmp/talk.srt

# Overwrite an existing SRT (safety guard requires --force)
.claude/skills/transcribe/scripts/transcribe.py audio.mp3 --force
```

# Model Selection

| Model | First-run download | 1h audio | When to use |
|---|---|---|---|
| `large-v3` (default) | ~3 GB | 3-8 min | Best accuracy — single-shot or final transcript |
| `large-v3-turbo` | ~1.6 GB | ~half of large-v3 | Bulk runs, drafts, first looks; slight accuracy hit on jargon and overlapping speech |
| `medium` | ~1.5 GB | ~half of large-v3 | Smoke testing the pipeline; noticeably lower accuracy |

**Recommendation**: default to `large-v3` unless the user has explicitly asked
for speed. Whisper accuracy compounds across an hour of content — a small WER
delta becomes a lot of misheard words.

# Steps

1. **Confirm Apple Silicon and ffmpeg availability.** If unsure, run
   `uname -m` (expect `arm64`) and `which ffmpeg`. If on Intel Mac or Linux,
   tell the user and recommend `faster-whisper` instead.
2. **Identify the input file.** If the user gave a video, the script handles
   audio extraction internally via ffmpeg — no need to pre-extract.
3. **Choose a model.** Default to `large-v3`. Only deviate if the user asks for
   speed or it's a smoke test.
4. **Warn about first-run download.** If the chosen model hasn't been used
   before (`~/.cache/huggingface/hub/models--mlx-community--whisper-*` absent),
   tell the user the 3GB download is about to happen.
5. **Run the script.** It will print progress to stderr and write SRT to stdout
   path (default: input-with-.srt-suffix).
6. **Report.** Tell the user the cue count, runtime, and output path. If they
   asked for "verification" against an existing transcript, suggest opening
   both SRTs side-by-side in a diff tool.

# Caveats

- **No speaker labels.** Whisper does not do speaker diarization. If the user
  needs `[Alice]` / `[Bob]` tags, they'll need a separate diarization model
  (e.g. `pyannote.audio`) layered on top, OR cross-reference with an existing
  speaker-labeled transcript (the typical "verification copy" workflow).
- **Long-audio drift.** For audio over ~30 min, occasionally Whisper hallucinates
  or repeats a phrase. The script sets `condition_on_previous_text=False` to
  mitigate this — known mitigation, doesn't eliminate it. Skim the output.
- **Word-level timestamps are produced** (`word_timestamps=True`) but the SRT
  emitter groups them by Whisper's natural segment boundaries (~2-15s cues).
  If you need per-word SRT cues, modify the script to iterate `seg["words"]`.
- **Idempotence**: the script refuses to overwrite an existing SRT unless
  `--force` is passed. This is deliberate — Whisper runs are expensive, and the
  user often hand-edits the SRT after the fact.
