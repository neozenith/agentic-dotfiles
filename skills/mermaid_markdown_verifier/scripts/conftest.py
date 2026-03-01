"""Standalone test configuration for PEP-723 skill scripts.

When tests run via __main__ (PEP-723 entry point), the module under test
is imported before pytest.main() starts coverage tracing. This conftest
reloads it after coverage activates so module-level statements are traced.
"""

from __future__ import annotations

import importlib

import mermaid_markdown_verifier as mod
import pytest


@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    """Reload module under test so pytest-cov captures module-level code."""
    importlib.reload(mod)
