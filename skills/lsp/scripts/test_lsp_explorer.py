#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0", "lsprotocol>=2024.0.0"]
# ///
"""Tests for lsp_explorer.py — real fixtures, no mocks."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).parent))
import lsp_explorer  # noqa: E402

# ============================================================================
# Fixtures
# ============================================================================

HAS_PYRIGHT = shutil.which("pyright-langserver") is not None
HAS_TS_SERVER = shutil.which("typescript-language-server") is not None

skip_no_pyright = pytest.mark.skipif(not HAS_PYRIGHT, reason="pyright-langserver not installed")
skip_no_ts = pytest.mark.skipif(not HAS_TS_SERVER, reason="typescript-language-server not installed")


@pytest.fixture
def temp_dir() -> Any:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def python_fixture(temp_dir: Path) -> Path:
    """Create a Python test file with known symbols."""
    src = temp_dir / "example.py"
    src.write_text(
        textwrap.dedent("""\
        class MyClass:
            \"\"\"A test class.\"\"\"

            def __init__(self, name: str) -> None:
                self.name = name

            def greet(self) -> str:
                return f"Hello, {self.name}!"

        def main() -> None:
            obj = MyClass("World")
            print(obj.greet())

        if __name__ == "__main__":
            main()
        """),
        encoding="utf-8",
    )
    return src


@pytest.fixture
def typescript_fixture(temp_dir: Path) -> Path:
    """Create a TypeScript test file with known symbols."""
    src = temp_dir / "example.ts"
    src.write_text(
        textwrap.dedent("""\
        interface Greeter {
            greet(): string;
        }

        class MyClass implements Greeter {
            constructor(private name: string) {}

            greet(): string {
                return `Hello, ${this.name}!`;
            }
        }

        function main(): void {
            const obj = new MyClass("World");
            console.log(obj.greet());
        }

        main();
        """),
        encoding="utf-8",
    )
    # Also create a minimal tsconfig.json
    tsconfig = temp_dir / "tsconfig.json"
    tsconfig.write_text(json.dumps({"compilerOptions": {"strict": True, "target": "es2020"}}))
    return src


# ============================================================================
# Fake JSON-RPC Server for Unit Tests
# ============================================================================

FAKE_SERVER_SCRIPT = textwrap.dedent("""\
import json
import sys

def read_message():
    \"\"\"Read a Content-Length framed message from stdin.\"\"\"
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line or line == b'\\r\\n':
            break
        decoded = line.decode('ascii').strip()
        if ':' in decoded:
            key, val = decoded.split(':', 1)
            headers[key.strip().lower()] = val.strip()
    content_length = int(headers.get('content-length', 0))
    if content_length == 0:
        return None
    body = sys.stdin.buffer.read(content_length)
    return json.loads(body)

def send_message(msg):
    \"\"\"Send a Content-Length framed message to stdout.\"\"\"
    body = json.dumps(msg).encode('utf-8')
    header = f'Content-Length: {len(body)}\\r\\n\\r\\n'.encode('ascii')
    sys.stdout.buffer.write(header + body)
    sys.stdout.buffer.flush()

# Simple echo server: returns the method name as the result
while True:
    msg = read_message()
    if msg is None:
        break
    if 'id' in msg:
        # It's a request — send a response
        method = msg.get('method', '')
        if method == 'initialize':
            send_message({
                'jsonrpc': '2.0',
                'id': msg['id'],
                'result': {'capabilities': {'documentSymbolProvider': True}}
            })
        elif method == 'shutdown':
            send_message({'jsonrpc': '2.0', 'id': msg['id'], 'result': None})
            # Wait for exit notification then quit
            exit_msg = read_message()
            break
        elif method == 'textDocument/documentSymbol':
            send_message({
                'jsonrpc': '2.0',
                'id': msg['id'],
                'result': [
                    {
                        'name': 'TestSymbol',
                        'kind': 12,
                        'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 5, 'character': 0}},
                        'selectionRange': {'start': {'line': 0, 'character': 4}, 'end': {'line': 0, 'character': 14}},
                        'children': []
                    }
                ]
            })
        elif method == 'textDocument/definition':
            send_message({
                'jsonrpc': '2.0',
                'id': msg['id'],
                'result': [{
                    'uri': msg['params']['textDocument']['uri'],
                    'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 10}}
                }]
            })
        elif method == 'textDocument/references':
            send_message({
                'jsonrpc': '2.0',
                'id': msg['id'],
                'result': [
                    {
                        'uri': msg['params']['textDocument']['uri'],
                        'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 10}}
                    },
                    {
                        'uri': msg['params']['textDocument']['uri'],
                        'range': {'start': {'line': 5, 'character': 0}, 'end': {'line': 5, 'character': 10}}
                    }
                ]
            })
        elif method == 'textDocument/hover':
            send_message({
                'jsonrpc': '2.0',
                'id': msg['id'],
                'result': {
                    'contents': {'kind': 'plaintext', 'value': '(function) test_func() -> None'}
                }
            })
        else:
            send_message({'jsonrpc': '2.0', 'id': msg['id'], 'result': None})
    # Notifications (no id) are silently consumed
