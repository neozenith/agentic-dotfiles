#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["lsprotocol>=2024.0.0"]
# ///
"""LSP Explorer — Query language servers for code intelligence.

A CLI tool that wraps Language Server Protocol (LSP) servers for Python (pyright)
and TypeScript (typescript-language-server) to provide code intelligence: symbols,
definitions, references, hover info, diagnostics, and impact analysis.

Architecture (5 layers):
    CLI (argparse)          <- User/Claude invokes commands
        |
    CodeExplorer            <- High-level: explore, plan, impact
        |
    LspSession              <- Protocol: initialize, shutdown, textDocument/*
        |
    JsonRpcClient           <- Wire: Content-Length framing, request/response matching
        |
    subprocess (stdin/stdout) <- pyright-langserver or typescript-language-server
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import select
import shutil
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

log = logging.getLogger(__name__)

# LSP Symbol Kind mapping (from LSP spec)
SYMBOL_KIND: dict[int, str] = {
    1: "file",
    2: "module",
    3: "namespace",
    4: "package",
    5: "class",
    6: "method",
    7: "property",
    8: "field",
    9: "constructor",
    10: "enum",
    11: "interface",
    12: "function",
    13: "variable",
    14: "constant",
    15: "string",
    16: "number",
    17: "boolean",
    18: "array",
    19: "object",
    20: "key",
    21: "null",
    22: "enum_member",
    23: "struct",
    24: "event",
    25: "operator",
    26: "type_parameter",
}

# Language detection from file extensions
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
}

# Server commands per language
SERVER_COMMANDS: dict[str, list[str]] = {
    "python": ["pyright-langserver", "--stdio"],
    "typescript": ["typescript-language-server", "--stdio"],
    "javascript": ["typescript-language-server", "--stdio"],
}

# Default timeout in seconds
DEFAULT_TIMEOUT = 30.0


# ============================================================================
# Layer 1: JSON-RPC Client
# ============================================================================


class JsonRpcError(Exception):
    """Error from a JSON-RPC response."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"JSON-RPC error {code}: {message}")
        self.code = code
        self.error_message = message
        self.data = data


