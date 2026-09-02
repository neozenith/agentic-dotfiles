"""Eval: does the discovery skill produce a grounded Current/Desired State document?

The fixture is a small but real codebase (``legacy_pipeline``: a nightly CSV -> HTML batch
job with documented pain). The agent must run the skill's whole loop -- internal research
over that code, external research, synthesis -- and leave behind the one artifact the
skill exists for: a DISCOVERY.md whose two state sections are drawn through the same
lenses with shared node ids, and whose claims trace to ``file:line`` citations or URLs.

This is also the reference case for a skill that spawns research subagents, so the ledger
is asserted to show that the delegation actually happened.

## Why this case has no golden

Discovery output is research: which lenses, which sources, which claims. Two correct
DISCOVERY.md files over this fixture share almost no text (ADR 0046). What is checkable is
the *contract* the skill declares in its own "Done when" line, so that is what this grades,
clause by clause.
"""

from __future__ import annotations

import re

from pytest_xharness_eval import CaseOutput, evalcase
from pytest_xharness_eval.verify import (
    check_files_written,
    check_no_files_added,
    check_rollout,
    check_skill_was_loaded,
    check_subagents_spawned,
    facets,
)

SKILL = "discovery"
FIXTURE = "legacy_pipeline"  # evals/fixtures/legacy_pipeline/
TARGET = "DISCOVERY.md"

# The skill's own `argument-hint` is "<path/to/DISCOVERY.md | path/to/folder/> [one-line
# initiative brief]", so this task is exactly the two arguments it asks for and nothing
# else: `/discovery DISCOVERY.md replace the ...` is what a human types (ADR 0044).
#
# The trailing sentence is not instruction to the skill -- it is sandbox tolerance. This
# workspace has no browser and no mmdc, and the skill's own fallbacks for both are what
# should fire. Without it the cell grades "is a browser installed", which is not a
# property of the skill.
TASK = (
    "DISCOVERY.md -- replace the in-memory nightly orders batch (pipeline/) with a "
    "streaming, fault-tolerant, observable pipeline. Use exactly two lenses and keep the "
    "external research brief. If no browser or fetch tool is available, or mmdc is "
    "missing, take the skill's documented fallback rather than stopping."
)

CITATION = re.compile(r"[\w/]+\.(?:py|md):\d+")


def _sections(doc: str) -> dict[str, str]:
    """Map ``## Heading`` -> its body, up to the next ``##``."""
    parts = re.split(r"^##\s+(.+?)\s*$", doc, flags=re.MULTILINE)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def _named(sections: dict[str, str], prefix: str) -> str | None:
    return next((body for name, body in sections.items() if name.lower().startswith(prefix)), None)


def check_the_two_states_are_paired(output: CaseOutput) -> None:
    """Both sections exist, carry the same number of lens diagrams, and share node ids.

    Coarse to fine. The shared-ids clause is the one that matters: without it the skill has
    produced two unrelated diagrams rather than a before and an after, and a reader cannot
    read the delta -- which is the entire purpose of the document.
    """
    doc = output.read(TARGET)
    sections = _sections(doc)
    current = _named(sections, "current state")
    desired = _named(sections, "desired state")
    assert current is not None, f"no `## Current State` section (sections: {sorted(sections)})"
    assert desired is not None, f"no `## Desired State` section (sections: {sorted(sections)})"

    n_current, n_desired = facets.fence_count(current), facets.fence_count(desired)
    assert 1 <= n_current <= 3, f"Current State has {n_current} lens diagrams; the skill draws 2-3 (1 accepted)"
    assert n_current == n_desired, (
        f"lens mismatch: {n_current} Current vs {n_desired} Desired diagrams. "
        "The pairs must be drawn through the same lenses or they cannot be compared."
    )

    shared = facets.node_ids(current) & facets.node_ids(desired)
    assert shared, (
        "no node id appears in both a Current and a Desired diagram, so the pair cannot be "
        f"read as a before/after. Current: {sorted(facets.node_ids(current))[:10]}; "
        f"Desired: {sorted(facets.node_ids(desired))[:10]}"
    )


def check_the_claims_are_grounded(output: CaseOutput) -> None:
    """Current State cites the fixture's code; Desired State points at external sources."""
    doc = output.read(TARGET)
    sections = _sections(doc)
    current = _named(sections, "current state") or ""
    desired = _named(sections, "desired state") or ""
    assert CITATION.search(current), (
        "Current State carries no file:line citation into the fixture codebase; the skill "
        "requires every factual claim to trace to one"
    )
    assert "http://" in desired or "https://" in desired or "LINK_NOT_VERIFIED" in doc, (
        "Desired State names no external source and carries no unverified-link marker; it "
        "is meant to be grounded in verified external research, not invented"
    )


@evalcase(task=TASK, skill=SKILL, fixture=FIXTURE)
def eval_discovery_document(output: CaseOutput) -> None:
    """Evidence, then delegation, then the document's contract clause by clause."""
    check_rollout(output)
    check_files_written(output, TARGET)
    # DISCOVERY.md is the artifact; `.playwright-cli/` is the skill's own browser tool
    # leaving timestamped page and console dumps behind while it does external research.
    # Both are expected side effects of following the skill -- anything else is not.
    check_no_files_added(output, allow=[TARGET, ".playwright-cli/*"])
    # Not SKILL.md: a native invocation injects it, so it never appears as a read
    # (ADR 0044). These two are what SKILL.md sends the agent to -- the lens menu it must
    # pick from and the shape the document must take -- so reaching them is the evidence
    # that the skill's method was followed rather than improvised.
    check_skill_was_loaded(output, "resources/mermaidjs-diagrams.md", "resources/discovery-template.md")
    # Step 2 of the skill is parallel research subagents. Read off the captured
    # transcripts rather than a tool name, so it means the same thing in both dialects.
    check_subagents_spawned(output, at_least=2)
    check_the_two_states_are_paired(output)
    check_the_claims_are_grounded(output)