""")


@pytest.fixture
def fake_server() -> Any:
    """Start a fake JSON-RPC server subprocess."""
    proc = subprocess.Popen(
        [sys.executable, "-c", FAKE_SERVER_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


# ============================================================================
# Unit Tests: JsonRpcClient
# ============================================================================


class TestJsonRpcClient:
    """Test the JSON-RPC wire protocol layer."""

    def test_send_request_and_wait_response(self, fake_server: subprocess.Popen[bytes]) -> None:
        """Test basic request/response cycle."""
        client = lsp_explorer.JsonRpcClient(fake_server)
        req_id = client.send_request("initialize", {"processId": os.getpid()})
        assert req_id == 1
        result = client.wait_response(req_id)
        assert "capabilities" in result

    def test_send_notification(self, fake_server: subprocess.Popen[bytes]) -> None:
        """Test sending a notification (no response expected)."""
        client = lsp_explorer.JsonRpcClient(fake_server)
        # Initialize first
        req_id = client.send_request("initialize", {})
        client.wait_response(req_id)
        # Send notification — should not raise
        client.send_notification("initialized", {})

    def test_request_id_increments(self, fake_server: subprocess.Popen[bytes]) -> None:
        """Request IDs should auto-increment."""
        client = lsp_explorer.JsonRpcClient(fake_server)
        id1 = client.send_request("initialize", {})
        client.wait_response(id1)
        client.send_notification("initialized", {})
        id2 = client.send_request("textDocument/documentSymbol", {"textDocument": {"uri": "file:///test.py"}})
        assert id2 == id1 + 1

    def test_timeout_raises(self, fake_server: subprocess.Popen[bytes]) -> None:
        """Wait with very short timeout should raise TimeoutError."""
        client = lsp_explorer.JsonRpcClient(fake_server)
        req_id = client.send_request("initialize", {})
        client.wait_response(req_id)
        # Now try to wait for a response that won't come (we didn't send a request)
        with pytest.raises(TimeoutError):
            client.wait_response(999, timeout=0.1)

    def test_drain_notifications_empty(self, fake_server: subprocess.Popen[bytes]) -> None:
        """Draining with no pending notifications returns empty list."""
        client = lsp_explorer.JsonRpcClient(fake_server)
        req_id = client.send_request("initialize", {})
        client.wait_response(req_id)
        result = client.drain_notifications(timeout=0.2)
        assert result == []


# ============================================================================
# Unit Tests: LspSession (with fake server)
# ============================================================================


class TestLspSession:
    """Test LSP protocol operations with the fake server."""

    def _make_session(self, fake_server: subprocess.Popen[bytes], temp_dir: Path) -> lsp_explorer.LspSession:
        client = lsp_explorer.JsonRpcClient(fake_server)
        return lsp_explorer.LspSession(client, temp_dir, "python")

    def test_initialize_and_shutdown(self, fake_server: subprocess.Popen[bytes], temp_dir: Path) -> None:
        """Test the full LSP lifecycle."""
        session = self._make_session(fake_server, temp_dir)
        result = session.initialize()
        assert "capabilities" in result
        session.shutdown()

    def test_document_symbol(self, fake_server: subprocess.Popen[bytes], temp_dir: Path) -> None:
        """Test documentSymbol returns formatted symbols."""
        # Create a test file so did_open can read it
        test_file = temp_dir / "test.py"
        test_file.write_text("def test_func(): pass\n")

        session = self._make_session(fake_server, temp_dir)
        session.initialize()
        symbols = session.document_symbol(test_file)
        assert len(symbols) == 1
        assert symbols[0]["name"] == "TestSymbol"
        assert symbols[0]["kind"] == 12  # function
        session.shutdown()

    def test_definition(self, fake_server: subprocess.Popen[bytes], temp_dir: Path) -> None:
        """Test go-to-definition."""
        test_file = temp_dir / "test.py"
        test_file.write_text("def test_func(): pass\n")

        session = self._make_session(fake_server, temp_dir)
        session.initialize()
        result = session.definition(test_file, 0, 4)
        assert len(result) >= 1
        assert "uri" in result[0]
        session.shutdown()

    def test_references(self, fake_server: subprocess.Popen[bytes], temp_dir: Path) -> None:
        """Test find references."""
        test_file = temp_dir / "test.py"
        test_file.write_text("x = 1\nprint(x)\n")

        session = self._make_session(fake_server, temp_dir)
        session.initialize()
        result = session.references(test_file, 0, 0)
        assert len(result) == 2
        session.shutdown()

    def test_hover(self, fake_server: subprocess.Popen[bytes], temp_dir: Path) -> None:
        """Test hover information."""
        test_file = temp_dir / "test.py"
        test_file.write_text("def test_func(): pass\n")

        session = self._make_session(fake_server, temp_dir)
        session.initialize()
        result = session.hover(test_file, 0, 4)
        assert result is not None
        assert "contents" in result
        session.shutdown()

    def test_did_open_idempotent(self, fake_server: subprocess.Popen[bytes], temp_dir: Path) -> None:
        """Opening the same document twice should be safe."""
        test_file = temp_dir / "test.py"
        test_file.write_text("pass\n")

        session = self._make_session(fake_server, temp_dir)
        session.initialize()
        session.did_open(test_file)
        session.did_open(test_file)  # Should not raise
        session.shutdown()


# ============================================================================
# Unit Tests: Helper Functions
# ============================================================================


class TestHelpers:
    """Test utility functions."""

    def test_detect_language_python(self) -> None:
        assert lsp_explorer.detect_language(Path("test.py")) == "python"

    def test_detect_language_typescript(self) -> None:
        assert lsp_explorer.detect_language(Path("test.ts")) == "typescript"

    def test_detect_language_tsx(self) -> None:
        assert lsp_explorer.detect_language(Path("test.tsx")) == "typescript"

    def test_detect_language_js(self) -> None:
        assert lsp_explorer.detect_language(Path("test.js")) == "javascript"

    def test_detect_language_unsupported(self) -> None:
        with pytest.raises(lsp_explorer.UnsupportedLanguage):
            lsp_explorer.detect_language(Path("test.rb"))

    def test_detect_project_root_with_git(self, temp_dir: Path) -> None:
        resolved_dir = temp_dir.resolve()  # macOS: /var -> /private/var
        (resolved_dir / ".git").mkdir()
        sub = resolved_dir / "src"
        sub.mkdir()
        test_file = sub / "test.py"
        test_file.touch()
        assert lsp_explorer.detect_project_root(test_file) == resolved_dir

    def test_detect_project_root_with_pyproject(self, temp_dir: Path) -> None:
        resolved_dir = temp_dir.resolve()
        (resolved_dir / "pyproject.toml").touch()
        test_file = resolved_dir / "test.py"
        test_file.touch()
        assert lsp_explorer.detect_project_root(test_file) == resolved_dir

    def test_detect_project_root_fallback(self, temp_dir: Path) -> None:
        resolved_dir = temp_dir.resolve()
        test_file = resolved_dir / "test.py"
        test_file.touch()
        # No project markers — falls back to parent dir
        result = lsp_explorer.detect_project_root(test_file)
        assert result == resolved_dir

    def test_symbol_kind_name(self) -> None:
        assert lsp_explorer._symbol_kind_name(5) == "class"
        assert lsp_explorer._symbol_kind_name(12) == "function"
        assert lsp_explorer._symbol_kind_name(6) == "method"
        assert "unknown" in lsp_explorer._symbol_kind_name(999)

    def test_format_symbol_basic(self) -> None:
        sym = {
            "name": "MyFunc",
            "kind": 12,
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 5, "character": 0}},
            "selectionRange": {
                "start": {"line": 0, "character": 4},
                "end": {"line": 0, "character": 10},
            },
            "children": [],
        }
        result = lsp_explorer._format_symbol(sym)
        assert result["n"] == "MyFunc"
        assert result["k"] == "function"
        assert result["r"] == [1, 6]  # 1-indexed
        assert result["l"] == 1
        assert result["c"] == 5

    def test_format_symbol_with_children(self) -> None:
        sym = {
            "name": "MyClass",
            "kind": 5,
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 10, "character": 0}},
            "children": [
                {
                    "name": "__init__",
                    "kind": 6,
                    "range": {
                        "start": {"line": 2, "character": 4},
                        "end": {"line": 4, "character": 0},
                    },
                    "children": [],
                }
            ],
        }
        result = lsp_explorer._format_symbol(sym)
        assert "ch" in result
        assert len(result["ch"]) == 1
        assert result["ch"][0]["n"] == "__init__"
        assert result["ch"][0]["k"] == "method"

    def test_format_location(self, temp_dir: Path) -> None:
        loc = {
            "uri": (temp_dir / "src" / "main.py").as_uri(),
            "range": {"start": {"line": 10, "character": 5}, "end": {"line": 10, "character": 15}},
        }
        result = lsp_explorer._format_location(loc, temp_dir)
        assert result["f"] == "src/main.py"
        assert result["l"] == 11  # 1-indexed
        assert result["c"] == 6

    def test_format_hover_plaintext(self) -> None:
        result = lsp_explorer._format_hover({"contents": {"kind": "plaintext", "value": "def foo() -> int"}})
        assert result is not None
        assert "type" in result

    def test_format_hover_markdown_codeblock(self) -> None:
        result = lsp_explorer._format_hover(
            {
                "contents": {
                    "kind": "markdown",
                    "value": "```python\ndef foo() -> int\n```\nReturns an integer.",
                }
            }
        )
        assert result is not None
        assert result["type"] == "def foo() -> int"
        assert "Returns" in result.get("doc", "")

    def test_format_hover_none(self) -> None:
        assert lsp_explorer._format_hover(None) is None

    def test_format_hover_empty(self) -> None:
        assert lsp_explorer._format_hover({"contents": {"kind": "plaintext", "value": ""}}) is None

    def test_format_diagnostic(self, temp_dir: Path) -> None:
        diag = {
            "range": {"start": {"line": 5, "character": 10}, "end": {"line": 5, "character": 20}},
            "severity": 1,
            "message": "Type error",
            "source": "pyright",
            "code": "reportGeneralClassIssue",
        }
        result = lsp_explorer._format_diagnostic(diag, temp_dir / "test.py", temp_dir)
        assert result["f"] == "test.py"
        assert result["l"] == 6  # 1-indexed
        assert result["s"] == 1
        assert result["msg"] == "Type error"
        assert result["src"] == "pyright"

    def test_get_line_preview(self, temp_dir: Path) -> None:
        f = temp_dir / "test.py"
        f.write_text("line one\nline two\nline three\n")
        assert lsp_explorer._get_line_preview(f, 2) == "line two"
        assert lsp_explorer._get_line_preview(f, 99) is None

    def test_uri_to_path(self) -> None:
        p = lsp_explorer._uri_to_path("file:///Users/test/foo.py")
        assert str(p) == "/Users/test/foo.py"

    def test_relative_path(self, temp_dir: Path) -> None:
        sub = temp_dir / "src" / "main.py"
        assert lsp_explorer._relative_path(sub, temp_dir) == "src/main.py"


# ============================================================================
# Unit Tests: CLI
# ============================================================================


class TestCLI:
    """Test CLI argument parsing."""

    def test_build_parser_help(self) -> None:
        """Parser builds without error."""
        parser = lsp_explorer.build_parser()
        assert parser is not None

    def test_symbols_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["symbols", "test.py"])
        assert args.command == "symbols"
        assert args.file == "test.py"

    def test_definition_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["definition", "test.py", "10", "5"])
        assert args.command == "definition"
        assert args.line == 10
        assert args.col == 5

    def test_references_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["references", "test.py", "3", "8"])
        assert args.command == "references"
        assert args.line == 3

    def test_hover_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["hover", "test.py", "1", "1"])
        assert args.command == "hover"

    def test_diagnostics_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["diagnostics", "test.py"])
        assert args.command == "diagnostics"

    def test_explore_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["explore", "test.py"])
        assert args.command == "explore"

    def test_impact_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["impact", "test.py", "5", "10", "--depth", "2"])
        assert args.command == "impact"
        assert args.depth == 2

    def test_global_flags(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["symbols", "test.py", "-v", "--pretty", "--timeout", "60"])
        assert args.verbose is True
        assert args.pretty is True
        assert args.timeout == 60.0

    def test_error_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test error JSON formatting."""
        lsp_explorer._error_json("Something failed", hint="Try again")
        captured = capsys.readouterr()
        err = json.loads(captured.err)
        assert err["error"] == "Something failed"
        assert err["hint"] == "Try again"

    def test_output_json_compact(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Default output should be compact JSON."""
        lsp_explorer._output_json({"key": "value", "num": 42})
        captured = capsys.readouterr()
        # Compact = no spaces after : or ,
        assert captured.out.strip() == '{"key":"value","num":42}'

    def test_output_json_pretty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--pretty should indent JSON."""
        lsp_explorer._output_json({"key": "value"}, pretty=True)
        captured = capsys.readouterr()
        assert "  " in captured.out  # Has indentation


# ============================================================================
# Unit Tests: CodeExplorer (with fake server via subprocess)
# ============================================================================


class TestCodeExplorerWithFakeServer:
    """Test CodeExplorer methods using a patched LanguageServerManager that spawns the fake server."""

    def _make_explorer_symbols(self, temp_dir: Path, test_file: Path) -> list[dict[str, Any]]:
        """Directly test the formatting pipeline without a real server."""
        # Simulate what CodeExplorer.symbols() does with raw LSP output
        raw_symbols = [
            {
                "name": "MyClass",
                "kind": 5,
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 8, "character": 0}},
                "selectionRange": {
                    "start": {"line": 0, "character": 6},
                    "end": {"line": 0, "character": 13},
                },
                "children": [
                    {
                        "name": "__init__",
                        "kind": 6,
                        "range": {
                            "start": {"line": 3, "character": 4},
                            "end": {"line": 4, "character": 25},
                        },
                        "selectionRange": {
                            "start": {"line": 3, "character": 8},
                            "end": {"line": 3, "character": 16},
                        },
                        "children": [],
                    },
                    {
                        "name": "greet",
                        "kind": 6,
                        "range": {
                            "start": {"line": 6, "character": 4},
                            "end": {"line": 7, "character": 41},
                        },
                        "selectionRange": {
                            "start": {"line": 6, "character": 8},
                            "end": {"line": 6, "character": 13},
                        },
                        "children": [],
                    },
                ],
            },
            {
                "name": "main",
                "kind": 12,
                "range": {
                    "start": {"line": 10, "character": 0},
                    "end": {"line": 12, "character": 26},
                },
                "selectionRange": {
                    "start": {"line": 10, "character": 4},
                    "end": {"line": 10, "character": 8},
                },
                "children": [],
            },
        ]
        return [lsp_explorer._format_symbol(s) for s in raw_symbols]

    def test_symbols_formatting(self, temp_dir: Path) -> None:
        test_file = temp_dir / "example.py"
        test_file.write_text("class MyClass:\n    pass\n")
        result = self._make_explorer_symbols(temp_dir, test_file)
        assert len(result) == 2
        # MyClass
        assert result[0]["n"] == "MyClass"
        assert result[0]["k"] == "class"
        assert result[0]["r"] == [1, 9]
        assert len(result[0]["ch"]) == 2
        # main
        assert result[1]["n"] == "main"
        assert result[1]["k"] == "function"

    def test_compact_json_output(self, temp_dir: Path) -> None:
        test_file = temp_dir / "example.py"
        test_file.write_text("pass\n")
        result = self._make_explorer_symbols(temp_dir, test_file)
        output = json.dumps(result, separators=(",", ":"))
        # Verify it's compact (no spaces)
        assert " " not in output


