"""Standalone test config for PEP-723 skill scripts.

The PEP-723 __main__ entry imports the module under test before pytest-cov's
tracer starts; reloading inside a session fixture re-executes module-level code
under active tracing (see .claude/rules/claude_skills/scripts.md).
"""

from __future__ import annotations

import importlib

import pgsm
import pytest
import rollout
import trajectory


@pytest.fixture(autouse=True, scope="session")
def _reload_for_coverage() -> None:
    importlib.reload(pgsm)
    importlib.reload(trajectory)
    importlib.reload(rollout)
