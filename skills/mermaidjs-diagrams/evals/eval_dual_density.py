"""Eval: can the skill restructure an over-budget diagram into its dual-density pattern?

The fixture holds one realistic 46-node platform diagram, well past the skill's 35-node
detailed budget and its 12-node overview budget. The skill's organisation doctrine
(``resources/diagram_organization.md``) says such a diagram becomes *two* fences: a
simplified overview that stays visible, and a detailed reference wrapped in
``<details>`` -- split further if the detail still exceeds 35 nodes -- both colour-themed
and both passing the complexity and contrast gates.

## Why this case has no golden

Its sibling ``eval_palette_mandate`` compares against a committed correct answer, because
styling a fixed four-node diagram is very nearly determined. This is the opposite case.
*Which* twelve of forty-six concepts belong in an overview, and where the detail splits,
are genuine design judgements with many defensible answers -- there is no artifact we
could commit that a correct run should resemble facet by facet (ADR 0046). So the verdict
comes from the skill's own gate scripts, run the way a CI pipeline would run them, plus
the structural properties the doctrine actually names.

The last check is the interesting one: getting the structure right *by luck* without ever
running the mandatory gates is a different outcome from getting it right and checking, and
only the second is the behaviour the skill mandates.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pytest_xharness_eval import CaseOutput, evalcase
from pytest_xharness_eval.verify import (
    check_files_written,
    check_no_files_added,
    check_rollout,
    check_skill_scripts_ran,
    facets,
)

SKILL = "mermaidjs-diagrams"
FIXTURE = "complex_diagram"  # evals/fixtures/complex_diagram/
TARGET = "ARCHITECTURE.md"
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

# What a user types after naming the skill. The skill's own doctrine supplies the budgets
# and the pattern, so the task does not restate them: naming the file and the intent is
# the whole ask, and a task that re-taught the skill its own rules would measure the task.
TASK = (
    "ARCHITECTURE.md -- its flowchart is over the complexity budget. Restructure it into "
    "the dual-density pattern, editing the file in place. Do not add new files and do not "
    "render images."
)


# -- The skill's own gates, used as verifiers -----------------------------------------


def gate(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one of the skill's gate scripts; the caller judges the exit code.

    A local verifier, which is exactly what ADR 0013 keeps room for: it is specific to
    this skill's toolchain and belongs beside the case, not in the plugin.
    """
    return subprocess.run(
        ["bun", "run", str(SCRIPTS / script), *args], capture_output=True, text=True, check=False
    )


def check_dual_density_structure(output: CaseOutput) -> None:
    """Two fences at least, one always visible and one collapsed, every one of them themed."""
    doc = output.read(TARGET)
    visible, collapsed = facets.visible_fences(doc), facets.collapsed_fences(doc)
    total = len(visible) + len(collapsed)
    assert total >= 2, f"expected an overview fence and at least one detailed fence, found {total}"
    assert visible, "every fence is inside <details>: there is no always-visible overview"
    assert collapsed, "no fence inside a <details> block: the detail was not collapsed"
    bare = facets.unstyled_nodes(doc)
    assert not bare, f"{len(bare)} node(s) left on Mermaid's default palette: {sorted(bare)[:12]}"


def check_the_skills_gates_pass(output: CaseOutput) -> None:
    """The overview fences fit the low preset, and the whole file passes both gates.

    The overview budget is asserted per fence because the gate's default preset only sees
    the file: a document whose overview is 30 nodes passes the default and still fails the
    doctrine that says an overview is at most 12.
    """
    doc = output.read(TARGET)
    scratch = output.path(".gate-scratch")
    scratch.mkdir(exist_ok=True)
    for i, fence in enumerate(facets.visible_fences(doc)):
        single = scratch / f"overview_{i}.mmd"
        single.write_text(fence, encoding="utf-8")
        low = gate("mermaid_complexity.ts", str(single), "--preset", "low")
        assert low.returncode == 0, f"visible fence {i} is over the overview budget (<=12 nodes, VCS <=25):\n{low.stdout}"

    detailed = gate("mermaid_complexity.ts", str(output.path(TARGET)))
    assert detailed.returncode == 0, f"a fence is over the detailed budget (<=35 nodes, VCS <=60):\n{detailed.stdout}"
    contrast = gate("mermaid_contrast.ts", str(output.path(TARGET)))
    assert contrast.returncode == 0, f"the contrast gate failed:\n{contrast.stdout}"


# -- The case -------------------------------------------------------------------------


@evalcase(task=TASK, skill=SKILL, fixture=FIXTURE)
def eval_dual_density(output: CaseOutput) -> None:
    """Evidence, then the structure, then the skill's own gates, then whether it ran them."""
    check_rollout(output)
    check_files_written(output, TARGET)
    # The scratch directory this grader writes is its own, and is created after the run.
    check_no_files_added(output)
    check_dual_density_structure(output)
    check_the_skills_gates_pass(output)
    check_skill_scripts_ran(output, "scripts/mermaid_complexity.ts", "scripts/mermaid_contrast.ts")
