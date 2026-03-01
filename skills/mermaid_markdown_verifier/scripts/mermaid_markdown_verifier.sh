#!/usr/bin/env bash
# Wrapper script for mermaid_markdown_verifier.py
# Claude Code skills cannot directly invoke `uv`, so this wrapper is needed.
#
# Usage: mermaid_markdown_verifier.sh [paths...] [-v] [-q]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run "$SCRIPT_DIR/mermaid_markdown_verifier.py" "$@"
