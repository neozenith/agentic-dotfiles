#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for serve.py — real server on port 0, real HTTP requests."""

from __future__ import annotations

import sys
import threading
import urllib.error
import urllib.request
from argparse import Namespace
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
import serve


@pytest.fixture
def site(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text("<h1>hello richdocs</h1>", encoding="utf-8")
    (tmp_path / "app.mjs").write_text("export const x = 1;", encoding="utf-8")
    (tmp_path / "data.json").write_text('{"ok": true}', encoding="utf-8")
    return tmp_path


def _start(directory: Path) -> tuple[ThreadingHTTPServer, str]:
    httpd = serve.serve(directory, 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def test_serve_sends_no_store_and_mimetypes(site: Path) -> None:
    httpd, base = _start(site)
    try:
        for path, ctype, expected in [
            ("/index.html", "text/html", b"hello richdocs"),
            ("/app.mjs", "text/javascript", b"export const"),
            ("/data.json", "application/json", b'"ok"'),
        ]:
            with urllib.request.urlopen(f"{base}{path}") as resp:
                assert resp.status == 200
                assert resp.headers["Cache-Control"] == "no-store"
                assert resp.headers["Content-Type"].startswith(ctype)
                assert expected in resp.read()
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_serve_404_also_no_store(site: Path) -> None:
    httpd, base = _start(site)
    try:
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(f"{base}/missing.html")
        assert excinfo.value.code == 404
        assert excinfo.value.headers["Cache-Control"] == "no-store"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_main_missing_dir_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = Namespace(dir=str(tmp_path / "nope"), port=0, open=False)
    with pytest.raises(SystemExit) as excinfo:
        serve.main(args)
    assert excinfo.value.code == 1
    assert "does not exist" in capsys.readouterr().err


def test_main_busy_port_exits_1(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    httpd, _ = _start(site)
    try:
        port = httpd.server_address[1]
        args = Namespace(dir=str(site), port=port, open=False)
        with pytest.raises(SystemExit) as excinfo:
            serve.main(args, run=lambda h: None)
        assert excinfo.value.code == 1
        assert "already in use" in capsys.readouterr().err
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_main_prints_url_and_opens(
    site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    opened: list[str] = []
    args = Namespace(dir=str(site), port=0, open=True)
    serve.main(args, run=lambda h: None, opener=opened.append)
    out = capsys.readouterr().out
    assert "http://127.0.0.1:0/" in out
    assert opened == ["http://127.0.0.1:0/"]


def test_main_keyboard_interrupt_exits_cleanly(
    site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def raise_interrupt(_: ThreadingHTTPServer) -> None:
        raise KeyboardInterrupt

    args = Namespace(dir=str(site), port=0, open=False)
    serve.main(args, run=raise_interrupt)  # must not raise
    assert "Stopped." in capsys.readouterr().out


def test_build_parser_defaults() -> None:
    args = serve.build_parser().parse_args([])
    assert args.dir == str(serve.DEFAULT_DIR)
    assert args.port == serve.DEFAULT_PORT
    assert args.open is False


def test_build_parser_custom() -> None:
    args = serve.build_parser().parse_args(["some/dir", "--port", "9000", "--open"])
    assert args.dir == "some/dir"
    assert args.port == 9000
    assert args.open is True


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
