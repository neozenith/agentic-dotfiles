"use strict";
// Runtime renderer for the paired-markdown viewer.
//
// Boot order: tokens -> CSS vars -> markdown -> marked.parse -> fenced-block
// upgrades. Tokens land first so nothing paints in fallback colours.
//
// This file contains NO template placeholders — it is copied verbatim into the
// output and is therefore real, lintable JS. Everything md2html.py needs to
// inject (build id, source name, CDN pins, fallback tokens) arrives through the
// #rd-config JSON block in viewer.html. Keep it that way: the moment a mustache
// placeholder appears here, the file stops parsing and stops being editable as
// JavaScript. A test enforces this (ADR-008).
var CFG = JSON.parse(document.getElementById("rd-config").textContent);

var BUILD_ID = CFG.buildId;
var SOURCE = CFG.source;
var CDN = CFG.cdn;
var FALLBACK_TOKENS = CFG.fallbackTokens;
var TOKENS = FALLBACK_TOKENS;

var cyBlocks = [];       // { el, payload, cy } — kept for re-theming
var plotlyBlocks = [];   // { el, payload }
var mermaidSources = []; // { el, src }
var lazyLoaded = {};

function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

// CSS can reach the chrome; canvas renderers cannot. Hence two palettes in the
// token file, and hence this function only handles the CSS half (ADR-004).
function applyTokenCss(tokens) {
  var css = "";
  ["light", "dark"].forEach(function (theme) {
    var t = tokens.themes[theme];
    css += ":root[data-theme=" + theme + "]{"
      + "--rd-bg:" + t.bg + ";--rd-fg:" + t.fg + ";--rd-muted:" + t.muted + ";"
      + "--rd-accent:" + t.accent + ";--rd-surface:" + t.surface + ";--rd-border:" + t.border + ";"
      + "--rd-font-body:" + tokens.fonts.body + ";--rd-font-mono:" + tokens.fonts.mono + ";}";
  });
  var style = document.getElementById("rd-token-css");
  if (!style) {
    style = document.createElement("style");
    style.id = "rd-token-css";
    document.head.appendChild(style);
  }
  style.textContent = css;
}

function loadScript(name, url) {
  if (lazyLoaded[name]) return lazyLoaded[name];
  lazyLoaded[name] = new Promise(function (resolve, reject) {
    var s = document.createElement("script");
    s.src = url;
    s.onload = resolve;
    s.onerror = function () { reject(new Error("failed to load " + url)); };
    document.head.appendChild(s);
  });
  return lazyLoaded[name];
}

// ?v=BUILD_ID + no-store: the whole point of the live-authoring loop is that a
// browser refresh shows the edited markdown, never a cached copy.
function fetchNoStore(url) {
  return fetch(url + "?v=" + BUILD_ID, { cache: "no-store" }).then(function (r) {
    if (!r.ok) throw new Error("HTTP " + r.status + " fetching " + url);
    return r;
  });
}

function showError(el, err) {
  var div = document.createElement("div");
  div.className = "rd-error";
  div.textContent = String(err && err.message ? err.message : err);
  el.replaceChildren(div);
  console.error(err);
}

// ── Mermaid ────────────────────────────────────────────────────────────────
// Rendered mermaid SVG is not re-themable in place: it must be re-rendered from
// source on every theme flip.
function renderAllMermaid() {
  if (mermaidSources.length === 0) return Promise.resolve();
  window.mermaid.initialize({
    startOnLoad: false,
    theme: currentTheme() === "dark" ? "dark" : "default",
    securityLevel: "loose"
  });
  var seq = Promise.resolve();
  mermaidSources.forEach(function (m, i) {
    seq = seq.then(function () {
      return window.mermaid.render("rd-mmd-" + BUILD_ID + "-" + i + "-" + currentTheme(), m.src)
        .then(function (out) { m.el.innerHTML = out.svg; })
        .catch(function (err) { showError(m.el, err); });
    });
  });
  return seq;
}

// ── Cytoscape ──────────────────────────────────────────────────────────────
function cyStyle(theme) {
  var c = TOKENS.canvas.cytoscape[theme];
  return [
    { selector: "node", style: {
        "background-color": c.nodeFill, "label": "data(label)",
        "color": c.nodeLabel, "font-size": "11px",
        "text-valign": "bottom", "text-margin-y": 4,
        "font-family": TOKENS.fonts.body } },
    { selector: ":parent", style: {
        "background-color": c.compoundBg, "border-color": c.compoundBorder,
        "border-width": 1, "text-valign": "top", "color": c.nodeLabel } },
    { selector: "edge", style: {
        "line-color": c.edge, "target-arrow-color": c.edge,
        "target-arrow-shape": "triangle", "curve-style": "bezier", "width": 1.5 } }
  ];
}

function renderCytoscape(block) {
  var payload = block.payload;
  var el = block.el;
  el.style.height = (payload.height || 420) + "px";
  var layout = payload.layout || { name: "dagre", rankDir: "LR" };
  if (layout.name === "dagre" && !layout.rankDir) layout.rankDir = "LR";
  if (block.cy) { block.cy.destroy(); }
  block.cy = window.cytoscape({
    container: el,
    elements: payload.elements,
    layout: layout,
    style: cyStyle(currentTheme())
  });
}

