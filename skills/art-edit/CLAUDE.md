# CLAUDE.md — maintaining the `art-edit` skill

Guidance for an assistant editing files under `.claude/skills/art-edit/`. Read the ADR log
below before changing behaviour — each ADR records *why* a decision was made and a
**Lens** for applying it to the next decision.

## The development contract

Two commands are the entire loop. Run from the repo root (never `cd` in):

```bash
make -C .claude/skills/art-edit/scripts fix   # auto-format + lint-fix (MUTATES source)
make -C .claude/skills/art-edit/scripts ci    # the gate: format-check, lint, mypy --strict, ≥90% cov
```

`ci` must be 0-exit before handing work off. Use sub-targets (`lint-py`, `typecheck-py`,
`test-cov-py`, …) only to narrow a failure. See `.claude/rules/claude_skills/index.md`.

## File map

| File | Role |
|------|------|
| `scripts/art_edit.py` | The script. Pure machine-vision primitives + file-IO orchestrators + `main`. |
| `scripts/test_art_edit.py` | PEP-723 test entry. Pure math tested on tiny arrays; a real fake segmenter through the seam (deps exclude `rembg`). |
| `scripts/conftest.py` | `importlib.reload` fixture for coverage. |
| `scripts/Makefile` | `fix` / `ci`. `COV_MIN = 90`. |
| `SKILL.md` / `README.md` | Agent-facing / human-facing docs. |
| `reference/config.example.json` | Neutral wordmark/icon/canvas config. |

## Architecture: pure primitives, thin orchestrators

- **Pure, fully-tested on synthetic arrays:** `auto_crop`, `color_distance`,
  `color_signal`, `scharr_edges`, `dilate_edge_mask`, `element_alpha`, `sigmoid_sharpen`,
  `combined_matte`, `resolve_position`, `render_text`, `write_sidecar`, `load_config`.
  These are the matte math and have **no file IO and no model**.
- **Orchestrators** (`remove_background`, `segment_layers`, `generate_pipeline_steps`,
  `add_wordmark`, `composite_pipeline`, `main`): do file IO and call the **segmenter**,
  which is an injected parameter. `segment_layers`/`steps` reuse `combined_matte` so the
  matte math lives in exactly one place.
- **Boundary, `# pragma: no cover`:** `_default_segmenter` (the only `rembg` import) and
  the `if segmenter is None:` default-construction lines. Validated by running the real
  CLI (`remove-bg --mode model`), not by pytest — see ADR-010.

When adding a stage, add a **pure** primitive and call it from the orchestrator — don't
bury new math inside a file-IO function.

## Testing rules (non-negotiable)

- **No mocks / no patches** (`.claude/rules/python/tests.md`). The fake segmenter in the
  test file is a real function passed through the documented seam.
- New machine-vision math gets a direct unit test on a tiny synthetic array (see
  `_sample_array`), asserting a specific numeric property.
- Keep `# pragma: no cover` confined to the `rembg` boundary, the segmenter default
  assignment, the corrupt-font `except`, and `__main__`.

## ADR log

### ADR-001 — Two skills split on the auth/compute boundary
**Status:** Accepted.
**Context:** The source workflow mixed paid, non-deterministic generation with free,
deterministic editing.
**Decision:** `art-edit` owns everything offline + deterministic; `art-gen` owns the API.
**Consequences:** No API key here; the heavy ML/onnx deps stay out of `art-gen`.
**Lens:** A new capability belongs here only if it is deterministic and offline. If it
needs the GenAI API, it goes in `art-gen`.

### ADR-002 — Pure primitives separated from orchestrators
**Status:** Accepted.
**Context:** The matte math must be testable without files or a 170 MB model, and is
shared by `segment` and `steps`.
**Decision:** Every signal is a pure `np.ndarray → np.ndarray` function; orchestrators
only do IO + sequencing and reuse `combined_matte`.
**Consequences:** ≥90% coverage offline; one source of truth for the matte.
**Lens:** New math = new pure function with its own unit test. Never duplicate a signal
between `segment` and `steps`; extend `combined_matte`.

### ADR-003 — Segmenter as an injected seam
**Status:** Accepted.
**Context:** The no-mocks rule + coverage gate collide with U2-Net's 170 MB model.
**Decision:** `segmenter` is a `Callable[[Image], Image]` parameter, defaulting lazily to
rembg. Tests inject a deterministic fake (centre-quadrant matte).
**Consequences:** The model-backed paths are covered offline; only the import + default
assignment are `no-cover`.
**Lens:** Any new model/external collaborator gets an injected seam + real fake. Don't
`mock` rembg; pass a function.

### ADR-004 — Deferred `rembg`/`onnxruntime` import
**Status:** Accepted.
**Context:** A top-level import would force the heavy ML stack on every test and `--help`.
**Decision:** Import `rembg` only inside `_default_segmenter`.
**Consequences:** Test deps are `Pillow`+`numpy`; the boundary is one function.
**Lens:** Heavy/external libs import at point of use. This is the sanctioned exception to
"imports at the top."

