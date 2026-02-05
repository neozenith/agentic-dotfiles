#!/usr/bin/env bash
# Wrapper script for introspect_sessions.py
# Claude Code skills cannot directly invoke `uv`, so this wrapper is needed.
#
# Usage: introspect_sessions.sh [command] [args...]
# Example: introspect_sessions.sh summary SESSION_ID

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run "$SCRIPT_DIR/introspect_sessions.py" "$@"
