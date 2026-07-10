"""Shared test configuration for richdocs skill scripts.

When tests run via __main__ (PEP-723 entry point), modules under test are
imported before pytest.main() starts coverage tracing. This conftest reloads
all modules after coverage activates so module-level statements are traced.
"""

from __future__ import annotations

import importlib

import md2html
import pytest
import serve
import stencil


@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    """Reload modules under test so pytest-cov captures module-level code."""
    importlib.reload(serve)
    importlib.reload(stencil)
    importlib.reload(md2html)
