# Static SPA viewer — generate / serve / inline / archive

Part of the **cli** skill ([SKILL.md](../SKILL.md)). How to make a CLI emit a static,
server-optional single-page viewer: client-side routing, a collapsible sidebar,
light/dark + rebrandable theming, a graph (Cytoscape) or chart (Plotly) canvas, and the
`generate`/`serve`/`--inline`/`--archive` command surface. Builds on
[cli-foundations.md](cli-foundations.md).

## The core idea

**Python emits a renderer-agnostic JSON payload next to a templated HTML+JS viewer;
vanilla JS renders it client-side.** No web framework, no build step. The same skeleton
serves a Cytoscape graph or a Plotly chart — only the "build the canvas from JSON" call
differs. Two tokens are stamped into the templates at write time:

- `{{BUILD_ID}}` — a UTC timestamp (`%Y%m%dT%H%M%SZ`): cache-bust + a visible banner.
- `{{SOURCE}}` — where the data came from.

```python
def _build_id(): return dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
def _apply_tokens(t, *, build_id, source):
    return t.replace("{{BUILD_ID}}", build_id).replace("{{SOURCE}}", source)
```

Every JSON/JS fetch appends `?v=<BUILD_ID>` so a regenerated output dir can't serve a
stale payload. **`design-tokens.json` is copied verbatim — never templated** (it stays
the editable re-skin point).

## Client-side SPA + deep-linkable routing

The URL is the router; CSS shows the active view from one attribute on `<body>`.

```css
body[data-view="overview"] #detail  { display: none; }
body[data-view="detail"]   #overview{ display: none; }
```

```js
const PARAM = "item";
const url = () => location.pathname + location.search + location.hash;
function navigate(id) {
  const p = new URLSearchParams(location.search);
  id ? p.set(PARAM, id) : p.delete(PARAM);
  const next = location.pathname + (p.toString() ? "?" + p : "") + location.hash;
  if (next !== url()) history.pushState(null, "", next);   // no-op guard
  applyRoute(id);
}
function applyRoute(id) {
  document.body.dataset.view = id ? "detail" : "overview";
  id ? renderDetail(id) : renderOverview();
}
addEventListener("popstate", () =>
  applyRoute(new URLSearchParams(location.search).get(PARAM)));
```

For **multiple** state params (view + filter + selection), centralise read/write in
`readUrlState()` / `syncUrl()` and set a `suppressUrlSync` flag while rendering *from* a
popstate, so the handler doesn't write the URL back into history.

## Collapsible sidebar

One class on a root element; CSS hides the aside; persist + redraw the canvas (its
container width changed) on the next frame.

```js
const KEY = "app-sidebar";
function setCollapsed(c) {
  root.classList.toggle("sidebar-collapsed", c);
  btn.textContent = c ? "⟩" : "⟨";
  try { localStorage.setItem(KEY, c ? "1" : "0"); } catch {}
  requestAnimationFrame(redrawCanvas);   // Plotly.Plots.resize / cy.resize()+fit()
}
setCollapsed(localStorage.getItem(KEY) === "1");   // restore on boot
```

The `requestAnimationFrame(redraw)` is load-bearing for **any** canvas viewer — without
it the chart keeps its old width after the sidebar toggles.

## Light/dark theme — with the one critical nuance

Themes are CSS custom properties under `:root[data-theme="…"]`, **bootstrapped before
first paint** to avoid a flash of the wrong theme:

```html
<head>
<script>(function(){                 // runs BEFORE the body — no FOUC
  var s=null; try{ s=localStorage.getItem("app-theme"); }catch(e){}
  var light = matchMedia && matchMedia("(prefers-color-scheme: light)").matches;
  document.documentElement.setAttribute("data-theme",
    s==="light"||s==="dark" ? s : (light ? "light" : "dark"));
})();</script>
<style>:root[data-theme="dark"]{--canvas:#242C30;--text:#E3E6E7;/* … */}</style>
</head>
```

**Critical:** a canvas (Plotly/Cytoscape) **cannot read CSS variables**. A theme flip
must do *two* things — set `data-theme` (re-themes the chrome via CSS) **and** feed a
parallel JS palette into the canvas and re-render. The `:root[data-theme]` CSS block is
only the first-paint chrome fallback.

## Rebrandable theming via `design-tokens.json`

The anti-repetition payoff: **build the viewer once, re-skin by editing one JSON file.**
Tokens (palette, fonts, thresholds, optionally a `brands` map) are fetched at runtime and
turned into CSS vars + a JS palette. A re-skin needs no rebuild — edit, re-serve, refresh.

```js
const CHROME_VARS = { canvas:"--canvas", text:"--text", accent:"--accent" /* … */ };
async function loadTokens() {
  if (window.__APP_TOKENS__) return window.__APP_TOKENS__;     // inline build
  try { const r = await fetch(`design-tokens.json?v=${BUILD_ID}`, {cache:"no-store"});
        if (r.ok) return await r.json(); } catch {}
  return FALLBACK_TOKENS;                  // soft-fail keeps the viewer alive
}
function applyTheme(theme) {
  const root = document.documentElement;
  for (const [k, v] of Object.entries(CHROME_VARS))
    if (theme.chrome[k]) root.style.setProperty(v, theme.chrome[k]);
  redrawCanvasWithPalette(theme.canvasPalette);   // canvas can't read CSS vars
}
```

