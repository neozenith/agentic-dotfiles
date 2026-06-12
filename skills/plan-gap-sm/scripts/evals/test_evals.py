#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "deepeval>=2.0"]
# ///
"""Golden evals for plan-gap-sm — REAL agent runs, costs money. Never part of `make ci`.

Each golden drives ONE state-machine turn: build the hermetic fixture, init the
machine, force the case's state, compose the prompt with pgsm (self-contained —
no skill resolution needed inside the fixture), run `claude -p` via _evalkit,
then score with deterministic deepeval metrics (file existence, content checks,
cost ceilings). Model matrix via EVAL_MODELS (comma-separated full model ids).

Run: make -C .claude/skills/plan-gap-sm/scripts evals
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
import uuid
from pathlib import Path
from typing import Any

import pytest
from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

SCRIPT_DIR = Path(__file__).parent.resolve()
SCRIPTS_DIR = SCRIPT_DIR.parent
SKILL_DIR = SCRIPTS_DIR.parent
REPO_ROOT = SKILL_DIR.parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SKILL_DIR.parent / "_evalkit"))
import evalkit  # noqa: E402
import pgsm  # noqa: E402

EVAL_MODELS = os.environ.get("EVAL_MODELS", "claude-haiku-4-5").split(",")
CASES = tomllib.loads((SCRIPT_DIR / "goldens" / "cases.toml").read_text(encoding="utf-8"))["case"]


class DeterministicChecks(BaseMetric):
    """deepeval metric wrapping precomputed (name, passed, detail) checks."""

    def __init__(self, checks: list[tuple[str, bool, str]]) -> None:
        self.checks = checks
        self.threshold = 1.0

    def measure(self, test_case: LLMTestCase) -> float:
        passed = sum(1 for _, ok, _ in self.checks if ok)
        self.score = passed / len(self.checks) if self.checks else 1.0
        self.success = self.score >= self.threshold
        self.reason = "; ".join(
            f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}" for name, ok, detail in self.checks
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(getattr(self, "success", False))

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "DeterministicChecks"


def run_case(case: dict[str, Any], model: str) -> tuple[Path, Any, str]:
    fixture_dir = SCRIPT_DIR / "fixtures" / str(case["fixture"])
    dest = REPO_ROOT / "tmp" / "evals" / f"{case['name']}-{model}-{uuid.uuid4().hex[:8]}"
    evalkit.make_fixture(fixture_dir, dest, SKILL_DIR)
    plan = dest / str(case["plan_dir"])
    plan.mkdir(parents=True, exist_ok=True)
    machine = pgsm.load_machine(pgsm.DEFAULT_MACHINE)
    state = pgsm.init_state(plan, machine, brief=str(case["brief"]), force=True)
    if state.state != case["state"]:
        state.data["state"] = str(case["state"])
        state.save()
        state = pgsm.load_state(plan)
    prompt = pgsm.build_prompt(plan, machine, state)
    result = evalkit.run_claude_skill(
        prompt, cwd=dest, model=model, max_budget_usd=float(case["max_budget_usd"]), timeout_s=900
    )
    return dest, result, prompt


def score_case(case: dict[str, Any], dest: Path, result: Any) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = [
        ("exit_code", result.returncode == 0, f"returncode={result.returncode}")
    ]
    for rel in case.get("must_exist", []):
        path = dest / str(rel)
        checks.append((f"exists:{rel}", path.is_file(), "ok" if path.is_file() else "missing"))
    for rel, needle in case.get("must_contain", []):
        path = dest / str(rel)
        ok = path.is_file() and str(needle) in path.read_text(encoding="utf-8")
        checks.append((f"contains:{rel}", ok, f"needle={needle!r}"))
    plan = dest / str(case["plan_dir"])
    for pattern, minimum in case.get("glob_min", []):
        count = len(list(plan.glob(str(pattern)))) if plan.is_dir() else 0
        checks.append((f"glob:{pattern}", count >= int(minimum), f"{count} >= {minimum}"))
    max_cost = float(case.get("max_cost_usd", 1.0))
    checks.append(
        (
            "cost_ceiling",
            result.total_cost_usd <= max_cost,
            f"${result.total_cost_usd:.2f} <= ${max_cost}",
        )
    )
    return checks


@pytest.mark.parametrize("model", EVAL_MODELS)
@pytest.mark.parametrize("case", CASES, ids=[str(c["name"]) for c in CASES])
def test_golden(case: dict[str, Any], model: str) -> None:
    dest, result, prompt = run_case(case, model)
    checks = score_case(case, dest, result)
    (dest / "eval-checks.json").write_text(
        json.dumps([{"name": n, "passed": p, "detail": d} for n, p, d in checks], indent=2) + "\n",
        encoding="utf-8",
    )
    test_case = LLMTestCase(input=prompt[:2000], actual_output=result.result_text[:4000])
    assert_test(test_case, [DeterministicChecks(checks)])


if __name__ == "__main__":  # pragma: no cover
    base_args = [__file__, "-v", "--rootdir", str(SCRIPT_DIR), "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
