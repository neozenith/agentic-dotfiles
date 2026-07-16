"""Standalone test config for the PEP-723 skill scripts.

The modules under test are imported before pytest.main() starts coverage tracing,
so their module-level statements run untraced and report as missed. Reloading them
inside a session-scoped fixture re-executes every top-level statement while the
tracer is active.
"""

from __future__ import annotations

import importlib

import pytest

import prose_check
import scaffold_deck
import slide_durations
import tier_progress


@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    importlib.reload(tier_progress)
    importlib.reload(slide_durations)
    importlib.reload(prose_check)
    importlib.reload(scaffold_deck)