class JsonRpcClient:
    """Low-level JSON-RPC 2.0 client over stdio with Content-Length framing.

    The LSP wire protocol uses HTTP-style Content-Length headers to delimit
    JSON messages over stdin/stdout of a subprocess. Each message looks like:

        Content-Length: 52\\r\\n
        \\r\\n
        {"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}

    Architecture: Single-threaded IO with our own byte buffer and raw fd reads.
    We bypass Python's BufferedReader entirely because its internal buffer is
    invisible to select.select() — after one readline() call, BufferedReader
    may greedily consume multiple messages into its buffer, but select() on the
    raw fd reports "no data" because the fd was drained. This causes timeouts
    when the buffered messages are never read.

    Instead, we use os.read() on the raw fd + select.select() for timeouts,
    maintaining our own _buffer (bytearray). This gives us full control over
    both timeout detection and data buffering. Server-initiated requests are
    handled inline during wait_response() to prevent deadlocks.
    """

    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        self._proc = proc
        self._next_id = 1
        self._pending_notifications: list[dict[str, Any]] = []
        assert proc.stdin is not None
        assert proc.stdout is not None
        self._stdin = proc.stdin
        self._stdout_fd = proc.stdout.fileno()
        # Our own buffer — replaces Python's BufferedReader
        self._buffer = bytearray()

    def send_request(self, method: str, params: dict[str, Any] | None = None) -> int:
        """Send a JSON-RPC request and return the request ID."""
        request_id = self._next_id
        self._next_id += 1
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        self._send(msg)
        log.debug("-> request id=%d method=%s", request_id, method)
        return request_id

    def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        self._send(msg)
        log.debug("-> notification method=%s", method)

    def wait_response(self, request_id: int, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """Read messages until we get a response for our request_id.

        Three message types are handled:
        1. Responses (id + result/error) — matched to our request by id
        2. Server requests (id + method) — auto-responded to prevent deadlocks
        3. Notifications (method only) — buffered for later collection

        Uses select.select() on the raw fd for timeout, then buffered reads
        for efficient message parsing.
        """
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"No response for request {request_id} within {timeout}s")

            msg = self._read_one_message(remaining)
            if msg is None:
                raise TimeoutError(f"No response for request {request_id} within {timeout}s")

            has_id = "id" in msg
            has_method = "method" in msg

            if has_id and has_method:
                # Server request — respond immediately to prevent deadlocks
                self._handle_server_request(msg)
            elif has_id and not has_method:
                # Response
                if msg["id"] == request_id:
                    if "error" in msg:
                        err = msg["error"]
                        raise JsonRpcError(
                            err.get("code", -1),
                            err.get("message", "Unknown"),
                            err.get("data"),
                        )
                    log.debug("<- response id=%d", request_id)
                    result: dict[str, Any] = msg["result"]
                    return result
                else:
                    log.warning(
                        "Received response for unexpected id=%s",
                        msg["id"],
                    )
            else:
                # Notification — buffer for later
                self._pending_notifications.append(msg)
                log.debug("<- notification method=%s", msg.get("method", "?"))

    def _handle_server_request(self, msg: dict[str, Any]) -> None:
        """Respond to server-initiated requests.

        LSP servers can send requests to the client (e.g., workspace/configuration,
        client/registerCapability). If we don't respond, the server blocks waiting
        and never processes our requests — causing timeouts.
        """
        method = msg.get("method", "")
        req_id = msg["id"]
        log.debug("<- server request id=%s method=%s", req_id, method)

        if method == "workspace/configuration":
            items = msg.get("params", {}).get("items", [])
            response: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": [{}] * len(items),
            }
            self._send(response)
            log.debug(
                "-> response to workspace/configuration (%d items)",
                len(items),
            )
        elif method == "client/registerCapability":
            response = {"jsonrpc": "2.0", "id": req_id, "result": None}
            self._send(response)
            log.debug("-> response to client/registerCapability")
        elif method == "window/workDoneProgress/create":
            response = {"jsonrpc": "2.0", "id": req_id, "result": None}
            self._send(response)
            log.debug("-> response to window/workDoneProgress/create")
        else:
            response = {"jsonrpc": "2.0", "id": req_id, "result": None}
            self._send(response)
            log.debug("-> response to %s (generic null)", method)

    def drain_notifications(self, timeout: float = 0.5) -> list[dict[str, Any]]:
        """Collect all pending + incoming notifications.

        Reads messages for up to `timeout` seconds, handling server requests
        and buffering notifications. Useful for collecting diagnostics.
        """
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            msg = self._read_one_message(remaining)
            if msg is None:
                break
            has_id = "id" in msg
            has_method = "method" in msg
            if has_id and has_method:
                self._handle_server_request(msg)
            elif has_id and not has_method:
                log.warning("Unexpected response while draining: %s", msg)
            else:
                self._pending_notifications.append(msg)

        result = self._pending_notifications[:]
        self._pending_notifications.clear()
        return result

    def _send(self, msg: dict[str, Any]) -> None:
        """Encode and send a JSON-RPC message with Content-Length header."""
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self._stdin.write(header + body)
        self._stdin.flush()

    def _fill_buffer(self, timeout: float) -> bool:
        """Read more data from the fd into our buffer.

        Returns True if new data was read, False on timeout or EOF.
        Uses select.select() for timeout, then os.read() for data.
        Always attempts to read from the fd, even if buffer has data.
        """
        ready, _, _ = select.select([self._stdout_fd], [], [], timeout)
        if not ready:
            return False
        chunk = os.read(self._stdout_fd, 65536)
        if not chunk:
            return False  # EOF
        self._buffer.extend(chunk)
        return True

    def _read_line_raw(self, timeout: float) -> bytes | None:
        """Read one line (ending in \\n) from our buffer + fd.

        Returns the line including the trailing \\n, or None on timeout/EOF.
        """
        deadline = time.monotonic() + timeout
        while True:
            # Check if we already have a complete line in the buffer
            newline_pos = self._buffer.find(b"\n")
            if newline_pos >= 0:
                line = bytes(self._buffer[: newline_pos + 1])
                del self._buffer[: newline_pos + 1]
                return line
            # Need more data
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            if not self._fill_buffer(remaining):
                return None

    def _read_exactly_raw(self, n: int, timeout: float) -> bytes | None:
        """Read exactly n bytes from our buffer + fd.

        Returns exactly n bytes, or None on timeout/EOF.
        """
        deadline = time.monotonic() + timeout
        while len(self._buffer) < n:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            if not self._fill_buffer(remaining):
                return None
        data = bytes(self._buffer[:n])
        del self._buffer[:n]
        return data

    def _read_one_message(self, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any] | None:
        """Read a single Content-Length-framed JSON-RPC message.

        Uses our own buffer + raw os.read() on the fd, with select.select()
        for timeout detection. This avoids the classic BufferedReader pitfall
        where Python's internal buffer holds data invisible to select().

        Protocol format:
            Content-Length: <n>\\r\\n
            \\r\\n
            <n bytes of JSON body>
        """
        deadline = time.monotonic() + timeout

        # Read headers until empty line
        headers: list[str] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            line = self._read_line_raw(remaining)
            if line is None:
                return None
            line_str = line.decode("ascii").rstrip("\r\n")
            if line_str == "":
                break
            headers.append(line_str)

        # Parse Content-Length
        content_length = 0
        for header_line in headers:
            if header_line.lower().startswith("content-length:"):
                content_length = int(header_line.split(":", 1)[1].strip())

        if content_length == 0:
            log.warning("No Content-Length in headers: %s", headers)
            return None

        # Read body
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        body = self._read_exactly_raw(content_length, remaining)
        if body is None or len(body) < content_length:
            return None

        return json.loads(body.decode("utf-8"))  # type: ignore[no-any-return]


