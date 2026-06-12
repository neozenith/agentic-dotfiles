# plan-gap-sm — maintainer decision lens

Read the ADR log below before changing anything: each entry carries a **Lens** — an imperative
rule to apply to the next decision of its class. Usage documentation lives in `SKILL.md` (agent)
and `README.md` (human); this file holds only rationale.

## The development contract

```bash
make -C .claude/skills/plan-gap-sm/scripts fix   # mutates: format + lint-fix
make -C .claude/skills/plan-gap-sm/scripts ci    # gate: format-check, lint, mypy --strict, test-cov ≥90% — must be 0-exit
```

`make … evals` (single-turn goldens) and `rollout.py run` (long trajectories) spend real money and
are never part of `ci`.

## File map

| File | Role |
|------|------|
| `resources/machines/plan-gap.toml` | The machine: states, transitions, evidence gates — pure data |
| `resources/states/*.md` | Per-state operative instructions, inlined into composed prompts |
| `scripts/pgsm.py` | Generic engine: gate evaluation, durable state, prompt composition, CLI |
| `scripts/trajectory.py` | Session-jsonl forensics: real file loads, tokens, tool failures, prompt-delivery check |
| `scripts/rollout.py` | Long-trajectory eval: worktree per model, gold-milestone tracking, abandon gates |
| `scripts/evals/goldens/cases.toml` | Single-turn golden cases (state → deterministic checks) |
| `scripts/evals/fixtures/*/_base/` | Seeded fixture projects for the goldens |
| `scripts/evals/rollouts/example.toml` | Documented rollout config template (gold-branch protocol) |
| `scripts/evals/test_evals.py` | Paid golden runner (pytest + deepeval, EVAL_MODELS matrix) |

## Architecture principles

- **The script owns state; the model does work.** No instruction may ask the model to decide which
  phase it is in, remember progress, or self-report a transition.
- **Gates are evidence, not assertion.** Every gate is computable from the plan directory (or a
  receipt file recording an actually-executed check). A gate that trusts model claims is a bug.
- **The machine is data.** New states, reordered phases, or project-specific gates are TOML edits;
  the engine adds gate *kinds* only when a check genuinely cannot be expressed with existing ones.
- **Composed prompts are the only instruction channel** — and every one is logged with its sha256,
  so "what text was loaded" is a byte-level audit, never an inference.

## ADR log

### ADR-1 — The script owns phase state, not the model

- **Status:** accepted.
- **Context:** auditing sibling-skill sessions (via the introspect tooling) showed phases running
  without their playbooks ever loading: resource-loading is model-driven and advisory, so the
  phase protocol silently degraded on long horizons, and every re-derivation of "where am I?"
  burned tokens and tool calls.
- **Decision:** a deterministic Python engine evaluates evidence gates and fires transitions;
  durable state lives in `<plan>/.pgsm/state.json` with full history and per-transition evidence.
- **Consequences:** pause/resume across sessions is free; "did the protocol run?" becomes a query;
  the model's job shrinks to one state's work per turn.
- **Lens:** when a workflow guarantee matters, move it from prompt instructions into a script-side
  check — an instruction is a request, a gate is a guarantee.

### ADR-2 — Phase-granularity states in v1, finer steps stay inside state instructions

- **Status:** accepted.
- **Context:** the source phases decompose into sub-steps (dual research, link verification,
  synthesis, …); modelling each as a machine state would multiply gates and turns.
- **Decision:** five working states matching the phase seams (the points with checkable exit
  evidence); sub-steps remain prose inside the state's instruction file.
- **Consequences:** fewer, stronger gates; a sub-step cannot be individually enforced — if one
  proves load-bearing (e.g. link verification), it earns a state or a receipt gate later via TOML.
- **Lens:** make something a state only when its exit can be checked deterministically; otherwise
  it is instruction prose.

### ADR-3 — Structural gates by default; receipt files for checks that require execution

- **Status:** accepted.
- **Context:** some validation requires running tools (diagram render, contrast) that may not
  exist in every eval environment; pure command gates would fail on environment, not on the work.
