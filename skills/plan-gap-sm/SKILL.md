---
name: plan-gap-sm
description: "Script-driven gap-analysis planning: a deterministic state machine (pgsm.py) owns the phases of a tiered gap-analysis spec — bootstrap → refinement → validation → decomposition → execution → complete — with evidence-based transition gates, per-state-only instructions composed into a single prompt, durable pause/resume state, and session-log forensics. Use for long-horizon work-breakdown planning where phase tracking must not live in the model's head. Requires uv. Skip for quick single-file plans (use plan-gap) or when no plan document is wanted."
argument-hint: "<path-to-plan-folder/>"
user-invocable: true
---

# Gap Analysis Planning — State Machine Mode

The sibling `plan-gap` skill asks the model to track phases by reading playbooks at the right
moments. This skill inverts that: **the script owns the state**. `scripts/pgsm.py` evaluates
deterministic evidence gates against the plan directory, fires transitions, and composes the exact
prompt for the current state — the state's instructions plus the root→leaf document path — so the
executing agent receives one consolidated context block instead of spending tool calls discovering
it. Every emitted prompt is logged with its sha256, making "what text actually loaded" auditable
against the session transcript.

## Quick start

```bash
# 1. Initialise machine state for a plan folder (creates <plan>/.pgsm/state.json)
uv run .claude/skills/plan-gap-sm/scripts/pgsm.py init docs/plans/my-initiative \
  --brief "One-sentence initiative description"

# 2. Each turn: get the composed prompt for the current state, do exactly that work, stop
uv run .claude/skills/plan-gap-sm/scripts/pgsm.py prompt docs/plans/my-initiative

# 3. After the work: evaluate evidence gates; the first fully-passed transition fires
uv run .claude/skills/plan-gap-sm/scripts/pgsm.py next docs/plans/my-initiative

# Anytime: current state + live gate evaluation (the remaining work list)
uv run .claude/skills/plan-gap-sm/scripts/pgsm.py status docs/plans/my-initiative
```

## Operating protocol (for the agent)

When invoked as `/plan-gap-sm <plan-dir>`:

1. If `<plan-dir>/.pgsm/state.json` does not exist, ask the user for a one-sentence brief (or take
   it from the invocation) and run `pgsm init`.
2. Set the session goal to: *"drive the plan at `<plan-dir>` until `pgsm status` reports a terminal
   state or a question requires the user"* — execution is goal-driven (`/goal`), not a
   self-scheduled loop; the machine's gate evaluation is the stop condition.
3. Each turn, run `pgsm prompt <plan-dir> --session-id "${CLAUDE_SESSION_ID}"` and do ONLY what the
   emitted prompt says. The prompt inlines the current state's instructions and the composed
   document context — do not re-read playbooks or other plan tiers on your own.
4. After the state's work, run `pgsm next <plan-dir>`. If it transitions, continue with the new
   state's prompt. If it holds, the listed `[FAIL]` gates are your remaining work for this state.
5. In `refinement`, asking the user the one ranked question and waiting IS the correct behaviour —
   the machine stays put until markers resolve. Resuming days later in a fresh session is free:
   state lives on disk, `pgsm status` re-orients you.
6. Never edit `.pgsm/state.json` or `.pgsm/prompts/`; write `.pgsm/receipts/` files only when a
   state's instructions direct it.

## Command reference

| Command | Purpose |
|---------|---------|
| `pgsm.py init <plan> --brief "…" [--machine TOML] [--force]` | Create durable machine state for a plan folder |
| `pgsm.py status <plan> [--json]` | Current state + live exit-gate evaluation |
| `pgsm.py next <plan> [--dry-run] [--json]` | Evaluate gates; fire the first fully-passed transition (evidence recorded in history) |
| `pgsm.py prompt <plan> [--session-id ID] [--no-log]` | Emit the composed prompt for the current state; logs a copy to `.pgsm/prompts/` with sha256 |
| `pgsm.py compose <plan> [--ticket T2.1] [--select …]` | Emit only the root→leaf document composition |
| `pgsm.py pause <plan>` / `resume <plan>` | Freeze/unfreeze the machine (`next`/`prompt` refuse while paused) |
| `trajectory.py --session-id ID [--watch PREFIX] [--prompts-dir <plan>/.pgsm/prompts] [--json]` | Session-log forensics: real file loads, token/time costs, tool-failure rate, emitted-prompt delivery check |
| `rollout.py gold-extract --repo R --base B --gold G` | Derive the hidden gold milestone set from a completed feature branch |
| `rollout.py run --config evals/rollouts/<cfg>.toml` | Long-trajectory eval: worktree per model, gold tracking, early-abandon gates |
| `rollout.py status` | Effectiveness-over-time history (results.jsonl) |

All scripts run from the repo root via `uv run` — never `cd`.

## The machine

Defined in `resources/machines/plan-gap.toml` (the engine is generic; states, transitions, and
gates are pure data — new machines are new TOML files, not new code):

| State | Work | Exit evidence (script-checked) |
|-------|------|--------------------------------|
| `bootstrap` | dual research → index + discovery + gap stubs | files exist, diagrams present, no TODO outside Execution Plan |
| `refinement` | one ranked question at a time | zero `UNRESOLVED` / `CHANGE-REQUEST` / `ASSUMPTION` markers |
| `validation` | diagram + requirement-integrity + consistency gates | `.pgsm/receipts/validation.json` + marker/diagram checks |
| `decomposition` | TDD vertical-slice tickets + Execution Plan | every gap ticketed, DAG acyclic, no TODO in index |
| `execution` | one ticket per turn, red→green→refactor | all tickets `[x]`; markers route back to `refinement` |
| `complete` | terminal | a new `UNRESOLVED` marker deliberately re-opens to `refinement` |

Per-state instructions live in `resources/states/<state>.md` and are **inlined into the prompt** —
only the current state's instructions ever load, never the whole playbook set.

## Resources

| File | Purpose |
|------|---------|
| `resources/machines/plan-gap.toml` | The state machine definition (states, transitions, evidence gates) |
| `resources/states/*.md` | Per-state operative instructions, one file per state |
| `scripts/evals/rollouts/example.toml` | Rollout config template — the gold-branch eval protocol |
| `scripts/evals/goldens/cases.toml` | Single-turn golden eval cases (`make evals`) |

Maintainer rationale and the ADR log live in `CLAUDE.md`; the human-facing overview with
architecture diagrams lives in `README.md`.
