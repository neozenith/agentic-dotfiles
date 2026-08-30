"""Eval: does the discovery skill produce a grounded Current/Desired State document?

The fixture is a small but real codebase (`legacy_pipeline`: a nightly CSV -> HTML
batch job with documented pain). The agent must run the skill's whole loop - internal
research over that code, external research, synthesis - and leave behind the one
artifact the skill exists for: a DISCOVERY.md whose two state sections are drawn
through the same lenses with shared node IDs, and whose claims trace to file:line
citations or URLs. This is also the reference case for a skill that spawns research
subagents, so the ledger is asserted to show that delegation actually happened.
"""

import re
from pathlib import Path

from pytest_xharness_eval import RunResult, evalcase

SKILL = "discovery"
FIXTURE = "legacy_pipeline"  # evals/fixtures/legacy_pipeline/

# The prompt pins the target (DISCOVERY.md at the workspace root), gives the one-line
# brief the skill asks for, and keeps the run affordable: two lenses, and the
# validation step must not fail the run when mmdc or a browser is unavailable in the
# sandbox - the document is what is graded here, not the toolchain around it.
PROMPT = (
    "Use the discovery skill (its SKILL.md is in the extra allowed directory / your "
    "skills). Target: DISCOVERY.md at the repository root (it does not exist yet). "
    "Initiative brief: replace the in-memory nightly orders batch (pipeline/) with a "
    "streaming, fault-tolerant, observable pipeline. Use exactly two lenses. Keep "
    "external research brief: a handful of authoritative sources is enough; if no "
    "browser or fetch tool is available, mark links per the skill instead of "
    "stopping. If mmdc is unavailable, skip the render step. Write only "
    "DISCOVERY.md; do not add other files."
)

# -- Section and diagram parsing (verifiers live beside the case, ADR 0013) --

SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
FENCE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
# `flowchart` node ids at the start of an edge or definition: `Loader[...]`, `A --> B`.
NODE_ID = re.compile(r"(?:^|\s)([A-Za-z][A-Za-z0-9_]*)\s*(?:\[|\(|\{)", re.MULTILINE)
CITATION = re.compile(r"[\w/]+\.(?:py|md):\d+")


def sections_of(doc: str) -> dict[str, str]:
    """Map `## Heading` -> body text (up to the next `##`)."""
    parts = SECTION.split(doc)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def node_ids(mermaid_bodies: list[str]) -> set[str]:
    ids: set[str] = set()
    for body in mermaid_bodies:
        ids.update(NODE_ID.findall(body))
    return ids - {"classDef", "class", "subgraph", "flowchart", "graph", "sequenceDiagram", "stateDiagram"}


# -- Check 1: the run is real evidence ---------------------------------------


def check_run_is_real(run: RunResult) -> None:
    """Same gate as every eval: the verdict must be tied to a session that happened."""
    assert run.session_id, "no session id - the run cannot prove which log is its own"
    assert Path(run.session_log).is_file(), f"session log missing: {run.session_log}"
    assert run.exit_code == 0, f"agent CLI exited {run.exit_code}"
    assert run.usage.accumulative_billed_tokens > 0, "zero tokens - an empty run must never pass"
    assert run.cost_status == "priced", f"run was not priced (status={run.cost_status})"


# -- Check 2: the research was delegated -------------------------------------


def check_research_was_delegated(run: RunResult) -> None:
    """Step 2 of the skill is two parallel research subagents; the ledger must show it.

    Only the Claude CLI exposes a subagent tool the ledger can name (Task/Agent);
    Codex runs the research in its own loop, so the assertion is harness-scoped
    rather than pretending both CLIs look alike.
    """
    if run.harness != "claude":
        return
    spawned = sum(count for name, count in run.tool_calls.items() if name in {"Task", "Agent"})
    assert spawned >= 2, f"the skill mandates parallel research subagents; ledger shows {spawned} spawn(s) ({run.tool_calls})"


# -- Check 3: the document is the skill's contract ---------------------------


def check_document_contract(run: RunResult, workspace: Path) -> None:
    """DISCOVERY.md exists with paired, citation-grounded state sections.

    Coarse to fine: the file was written, both sections exist, each carries the
    same number of lens diagrams (1-3), the pairs share node IDs so they read as a
    before/after, Current State cites the fixture's code, Desired State points at
    external sources (verified or explicitly marked).
    """
    doc_path = workspace / "DISCOVERY.md"
    assert "DISCOVERY.md" in run.files_written, f"agent did not write DISCOVERY.md (files written: {run.files_written})"
    doc = doc_path.read_text(encoding="utf-8")
    sections = sections_of(doc)

    current = next((body for name, body in sections.items() if name.lower().startswith("current state")), None)
    desired = next((body for name, body in sections.items() if name.lower().startswith("desired state")), None)
    assert current, f"no `## Current State` section (sections: {list(sections)})"
    assert desired, f"no `## Desired State` section (sections: {list(sections)})"

    current_diagrams = FENCE.findall(current)
    desired_diagrams = FENCE.findall(desired)
    assert 1 <= len(current_diagrams) <= 3, f"Current State has {len(current_diagrams)} mermaid diagrams; the skill wants 2-3 lenses (>=1 accepted)"
    assert len(current_diagrams) == len(desired_diagrams), (
        f"lens mismatch: {len(current_diagrams)} Current vs {len(desired_diagrams)} Desired diagrams - the pairs must share lenses"
    )

    shared = node_ids(current_diagrams) & node_ids(desired_diagrams)
    assert shared, "no node ID appears in both a Current and a Desired diagram - the before/after cannot be read as a diff"

    assert CITATION.search(current), "Current State has no file:line citation into the fixture codebase"
    has_url = "http://" in desired or "https://" in desired
    assert has_url or "LINK_NOT_VERIFIED" in doc, "Desired State names no external source and carries no unverified-link marker"


# -- The case ----------------------------------------------------------------


@evalcase(prompt=PROMPT, skill=SKILL, fixture=FIXTURE)
def eval_discovery_document(run: RunResult, workspace: Path) -> None:
    """Evidence first, delegation second, the document's contract last."""
    check_run_is_real(run)
    check_research_was_delegated(run)
    check_document_contract(run, workspace)
