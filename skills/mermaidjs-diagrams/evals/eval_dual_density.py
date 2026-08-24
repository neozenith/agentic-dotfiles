"""Eval: can the mermaidjs-diagrams skill restructure an over-budget diagram into its dual-density pattern?

The fixture holds one realistic 46-node platform diagram, well past the skill's
35-node detailed budget and its 12-node overview budget. The skill's own
organisation doctrine (``resources/diagram_organization.md``) says such a diagram
becomes *two* fences: a simplified overview that stays visible and a detailed
reference wrapped in ``<details>``, split further if the detail still exceeds 35
nodes, both colour-themed and both passing the complexity and contrast gates.

The grader uses the skill's gate scripts as verifiers, the way a CI pipeline
would: the always-visible fences must pass ``--preset low`` (<=12 nodes, VCS
<=25), every fence must pass the default preset (<=35 nodes), and the contrast
gate must pass. It also asks the coverage ledger whether the agent actually ran
the gates it was told are mandatory: a run that got the structure right by luck
without running them is a different outcome from one that checked.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from pytest_xharness_eval import RunResult, evalcase

SKILL = "mermaidjs-diagrams"
FIXTURE = "complex_diagram"  # evals/fixtures/complex_diagram/

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

PROMPT = (
    "Use the mermaidjs-diagrams skill (its SKILL.md is in the extra allowed directory / your skills). "
    "ARCHITECTURE.md holds one flowchart that exceeds the skill's complexity budget. Restructure it into the "
    "skill's dual-density pattern from resources/diagram_organization.md: a simplified overview fence that stays "
    "visible (at most 12 nodes), and the complete detailed diagram inside a collapsed <details> block (at most 35 "
    "nodes per fence; split it into more than one detailed fence if needed). Every fence must carry the skill's "
    "mandatory colour theming (explicit classDef with fill and color from color_theming.md) and must pass the "
    "skill's complexity and contrast gates. Edit ARCHITECTURE.md in place. Do not add new files. Do not render images."
)

FENCE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


def _gate(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one of the skill's gate scripts; the caller judges the exit code."""
    return subprocess.run(["bun", "run", str(SCRIPTS / script), *args], capture_output=True, text=True, check=False)


def _fences(doc: str) -> list[tuple[str, bool]]:
    """Every mermaid fence with whether it sits inside a ``<details>`` block."""
    out = []
    for m in FENCE.finditer(doc):
        before = doc[: m.start()]
        inside = before.count("<details") > before.count("</details>")
        out.append((m.group(1), inside))
    return out


# -- Check 1: the run is real evidence and priced (same bar as the reference case) ----


def check_run_is_real_and_priced(run: RunResult) -> None:
    assert run.session_id and Path(run.session_log).is_file(), "no session log to tie the verdict to"
    assert run.exit_code == 0, f"agent CLI exited {run.exit_code}"
    assert run.usage.accumulative_billed_tokens > 0, "zero tokens - an empty run must never pass"
    assert run.cost_status == "priced" and run.estimated_cost_usd, "run was not priced"


# -- Check 2: the structure is dual density ---------------------------------------


def check_dual_density_structure(run: RunResult, workspace: Path) -> list[tuple[str, bool]]:
    doc = (workspace / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "ARCHITECTURE.md" in run.files_written, f"agent did not modify ARCHITECTURE.md (wrote {run.files_written})"
    fences = _fences(doc)
    visible = [f for f, inside in fences if not inside]
    collapsed = [f for f, inside in fences if inside]
    assert len(fences) >= 2, f"expected at least two mermaid fences (overview + detail), found {len(fences)}"
    assert visible, "no always-visible overview fence (every fence is inside <details>)"
    assert collapsed, "no detailed fence inside a <details> block"
    for fence in fences:
        assert "classDef" in fence[0] and "fill:" in fence[0] and "color:" in fence[0], (
            "a fence carries no explicit classDef fill + color (the skill's palette mandate)"
        )
    return fences


# -- Check 3: the skill's own gates agree ------------------------------------------


def check_gates_pass(workspace: Path, fences: list[tuple[str, bool]], tmp: Path) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    for i, (fence, inside) in enumerate(fences):
        if inside:
            continue
        single = tmp / f"overview_{i}.mmd"
        single.write_text(fence, encoding="utf-8")
        low = _gate("mermaid_complexity.ts", str(single), "--preset", "low")
        assert low.returncode == 0, f"overview fence {i} exceeds the low preset (<=12 nodes, VCS <=25):\n{low.stdout}"
    high = _gate("mermaid_complexity.ts", str(workspace / "ARCHITECTURE.md"))
    assert high.returncode == 0, f"a fence exceeds the detailed budget (<=35 nodes, VCS <=60):\n{high.stdout}"
    contrast = _gate("mermaid_contrast.ts", str(workspace / "ARCHITECTURE.md"))
    assert contrast.returncode == 0, f"contrast gate failed:\n{contrast.stdout}"


# -- Check 4: the agent ran the gates it was told are mandatory --------------------


def check_agent_ran_the_gates(run: RunResult) -> None:
    ran = set(run.skill_coverage.get("run") or [])
    assert "scripts/mermaid_complexity.ts" in ran, f"agent never ran the complexity gate (ran: {sorted(ran)})"
    assert "scripts/mermaid_contrast.ts" in ran, f"agent never ran the contrast gate (ran: {sorted(ran)})"


# -- The case ----------------------------------------------------------------------


@evalcase(prompt=PROMPT, skill=SKILL, fixture=FIXTURE)
def eval_dual_density(run: RunResult, workspace: Path) -> None:
    """One cell = one (harness, model) pair restructuring the over-budget diagram.

    Order matters: evidence first, structure second, the skill's own gates third,
    and last whether the agent took the decision path the skill mandates.
    """
    check_run_is_real_and_priced(run)
    fences = check_dual_density_structure(run, workspace)
    check_gates_pass(workspace, fences, workspace.parent / f"{workspace.name}.grader")
    check_agent_ran_the_gates(run)
