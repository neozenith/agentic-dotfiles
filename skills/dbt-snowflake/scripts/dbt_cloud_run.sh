#!/usr/bin/env bash
# Wrapper script to run dbt_cloud_run.py with uv
# This is needed because Claude Code skills cannot directly invoke uv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/dbt_cloud_run.py"

exec uv run "${PYTHON_SCRIPT}" "$@"
