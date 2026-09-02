"""Standalone test config for the PEP-723 hook scripts.

The module under test is imported before pytest-cov starts tracing, so its
module-level statements would report as uncovered. Reloading inside a
session-scoped fixture re-executes them under an active tracer.
"""

from __future__ import annotations

import importlib

import pytest

import tool_coach


@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    importlib.reload(tool_coach)