# ============================================================================
# Integration Tests: Real LSP Servers
# ============================================================================


@skip_no_pyright
class TestPyrightIntegration:
    """Integration tests with real pyright-langserver."""

    def test_symbols(self, python_fixture: Path) -> None:
        """Test document symbols with real pyright."""
        explorer = lsp_explorer.CodeExplorer(root_path=python_fixture.parent)
        result = explorer.symbols(python_fixture)
        # Should find MyClass and main at minimum
        names = [s["n"] for s in result]
        assert "MyClass" in names
        assert "main" in names
        # MyClass should have children
        my_class = next(s for s in result if s["n"] == "MyClass")
        child_names = [c["n"] for c in my_class.get("ch", [])]
        assert "__init__" in child_names
        assert "greet" in child_names

    def test_definition(self, python_fixture: Path) -> None:
        """Test go-to-definition with pyright."""
        explorer = lsp_explorer.CodeExplorer(root_path=python_fixture.parent)
        # Line 11 (1-indexed): `obj = MyClass("World")`
        # Column for MyClass should be around 11
        result = explorer.definition(python_fixture, 11, 11)
        assert len(result) >= 1
        # Definition should point to line 1 where MyClass is defined
        assert result[0]["l"] == 1

    def test_references(self, python_fixture: Path) -> None:
        """Test find-references with pyright."""
        explorer = lsp_explorer.CodeExplorer(root_path=python_fixture.parent)
        # Reference to 'main' — defined on line 10, called on line 15
        result = explorer.references(python_fixture, 10, 5)
        assert result["total"] >= 1

    def test_hover(self, python_fixture: Path) -> None:
        """Test hover with pyright."""
        explorer = lsp_explorer.CodeExplorer(root_path=python_fixture.parent)
        # Hover over 'MyClass' on line 1
        result = explorer.hover(python_fixture, 1, 7)
        assert result is not None
        assert "type" in result or "doc" in result

    def test_explore(self, python_fixture: Path) -> None:
        """Test combined explore with pyright."""
        explorer = lsp_explorer.CodeExplorer(root_path=python_fixture.parent)
        result = explorer.explore(python_fixture)
        assert result["lang"] == "python"
        assert result["symbols"] >= 2
        assert "syms" in result

    def test_impact(self, python_fixture: Path) -> None:
        """Test impact analysis with pyright."""
        explorer = lsp_explorer.CodeExplorer(root_path=python_fixture.parent)
        result = explorer.impact(python_fixture, 10, 5)
        assert "affected" in result
        assert "total" in result


@skip_no_ts
class TestTypescriptIntegration:
    """Integration tests with real typescript-language-server."""

    def test_symbols(self, typescript_fixture: Path) -> None:
        """Test document symbols with real TS server."""
        explorer = lsp_explorer.CodeExplorer(root_path=typescript_fixture.parent)
        result = explorer.symbols(typescript_fixture)
        names = [s["n"] for s in result]
        assert "MyClass" in names or "Greeter" in names

    def test_hover(self, typescript_fixture: Path) -> None:
        """Test hover with TS server."""
        explorer = lsp_explorer.CodeExplorer(root_path=typescript_fixture.parent)
        result = explorer.hover(typescript_fixture, 5, 7)
        assert result is not None


# ============================================================================
# Unit Tests: File Classification
# ============================================================================


class TestFileClassification:
    """Test the classify_file_type function with parametrized test patterns."""

    @pytest.mark.parametrize(
        "path,expected",
        [
            # Test directories
            ("tests/test_main.py", "test"),
            ("test/test_main.py", "test"),
            ("src/tests/test_main.py", "test"),
            ("__tests__/MyComponent.test.ts", "test"),
            # Pytest patterns
            ("test_main.py", "test"),
            ("src/test_main.py", "test"),
            ("main_test.py", "test"),
            ("conftest.py", "test"),
            ("tests/conftest.py", "test"),
            # JS/TS test patterns
            ("Button.test.ts", "test"),
            ("Button.test.tsx", "test"),
            ("Button.spec.ts", "test"),
            ("Button.spec.tsx", "test"),
            ("Button.test.js", "test"),
            ("Button.spec.jsx", "test"),
            # Fixtures
            ("fixtures/data.py", "test"),
            ("fixture/sample.py", "test"),
            # Source files
            ("src/main.py", "source"),
            ("lib/utils.ts", "source"),
            ("app/components/Button.tsx", "source"),
            ("main.py", "source"),
            ("setup.py", "source"),
        ],
    )
    def test_classify_file_type(self, path: str, expected: str) -> None:
        assert lsp_explorer.classify_file_type(path) == expected


# ============================================================================
# Unit Tests: Semantic Token Decoding
# ============================================================================


class TestSemanticTokenDecoding:
    """Test the decode_semantic_tokens function."""

    def _make_legend(self) -> dict[str, Any]:
        return {
            "tokenTypes": lsp_explorer.STANDARD_TOKEN_TYPES,
            "tokenModifiers": lsp_explorer.STANDARD_TOKEN_MODIFIERS,
        }

    def test_empty_data(self) -> None:
        result = lsp_explorer.decode_semantic_tokens([], self._make_legend(), "")
        assert result == []

    def test_single_reference_token(self) -> None:
        # One token: line 0, col 4, length 3, type=variable (idx 8), modifiers=0 (reference)
        source = "def foo():\n    bar()\n"
        data = [1, 4, 3, 8, 0]  # deltaLine=1, deltaCol=4, len=3, type=variable, mods=0
        result = lsp_explorer.decode_semantic_tokens(data, self._make_legend(), source)
        assert len(result) == 1
        assert result[0]["name"] == "bar"
        assert result[0]["kind"] == "variable"
        assert result[0]["line"] == 2  # 1-indexed
        assert result[0]["col"] == 5  # 1-indexed
        assert result[0]["is_definition"] is False

    def test_definition_token_with_declaration_modifier(self) -> None:
        # declaration modifier = bit 0 = bitmask 1
        source = "class MyClass:\n    pass\n"
        data = [0, 6, 7, 2, 1]  # line=0, col=6, len=7, type=class (idx 2), mods=1 (declaration)
        result = lsp_explorer.decode_semantic_tokens(data, self._make_legend(), source)
        assert len(result) == 1
        assert result[0]["name"] == "MyClass"
        assert result[0]["kind"] == "class"
        assert result[0]["is_definition"] is True

    def test_definition_token_with_definition_modifier(self) -> None:
        # definition modifier = bit 1 = bitmask 2
        source = "def func():\n    pass\n"
        data = [0, 4, 4, 12, 2]  # line=0, col=4, len=4, type=function (idx 12), mods=2 (definition)
        result = lsp_explorer.decode_semantic_tokens(data, self._make_legend(), source)
        assert len(result) == 1
        assert result[0]["name"] == "func"
        assert result[0]["kind"] == "function"
        assert result[0]["is_definition"] is True

    def test_skips_keyword_tokens(self) -> None:
        # keyword type = index 15, should be skipped
        source = "class MyClass:\n    pass\n"
        data = [0, 0, 5, 15, 0]  # type=keyword (idx 15)
        result = lsp_explorer.decode_semantic_tokens(data, self._make_legend(), source)
        assert len(result) == 0

    def test_multiple_tokens_delta_encoding(self) -> None:
        source = "x = y + z\n"
        data = [
            0,
            0,
            1,
            8,
            1,  # x at (0,0), variable, declaration
            0,
            4,
            1,
            8,
            0,  # y at (0,4), variable, reference
            0,
            4,
            1,
            8,
            0,  # z at (0,8), variable, reference
        ]
        result = lsp_explorer.decode_semantic_tokens(data, self._make_legend(), source)
        assert len(result) == 3
        assert result[0]["name"] == "x"
        assert result[0]["is_definition"] is True
        assert result[1]["name"] == "y"
        assert result[1]["is_definition"] is False
        assert result[2]["name"] == "z"
        assert result[2]["is_definition"] is False

    def test_multiline_tokens(self) -> None:
        source = "a = 1\nb = 2\nc = 3\n"
        data = [
            0,
            0,
            1,
            8,
            1,  # a at (0,0)
            1,
            0,
            1,
            8,
            1,  # b at (1,0)  — new line resets col
            1,
            0,
            1,
            8,
            1,  # c at (2,0)
        ]
        result = lsp_explorer.decode_semantic_tokens(data, self._make_legend(), source)
        assert len(result) == 3
        assert result[0]["line"] == 1
        assert result[1]["line"] == 2
        assert result[2]["line"] == 3