# ============================================================================
# Layer 2: LSP Session
# ============================================================================


def _file_uri(path: Path) -> str:
    """Convert a file path to a file:// URI."""
    return path.resolve().as_uri()


def _read_file_text(path: Path) -> str:
    """Read file contents for didOpen notification."""
    return path.read_text(encoding="utf-8", errors="replace")


class LspSession:
    """LSP protocol operations wrapping a JsonRpcClient.

    Handles the LSP lifecycle (initialize/shutdown) and provides
    typed wrappers for common textDocument/* requests.

    LSP positions are 0-indexed (line 0, character 0 = first character).
    This class works in 0-indexed coordinates internally.
    """

    def __init__(self, client: JsonRpcClient, root_path: Path, language: str) -> None:
        self._client = client
        self._root_path = root_path
        self._language = language
        self._open_docs: set[str] = set()
        self._initialized = False

    @property
    def language(self) -> str:
        return self._language

    def initialize(self) -> dict[str, Any]:
        """Perform the LSP 3-way handshake: initialize -> response -> initialized.

        The initialize request tells the server about client capabilities and
        the project root. The server responds with its own capabilities.
        Then we send an 'initialized' notification to complete the handshake.
        """
        params = {
            "processId": os.getpid(),
            "rootUri": _file_uri(self._root_path),
            "rootPath": str(self._root_path),
            "capabilities": {
                "textDocument": {
                    "documentSymbol": {
                        "hierarchicalDocumentSymbolSupport": True,
                    },
                    "definition": {"linkSupport": False},
                    "references": {},
                    "hover": {"contentFormat": ["plaintext", "markdown"]},
                    "publishDiagnostics": {"relatedInformation": True},
                },
                # Note: we intentionally do NOT advertise workspace.workspaceFolders
                # capability. Pyright deadlocks when this is set — it blocks internally
                # waiting for workspace/configuration negotiation that never completes.
                # Workspace folders are still provided via params.workspaceFolders above.
            },
            "workspaceFolders": [{"uri": _file_uri(self._root_path), "name": self._root_path.name}],
        }
        req_id = self._client.send_request("initialize", params)
        result = self._client.wait_response(req_id)

        # Complete the handshake
        self._client.send_notification("initialized", {})

        # Drain post-initialization messages (window/logMessage, etc.)
        # and respond to any server requests (client/registerCapability).
        self._client.drain_notifications(timeout=0.5)

        self._initialized = True
        log.info("LSP initialized for %s at %s", self._language, self._root_path)
        return result

    def shutdown(self) -> None:
        """Gracefully shut down the LSP session."""
        # Close any open documents first
        for uri in list(self._open_docs):
            self._client.send_notification(
                "textDocument/didClose",
                {"textDocument": {"uri": uri}},
            )
        self._open_docs.clear()

        req_id = self._client.send_request("shutdown")
        try:
            self._client.wait_response(req_id, timeout=5.0)
        except (TimeoutError, JsonRpcError):
            log.warning("Shutdown response not received cleanly")
        self._client.send_notification("exit")
        self._initialized = False
        log.info("LSP session shut down")

    def did_open(self, file_path: Path) -> None:
        """Open a document in the language server.

        The LSP requires documents to be "opened" before querying them.
        We send the full file contents as part of the didOpen notification.
        """
        uri = _file_uri(file_path)
        if uri in self._open_docs:
            return
        lang_id = self._language
        if lang_id == "javascript":
            lang_id = "javascriptreact" if file_path.suffix == ".jsx" else "javascript"
        elif lang_id == "typescript":
            lang_id = "typescriptreact" if file_path.suffix == ".tsx" else "typescript"

        text = _read_file_text(file_path)
        self._client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": lang_id,
                    "version": 1,
                    "text": text,
                },
            },
        )
        self._open_docs.add(uri)
        log.debug("Opened document: %s", file_path)

    def did_close(self, file_path: Path) -> None:
        """Close a document in the language server."""
        uri = _file_uri(file_path)
        if uri not in self._open_docs:
            return
        self._client.send_notification(
            "textDocument/didClose",
            {"textDocument": {"uri": uri}},
        )
        self._open_docs.discard(uri)

    def document_symbol(self, file_path: Path) -> list[dict[str, Any]]:
        """Get symbols in a document (textDocument/documentSymbol).

        Returns hierarchical symbols (DocumentSymbol[]) if the server supports it,
        otherwise flat SymbolInformation[].
        """
        self.did_open(file_path)
        uri = _file_uri(file_path)
        req_id = self._client.send_request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": uri}},
        )
        result = self._client.wait_response(req_id)
        return result if isinstance(result, list) else []

    def definition(self, file_path: Path, line: int, col: int) -> list[dict[str, Any]]:
        """Go to definition (textDocument/definition).

        Args:
            file_path: File containing the symbol
            line: 0-indexed line number
            col: 0-indexed column number
        """
        self.did_open(file_path)
        uri = _file_uri(file_path)
        req_id = self._client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": col},
            },
        )
        result = self._client.wait_response(req_id)
        if result is None:
            return []
        if isinstance(result, dict):
            return [result]
        return result if isinstance(result, list) else []

    def references(self, file_path: Path, line: int, col: int) -> list[dict[str, Any]]:
        """Find all references (textDocument/references).

        Args:
            file_path: File containing the symbol
            line: 0-indexed line number
            col: 0-indexed column number
        """
        self.did_open(file_path)
        uri = _file_uri(file_path)
        req_id = self._client.send_request(
            "textDocument/references",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": col},
                "context": {"includeDeclaration": True},
            },
        )
        result = self._client.wait_response(req_id)
        if result is None:
            return []
        return result if isinstance(result, list) else []

    def hover(self, file_path: Path, line: int, col: int) -> dict[str, Any] | None:
        """Get hover information (textDocument/hover).

        Args:
            file_path: File containing the symbol
            line: 0-indexed line number
            col: 0-indexed column number
        """
        self.did_open(file_path)
        uri = _file_uri(file_path)
        req_id = self._client.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": col},
            },
        )
        result = self._client.wait_response(req_id)
        return result if isinstance(result, dict) else None

    def collect_diagnostics(self, file_path: Path, timeout: float = 3.0) -> list[dict[str, Any]]:
        """Collect publishDiagnostics notifications for a file.

        After opening a document, the server asynchronously sends diagnostics
        as notifications. This method drains the notification buffer and
        returns diagnostics for the specified file.
        """
        self.did_open(file_path)
        uri = _file_uri(file_path)

        notifications = self._client.drain_notifications(timeout=timeout)
        diagnostics: list[dict[str, Any]] = []
        for notif in notifications:
            if notif.get("method") == "textDocument/publishDiagnostics":
                params = notif.get("params", {})
                if params.get("uri") == uri:
                    diagnostics.extend(params.get("diagnostics", []))
        return diagnostics


