# Design Rationale

Why the scaffold makes the choices it does.

## Top-level + per-language sub-Makefiles (not a single flat Makefile)

Each subproject is independently usable for tight inner-loops; the top-level is
pure orchestration. Avoids a 200-line monolith and keeps blast radius small when
adding new targets.

## `concurrently` in package.json (not `make -j`)

`concurrently -k` (kill-others) gives prefixed/colored logs and a single Ctrl-C
tears down both processes cleanly. `make -j` with two long-running processes
interleaves output and orphans children on interrupt.

## `uvicorn(factory=True)` with `create_app()`

Tests can build isolated `FastAPI` instances per fixture without sharing
module-level state.

## `server.core` with no FastAPI imports

The boundary that the ≥90% coverage gate is meant to load on. Pure functions are
easy to test exhaustively; framework glue isn't.

## `tests/unit` vs `tests/api` split

Lets the coverage gate apply primarily to deterministic logic while API tests
verify wiring without inflating the denominator.

## Both backend AND frontend ports split across human/agent profiles

A shared backend at `8200` would mean the human and the agent compete for the
same uvicorn process; reload semantics and dev DB state would race. Splitting
both lets two concurrent dev sessions iterate independently.

## Pydantic v2 + `response_model` everywhere

Schemas ARE the contract; OpenAPI generation is free; mypy `pydantic.mypy` plugin
gives strict static checking on top.

## `hatchling` build backend

Modern, simple, default for pyproject-only Python packages. No `setup.py`.

## E2e pattern: slug-taxonomy + coverage-matrix

Playwright's `webServer` block spawns BOTH halves via `concurrently` so e2e
exercises the real FastAPI backend, not a mock.

```ts
// e2e/matrix.ts
export const SECTIONS = ["home"] as const;
export const VARIANTS = ["default"] as const;
export const MATRIX = SECTIONS.flatMap((s) =>
  VARIANTS.map((v) => ({ id: `${s}__${v}`, path: `/${s === "home" ? "" : s}` })),
);
```

Each generated test produces three paired artifacts keyed by a deterministic slug:

```
test-results/matrix/<slug>.png            # full-page screenshot
test-results/matrix/<slug>.log            # console + page errors (filtered)
test-results/matrix/<slug>.network.json   # request timings (start_offset_ms, duration_ms)
```

Console-error filter: tolerates `[vite]` chatter, React DevTools nudge, favicon
misses, and `503`s for optional data; everything else fails the test.

To add a route: append to `SECTIONS`. To grow a new axis (locales, viewport
sizes, auth states): copy the `SECTIONS`/`VARIANTS` shape and weave it into the
`MATRIX` flatMap.
