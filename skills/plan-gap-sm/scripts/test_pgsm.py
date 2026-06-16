#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for pgsm.py — real files in tmp dirs, no mocks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pgsm
import pytest

# ── Fixture builders ─────────────────────────────────────────────────────────
INDEX_DRAFTED = """# Demo Initiative

## Execution Plan

### Runner
<!-- TODO: pending decomposition -->

### Progress
<!-- TODO: pending decomposition -->

## Overview

Two gaps close the demo initiative.

## Gap Analysis

### Gap Map
```mermaid
flowchart TD
    A --> B
```

### Dependencies
```mermaid
flowchart LR
    G1 --> G2
```

## Success Measures

- G1 output committed.
"""

DISCOVERY = """# Demo — Discovery

## Current State

### Current State — components
```mermaid
flowchart TD
    X
```

### Current State — data flow
```mermaid
flowchart LR
    X --> Y
```

## Desired State

### Desired State — components
```mermaid
flowchart TD
    X2
```

### Desired State — data flow
```mermaid
flowchart LR
    X2 --> Y2
```
"""


def ticket_md(tid: str, deps: list[str], done: bool = False) -> str:
    box = "x" if done else " "
    dep_cell = ", ".join(f"[{d}](./G{d[1:].split('.')[0]}-{d}.md)" for d in deps) or "—"
    return (
        f"# {tid}: actor does outcome\n\n- [{box}] **Done**\n\n"
        f"| | |\n|--|--|\n| Test | `tests/test_x.py::test_{tid.replace('.', '_')}` |\n"
        f"| Implements | `src/x.py` |\n| Depends on | {dep_cell} |\n"
    )


def make_plan(
    tmp_path: Path,
    *,
    index: str = INDEX_DRAFTED,
    discovery: str = DISCOVERY,
    gaps: dict[str, str] | None = None,
    tickets: dict[str, str] | None = None,
) -> Path:
    plan = tmp_path / "demo-plan"
    plan.mkdir(exist_ok=True)
    (plan / "README.md").write_text(index, encoding="utf-8")
    (plan / "DISCOVERY.md").write_text(discovery, encoding="utf-8")
    for name, body in (
        gaps or {"G1.md": "# G1: First\n\n## Outputs\n\n| File | Change |\n"}
    ).items():
        (plan / name).write_text(body, encoding="utf-8")
    for name, body in (tickets or {}).items():
        (plan / name).write_text(body, encoding="utf-8")
    return plan


@pytest.fixture
def machine() -> pgsm.Machine:
    return pgsm.load_machine(pgsm.DEFAULT_MACHINE)


# ── Machine loading ──────────────────────────────────────────────────────────
def test_default_machine_loads(machine: pgsm.Machine) -> None:
    assert machine.name == "plan-gap"
    assert machine.initial == "bootstrap"
    assert "complete" in machine.terminal
    assert set(machine.states) >= {
        "bootstrap",
        "refinement",
        "validation",
        "decomposition",
        "execution",
        "complete",
    }


def test_machine_resources_exist(machine: pgsm.Machine) -> None:
    for state in machine.states.values():
        assert (machine.root / state.resource).is_file(), state.name


def test_machine_unknown_state_raises(machine: pgsm.Machine) -> None:
    with pytest.raises(ValueError, match="unknown state"):
        machine.state("nope")