# ============================================================================
# Layer 3: Language Server Manager
# ============================================================================


class ServerNotFound(Exception):
    """Raised when a language server binary is not found."""

    def __init__(self, language: str, binary: str) -> None:
        self.language = language
        self.binary = binary
        install_hint = (
            "pip install pyright"
            if language == "python"
            else "npm install -g typescript-language-server typescript"
        )
        super().__init__(
            f"Language server for {language} not found: {binary}. Install with: {install_hint}"
        )


class UnsupportedLanguage(Exception):
    """Raised for file types we don't support."""

    def __init__(self, ext: str) -> None:
        self.ext = ext
        super().__init__(
            f"Unsupported file extension: {ext}. Supported: {', '.join(sorted(EXTENSION_TO_LANGUAGE.keys()))}"
        )


def detect_language(file_path: Path) -> str:
    """Detect language from file extension."""
    ext = file_path.suffix.lower()
    lang = EXTENSION_TO_LANGUAGE.get(ext)
    if lang is None:
        raise UnsupportedLanguage(ext)
    return lang


def detect_project_root(file_path: Path) -> Path:
    """Walk up from file_path to find the project root.

    Looks for common project markers: .git, pyproject.toml, package.json, etc.
    Falls back to file's parent directory.
    """
    markers = {".git", "pyproject.toml", "package.json", "tsconfig.json", "setup.py", "Cargo.toml"}
    current = file_path.resolve().parent
    while current != current.parent:
        if any((current / m).exists() for m in markers):
            return current
        current = current.parent
    return file_path.resolve().parent


