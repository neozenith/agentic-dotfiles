"""Eval: does the mermaidjs-diagrams skill's palette mandate actually get applied?

This is the harness's reference case. It is deliberately small (one fixture,
one prompt) but it exercises every layer of the harness in a single cell, so a
green run here is evidence that the whole pipeline works end to end:

    run the real CLI  ->  capture its own session log  ->  price it
    ->  grade the workspace the agent left behind  ->  report

The grading is split into three named checks, one per concern. Read them top
to bottom as a tutorial on what an eval can assert and why each assertion is
there. Every check raises AssertionError with a message saying what went wrong
in the agent's terms, not the harness's.
"""

from pathlib import Path

from pytest_xharness_eval import RunResult, evalcase

# The skill under test and the fixture it works on. The fixture is one
# markdown file holding an unstyled flowchart - the exact thing the skill
# says must never ship (SKILL.md: "Never leave an authored diagram on
# Mermaid's default unstyled palette").
SKILL = "mermaidjs-diagrams"
FIXTURE = "unstyled_diagram"  # evals/fixtures/unstyled_diagram/

# The prompt names the skill explicitly and constrains the task so the grade
# measures one behaviour: did the agent apply the mandate to the existing
# diagram? "Do not add new files" stops an agent satisfying the check by
# writing a second, styled copy and leaving the original untouched.
PROMPT = (
    "Use the mermaidjs-diagrams skill (its SKILL.md is in the extra allowed "
    "directory / your skills). Apply its mandatory color-theming requirement to "
    "the diagram in ARCHITECTURE.md: every node must get an explicit classDef "
    "with both fill and color derived from the skill's color_theming.md palette. "
    "Edit ARCHITECTURE.md in place. Do not add new files. Do not render images."
)


# -- Check 1: the run is real evidence ---------------------------------------

def check_run_is_real(run: RunResult) -> None:
    """The verdict must be tied to a session that actually happened.

    A harness that grades the wrong transcript, or an empty one, looks exactly
    like a harness that works. These four assertions close that gap: the run
    knows its own session id, the log it names exists on disk, the CLI exited
    cleanly, and the model produced tokens. If any of these fail, nothing
    below is worth reading.
    """
    assert run.session_id, "no session id - the run cannot prove which log is its own"
    assert Path(run.session_log).is_file(), f"session log missing: {run.session_log}"
    assert run.exit_code == 0, f"agent CLI exited {run.exit_code}"
    assert run.usage.total_tokens > 0, "zero tokens - an empty run must never pass"


# -- Check 2: the run is priced ----------------------------------------------

def check_run_is_priced(run: RunResult) -> None:
    """Cost must be a real positive figure, never a silent zero.

    Neither CLI's session log carries cost. Claude reports it on stdout, Codex
    reports it nowhere, so the harness prices from its own table. An unpriced
    model is supposed to abort before the cell runs; this check catches the
    case where pricing silently produced nothing, which would make an
    expensive sweep look free.
    """
    assert run.cost_status == "priced", f"run was not priced (status={run.cost_status})"
    assert run.cost_usd is not None and run.cost_usd > 0, "cost must be a positive USD figure"


# -- Check 3: the skill did its job ------------------------------------------

def check_palette_mandate_applied(run: RunResult, workspace: Path) -> None:
    """The diagram in the workspace now carries the mandated palette.

    This is the only check that is about the skill rather than the harness.
    It grades the artifact the agent left behind, not the prose it returned,
    because the skill's contract is about the file. The assertions go from
    coarse to fine: the right file changed, a classDef exists, it has an
    explicit fill, it has an explicit text colour, and the fence survived.
    """
    doc_path = workspace / "ARCHITECTURE.md"
    doc = doc_path.read_text(encoding="utf-8")

    assert "ARCHITECTURE.md" in run.files_written, (
        f"agent did not modify ARCHITECTURE.md (files written: {run.files_written})"
    )
    assert "```mermaid" in doc, "the mermaid fence was destroyed rather than styled"
    assert "classDef" in doc, "diagram still has no classDef - palette mandate not applied"
    assert "fill:#" in doc, "classDef carries no explicit fill"
    assert "color:" in doc, "classDef carries no explicit text colour (skill forbids the default)"


# -- The case ----------------------------------------------------------------

@evalcase(prompt=PROMPT, skill=SKILL, fixture=FIXTURE)
def eval_palette_mandate(run: RunResult, workspace: Path) -> None:
    """One cell = one (cli, model) pair running PROMPT against FIXTURE.

    The harness expands this over the default matrix (pytest_xharness_eval.matrix),
    so the same three checks run once per CLI per model. Order matters:
    evidence first, cost second, behaviour last - a failure in an earlier
    check makes the later ones meaningless.
    """
    check_run_is_real(run)
    check_run_is_priced(run)
    check_palette_mandate_applied(run, workspace)
