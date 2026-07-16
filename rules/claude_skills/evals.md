# Claude Skill Evals Contract

This is the **evals** child of the skill/rule family rooted at
[`index.md`](index.md) (500-line invariant, tree structure). Sibling
[`scripts.md`](scripts.md) owns the `fix`/`ci` code gates this rule extends;
sibling [`environments.md`](environments.md) defines the capability tiers the
suite must simulate.

A skill is a prompt, and prompts regress silently when models change. Evals
convert "the skill seems good" into a falsifiable, re-runnable gate: fixture
inputs → real agent CLI runs → scored outputs + session-log forensics.

## The target

```bash
make -C .claude/skills/{skill_name}/scripts evals          # default tier (cheap)
make -C .claude/skills/{skill_name}/scripts evals-nightly  # full model matrix
```

`evals` is **not** part of `ci` (it spends money and minutes); `ci` must stay
free and deterministic.

**Environment guarantee:** like `make ci` in [`scripts.md`](scripts.md), the
eval suite itself always runs in a Tier A dev-laptop/CI environment — `uv`,
network, package installs available. The harness therefore relies on
**pytest + deepeval** as its framework with no tier hedging. (The Tier B/C
simulation below constrains the *skill's scripts under test*, never the
harness.) Goldens run via the PEP-723 entry point
(`uv run evals/test_evals.py`); golden checks are expressed as deepeval
metrics passed to `assert_test` — deterministic `BaseMetric`s first, so
adding judged `GEval` metrics later is appending to a list, not a rewrite.
`deepeval test run evals/ -n 2 -c -id "{skill}@<sha>"` (cache, parallelism,
run ids) is the upgrade path once suites grow.

## Directory layout

```
.claude/skills/_evalkit/           # SHARED harness (stdlib-only, offline-tested)
├── evalkit.py                     # fixture builder, claude runner, transcript parser
├── test_evalkit.py                # $0 self-tests (run by every skill's `make ci`)
└── Makefile

.claude/skills/{skill}/scripts/
├── Makefile                       # evals / evals-nightly / ci / fix
└── evals/
    ├── goldens/cases.toml         # one [[case]] per scenario: prompt, must_mention,
    │                              #   budgets, files_unchanged. TOML so the schema is
    │                              #   documented in comments and regexes live in
    │                              #   single-quoted literals (no escaping); parsed
    │                              #   with stdlib tomllib — zero extra deps
    ├── fixtures/<case>/_base/     # committed template (git-committed at build time)
    │              └── _head/      # optional overlay = the uncommitted "diff under review"
    └── test_evals.py              # generic golden runner (PEP-723: pytest +
                                   #   deepeval; imports _evalkit; assert_test
                                   #   with deterministic BaseMetrics)
```

The fixture builder injects the skill under test into the fixture's own
`.claude/skills/` so `/skill-name` resolves hermetically inside the fixture
project (the skill's `scripts/` dir is excluded to avoid recursion).

Fixture discipline: copy `fixtures/<case>` into `tmp/evals/<run-id>/<case>/`
(project-local `tmp/`, never system `/tmp/`), `git init` the copy, reset by
re-copying. Every fixture contains **seeded ground truth** (a planted bug, a
deviant hunk in a codemod, a false doc claim) so scoring is against known
answers, not vibes.

## Driving the CLIs (verified recipes, 2026-06)

**Claude Code headless:**

```bash
claude -p "/skill-name <args>" \
  --setting-sources project \       # ONLY the fixture project's settings/skills load;
                                    #   user/local settings, hooks, MCP stay out
  --model claude-haiku-4-5 \        # pin FULL ids, never aliases (aliases re-point silently)
  --session-id "$UUID" \            # pre-pick ⇒ transcript path known before the run
  --output-format json \            # → result, session_id, total_cost_usd, usage
  --permission-mode bypassPermissions \
  --max-budget-usd 0.50             # hard dollar cap — always set
```

**Auth modes** (runs inherit the caller's env): with `ANTHROPIC_API_KEY` set,
API billing; without it, the logged-in **subscription** (OAuth/keychain) —
so cheap-model trial runs work on a dev laptop before any API key exists.

> ⚠️ **Do NOT use `--bare` for skill evals** (verified 2026-06): `--bare`
> never reads OAuth/keychain (subscription auth impossible) and does not load
> the fixture's `.claude/skills` even with `--setting-sources project` — the
> run dies instantly with `Unknown command: /<skill>`, 0 turns, $0. The
> failure is cheap and unmistakable, which is how it was caught.
> `--setting-sources project` is the isolation mechanism instead.

- Transcript: `~/.claude/projects/<cwd-slug>/<session-id>.jsonl` where
  `<cwd-slug>` = absolute cwd with `/` and `.` → `-`. The fixture cwd
  determines the slug — compute it per run.
- Lines carry `type` (`assistant`/`user`/`system`/…); `assistant` lines hold
  `message.model`, `content[].type == "tool_use"` (name + input), and
  per-call `usage` tokens; `isSidechain: true` marks subagent traffic.

**Codex headless:**

```bash
codex exec "<prompt>" -m gpt-5.5 -C "$FIXTURE_DIR" \
  -s workspace-write --skip-git-repo-check --json \
  -o tmp/evals/last_message.txt
```

- Rollout log: `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl`
  (lookup via `~/.codex/session_index.jsonl`). `turn_context` lines carry
  model + `sandbox_policy` (assert `network_access` here); `event_msg`
  `token_count` carries token usage; `response_item` carries tool calls.
- Codex auto-migrates model ids — always pass `-m` explicitly.
- `_evalkit` provides `run_codex_skill()` + `parse_codex_rollout()`; codex
  doesn't read `.claude/skills`, so inject the skill with
  `inject_agents_md(fixture, skill_dir)` (SKILL.md → the fixture's AGENTS.md)
  before the run.

**Subprocess rules:** build `env` from scratch (never inherit `os.environ`) —
that's also the constrained-environment lever; explicit `timeout=` always,
kill the process group on expiry; one fixture dir per test ⇒ pytest `-n`
parallelism is safe.

## Model matrix

Parametrize across the capability spectrum so a skill is known-good per tier:

```python
EVAL_MODELS = os.environ.get("EVAL_MODELS", "claude-haiku-4-5").split(",")
# nightly: claude-haiku-4-5,claude-sonnet-4-6,claude-opus-4-8 (+ codex gpt-5.5)
@pytest.mark.parametrize("model", EVAL_MODELS)
```

A skill that only works on Opus is a finding, not a failure — record the
floor model in the skill's CLAUDE.md.

## The generative matrix (model × task)

Goldens score a skill against *seeded truth*. The complement is the **generative
matrix**: run the skill for real across `{model tier} × {task}` and keep every
artefact next to the session log that produced it. Where goldens answer "did it
find the planted bug", the matrix answers **"which models can actually follow
this skill, and what does it cost to find out"** — the question that decides the
floor model in CLAUDE.md.

Reach for it when the skill's value *is* instruction-following at volume (a
house style, a mechanical rule set, a multi-format authoring contract). Skip it
when a golden already answers the question — it is strictly more expensive.

```
scripts/
├── _generate_example.py   # private helper: one `claude -p` run per matrix cell
├── _session_report.py     # private helper: reads the logs back (free, offline)
└── examples/
    └── {haiku,sonnet,opus}/{task-a,task-b,...}/
        ├── <artefact>           # what the run produced
        └── <artefact>.session.jsonl   # the transcript that produced it
```

Rules that make the matrix trustworthy:

- **Tier names, pinned ids.** One `TIERS = {"haiku": "claude-haiku-4-5", ...}`
  table maps a tier to a **full model id, never an alias** — aliases silently
  re-point, and a committed log would then misattribute the run. Only that table
  knows ids; Makefile targets pass tier names.
- **One directory per cell.** The cwd determines the transcript slug, so a
  per-cell working directory is also what keeps logs unambiguously attributable.
  Targets are named after their output (`make haiku/md`), so a single cell is
  re-runnable.
- **Prompts name the artefact, never the rules.** The generator prompt carries
  only the task shape and format mechanics; it tells the agent to *read* the
  skill. A prompt containing a copy of the rules is a third copy, and it rots.
- **Pre-pick the session id.** `--session-id <uuid>` makes the log path
  (`~/.claude/projects/<cwd-slug>/<uuid>.jsonl`) knowable *before* the run, so
  the transcript is copied deterministically next to its artefact. Discovering
  it afterwards by globbing or mtime is a race you eventually lose.
- **Paid targets are siblings of `ci`, never dependencies** — per
  [`scripts.md`](scripts.md), private helpers wire to `docs`, which `ci` depends
  on. Followed literally here, every CI run would spawn a fleet and spend money.
  Keep `docs` free; give generation its own targets, like `make evals`.
- **Cap every cell** with `--max-budget-usd`, and fan out with `-j` so the sweep
  is bounded in both dollars and wall clock.

## Post-run reporting (the logs are the eval)

The matrix is only half the artefact. A **report script** reads the committed
`*.session.jsonl` back and turns a pile of runs into a verdict. It is free,
offline, and deterministic, so unlike generation it *can* live in `ci`.

Report on **outcome, wall clock, and cost — in that order**:

1. **Did the artefact land?** Check the expected output file exists. Import the
   filename from the generator; never restate it.
2. **How did the run stop?** Take the **last** non-null `stop_reason` — every
   intermediate turn stops with `tool_use`, and only the final turn says how the
   run ended. `end_turn` is the only clean stop; `max_tokens` (truncated) and
   `refusal` are failures.
3. **Wall clock** — min→max of the `timestamp` field across **every** record,
   not just assistant turns: tool execution is real elapsed time.
4. **Cost** — sum `input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
   `cache_read_input_tokens` per model and price them.

Non-obvious rules, each learned the hard way:

- **Both outcome checks are load-bearing.** A `max_tokens` truncation leaves a
  *real but half-written* file (file check alone passes); a declined tool call
  can end cleanly with `end_turn` and no file (stop-reason check alone passes).
  Fail on either.
- **Transcripts record the served snapshot id** (`claude-haiku-4-5-20251001`),
  not the id you requested. Strip the `-\d{8}` suffix before pricing, or a real
  paid run reports as unpriced and vanishes from the total.
- **A failed run still costs money.** Price and report it exactly like a
  successful one — failure changes the verdict, never the accounting. A tier
  that fails *fast and cheap* is a different finding from one that fails
  *slow and expensive*.
- **An unknown model is `unpriced`, never `$0.00`.** Silent zeros read as fact.
- **Derive cache rates from the input rate** (1.25× write, 0.1× read) rather
  than typing four numbers per model. Date the pricing table and source it;
  never write a rate from memory.
- **Failures are an exit code, not a table cell.** A reader skims a table; CI
  cannot skim an exit code.

The pattern's payoff is that the matrix + report make the floor model *fall out
of the data*: when every cell of one tier reports `MISSING ARTEFACT` while the
tiers above it pass, that tier is below the skill's floor — and you have the
per-cell spend to say what learning it cost.

## Metric tiers (cheapest first)

1. **Deterministic `BaseMetric`s** (free, non-flaky — the bulk of the suite):
   seeded-truth checks (was the planted deviant promoted? the planted drift
   flagged? the planted bug reported and the style-bait NOT?), artifact
   exists/parses, exit code, turn/token/cost ceilings from the transcript.
2. **`ToolCorrectnessMetric`**: `tools_called` from the session jsonl vs
   `expected_tools` from the golden.
3. **`GEval` LLM judge** (custom `DeepEvalBaseLLM` wrapping the anthropic
   SDK; judge model pinned, e.g. `claude-sonnet-4-6` routine /
   `claude-opus-4-8` nightly): output-quality rubrics written as
   `evaluation_steps`, never loose criteria; `threshold`, never exact-score.

## Environment simulation

Evals must also exercise the script tiers from
[`environments.md`](environments.md): run each public helper script under a
stripped PATH (Tier B: `python3` only, no `uv`/`bunx`/network) and assert it
either works or **crashes loudly with a clear message** — per the
escalators-not-stairs rule, missing hard deps must crash, and the eval
asserts the crash. Network-off: assert `sandbox_policy.network_access ==
false` in Codex traces; for Claude, deny WebFetch/WebSearch/curl via
`--disallowedTools` (or `unshare -n` on Linux CI).

## Cost & cadence

| Cadence | Scope | Budget |
|---------|-------|--------|
| per-commit (`ci`) | deterministic script tests + transcript-parser tests on committed fixture logs — **no LLM calls** | $0 |
| per-PR (`evals`) | 1 cheap model, 2-3 goldens, `--max-budget-usd 0.25`/run, deepeval `-c` cache | ≪ $1 |
| nightly (`evals-nightly`) | full matrix, all goldens, `-r 2` repeats to measure flake | dollars |

## Pitfalls

- **Session jsonl schemas are internal/unversioned.** Isolate parsing in
  `transcript.py`; assert hard on the fields metrics need; fail loudly on
  drift (each Claude line carries `version` — check it).
- **Flaky judges**: `evaluation_steps` + thresholds + nightly repeats; pin
  judge ids; don't let a model family be sole judge of itself.
- **Cost runaways**: timeout + `--max-budget-usd` + token-ceiling metric on
  every agentic test, no exceptions.
- **Environment bleed**: a run without `--bare` (or with inherited
  `~/.codex/config.toml`) tests your laptop, not the skill.
- Re-baseline thresholds when pinned model ids bump; tag runs
  `-id "{skill}@{model}@{sha}"` so regressions bisect.
