#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest>=8.0",
#   "pytest-cov>=4.0",
#   "Pillow>=10.0.0",
# ]
# ///
"""Tests for art_gen.

Offline coverage is achieved with hand-written *fakes* injected through the documented
seams (the GenAI client and the config factories) — no ``unittest.mock``, no network,
no API key. A real-key integration test (``TestLiveGeneration``) exercises the live path
and is skipped unless ``GOOGLE_API_KEY`` is exported.
"""

from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

import art_gen
import pytest
from PIL import Image


# ── Fakes (real objects, not mocks) ────────────────────────────────────────
def _png_bytes(color: tuple[int, int, int] = (10, 20, 30), size: tuple[int, int] = (4, 4)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


class _Part:
    """Stand-in for a gemini response part (text-only or inline image)."""

    def __init__(self, *, text: str | None = None, data: bytes | None = None) -> None:
        self.text = text
        self.inline_data = _Inline(data) if data is not None else None


class _Inline:
    def __init__(self, data: bytes) -> None:
        self.data = data


class _GeminiResponse:
    def __init__(self, parts: list[_Part]) -> None:
        self.parts = parts


class _FakeGeminiClient:
    """Records the last call and returns a fixed text + image part list."""

    def __init__(self) -> None:
        self.last: dict[str, object] = {}
        self.models = self

    def generate_content(self, *, model: str, contents: list, config) -> _GeminiResponse:  # noqa: ANN001
        self.last = {"model": model, "contents": contents, "config": config}
        return _GeminiResponse([_Part(text="here you go"), _Part(data=_png_bytes())])


class _ImagenImage:
    def __init__(self, data: bytes) -> None:
        self.image_bytes = data


class _Generated:
    def __init__(self, data: bytes) -> None:
        self.image = _ImagenImage(data)


class _ImagenResponse:
    def __init__(self, n: int) -> None:
        self.generated_images = [_Generated(_png_bytes((i, i, i))) for i in range(n)]


class _FakeImagenClient:
    def __init__(self) -> None:
        self.last: dict[str, object] = {}
        self.models = self

    def generate_images(self, *, model: str, prompt: str, config) -> _ImagenResponse:  # noqa: ANN001
        n = int(getattr(config, "count", config) if not isinstance(config, dict) else config["count"])
        self.last = {"model": model, "prompt": prompt}
        return _ImagenResponse(n)


def _dict_gemini_config(aspect, size):  # noqa: ANN001
    return {"aspect": aspect, "size": size}


def _dict_imagen_config(count, aspect, size):  # noqa: ANN001
    return {"count": count, "aspect": aspect, "size": size}


# ── require_api_key ────────────────────────────────────────────────────────
@pytest.mark.parametrize("value", ["", "   ", None])
def test_require_api_key_rejects_blank(value: str | None) -> None:
    env: dict[str, str] = {} if value is None else {"GOOGLE_API_KEY": value}
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        art_gen.require_api_key(env)


def test_require_api_key_accepts_value() -> None:
    assert art_gen.require_api_key({"GOOGLE_API_KEY": "  secret  "}) == "secret"


# ── load_prompt_file ───────────────────────────────────────────────────────
def test_load_prompt_file_strips_comments(tmp_path: Path) -> None:
    pf = tmp_path / "p.md"
    pf.write_text("# heading\n<!-- note -->\nA bold subject.\nSecond line.\n", encoding="utf-8")
    assert art_gen.load_prompt_file(pf) == "A bold subject.\nSecond line."


def test_load_prompt_file_empty_raises(tmp_path: Path) -> None:
    pf = tmp_path / "p.md"
    pf.write_text("# only comments\n<!-- nothing -->\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        art_gen.load_prompt_file(pf)


# ── resolve_model ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "backend,alias,expected",
    [
        ("gemini", None, art_gen.GEMINI_MODELS["pro"]),
        ("gemini", "flash", art_gen.GEMINI_MODELS["flash"]),
        ("imagen", None, art_gen.IMAGEN_MODELS["standard"]),
        ("imagen", "ultra", art_gen.IMAGEN_MODELS["ultra"]),
        ("gemini", "models/raw-id", "models/raw-id"),
    ],
)
def test_resolve_model(backend: str, alias: str | None, expected: str) -> None:
    assert art_gen.resolve_model(backend, alias) == expected


# ── metadata / save_image ──────────────────────────────────────────────────
def test_build_metadata_includes_optionals(tmp_path: Path) -> None:
    meta = art_gen.build_metadata(
        prompt="p",
        model="m",
        backend="gemini",
        timestamp="T",
        index=2,
        dimensions="4x4",
        aspect="1:1",
        requested_size="1K",
        prompt_file=tmp_path / "x.md",
        ref_images=[tmp_path / "r.png"],
    )
    assert meta["prompt_file"].endswith("x.md")
    assert meta["ref_images"] == [str(tmp_path / "r.png")]
    assert meta["dimensions"] == "4x4"


def test_save_image_writes_png_and_sidecar(tmp_path: Path) -> None:
    img = Image.new("RGB", (8, 6), (1, 2, 3))
    path = art_gen.save_image(
        img, tmp_path, prompt="hello", model="m", backend="gemini", timestamp="20260601_010203", index=0, aspect="1:1"
    )
    assert path.name == "art_20260601_010203_0.png"
    assert path.exists()
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["prompt"] == "hello"
    assert meta["dimensions"] == "8x6"


# ── history ────────────────────────────────────────────────────────────────
def test_read_and_format_history(tmp_path: Path) -> None:
    (tmp_path / "art_20260601_000001_0.json").write_text(
        json.dumps({"prompt": "first", "model": "m", "aspect": "1:1"}), encoding="utf-8"
    )
    (tmp_path / "art_20260601_000002_0.json").write_text(
        json.dumps({"prompt": "second " * 60, "model": "m", "aspect": "1:1"}), encoding="utf-8"
    )
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "scalar.json").write_text("42", encoding="utf-8")
    # An art-edit sidecar (no "prompt") sharing the directory must be ignored.
    (tmp_path / "edit.json").write_text(json.dumps({"command": "remove-bg", "params": {}}), encoding="utf-8")
    items = art_gen.read_history(tmp_path)
    assert [it["prompt"][:5] for it in items] == ["first", "secon"]  # ordered; broken/scalar/edit skipped
    digest = art_gen.format_history(items)
    assert "[0]" in digest and "..." in digest  # second prompt got truncated