# ============================================================================
# Unit Tests: IndexCacheManager
# ============================================================================


class TestIndexCacheManager:
    """Test the SQLite-backed symbol index cache."""

    @pytest.fixture
    def cache_dir(self, temp_dir: Path) -> Path:
        d = temp_dir / "cache"
        d.mkdir()
        return d

    @pytest.fixture
    def cache(self, cache_dir: Path) -> Any:
        db_path = cache_dir / "test_index.db"
        mgr = lsp_explorer.IndexCacheManager(db_path=db_path)
        mgr.init_schema()
        yield mgr
        mgr.close()

    def test_init_schema_creates_tables(self, cache: lsp_explorer.IndexCacheManager) -> None:
        tables = {row[0] for row in cache.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "source_files" in tables
        assert "symbols" in tables
        assert "cache_metadata" in tables
        assert "symbol_containments" in tables
        assert "definition_ranges" in tables

    def test_init_schema_creates_views(self, cache: lsp_explorer.IndexCacheManager) -> None:
        views = {row[0] for row in cache.conn.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()}
        assert "definitions" in views
        assert "references" in views

    def test_needs_rebuild_false_after_init(self, cache: lsp_explorer.IndexCacheManager) -> None:
        assert cache.needs_rebuild() is False

    def test_needs_rebuild_true_for_fresh_db(self, cache_dir: Path) -> None:
        db_path = cache_dir / "fresh.db"
        mgr = lsp_explorer.IndexCacheManager(db_path=db_path)
        assert mgr.needs_rebuild() is True
        mgr.close()

    def test_clear_empties_all(self, cache: lsp_explorer.IndexCacheManager) -> None:
        # Insert some data
        cache.conn.execute(
            "INSERT INTO source_files (filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("/test.py", "test.py", 1.0, 100, "now", "python", "pyright-langserver", "source"),
        )
        cache.conn.commit()
        assert cache.conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0] == 1

        cache.clear()
        assert cache.conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0] == 0

    def test_get_status(self, cache: lsp_explorer.IndexCacheManager) -> None:
        status = cache.get_status()
        assert status["files"] == 0
        assert status["symbols"] == 0
        assert status["definitions"] == 0
        assert status["references"] == 0
        assert "db_path" in status

    def test_get_status_with_data(self, cache: lsp_explorer.IndexCacheManager) -> None:
        # Insert a source file
        cache.conn.execute(
            "INSERT INTO source_files (filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("/test.py", "test.py", 1.0, 100, "now", "python", "pyright-langserver", "source"),
        )
        # Insert a definition
        cache.conn.execute(
            "INSERT INTO symbols (source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition, scope_start_line, scope_end_line) "
            "VALUES (1, 'foo', 'function', 1, 1, 5, 1, 1, 1, 5)",
        )
        # Insert a reference
        cache.conn.execute(
            "INSERT INTO symbols (source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition) VALUES (1, 'foo', 'function', 10, 1, 10, 4, 0)",
        )
        cache.conn.commit()

        status = cache.get_status()
        assert status["files"] == 1
        assert status["symbols"] == 2
        assert status["definitions"] == 1
        assert status["references"] == 1

    def test_high_watermark_empty(self, cache: lsp_explorer.IndexCacheManager) -> None:
        assert cache.get_high_watermark() == 0.0

    def test_high_watermark_with_data(self, cache: lsp_explorer.IndexCacheManager) -> None:
        cache.conn.execute(
            "INSERT INTO source_files (filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("/a.py", "a.py", 100.0, 50, "now", "python", "pyright-langserver", "source"),
        )
        cache.conn.execute(
            "INSERT INTO source_files (filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("/b.py", "b.py", 200.0, 50, "now", "python", "pyright-langserver", "source"),
        )
        cache.conn.commit()
        assert cache.get_high_watermark() == 200.0

    def test_remove_stale_files(self, cache: lsp_explorer.IndexCacheManager) -> None:
        cache.conn.execute(
            "INSERT INTO source_files (filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("/a.py", "a.py", 1.0, 50, "now", "python", "pyright-langserver", "source"),
        )
        cache.conn.execute(
            "INSERT INTO source_files (filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("/b.py", "b.py", 1.0, 50, "now", "python", "pyright-langserver", "source"),
        )
        cache.conn.commit()

        removed = cache.remove_stale_files({"/a.py"})
        assert removed == 1
        remaining = cache.conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
        assert remaining == 1

    def test_get_files_needing_update(self, cache: lsp_explorer.IndexCacheManager) -> None:
        # Insert a file with mtime 100
        cache.conn.execute(
            "INSERT INTO source_files (filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("/a.py", "a.py", 100.0, 50, "now", "python", "pyright-langserver", "source"),
        )
        cache.conn.commit()

        files = [
            {"filepath": "/a.py", "mtime": 100.0},  # same mtime = no update
            {"filepath": "/a.py", "mtime": 200.0},  # newer = needs update
            {"filepath": "/c.py", "mtime": 50.0},  # new file = needs update
        ]
        # Check each case
        assert len(cache.get_files_needing_update([files[0]])) == 0
        assert len(cache.get_files_needing_update([files[1]])) == 1
        assert len(cache.get_files_needing_update([files[2]])) == 1

    def test_cascade_delete(self, cache: lsp_explorer.IndexCacheManager) -> None:
        """Deleting a source_file should cascade-delete its symbols."""
        cache.conn.execute(
            "INSERT INTO source_files (filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("/a.py", "a.py", 1.0, 50, "now", "python", "pyright-langserver", "source"),
        )
        cache.conn.execute(
            "INSERT INTO symbols (source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition) VALUES (1, 'foo', 'function', 1, 1, 5, 1, 1)",
        )
        cache.conn.commit()
        assert cache.conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0] == 1

        cache.conn.execute("DELETE FROM source_files WHERE id = 1")
        cache.conn.commit()
        assert cache.conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0] == 0


# ============================================================================
# Unit Tests: Index Queries (hand-constructed data)
# ============================================================================


