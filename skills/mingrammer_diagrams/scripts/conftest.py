"""Standalone test config for the mingrammer_diagrams skill scripts.

Reloads the module under test *after* pytest-cov's tracer starts, so module-level
statements (imports, constants) are counted toward coverage. See
``.claude/rules/claude_skills/scripts.md`` → "conftest.py for Coverage Reload".
"""

from __future__ import annotations

import importlib

import pytest

import _update_examples_readme


@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    importlib.reload(_update_examples_readme)
