#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "google-genai>=1.0.0",
#   "Pillow>=10.0.0",
# ]
# ///
"""art-vid — generate video clips from curated prompt files via Google's Veo models.

The video sibling of ``art_gen.py``, built on the same contract: a curated prompt file in,
a media file out, and a JSON sidecar that is a **complete revision snapshot** — the exact
prompt sent, the model id, every input parameter, the keyframes used, and an estimated
cost. Because what a human asks for is never the literal prompt sent to the service, the
sidecar is what lets the next revision be expressed as a minimal delta from a known point.

Three ideas beyond the image workflow:

  story arc   A macro narrative shared by every clip is prepended to each clip's micro
              prompt, so an 8-second shot is generated knowing the whole story. The arc
              text is stored in the sidecar, because changing it changes every clip.
  keyframes   A clip can be pinned to an exact start image and an exact end image
              (Veo first-frame + ``last_frame`` interpolation), which is what makes a
              sequence of clips cut together.
  frames      ffmpeg extracts the real first/last frame of the produced clip as sibling
              PNGs, so clip N's last frame can become clip N+1's start frame — the chain
              is built from what was actually rendered, not what was requested.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Configuration ──────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

# Marketing name → API model id, **per backend**. Verified 2026-07-24 by listing publisher
# models: Vertex serves GA ids (`-001`); the Gemini Developer API serves `-preview` ids. Using
# the wrong set 404s. Veo 3.0 is superseded; 3.1 only.
VEO_MODELS_BY_BACKEND: dict[str, dict[str, str]] = {
    "vertex": {
        "standard": "veo-3.1-generate-001",
        "fast": "veo-3.1-fast-generate-001",
        "lite": "veo-3.1-lite-generate-001",
    },
    "gemini": {
        "standard": "veo-3.1-generate-preview",
        "fast": "veo-3.1-fast-generate-preview",
        "lite": "veo-3.1-lite-generate-preview",
    },
}
DEFAULT_BACKEND = "vertex"
DEFAULT_VEO_ALIAS = "fast"  # prototyping default — ~4x cheaper than standard

# USD **per second** of generated video, keyed by model FAMILY and resolution (audio included).
# Family-keyed so one table prices both the `-001` and `-preview` id schemes.
# Captured 2026-07-24 from ai.google.dev/gemini-api/docs/pricing.
VEO_PRICING_USD: dict[str, dict[str, float]] = {
    "standard": {"720p": 0.40, "1080p": 0.40, "4k": 0.60},
    "fast": {"720p": 0.10, "1080p": 0.12, "4k": 0.30},
    "lite": {"720p": 0.05, "1080p": 0.08},
}

RESOLUTIONS = ["720p", "1080p", "4k"]
DURATIONS = [4, 6, 8]
ASPECT_RATIOS = ["16:9", "9:16"]
DEFAULT_OUTPUT_DIR = Path("clips")
POLL_SECONDS = 10
# Veo publisher models are not served from the Vertex "global" endpoint; pick a real region.
DEFAULT_VERTEX_LOCATION = "us-central1"

# What we never want in these clips unless asked — kept as a constant so every clip inherits
# the same audio/style exclusions and the sidecar records them verbatim.
DEFAULT_NEGATIVE_PROMPT = (
    "dialogue, talking, speech, voiceover, narration, lip movement, subtitles, captions, "
    "on-screen text, background music, soundtrack, score"
)


# ── Pure helpers (no network, fully unit-tested) ───────────────────────────
def timestamp_now() -> str:
    """Filesystem-sortable timestamp, e.g. ``20260724_143501``."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_prompt_file(path: Path) -> str:
    """Read a prompt from markdown, dropping heading/comment lines.

    Same contract as ``art_gen``: ``#`` and ``<!--`` lines document intent and iteration
    history without being sent to the model, so a prompt file can carry its own changelog.
    """
    raw = path.read_text(encoding="utf-8")
    kept = [ln for ln in raw.splitlines() if not ln.strip().startswith(("#", "<!--"))]
    prompt = "\n".join(kept).strip()
    if not prompt:
        raise ValueError(f"Prompt file is empty after stripping comments: {path}")
    return prompt


