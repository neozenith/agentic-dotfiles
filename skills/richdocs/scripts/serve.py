#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Serve a directory of richdocs HTML on localhost with caching disabled.

Multi-file richdocs output fetches its markdown + design tokens at runtime,
which file:// blocks. This server exists so those fetches work locally, and
sends ``Cache-Control: no-store`` on every response so rebuilds are always
picked up on refresh.
"""

from __future__ import annotations

import argparse
import functools
import sys
import webbrowser
from collections.abc import Callable
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────
DEFAULT_DIR = Path("tmp/richdocs")
DEFAULT_PORT = 8642
BIND_HOST = "127.0.0.1"


# ── Core ───────────────────────────────────────────────────────────────────
class NoStoreHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler that forbids caching on every response."""

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".mjs": "text/javascript",
        ".js": "text/javascript",
        ".json": "application/json",
        ".md": "text/markdown",
    }

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f"[serve] {format % args}\n")


def serve(directory: Path, port: int) -> ThreadingHTTPServer:
    """Build a ThreadingHTTPServer bound to 127.0.0.1:<port> serving <directory>.

    Raises OSError if the port is busy; the caller owns serve_forever/shutdown.
    """
    handler = functools.partial(NoStoreHandler, directory=str(directory))
    return ThreadingHTTPServer((BIND_HOST, port), handler)


# ── CLI ────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="serve.py",
        description="Serve a richdocs output directory on localhost with Cache-Control: no-store.",
    )
    parser.add_argument(
        "dir",
        nargs="?",
        default=str(DEFAULT_DIR),
        help=f"Directory to serve (default: {DEFAULT_DIR})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to bind (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--open", action="store_true", help="Open the served URL in the default browser"
    )
    return parser


def main(
    args: argparse.Namespace,
    run: Callable[[ThreadingHTTPServer], None] | None = None,
    opener: Callable[[str], object] = webbrowser.open,
) -> None:
    """Validate args, start the server, and block until interrupted.

    `run` and `opener` are injectable for tests; the defaults are the real
    blocking serve loop and the real browser opener.
    """
    directory = Path(args.dir)
    if not directory.is_dir():
        print(f"error: directory does not exist: {directory}", file=sys.stderr)
        raise SystemExit(1)

    try:
        httpd = serve(directory, args.port)
    except OSError as err:
        print(
            f"error: cannot bind {BIND_HOST}:{args.port} ({err}). Is the port already in use?",
            file=sys.stderr,
        )
        raise SystemExit(1) from err

    url = f"http://{BIND_HOST}:{args.port}/"
    print(
        f"Serving {directory.resolve()} at {url} (Cache-Control: no-store; Ctrl-C to stop)"
    )
    if args.open:
        opener(url)

    if run is None:
        run = ThreadingHTTPServer.serve_forever  # pragma: no cover
    try:
        run(httpd)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":  # pragma: no cover
    main(build_parser().parse_args())