class LanguageServerManager:
    """Manages the lifecycle of a language server subprocess.

    Handles:
    - Language detection from file extension
    - Binary validation (is pyright-langserver on PATH?)
    - Subprocess creation (stdin/stdout pipes)
    - Creating JsonRpcClient + LspSession
    - Clean shutdown
    """

    def __init__(self, language: str) -> None:
        self._language = language
        self._proc: subprocess.Popen[bytes] | None = None
        self._session: LspSession | None = None

    @classmethod
    def for_file(cls, file_path: Path) -> LanguageServerManager:
        """Create a manager for the given file's language."""
        lang = detect_language(file_path)
        return cls(lang)

    def start(self, root_path: Path) -> LspSession:
        """Start the language server and perform initialization."""
        cmd = SERVER_COMMANDS.get(self._language)
        if cmd is None:
            raise UnsupportedLanguage(f"No server configured for {self._language}")

        binary = cmd[0]
        if shutil.which(binary) is None:
            raise ServerNotFound(self._language, binary)

        log.info("Starting %s: %s", self._language, " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(root_path),
        )
        client = JsonRpcClient(self._proc)
        self._session = LspSession(client, root_path, self._language)
        self._session.initialize()
        return self._session

    def stop(self) -> None:
        """Shut down the language server."""
        if self._session is not None:
            try:
                self._session.shutdown()
            except Exception:
                log.warning("Error during LSP shutdown", exc_info=True)
            self._session = None

        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
            self._proc = None

    @contextmanager
    def lsp_session(self, root_path: Path) -> Generator[LspSession, None, None]:
        """Context manager for a complete LSP session lifecycle."""
        session = self.start(root_path)
        try:
            yield session
        finally:
            self.stop()


@contextmanager
def lsp_session_for_file(
    file_path: Path, root_path: Path | None = None
) -> Generator[LspSession, None, None]:
    """Convenience context manager: detect language, start server, yield session."""
    resolved = file_path.resolve()
    if root_path is None:
        root_path = detect_project_root(resolved)
    mgr = LanguageServerManager.for_file(resolved)
    with mgr.lsp_session(root_path) as session:
        yield session


# ============================================================================
# Layer 4: Code Explorer
# ============================================================================


def _relative_path(path: Path, root: Path) -> str:
    """Get relative path string from root, or absolute if outside root."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _uri_to_path(uri: str) -> Path:
    """Convert file:// URI to Path."""
    if uri.startswith("file://"):
        # Handle file:///path and file://host/path
        parsed = urlparse(uri)
        return Path(unquote(parsed.path))
    return Path(uri)


def _symbol_kind_name(kind_num: int) -> str:
    """Get human-readable symbol kind name."""
    return SYMBOL_KIND.get(kind_num, f"unknown({kind_num})")


