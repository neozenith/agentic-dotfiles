"""Eval: does a discovery refresh stay inside the sections the skill owns?

The fixture (``staged_discovery``) already holds a DISCOVERY.md whose two state sections
are marked stale and whose ``## Gap Backlog`` section belongs to a downstream planning
workflow. The skill's contract is explicit: refresh only Current State and Desired State,
preserve every other section verbatim.

This case grades exactly that boundary. It is the highest-value assertion in the suite,
because ownership is the rule that erodes *silently*: a helpful agent reformats the
backlog, or a rewrite drops the checksum comment, and nobody reviewing a diff notices.
A character-for-character comparison is what turns that erosion into a red cell.
"""

from __future__ import annotations

from pytest_xharness_eval import CaseOutput, evalcase
from pytest_xharness_eval.verify import (
    check_file_unchanged,
    check_files_written,
    check_no_files_added,
    check_rollout,
    check_skill_was_loaded,
    facets,
)

SKILL = "discovery"
FIXTURE = "staged_discovery"  # evals/fixtures/staged_discovery/
TARGET = "DISCOVERY.md"

# The same two arguments the skill's `argument-hint` asks for; "refresh it" is the whole
# difference from the sibling case. The task does not tell the skill which sections it
# owns -- that is the rule under test, and a task that restated it would be grading the
# task rather than the skill (ADR 0044).
TASK = (
    "DISCOVERY.md -- refresh it. Initiative: replace the in-memory nightly orders batch "
    "(pipeline/) with a streaming, fault-tolerant, observable pipeline. Use exactly two "
    "lenses and keep the external research brief. If no browser or fetch tool is "
    "available, or mmdc is missing, take the skill's documented fallback rather than "
    "stopping."
)

# The planner-owned block, verbatim from the fixture. It is inlined rather than read back
# from the fixture directory so that editing the fixture and forgetting this case cannot
# quietly weaken the check into a comparison of the file with itself.
PRESERVED = """## Gap Backlog (owned by the planning workflow — do not edit)

- [ ] GAP-1: spike a streaming CSV reader behind a feature flag
- [ ] GAP-2: quarantine malformed rows instead of aborting the batch
- [ ] GAP-3: emit per-stage timing metrics

<!-- planner-checksum: 7f3a2b -->"""


def check_the_refresh_happened(output: CaseOutput) -> None:
    """The stale markers are gone and both state sections now carry diagrams.

    Without this the ownership check below passes trivially: an agent that edited nothing
    at all preserves the planner's section perfectly.
    """
    doc = output.read(TARGET)
    assert "refresh me" not in doc, "the stale placeholders are still in place -- no refresh happened"
    fences = facets.fence_count(doc)
    assert fences >= 2, f"a refreshed discovery carries at least one diagram per state section, found {fences}"


@evalcase(task=TASK, skill=SKILL, fixture=FIXTURE)
def eval_discovery_refresh(output: CaseOutput) -> None:
    """Evidence, then the refresh itself, then the ownership boundary."""
    check_rollout(output)
    check_files_written(output, TARGET)
    # The target already exists here, so it is an edit rather than an addition; the
    # `.playwright-cli/` dumps are the skill's own research tool (see the sibling case).
    check_no_files_added(output, allow=[".playwright-cli/*"])
    # Not SKILL.md: a native invocation injects it, so it never appears as a read
    # (ADR 0044). These two are what SKILL.md sends the agent to -- the lens menu it must
    # pick from and the shape the document must take -- so reaching them is the evidence
    # that the skill's method was followed rather than improvised.
    check_skill_was_loaded(output, "resources/mermaidjs-diagrams.md", "resources/discovery-template.md")
    check_the_refresh_happened(output)
    # The skill's hardest rule: "this skill never edits a section it does not author."
    check_file_unchanged(output, TARGET, PRESERVED)