- A small **`FALLBACK_TOKENS`** baked into the JS is a soft-fail net only (used when the
  fetch fails), never the source of truth.
- **Data-encoding colours are NOT branded.** Colours that encode *meaning* (status =
  red/amber/green, a per-type palette) live in tokens too but stay constant across
  brands — only chrome/accent re-skins.
- A `brands` map (each brand → fonts + `themes.{light,dark}`) lets a picker switch brand
  live and persist it; a single-brand viewer just omits the map.

## The canvas: Cytoscape (graph) or Plotly (chart)

Generic rule both obey: **Python emits a flat JSON payload; JS builds the figure; a
click routes through `navigate()`.** Pin the renderer lib at a specific version (CDN or
vendored).

- **Plotly:** build traces from the data rows in JS and call `Plotly.react` (not
  `newPlot`) so theme/data changes re-render in place. Take the paper/plot/font/marker
  colours from the active theme's `plotly` sub-palette. Bind `plotly_click` →
  `points[0].customdata` (the id) → `navigate(id)`. Use `type:"scatter"` (SVG), not
  `scattergl`, if you need clickable/addressable points (e.g. for e2e tests).
- **Cytoscape:** feed `elements` + a stylesheet built from the theme palette; lay out
  with `dagre`; bind `tap` on nodes → `navigate(id)`; rebuild the stylesheet on a theme
  flip. (For a graph, emit two payloads — a full element graph and a collapsed
  super-graph — and toggle between them client-side.)

## generate / serve

`generate` = query → pure transform → write assets. `serve` = **regenerate first**, then
host over the stdlib `http.server` with **no-store headers** so reloads always re-fetch
fresh JSON; a busy port fails loud.

```python
def cmd_generate(args):
    full = build_payload(args)            # pure
    write_outputs(args.output, full, source=str(args.source))   # or write_inline(...)
    return 0

def serve(out: Path, port: int):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k): super().__init__(*a, directory=str(out), **k)
        def end_headers(self):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache"); self.send_header("Expires", "0")
            super().end_headers()
    try: httpd = socketserver.TCPServer(("127.0.0.1", port), H)
    except OSError as e:
        raise RuntimeError(f"port {port} already in use — stop it or pass a different --port") from e
    with httpd: httpd.serve_forever()
```

## As-is (multi-file) vs `--inline` (single standalone file)

- **Multi-file** (`write_outputs`): HTML + JS + sidecar `*.json` + `design-tokens.json`.
  Needs a server — `file://` blocks `fetch`. The default; pairs with `serve`.
- **`--inline`** (`write_inline`): one self-contained HTML with the data + JS inlined,
  opens over `file://`, no server. Embed the payload on a `window.__APP_DATA__` global
  and **escape `</` → `<\/`** so a stray `</script>` inside a string value (a node name,
  a tag) can't terminate the inline `<script>` early. The JS prefers the global:

```python
def write_inline(out, payload, *, source):
    build_id = _build_id()
    data = json.dumps(payload).replace("</", "<\\/")              # the gotcha
    data_script = f"<script>window.__APP_DATA__ = {data};</script>"
    inline_js = "<script>\n" + JS_TEMPLATE + "\n</script>"
    html = HTML_TEMPLATE.replace(JS_INCLUDE, f"{data_script}\n{inline_js}")
    (out / "app.html").write_text(_apply_tokens(html, build_id=build_id, source=source))
```

```js
async function fetchView(name) {
  if (window.__APP_DATA__?.[name]) return window.__APP_DATA__[name];   // inline build
  return (await fetch(`${name}.json?v=${BUILD_ID}`, {cache:"no-store"})).json();
}
```

## `--archive`

Bundle whichever declared viewer files are present into a flat (fetch-relative) zip.
A multi-file build zips all of them; an `--inline` build zips the one HTML. Fail loud on
a missing dir / empty set.

```python
VIEWER_FILES = ("app.html", "app.js", "data.json", "design-tokens.json")
def write_archive(out: Path, zip_path: Path) -> list[str]:
    if not out.is_dir(): raise FileNotFoundError(f"{out} does not exist — generate first")
    present = [n for n in VIEWER_FILES if (out / n).is_file()]
    if not present: raise FileNotFoundError("no viewer assets found — nothing to archive")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for n in present: zf.write(out / n, arcname=n)
    return sorted(present)
```

CLI sugar: bare `--archive` → `<output>/app.zip`; `--archive PATH` → `PATH`.

## Pitfalls

- **Canvas can't read CSS vars** — every theme/brand switch must re-feed a JS palette and
  re-render, not just flip `data-theme`.
- **FOUC** — the theme bootstrap must be an inline `<script>` in `<head>`, before paint.
- **Stale data after regenerate** — without `?v=<BUILD_ID>` on fetches, browsers serve
  cached JSON; the build-id query is the cheap fix.
- **`--inline` `</script>` break** — always `replace("</", "<\\/")` before embedding JSON.
- **Sidebar toggle leaves the chart the wrong width** — `requestAnimationFrame(redraw)`.
- **`file://` multi-file build looks broken** — that's expected (fetch is blocked); use
  `serve` or `--inline`. Say so in the `generate` output.
- **Don't render the chart server-side.** Emit data; let JS build the figure — it keeps
  the payload renderer-agnostic and the theme/brand switch a pure client re-render.