@pytest.mark.parametrize(
    "toml_body,err",
    [
        ("[states.a]\nresource = ''\n", r"missing \[machine\] table"),
        ("[machine]\nname='m'\ninitial='ghost'\n[states.a]\nresource=''\n", "not defined"),
        (
            "[machine]\nname='m'\ninitial='a'\n[states.a]\nresource=''\n"
            "[[states.a.transitions]]\nto='ghost'\ngates=[]\n",
            "undefined",
        ),
        (
            "[machine]\nname='m'\ninitial='a'\nterminal=['ghost']\n[states.a]\nresource=''\n",
            "terminal",
        ),
        (
            "[machine]\nname='m'\ninitial='a'\n[states.a]\nresource='states/ghost.md'\n",
            "resource missing",
        ),
    ],
)
def test_invalid_machine_raises(tmp_path: Path, toml_body: str, err: str) -> None:
    machines_dir = tmp_path / "resources" / "machines"
    machines_dir.mkdir(parents=True)
    path = machines_dir / "bad.toml"
    path.write_text(toml_body, encoding="utf-8")
    with pytest.raises(ValueError, match=err):
        pgsm.load_machine(path)


# ── Spec parsing ─────────────────────────────────────────────────────────────
def test_parse_ticket_deps_and_done(tmp_path: Path) -> None:
    plan = make_plan(tmp_path, tickets={"G1-T1.2.md": ticket_md("T1.2", ["T1.1"], done=True)})
    ticket = pgsm.parse_ticket(plan / "G1-T1.2.md")
    assert (ticket.gap, ticket.minor, ticket.tid) == (1, 2, "T1.2")
    assert ticket.deps == ("T1.1",)
    assert ticket.done


def test_parse_ticket_rejects_non_ticket(tmp_path: Path) -> None:
    path = tmp_path / "G1.md"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not a ticket"):
        pgsm.parse_ticket(path)


def test_load_tickets_sorted_and_next_eligible(tmp_path: Path) -> None:
    plan = make_plan(
        tmp_path,
        tickets={
            "G1-T1.1.md": ticket_md("T1.1", [], done=True),
            "G1-T1.2.md": ticket_md("T1.2", ["T1.1"]),
            "G2-T2.1.md": ticket_md("T2.1", ["T1.2"]),
        },
    )
    tickets = pgsm.load_tickets(plan)
    assert [t.tid for t in tickets] == ["T1.1", "T1.2", "T2.1"]
    eligible = pgsm.next_eligible_ticket(tickets)
    assert eligible is not None and eligible.tid == "T1.2"


def test_next_eligible_none_when_all_done(tmp_path: Path) -> None:
    plan = make_plan(tmp_path, tickets={"G1-T1.1.md": ticket_md("T1.1", [], done=True)})
    assert pgsm.next_eligible_ticket(pgsm.load_tickets(plan)) is None


def test_dag_cycle_detected(tmp_path: Path) -> None:
    plan = make_plan(
        tmp_path,
        tickets={
            "G1-T1.1.md": ticket_md("T1.1", ["T1.2"]),
            "G1-T1.2.md": ticket_md("T1.2", ["T1.1"]),
        },
    )
    cycle = pgsm.find_dag_cycle(pgsm.load_tickets(plan))
    assert cycle is not None and set(cycle) >= {"T1.1", "T1.2"}


def test_dag_acyclic_ok(tmp_path: Path) -> None:
    plan = make_plan(tmp_path, tickets={"G1-T1.1.md": ticket_md("T1.1", [])})
    assert pgsm.find_dag_cycle(pgsm.load_tickets(plan)) is None


# ── Gates ────────────────────────────────────────────────────────────────────
def test_gate_file_exists(tmp_path: Path) -> None:
    plan = make_plan(tmp_path)
    assert pgsm.eval_gate(plan, {"kind": "file_exists", "path": "README.md"}).passed
    assert not pgsm.eval_gate(plan, {"kind": "file_exists", "path": "GHOST.md"}).passed


def test_gate_glob_min(tmp_path: Path) -> None:
    plan = make_plan(tmp_path)
    assert pgsm.eval_gate(plan, {"kind": "glob_min", "pattern": "G*.md", "min": 1}).passed
    assert not pgsm.eval_gate(plan, {"kind": "glob_min", "pattern": "G*-T*.md", "min": 1}).passed