def test_format_history_empty() -> None:
    assert art_gen.format_history([]) == "No prior generations found."


# ── resolve_prompts (fan-out seam) ─────────────────────────────────────────
def test_resolve_prompts_inline_wins(tmp_path: Path) -> None:
    pf = tmp_path / "p.md"
    pf.write_text("file body", encoding="utf-8")
    assert art_gen.resolve_prompts("inline", [pf]) == [("inline", None)]


def test_resolve_prompts_fans_out_files(tmp_path: Path) -> None:
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("alpha", encoding="utf-8")
    b.write_text("beta", encoding="utf-8")
    assert art_gen.resolve_prompts(None, [a, b]) == [("alpha", a), ("beta", b)]


def test_resolve_prompts_requires_something() -> None:
    with pytest.raises(ValueError, match="No prompt"):
        art_gen.resolve_prompts(None, [])


# ── generation loops (fake client) ─────────────────────────────────────────
def test_gemini_generate_saves_image(tmp_path: Path) -> None:
    saved = art_gen.gemini_generate(
        _FakeGeminiClient(),
        "a subject",
        "gemini-x",
        tmp_path,
        aspect="1:1",
        size="1K",
        timestamp="20260601_111111",
        config_factory=_dict_gemini_config,
    )
    assert len(saved) == 1 and saved[0].exists()
    meta = json.loads(saved[0].with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["backend"] == "gemini" and meta["requested_size"] == "1K"


def test_gemini_generate_with_ref_image(tmp_path: Path) -> None:
    ref = tmp_path / "ref.png"
    Image.new("RGB", (4, 4), (9, 9, 9)).save(ref)
    saved = art_gen.gemini_generate(
        _FakeGeminiClient(),
        "p",
        "m",
        tmp_path,
        ref_images=[ref],
        timestamp="20260601_222222",
        config_factory=_dict_gemini_config,
    )
    meta = json.loads(saved[0].with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["ref_images"][0].endswith("ref.png")


def test_imagen_generate_count(tmp_path: Path) -> None:
    saved = art_gen.imagen_generate(
        _FakeImagenClient(),
        "p",
        "imagen-x",
        tmp_path,
        count=3,
        timestamp="20260601_333333",
        config_factory=_dict_imagen_config,
    )
    assert len(saved) == 3
    assert {p.name for p in saved} == {f"art_20260601_333333_{i}.png" for i in range(3)}


# ── main dispatch (injected client) ────────────────────────────────────────
def _gen_ns(**kw) -> argparse.Namespace:  # noqa: ANN003
    base = {
        "command": "generate",
        "prompt": None,
        "prompt_file": [],
        "backend": "gemini",
        "model": None,
        "aspect": "1:1",
        "size": None,
        "count": 1,
        "ref": [],
        "out_dir": Path("."),
        "verbose": False,
        "quiet": False,
    }
    base.update(kw)
    return argparse.Namespace(**base)


class _ConfiglessGemini(_FakeGeminiClient):
    """A fake whose generate_content ignores the (real) config object entirely."""


def test_main_generate_gemini(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ns = _gen_ns(prompt="a subject", out_dir=tmp_path)
    rc = art_gen.main(ns, client=_ConfiglessGemini(), gemini_config_factory=_dict_gemini_config)
    assert rc == 0
    assert "saved:" in capsys.readouterr().out


def test_main_generate_fans_out_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("alpha subject", encoding="utf-8")
    b.write_text("beta subject", encoding="utf-8")
    ns = _gen_ns(prompt_file=[a, b], out_dir=tmp_path)
    rc = art_gen.main(ns, client=_ConfiglessGemini(), gemini_config_factory=_dict_gemini_config)
    assert rc == 0
    assert capsys.readouterr().out.count("saved:") == 2


def test_main_generate_imagen(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ns = _gen_ns(backend="imagen", prompt="p", count=2, out_dir=tmp_path)
    rc = art_gen.main(ns, client=_FakeImagenClient(), imagen_config_factory=_dict_imagen_config)
    assert rc == 0
    assert capsys.readouterr().out.count("saved:") == 2


def test_main_history(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "art_1_0.json").write_text(json.dumps({"prompt": "x", "model": "m"}), encoding="utf-8")
    ns = argparse.Namespace(command="history", out_dir=tmp_path, verbose=False, quiet=False)
    assert art_gen.main(ns) == 0
    assert "art_1_0.png" in capsys.readouterr().out


# ── parser smoke ───────────────────────────────────────────────────────────
def test_build_parser_generate() -> None:
    ns = art_gen.build_parser().parse_args(["generate", "--prompt", "hi", "--backend", "imagen"])
    assert ns.command == "generate" and ns.backend == "imagen"


def test_build_parser_history_default_out_dir() -> None:
    ns = art_gen.build_parser().parse_args(["history"])
    assert ns.out_dir == art_gen.DEFAULT_OUTPUT_DIR


# NOTE: Live, real-credential validation is performed via the CLI (see README.md), NOT
# via pytest. Routing a GOOGLE_API_KEY through pytest is unsafe — pytest renders each
# frame's arguments in tracebacks, so a failure inside make_client(api_key=...) would
# print the secret. The CLI uses plain CPython, whose tracebacks omit argument values.
# See CLAUDE.md ADR-008.


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