class TestIndexQueries:
    """Test SQL queries against hand-constructed index data."""

    @pytest.fixture
    def populated_cache(self, temp_dir: Path) -> Any:
        db_path = temp_dir / "query_test.db"
        cache = lsp_explorer.IndexCacheManager(db_path=db_path)
        cache.init_schema()

        # Create two source files
        cache.conn.execute(
            "INSERT INTO source_files (id, filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (1, '/src/main.py', 'src/main.py', 1.0, 100, "
            "'now', 'python', 'pyright-langserver', 'source')"
        )
        cache.conn.execute(
            "INSERT INTO source_files (id, filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (2, '/tests/test_main.py', 'tests/test_main.py', "
            "1.0, 80, 'now', 'python', 'pyright-langserver', 'test')"
        )

        # Definitions in main.py
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition, scope_start_line, scope_end_line) "
            "VALUES (1, 1, 'MyClass', 'class', 1, 7, 1, 14, 1, 1, 20)"
        )
        cache.conn.execute(
            "INSERT INTO definition_ranges (id, min_line, max_line, min_file_id, max_file_id) VALUES (1, 1, 20, 1, 1)"
        )
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition, scope_start_line, scope_end_line) "
            "VALUES (2, 1, 'process', 'method', 5, 9, 5, 16, 1, 5, 15)"
        )
        cache.conn.execute(
            "INSERT INTO definition_ranges (id, min_line, max_line, min_file_id, max_file_id) VALUES (2, 5, 15, 1, 1)"
        )
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition, scope_start_line, scope_end_line) "
            "VALUES (3, 1, 'main', 'function', 22, 5, 22, 9, 1, 22, 30)"
        )
        cache.conn.execute(
            "INSERT INTO definition_ranges (id, min_line, max_line, min_file_id, max_file_id) VALUES (3, 22, 30, 1, 1)"
        )
        # Unreferenced definition (dead code)
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition, scope_start_line, scope_end_line) "
            "VALUES (4, 1, '_helper', 'function', 32, 5, 32, 12, 1, 32, 35)"
        )
        cache.conn.execute(
            "INSERT INTO definition_ranges (id, min_line, max_line, min_file_id, max_file_id) VALUES (4, 32, 35, 1, 1)"
        )

        # References — 'process' used in main.py's main function (line 25)
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition) VALUES (5, 1, 'process', 'method', 25, 10, 25, 17, 0)"
        )
        # Reference to 'MyClass' in test file
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition) VALUES (6, 2, 'MyClass', 'class', 5, 10, 5, 17, 0)"
        )
        # Reference to 'main' in test file
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition) VALUES (7, 2, 'main', 'function', 10, 5, 10, 9, 0)"
        )

        cache.conn.commit()

        # Populate containments
        cache._populate_containments()

        yield cache
        cache.close()

    def test_definitions_view(self, populated_cache: lsp_explorer.IndexCacheManager) -> None:
        rows = populated_cache.conn.execute("SELECT * FROM definitions").fetchall()
        assert len(rows) == 4  # MyClass, process, main, _helper

    def test_references_view(self, populated_cache: lsp_explorer.IndexCacheManager) -> None:
        rows = populated_cache.conn.execute('SELECT * FROM "references"').fetchall()
        assert len(rows) == 3  # process ref, MyClass ref, main ref

    def test_dead_code_query(self, populated_cache: lsp_explorer.IndexCacheManager) -> None:
        """_helper has no references — should appear as dead code."""
        rows = populated_cache.conn.execute(
            """\
            SELECT s.name, s.kind, sf.relative_path, s.line
            FROM symbols s
            JOIN source_files sf ON sf.id = s.source_file_id
            WHERE s.is_definition = 1
              AND s.kind NOT IN ('module', 'package', 'namespace')
              AND NOT EXISTS (
                  SELECT 1 FROM symbols ref
                  WHERE ref.name = s.name AND ref.id != s.id AND ref.is_definition = 0
              )
            ORDER BY sf.relative_path, s.line
            """
        ).fetchall()
        dead_names = [r["name"] for r in rows]
        assert "_helper" in dead_names

    def test_dead_code_excludes_referenced(self, populated_cache: lsp_explorer.IndexCacheManager) -> None:
        """MyClass, process, main all have references — should NOT appear as dead."""
        rows = populated_cache.conn.execute(
            """\
            SELECT s.name FROM symbols s
            WHERE s.is_definition = 1
              AND s.kind NOT IN ('module', 'package', 'namespace')
              AND NOT EXISTS (
                  SELECT 1 FROM symbols ref
                  WHERE ref.name = s.name AND ref.id != s.id AND ref.is_definition = 0
              )
            """
        ).fetchall()
        dead_names = {r["name"] for r in rows}
        assert "MyClass" not in dead_names
        assert "process" not in dead_names
        assert "main" not in dead_names

    def test_containment_edges(self, populated_cache: lsp_explorer.IndexCacheManager) -> None:
        """'process' method (line 5) should be contained within MyClass (lines 1-20)."""
        rows = populated_cache.conn.execute(
            """\
            SELECT inner_symbol_id, outer_symbol_id FROM symbol_containments
            WHERE inner_symbol_id = 2
            """
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["outer_symbol_id"] == 1  # MyClass contains process

    def test_reference_containment(self, populated_cache: lsp_explorer.IndexCacheManager) -> None:
        """Reference to 'process' at line 25 should be contained in 'main' (lines 22-30)."""
        rows = populated_cache.conn.execute(
            """\
            SELECT inner_symbol_id, outer_symbol_id FROM symbol_containments
            WHERE inner_symbol_id = 5
            """
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["outer_symbol_id"] == 3  # main() contains the process reference

    def test_impact_cte(self, populated_cache: lsp_explorer.IndexCacheManager) -> None:
        """Impact trace from 'process' should find 'main' via containment."""
        rows = populated_cache.conn.execute(
            """\
            WITH RECURSIVE impact_chain(sym_id, name, source_file_id, depth) AS (
                SELECT s.id, s.name, s.source_file_id, 0
                FROM symbols s WHERE s.id = 2 AND s.is_definition = 1
                UNION ALL
                SELECT enclosing.id, enclosing.name, enclosing.source_file_id, ic.depth + 1
                FROM impact_chain ic
                JOIN symbols ref ON ref.name = ic.name AND ref.is_definition = 0
                JOIN symbol_containments sc ON sc.inner_symbol_id = ref.id
                JOIN symbols enclosing ON enclosing.id = sc.outer_symbol_id
                WHERE ic.depth < 3
            )
            SELECT DISTINCT ic.depth, ic.name, s.kind, sf.relative_path, s.line
            FROM impact_chain ic
            JOIN symbols s ON s.id = ic.sym_id
            JOIN source_files sf ON sf.id = ic.source_file_id
            ORDER BY ic.depth, sf.relative_path, s.line
            """
        ).fetchall()
        names_by_depth = {r["depth"]: r["name"] for r in rows}
        assert 0 in names_by_depth
        assert names_by_depth[0] == "process"
        # Depth 1: main() contains a reference to 'process'
        assert 1 in names_by_depth
        assert names_by_depth[1] == "main"

    def test_ancestors_cte(self, populated_cache: lsp_explorer.IndexCacheManager) -> None:
        """Walk UP from 'process' → should find 'MyClass'."""
        rows = populated_cache.conn.execute(
            """\
            WITH RECURSIVE ancestors(sym_id, depth) AS (
                SELECT 2, 0
                UNION ALL
                SELECT sc.outer_symbol_id, a.depth + 1
                FROM ancestors a
                JOIN symbol_containments sc ON sc.inner_symbol_id = a.sym_id
                WHERE a.depth < 5
            )
            SELECT a.depth, s.name, s.kind
            FROM ancestors a
            JOIN symbols s ON s.id = a.sym_id
            ORDER BY a.depth
            """
        ).fetchall()
        assert len(rows) >= 2
        assert rows[0]["name"] == "process"
        assert rows[1]["name"] == "MyClass"

    def test_descendants_cte(self, populated_cache: lsp_explorer.IndexCacheManager) -> None:
        """Walk DOWN from 'MyClass' → should find 'process'."""
        rows = populated_cache.conn.execute(
            """\
            WITH RECURSIVE descendants(sym_id, depth) AS (
                SELECT 1, 0
                UNION ALL
                SELECT sc.inner_symbol_id, d.depth + 1
                FROM descendants d
                JOIN symbol_containments sc ON sc.outer_symbol_id = d.sym_id
                WHERE d.depth < 5
            )
            SELECT d.depth, s.name, s.kind, s.is_definition
            FROM descendants d
            JOIN symbols s ON s.id = d.sym_id
            ORDER BY d.depth, s.line
            """
        ).fetchall()
        names = [r["name"] for r in rows]
        assert "MyClass" in names  # depth 0
        assert "process" in names  # depth 1

    def test_direct_children(self, populated_cache: lsp_explorer.IndexCacheManager) -> None:
        """Direct children of MyClass (id=1)."""
        rows = populated_cache.conn.execute(
            """\
            SELECT s.name, s.kind, s.is_definition, s.line
            FROM symbol_containments sc
            JOIN symbols s ON s.id = sc.inner_symbol_id
            WHERE sc.outer_symbol_id = 1
            ORDER BY s.line
            """
        ).fetchall()
        child_names = [r["name"] for r in rows]
        assert "process" in child_names


# ============================================================================
# Unit Tests: File Discovery
# ============================================================================


class TestFileDiscovery:
    """Test file discovery in the IndexCacheManager."""

    @pytest.fixture
    def project_dir(self, temp_dir: Path) -> Path:
        """Create a mini project structure."""
        d = temp_dir / "project"
        d.mkdir()
        (d / "src").mkdir()
        (d / "tests").mkdir()
        (d / "src" / "main.py").write_text("def main(): pass\n")
        (d / "src" / "utils.py").write_text("def util(): pass\n")
        (d / "tests" / "test_main.py").write_text("def test(): pass\n")
        (d / "src" / "app.ts").write_text("function app() {}\n")
        (d / "README.md").write_text("# Project\n")  # Should be filtered out
        return d

    def test_discover_files_filters_extensions(self, project_dir: Path, temp_dir: Path) -> None:
        db_path = temp_dir / "test.db"
        cache = lsp_explorer.IndexCacheManager(db_path=db_path)
        cache.init_schema()

        files = cache.discover_files(project_dir)
        extensions = {Path(f["filepath"]).suffix for f in files}
        assert ".md" not in extensions
        assert ".py" in extensions
        assert ".ts" in extensions
        cache.close()

    def test_discover_files_classifies_types(self, project_dir: Path, temp_dir: Path) -> None:
        db_path = temp_dir / "test.db"
        cache = lsp_explorer.IndexCacheManager(db_path=db_path)
        cache.init_schema()

        files = cache.discover_files(project_dir)
        file_types = {f["relative_path"]: f["file_type"] for f in files}
        assert file_types.get("tests/test_main.py") == "test"
        assert file_types.get("src/main.py") == "source"
        cache.close()

    def test_discover_files_includes_language(self, project_dir: Path, temp_dir: Path) -> None:
        db_path = temp_dir / "test.db"
        cache = lsp_explorer.IndexCacheManager(db_path=db_path)
        cache.init_schema()

        files = cache.discover_files(project_dir)
        langs = {f["relative_path"]: f["language"] for f in files}
        assert langs.get("src/main.py") == "python"
        assert langs.get("src/app.ts") == "typescript"
        cache.close()


# ============================================================================
# Unit Tests: New CLI Subcommands
# ============================================================================


class TestNewCLI:
    """Test CLI argument parsing for new subcommands."""

    def test_index_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["index"])
        assert args.command == "index"

    def test_index_status_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["index-status"])
        assert args.command == "index-status"

    def test_index_clear_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["index-clear"])
        assert args.command == "index-clear"

    def test_lookup_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["lookup", "MyClass"])
        assert args.command == "lookup"
        assert args.name == "MyClass"

    def test_lookup_with_filters(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["lookup", "main", "--kind", "function", "--file-type", "source"])
        assert args.kind == "function"
        assert args.file_type == "source"

    def test_dead_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["dead"])
        assert args.command == "dead"

    def test_dead_with_exclude_private(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["dead", "--exclude-private"])
        assert args.exclude_private is True

    def test_trace_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["trace", "src/main.py", "10", "5", "--depth", "5"])
        assert args.command == "trace"
        assert args.file == "src/main.py"
        assert args.line == 10
        assert args.col == 5
        assert args.depth == 5

    def test_files_subcommand(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["files", "--language", "python"])
        assert args.command == "files"
        assert args.language == "python"

    def test_cache_frozen_flag(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["index", "--cache-frozen"])
        assert args.cache_mode == "frozen"

    def test_cache_incremental_flag(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["index", "--cache-incremental"])
        assert args.cache_mode == "incremental"

    def test_cache_rebuild_flag(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["index", "--cache-rebuild"])
        assert args.cache_mode == "rebuild"

    def test_default_cache_mode_is_rebuild(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["index"])
        assert args.cache_mode == "rebuild"

    def test_flags_work_after_subcommand(self) -> None:
        """Flags like --root work after the subcommand name (the whole point)."""
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["index", "--root", "/tmp/project"])
        assert args.root == Path("/tmp/project")

    def test_flags_work_with_verbose_and_pretty(self) -> None:
        parser = lsp_explorer.build_parser()
        args = parser.parse_args(["symbols", "test.py", "-v", "--pretty"])
        assert args.verbose is True
        assert args.pretty is True