function loadCytoscapeLibs() {
  return loadScript("cytoscape", CDN.cytoscape)
    .then(function () { return loadScript("dagre", CDN.dagre); })
    .then(function () { return loadScript("cytoscapeDagre", CDN.cytoscapeDagre); })
    .then(function () { window.cytoscape.use(window.cytoscapeDagre); });
}

// ── Plotly ─────────────────────────────────────────────────────────────────
function plotlyLayout(payload) {
  var p = TOKENS.canvas.plotly[currentTheme()];
  var layout = Object.assign({}, payload.layout || {});
  layout.paper_bgcolor = p.paper;
  layout.plot_bgcolor = p.plot;
  layout.font = Object.assign({}, layout.font || {}, { color: p.font, family: TOKENS.fonts.body });
  layout.colorway = p.series;
  layout.xaxis = Object.assign({}, layout.xaxis || {}, { gridcolor: p.grid });
  layout.yaxis = Object.assign({}, layout.yaxis || {}, { gridcolor: p.grid });
  return layout;
}

function renderPlotly(block) {
  return window.Plotly.react(block.el, block.payload.data, plotlyLayout(block.payload), { responsive: true });
}

// ── Fenced-block upgrade ───────────────────────────────────────────────────
// A block's `data` may be a URL string instead of inline data — fetch and merge.
function resolvePayload(raw) {
  var payload = JSON.parse(raw);
  if (typeof payload.data === "string") {
    return fetchNoStore(payload.data).then(function (r) { return r.json(); }).then(function (remote) {
      if (Array.isArray(remote)) {
        payload.data = remote;
      } else {
        delete payload.data;
        payload = Object.assign({}, remote, payload);
      }
      return payload;
    });
  }
  return Promise.resolve(payload);
}

// cytoscape/dagre/plotly are injected only when a doc actually uses them, so a
// plain prose doc pays for none of them.
function upgradeFences(article) {
  var jobs = [];
  article.querySelectorAll("pre > code").forEach(function (code) {
    var lang = (code.className.match(/language-([\w-]+)/) || [])[1];
    if (lang !== "mermaid" && lang !== "cytoscape" && lang !== "plotly") return;
    var pre = code.parentElement;
    var div = document.createElement("div");
    div.className = "rd-canvas rd-" + lang;
    pre.replaceWith(div);
    var raw = code.textContent;
    if (lang === "mermaid") {
      mermaidSources.push({ el: div, src: raw });
      return;
    }
    jobs.push(resolvePayload(raw).then(function (payload) {
      var block = { el: div, payload: payload };
      if (lang === "cytoscape") { cyBlocks.push(block); }
      else { plotlyBlocks.push(block); }
    }).catch(function (err) { showError(div, err); }));
  });

  return Promise.all(jobs).then(function () {
    var loads = [];
    if (cyBlocks.length) loads.push(loadCytoscapeLibs());
    if (plotlyBlocks.length) loads.push(loadScript("plotly", CDN.plotly));
    return Promise.all(loads);
  }).then(function () {
    cyBlocks.forEach(function (b) { try { renderCytoscape(b); } catch (e) { showError(b.el, e); } });
    plotlyBlocks.forEach(function (b) { renderPlotly(b).catch(function (e) { showError(b.el, e); }); });
    return renderAllMermaid();
  });
}

function wrapTables(article) {
  article.querySelectorAll("table").forEach(function (table) {
    var wrap = document.createElement("div");
    wrap.className = "rd-table-wrap";
    table.replaceWith(wrap);
    wrap.appendChild(table);
  });
}

// ── Theme toggle ───────────────────────────────────────────────────────────
// CSS vars flip themselves; the canvas renderers must be re-fed by hand.
function retheme() {
  cyBlocks.forEach(function (b) { try { renderCytoscape(b); } catch (e) { showError(b.el, e); } });
  plotlyBlocks.forEach(function (b) { renderPlotly(b).catch(function (e) { showError(b.el, e); }); });
  renderAllMermaid();
}

document.getElementById("rd-theme-toggle").addEventListener("click", function () {
  var next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("richdocs-theme", next); } catch (e) {}
  retheme();
});

// ── Boot ───────────────────────────────────────────────────────────────────
// --inline mode pre-seeds window.__DOC_*__; multi-file mode fetches.
function loadTokens() {
  if (window.__DOC_TOKENS__ !== undefined) return Promise.resolve(window.__DOC_TOKENS__);
  return fetchNoStore("design-tokens.json").then(function (r) { return r.json(); })
    .catch(function (err) {
      console.error("design-tokens.json fetch failed; using baked fallback tokens", err);
      return FALLBACK_TOKENS;
    });
}

function loadDoc() {
  if (window.__DOC_MD__ !== undefined) return Promise.resolve(window.__DOC_MD__);
  return fetchNoStore(SOURCE).then(function (r) { return r.text(); });
}

loadTokens().then(function (tokens) {
  TOKENS = tokens;
  applyTokenCss(tokens);
  return loadDoc();
}).then(function (md) {
  var article = document.getElementById("rd-article");
  article.innerHTML = window.marked.parse(md);
  wrapTables(article);
  return upgradeFences(article);
}).catch(function (err) {
  showError(document.getElementById("rd-article"), err);
});
