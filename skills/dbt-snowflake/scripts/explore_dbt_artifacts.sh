#!/usr/bin/env bash
# Wrapper script to run explore_dbt_artifacts.py with uv
# This is needed because Claude Code skills cannot directly invoke uv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/explore_dbt_artifacts.py"

exec uv run "${PYTHON_SCRIPT}" "$@"
