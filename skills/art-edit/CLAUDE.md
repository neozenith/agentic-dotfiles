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

### ADR-011 — A registry-driven pipeline with two dynamic escape hatches
**Status:** Accepted (2026-07-24).
**Context:** The fixed five-command surface could not express "composite these logos onto
that car, heal the livery underneath, and paste a face crop over a head" without new code
per combination. The requirement was explicitly for *reach* — any OpenCV feature, any
HuggingFace model, composed in any order, with the working-out visible.
**Decision:** A sibling script `art_pipe.py` runs a declarative JSON spec of named ops
against a `Frame` (RGBA image + named buffers + meta). Ops live in a decorator-built
registry, so adding one is a single function and `ops` documents it automatically. Two ops
are deliberately *unbounded*: `cv2` dispatches to any attribute of the OpenCV namespace, and
`hf` to any `transformers` pipeline. `$image` / `$buf:NAME` placeholders and `"cv2.CONST"`
strings let a JSON spec hand live data and real enums to a function nobody wrapped.
**Consequences:** New capability usually needs a spec, not a commit. The tradeoff is that
the dynamic ops cannot be type-checked at the spec boundary — they fail at run time with the
underlying library's error, which is why `run_pipeline` reports the failing step index and
`--steps` writes every intermediate.
**Lens:** When a surface must stay open-ended, expose a *registry + placeholder grammar*
rather than growing a wrapper per feature. Wrap something explicitly only when it needs
non-obvious glue (as `inpaint` and `seamless-clone` do); otherwise let `cv2`/`hf` carry it.

### ADR-012 — OpenCV 5 dropped Haar; face detection is an injected seam
**Status:** Accepted (2026-07-24).
**Context:** `face-crop` was first written against `cv2.CascadeClassifier` with the bundled
cascade XML. On OpenCV 5.0 that attribute **does not exist** — the cascades were removed
outright — and the tests caught it immediately. The 5.0 replacement, `FaceDetectorYN`
(YuNet), is a DNN needing a ~350 KB ONNX file, i.e. a network fetch.
**Decision:** Detection is a `FaceDetector` callable on `OpContext`, defaulting to YuNet with
a one-time cached download; tests inject real stand-in detectors. `face-crop` also accepts an
explicit `box`, which bypasses detection entirely. A missing model raises — it never
silently reports "no faces".
**Consequences:** The op is testable offline and usable with zero network via `box`. The
crop maths is asserted against known boxes rather than against whatever a detector happened
to find, which makes the test deterministic.
**Lens:** Do not assume a 4.x OpenCV API exists in 5.x — probe before depending on it. Any
detector/model collaborator goes behind an injected seam **and** gets a manual override, so
the op stays usable when the model is unavailable.

### ADR-013 — Perspective decals and landmark face-align as first-class ops
**Status:** Accepted (2026-07-24).
**Context:** Real jobs needed a logo placed on a foreshortened car door and a real face mapped
onto a generated one. A flat `overlay` reads as stuck-on when the surface recedes, and there
was no face-correspondence primitive at all.
**Decision:** `perspective-overlay` warps a layer to a 4-corner quad (`cv2.getPerspectiveTransform`
+ `warpPerspective`, alpha-composited). `face-align` uses YuNet's **5-point landmarks** (free
alongside the box) with `estimateAffinePartial2D` to map a source portrait onto a detected
target face, blended by alpha or `seamlessClone`. Both take their detector through the same
injected seam as `face-crop`, so they test offline against fakes.
**Consequences:** Logos sit in-plane; faces can be swapped deterministically with no extra
model. **Measured limit:** a 2D affine paste imports the *source portrait's* expression and
lighting, so on a mid-action frame the native AI face looks better — face-align earns its
place on calm frames or as a base for a re-synthesising `hf` model, not as a universal win.
**Lens:** Prefer the free capability already in a dependency (YuNet landmarks) before adding
a model. When a deterministic technique has a quality ceiling, measure it and record the
ceiling next to the feature, so the next decision picks the right tool instead of assuming.

### ADR-014 — Collaboration aids: labelled grid + identity annotation
**Status:** Accepted (2026-07-24).
**Context:** Targeted edits kept mis-landing — a logo on the wrong panel, a face swapped onto
the wrong person — because human↔agent region/identity communication was ad-hoc (raw pixel
coords, guessed correspondence). An embedding auto-match confidently mapped the wrong
teammate onto the driver.
**Decision:** Add `grid.py` (public, tested): a labelled letter×number grid overlay plus a
`resolve` that turns a spreadsheet range (`C5:F6`) into a pixel box + TL/TR/BR/BL quad for a
spec. Establish the ritual of a **colour-coded, named identity annotation** confirmed before
any face op, with names assigned by stable features + fixed seating role, not by
low-confidence recognition embeddings. Both rituals are documented in
`resources/learned/collaboration_workflows.md` and pointed at from SKILL.md.
**Consequences:** Regions and identities are agreed on a cheap artifact before the costly
edit. `grid.py resolve` output feeds `perspective-overlay`/`crop` directly, so coordinates
are never hand-typed.
**Lens:** When an edit must "target the right thing", the first deliverable is an agreement
artifact (labelled grid, named face map, side-by-side), not the edit. Prefer a shared
symbolic vocabulary (cell ranges, stable per-person colours) over exchanging raw pixels or
trusting an automatic match that can be confidently wrong.

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