- **Decision:** default gates are structural (markers, files, fence counts, DAG); validation exit
  additionally requires `.pgsm/receipts/validation.json`, which the instructions direct the agent
  to write only after actually running the render — plus a `command` gate kind for projects that
  want the script to run checks itself.
- **Consequences:** portable default machine; the receipt is the one agent-written `.pgsm/` file,
  and a dishonest receipt is detectable in review (it names the exact command run).
- **Lens:** degrade on environment, never on requirement — when a check can't run everywhere,
  gate on a recorded execution of it rather than dropping it.

### ADR-4 — State instructions are inlined into the composed prompt, never Read by the model

- **Status:** accepted.
- **Context:** "read the playbook" instructions are advisory and unverifiable; reads cost tool
  calls; only the current state's instructions should ever occupy context.
- **Decision:** `pgsm prompt` inlines the state file + gate report + root→leaf document
  composition; the emitted prompt is logged to `.pgsm/prompts/` with sha256, and `trajectory.py
  --prompts-dir` verifies byte-level delivery against the transcript.
- **Consequences:** zero context-discovery tool calls per turn; prompt-content audits are exact;
  state files must stay lean since they ride in every turn of that state.
- **Lens:** if the agent must see a text, put it in the prompt and log what was sent — never
  instruct the agent to fetch it.

### ADR-5 — State files are self-contained (no cross-skill resource references)

- **Status:** accepted.
- **Context:** eval fixtures inject only this skill; instructions referencing a sibling skill's
  resources would dangle in hermetic fixtures and in standalone copies.
- **Decision:** each state file carries the distilled rules it needs (TDD anti-patterns, marker
  conventions), accepting modest duplication of sibling-skill prose.
- **Consequences:** hermetic everywhere; duplicated rules can drift from the sibling — when one
  changes, check the other (see gotchas).
- **Lens:** within a skill, DRY by linking; across skills, copy the distilled rule — a skill must
  survive being the only skill installed.

### ADR-6 — Execution turns are goal-driven, not loop-scheduled

- **Status:** accepted.
- **Context:** the predecessor drove execution with a self-referential `/loop` runner prompt; the
  loop primitive re-fires on a timer and the prompt had to re-derive eligibility each pass.
- **Decision:** the machine's gate evaluation is the stop condition; the driver (a goal-holding
  session or `rollout.py`) repeats prompt → work → `next` until terminal/paused, and `pgsm`
  selects the next eligible ticket deterministically.
- **Consequences:** no scheduling prompt to maintain; ticket selection is exact (dependency-aware,
  lowest-numbered); an interrupted session resumes from disk.
- **Lens:** drive iteration from state on disk, not from a prompt that restates the state.

### ADR-7 — Gold milestones are the changed-file set, and the gold branch stays hidden

- **Status:** accepted.
- **Context:** long-horizon evals need a correctness reference that does not leak into the run;
  content-level diffing is brittle against legitimate implementation variance across models.
- **Decision:** `gold-extract` derives only `git diff --name-only base...gold` (+ commit count);
  rollouts run in detached worktrees off base and never check the gold ref out; tracking scores
  are recall/precision/jaccard over file paths, with recall as the gate metric.
- **Consequences:** cheap, content-agnostic tracking that tolerates different-but-correct
  implementations; path-level recall can be gamed by touching files without substance — the
  complete-status gate (machine terminal + tickets done) and final review carry that weight.
- **Lens:** score trajectories on cheap structural signals, and gate completion on the machine's
  own evidence — don't conflate "tracking toward gold" with "correct".

### ADR-8 — Abandon gates are pure functions with a grace window; progress counts tickets

- **Status:** accepted.
- **Context:** early rollouts must die cheaply when off-track, but bootstrap turns legitimately
  touch nothing gold-shaped, and a long execution phase legitimately stays in one state for many
  turns.
- **Decision:** `decide_abandon(policy, turn, score, stalled_turns, failure_rate)` is pure and
  $0-tested; no gate fires inside `grace_turns`; a turn "progresses" via a state transition OR a
  newly-done ticket; thresholds live in the rollout TOML.
- **Consequences:** gate behaviour is fully unit-tested and tunable per initiative; a genuinely
  slow-but-correct rollout can still be killed by a tight recall floor — tune per initiative size.
