"""Standalone test config for the art-edit skill scripts.

Reloads the module under test *after* pytest-cov's tracer starts, so module-level
statements are counted toward coverage. See
``.claude/rules/claude_skills/scripts.md`` → "conftest.py for Coverage Reload".
"""

from __future__ import annotations

import importlib

import pytest

import art_edit


@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    importlib.reload(art_edit)
