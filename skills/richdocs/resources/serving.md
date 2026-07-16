# Reliable Localhost Serving for Rich HTML

Why HTML documents that "work on my machine" break when opened from Finder,
and the one-command fix. Companion to `scripts/serve.py`.

## The failure mode: `file://`

Opening a multi-file HTML document directly (double-click, `open doc.html`)
loads it over the `file://` scheme, where browsers block `fetch()` of sibling
files (CORS treats every `file://` URL as an opaque origin). Symptoms:

- Blank page or spinner forever; console shows
  `Fetch API cannot load file:///…` or `CORS request not HTTP`.
- CDN `<script>` tags still load (network is fine) — so the page *chrome*
  appears but the *data* never arrives. This half-working state is the tell.

Two valid responses, both provided by this skill:

| Mode | Mechanism | When |
|------|-----------|------|
| `serve.py` | real `http://127.0.0.1` origin — fetch works | authoring loop, data-driven docs |
| `md2html.py --inline` | no fetch at all — data embedded on `window.__DOC_MD__` | sharing one file, attaching to a PR |

## The serving contract

`serve.py` is a stdlib `http.server` wrapper with three load-bearing behaviours:

1. **`Cache-Control: no-store` on every response.** Browsers aggressively
   cache `http://localhost` JSON. Without this, you edit the markdown,
   refresh, and see stale content — the most common "it's broken" report.
   Belt-and-braces: generated HTML also appends `?v=<BUILD_ID>` to every
   runtime fetch, so even a proxy or misbehaving cache is defeated.
2. **Fail loud on a busy port.** A second `serve.py` on the same port exits 1
   with the reason — never silently serves a *different* directory than the
   one you think you're looking at.
3. **Bind `127.0.0.1`, not `0.0.0.0`.** These documents can embed internal
   architecture and cost data; never expose them to the LAN.

```bash
uv run --no-project .claude/skills/richdocs/scripts/serve.py tmp/richdocs --open
```

## Pinned CDN libraries

Third-party libraries load from jsdelivr/CDN over `http://localhost` without
issue (the page origin is localhost; the CDN request is an ordinary
cross-origin script/style load, which is always allowed). **Always pin exact
versions** — floating majors is how a working document breaks a month later.

| Library | Pinned | URL pattern |
|---------|--------|-------------|
| marked (markdown) | 12.0.2 | `cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js` |
| mermaid | 11.4.1 | `cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js` |
| cytoscape | 3.30.2 | `cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js` |
| dagre + cytoscape-dagre | 0.8.5 / 2.5.0 | `…/npm/dagre@0.8.5/dist/dagre.min.js`, `…/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.js` |
| plotly | 2.35.2 | `cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js` |
| deck.gl | 9.0.36 | `cdn.jsdelivr.net/npm/deck.gl@9.0.36/dist.min.js` |
| MapLibre GL (vector basemap) | 4.7.1 | `…/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js` + `…/maplibre-gl.css` |
| duckdb-wasm (in-browser SQL) | 1.32.0 | `…/npm/@duckdb/duckdb-wasm@1.32.0/+esm` (ESM; **pin the stable, not `latest` = a -dev build**) |
| Tailwind (play CDN) | 3.4.16 | `cdn.jsdelivr.net/npm/tailwindcss-cdn@3.4.16/tailwindcss.js` (or `cdn.tailwindcss.com/3.4.16`) |
| Google Fonts | n/a | `fonts.googleapis.com/css2?family=…&display=swap` |

Notes:

- `md2html.py` output uses only marked + mermaid eagerly; cytoscape/plotly are
  **lazy-injected** on first fenced-block use, so a plain prose doc costs two
  script loads, not seven.
- Tailwind's play CDN is a runtime JIT — fine for local viewers, wrong for
  anything committed/production (use a build). Google Fonts: always
  `display=swap` and a system-font fallback stack so offline viewing degrades
  to readable, not invisible, text.
- **Offline is environment degradation, announce it**: the generated JS
  console.errors and falls back (baked `FALLBACK_TOKENS`, unstyled fenced
  blocks shown as code). If the user's request *requires* the interactive
  canvas, offline is a loud failure, not a fallback (escalators-not-stairs).

## Port etiquette

Default port **8642** (unregistered, avoids 8000/8080/3000/5173 collisions
with dev servers). Multiple documents: one `serve.py` per output dir on
distinct ports, or point one server at a parent dir and browse subpaths.

## Deeper patterns

`serve.py` is deliberately minimal: static files + no-store, nothing else.
A document that needs routing, sidebars, or an `--archive` bundle has
outgrown the companion — build it as a standalone SPA sub-project (rung 4 of
the fidelity ladder in `discovery-docs.md`), not by extending this server.