def test_gate_marker_absent_with_excluded_section(tmp_path: Path) -> None:
    plan = make_plan(tmp_path)  # INDEX_DRAFTED has TODOs only inside ## Execution Plan
    gate = {
        "kind": "marker_absent",
        "marker": "<!-- TODO",
        "glob": "README.md",
        "exclude_sections": ["## Execution Plan"],
    }
    assert pgsm.eval_gate(plan, gate).passed
    assert not pgsm.eval_gate(
        plan, {"kind": "marker_absent", "marker": "<!-- TODO", "glob": "README.md"}
    ).passed


def test_gate_marker_present(tmp_path: Path) -> None:
    plan = make_plan(tmp_path, gaps={"G1.md": "# G1\n<!-- UNRESOLVED -->\n"})
    assert pgsm.eval_gate(
        plan, {"kind": "marker_present", "marker": "<!-- UNRESOLVED -->", "glob": "G*.md"}
    ).passed
    assert not pgsm.eval_gate(
        plan, {"kind": "marker_present", "marker": "<!-- CHANGE-REQUEST -->", "glob": "G*.md"}
    ).passed


def test_gate_all_files_contain(tmp_path: Path) -> None:
    plan = make_plan(
        tmp_path,
        tickets={
            "G1-T1.1.md": ticket_md("T1.1", [], done=True),
            "G1-T1.2.md": ticket_md("T1.2", []),
        },
    )
    assert pgsm.eval_gate(
        plan, {"kind": "all_files_contain", "glob": "G*-T*.md", "needle": "**Done**"}
    ).passed
    result = pgsm.eval_gate(
        plan, {"kind": "all_files_contain", "glob": "G*-T*.md", "needle": "- [x] **Done**"}
    )
    assert not result.passed and "G1-T1.2.md" in result.detail
    assert not pgsm.eval_gate(
        plan, {"kind": "all_files_contain", "glob": "Z*.md", "needle": "x"}
    ).passed


def test_gate_mermaid_min(tmp_path: Path) -> None:
    plan = make_plan(tmp_path)
    assert pgsm.eval_gate(plan, {"kind": "mermaid_min", "path": "DISCOVERY.md", "min": 4}).passed
    assert not pgsm.eval_gate(plan, {"kind": "mermaid_min", "path": "README.md", "min": 3}).passed
    assert not pgsm.eval_gate(plan, {"kind": "mermaid_min", "path": "GHOST.md", "min": 1}).passed


def test_gate_tickets_per_gap(tmp_path: Path) -> None:
    plan = make_plan(
        tmp_path,
        gaps={"G1.md": "# G1\n", "G2.md": "# G2\n"},
        tickets={"G1-T1.1.md": ticket_md("T1.1", [])},
    )
    result = pgsm.eval_gate(plan, {"kind": "tickets_per_gap"})
    assert not result.passed and "G2.md" in result.detail
    (plan / "G2-T2.1.md").write_text(ticket_md("T2.1", []), encoding="utf-8")
    assert pgsm.eval_gate(plan, {"kind": "tickets_per_gap"}).passed


def test_gate_dag_acyclic_dangling_dep(tmp_path: Path) -> None:
    plan = make_plan(tmp_path, tickets={"G1-T1.1.md": ticket_md("T1.1", ["T9.9"])})
    result = pgsm.eval_gate(plan, {"kind": "dag_acyclic", "glob": "G*-T*.md"})
    assert not result.passed and "T9.9" in result.detail


def test_gate_command(tmp_path: Path) -> None:
    plan = make_plan(tmp_path)
    assert pgsm.eval_gate(plan, {"kind": "command", "argv": ["true"]}).passed
    assert not pgsm.eval_gate(plan, {"kind": "command", "argv": ["false"]}).passed
    assert not pgsm.eval_gate(plan, {"kind": "command", "argv": ["pgsm-no-such-binary-xyz"]}).passed


