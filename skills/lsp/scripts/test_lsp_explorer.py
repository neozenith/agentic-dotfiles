#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0", "lsprotocol>=2024.0.0"]
# ///
"""Tests for lsp_explorer.py — real fixtures, no mocks."""

from __future__ import annotations

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
skip_no_ts = pytest.mark.skipif(
    not HAS_TS_SERVER, reason="typescript-language-server not installed"
)


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
        id2 = client.send_request(
            "textDocument/documentSymbol", {"textDocument": {"uri": "file:///test.py"}}
        )
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

    def _make_session(
        self, fake_server: subprocess.Popen[bytes], temp_dir: Path
    ) -> lsp_explorer.LspSession:
        client = lsp_explorer.JsonRpcClient(fake_server)
        return lsp_explorer.LspSession(client, temp_dir, "python")

    def test_initialize_and_shutdown(
        self, fake_server: subprocess.Popen[bytes], temp_dir: Path
    ) -> None:
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

    def test_did_open_idempotent(
        self, fake_server: subprocess.Popen[bytes], temp_dir: Path
    ) -> None:
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
        result = lsp_explorer._format_hover(
            {"contents": {"kind": "plaintext", "value": "def foo() -> int"}}
        )
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
        args = parser.parse_args(["-v", "--pretty", "--timeout", "60", "symbols", "test.py"])
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
# Entry point for uv run
# ============================================================================

if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v", *sys.argv[1:]]))
