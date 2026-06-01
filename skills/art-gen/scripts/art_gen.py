#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "google-genai>=1.0.0",
#   "Pillow>=10.0.0",
# ]
# ///
"""art-gen — generate images from curated prompt files via Google's GenAI image models.

Two backends:
  gemini  — conversational image models (a.k.a. "Nano Banana"). Best for iteration
            and for supplying reference images alongside the prompt.
  imagen  — the Imagen 4 family. Best for high-fidelity standalone batches.

Auth:
  Requires a NON-EMPTY ``GOOGLE_API_KEY`` environment variable. This skill uses the
  API-key path only — it deliberately does NOT use Vertex AI / application-default
  credentials. If the variable is missing or blank, generation fails fast.

Sidecars:
  Every generated ``<stem>.png`` is written with a ``<stem>.json`` sidecar recording
  the exact prompt, model, backend, aspect/size, and source prompt file. Filenames are
  timestamped so the directory listing reads chronologically, and the sidecars let a
  later run curate the next prompt from elements of previous ones — see the ``history``
  subcommand, which prints prior prompts oldest-to-newest for exactly that purpose.

Fan-out:
  ``--prompt-file`` is repeatable. Passing several prompt files (e.g. pose variants)
  generates one image per file in a single invocation, so an exploration sweep is one
  command. ``--count`` additionally requests N variants per prompt on the imagen backend.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

# ── Configuration ──────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

API_KEY_ENV = "GOOGLE_API_KEY"

GEMINI_MODELS = {
    "flash": "gemini-2.5-flash-image",
    "pro": "gemini-3-pro-image-preview",
}
IMAGEN_MODELS = {
    "standard": "imagen-4.0-generate-001",
    "ultra": "imagen-4.0-ultra-generate-001",
    "fast": "imagen-4.0-fast-generate-001",
}
DEFAULT_GEMINI_ALIAS = "pro"
DEFAULT_IMAGEN_ALIAS = "standard"

ASPECT_RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9"]
IMAGE_SIZES = ["1K", "2K", "4K"]  # 4K is gemini-only; imagen tops out at 2K.

DEFAULT_OUTPUT_DIR = Path("art/gen")

# A "config factory" turns aspect/size knobs into the backend-specific config object.
# It is injected so tests can exercise the response-handling loop without importing
# google-genai. The production factories live below and are import-guarded.
ConfigFactory = Callable[..., Any]


# ── Pure helpers (no network, fully unit-tested) ───────────────────────────
def require_api_key(env: Mapping[str, str] | None = None) -> str:
    """Return a non-empty GOOGLE_API_KEY, or raise with a clear message.

    The API-key path is the *only* supported auth for this skill — no Vertex AI,
    no application-default credentials. A blank/whitespace value is treated as unset.
    """
    environ: Mapping[str, str] = os.environ if env is None else env
    key = environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise RuntimeError(
            f"{API_KEY_ENV} is not set (or is empty). Export a valid Google GenAI API key, "
            f"e.g.  export {API_KEY_ENV}='...'"
        )
    return key


def load_prompt_file(path: Path) -> str:
    """Read a prompt from a markdown file, dropping comment lines.

    Lines whose first non-space character starts a markdown heading (``#``) or an HTML
    comment (``<!--``) are structural notes, not prompt content, and are stripped. This
    lets a prompt file carry a documented header of intent above the curated prompt while
    sending only the prompt body to the model — maximising signal per token.
    """
    raw = path.read_text(encoding="utf-8")
    kept = [ln for ln in raw.splitlines() if not ln.strip().startswith(("#", "<!--"))]
    prompt = "\n".join(kept).strip()
    if not prompt:
        raise ValueError(f"Prompt file is empty after stripping comments: {path}")
    return prompt


def resolve_model(backend: str, alias: str | None) -> str:
    """Map a friendly alias to a model id, falling back to the backend default.

    An unrecognised alias is returned verbatim so a raw model id can be passed through.
    """
    table = GEMINI_MODELS if backend == "gemini" else IMAGEN_MODELS
    default = DEFAULT_GEMINI_ALIAS if backend == "gemini" else DEFAULT_IMAGEN_ALIAS
    if alias is None:
        return table[default]
    return table.get(alias, alias)


def timestamp_now() -> str:
    """Filesystem-sortable timestamp (local time), e.g. ``20260601_143501``."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_metadata(
    *,
    prompt: str,
    model: str,
    backend: str,
    timestamp: str,
    index: int,
    dimensions: str,
    aspect: str | None = None,
    requested_size: str | None = None,
    prompt_file: Path | None = None,
    ref_images: Sequence[Path] | None = None,
) -> dict[str, Any]:
    """Build the JSON sidecar payload that pairs an image with how it was generated."""
    meta: dict[str, Any] = {
        "prompt": prompt,
        "model": model,
        "backend": backend,
        "timestamp": timestamp,
        "index": index,
        "dimensions": dimensions,
        "aspect": aspect,
        "requested_size": requested_size,
    }
    if prompt_file is not None:
        meta["prompt_file"] = str(prompt_file)
    if ref_images:
        meta["ref_images"] = [str(p) for p in ref_images]
    return meta


