#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""pgsm — deterministic state machine driving a gap-analysis spec to completion.

The machine (states, transitions, evidence gates) is pure data in a TOML file;
this engine evaluates gates against the plan directory, persists state in
<plan>/.pgsm/state.json, and composes the exact prompt for the current state —
state instructions + the root→leaf document path — so the executing agent never
spends tool calls discovering context. Every emitted prompt is logged to
<plan>/.pgsm/prompts/ with its sha256 recorded in history, making "what text was
actually loaded" a byte-level check against the session transcript.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import logging
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT = Path(__file__)
SCRIPT_DIR = SCRIPT.parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_MACHINE = SKILL_DIR / "resources" / "machines" / "plan-gap.toml"

STATE_REL = Path(".pgsm") / "state.json"
PROMPTS_REL = Path(".pgsm") / "prompts"

GAP_FILE_RE = re.compile(r"^G(\d+)\.md$")
TICKET_FILE_RE = re.compile(r"^G(\d+)-T(\d+)\.(\d+)\.md$")
TICKET_ID_RE = re.compile(r"\bT(\d+)\.(\d+)\b")
MERMAID_FENCE_RE = re.compile(r"^```mermaid\s*$", re.MULTILINE)
DONE_CHECKED = "- [x] **Done**"

OPEN_MARKERS = ("<!-- UNRESOLVED -->", "<!-- CHANGE-REQUEST -->", "<!-- ASSUMPTION")

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ── Machine definition ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class Transition:
    to: str
    gates: list[dict[str, Any]]


@dataclass(frozen=True)
class StateDef:
    name: str
    resource: str
    description: str
    compose: list[str]
    transitions: list[Transition]


@dataclass(frozen=True)
class Machine:
    name: str
    initial: str
    terminal: list[str]
    states: dict[str, StateDef]
    path: Path

    @property
    def root(self) -> Path:
        """Resource paths resolve relative to the machine file's resources/ root."""
        return self.path.parent.parent

    def state(self, name: str) -> StateDef:
        if name not in self.states:
            raise ValueError(f"unknown state {name!r} (machine {self.name!r})")
        return self.states[name]