- **Lens:** any kill-switch must be a pure function of observable counters, with its false-positive
  modes named and tested before it gains a new input.

### ADR-9 — Unattended refinement self-answers by explicit policy, never by default

- **Status:** accepted.
- **Context:** refinement is human-in-the-loop by design; rollouts have no human, and silently
  skipping questions would be requirement degradation.
- **Decision:** rollout configs set `answer_policy = "self"`, which appends an explicit eval-mode
  block instructing the agent to adopt its top-ranked recommendation and record it as the ADR
  Decision with a self-selected-default note; interactive use never gets that block.
- **Consequences:** unattended runs converge; self-answered ADRs are marked as such and reviewable;
  the policy is config, visible in the run record.
- **Lens:** when an eval must bypass a human gate, bypass it loudly via declared policy text in the
  prompt — never by weakening the state's own instructions.

### ADR-10 — The rollout agent is an injectable seam

- **Status:** accepted.
- **Context:** the rollout loop (worktrees, gates, scoring, records) is the load-bearing logic and
  must be testable without spending money; the no-mocks rule forbids faking subprocess layers.
- **Decision:** `run_rollout(..., agent_fn)` takes the agent as a function; production passes
  `claude_agent` (wrapping the shared `_evalkit` runner); tests pass a scripted agent that stages
  real evidence in the real worktree.
- **Consequences:** the whole loop — including completion, abandonment, and exhaustion paths — is
  covered by $0 deterministic tests against real git repos.
- **Lens:** put the money-spending call behind a function parameter and test everything around it
  with a real-effects substitute, not a mock.

## Extension checklist

- [ ] Machine/gate changes: update `resources/machines/plan-gap.toml` first; add a gate *kind* to
      `pgsm.py` only if no existing kind expresses the check, with tests for pass AND fail.
- [ ] New/changed state: its `resources/states/<state>.md` stays lean (it rides every turn) and
      states its exit evidence in the same terms as the TOML gates.
- [ ] `make -C .claude/skills/plan-gap-sm/scripts fix` then `ci` green (≥90% cov, mypy strict).
- [ ] Goldens still parse: `cases.toml` schema changes update `test_evals.py` in the same change.
- [ ] Docs trio updated by role (SKILL=operating, README=overview, this file=rationale); README
      diagrams re-pass `mermaid_contrast.ts` + `mermaid_complexity.ts`; all files ≤500 lines.
- [ ] New decision ⇒ new ADR here, with a forward-looking Lens.

## Known gotchas

- **Ticket dep parsing sees each id twice** in `| Depends on | [T1.1](./G1-T1.1.md) |` (link text +
  filename) — `parse_ticket` dedups with `dict.fromkeys`; keep that when touching the regex.
  Symptom: duplicated deps in `Ticket.deps`.
- **`ruff format` can orphan a trailing `# type: ignore`** when it wraps an expression across
  lines — mypy then reports both `union-attr` and `unused-ignore`. Prefer a small helper with a
  real `None` check over inline ignores (see `gap_number`).
- **Coverage reads 0% on module-level code without `conftest.py`** — the PEP-723 `__main__` entry
  imports modules before pytest-cov traces; the session-scoped `importlib.reload` fixture restores
  it. Symptom: ~60% coverage with all tests passing.
- **`G*.md` glob gates also match ticket files** (`G1-T1.1.md`). Marker gates intentionally cover
  both tiers; anything needing strict tier separation must use the regex-based helpers
  (`gap_files`, `load_tickets`), not the glob.
- **Terminal states can still transition** — `complete` carries a marker-triggered re-open route,
  and `advance` evaluates transitions before reporting terminal. Don't "optimise" terminal states
  to early-return.
- **Abandoned/exhausted rollouts keep their worktrees** for inspection; `git worktree add` then
  fails on a name collision next run until `git worktree remove --force` (run dirs are timestamped,
  so this only bites manual re-runs into the same dir).
- **State files duplicate distilled sibling-skill rules by design (ADR-5)** — when the sibling
  planning skill's TDD/marker conventions change, sweep `resources/states/` for drift.