def test_gate_unknown_kind_crashes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown gate kind"):
        pgsm.eval_gate(make_plan(tmp_path), {"kind": "vibes"})


# ── State IO + advance ───────────────────────────────────────────────────────
def init_plan(tmp_path: Path, **kwargs: object) -> tuple[Path, pgsm.Machine, pgsm.PlanState]:
    plan = make_plan(tmp_path, **kwargs)  # type: ignore[arg-type]
    machine = pgsm.load_machine(pgsm.DEFAULT_MACHINE)
    state = pgsm.init_state(plan, machine, brief="demo brief")
    return plan, machine, state


def test_init_and_reload_state(tmp_path: Path) -> None:
    plan, machine, state = init_plan(tmp_path)
    assert state.state == "bootstrap"
    reloaded = pgsm.load_state(plan)
    assert reloaded.state == "bootstrap"
    assert reloaded.data["brief"] == "demo brief"
    with pytest.raises(FileExistsError):
        pgsm.init_state(plan, machine, brief="again")
    forced = pgsm.init_state(plan, machine, brief="again", force=True)
    assert forced.data["brief"] == "again"


def test_load_state_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="pgsm init"):
        pgsm.load_state(tmp_path)


def test_advance_bootstrap_to_refinement(tmp_path: Path) -> None:
    plan, machine, state = init_plan(tmp_path)
    result = pgsm.advance(plan, machine, state)
    assert result["transitioned"] and result["to"] == "refinement"
    assert pgsm.load_state(plan).state == "refinement"
    history = pgsm.load_state(plan).data["history"]
    assert history[-1]["event"] == "transition" and history[-1]["evidence"]


def test_advance_holds_on_missing_evidence(tmp_path: Path) -> None:
    plan = tmp_path / "empty-plan"
    plan.mkdir()
    machine = pgsm.load_machine(pgsm.DEFAULT_MACHINE)
    state = pgsm.init_state(plan, machine, brief="")
    result = pgsm.advance(plan, machine, state)
    assert not result["transitioned"]
    assert pgsm.load_state(plan).state == "bootstrap"


def test_advance_dry_run_does_not_record(tmp_path: Path) -> None:
    plan, machine, state = init_plan(tmp_path)
    result = pgsm.advance(plan, machine, state, dry_run=True)
    assert result["transitioned"]
    assert pgsm.load_state(plan).state == "bootstrap"


def test_advance_paused_refuses(tmp_path: Path) -> None:
    plan, machine, state = init_plan(tmp_path)
    state.data["paused"] = True
    state.save()
    result = pgsm.advance(plan, machine, pgsm.load_state(plan))
    assert result["paused"] and not result["transitioned"]


def test_full_walk_to_complete(tmp_path: Path) -> None:
    """Drive the machine bootstrap → … → complete with evidence staged per state."""
    plan, machine, state = init_plan(
        tmp_path,
        gaps={"G1.md": "# G1: First\n\n## ADR1.1: choice\n<!-- UNRESOLVED -->\n"},
    )
    assert pgsm.advance(plan, machine, pgsm.load_state(plan))["to"] == "refinement"
    # refinement holds while the ADR is open
    assert not pgsm.advance(plan, machine, pgsm.load_state(plan))["transitioned"]
    (plan / "G1.md").write_text(
        "# G1: First\n\n## ADR1.1: choice\n- **Decision:** A.\n", encoding="utf-8"
    )
    assert pgsm.advance(plan, machine, pgsm.load_state(plan))["to"] == "validation"
    # validation needs the receipt
    assert not pgsm.advance(plan, machine, pgsm.load_state(plan))["transitioned"]
    receipt = plan / ".pgsm" / "receipts" / "validation.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{"requirement_integrity": "pass"}\n', encoding="utf-8")
    assert pgsm.advance(plan, machine, pgsm.load_state(plan))["to"] == "decomposition"
    # decomposition needs tickets + populated Execution Plan
    assert not pgsm.advance(plan, machine, pgsm.load_state(plan))["transitioned"]
    (plan / "G1-T1.1.md").write_text(ticket_md("T1.1", []), encoding="utf-8")
    (plan / "README.md").write_text(
        INDEX_DRAFTED.replace("<!-- TODO: pending decomposition -->", "populated"), encoding="utf-8"
    )
    assert pgsm.advance(plan, machine, pgsm.load_state(plan))["to"] == "execution"
    # execution holds until the ticket is done
    assert not pgsm.advance(plan, machine, pgsm.load_state(plan))["transitioned"]
    (plan / "G1-T1.1.md").write_text(ticket_md("T1.1", [], done=True), encoding="utf-8")
    assert pgsm.advance(plan, machine, pgsm.load_state(plan))["to"] == "complete"
    final = pgsm.load_state(plan)
    assert final.state in machine.terminal
    # re-opening: a new UNRESOLVED marker routes back to refinement
    (plan / "G1.md").write_text("# G1\n<!-- UNRESOLVED -->\n", encoding="utf-8")
    assert pgsm.advance(plan, machine, final)["to"] == "refinement"