def resolve_model(alias: str | None, backend: str = DEFAULT_BACKEND) -> str:
    """Map a friendly alias to the model id for this backend; unknown aliases pass through."""
    table = VEO_MODELS_BY_BACKEND.get(backend, VEO_MODELS_BY_BACKEND[DEFAULT_BACKEND])
    if alias is None:
        return table[DEFAULT_VEO_ALIAS]
    return table.get(alias, alias)


def veo_family(model: str) -> str | None:
    """Classify a Veo model id into its pricing family (``lite``/``fast``/``standard``).

    Keyed on substrings rather than exact ids so the same table prices Vertex `-001` ids,
    Gemini `-preview` ids, and whatever the next revision is named.
    """
    name = model.lower()
    if "veo" not in name:
        return None
    if "lite" in name:
        return "lite"
    if "fast" in name:
        return "fast"
    return "standard"


def compose_prompt(clip_prompt: str, story_arc: str | None = None) -> str:
    """Combine the macro story arc with this clip's micro direction.

    The arc goes FIRST and is explicitly labelled: the model reads the whole-story context
    before the shot-specific detail, which keeps 8-second fragments consistent with each
    other instead of each re-inventing the world.
    """
    clip = clip_prompt.strip()
    if not story_arc or not story_arc.strip():
        return clip
    return f"STORY CONTEXT (the whole film, for consistency):\n{story_arc.strip()}\n\nTHIS SHOT:\n{clip}"


def estimate_video_cost(model: str, resolution: str, duration_seconds: int) -> float | None:
    """Estimated USD for one clip, or ``None`` when the model/resolution isn't priced."""
    family = veo_family(model)
    tiers = VEO_PRICING_USD.get(family) if family else None
    if tiers is None:
        return None
    rate = tiers.get(resolution)
    if rate is None:
        return None
    return round(rate * float(duration_seconds), 4)


