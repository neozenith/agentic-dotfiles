#!/usr/bin/env bash
# Wrapper script for introspect_sessions.py
# Claude Code skills cannot directly invoke `uv`, so this wrapper is needed.
#
# Usage: introspect_sessions.sh [command] [args...]
# Example: introspect_sessions.sh summary SESSION_ID
#
# When reflect --engine is used, ML dependencies (transformers, torch) are
# injected via --with flags so they're only loaded when needed.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if reflect --engine is being used (needs ML deps)
ML_DEPS=""
for arg in "$@"; do
    if [ "$arg" = "--engine" ]; then
        ML_DEPS="yes"
        break
    fi
done

if [ -n "$ML_DEPS" ]; then
    exec uv run \
        --with "transformers>=4.40.0,<5.0.0" \
        --with "torch>=2.2.0" \
        --with "sentencepiece>=0.2.0" \
        "$SCRIPT_DIR/introspect_sessions.py" "$@"
else
    exec uv run "$SCRIPT_DIR/introspect_sessions.py" "$@"
fi