### ADR-005 — A reproducibility sidecar for *every* edit
**Status:** Accepted (explicit requirement).
**Context:** Edits must be redoable, including the intermediate-steps visualisation.
**Decision:** `write_sidecar` emits `<output>.json` (and `steps.json` for the steps dir)
capturing command, input, params, and outputs.
**Consequences:** Any edit can be reconstructed from its sidecar; settings are auditable.
**Lens:** A new command, or a new tunable on an existing one, **must** be reflected in its
sidecar `params`. The sidecar is the edit's recipe — keep it complete.

### ADR-006 — Dropped flood-fill BG mode and the decorative-glyph overlay
**Status:** Accepted.
**Context:** The source had a third `flood` background mode and a low-opacity rune
overlay. Flood was superseded by the model/global modes; the glyph overlay was a
brand-specific easter egg.
**Decision:** Ship `model` + `global` removal and `wordmark`; omit flood and the glyph
overlay.
**Consequences:** Smaller, faithful surface; ~140 hard-to-cover flood lines avoided.
**Lens:** Prefer the smallest faithful surface. Re-add a dropped mode only with a real
use case **and** a test that covers it — don't resurrect dead code for symmetry.

### ADR-007 — Font-size clamp + Pillow ≥10.1 size-aware default
**Status:** Accepted (bug fix).
**Context:** FreeType raises `division by zero` at sub-~8px sizes, and the legacy bitmap
default font can't `getbbox`; both break wordmarks on tiny canvases and on hosts with no
system fonts.
**Decision:** Clamp the wordmark font to a 16px minimum and fall back to
`ImageFont.load_default(size)` (Pillow ≥10.1, FreeType-backed).
**Consequences:** Wordmark works cross-platform with no system fonts and on small inputs.
**Lens:** Treat the no-system-font, tiny-input case as a first-class path, not an edge to
ignore. Don't lower the Pillow floor below 10.1.

### ADR-008 — `cast()` for numpy under `mypy --strict`
**Status:** Accepted.
**Context:** `np.max`/`np.sqrt`/`np.maximum` are typed `Any`, tripping `warn_return_any`.
**Decision:** Wrap those return sites in `cast(np.ndarray, …)`.
**Consequences:** `--strict` passes without weakening the gate elsewhere.
**Lens:** Fix `no-any-return` with a targeted `cast` at the specific site; never disable
strict or add a blanket `ignore`.

### ADR-009 — Brand-agnostic by construction
**Status:** Accepted (`.claude/rules/agnostic_examples.md`).
**Context:** Extracted from a brand-specific logo pipeline.
**Decision:** Neutral defaults (`BRAND`, generic colours); no mascot, palette, or runes.
**Consequences:** Reusable in any project.
**Lens:** No project-specific names/palettes in code, docs, config, or examples.

### ADR-010 — Real-model validation via the CLI, not pytest
**Status:** Accepted (2026-06-01).
**Context:** An earlier `ART_EDIT_RUN_MODEL=1` pytest test called the real model, but the
test deps are fakes-only by design (no `rembg`/`onnxruntime`), so the test could only ever
`ModuleNotFoundError` — turning the gate red the moment someone set the flag. (Sibling skill
`art-gen` hit the same anti-pattern with a worse outcome: a leaked secret — see its ADR-008.)
**Decision:** Remove the in-pytest real-model test. The `rembg` boundary stays
`# pragma: no cover`; real-model validation is done by running the **CLI**
(`art_edit.py remove-bg --mode model` / `segment` / `steps`), which carries the full ML
stack in its own PEP-723 block.
**Consequences:** The gate is green regardless of env flags; test deps stay
`Pillow`+`numpy`; the real model is still exercised — just through the CLI.
**Lens:** Don't put a heavy/external dependency's real path in a pytest whose deps exclude
it. Keep unit tests on the injected fake; validate the real collaborator via the CLI.

## Extension checklist

- [ ] New signal/stage → pure primitive + unit test (ADR-002), reused via `combined_matte`.
- [ ] New external model → injected seam + fake (ADR-003); heavy import deferred (ADR-004).
- [ ] New command/tunable → reflected in its sidecar `params` (ADR-005).
- [ ] Text rendering safe on tiny/no-font hosts (ADR-007).
- [ ] `make … fix` then `make … ci` green (≥90% cov, mypy --strict).
- [ ] `SKILL.md`, `README.md`, and this ADR log updated if behaviour changed.

## Known gotchas

- The PEP-723 dep blocks in `art_edit.py` (full ML stack) and `test_art_edit.py`
  (`Pillow`+`numpy`+`pytest` only) are separate — the test never imports `rembg`.
- `combined_matte` returns `(union, signals_dict)`; `segment`/`steps` rely on the dict
  keys (`u2net`, `color`, `edge_scharr`, `edge_dilated`, `edge_refined`, `combined`).
  Renaming a key is a breaking change to both orchestrators.
