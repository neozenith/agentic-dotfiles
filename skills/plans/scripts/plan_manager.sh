#!/usr/bin/env bash
# Wrapper script for plan_manager.py
# Claude Code skills cannot directly invoke `uv`, so this wrapper is needed.
#
# Usage: plan_manager.sh [command] [args...]
# Example: plan_manager.sh analyze plan.md

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run "$SCRIPT_DIR/plan_manager.py" "$@"