def build_metadata(
    *,
    prompt: str,
    model: str,
    timestamp: str,
    duration_seconds: int,
    resolution: str,
    aspect: str,
    story_arc: str | None = None,
    story_arc_file: Path | None = None,
    clip_prompt: str | None = None,
    prompt_file: Path | None = None,
    start_frame: Path | None = None,
    end_frame: Path | None = None,
    negative_prompt: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The sidecar payload: everything needed to regenerate or diff this clip.

    ``prompt`` is the EXACT text sent to Veo (arc + shot). ``clip_prompt`` and ``story_arc``
    are kept separately as well, so a later revision can change one without re-deriving the
    other — the whole reason the sidecar exists.
    """
    meta: dict[str, Any] = {
        "kind": "video",
        "prompt": prompt,
        "model": model,
        "backend": "veo",
        "timestamp": timestamp,
        "duration_seconds": duration_seconds,
        "resolution": resolution,
        "aspect": aspect,
        "negative_prompt": negative_prompt,
        "estimated_cost_usd": estimate_video_cost(model, resolution, duration_seconds),
    }
    if clip_prompt is not None:
        meta["clip_prompt"] = clip_prompt
    if story_arc is not None:
        meta["story_arc"] = story_arc
    if story_arc_file is not None:
        meta["story_arc_file"] = str(story_arc_file)
    if prompt_file is not None:
        meta["prompt_file"] = str(prompt_file)
    if start_frame is not None:
        meta["start_frame"] = str(start_frame)
    if end_frame is not None:
        meta["end_frame"] = str(end_frame)
    if extra:
        meta.update(dict(extra))
    return meta


def build_video_config_kwargs(
    *,
    duration_seconds: int | None = None,
    resolution: str | None = None,
    aspect: str | None = None,
    negative_prompt: str | None = None,
    number_of_videos: int = 1,
    has_end_frame: bool = False,
) -> dict[str, Any]:
    """Assemble ``GenerateVideosConfig`` kwargs, omitting anything unset.

    Only sending explicitly-chosen options matters: the Veo config surface changes between
    previews, and passing a parameter a given model doesn't accept fails the whole (paid)
    request. ``last_frame`` is added by the caller because it needs a real Image object.
    """
    kwargs: dict[str, Any] = {"number_of_videos": number_of_videos}
    if duration_seconds is not None:
        kwargs["duration_seconds"] = int(duration_seconds)
    if resolution:
        kwargs["resolution"] = resolution
    if aspect:
        kwargs["aspect_ratio"] = aspect
    if negative_prompt:
        kwargs["negative_prompt"] = negative_prompt
    if has_end_frame:
        kwargs["_needs_last_frame"] = True  # marker resolved by the caller
    return kwargs


def clip_paths(out_dir: Path, stem: str) -> dict[str, Path]:
    """Every sibling artifact for a clip, derived from one stem — one naming rule."""
    return {
        "video": out_dir / f"{stem}.mp4",
        "sidecar": out_dir / f"{stem}.json",
        "first": out_dir / f"{stem}.first.png",
        "last": out_dir / f"{stem}.last.png",
    }


def read_history(out_dir: Path) -> list[dict[str, Any]]:
    """Load clip sidecars oldest-to-newest so revisions read as a sequence."""
    items: list[dict[str, Any]] = []
    for jf in sorted(out_dir.rglob("*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Skipping unreadable sidecar: %s", jf)
            continue
        if not isinstance(data, dict) or data.get("kind") != "video":
            continue
        data["_sidecar"] = str(jf)
        items.append(data)
    return items


def format_history(items: Sequence[Mapping[str, Any]]) -> str:
    """Render clip history with per-clip and total estimated cost."""
    if not items:
        return "No prior clips found."
    lines: list[str] = []
    total = 0.0
    unpriced = 0
    for i, it in enumerate(items):
        cost = it.get("estimated_cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            total += float(cost)
            cost_str = f"${float(cost):.2f}"
        else:
            unpriced += 1
            cost_str = "$?"
        prompt = str(it.get("clip_prompt") or it.get("prompt", "")).replace("\n", " ")
        preview = prompt if len(prompt) <= 200 else prompt[:197] + "..."
        lines.append(
            f"[{i}] {it.get('_sidecar', '?')}  ({cost_str}, {it.get('model', '?')}, "
            f"{it.get('duration_seconds', '?')}s {it.get('resolution', '?')})\n    {preview}"
        )
    note = f"   ({unpriced} without a price estimate)" if unpriced else ""
    lines += ["", f"Total ({len(items)} clips): ${total:.2f}{note}"]
    return "\n".join(lines)


# ── ffmpeg frame extraction (real subprocess; covered by a fake runner in tests) ──
def ffmpeg_available() -> bool:
    """True when an ffmpeg binary is on PATH."""
    return shutil.which("ffmpeg") is not None


def extract_frames(
    video: Path,
    first_out: Path,
    last_out: Path,
    runner: Any = subprocess.run,
) -> dict[str, Path]:
    """Write the clip's real first and last frames as PNG siblings.

    Chaining clips uses what was *actually rendered* (this last frame), not the keyframe
    that was requested — the model never lands exactly on the requested end image, so
    seeding the next clip from the request would visibly jump at the cut.
    """
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg not found on PATH — needed to extract first/last frames")
    first_out.parent.mkdir(parents=True, exist_ok=True)
    # First frame: plain seek to 0. Last frame: reverse-select the final frame.
    runner(["ffmpeg", "-y", "-i", str(video), "-vf", "select=eq(n\\,0)", "-vframes", "1", str(first_out)], check=True)
    runner(["ffmpeg", "-y", "-sseof", "-1", "-i", str(video), "-update", "1", "-q:v", "1", str(last_out)], check=True)
    return {"first": first_out, "last": last_out}


# ── Boundary: the live Veo call (import-guarded; validated via the CLI, not pytest) ──
def _load_image(path: Path) -> Any:  # pragma: no cover - requires google-genai
    from google.genai import types

    return types.Image.from_file(location=str(path))


def generate_clip(  # pragma: no cover - network + paid; validated by running the CLI
    client: Any,
    prompt: str,
    model: str,
    out_video: Path,
    *,
    config_kwargs: Mapping[str, Any],
    start_frame: Path | None = None,
    end_frame: Path | None = None,
    poll_seconds: int = POLL_SECONDS,
) -> Path:
    """Submit a Veo job, poll to completion, and save the mp4."""
    from google.genai import types

    kwargs = {k: v for k, v in config_kwargs.items() if not k.startswith("_")}
    if end_frame is not None:
        kwargs["last_frame"] = _load_image(end_frame)
    config = types.GenerateVideosConfig(**kwargs)

    call: dict[str, Any] = {"model": model, "prompt": prompt, "config": config}
    if start_frame is not None:
        call["image"] = _load_image(start_frame)

    log.info("Submitting Veo job (%s)…", model)
    operation = client.models.generate_videos(**call)
    waited = 0
    while not operation.done:
        time.sleep(poll_seconds)
        waited += poll_seconds
        log.info("  …still rendering (%ds)", waited)
        operation = client.operations.get(operation)

    generated = operation.response.generated_videos[0]
    out_video.parent.mkdir(parents=True, exist_ok=True)
    save_generated_video(client, generated.video, out_video)
    log.info("Saved %s", out_video)
    return out_video


def save_generated_video(client: Any, video: Any, out_video: Path) -> Path:
    """Persist a returned video across both backends.

    Vertex hands back the bytes inline on the ``Video`` object; the Gemini Developer API
    returns a file handle that must be downloaded first (``files.download`` raises on
    Vertex). Preferring inline bytes means no backend-specific branch at the call site.
    """
    data = getattr(video, "video_bytes", None)
    if data:
        out_video.write_bytes(data)
        return out_video
    client.files.download(file=video)  # pragma: no cover - Gemini Developer API path
    video.save(str(out_video))  # pragma: no cover - Gemini Developer API path
    return out_video


# ── CLI ────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="art_vid.py",
        description="Generate Veo video clips from curated prompt files, with revision sidecars.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate one clip from a prompt file")
    gen.add_argument("--prompt-file", type=Path, default=None, help="Clip prompt markdown")
    gen.add_argument("--prompt", default=None, help="Inline prompt (wins over --prompt-file)")
    gen.add_argument("--story-arc", type=Path, default=None, help="Macro story file prepended to the clip prompt")
    gen.add_argument("--start-frame", type=Path, default=None, help="Exact first frame image")
    gen.add_argument("--end-frame", type=Path, default=None, help="Exact last frame image (interpolation)")
    gen.add_argument("--model", default=None, help="Alias (standard/fast/lite) or a raw model id")
    gen.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        choices=sorted(VEO_MODELS_BY_BACKEND),
        help="Which id set to use: vertex (GA -001, ADC auth) or gemini (-preview, API key)",
    )
    gen.add_argument("--duration", type=int, default=8, choices=DURATIONS, help="Clip seconds (default 8)")
    gen.add_argument("--resolution", default="1080p", choices=RESOLUTIONS, help="Output resolution")
    gen.add_argument("--aspect", default="16:9", choices=ASPECT_RATIOS, help="Aspect ratio")
    gen.add_argument("--negative-prompt", default=DEFAULT_NEGATIVE_PROMPT, help="What to exclude (audio/style)")
    gen.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Output dir (default {DEFAULT_OUTPUT_DIR})"
    )
    gen.add_argument("--name", default=None, help="Clip stem (default: timestamped)")
    gen.add_argument("--dry-run", action="store_true", help="Print the composed prompt + cost, call nothing")
    gen.add_argument("--project", default=None, help="GCP project for ADC/Vertex auth")
    gen.add_argument(
        "--location",
        default=DEFAULT_VERTEX_LOCATION,
        help=f"Vertex region (default {DEFAULT_VERTEX_LOCATION}). Veo is region-restricted; "
        "'global' has no Veo publisher model.",
    )

    fr = sub.add_parser("frames", help="Extract first/last frames from an existing clip")
    fr.add_argument("video", type=Path)

    hist = sub.add_parser("history", help="List prior clips with costs")
    hist.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    for q in (gen, fr, hist):
        q.add_argument("-v", "--verbose", action="store_true")
        q.add_argument("-q", "--quiet", action="store_true")
    return p


def main(args: argparse.Namespace, client: Any | None = None) -> int:
    """Dispatch. ``client`` is injected by tests; production builds the live Veo client."""
    if args.command == "history":
        sys.stdout.write(format_history(read_history(args.out_dir)) + "\n")
        return 0

    if args.command == "frames":
        paths = clip_paths(args.video.parent, args.video.stem)
        extract_frames(args.video, paths["first"], paths["last"])
        sys.stdout.write(f"  first: {paths['first']}\n  last:  {paths['last']}\n")
        return 0

    # command == "generate"
    if args.prompt:
        clip_prompt, prompt_file = args.prompt, None
    elif args.prompt_file:
        clip_prompt, prompt_file = load_prompt_file(args.prompt_file), args.prompt_file
    else:
        raise ValueError("No prompt provided. Pass --prompt or --prompt-file.")

    story_arc = load_prompt_file(args.story_arc) if args.story_arc else None
    full_prompt = compose_prompt(clip_prompt, story_arc)
    model = resolve_model(args.model, getattr(args, "backend", DEFAULT_BACKEND))
    stem = args.name or f"clip_{timestamp_now()}"
    paths = clip_paths(args.out_dir, stem)
    cost = estimate_video_cost(model, args.resolution, args.duration)

    sys.stdout.write(
        f"  model:    {model}\n  duration: {args.duration}s @ {args.resolution} {args.aspect}\n"
        f"  est cost: {'$%.2f' % cost if cost is not None else '$?'}\n  output:   {paths['video']}\n"
    )
    if args.dry_run:
        sys.stdout.write("\n── composed prompt ──\n" + full_prompt + "\n")
        return 0

    config_kwargs = build_video_config_kwargs(
        duration_seconds=args.duration,
        resolution=args.resolution,
        aspect=args.aspect,
        negative_prompt=args.negative_prompt,
        has_end_frame=args.end_frame is not None,
    )
    if client is None:  # pragma: no cover - live path
        from art_gen import make_client, resolve_auth

        auth = resolve_auth("auto", project=getattr(args, "project", None), location=getattr(args, "location", None))
        log.info("auth: %s", auth.describe())
        client = make_client(auth)

    generate_clip(
        client,
        full_prompt,
        model,
        paths["video"],
        config_kwargs=config_kwargs,
        start_frame=args.start_frame,
        end_frame=args.end_frame,
    )

    extracted: dict[str, Any] = {}
    if ffmpeg_available():
        extract_frames(paths["video"], paths["first"], paths["last"])
        extracted = {"first_frame": str(paths["first"]), "last_frame": str(paths["last"])}
    else:  # pragma: no cover - depends on host
        log.warning("ffmpeg not on PATH — skipping first/last frame extraction")

    meta = build_metadata(
        prompt=full_prompt,
        model=model,
        timestamp=timestamp_now(),
        duration_seconds=args.duration,
        resolution=args.resolution,
        aspect=args.aspect,
        story_arc=story_arc,
        story_arc_file=args.story_arc,
        clip_prompt=clip_prompt,
        prompt_file=prompt_file,
        start_frame=args.start_frame,
        end_frame=args.end_frame,
        negative_prompt=args.negative_prompt,
        extra={
            "config": {k: v for k, v in config_kwargs.items() if not k.startswith("_")},
            "location": getattr(args, "location", None),
            **extracted,
        },
    )
    paths["sidecar"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    sys.stdout.write(f"  saved: {paths['video']}\n  sidecar: {paths['sidecar']}\n")
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
    except (RuntimeError, ValueError) as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc
