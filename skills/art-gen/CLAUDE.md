# CLAUDE.md — maintaining the `art-gen` skill

Guidance for an assistant editing files under `.claude/skills/art-gen/`. Read the ADR log
below before changing behaviour — each ADR records *why* a decision was made and a
**Lens** for applying it to the next decision.

## The development contract

Two commands are the entire loop. Run from the repo root (never `cd` in):

```bash
make -C .claude/skills/art-gen/scripts fix   # auto-format + lint-fix (MUTATES source)
make -C .claude/skills/art-gen/scripts ci    # the gate: format-check, lint, mypy --strict, ≥90% cov
```

`ci` must be 0-exit before handing work off. Use per-language sub-targets
(`format-check-py`, `lint-py`, `typecheck-py`, `test-cov-py`) only to narrow a failure;
the contract is `ci`. See `.claude/rules/claude_skills.md` for the canonical convention.

## File map

| File | Role |
|------|------|
| `scripts/art_gen.py` | The script. Pure helpers + two boundary functions + `main`. |
| `scripts/test_art_gen.py` | PEP-723 test entry point. Real fakes injected through seams (fakes-only deps — no `google-genai`). |
| `scripts/conftest.py` | `importlib.reload` fixture so module-level lines count toward coverage. |
| `scripts/Makefile` | `fix` / `ci` and their sub-targets. `COV_MIN = 90`. |
| `SKILL.md` | Agent-facing trigger + usage. |
| `README.md` | Human-facing consumer docs. |
| `reference/prompt_template.md` | Generic starter prompt (no brand specifics). |

## Architecture: pure core, thin boundary

The module is deliberately split so the gate is reachable offline:

- **Pure, fully-tested:** `require_api_key`, `load_prompt_file`, `resolve_model`,
  `build_metadata`, `save_image`, `read_history`, `format_history`, `resolve_prompts`.
- **Generation loops** (`gemini_generate`, `imagen_generate`, `main`): take the GenAI
  **client** and a **config factory** as parameters. Tests pass real fakes; production
  passes the live client. This is the seam that makes response-handling testable without
  a network call.
- **Boundary, `# pragma: no cover`:** `make_client`, `_default_gemini_config`,
  `_default_imagen_config` — the only lines that import `google-genai`. They are validated
  by running the real CLI (`generate`), not by pytest — see ADR-008.

When you add a feature, decide which side of this line it belongs on and keep the pure
core pure.

## Testing rules (non-negotiable)

- **No mocks / no patches.** See `.claude/rules/python/tests.md`. Use real fakes passed
  through the client/config seams (the test file's `_FakeGeminiClient` etc.).
- **No secrets through pytest.** Live, real-credential validation is a CLI concern, never
  a pytest one — pytest renders frame arguments in tracebacks, so a key passed to
  `make_client(api_key=…)` would print on any failure. See ADR-008.
- Keep `# pragma: no cover` confined to the import-guarded boundary and `__main__`.

## ADR log

### ADR-001 — Two skills split on the auth/compute boundary
**Status:** Accepted.
**Context:** The source workflow mixed paid, non-deterministic generation with free,
deterministic editing.
**Decision:** `art-gen` owns everything that needs a key + network + spends money;
`art-edit` owns everything offline + deterministic.
**Consequences:** Clean dependency story (no ML/onnx here), and users can edit for free.
**Lens:** A new capability goes in `art-gen` only if it *requires* the API. Anything
deterministic belongs in `art-edit`.

### ADR-002 — API-key auth only (no Vertex AI / ADC)
**Status:** Accepted (explicit product requirement).
**Context:** The originating script defaulted to Vertex AI with a hardcoded cloud project.
**Decision:** Read a non-empty `GOOGLE_API_KEY`; construct `genai.Client(api_key=…)`;
fail fast on missing/blank. No ADC, no Vertex env juggling.
**Consequences:** One obvious setup step; portable across machines; no silent cloud-project
coupling.
**Lens:** Do not reintroduce credential fallback chains. If another auth mode is ever
needed, make it an explicit opt-in flag, never a silent fallback (see the global
"no graceful degradation" rule).

### ADR-003 — Dependency injection as the testability seam
**Status:** Accepted.
**Context:** The no-mocks rule + a ≥90% coverage gate collide with a paid API.
**Decision:** Inject the GenAI client and the config factories into the generation
functions and into `main`. Offline tests pass small real fakes; production passes the
live objects.
**Consequences:** Response-handling, fan-out, and dispatch are covered with zero network;
only two construction lines are `no-cover`.
**Lens:** Any new external call gets an injected seam with a hand-written fake — never a
`unittest.mock`. If you can't test it without a network call, isolate it behind a
`# pragma: no cover` boundary and validate it via the CLI (ADR-008), not pytest.

### ADR-004 — Deferred imports for the heavy SDK
**Status:** Accepted.
**Context:** A top-level `from google import genai` would force every test and `--help`
to install the SDK.
**Decision:** Import `google-genai` only inside `make_client` / the config factories.
**Consequences:** Test deps stay `Pillow`-only; `--help` is instant; the import lives
exactly where the `no-cover` boundary is.
**Lens:** Heavy/external libs import at the point of use, never at module top. This is the
sanctioned exception to "imports at the top."

### ADR-005 — JSON sidecars as the provenance mechanism
**Status:** Accepted.
**Context:** Iteration needs to recover *how* a good image was made.
**Decision:** Every PNG gets a `.json` sidecar (prompt, model, backend, aspect, size,
source file). The `history` subcommand replays them oldest→newest.
**Consequences:** Curation is just reading prior prompts; runs are reproducible.
**Lens:** If you add a generation knob, add it to `build_metadata` so the sidecar stays a
complete recipe. The sidecar schema is an API — extend, don't silently change keys.

### ADR-006 — One-shot + fan-out + history, not interactive chat
**Status:** Accepted.
**Context:** The original had a multi-turn interactive chat REPL.
**Decision:** Drop the REPL. Skills run non-interactively; provide repeatable
`--prompt-file` (fan-out) and a `history` curation aid instead.
**Consequences:** Every path is automatable and testable; exploration sweeps are one
command.
**Lens:** Prefer batch/declarative interfaces over interactive ones in skills — they are
testable and agent-drivable.

### ADR-007 — Brand-agnostic by construction
**Status:** Accepted (project rule `.claude/rules/agnostic_examples.md`).
**Context:** Extracted from a specific logo pipeline saturated with one brand's palette,
mascot, and runes.
**Decision:** Keep only generic capability; starter prompt and defaults are neutral.
**Consequences:** Reusable in any project.
**Lens:** No project-specific names, palettes, or mascots in code, docs, or the template.
Illustrative hex codes must be obviously generic.

### ADR-008 — Live validation via the CLI, never through pytest
**Status:** Accepted (security incident, 2026-06-01).
**Context:** An earlier `TestLiveGeneration` pytest test routed `GOOGLE_API_KEY` into
`make_client(api_key=…)`. When that call raised (the test env lacks `google-genai`, so
`from google import genai` → `ModuleNotFoundError`), **pytest rendered the frame's
arguments — including the key — in the traceback**, leaking the secret into session
output. The test was also structurally broken: the test deps are fakes-only by design, so
it could never import the SDK.
**Decision:** Remove in-pytest live tests. The import-guarded boundary stays
`# pragma: no cover`; real-credential validation is done by running the **CLI**
(`art_gen.py generate`), which has `google-genai` in its own PEP-723 block and, being plain
CPython, does **not** print frame arguments in tracebacks.
**Consequences:** The gate is green whether or not a key is exported; secrets never pass
through pytest; test deps stay lean.
**Lens:** Never pass a secret as an argument anywhere pytest can observe a failing frame.
"Run it under coverage with a key" is a trap — validate credentialed paths via the CLI.
If a future change reintroduces a credentialed pytest test, it must (a) add the SDK to the
test deps **and** (b) prove the key cannot appear in a traceback — otherwise reject it.

## Extension checklist

Before you finish a change here:

- [ ] New external call → injected seam + real fake test (ADR-003); heavy import deferred (ADR-004).
- [ ] New generation knob → threaded into `build_metadata` (ADR-005).
- [ ] No brand specifics introduced (ADR-007).
- [ ] `make … fix` run, then `make … ci` green (≥90% cov, mypy --strict).
- [ ] `SKILL.md` (agent), `README.md` (human), and this ADR log updated if behaviour changed.

## Known gotchas

- `mypy --strict` flags `no-any-return` on some SDK/`Any` returns — annotate or `cast`,
  don't loosen the gate.
- The PEP-723 dep block in `art_gen.py` and the one in `test_art_gen.py` are separate;
  the test block intentionally omits `google-genai` (fakes only).
