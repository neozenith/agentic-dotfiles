"""Shared test configuration for mermaidjs_diagrams skill scripts.

When tests run via __main__ (PEP-723 entry point), modules under test are
imported before pytest.main() starts coverage tracing. This conftest reloads
all modules after coverage activates so module-level statements are traced.
"""

from __future__ import annotations

import importlib

import _update_examples_readme
import mermaid_complexity
import pytest


@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    """Reload modules under test so pytest-cov captures module-level code."""
    importlib.reload(mermaid_complexity)
    importlib.reload(_update_examples_readme)