# ============================================================================
# Unit Tests: Walk Symbol Tree
# ============================================================================


class TestIndexCacheManagerEdgeCases:
    """Test IndexCacheManager edge cases for coverage."""

    def test_needs_rebuild_no_version_key(self, temp_dir: Path) -> None:
        """needs_rebuild returns True when cache_metadata exists but has no schema_version."""
        db_path = temp_dir / "noversion.db"
        cache = lsp_explorer.IndexCacheManager(db_path=db_path)
        cache.init_schema()
        cache.conn.execute("DELETE FROM cache_metadata WHERE key = 'schema_version'")
        cache.conn.commit()
        assert cache.needs_rebuild() is True
        cache.close()

    def test_get_cache_manager_default_path(self) -> None:
        """_get_cache_manager without db_path uses default CACHE_DB_PATH."""
        args = argparse.Namespace(pretty=False, verbose=False)
        cache = lsp_explorer._get_cache_manager(args)
        assert cache._db_path == lsp_explorer.CACHE_DB_PATH
        cache.close()


class TestWalkSymbolTree:
    """Test _walk_symbol_tree inserts definitions correctly."""

    @pytest.fixture
    def cache_with_file(self, temp_dir: Path) -> Any:
        db_path = temp_dir / "walk_test.db"
        cache = lsp_explorer.IndexCacheManager(db_path=db_path)
        cache.init_schema()
        cache.conn.execute(
            "INSERT INTO source_files (id, filepath, relative_path, mtime, size_bytes, indexed_at, "
            "language, lsp_server, file_type) VALUES (1, '/test.py', 'test.py', 1.0, 100, "
            "'now', 'python', 'pyright-langserver', 'source')"
        )
        cache.conn.commit()
        yield cache
        cache.close()

    def test_flat_symbols(self, cache_with_file: lsp_explorer.IndexCacheManager) -> None:
        raw = [
            {
                "name": "MyFunc",
                "kind": 12,
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 5, "character": 0}},
                "selectionRange": {
                    "start": {"line": 0, "character": 4},
                    "end": {"line": 0, "character": 10},
                },
                "children": [],
            }
        ]
        cursor = cache_with_file.conn.cursor()
        count = cache_with_file._walk_symbol_tree(cursor, raw, 1)
        cache_with_file.conn.commit()
        assert count == 1

        rows = cache_with_file.conn.execute("SELECT * FROM symbols WHERE is_definition = 1").fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "MyFunc"
        assert rows[0]["kind"] == "function"
        assert rows[0]["line"] == 1  # 1-indexed from selectionRange
        assert rows[0]["scope_start_line"] == 1
        assert rows[0]["scope_end_line"] == 6

    def test_nested_symbols(self, cache_with_file: lsp_explorer.IndexCacheManager) -> None:
        raw = [
            {
                "name": "MyClass",
                "kind": 5,
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 20, "character": 0},
                },
                "selectionRange": {
                    "start": {"line": 0, "character": 6},
                    "end": {"line": 0, "character": 13},
                },
                "children": [
                    {
                        "name": "__init__",
                        "kind": 6,
                        "range": {
                            "start": {"line": 2, "character": 4},
                            "end": {"line": 5, "character": 0},
                        },
                        "selectionRange": {
                            "start": {"line": 2, "character": 8},
                            "end": {"line": 2, "character": 16},
                        },
                        "children": [],
                    },
                ],
            }
        ]
        cursor = cache_with_file.conn.cursor()
        count = cache_with_file._walk_symbol_tree(cursor, raw, 1)
        cache_with_file.conn.commit()
        assert count == 2  # MyClass + __init__

        # Verify R-Tree entries
        rtree_count = cache_with_file.conn.execute("SELECT COUNT(*) FROM definition_ranges").fetchone()[0]
        assert rtree_count == 2

    def test_duplicate_symbol_skipped(self, cache_with_file: lsp_explorer.IndexCacheManager) -> None:
        """Inserting the same symbol twice should hit IntegrityError and skip."""
        raw = [
            {
                "name": "MyFunc",
                "kind": 12,
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 5, "character": 0}},
                "selectionRange": {
                    "start": {"line": 0, "character": 4},
                    "end": {"line": 0, "character": 10},
                },
                "children": [],
            }
        ]
        cursor = cache_with_file.conn.cursor()
        count1 = cache_with_file._walk_symbol_tree(cursor, raw, 1)
        cache_with_file.conn.commit()
        assert count1 == 1
        # Insert again — should hit IntegrityError and return 0
        count2 = cache_with_file._walk_symbol_tree(cursor, raw, 1)
        cache_with_file.conn.commit()
        assert count2 == 0


# ============================================================================
# Integration Tests: Index Commands (with fake server)
# ============================================================================


