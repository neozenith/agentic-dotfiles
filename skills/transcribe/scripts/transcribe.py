#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mlx-whisper>=0.4.0",
#   "srt>=3.5.3",
# ]
# ///
"""
Local Whisper transcription → SRT, via mlx-whisper (Apple Silicon native).

Accepts any audio OR video file ffmpeg can decode (mp3, mp4, mkv, wav, mov,
webm, etc.). Output is an SRT file written next to the input by default.

Usage:
    transcribe.py <input> [--out <srt>] [--model <size>] [--language <code>] [--force]
    transcribe.py recording.mp4
    transcribe.py podcast.mp3 --out tmp/podcast.srt --model large-v3
    transcribe.py interview.wav --language auto --model large-v3-turbo

Models (mlx-community/whisper-*-mlx on HuggingFace, downloaded on first use):
    large-v3        Best accuracy. ~3-8 min for 1h audio on M-series. (default)
    large-v3-turbo  ~2x faster than large-v3, slight accuracy loss on jargon /
                    overlapping speech. Good for first looks and bulk runs.
    medium          ~1.5GB download, faster still, lower accuracy. Smoke tests.

Requirements:
    - Apple Silicon Mac (mlx-whisper uses Apple's MLX framework — no CUDA path).
    - ffmpeg in PATH (mlx-whisper shells out to it to decode audio).
    - Internet access on first invocation of a given model (HuggingFace download
      to ~/.cache/huggingface/).
"""
import argparse
import datetime as dt
import shutil
import sys
import time
from pathlib import Path

import mlx_whisper
import srt

MODELS = {
    "large-v3":       "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "medium":         "mlx-community/whisper-medium-mlx",
}

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="transcribe",
        description="Local Whisper transcription via mlx-whisper. Emits SRT subtitles.",
    )
    p.add_argument("input", nargs="?", type=Path,
                   help="Audio or video file to transcribe (anything ffmpeg can decode)")
    p.add_argument("--out", type=Path, default=None,
                   help="Output SRT path (default: <input-stem>.srt next to the input)")
    p.add_argument("--model", choices=list(MODELS.keys()), default="large-v3",
                   help="Whisper model size (default: large-v3)")
    p.add_argument("--language", default="en",
                   help="Language code (e.g. en, es, fr) or 'auto' to detect (default: en)")
    p.add_argument("--force", action="store_true",
                   help="Overwrite the output SRT if it already exists")
    p.set_defaults(func=cmd_transcribe)
    return p

def cmd_transcribe(args: argparse.Namespace) -> None:
    if args.input is None:
        print("error: <input> is required. Run with --help for usage.", file=sys.stderr)
        sys.exit(2)

    audio = args.input.resolve()
    if not audio.exists():
        print(f"error: input file not found: {audio}", file=sys.stderr)
        sys.exit(1)
    if shutil.which("ffmpeg") is None:
        print("error: ffmpeg not found in PATH (required by mlx-whisper to decode audio)", file=sys.stderr)
        sys.exit(1)

    out_path = (args.out or audio.with_suffix(".srt")).resolve()
    if out_path.exists() and not args.force:
        print(
            f"error: output already exists: {out_path}\n"
            f"       pass --force to overwrite, or --out <path> to write elsewhere.",
            file=sys.stderr,
        )
        sys.exit(1)

    repo = MODELS[args.model]
    print(f"▶ Transcribing {audio.name} with {args.model} ({repo})", file=sys.stderr)
    t0 = time.time()
    result = mlx_whisper.transcribe(
        str(audio),
        path_or_hf_repo=repo,
        word_timestamps=True,
        # condition_on_previous_text=False reduces hallucination drift on long
        # audio at the cost of less consistent punctuation across segments.
        condition_on_previous_text=False,
        language=None if args.language == "auto" else args.language,
        verbose=False,
    )
    print(f"  done in {time.time() - t0:.1f}s — {len(result['segments'])} segments", file=sys.stderr)

    subs = [
        srt.Subtitle(
            index=i,
            start=dt.timedelta(seconds=float(seg["start"])),
            end=dt.timedelta(seconds=float(seg["end"])),
            content=seg["text"].strip(),
        )
        for i, seg in enumerate(result["segments"], 1)
        if seg["text"].strip()
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(srt.compose(subs), encoding="utf-8")
    print(f"✓ wrote {len(subs)} cues → {out_path}", file=sys.stderr)

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
