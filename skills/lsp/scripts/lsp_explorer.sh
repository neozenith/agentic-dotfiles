#!/usr/bin/env bash
# Wrapper script for lsp_explorer.py
# Claude Code skills cannot directly invoke `uv`, so this wrapper is needed.
#
# Usage: lsp_explorer.sh [command] [args...]
# Example: lsp_explorer.sh symbols src/main.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --with "lsprotocol>=2024.0.0" "$SCRIPT_DIR/lsp_explorer.py" "$@"
