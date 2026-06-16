#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "deepeval>=2.0"]
# ///
"""Base eval suite for this skill — the 0->1 example.

Extend 1->many by adding [[case]] tables to goldens/cases.toml and fixture
templates under fixtures/<case>/ (_base committed, optional _head overlay =
the uncommitted diff), and by appending metrics (e.g. judged GEval) to the
assert_test list. Contract: .claude/rules/claude_skills/evals.md.

The harness runs in a guaranteed Tier A dev/CI environment (pytest + deepeval
assumed). Golden runs need the claude CLI and auth — either ANTHROPIC_API_KEY
(API billing) or your logged-in subscription (OAuth/keychain), so cheap-model
trial runs work before any API key exists. Without the CLI they skip loudly
(the paid, environment-gated tier — ci stays $0).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tomllib
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

EVALS_DIR = Path(__file__).parent.resolve()
SKILL_DIR = EVALS_DIR.parents[1]  # .claude/skills/<name>
REPO_ROOT = EVALS_DIR.parents[4]
sys.path.insert(0, str(EVALS_DIR.parents[2] / "_evalkit"))

from evalkit import (  # noqa: E402
    git_status,
    inject_agents_md,
    make_fixture,
    run_claude_skill,
    run_codex_skill,
)

GOLDENS = tomllib.loads(
    (EVALS_DIR / "goldens" / "cases.toml").read_text(encoding="utf-8")
)["case"]
MODELS = os.environ.get("EVAL_MODELS", "claude-haiku-4-5").split(",")
# Codex joins the matrix only when requested (e.g. CODEX_EVAL_MODELS="gpt-5.5").
CODEX_MODELS = [m for m in os.environ.get("CODEX_EVAL_MODELS", "").split(",") if m]

needs_agent = pytest.mark.skipif(
    shutil.which("claude") is None,
    reason="evals need the claude CLI (auth: ANTHROPIC_API_KEY or subscription login — see evals.md)",
)
needs_codex = pytest.mark.skipif(
    shutil.which("codex") is None,
    reason="codex evals need the codex CLI on PATH",
)


class RegexCoverageMetric(BaseMetric):
    """Deterministic golden check: all must_mention regexes present, no must_not_mention.

    Score = matched assertions / total assertions; success requires a perfect score.
    """

    def __init__(self, must_mention: list[str], must_not_mention: list[str]) -> None:
        self.must_mention = must_mention
        self.must_not_mention = must_not_mention
        self.threshold = 1.0
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase) -> float:
        text = test_case.actual_output or ""
        missing = [
            p for p in self.must_mention if not re.search(p, text, re.IGNORECASE)
        ]
        forbidden = [
            p for p in self.must_not_mention if re.search(p, text, re.IGNORECASE)
        ]
        total = len(self.must_mention) + len(self.must_not_mention)
        passed = total - len(missing) - len(forbidden)
        self.score = passed / total if total else 1.0
        self.success = not missing and not forbidden
        self.reason = f"missing={missing} forbidden_hits={forbidden}"
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self) -> str:  # noqa: PLW3201
        return "RegexCoverage"


@needs_agent
@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("golden", GOLDENS, ids=[g["id"] for g in GOLDENS])
def test_golden(golden: dict, model: str) -> None:
    # No '@' or '.' in run dirs — Claude's transcript slug normalizes them
    # unpredictably (found 2026-06: '@' produced silently-empty traces).
    run_dir = (
        REPO_ROOT
        / "tmp"
        / "evals"
        / SKILL_DIR.name
        / f"{golden['id']}-{model.replace('.', '-')}"
    )
    fixture = make_fixture(
        EVALS_DIR / "fixtures" / golden["fixture"], run_dir, SKILL_DIR
    )
    status_before = git_status(fixture)

    res = run_claude_skill(
        golden["prompt"], fixture, model, golden.get("max_cost_usd", 1.0)
    )

    # Side-effect contract: plain asserts (not about LLM output quality).
    assert res.returncode == 0, (
        f"claude exited {res.returncode}\n{res.raw_stdout[:2000]}\n{res.raw_stderr[:500]}"
    )
    if golden.get("files_unchanged"):
        assert git_status(fixture) == status_before, (
            "skill modified the fixture working tree"
        )
    assert res.trace.tool_calls, (
        "no tool calls in transcript — the skill never inspected the repo"
    )
    assert res.total_cost_usd <= golden.get("max_cost_usd", 1.0), (
        f"cost {res.total_cost_usd}"
    )

    # Output-quality contract: deepeval metrics. Append GEval judges here for 1->many.
    test_case = LLMTestCase(input=golden["prompt"], actual_output=res.result_text)
    metrics: list[BaseMetric] = [
        RegexCoverageMetric(golden["must_mention"], golden.get("must_not_mention", [])),
    ]
    assert_test(test_case, metrics, run_async=False)


@needs_codex
@pytest.mark.parametrize("model", CODEX_MODELS)
@pytest.mark.parametrize("golden", GOLDENS, ids=[g["id"] for g in GOLDENS])
def test_golden_codex(golden: dict, model: str) -> None:
    """Same goldens through codex exec — the skill rides in as AGENTS.md."""
    run_dir = (
        REPO_ROOT
        / "tmp"
        / "evals"
        / SKILL_DIR.name
        / f"{golden['id']}-codex-{model.replace('.', '-')}"
    )
    fixture = make_fixture(
        EVALS_DIR / "fixtures" / golden["fixture"], run_dir, SKILL_DIR
    )
    inject_agents_md(fixture, SKILL_DIR)
    status_before = git_status(fixture)

    # Codex has no /skill-name expansion: strip the slash command and point at AGENTS.md.
    prompt = golden.get(
        "codex_prompt",
        "Follow the skill instructions in AGENTS.md. "
        + re.sub(r"^/\S+\s*", "", golden["prompt"]),
    )
    res = run_codex_skill(prompt, fixture, model)

    assert res.returncode == 0, (
        f"codex exited {res.returncode}\n{res.raw_stdout[:2000]}\n{res.raw_stderr[:500]}"
    )
    if golden.get("files_unchanged"):
        assert git_status(fixture) == status_before, (
            "skill modified the fixture working tree"
        )

    test_case = LLMTestCase(input=prompt, actual_output=res.result_text)
    metrics: list[BaseMetric] = [
        RegexCoverageMetric(golden["must_mention"], golden.get("must_not_mention", [])),
    ]
    assert_test(test_case, metrics, run_async=False)


if __name__ == "__main__":  # pragma: no cover
    here = str(EVALS_DIR)
    sys.exit(
        pytest.main(
            [__file__, "-v", "--rootdir", here, "-o", "addopts="] + sys.argv[1:]
        )
    )