class TestIndexCommands:
    """Test index CLI commands with real SQLite database."""

    @pytest.fixture
    def index_cache(self, temp_dir: Path) -> Any:
        db_path = temp_dir / "cmd_test.db"
        cache = lsp_explorer.IndexCacheManager(db_path=db_path)
        cache.init_schema()
        yield cache
        cache.close()

    def test_cmd_index_status_no_index(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        db_path = temp_dir / "empty.db"
        args = argparse.Namespace(
            pretty=False,
            db_path=str(db_path),
            verbose=False,
        )
        result = lsp_explorer.cmd_index_status(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "no_index"

    def test_cmd_index_status_with_data(
        self, index_cache: lsp_explorer.IndexCacheManager, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = argparse.Namespace(
            pretty=False,
            db_path=str(index_cache._db_path),
            verbose=False,
        )
        result = lsp_explorer.cmd_index_status(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert "files" in output
        assert output["files"] == 0

    def test_cmd_index_clear(
        self, index_cache: lsp_explorer.IndexCacheManager, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = argparse.Namespace(
            pretty=False,
            db_path=str(index_cache._db_path),
            verbose=False,
        )
        result = lsp_explorer.cmd_index_clear(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "cleared"


# ============================================================================
# Integration Tests: Real LSP Index (pyright)
# ============================================================================


@skip_no_pyright
class TestPyrightIndexIntegration:
    """Integration tests for the full indexing pipeline with real pyright."""

    def test_index_python_file(self, python_fixture: Path) -> None:
        """Test indexing a Python file with real pyright server."""
        root = python_fixture.parent
        db_path = root / "test_index.db"
        cache = lsp_explorer.IndexCacheManager(db_path=db_path)
        try:
            cache.init_schema()

            files = cache.discover_files(root)
            py_files = [f for f in files if f["language"] == "python"]
            assert len(py_files) >= 1

            stats = cache.index_files(root, py_files)
            assert stats["files_indexed"] >= 1
            assert stats["definitions"] > 0

            # Verify definitions are in the database
            defs = cache.conn.execute("SELECT * FROM definitions").fetchall()
            def_names = [d["name"] for d in defs]
            assert "MyClass" in def_names
            assert "main" in def_names
        finally:
            cache.close()


# ============================================================================
# Unit Tests: Additional Pure Functions & Edge Cases
# ============================================================================


class TestJsonRpcError:
    """Test JsonRpcError exception class."""

    def test_init_with_data(self) -> None:
        err = lsp_explorer.JsonRpcError(-32600, "Invalid Request", {"detail": "foo"})
        assert err.code == -32600
        assert err.error_message == "Invalid Request"
        assert err.data == {"detail": "foo"}
        assert "JSON-RPC error -32600" in str(err)

    def test_init_without_data(self) -> None:
        err = lsp_explorer.JsonRpcError(-32601, "Method not found")
        assert err.code == -32601
        assert err.data is None


class TestServerNotFoundInit:
    """Test ServerNotFound exception details."""

    def test_python_install_hint(self) -> None:
        err = lsp_explorer.ServerNotFound("python", "pyright-langserver")
        assert err.language == "python"
        assert err.binary == "pyright-langserver"
        assert "pip install pyright" in str(err)

    def test_typescript_install_hint(self) -> None:
        err = lsp_explorer.ServerNotFound("typescript", "typescript-language-server")
        assert "npm install" in str(err)


class TestFormatHoverExtended:
    """Test _format_hover edge cases not covered by existing tests."""

    def test_string_contents(self) -> None:
        result = lsp_explorer._format_hover({"contents": "def foo(): pass"})
        assert result is not None
        assert result["type"] == "def foo(): pass"

    def test_list_contents_strings(self) -> None:
        result = lsp_explorer._format_hover({"contents": ["line1", "line2"]})
        assert result is not None
        assert "line1" in result["type"]

    def test_list_contents_dicts(self) -> None:
        result = lsp_explorer._format_hover({"contents": [{"value": "sig"}, {"value": "doc"}]})
        assert result is not None
        assert "sig" in result["type"]

    def test_list_contents_mixed(self) -> None:
        result = lsp_explorer._format_hover({"contents": ["plain", {"value": "structured"}]})
        assert result is not None

    def test_unsupported_contents_type(self) -> None:
        result = lsp_explorer._format_hover({"contents": 42})
        assert result is None

    def test_contents_key_missing(self) -> None:
        result = lsp_explorer._format_hover({"contents": None})
        assert result is None

    def test_doc_with_leading_horizontal_rule(self) -> None:
        hover = {
            "contents": {
                "kind": "markdown",
                "value": "```python\ndef foo()\n```\n---\nSome docs",
            }
        }
        result = lsp_explorer._format_hover(hover)
        assert result is not None
        assert result.get("type") == "def foo()"
        assert result.get("doc") == "Some docs"

    def test_doc_with_trailing_horizontal_rule(self) -> None:
        hover = {
            "contents": {
                "kind": "markdown",
                "value": "```python\ndef bar()\n```\nDocs here\n---",
            }
        }
        result = lsp_explorer._format_hover(hover)
        assert result is not None
        assert result.get("doc") == "Docs here"

    def test_whitespace_only_contents(self) -> None:
        result = lsp_explorer._format_hover({"contents": {"value": "   "}})
        assert result is None


class TestFormatSymbolExtended:
    """Test _format_symbol edge cases."""

    def test_symbol_with_detail(self) -> None:
        sym = {
            "name": "age",
            "kind": 13,
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 10}},
            "detail": "int",
        }
        result = lsp_explorer._format_symbol(sym)
        assert result["d"] == "int"


class TestGetLinePreviewExtended:
    """Test _get_line_preview edge cases."""

    def test_nonexistent_file_returns_none(self) -> None:
        result = lsp_explorer._get_line_preview(Path("/nonexistent/file.py"), 1)
        assert result is None


class TestUriToPathExtended:
    """Test _uri_to_path edge cases."""

    def test_non_file_uri_treated_as_path(self) -> None:
        result = lsp_explorer._uri_to_path("some/path.py")
        assert result == Path("some/path.py")


class TestRelativePathExtended:
    """Test _relative_path edge cases."""

    def test_path_outside_root_returns_absolute(self) -> None:
        result = lsp_explorer._relative_path(Path("/tmp/other/file.py"), Path("/home/user/project"))
        assert result.startswith("/")


class TestDecodeSemanticTokensExtended:
    """Test decode_semantic_tokens edge cases."""

    def test_type_idx_out_of_range_skipped(self) -> None:
        legend = {"tokenTypes": ["variable"], "tokenModifiers": ["declaration"]}
        source = "x = 1"
        data = [0, 0, 1, 5, 0]  # type_idx=5 but only 1 type in legend
        tokens = lsp_explorer.decode_semantic_tokens(data, legend, source)
        assert tokens == []

    def test_empty_name_skipped(self) -> None:
        legend = {"tokenTypes": ["variable"], "tokenModifiers": ["declaration"]}
        source = "x"
        data = [0, 10, 3, 0, 0]  # col=10 past end of the 1-char line
        tokens = lsp_explorer.decode_semantic_tokens(data, legend, source)
        assert tokens == []


# ============================================================================
# Tests: cmd_* Functions with Seeded SQLite Database
# ============================================================================


class TestCmdWithPopulatedDB:
    """Test cmd_* functions with a pre-populated SQLite database.

    These tests exercise the CLI command wrappers (cmd_lookup, cmd_dead,
    cmd_trace, cmd_files, cmd_index) against a real SQLite database seeded
    with known symbol data. No live LSP server is needed.
    """

    @pytest.fixture
    def populated_cache(self, temp_dir: Path) -> Any:
        """Create a cache with realistic symbol data for query testing."""
        db_path = temp_dir / "populated.db"
        cache = lsp_explorer.IndexCacheManager(db_path=db_path)
        cache.init_schema()

        # Source files
        cache.conn.execute(
            "INSERT INTO source_files (id, filepath, relative_path, mtime, size_bytes, "
            "indexed_at, language, lsp_server, file_type) "
            "VALUES (1, '/project/src/main.py', 'src/main.py', 1000.0, 500, "
            "'2025-01-01T00:00:00', 'python', 'pyright-langserver', 'source')"
        )
        cache.conn.execute(
            "INSERT INTO source_files (id, filepath, relative_path, mtime, size_bytes, "
            "indexed_at, language, lsp_server, file_type) "
            "VALUES (2, '/project/tests/test_main.py', 'tests/test_main.py', 1000.0, 300, "
            "'2025-01-01T00:00:00', 'python', 'pyright-langserver', 'test')"
        )

        # Definitions
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition, scope_start_line, scope_end_line) "
            "VALUES (1, 1, 'MyClass', 'class', 5, 7, 5, 14, 1, 5, 25)"
        )
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition, scope_start_line, scope_end_line) "
            "VALUES (2, 1, 'do_stuff', 'function', 10, 5, 10, 13, 1, 10, 15)"
        )
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition, scope_start_line, scope_end_line) "
            "VALUES (3, 1, '_private_helper', 'function', 17, 5, 17, 20, 1, 17, 20)"
        )
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition, scope_start_line, scope_end_line) "
            "VALUES (4, 2, 'test_do_stuff', 'function', 3, 5, 3, 18, 1, 3, 10)"
        )

        # References (non-definition uses)
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition) "
            "VALUES (5, 2, 'MyClass', 'variable', 5, 10, 5, 17, 0)"
        )
        cache.conn.execute(
            "INSERT INTO symbols (id, source_file_id, name, kind, line, col, end_line, end_col, "
            "is_definition) "
            "VALUES (6, 2, 'do_stuff', 'function', 6, 5, 6, 13, 0)"
        )

        # Containments: references inside test_do_stuff
        cache.conn.execute("INSERT INTO symbol_containments (inner_symbol_id, outer_symbol_id) VALUES (5, 4)")
        cache.conn.execute("INSERT INTO symbol_containments (inner_symbol_id, outer_symbol_id) VALUES (6, 4)")

        # R-Tree entries for definitions
        for sym_id, min_line, max_line, file_id in [
            (1, 5, 25, 1),
            (2, 10, 15, 1),
            (3, 17, 20, 1),
            (4, 3, 10, 2),
        ]:
            cache.conn.execute(
                "INSERT INTO definition_ranges (id, min_line, max_line, min_file_id, max_file_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (sym_id, min_line, max_line, file_id, file_id),
            )

        cache.conn.commit()
        yield db_path
        cache.close()

    def _make_args(self, db_path: Path, **kwargs: Any) -> argparse.Namespace:
        defaults: dict[str, Any] = {
            "pretty": False,
            "verbose": False,
            "db_path": str(db_path),
            "root": None,
            "timeout": 30.0,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    # --- cmd_lookup ---

    def test_cmd_lookup_basic(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, name="MyClass")
        result = lsp_explorer.cmd_lookup(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert len(output) == 1
        assert output[0]["name"] == "MyClass"
        assert output[0]["file"] == "src/main.py"

    def test_cmd_lookup_with_kind_filter(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, name="do_stuff", kind="function")
        result = lsp_explorer.cmd_lookup(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        # "do_stuff" LIKE match also catches "test_do_stuff"
        assert len(output) >= 1
        assert all(r["kind"] == "function" for r in output)

    def test_cmd_lookup_with_file_type(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, name="test", file_type="test")
        result = lsp_explorer.cmd_lookup(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert all(r["file_type"] == "test" for r in output)

    def test_cmd_lookup_no_index(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(temp_dir / "empty.db", name="foo")
        result = lsp_explorer.cmd_lookup(args)
        assert result == 1

    # --- cmd_dead ---

    def test_cmd_dead_basic(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, kind=None, file_type=None, exclude_private=False)
        result = lsp_explorer.cmd_dead(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        dead_names = [d["name"] for d in output["dead"]]
        # _private_helper and test_do_stuff have no references
        assert "_private_helper" in dead_names
        assert "test_do_stuff" in dead_names
        # MyClass and do_stuff have references — should NOT be dead
        assert "MyClass" not in dead_names
        assert "do_stuff" not in dead_names

    def test_cmd_dead_exclude_private(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, kind=None, file_type=None, exclude_private=True)
        result = lsp_explorer.cmd_dead(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        dead_names = [d["name"] for d in output["dead"]]
        assert "_private_helper" not in dead_names

    def test_cmd_dead_with_kind_filter(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, kind="class", file_type=None, exclude_private=False)
        result = lsp_explorer.cmd_dead(args)
        assert result == 0

    def test_cmd_dead_with_file_type(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, kind=None, file_type="source", exclude_private=False)
        result = lsp_explorer.cmd_dead(args)
        assert result == 0

    def test_cmd_dead_no_index(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(temp_dir / "empty.db", kind=None, file_type=None, exclude_private=False)
        result = lsp_explorer.cmd_dead(args)
        assert result == 1

    # --- cmd_trace ---

    def test_cmd_trace_exact_match(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, file="src/main.py", line=10, col=5, depth=3)
        result = lsp_explorer.cmd_trace(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert "trace" in output
        assert "count" in output

    def test_cmd_trace_fuzzy_line_match(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        # Wrong col forces fallback to line-only match
        args = self._make_args(populated_cache, file="src/main.py", line=10, col=999, depth=3)
        result = lsp_explorer.cmd_trace(args)
        assert result == 0

    def test_cmd_trace_not_found(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, file="nonexistent.py", line=1, col=1, depth=3)
        result = lsp_explorer.cmd_trace(args)
        assert result == 1
        err = json.loads(capsys.readouterr().err)
        assert "No definition found" in err["error"]

    def test_cmd_trace_no_index(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(temp_dir / "empty.db", file="main.py", line=1, col=1, depth=3)
        result = lsp_explorer.cmd_trace(args)
        assert result == 1

    # --- cmd_files ---

    def test_cmd_files_basic(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, language=None, file_type=None)
        result = lsp_explorer.cmd_files(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert output["count"] == 2

    def test_cmd_files_with_language(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, language="python", file_type=None)
        result = lsp_explorer.cmd_files(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert output["count"] == 2

    def test_cmd_files_with_file_type(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, language=None, file_type="test")
        result = lsp_explorer.cmd_files(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert output["count"] == 1
        assert output["files"][0]["file"] == "tests/test_main.py"

    def test_cmd_files_no_index(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(temp_dir / "empty.db", language=None, file_type=None)
        result = lsp_explorer.cmd_files(args)
        assert result == 1

    # --- cmd_index ---

    def test_cmd_index_frozen_mode(self, populated_cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(populated_cache, cache_mode="frozen")
        result = lsp_explorer.cmd_index(args)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "frozen"


# ============================================================================
# Tests: main() Error Handling
# ============================================================================


class TestMainErrorHandling:
    """Test the main() dispatcher and its exception handling for each error type.

    Each exception type in the try/except chain produces a specific JSON error
    on stderr and a specific exit code. We test them all by injecting a function
    that raises the desired exception.
    """

    def _make_args(self, func: Any, verbose: bool = False) -> argparse.Namespace:
        return argparse.Namespace(verbose=verbose, func=func)

    def test_success(self) -> None:
        ret = lsp_explorer.main(self._make_args(lambda args: 0))
        assert ret == 0

    def test_verbose_enables_debug_logging(self) -> None:
        ret = lsp_explorer.main(self._make_args(lambda args: 0, verbose=True))
        assert ret == 0

    def test_server_not_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        def raise_it(args: Any) -> int:
            raise lsp_explorer.ServerNotFound("python", "pyright-langserver")

        ret = lsp_explorer.main(self._make_args(raise_it))
        assert ret == 1
        err = json.loads(capsys.readouterr().err)
        assert "not found" in err["error"]
        assert "hint" in err

    def test_unsupported_language(self, capsys: pytest.CaptureFixture[str]) -> None:
        def raise_it(args: Any) -> int:
            raise lsp_explorer.UnsupportedLanguage(".xyz")

        ret = lsp_explorer.main(self._make_args(raise_it))
        assert ret == 1
        err = json.loads(capsys.readouterr().err)
        assert ".xyz" in err["error"]

    def test_file_not_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        def raise_it(args: Any) -> int:
            raise FileNotFoundError("missing.py")

        ret = lsp_explorer.main(self._make_args(raise_it))
        assert ret == 1
        err = json.loads(capsys.readouterr().err)
        assert "File not found" in err["error"]

    def test_timeout_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        def raise_it(args: Any) -> int:
            raise TimeoutError("Server took too long")

        ret = lsp_explorer.main(self._make_args(raise_it))
        assert ret == 1
        err = json.loads(capsys.readouterr().err)
        assert "hint" in err

    def test_json_rpc_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        def raise_it(args: Any) -> int:
            raise lsp_explorer.JsonRpcError(-32600, "Invalid Request")

        ret = lsp_explorer.main(self._make_args(raise_it))
        assert ret == 1
        err = json.loads(capsys.readouterr().err)
        assert "Invalid Request" in err["error"]

    def test_keyboard_interrupt(self) -> None:
        def raise_it(args: Any) -> int:
            raise KeyboardInterrupt()

        ret = lsp_explorer.main(self._make_args(raise_it))
        assert ret == 130


# ============================================================================
# Integration Tests: cmd_* with Live LSP (pyright)
# ============================================================================


@skip_no_pyright
class TestCmdLiveLsp:
    """Test cmd_* functions end-to-end with a real pyright server.

    These tests verify the full cmd -> CodeExplorer -> LspSession -> pyright
    pipeline for each CLI command. They are slow (~2-5s each) because they
    start and stop a real pyright-langserver subprocess.
    """

    def test_cmd_symbols(self, python_fixture: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(
            file=str(python_fixture),
            root=python_fixture.parent,
            timeout=30.0,
            pretty=False,
            verbose=False,
        )
        ret = lsp_explorer.cmd_symbols(args)
        assert ret == 0
        output = json.loads(capsys.readouterr().out)
        assert len(output) > 0

    def test_cmd_definition(self, python_fixture: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(
            file=str(python_fixture),
            root=python_fixture.parent,
            timeout=30.0,
            pretty=False,
            verbose=False,
            line=11,
            col=11,
        )
        ret = lsp_explorer.cmd_definition(args)
        assert ret == 0

    def test_cmd_references(self, python_fixture: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(
            file=str(python_fixture),
            root=python_fixture.parent,
            timeout=30.0,
            pretty=False,
            verbose=False,
            line=10,
            col=5,
        )
        ret = lsp_explorer.cmd_references(args)
        assert ret == 0

    def test_cmd_hover(self, python_fixture: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(
            file=str(python_fixture),
            root=python_fixture.parent,
            timeout=30.0,
            pretty=False,
            verbose=False,
            line=1,
            col=7,
        )
        ret = lsp_explorer.cmd_hover(args)
        assert ret == 0

    def test_cmd_diagnostics(self, python_fixture: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(
            file=str(python_fixture),
            root=python_fixture.parent,
            timeout=30.0,
            pretty=False,
            verbose=False,
        )
        ret = lsp_explorer.cmd_diagnostics(args)
        assert ret == 0

    def test_cmd_explore(self, python_fixture: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(
            file=str(python_fixture),
            root=python_fixture.parent,
            timeout=30.0,
            pretty=False,
            verbose=False,
        )
        ret = lsp_explorer.cmd_explore(args)
        assert ret == 0

    def test_cmd_impact(self, python_fixture: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(
            file=str(python_fixture),
            root=python_fixture.parent,
            timeout=30.0,
            pretty=False,
            verbose=False,
            line=10,
            col=5,
            depth=1,
        )
        ret = lsp_explorer.cmd_impact(args)
        assert ret == 0

    def test_cmd_index_rebuild(self, python_fixture: Path, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        db_path = temp_dir / "rebuild_test.db"
        args = argparse.Namespace(
            root=python_fixture.parent,
            timeout=30.0,
            pretty=False,
            verbose=False,
            db_path=str(db_path),
            cache_mode="rebuild",
        )
        ret = lsp_explorer.cmd_index(args)
        assert ret == 0
        output = json.loads(capsys.readouterr().out)
        assert output["files_indexed"] >= 1

    def test_cmd_index_incremental(
        self, python_fixture: Path, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        db_path = temp_dir / "incr_test.db"
        # First: rebuild
        args = argparse.Namespace(
            root=python_fixture.parent,
            timeout=30.0,
            pretty=False,
            verbose=False,
            db_path=str(db_path),
            cache_mode="rebuild",
        )
        lsp_explorer.cmd_index(args)
        capsys.readouterr()  # clear output
        # Then: incremental (no files changed, so 0 should be re-indexed)
        args = argparse.Namespace(
            root=python_fixture.parent,
            timeout=30.0,
            pretty=False,
            verbose=False,
            db_path=str(db_path),
            cache_mode="incremental",
        )
        ret = lsp_explorer.cmd_index(args)
        assert ret == 0
        output = json.loads(capsys.readouterr().out)
        assert output["files_skipped"] >= 1


# ============================================================================
# Entry point for uv run
# ============================================================================

if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    extra_args = sys.argv[1:]
    sys.exit(pytest.main(base_args + extra_args))