def test_execution_marker_routes_back_to_refinement(tmp_path: Path) -> None:
    plan, machine, state = init_plan(tmp_path, gaps={"G1.md": "# G1\n<!-- CHANGE-REQUEST -->\n"})
    state.data["state"] = "execution"
    state.save()
    result = pgsm.advance(plan, machine, pgsm.load_state(plan))
    assert result["to"] == "refinement"


# ── Compose + prompt ─────────────────────────────────────────────────────────
def test_compose_selectors(tmp_path: Path) -> None:
    plan = make_plan(
        tmp_path,
        gaps={"G1.md": "# G1\n<!-- UNRESOLVED -->\n", "G2.md": "# G2 settled\n"},
        tickets={"G1-T1.1.md": ticket_md("T1.1", [])},
    )
    out = pgsm.compose_context(plan, ["index", "discovery", "all_gaps"])
    assert "FILE: README.md" in out and "FILE: DISCOVERY.md" in out
    assert "FILE: G1.md" in out and "FILE: G2.md" in out
    marked = pgsm.compose_context(plan, ["gaps_with_markers"])
    assert "FILE: G1.md" in marked and "G2.md" not in marked


def test_compose_ticket_path_is_root_to_leaf(tmp_path: Path) -> None:
    plan = make_plan(tmp_path, tickets={"G1-T1.1.md": ticket_md("T1.1", [])})
    ticket = pgsm.load_tickets(plan)[0]
    out = pgsm.compose_context(plan, ["ticket_path"], ticket)
    idx, gap, tkt = (
        out.index("FILE: README.md"),
        out.index("FILE: G1.md"),
        out.index("FILE: G1-T1.1.md"),
    )
    assert idx < gap < tkt


def test_compose_unknown_selector_crashes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown compose selector"):
        pgsm.compose_context(make_plan(tmp_path), ["vibes"])


def test_build_prompt_execution_assigns_one_ticket(tmp_path: Path) -> None:
    plan, machine, state = init_plan(tmp_path, tickets={"G1-T1.1.md": ticket_md("T1.1", [])})
    state.data["state"] = "execution"
    state.save()
    prompt = pgsm.build_prompt(plan, machine, pgsm.load_state(plan))
    assert "state: execution" in prompt
    assert "**T1.1**" in prompt
    assert "RED" in prompt  # state resource text inlined
    assert "FILE: G1-T1.1.md" in prompt  # leaf composed
    assert "Exit gates" in prompt


def test_build_prompt_execution_no_eligible_ticket(tmp_path: Path) -> None:
    plan, machine, state = init_plan(tmp_path, tickets={"G1-T1.1.md": ticket_md("T1.1", ["T9.9"])})
    state.data["state"] = "execution"
    state.save()
    prompt = pgsm.build_prompt(plan, machine, pgsm.load_state(plan))
    assert "No eligible ticket" in prompt