def save_image(
    image: Image.Image,
    out_dir: Path,
    *,
    prompt: str,
    model: str,
    backend: str,
    timestamp: str,
    index: int,
    aspect: str | None = None,
    requested_size: str | None = None,
    prompt_file: Path | None = None,
    ref_images: Sequence[Path] | None = None,
) -> Path:
    """Write ``art_<ts>_<index>.png`` plus its ``.json`` sidecar; return the image path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"art_{timestamp}_{index}"
    img_path = out_dir / f"{stem}.png"
    meta_path = out_dir / f"{stem}.json"

    image.save(img_path)
    meta = build_metadata(
        prompt=prompt,
        model=model,
        backend=backend,
        timestamp=timestamp,
        index=index,
        dimensions=f"{image.width}x{image.height}",
        aspect=aspect,
        requested_size=requested_size,
        prompt_file=prompt_file,
        ref_images=ref_images,
    )
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("Saved %s (%dx%d)", img_path, image.width, image.height)
    return img_path


def read_history(out_dir: Path) -> list[dict[str, Any]]:
    """Load all sidecars in ``out_dir`` oldest-to-newest for prompt curation.

    Timestamped filenames sort chronologically, so the returned list shows how the
    exploration evolved. Each entry is annotated with ``_sidecar`` and ``_image`` names.

    Only *generation* sidecars (those carrying a ``prompt``) are returned, so the command
    stays useful when the directory is shared with ``art-edit`` outputs (whose sidecars
    record edit settings, not prompts).
    """
    items: list[dict[str, Any]] = []
    for jf in sorted(out_dir.glob("*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Skipping unreadable sidecar: %s", jf)
            continue
        if not isinstance(data, dict) or "prompt" not in data:
            continue
        data["_sidecar"] = jf.name
        data["_image"] = jf.with_suffix(".png").name
        items.append(data)
    return items


def format_history(items: Sequence[Mapping[str, Any]]) -> str:
    """Render history entries as a human/agent-readable curation digest."""
    if not items:
        return "No prior generations found."
    blocks: list[str] = []
    for i, it in enumerate(items):
        prompt = str(it.get("prompt", "")).replace("\n", " ")
        preview = prompt if len(prompt) <= 280 else prompt[:277] + "..."
        blocks.append(
            f"[{i}] {it.get('_image', '?')}  ({it.get('model', '?')}, {it.get('aspect', '?')})\n    {preview}"
        )
    return "\n".join(blocks)


# ── Backend boundary (import-guarded; covered by the GOOGLE_API_KEY integration test) ──
def make_client(api_key: str) -> Any:  # pragma: no cover - requires google-genai + network
    """Construct a GenAI client using the API-key path (no Vertex AI)."""
    from google import genai

    return genai.Client(api_key=api_key)


def _default_gemini_config(aspect: str | None, size: str | None) -> Any:  # pragma: no cover - requires google-genai
    from google.genai import types

    cfg = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
    image_kwargs: dict[str, str] = {}
    if aspect:
        image_kwargs["aspect_ratio"] = aspect
    if size:
        image_kwargs["image_size"] = size
    if image_kwargs:
        cfg.image_config = types.ImageConfig(**image_kwargs)
    return cfg


def _default_imagen_config(count: int, aspect: str | None, size: str | None) -> Any:  # pragma: no cover - google-genai
    from google.genai import types

    kwargs: dict[str, Any] = {"number_of_images": count}
    if aspect:
        kwargs["aspect_ratio"] = aspect
    if size in ("1K", "2K"):  # imagen rejects 4K
        kwargs["image_size"] = size
    return types.GenerateImagesConfig(**kwargs)


# ── Generation (client injected → response handling is unit-tested with fakes) ─────────
def gemini_generate(
    client: Any,
    prompt: str,
    model: str,
    out_dir: Path,
    *,
    aspect: str | None = None,
    size: str | None = None,
    ref_images: Sequence[Path] | None = None,
    timestamp: str | None = None,
    prompt_file: Path | None = None,
    config_factory: ConfigFactory = _default_gemini_config,
) -> list[Path]:
    """Generate image(s) with a gemini image model (single turn) and save them."""
    ts = timestamp or timestamp_now()
    contents: list[Any] = [prompt]
    for p in ref_images or []:
        contents.append(Image.open(p))

    response = client.models.generate_content(model=model, contents=contents, config=config_factory(aspect, size))

    saved: list[Path] = []
    idx = 0
    for part in response.parts:
        if getattr(part, "text", None) is not None:
            log.info("model: %s", part.text)
        elif getattr(part, "inline_data", None) is not None:
            img = Image.open(BytesIO(part.inline_data.data))
            saved.append(
                save_image(
                    img,
                    out_dir,
                    prompt=prompt,
                    model=model,
                    backend="gemini",
                    timestamp=ts,
                    index=idx,
                    aspect=aspect,
                    requested_size=size,
                    prompt_file=prompt_file,
                    ref_images=ref_images,
                )
            )
            idx += 1
    return saved


def imagen_generate(
    client: Any,
    prompt: str,
    model: str,
    out_dir: Path,
    *,
    count: int = 1,
    aspect: str | None = None,
    size: str | None = None,
    timestamp: str | None = None,
    prompt_file: Path | None = None,
    config_factory: ConfigFactory = _default_imagen_config,
) -> list[Path]:
    """Generate ``count`` variant(s) with an Imagen 4 model and save them."""
    ts = timestamp or timestamp_now()
    response = client.models.generate_images(model=model, prompt=prompt, config=config_factory(count, aspect, size))

    saved: list[Path] = []
    for idx, generated in enumerate(response.generated_images):
        img = Image.open(BytesIO(generated.image.image_bytes))
        saved.append(
            save_image(
                img,
                out_dir,
                prompt=prompt,
                model=model,
                backend="imagen",
                timestamp=ts,
                index=idx,
                aspect=aspect,
                requested_size=size,
                prompt_file=prompt_file,
            )
        )
    return saved


def resolve_prompts(
    inline_prompt: str | None,
    prompt_files: Sequence[Path],
) -> list[tuple[str, Path | None]]:
    """Resolve the (prompt_text, source_file) pairs to generate this run.

    An inline ``--prompt`` wins and produces a single unsourced pair. Otherwise each
    ``--prompt-file`` becomes its own pair — this is the fan-out seam.
    """
    if inline_prompt:
        return [(inline_prompt, None)]
    pairs: list[tuple[str, Path | None]] = []
    for pf in prompt_files:
        pairs.append((load_prompt_file(pf), pf))
    if not pairs:
        raise ValueError("No prompt provided. Pass --prompt or one or more --prompt-file.")
    return pairs


# ── CLI ────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="art_gen.py",
        description="Generate images from curated prompt files via Google GenAI (API-key auth).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate image(s) from a prompt or prompt file(s)")
    gen.add_argument("--prompt", default=None, help="Inline prompt text (wins over --prompt-file)")
    gen.add_argument(
        "--prompt-file",
        action="append",
        default=[],
        type=Path,
        help="Prompt markdown file; repeatable to fan out variants in one run",
    )
    gen.add_argument(
        "--backend", choices=["gemini", "imagen"], default="gemini", help="Generation backend (default: gemini)"
    )
    gen.add_argument("--model", default=None, help="Model alias (flash/pro, standard/ultra/fast) or raw model id")
    gen.add_argument("--aspect", default="1:1", choices=ASPECT_RATIOS, help="Aspect ratio (default: 1:1)")
    gen.add_argument("--size", default=None, choices=IMAGE_SIZES, help="Resolution (1K/2K/4K; 4K is gemini-only)")
    gen.add_argument("--count", type=int, default=1, help="Variants per prompt (imagen only; default: 1)")
    gen.add_argument("--ref", action="append", default=[], type=Path, help="Reference image (repeatable; gemini only)")
    gen.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Output dir (default: {DEFAULT_OUTPUT_DIR})"
    )

    hist = sub.add_parser("history", help="Print prior prompts/metadata to curate the next prompt")
    hist.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory of generated images/sidecars")

    for q in (gen, hist):
        q.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
        q.add_argument("-q", "--quiet", action="store_true", help="Errors only")
    return p


def main(
    args: argparse.Namespace,
    client: Any | None = None,
    *,
    gemini_config_factory: ConfigFactory = _default_gemini_config,
    imagen_config_factory: ConfigFactory = _default_imagen_config,
) -> int:
    """Dispatch a parsed command.

    ``client`` and the config factories are injected by tests so the full generate
    dispatch is exercised offline; production leaves them defaulted (live path).
    """
    if args.command == "history":
        sys.stdout.write(format_history(read_history(args.out_dir)) + "\n")
        return 0

    # command == "generate"
    pairs = resolve_prompts(args.prompt, args.prompt_file)
    if client is None:
        client = make_client(require_api_key())  # pragma: no cover - live path

    for prompt, prompt_file in pairs:
        model = resolve_model(args.backend, args.model)
        log.info("Generating (%s / %s) from %s", args.backend, model, prompt_file or "inline prompt")
        if args.backend == "gemini":
            saved = gemini_generate(
                client,
                prompt,
                model,
                args.out_dir,
                aspect=args.aspect,
                size=args.size,
                ref_images=args.ref or None,
                prompt_file=prompt_file,
                config_factory=gemini_config_factory,
            )
        else:
            saved = imagen_generate(
                client,
                prompt,
                model,
                args.out_dir,
                count=args.count,
                aspect=args.aspect,
                size=args.size,
                prompt_file=prompt_file,
                config_factory=imagen_config_factory,
            )
        for path in saved:
            sys.stdout.write(f"  saved: {path}\n")
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