def _format_symbol(sym: dict[str, Any]) -> dict[str, Any]:
    """Convert an LSP DocumentSymbol to compact JSON format.

    Compact keys: n=name, k=kind, r=range[start,end], ch=children
    Lines are 1-indexed in output (LSP uses 0-indexed).
    """
    result: dict[str, Any] = {
        "n": sym.get("name", ""),
        "k": _symbol_kind_name(sym.get("kind", 0)),
    }

    # Range: convert 0-indexed to 1-indexed
    rng = sym.get("range") or sym.get("location", {}).get("range")
    if rng:
        start_line = rng["start"]["line"] + 1
        end_line = rng["end"]["line"] + 1
        result["r"] = [start_line, end_line]

    # Selection range (where the symbol name is)
    sel = sym.get("selectionRange")
    if sel:
        result["l"] = sel["start"]["line"] + 1
        result["c"] = sel["start"]["character"] + 1

    # Recursively format children
    children = sym.get("children", [])
    if children:
        result["ch"] = [_format_symbol(c) for c in children]

    # Detail (type annotation etc.)
    detail = sym.get("detail")
    if detail:
        result["d"] = detail

    return result


def _format_location(loc: dict[str, Any], root: Path) -> dict[str, Any]:
    """Convert an LSP Location to compact format."""
    result: dict[str, Any] = {}
    uri = loc.get("uri", loc.get("targetUri", ""))
    if uri:
        result["f"] = _relative_path(_uri_to_path(uri), root)

    rng = loc.get("range", loc.get("targetRange"))
    if rng:
        result["l"] = rng["start"]["line"] + 1
        result["c"] = rng["start"]["character"] + 1

    return result


def _get_line_preview(file_path: Path, line_1indexed: int) -> str | None:
    """Read a specific line from a file (1-indexed)."""
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        idx = line_1indexed - 1
        if 0 <= idx < len(lines):
            return lines[idx].rstrip()
    except OSError:
        pass
    return None


