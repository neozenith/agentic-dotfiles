"""Eval: does a discovery refresh stay inside the sections the skill owns?

The fixture (`staged_discovery`) already holds a DISCOVERY.md whose two state
sections are marked stale and whose `## Gap Backlog` section belongs to a downstream
planning workflow. The skill's contract is explicit: refresh only Current State and
Desired State, preserve every other section verbatim. This case grades exactly that
boundary - the refresh happened, and the planner's section (checksum comment
included) survived character for character.
"""

import re
from pathlib import Path

from pytest_xharness_eval import RunResult, evalcase

SKILL = "discovery"
FIXTURE = "staged_discovery"  # evals/fixtures/staged_discovery/

PROMPT = (
    "Use the discovery skill (its SKILL.md is in the extra allowed directory / your "
    "skills). Target: the existing DISCOVERY.md at the repository root - refresh it. "
    "Initiative brief: replace the in-memory nightly orders batch (pipeline/) with a "
    "streaming, fault-tolerant, observable pipeline. Use exactly two lenses. Keep "
    "external research brief; if no browser or fetch tool is available, mark links "
    "per the skill instead of stopping. If mmdc is unavailable, skip the render "
    "step. Write only DISCOVERY.md; do not add other files."
)

FENCE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

# The planner-owned block the skill must not touch, verbatim from the fixture.
PRESERVED = """## Gap Backlog (owned by the planning workflow — do not edit)

- [ ] GAP-1: spike a streaming CSV reader behind a feature flag
- [ ] GAP-2: quarantine malformed rows instead of aborting the batch
- [ ] GAP-3: emit per-stage timing metrics

<!-- planner-checksum: 7f3a2b -->"""


def check_run_is_real(run: RunResult) -> None:
    """Same gate as every eval: the verdict must be tied to a session that happened."""
    assert run.session_id, "no session id - the run cannot prove which log is its own"
    assert Path(run.session_log).is_file(), f"session log missing: {run.session_log}"
    assert run.exit_code == 0, f"agent CLI exited {run.exit_code}"
    assert run.usage.accumulative_billed_tokens > 0, "zero tokens - an empty run must never pass"
    assert run.cost_status == "priced", f"run was not priced (status={run.cost_status})"


def check_refresh_happened(run: RunResult, workspace: Path) -> None:
    """The stale markers are gone and both state sections now carry diagrams."""
    doc = (workspace / "DISCOVERY.md").read_text(encoding="utf-8")
    assert "DISCOVERY.md" in run.files_written, f"agent did not write DISCOVERY.md (files written: {run.files_written})"
    assert "refresh me" not in doc, "the stale placeholders were left in place - no refresh happened"
    assert len(FENCE.findall(doc)) >= 2, "a refreshed discovery carries at least one diagram per state section"


def check_foreign_sections_survive(workspace: Path) -> None:
    """The planning workflow's section is preserved character for character.

    The skill's hardest rule ("this skill never edits a section it does not author")
    is exactly the kind that erodes silently: a helpful agent reformats the backlog,
    or a rewrite drops the checksum comment, and no diff reviewer notices. The
    verbatim comparison makes that erosion a red cell.
    """
    doc = (workspace / "DISCOVERY.md").read_text(encoding="utf-8")
    assert PRESERVED in doc, "the planner-owned `## Gap Backlog` section was edited, reformatted or dropped - the skill may only touch the two state sections"


@evalcase(prompt=PROMPT, skill=SKILL, fixture=FIXTURE)
def eval_discovery_refresh(run: RunResult, workspace: Path) -> None:
    """Evidence first, the refresh itself, then the ownership boundary."""
    check_run_is_real(run)
    check_refresh_happened(run, workspace)
    check_foreign_sections_survive(workspace)
