"""Eval: does the mermaidjs-diagrams skill's palette mandate actually get applied?

This is the harness's reference case. It is deliberately small -- one fixture, one
sentence of task -- but it exercises every layer in a single cell, so a green run here
is evidence that the whole pipeline works end to end:

    invoke the skill the way a user does  ->  capture the CLI's own session log
    ->  price it  ->  compare what it left behind to a golden  ->  report

Read it top to bottom as a tutorial on what an eval can assert and why.

## Why this case has a golden

The fixture is one four-node flowchart, so a correct answer is very nearly determined:
the skill mandates an explicit ``classDef`` per node group with fill and text colour from
its own palette, and the fixture fixes which nodes exist. We can write down what right
looks like -- ``goldens/unstyled_diagram/ARCHITECTURE.md``, which passes the skill's own
contrast and complexity gates.

What we cannot write down is the *one* right answer: the class names, the exact hex
values on a palette ramp, and the whitespace are all legitimately the agent's. So the
golden is compared facet by facet, and each facet declares how free it is (ADR 0046).
The tolerances below are the interesting content of this eval -- they are the actual
claim about what the skill guarantees.
"""

from __future__ import annotations

from pathlib import Path

from pytest_xharness_eval import CaseOutput, evalcase
from pytest_xharness_eval.verify import (
    Count,
    Exact,
    Facet,
    GoldenCase,
    Ratio,
    Superset,
    check_files_written,
    check_no_files_added,
    check_rollout,
    check_skill_was_loaded,
    facets,
)

SKILL = "mermaidjs-diagrams"
FIXTURE = "unstyled_diagram"  # evals/fixtures/unstyled_diagram/
TARGET = "ARCHITECTURE.md"
EVALS = Path(__file__).resolve().parent

# The task is what a user types *after* naming the skill, and nothing more (ADR 0044).
# It matches the skill's own `argument-hint: "[markdown-file]"`, so this is literally what
# a human would run: `/mermaidjs-diagrams ARCHITECTURE.md ...` on Claude Code,
# `$mermaidjs-diagrams ARCHITECTURE.md ...` on Codex. It does not mention SKILL.md, an
# allowed directory, or a CLI -- registering and naming the skill is the harness's job.
#
# The two constraints that remain are about the *measurement*, not the harness: without
# "edit in place" an agent can satisfy every check by writing a second, styled copy and
# leaving the original exactly as unstyled as it found it; without "no images" the cell
# pays for a headless render that this case does not grade.
TASK = "ARCHITECTURE.md -- apply the mandatory colour theming to its diagram, editing the file in place. Do not add new files and do not render images."


# -- The golden, and what each part of it is allowed to vary --------------------------

GOLDEN = GoldenCase.at(
    EVALS,
    FIXTURE,
    TARGET,
    [
        Facet(
            name="mermaid fences",
            extract=facets.fence_count,
            tolerance=Exact(),
            why="the one fence must be styled in place -- not replaced, and not duplicated into a styled copy",
        ),
        Facet(
            name="node ids",
            extract=facets.node_ids,
            tolerance=Exact(),
            why="this is a styling task: the fixture fixes which nodes exist, so renaming one is a different diagram",
        ),
        Facet(
            name="edges",
            extract=facets.edges,
            tolerance=Exact(),
            why="likewise the shape -- colouring a diagram must not rewire it",
        ),
        Facet(
            name="unstyled nodes",
            extract=facets.unstyled_nodes,
            tolerance=Count(lo=0, hi=0),
            why=(
                "the mandate's actual claim: NO node is left on Mermaid's default. "
                "'a classDef exists' is satisfied by styling one node of four"
            ),
        ),
        Facet(
            name="classDef groups",
            extract=facets.classdef_count,
            tolerance=Count(lo=2, hi=6),
            why=(
                "colour must encode the meaningful categories (SKILL.md), and these four nodes "
                "have distinct roles -- one class for all of them encodes nothing"
            ),
        ),
        Facet(
            name="explicit fills",
            extract=facets.fill_colours,
            tolerance=Count(lo=2, hi=6),
            why="every group carries its own fill; the exact hex is the agent's to pick off the palette ramp",
        ),
        Facet(
            name="explicit text colours",
            extract=facets.text_colours,
            tolerance=Count(lo=1, hi=6),
            why="color_theming.md forbids relying on the host theme's default label colour",
        ),
        Facet(
            name="headings",
            extract=facets.headings,
            tolerance=Superset(),
            why="the document around the diagram survives; a styling task must not eat the prose",
        ),
        Facet(
            name="prose",
            extract=facets.body_text,
            tolerance=Ratio(at_least=0.9),
            why="same reason, at the level of the words rather than the headings",
        ),
    ],
)


# -- The case -------------------------------------------------------------------------


@evalcase(task=TASK, skill=SKILL, fixture=FIXTURE)
def eval_palette_mandate(output: CaseOutput) -> None:
    """One cell = one (harness, model) pair invoking the skill on the fixture.

    Order matters, and it is the same order every case here uses: evidence first (a
    verdict untied to a real, billed, priced session is not a verdict), then that the
    right file changed and nothing else appeared, then that the skill was actually
    loaded -- and only then the artifact itself. A failure in an earlier step makes
    everything below it unreadable.
    """
    check_rollout(output)
    check_files_written(output, TARGET)
    check_no_files_added(output)
    # Producing the right answer without reaching the skill's own material is a real
    # outcome, and a different one from the outcome this case exists to measure.
    # Not SKILL.md: a native invocation injects it, so it never shows up as a read
    # (ADR 0044). color_theming.md is what SKILL.md sends the agent to, so reaching it
    # is the evidence that the mandate was followed rather than guessed at.
    check_skill_was_loaded(output, "resources/color_theming.md")
    GOLDEN.assert_matches(output)
