"""Reload the modules under test after coverage tracing starts.

A PEP-723 test file imports its target before ``pytest.main()`` activates
coverage, so module-level statements (imports, constants, decorators) are
already executed and show as uncovered. Reloading here re-executes them under
the tracer.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture(scope="session", autouse=True)
def _reload_for_coverage() -> None:
    import okf_render

    importlib.reload(okf_render)