def test_log_prompt_writes_copy_and_hash(tmp_path: Path) -> None:
    plan, machine, state = init_plan(tmp_path)
    prompt = pgsm.build_prompt(plan, machine, state)
    path = pgsm.log_prompt(state, prompt, session_id="sess-1")
    assert path.is_file() and path.read_text(encoding="utf-8") == prompt
    reloaded = pgsm.load_state(plan)
    last = reloaded.data["history"][-1]
    assert last["event"] == "prompt" and last["session_id"] == "sess-1"
    assert len(last["sha256"]) == 64
    assert reloaded.data["prompt_seq"] == 1


def test_gate_report_terminal_state(tmp_path: Path) -> None:
    machine = pgsm.load_machine(pgsm.DEFAULT_MACHINE)
    no_exit = pgsm.StateDef(name="x", resource="", description="", compose=[], transitions=[])
    assert "Terminal" in pgsm.gate_report(make_plan(tmp_path), no_exit)
    assert machine  # fixture used


# ── CLI ──────────────────────────────────────────────────────────────────────
def run_cli(*argv: str) -> None:
    pgsm.main(list(argv))


def test_cli_init_status_next_prompt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plan = make_plan(tmp_path)
    run_cli("init", str(plan), "--brief", "demo")
    assert "initialised plan-gap" in capsys.readouterr().out
    run_cli("status", str(plan))
    out = capsys.readouterr().out
    assert "state:    bootstrap" in out and "demo" in out
    run_cli("status", str(plan), "--json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "bootstrap" and not payload["paused"]
    run_cli("next", str(plan), "--json")
    assert json.loads(capsys.readouterr().out)["to"] == "refinement"
    run_cli("prompt", str(plan), "--session-id", "s-1")
    out = capsys.readouterr().out
    assert "state: refinement" in out
    assert (plan / ".pgsm" / "prompts" / "0001-refinement.md").is_file()


def test_cli_next_holding_lists_failures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = tmp_path / "p"
    plan.mkdir()
    run_cli("init", str(plan))
    capsys.readouterr()
    run_cli("next", str(plan))
    out = capsys.readouterr().out
    assert "holding in bootstrap" in out and "[FAIL]" in out


def test_cli_pause_resume(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plan = make_plan(tmp_path)
    run_cli("init", str(plan))
    run_cli("pause", str(plan))
    assert "paused" in capsys.readouterr().out
    run_cli("next", str(plan))
    assert "paused" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="paused"):
        run_cli("prompt", str(plan))
    run_cli("resume", str(plan))
    assert "resumed" in capsys.readouterr().out


def test_cli_compose_ticket_and_selectors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = make_plan(tmp_path, tickets={"G1-T1.1.md": ticket_md("T1.1", [])})
    run_cli("compose", str(plan), "--ticket", "T1.1")
    out = capsys.readouterr().out
    assert "FILE: G1-T1.1.md" in out
    run_cli("compose", str(plan), "--select", "discovery")
    assert "FILE: DISCOVERY.md" in capsys.readouterr().out
    run_cli("compose", str(plan))
    assert "FILE: README.md" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="no ticket"):
        run_cli("compose", str(plan), "--ticket", "T9.9")


def test_cli_no_subcommand_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    run_cli()
    assert "usage: pgsm" in capsys.readouterr().out


def test_cli_next_dry_run_and_terminal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plan = make_plan(tmp_path)
    run_cli("init", str(plan))
    capsys.readouterr()
    run_cli("next", str(plan), "--dry-run")
    assert "dry-run" in capsys.readouterr().out
    state = pgsm.load_state(plan)
    state.data["state"] = "complete"
    state.save()
    run_cli("next", str(plan))
    assert "terminal" in capsys.readouterr().out


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