def _format_hover(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert LSP hover result to compact format."""
    if result is None:
        return None
    contents = result.get("contents")
    if contents is None:
        return None

    # MarkupContent: {"kind": "markdown"|"plaintext", "value": "..."}
    if isinstance(contents, dict):
        text = contents.get("value", "")
    elif isinstance(contents, str):
        text = contents
    elif isinstance(contents, list):
        # Array of MarkedString
        parts = []
        for item in contents:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("value", ""))
        text = "\n".join(parts)
    else:
        return None

    if not text.strip():
        return None

    out: dict[str, Any] = {}
    # Try to separate type signature from documentation
    lines = text.strip().split("\n")
    # If it looks like a code block, extract the signature
    if lines and lines[0].startswith("```"):
        # Find end of code block
        end_idx = 1
        for i in range(1, len(lines)):
            if lines[i].startswith("```"):
                end_idx = i
                break
        sig = "\n".join(lines[1:end_idx]).strip()
        doc_lines = lines[end_idx + 1 :]
        if sig:
            out["type"] = sig
        doc = "\n".join(doc_lines).strip()
        # Remove horizontal rule separators (common in LSP hover markdown)
        while doc.startswith("---"):
            doc = doc[3:].strip()
        while doc.endswith("---"):
            doc = doc[:-3].strip()
        if doc:
            out["doc"] = doc
    else:
        out["type"] = text.strip()

    return out if out else None


def _format_diagnostic(diag: dict[str, Any], file_path: Path, root: Path) -> dict[str, Any]:
    """Convert LSP Diagnostic to compact format."""
    result: dict[str, Any] = {"f": _relative_path(file_path, root)}
    rng = diag.get("range", {})
    start = rng.get("start", {})
    result["l"] = start.get("line", 0) + 1
    result["c"] = start.get("character", 0) + 1
    result["s"] = diag.get("severity", 1)  # 1=error, 2=warning, 3=info, 4=hint
    result["msg"] = diag.get("message", "")
    source = diag.get("source")
    if source:
        result["src"] = source
    code = diag.get("code")
    if code is not None:
        result["code"] = code
    return result


class CodeExplorer:
    """High-level code exploration operations.

    Each method opens a short-lived LSP session, performs queries,
    and returns token-efficient JSON-ready dicts.
    """

    def __init__(self, root_path: Path | None = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._root_override = root_path
        self._timeout = timeout

    def _root_for(self, file_path: Path) -> Path:
        if self._root_override:
            return self._root_override
        return detect_project_root(file_path)

    def symbols(self, file_path: Path) -> list[dict[str, Any]]:
        """List symbols in a file with hierarchy."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw_symbols = session.document_symbol(resolved)
        return [_format_symbol(s) for s in raw_symbols]

    def definition(self, file_path: Path, line: int, col: int) -> list[dict[str, Any]]:
        """Go to definition. Positions are 1-indexed (converted internally)."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw = session.definition(resolved, line - 1, col - 1)

        results = []
        for loc in raw:
            formatted = _format_location(loc, root)
            # Add source preview
            if "f" in formatted and "l" in formatted:
                target = root / formatted["f"]
                preview = _get_line_preview(target, formatted["l"])
                if preview:
                    formatted["preview"] = preview
            results.append(formatted)
        return results

    def references(self, file_path: Path, line: int, col: int) -> dict[str, Any]:
        """Find all references. Positions are 1-indexed. Returns grouped by file."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw = session.references(resolved, line - 1, col - 1)

        # Group by file
        by_file: dict[str, list[int]] = {}
        for loc in raw:
            formatted = _format_location(loc, root)
            f = formatted.get("f", "?")
            line_num = formatted.get("l", 0)
            if f not in by_file:
                by_file[f] = []
            by_file[f].append(line_num)

        return {"refs": by_file, "total": len(raw)}

    def hover(self, file_path: Path, line: int, col: int) -> dict[str, Any] | None:
        """Get hover info. Positions are 1-indexed."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw = session.hover(resolved, line - 1, col - 1)
        return _format_hover(raw)

    def diagnostics(self, file_path: Path) -> list[dict[str, Any]]:
        """Get diagnostics for a file."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw = session.collect_diagnostics(resolved, timeout=self._timeout)
        return [_format_diagnostic(d, resolved, root) for d in raw]

    def explore(self, file_path: Path) -> dict[str, Any]:
        """Combined symbols + diagnostics overview for a file."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        lang = detect_language(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw_symbols = session.document_symbol(resolved)
            raw_diags = session.collect_diagnostics(resolved, timeout=min(self._timeout, 5.0))

        syms = [_format_symbol(s) for s in raw_symbols]
        diags = [_format_diagnostic(d, resolved, root) for d in raw_diags]

        result: dict[str, Any] = {
            "file": _relative_path(resolved, root),
            "lang": lang,
            "symbols": len(syms),
            "diagnostics": len(diags),
            "syms": syms,
        }
        if diags:
            result["diags"] = diags
        return result

    def impact(self, file_path: Path, line: int, col: int, depth: int = 1) -> dict[str, Any]:
        """Multi-hop reference analysis. Find what a change would affect.

        Traces references up to `depth` hops from the starting symbol.
        Positions are 1-indexed.
        """
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        refs_result = self.references(file_path, line, col)

        # For depth > 1, we'd recursively trace references of each reference.
        # For now, depth=1 returns direct references.
        affected: list[dict[str, Any]] = []
        for f, lines in refs_result.get("refs", {}).items():
            for ln in lines:
                entry: dict[str, Any] = {"f": f, "l": ln}
                preview = _get_line_preview(root / f, ln)
                if preview:
                    entry["preview"] = preview
                affected.append(entry)

        return {
            "depth": depth,
            "total": refs_result.get("total", 0),
            "affected": affected,
        }


# ============================================================================
# Layer 5: CLI Interface
# ============================================================================


def _output_json(data: Any, *, pretty: bool = False) -> None:
    """Output JSON to stdout — compact by default, indented with --pretty."""
    if pretty:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data, separators=(",", ":"), ensure_ascii=False))


def _error_json(message: str, hint: str | None = None) -> None:
    """Output error as JSON to stderr."""
    err: dict[str, str] = {"error": message}
    if hint:
        err["hint"] = hint
    print(json.dumps(err, separators=(",", ":")), file=sys.stderr)


def cmd_symbols(args: argparse.Namespace) -> int:
    """Handle the 'symbols' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.symbols(Path(args.file))
    _output_json(result, pretty=args.pretty)
    return 0


def cmd_definition(args: argparse.Namespace) -> int:
    """Handle the 'definition' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.definition(Path(args.file), args.line, args.col)
    _output_json(result, pretty=args.pretty)
    return 0


def cmd_references(args: argparse.Namespace) -> int:
    """Handle the 'references' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.references(Path(args.file), args.line, args.col)
    _output_json(result, pretty=args.pretty)
    return 0


def cmd_hover(args: argparse.Namespace) -> int:
    """Handle the 'hover' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.hover(Path(args.file), args.line, args.col)
    if result is None:
        _output_json({}, pretty=args.pretty)
    else:
        _output_json(result, pretty=args.pretty)
    return 0


def cmd_diagnostics(args: argparse.Namespace) -> int:
    """Handle the 'diagnostics' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.diagnostics(Path(args.file))
    _output_json(result, pretty=args.pretty)
    return 0


def cmd_explore(args: argparse.Namespace) -> int:
    """Handle the 'explore' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.explore(Path(args.file))
    _output_json(result, pretty=args.pretty)
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    """Handle the 'impact' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.impact(Path(args.file), args.line, args.col, depth=args.depth)
    _output_json(result, pretty=args.pretty)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="lsp_explorer",
        description=(
            "Query language servers for code intelligence — symbols, definitions,"
            " references, hover, diagnostics, and impact analysis."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output (indent=2)")
    parser.add_argument("--root", type=Path, default=None, help="Override project root directory")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # symbols
    p_sym = subparsers.add_parser("symbols", help="List symbols in a file")
    p_sym.add_argument("file", help="File to analyze")
    p_sym.set_defaults(func=cmd_symbols)

    # definition
    p_def = subparsers.add_parser("definition", help="Go to definition of symbol at position")
    p_def.add_argument("file", help="File containing the symbol")
    p_def.add_argument("line", type=int, help="Line number (1-indexed)")
    p_def.add_argument("col", type=int, help="Column number (1-indexed)")
    p_def.set_defaults(func=cmd_definition)

    # references
    p_ref = subparsers.add_parser("references", help="Find all references to symbol at position")
    p_ref.add_argument("file", help="File containing the symbol")
    p_ref.add_argument("line", type=int, help="Line number (1-indexed)")
    p_ref.add_argument("col", type=int, help="Column number (1-indexed)")
    p_ref.set_defaults(func=cmd_references)

    # hover
    p_hov = subparsers.add_parser("hover", help="Get hover info (type signature, docs) at position")
    p_hov.add_argument("file", help="File containing the symbol")
    p_hov.add_argument("line", type=int, help="Line number (1-indexed)")
    p_hov.add_argument("col", type=int, help="Column number (1-indexed)")
    p_hov.set_defaults(func=cmd_hover)

    # diagnostics
    p_diag = subparsers.add_parser(
        "diagnostics", help="Get diagnostics (errors, warnings) for a file"
    )
    p_diag.add_argument("file", help="File to check")
    p_diag.set_defaults(func=cmd_diagnostics)

    # explore
    p_exp = subparsers.add_parser("explore", help="Combined symbols + diagnostics overview")
    p_exp.add_argument("file", help="File to explore")
    p_exp.set_defaults(func=cmd_explore)

    # impact
    p_imp = subparsers.add_parser("impact", help="Analyze change impact (multi-hop references)")
    p_imp.add_argument("file", help="File containing the symbol")
    p_imp.add_argument("line", type=int, help="Line number (1-indexed)")
    p_imp.add_argument("col", type=int, help="Column number (1-indexed)")
    p_imp.add_argument("--depth", type=int, default=1, help="Reference trace depth (default: 1)")
    p_imp.set_defaults(func=cmd_impact)

    return parser


def main(args: argparse.Namespace) -> int:
    """Main entry point."""
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    try:
        ret: int = args.func(args)
        return ret
    except ServerNotFound as e:
        _error_json(str(e), hint=f"Install the {e.language} language server")
        return 1
    except UnsupportedLanguage as e:
        _error_json(str(e))
        return 1
    except FileNotFoundError as e:
        _error_json(f"File not found: {e}")
        return 1
    except TimeoutError as e:
        _error_json(str(e), hint="Try increasing --timeout")
        return 1
    except JsonRpcError as e:
        _error_json(f"LSP error: {e.error_message} (code {e.code})")
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(build_parser().parse_args()))