def load_machine(path: Path) -> Machine:
    """Parse + validate a machine TOML. Invalid configs fail loudly here, not mid-run."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    meta = raw.get("machine")
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: missing [machine] table")
    states: dict[str, StateDef] = {}
    for name, body in raw.get("states", {}).items():
        transitions = [
            Transition(to=str(t["to"]), gates=list(t.get("gates", [])))
            for t in body.get("transitions", [])
        ]
        states[name] = StateDef(
            name=name,
            resource=str(body.get("resource", "")),
            description=str(body.get("description", "")),
            compose=list(body.get("compose", [])),
            transitions=transitions,
        )
    machine = Machine(
        name=str(meta["name"]),
        initial=str(meta["initial"]),
        terminal=[str(t) for t in meta.get("terminal", [])],
        states=states,
        path=path.resolve(),
    )
    if machine.initial not in states:
        raise ValueError(f"{path}: initial state {machine.initial!r} not defined")
    for state in states.values():
        for transition in state.transitions:
            if transition.to not in states:
                raise ValueError(
                    f"{path}: state {state.name!r} transitions to undefined {transition.to!r}"
                )
        if state.resource and not (machine.root / state.resource).is_file():
            raise ValueError(f"{path}: state {state.name!r} resource missing: {state.resource}")
    for terminal in machine.terminal:
        if terminal not in states:
            raise ValueError(f"{path}: terminal state {terminal!r} not defined")
    return machine


# ── Spec parsing (gap + ticket files) ────────────────────────────────────────
@dataclass(frozen=True)
class Ticket:
    path: Path
    gap: int
    minor: int
    done: bool
    deps: tuple[str, ...]

    @property
    def tid(self) -> str:
        return f"T{self.gap}.{self.minor}"


def parse_ticket(path: Path) -> Ticket:
    match = TICKET_FILE_RE.match(path.name)
    if match is None:
        raise ValueError(f"not a ticket filename: {path.name}")
    text = path.read_text(encoding="utf-8")
    deps: tuple[str, ...] = ()
    for line in text.splitlines():
        if "Depends on" in line and line.lstrip().startswith("|"):
            deps = tuple(dict.fromkeys(f"T{a}.{b}" for a, b in TICKET_ID_RE.findall(line)))
            break
    return Ticket(
        path=path,
        gap=int(match.group(1)),
        minor=int(match.group(3)),
        done=DONE_CHECKED in text,
        deps=deps,
    )


def load_tickets(plan: Path) -> list[Ticket]:
    tickets = [parse_ticket(p) for p in plan.iterdir() if TICKET_FILE_RE.match(p.name)]
    return sorted(tickets, key=lambda t: (t.gap, t.minor))


def gap_number(path: Path) -> int:
    match = GAP_FILE_RE.match(path.name)
    if match is None:
        raise ValueError(f"not a gap filename: {path.name}")
    return int(match.group(1))


def gap_files(plan: Path) -> list[Path]:
    return sorted((p for p in plan.iterdir() if GAP_FILE_RE.match(p.name)), key=gap_number)


def next_eligible_ticket(tickets: list[Ticket]) -> Ticket | None:
    """Lowest-numbered not-done ticket whose dependencies are all done."""
    done_ids = {t.tid for t in tickets if t.done}
    for ticket in tickets:
        if not ticket.done and all(dep in done_ids for dep in ticket.deps):
            return ticket
    return None


def find_dag_cycle(tickets: list[Ticket]) -> list[str] | None:
    """Return a dependency cycle as a list of ticket ids, or None when acyclic."""
    graph = {t.tid: t.deps for t in tickets}
    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)

    def visit(node: str, stack: list[str]) -> list[str] | None:
        color[node] = GREY
        stack.append(node)
        for dep in graph.get(node, ()):
            if color.get(dep, BLACK) == GREY:
                return stack[stack.index(dep) :] + [dep]
            if color.get(dep) == WHITE:
                cycle = visit(dep, stack)
                if cycle is not None:
                    return cycle
        stack.pop()
        color[node] = BLACK
        return None

    for tid in graph:
        if color[tid] == WHITE:
            cycle = visit(tid, [])
            if cycle is not None:
                return cycle
    return None


# ── Evidence gates ───────────────────────────────────────────────────────────
@dataclass(frozen=True)
class GateResult:
    kind: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "passed": self.passed, "detail": self.detail}


def _strip_sections(text: str, headings: list[str]) -> str:
    """Remove each named section (its heading line through the next same-or-higher heading)."""
    lines = text.splitlines()
    keep: list[str] = []
    skip_level = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            if skip_level and level <= skip_level:
                skip_level = 0
            if not skip_level and any(stripped.startswith(h) for h in headings):
                skip_level = level
                continue
        if not skip_level:
            keep.append(line)
    return "\n".join(keep)


def _matching_files(plan: Path, pattern: str) -> list[Path]:
    return sorted(p for p in plan.iterdir() if p.is_file() and fnmatch.fnmatch(p.name, pattern))


def eval_gate(plan: Path, gate: dict[str, Any]) -> GateResult:
    """Evaluate one declarative gate against the plan directory. Unknown kinds crash."""
    kind = str(gate["kind"])
    if kind == "file_exists":
        path = plan / str(gate["path"])
        return GateResult(
            kind, path.is_file(), f"{gate['path']}: {'exists' if path.is_file() else 'MISSING'}"
        )
    if kind == "glob_min":
        files = _matching_files(plan, str(gate["pattern"]))
        minimum = int(gate["min"])
        return GateResult(
            kind,
            len(files) >= minimum,
            f"{gate['pattern']}: {len(files)} file(s), need >= {minimum}",
        )
    if kind in {"marker_absent", "marker_present"}:
        marker = str(gate["marker"])
        exclude = [str(h) for h in gate.get("exclude_sections", [])]
        hits: list[str] = []
        for path in _matching_files(plan, str(gate["glob"])):
            text = path.read_text(encoding="utf-8")
            if exclude:
                text = _strip_sections(text, exclude)
            count = text.count(marker)
            if count:
                hits.append(f"{path.name}({count})")
        found = bool(hits)
        passed = found if kind == "marker_present" else not found
        detail = f"{marker!r} in {', '.join(hits)}" if found else f"{marker!r} not found"
        return GateResult(kind, passed, detail)
    if kind == "all_files_contain":
        needle = str(gate["needle"])
        files = _matching_files(plan, str(gate["glob"]))
        missing = [p.name for p in files if needle not in p.read_text(encoding="utf-8")]
        if not files:
            return GateResult(kind, False, f"no files match {gate['glob']}")
        detail = (
            f"missing {needle!r}: {', '.join(missing)}"
            if missing
            else f"all {len(files)} contain {needle!r}"
        )
        return GateResult(kind, not missing, detail)
    if kind == "mermaid_min":
        path = plan / str(gate["path"])
        count = (
            len(MERMAID_FENCE_RE.findall(path.read_text(encoding="utf-8"))) if path.is_file() else 0
        )
        minimum = int(gate["min"])
        return GateResult(
            kind, count >= minimum, f"{gate['path']}: {count} mermaid fence(s), need >= {minimum}"
        )
    if kind == "tickets_per_gap":
        tickets = load_tickets(plan)
        gaps_with = {t.gap for t in tickets}
        bare = [p.name for p in gap_files(plan) if gap_number(p) not in gaps_with]
        detail = f"gaps without tickets: {', '.join(bare)}" if bare else "every gap has >= 1 ticket"
        return GateResult(kind, not bare, detail)
    if kind == "dag_acyclic":
        tickets = load_tickets(plan)
        known = {t.tid for t in tickets}
        dangling = sorted({dep for t in tickets for dep in t.deps if dep not in known})
        if dangling:
            return GateResult(kind, False, f"deps without ticket files: {', '.join(dangling)}")
        cycle = find_dag_cycle(tickets)
        detail = f"cycle: {' -> '.join(cycle)}" if cycle else f"acyclic ({len(tickets)} tickets)"
        return GateResult(kind, cycle is None, detail)
    if kind == "command":
        argv = [str(a) for a in gate["argv"]]
        timeout_s = int(gate.get("timeout_s", 120))
        try:
            proc = subprocess.run(argv, cwd=plan, capture_output=True, text=True, timeout=timeout_s)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return GateResult(kind, False, f"{' '.join(argv)}: {exc}")
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:] if proc.returncode else []
        suffix = f" — {tail[0]}" if tail else ""
        return GateResult(
            kind, proc.returncode == 0, f"{' '.join(argv)}: exit {proc.returncode}{suffix}"
        )
    raise ValueError(f"unknown gate kind: {kind!r}")


def eval_transition(plan: Path, transition: Transition) -> tuple[bool, list[GateResult]]:
    results = [eval_gate(plan, gate) for gate in transition.gates]
    return all(r.passed for r in results), results


# ── Plan state (durable, on disk) ────────────────────────────────────────────
@dataclass
class PlanState:
    plan: Path
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return self.plan / STATE_REL

    @property
    def state(self) -> str:
        return str(self.data["state"])

    @property
    def paused(self) -> bool:
        return bool(self.data.get("paused", False))

    def record(self, event: dict[str, Any]) -> None:
        event["at"] = _now()
        self.data.setdefault("history", []).append(event)
        self.data["updated_at"] = event["at"]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")


def init_state(plan: Path, machine: Machine, brief: str, force: bool = False) -> PlanState:
    state = PlanState(plan)
    if state.path.is_file() and not force:
        raise FileExistsError(f"{state.path} already exists (use --force to reinitialise)")
    state.data = {
        "machine": machine.name,
        "machine_path": str(machine.path),
        "state": machine.initial,
        "brief": brief,
        "paused": False,
        "prompt_seq": 0,
        "last_session_id": None,
        "created_at": _now(),
        "history": [],
    }
    state.record({"event": "init", "state": machine.initial})
    state.save()
    return state


def load_state(plan: Path) -> PlanState:
    state = PlanState(plan)
    if not state.path.is_file():
        raise FileNotFoundError(f"no state at {state.path} — run `pgsm init` first")
    state.data = json.loads(state.path.read_text(encoding="utf-8"))
    return state


def load_machine_for(state: PlanState, override: Path | None = None) -> Machine:
    return load_machine(override or Path(str(state.data["machine_path"])))


# ── Composition: root → leaf document path ───────────────────────────────────
def _render_file(plan: Path, path: Path) -> str:
    rel = path.relative_to(plan) if path.is_relative_to(plan) else path
    return f"═══ FILE: {rel} ═══\n{path.read_text(encoding='utf-8').rstrip()}\n"


def compose_context(plan: Path, selectors: list[str], ticket: Ticket | None = None) -> str:
    """Append the document tree path root→leaf into one consolidated context block."""
    chunks: list[str] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        if path.is_file() and path not in seen:
            seen.add(path)
            chunks.append(_render_file(plan, path))

    for selector in selectors:
        if selector == "index":
            add(plan / "README.md")
        elif selector == "discovery":
            add(plan / "DISCOVERY.md")
        elif selector == "all_gaps":
            for path in gap_files(plan):
                add(path)
        elif selector == "gaps_with_markers":
            for path in gap_files(plan):
                text = path.read_text(encoding="utf-8")
                if any(marker in text for marker in OPEN_MARKERS):
                    add(path)
        elif selector == "ticket_path":
            add(plan / "README.md")
            if ticket is not None:
                add(plan / f"G{ticket.gap}.md")
                add(ticket.path)
        else:
            raise ValueError(f"unknown compose selector: {selector!r}")
    return "\n".join(chunks)


def gate_report(plan: Path, state_def: StateDef) -> str:
    """Human/agent-readable exit-gate status — the objective function for this state."""
    if not state_def.transitions:
        return "Terminal state — no exit gates."
    lines: list[str] = []
    for transition in state_def.transitions:
        passed, results = eval_transition(plan, transition)
        lines.append(f"→ {transition.to}: {'READY' if passed else 'blocked'}")
        for result in results:
            lines.append(
                f"  [{'PASS' if result.passed else 'FAIL'}] {result.kind}: {result.detail}"
            )
    return "\n".join(lines)


def build_prompt(plan: Path, machine: Machine, state: PlanState) -> str:
    state_def = machine.state(state.state)
    resource_text = (machine.root / state_def.resource).read_text(encoding="utf-8").rstrip()
    ticket = (
        next_eligible_ticket(load_tickets(plan)) if "ticket_path" in state_def.compose else None
    )
    sections = [
        f"# {machine.name} state machine — state: {state.state}",
        f"Plan directory: `{plan}`. Initiative brief: {state.data.get('brief') or '(none recorded)'}",
        "You are executing ONE turn of a script-managed state machine. The script — not you — owns "
        "phase tracking and transitions. Do the work this state's instructions describe, then STOP. "
        "Never edit `.pgsm/state.json` or `.pgsm/prompts/`; write under `.pgsm/receipts/` only when "
        "the state instructions direct it. "
        "After you stop, the driver runs `pgsm next` to evaluate the evidence gates below.",
        "## State instructions\n\n" + resource_text,
        "## Exit gates (evidence the script checks after your turn)\n\n```\n"
        + gate_report(plan, state_def)
        + "\n```",
    ]
    if ticket is not None:
        sections.append(
            f"## Assigned ticket\n\nWork exactly one ticket this turn: **{ticket.tid}** (`{ticket.path.name}`)."
        )
    elif "ticket_path" in state_def.compose:
        sections.append(
            "## Assigned ticket\n\nNo eligible ticket found — re-check the Progress table and dependency states."
        )
    context = compose_context(plan, state_def.compose, ticket)
    if context:
        sections.append("## Composed context (root → leaf)\n\n" + context)
    return "\n\n".join(sections) + "\n"


def log_prompt(state: PlanState, prompt: str, session_id: str | None) -> Path:
    seq = int(state.data.get("prompt_seq", 0)) + 1
    state.data["prompt_seq"] = seq
    prompts_dir = state.plan / PROMPTS_REL
    prompts_dir.mkdir(parents=True, exist_ok=True)
    path = prompts_dir / f"{seq:04d}-{state.state}.md"
    path.write_text(prompt, encoding="utf-8")
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if session_id:
        state.data["last_session_id"] = session_id
    state.record(
        {
            "event": "prompt",
            "seq": seq,
            "state": state.state,
            "sha256": digest,
            "path": str(path),
            "session_id": session_id,
        }
    )
    state.save()
    return path


# ── Engine operations ────────────────────────────────────────────────────────
def advance(
    plan: Path, machine: Machine, state: PlanState, dry_run: bool = False
) -> dict[str, Any]:
    """Evaluate the current state's transitions in order; fire the first fully-passed one."""
    if state.paused:
        return {
            "state": state.state,
            "transitioned": False,
            "paused": True,
            "terminal": False,
            "transitions": [],
        }
    state_def = machine.state(state.state)
    report: list[dict[str, Any]] = []
    fired: str | None = None
    for transition in state_def.transitions:
        passed, results = eval_transition(plan, transition)
        report.append(
            {"to": transition.to, "passed": passed, "gates": [r.as_dict() for r in results]}
        )
        if passed and fired is None:
            fired = transition.to
            if not dry_run:
                state.record(
                    {
                        "event": "transition",
                        "from": state.state,
                        "to": transition.to,
                        "evidence": [r.as_dict() for r in results],
                    }
                )
                state.data["state"] = transition.to
                state.save()
            break
    return {
        "state": state.state,
        "transitioned": fired is not None,
        "to": fired,
        "paused": False,
        "terminal": state.state in machine.terminal,
        "transitions": report,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────
def cmd_init(args: argparse.Namespace) -> None:
    plan = Path(args.plan)
    plan.mkdir(parents=True, exist_ok=True)
    machine = load_machine(Path(args.machine))
    state = init_state(plan, machine, brief=args.brief or "", force=args.force)
    print(f"initialised {machine.name} at {state.path} (state: {state.state})")


def cmd_status(args: argparse.Namespace) -> None:
    plan = Path(args.plan)
    state = load_state(plan)
    machine = load_machine_for(state)
    state_def = machine.state(state.state)
    if args.json:
        payload = {
            "machine": machine.name,
            "state": state.state,
            "paused": state.paused,
            "terminal": state.state in machine.terminal,
            "prompt_seq": state.data.get("prompt_seq", 0),
            "last_session_id": state.data.get("last_session_id"),
            "updated_at": state.data.get("updated_at"),
            "history_len": len(state.data.get("history", [])),
        }
        print(json.dumps(payload, indent=2))
        return
    print(f"machine:  {machine.name} ({machine.path})")
    flags = (" [PAUSED]" if state.paused else "") + (
        " [TERMINAL]" if state.state in machine.terminal else ""
    )
    print(f"state:    {state.state}{flags}")
    print(f"brief:    {state.data.get('brief') or '(none)'}")
    print(
        f"updated:  {state.data.get('updated_at')}  prompts emitted: {state.data.get('prompt_seq', 0)}"
    )
    print(f"session:  {state.data.get('last_session_id') or '(none recorded)'}")
    print()
    print(gate_report(plan, state_def))


def cmd_next(args: argparse.Namespace) -> None:
    plan = Path(args.plan)
    state = load_state(plan)
    machine = load_machine_for(state)
    result = advance(plan, machine, state, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    if result["paused"]:
        print("machine is paused — `pgsm resume` first")
    elif result["transitioned"]:
        print(
            f"transitioned: {result['state']} → {result['to']}"
            + (" (dry-run, not recorded)" if args.dry_run else "")
        )
    elif result["terminal"]:
        print(f"state {result['state']} is terminal — nothing to do")
    else:
        print(f"holding in {result['state']} — failing gates:")
        for transition in result["transitions"]:
            for gate in transition["gates"]:
                if not gate["passed"]:
                    print(f"  → {transition['to']}  [FAIL] {gate['kind']}: {gate['detail']}")


def cmd_prompt(args: argparse.Namespace) -> None:
    plan = Path(args.plan)
    state = load_state(plan)
    if state.paused:
        raise SystemExit("error: machine is paused — `pgsm resume` first")
    machine = load_machine_for(state)
    prompt = build_prompt(plan, machine, state)
    if not args.no_log:
        path = log_prompt(state, prompt, args.session_id)
        log.info("prompt logged to %s", path)
    print(prompt, end="")


def cmd_compose(args: argparse.Namespace) -> None:
    plan = Path(args.plan)
    if args.ticket:
        tickets = [t for t in load_tickets(plan) if t.tid == args.ticket]
        if not tickets:
            raise SystemExit(f"error: no ticket {args.ticket!r} in {plan}")
        print(compose_context(plan, ["ticket_path"], tickets[0]), end="")
        return
    selectors = args.select or ["index"]
    print(compose_context(plan, selectors), end="")


def _set_paused(plan_arg: str, paused: bool) -> None:
    state = load_state(Path(plan_arg))
    state.data["paused"] = paused
    state.record({"event": "pause" if paused else "resume"})
    state.save()
    print(f"{'paused' if paused else 'resumed'} at state {state.state}")


def cmd_pause(args: argparse.Namespace) -> None:
    _set_paused(args.plan, True)


def cmd_resume(args: argparse.Namespace) -> None:
    _set_paused(args.plan, False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pgsm", description="Config-driven gap-analysis state machine"
    )

    def _help(p: argparse.ArgumentParser) -> Any:
        def _print_help(_: argparse.Namespace) -> None:
            p.print_help()

        return _print_help

    parser.set_defaults(func=_help(parser))
    sub = parser.add_subparsers(dest="cmd", required=False)

    p_init = sub.add_parser("init", help="Initialise machine state for a plan directory")
    p_init.add_argument("plan")
    p_init.add_argument("--machine", default=str(DEFAULT_MACHINE), help="Path to machine TOML")
    p_init.add_argument("--brief", default="", help="One-sentence initiative brief")
    p_init.add_argument("--force", action="store_true", help="Reinitialise over existing state")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="Show current state and exit-gate evaluation")
    p_status.add_argument("plan")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_next = sub.add_parser("next", help="Evaluate gates; fire the first fully-passed transition")
    p_next.add_argument("plan")
    p_next.add_argument("--dry-run", action="store_true", help="Evaluate without recording")
    p_next.add_argument("--json", action="store_true")
    p_next.set_defaults(func=cmd_next)

    p_prompt = sub.add_parser("prompt", help="Emit the composed prompt for the current state")
    p_prompt.add_argument("plan")
    p_prompt.add_argument(
        "--session-id", default=None, help="Session id to record against this prompt"
    )
    p_prompt.add_argument(
        "--no-log", action="store_true", help="Do not write a .pgsm/prompts/ copy"
    )
    p_prompt.set_defaults(func=cmd_prompt)

    p_compose = sub.add_parser("compose", help="Emit the root→leaf document composition only")
    p_compose.add_argument("plan")
    p_compose.add_argument(
        "--ticket", default=None, help="Compose index→gap→ticket for ticket id (e.g. T2.1)"
    )
    p_compose.add_argument(
        "--select",
        nargs="*",
        default=None,
        help="Selectors: index discovery all_gaps gaps_with_markers",
    )
    p_compose.set_defaults(func=cmd_compose)

    p_pause = sub.add_parser("pause", help="Pause the machine (next/prompt refuse until resume)")
    p_pause.add_argument("plan")
    p_pause.set_defaults(func=cmd_pause)

    p_resume = sub.add_parser("resume", help="Resume a paused machine")
    p_resume.add_argument("plan")
    p_resume.set_defaults(func=cmd_resume)

    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
