"use strict";
// Theme showcase renderer.
//
// Placeholder-free (ADR-008): everything from generation time arrives via the
// #sc-payload JSON block. SC_SINGLE is set by the shell (one brand, or a gallery).
//
// Two axes of state, both on <html>:
//   data-brand  — which brandpack is active (drives --rd-* AND the scoped theme.css)
//   data-theme  — light | dark

var SC = JSON.parse(document.getElementById("sc-payload").textContent);
var BRANDS = SC.brands;
var lazy = {};

function brand() {
  var n = document.documentElement.getAttribute("data-brand");
  return BRANDS.find(function (b) { return b.name === n; }) || BRANDS[0];
}
function mode() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function loadScript(name, url) {
  if (lazy[name]) return lazy[name];
  lazy[name] = new Promise(function (res, rej) {
    var s = document.createElement("script");
    s.src = url; s.onload = res;
    s.onerror = function () { rej(new Error("failed to load " + url)); };
    document.head.appendChild(s);
  });
  return lazy[name];
}

// A stylesheet has no reliable onload across browsers, and we only need it present
// before the map paints, so resolve on append — MapLibre tolerates the brief gap.
function loadCss(name, url) {
  if (lazy["css:" + name]) return lazy["css:" + name];
  lazy["css:" + name] = new Promise(function (res) {
    var l = document.createElement("link");
    l.rel = "stylesheet"; l.href = url; l.onload = res;
    document.head.appendChild(l); res();
  });
  return lazy["css:" + name];
}

// ── tokens -> CSS vars ─────────────────────────────────────────────────────
function applyTokens(b) {
  var t = b.tokens;
  var display = t.fonts.display || t.fonts.body;
  var css = "";
  ["light", "dark"].forEach(function (m) {
    var c = t.themes[m];
    // accent has THREE jobs. Conflating them is what rendered V2 in cyan.
    var fill = c.accent;
    var on = c.onAccent || c.bg;      // text ON the fill
    var link = c.link || c.accent;    // headings/links — must be text-safe
    css += ':root[data-brand="' + b.name + '"][data-theme=' + m + ']{'
      + "--rd-bg:" + c.bg + ";--rd-fg:" + c.fg + ";--rd-muted:" + c.muted + ";"
      + "--rd-accent:" + fill + ";--rd-on-accent:" + on + ";--rd-link:" + link + ";"
      + "--rd-surface:" + c.surface + ";--rd-border:" + c.border + ";"
      + "--rd-radius:" + (c.radius !== undefined ? c.radius : "12px") + ";"
      + "--rd-pill:" + (c.pill !== undefined ? c.pill : "999px") + ";"
      + "--rd-font-body:" + t.fonts.body + ";--rd-font-mono:" + t.fonts.mono + ";"
      + "--rd-font-display:" + display + ";}";
  });
  var el = document.getElementById("sc-tokens-" + b.name);
  if (!el) {
    el = document.createElement("style");
    el.id = "sc-tokens-" + b.name;
    document.head.appendChild(el);
  }
  el.textContent = css;
}
BRANDS.forEach(applyTokens);   // every brand's vars, all scoped — no flicker on switch

// ── swatches ───────────────────────────────────────────────────────────────
function swatch(hex, label, sub) {
  var dark = (function () {
    var r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 150;
  })();
  return '<div class="sc-sw" style="background:' + hex + ';color:' + (dark ? "#fff" : "#000") + '">'
    + (label ? "<b>" + label + "</b>" : "") + "<span>" + (sub || hex) + "</span></div>";
}

function paintSwatches() {
  var b = brand(), m = mode(), t = b.tokens;
  var th = t.themes[m];
  document.getElementById("sc-theme-ramp").innerHTML =
    ["bg", "surface", "border", "muted", "fg", "accent"].map(function (k) {
      return swatch(th[k], k, th[k]);
    }).join("");

  var series = t.canvas.plotly[m].series || [];
  document.getElementById("sc-series-ramp").innerHTML =
    series.map(function (c, i) { return swatch(c, String(i + 1), c); }).join("");

  var cats = t.categoryColours || {};
  document.getElementById("sc-cat-ramp").innerHTML =
    Object.keys(cats).map(function (k) { return swatch(cats[k], k, cats[k]); }).join("");

  var plot = t.canvas.plotly[m];
  var muted = plot.muted || [];
  document.getElementById("sc-muted-ramp").innerHTML =
    muted.map(function (c, i) { return swatch(c, "grey " + (i + 1), c); }).join("");

  var seq = plot.sequential || [];
  document.getElementById("sc-seq-ramp").innerHTML =
    seq.map(function (c, i) {
      return swatch(c, i === 0 ? "low" : i === seq.length - 1 ? "high" : "", c);
    }).join("");
}

// ── deuteranopia (Machado-2009) — the same maths the themecheck gate uses, so the
// page SHOWS what the build enforces. If these ever disagree, one of them is lying.
function deuteranopia(hex) {
  var lin = function (c) { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  var gam = function (c) {
    c = c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
    return Math.round(Math.max(0, Math.min(1, c)) * 255).toString(16).padStart(2, "0");
  };
  var r = lin(parseInt(hex.slice(1, 3), 16)),
      g = lin(parseInt(hex.slice(3, 5), 16)),
      b = lin(parseInt(hex.slice(5, 7), 16));
  return "#" + gam(0.367322 * r + 0.860646 * g - 0.227968 * b)
             + gam(0.280085 * r + 0.672501 * g + 0.047413 * b)
             + gam(-0.011820 * r + 0.042940 * g + 0.968881 * b);
}

function divScale(d) {
  return d.good.slice().reverse().concat([d.zero], d.bad);
}

// A diverging scale a brand does NOT ship must not be invented here. V2 has no
// green-safe alternate — every green-adjacent hue collapses against its pink — so
// its `divergingAlt` is absent, and this simply renders one scale.
function paintDiverging() {
  var t = brand().tokens, m = mode();
  var plot = t.canvas.plotly[m];
  var scales = [];
  if (plot.diverging) scales.push({ key: "diverging", d: plot.diverging, note: "default" });
  if (plot.divergingAlt) scales.push({ key: "divergingAlt", d: plot.divergingAlt, note: "alternate" });

  document.getElementById("sc-divs").innerHTML = scales.map(function (s) {
    return "<h3>" + (s.d.label || s.key) + ' <span style="font-weight:400;color:var(--rd-muted);font-size:.8rem">· '
      + s.note + "</span></h3>"
      + '<div class="sc-ramp">' + divScale(s.d).map(function (c, i) {
          var lab = i === 0 ? "good" : i === 3 ? "zero" : i === 6 ? "bad" : "";
          return swatch(c, lab, c);
        }).join("") + "</div>";
  }).join("") + (plot.divergingAlt ? "" :
    '<p style="font-size:.85rem;color:var(--rd-muted);margin-top:.6rem">'
    + "This brand ships <strong>no green-semantics alternate</strong>: every green-adjacent "
    + "hue collapses against its warm pole under deuteranopia. Rather than invent one, "
    + "the scale is reinforced with a sign and an arrow.</p>");

  document.getElementById("sc-div-sims").innerHTML = scales.map(function (s) {
    var arr = divScale(s.d);
    var poleDelta = "";  // rendered honestly: what the reader can still tell apart
    return '<div style="margin-bottom:1rem"><div style="font-size:.85rem;font-weight:600">'
      + (s.d.label || s.key) + poleDelta + "</div>"
      + '<div class="sc-ramp">' + arr.map(function (c) {
          return '<div class="sc-sw" style="background:' + deuteranopia(c) + ';height:44px"></div>';
        }).join("") + "</div></div>";
  }).join("")
  + '<div style="margin-bottom:1rem"><div style="font-size:.85rem;font-weight:600;color:var(--rd-muted)">'
  + "green ↔ red · what this system refuses to ship</div>"
  + '<div class="sc-ramp">'
  + ["#1a7f37", "#4caf50", "#8bc34a", plot.diverging.zero, "#ef9a9a", "#e57373", "#c62828"]
      .map(function (c) { return '<div class="sc-sw" style="background:' + deuteranopia(c) + ';height:44px"></div>'; }).join("")
  + '</div><div style="font-size:.8rem;color:var(--rd-muted);margin-top:.3rem">'
  + "Both poles become the same colour. The scale conveys nothing.</div></div>";
}

function paintStatus() {
  var t = brand().tokens, m = mode();
  if (!t.status) { document.getElementById("sc-status").innerHTML = ""; return; }
  var st = t.status[m];
  var order = ["good", "warning", "serious", "critical"];
  var glyph = { good: "\u2713", warning: "!", serious: "\u25B2", critical: "\u2715" };
  document.getElementById("sc-status").innerHTML =
    '<div style="display:flex;gap:.6rem;flex-wrap:wrap;margin-top:.8rem">'
    + order.filter(function (k) { return st.colours[k]; }).map(function (k) {
        return '<span class="sc-tag" style="color:' + st.colours[k] + '">'
          + glyph[k] + " " + st.labels[k] + "</span>";
      }).join("") + "</div>";
}

// ── charts ─────────────────────────────────────────────────────────────────
// Plotly MUTATES the layout object it is handed — it writes computed ranges back
// onto `xaxis`/`yaxis`. Sharing one `base` across charts via Object.assign is a
// SHALLOW copy, so every chart ends up pointing at the same axis objects: the bar
// chart wrote a numeric y-range, and the heatmap then inherited it while holding
// categorical rows. Degenerate axis, `height="NaN"`, raster silently broken.
// Hence: a FRESH layout per chart, never a shared one.
function plotlyBase(t, m) {
  var p = t.canvas.plotly[m];
  return {
    paper_bgcolor: p.paper, plot_bgcolor: p.plot,
    font: { family: t.fonts.body, color: p.font, size: 12 },
    colorway: p.series,
    xaxis: { gridcolor: p.grid, zerolinecolor: p.grid },
    yaxis: { gridcolor: p.grid, zerolinecolor: p.grid },
    margin: { l: 48, r: 16, t: 28, b: 40 },
    legend: { font: { color: p.font, size: 11 } },
    title: { font: { family: t.fonts.display || t.fonts.body, size: 14 } }
  };
}

function drawCharts() {
  return loadScript("plotly", SC.cdn.plotly).then(function () {
    var b = brand(), m = mode(), t = b.tokens;
    var cfg = { displayModeBar: false, responsive: true };
    var rooms = ["Auth", "Search", "Billing", "Media", "Graph", "Cache"];

    // A fresh layout every time. Never reuse one Plotly has already touched.
    var L = function (extra) { return Object.assign(plotlyBase(t, m), extra || {}); };

    Plotly.react("sc-bar", [{
      type: "bar", x: rooms, y: [482, 431, 377, 299, 265, 214],
      marker: { color: t.canvas.plotly[m].series, line: { width: 2, color: t.canvas.plotly[m].plot } }
    }], L({ title: { text: "Requests by service" } }), cfg);

    var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"];
    var traces = ["us-east", "eu-west", "ap-south"].map(function (name, i) {
      return {
        type: "scatter", mode: "lines+markers", name: name, x: months,
        y: months.map(function (_, j) { return 40 + i * 18 + j * (7 + i * 4); }),
        line: { width: 2 }, marker: { size: 6 }
      };
    });
    Plotly.react("sc-line", traces, L({ title: { text: "Requests per region" } }), cfg);

    var plot = t.canvas.plotly[m];

    // Storytelling-with-data: everything grey, ONE series keeps its hue.
    var greys = plot.muted || [];
    var hiTraces = rooms.map(function (nm, i) {
      var on = i === 0;
      return {
        type: "scatter", mode: on ? "lines+markers" : "lines", name: nm, x: months,
        y: months.map(function (_, j) { return 60 + i * -7 + j * (on ? 11 : 2.5); }),
        line: { color: on ? plot.series[0] : greys[i % greys.length], width: on ? 3.5 : 1.5 },
        marker: { size: 6 }, showlegend: false
      };
    });
    var hiLayout = L({
      title: { text: "One accent. Everything else recedes." },
      annotations: rooms.map(function (nm, i) {
        return {
          x: months.length - 0.9, y: 60 + i * -7 + (months.length - 1) * (i === 0 ? 11 : 2.5),
          xref: "x", yref: "y", text: nm, showarrow: false, xanchor: "left",
          font: { size: 11, color: i === 0 ? plot.series[0] : plot.font }
        };
      }),
    });
    hiLayout.xaxis.range = [-0.3, months.length + 2];
    Plotly.react("sc-highlight", hiTraces, hiLayout, cfg);

    // Sequential: magnitude. One hue, monotone lightness.
    if (plot.sequential) {
      var days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
      var hours = ["4pm", "6pm", "8pm", "10pm", "12am"];
      Plotly.react("sc-heat", [{
        type: "heatmap", x: days, y: hours, xgap: 2, ygap: 2,
        z: hours.map(function (_, hi) {
          return days.map(function (__, di) {
            return Math.round(10 + 70 * Math.sin((hi + 1) / 5 * Math.PI) * (0.35 + 0.65 * (di >= 4 ? 1 : di / 5)));
          });
        }),
        colorscale: plot.sequential.map(function (c, i) { return [i / (plot.sequential.length - 1), c]; }),
        colorbar: { tickfont: { color: plot.font }, outlinewidth: 0, thickness: 12 }
      }], L({ title: { text: "Utilisation (sequential)" } }), cfg);
    }

    // Diverging: polarity. Sign + arrow carry the meaning; colour reinforces.
    if (plot.diverging) {
      var d = plot.diverging;
      var svc = ["NAT Gateway", "EC2", "S3 Std-IA", "Lambda", "Route 53", "CloudWatch"];
      var vals = [34.0, 12.5, -11.5, -3.2, 0.0, 21.8];
      var pick = function (v) {
        if (v > 20) return d.bad[2]; if (v > 8) return d.bad[1]; if (v > 2) return d.bad[0];
        if (v < -8) return d.good[2]; if (v < -2) return d.good[1];
        return d.zero;
      };
      Plotly.react("sc-div-chart", [{
        type: "bar", orientation: "h", x: vals, y: svc,
        marker: { color: vals.map(pick), line: { width: 2, color: plot.plot } },
        text: vals.map(function (v) { return (v > 0 ? "\u25B2 +" : v < 0 ? "\u25BC " : "\u2014 ") + v.toFixed(1) + "%"; }),
        textposition: "outside",
        textfont: { family: t.fonts.mono, color: plot.font, size: 11 }
      }], (function () {
        var lay = L({
          title: { text: "Cost vs baseline — sign and arrow carry the meaning" },
          margin: { l: 110, r: 24, t: 34, b: 40 }
        });
        lay.xaxis.range = [-26, 52];
        lay.xaxis.zeroline = true;
        lay.xaxis.zerolinewidth = 2;
        return lay;
      })(), cfg);
    }
  });
}

// ── cytoscape ──────────────────────────────────────────────────────────────
// A deliberately dense graph: six compound clusters, each carrying a `category`
// so it is tinted by that category's hue with a contrast-safe label in every
// theme, plus fourteen leaf services and their cross-cluster flows. This exercises
// compound layout, categorical hues, and per-theme label legibility at once.
var CY_ELEMENTS = [
  { data: { id: "edge", label: "Edge", category: "Networking" } },
  { data: { id: "sec", label: "Security", category: "Security" } },
  { data: { id: "compute", label: "Compute", category: "Compute" } },
  { data: { id: "integ", label: "Integration", category: "Integration" } },
  { data: { id: "data", label: "Data", category: "Database" } },
  { data: { id: "store", label: "Storage", category: "Storage" } },

  { data: { id: "cdn", label: "CDN", parent: "edge" } },
  { data: { id: "lb", label: "Load Balancer", parent: "edge", variant: "alt" } },
  { data: { id: "waf", label: "WAF", parent: "sec" } },
  { data: { id: "authz", label: "Authorizer", parent: "sec", variant: "alt" } },
  { data: { id: "api", label: "API Service", parent: "compute" } },
  { data: { id: "worker", label: "Worker", parent: "compute", variant: "alt" } },
  { data: { id: "agent", label: "Agent", parent: "compute" } },
  { data: { id: "queue", label: "Queue", parent: "integ" } },
  { data: { id: "bus", label: "Event Bus", parent: "integ", variant: "alt" } },
  { data: { id: "primary", label: "Primary DB", parent: "data" } },
  { data: { id: "cache", label: "Cache", parent: "data", variant: "alt" } },
  { data: { id: "blobs", label: "Object Store", parent: "store" } },
  { data: { id: "warehouse", label: "Warehouse", parent: "store", variant: "alt" } },

  { data: { source: "cdn", target: "lb", label: "route" } },
  { data: { source: "lb", target: "waf", label: "inspect" } },
  { data: { source: "waf", target: "authz", label: "verify" } },
  { data: { source: "authz", target: "api", label: "https" } },
  { data: { source: "api", target: "cache", label: "read" } },
  { data: { source: "api", target: "primary", label: "write" } },
  { data: { source: "api", target: "queue", label: "enqueue" } },
  { data: { source: "queue", target: "worker", label: "consume" } },
  { data: { source: "worker", target: "warehouse", label: "load" } },
  { data: { source: "api", target: "blobs", label: "store" } },
  { data: { source: "worker", target: "bus", label: "emit" } },
  { data: { source: "bus", target: "agent", label: "trigger" } },
  { data: { source: "agent", target: "primary", label: "update" } }
];
var cyBlock = { el: null, payload: { elements: CY_ELEMENTS, height: 480 } };

function drawGraph() {
  return loadScript("cytoscape", SC.cdn.cytoscape)
    .then(function () { return loadScript("dagre", SC.cdn.dagre); })
    .then(function () { return loadScript("cydagre", SC.cdn.cytoscapeDagre); })
    .then(function () {
      if (!lazy._cyReg) { window.cytoscape.use(window.cytoscapeDagre); lazy._cyReg = true; }
      cyBlock.el = document.getElementById("sc-cy");
      // Reuses the SAME graph styling the doc viewer uses (viewer-cytoscape.js),
      // so the showcase cannot drift from what a real doc renders.
      rdRenderCytoscape(cyBlock, brand().tokens, mode());
    });
}

// ── mermaid — dual density ───────────────────────────────────────────────────
// The SAME system at two zoom levels: an at-a-glance overview, and a detailed
// view with subgraph clusters. A dense diagram stresses layout, edge routing, and
// the themed palette far harder than a five-box flow.
var MERMAID_OVERVIEW = [
  "flowchart LR",
  "  U([Client]) --> G[API Gateway]",
  "  G --> S[Services]",
  "  S --> D[(Data store)]",
  "  S --> Q[/Queue/]",
  "  Q --> W[Workers]"
].join("\n");

var MERMAID_DETAIL = [
  "flowchart TB",
  "  subgraph edge[Edge]",
  "    CDN[CDN] --> LB[Load Balancer]",
  "  end",
  "  subgraph sec[Security]",
  "    WAF[WAF] --> AUTH[Authorizer]",
  "  end",
  "  subgraph compute[Compute]",
  "    API[API Service]",
  "    WRK[Worker]",
  "    AGT[Agent]",
  "  end",
  "  subgraph data[Data]",
  "    PDB[(Primary DB)]",
  "    CACHE[(Cache)]",
  "    WH[(Warehouse)]",
  "  end",
  "  LB --> WAF",
  "  AUTH --> API",
  "  API --> CACHE",
  "  API --> PDB",
  "  API --> Q[/Queue/]",
  "  Q --> WRK",
  "  WRK --> WH",
  "  WRK --> BUS([Event Bus])",
  "  BUS --> AGT",
  "  AGT --> PDB"
].join("\n");

function drawMermaid() {
  var b = brand(), m = mode(), t = b.tokens, th = t.themes[m];
  window.mermaid.initialize({
    startOnLoad: false, theme: "base", securityLevel: "loose",
    themeVariables: {
      fontFamily: t.fonts.body, fontSize: "13px",
      background: th.bg, primaryColor: th.surface, primaryTextColor: th.fg,
      primaryBorderColor: th.accent, lineColor: th.muted, textColor: th.fg,
      mainBkg: th.surface, nodeBorder: th.accent,
      edgeLabelBackground: th.bg, tertiaryColor: th.surface,
      clusterBkg: th.surface, clusterBorder: th.border
    }
  });
  // Rendered mermaid SVG is not re-themable in place — always re-render both.
  var jobs = [["sc-mermaid", MERMAID_OVERVIEW, "ov"], ["sc-mermaid-detail", MERMAID_DETAIL, "de"]];
  return Promise.all(jobs.map(function (j) {
    var host = document.getElementById(j[0]);
    if (!host) return Promise.resolve();
    host.innerHTML = "";
    return window.mermaid
      .render("sc-mmd-" + j[2] + "-" + b.name + "-" + m + "-" + SC.buildId, j[1])
      .then(function (o) { host.innerHTML = o.svg; })
      .catch(function (e) { host.textContent = "mermaid error: " + e.message; });
  }));
}

// ── deck.gl: 3D embeddings + geographic ──────────────────────────────────────
// The SAME renderer a real richdocs doc uses (viewer-deckgl.js). Embeddings prove
// the 3D view is not only for colour space; the map proves a geographic view can
// ride a real vector basemap with no vendor key.
function hexRgb(h) {
  return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
}
function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
var embLocal = { el: null, payload: null };
var embGlobal = { el: null, payload: null };
var geoBlock = { el: null, payload: null };

// Two independent controls over the SAME point cloud:
//   colour — encode the KNOWN topic, or the EVoC-DISCOVERED cluster. Toggling is the
//            honest test of the embedding: do discovered clusters match known topics?
//   sel    — up to two chunks picked by click, to read their cosine distance. Cosine
//            is computed on the RAW vectors, so it is the true semantic distance,
//            independent of whichever 3D projection is on screen.
var embState = { colour: "topic", sel: [] };

function embColour(clusterColours) {
  return function (d) {
    return embState.colour === "cluster"
      ? (clusterColours[String(d.cluster)] || [130, 130, 130])
      : d.color;
  };
}

function embPayload(key, colourFn, halo) {
  var pts = SC.embeddings[key].points;
  var layers = [];
  // Halo layer FIRST (drawn under): a larger sphere at each selected point, so the
  // topic-coloured point sits inside a bright ring the eye finds immediately.
  if (embState.sel.length) {
    var picked = pts.filter(function (p) { return embState.sel.indexOf(p.idx) >= 0; });
    layers.push({
      type: "PointCloudLayer", id: "emb-halo", pointSize: 30, data: picked,
      getColor: function () { return halo; }
    });
  }
  layers.push({
    type: "PointCloudLayer", id: "emb-points", pointSize: 13, data: pts,
    getColor: colourFn,
    onClick: function (info) { if (info && info.object) selectEmb(info.object.idx); }
  });
  return { view: "orbit", height: 440, layers: layers };
}

function renderEmb() {
  if (typeof deck === "undefined") return;
  var t = brand().tokens, m = mode(), th = t.themes[m];
  var colourFn = embColour(SC.embeddings.local.clusterColors);
  var halo = hexRgb(th.link || th.accent).concat([220]);
  [["sc-emb-local", "local", embLocal], ["sc-emb-global", "global", embGlobal]].forEach(function (j) {
    var blk = j[2];
    blk.el = document.getElementById(j[0]);
    if (!blk.el) return;
    blk.payload = embPayload(j[1], colourFn, halo);
    try { rdRenderDeckGL(blk, t, m); } catch (e) { blk.el.textContent = "deckgl error: " + e.message; }
  });
  syncEmbControls();
  updateEmbReadout();
}

function selectEmb(idx) {
  var i = embState.sel.indexOf(idx);
  if (i >= 0) embState.sel.splice(i, 1);                    // click a picked point to drop it
  else if (embState.sel.length >= 2) embState.sel = [idx];  // a third pick starts a fresh pair
  else embState.sel.push(idx);
  renderEmb();
}

function syncEmbControls() {
  document.querySelectorAll("[data-emb-colour]").forEach(function (btn) {
    btn.setAttribute("aria-pressed", String(btn.dataset.embColour === embState.colour));
  });
}

function updateEmbReadout() {
  var el = document.getElementById("sc-emb-readout");
  if (!el) return;
  if (embState.sel.length < 2) {
    var one = embState.sel.length === 1;
    el.innerHTML = '<p class="sc-emb-hint">Click two points to compare their cosine distance. '
      + (one ? "One selected — pick a second." : "None selected.") + "</p>";
    return;
  }
  var by = {};
  SC.embeddings.local.points.forEach(function (p) { by[p.idx] = p; });
  var a = by[embState.sel[0]], b = by[embState.sel[1]];
  var dist = SC.embeddings.local.cosine[a.idx][b.idx];
  var sim = 1 - dist;
  var same = a.topic === b.topic;
  el.innerHTML =
    '<div class="sc-emb-pair">'
    + '<div class="sc-emb-chunk"><span class="sc-emb-topic">' + escapeHtml(a.topic) + "</span>"
    + escapeHtml(a.text) + "</div>"
    + '<div class="sc-emb-chunk"><span class="sc-emb-topic">' + escapeHtml(b.topic) + "</span>"
    + escapeHtml(b.text) + "</div></div>"
    + '<div class="sc-emb-metric">cosine distance <strong>' + dist.toFixed(3) + "</strong>"
    + " · similarity <strong>" + sim.toFixed(3) + "</strong>"
    + ' · <span class="' + (same ? "sc-emb-same" : "sc-emb-diff") + '">'
    + (same ? "same topic" : "different topics") + "</span></div>";
}

function drawGeo() {
  return Promise.all([
    loadScript("maplibre", SC.cdn.maplibre),
    loadCss("maplibre", SC.cdn.maplibreCss)
  ]).then(function () {
    var t = brand().tokens, m = mode();
    var plot = t.canvas.plotly[m], th = t.themes[m];
    var acc = hexRgb(th.link || th.accent);
    var s1 = hexRgb(plot.series[0]), s2 = hexRgb(plot.series[3] || plot.series[1]);
    // Melbourne is the home region (the hub); traffic fans to the other AU capitals.
    var regions = [
      { name: "Melbourne", coordinates: [144.96, -37.81] }, { name: "Sydney", coordinates: [151.21, -33.87] },
      { name: "Brisbane", coordinates: [153.03, -27.47] }, { name: "Perth", coordinates: [115.86, -31.95] },
      { name: "Adelaide", coordinates: [138.60, -34.93] }, { name: "Hobart", coordinates: [147.33, -42.88] },
      { name: "Darwin", coordinates: [130.84, -12.46] }, { name: "Canberra", coordinates: [149.13, -35.28] }
    ];
    var hub = regions[0].coordinates;
    var arcs = regions.slice(1).map(function (r) { return { from: hub, to: r.coordinates, name: r.name }; });
    geoBlock.el = document.getElementById("sc-geo");
    if (!geoBlock.el) return;
    geoBlock.payload = {
      view: "map", height: 520,
      // CartoDB dark-matter VECTOR style — MapLibre owns the basemap, deck the arcs.
      // Free, keyless, and crisp at any zoom; the same style hows-the-serenity uses.
      basemapStyle: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      initialViewState: { longitude: 134, latitude: -28, zoom: 3.4, pitch: 28, bearing: 0 },
      layers: [
        {
          type: "ArcLayer", data: arcs,
          getSourcePosition: function (d) { return d.from; },
          getTargetPosition: function (d) { return d.to; },
          getSourceColor: s1, getTargetColor: s2, getWidth: 2.5, getHeight: 0.4
        },
        {
          type: "ScatterplotLayer", data: regions,
          getPosition: function (d) { return d.coordinates; },
          getFillColor: acc, getRadius: 6, radiusUnits: "pixels",
          stroked: true, getLineColor: [255, 255, 255], lineWidthUnits: "pixels", getLineWidth: 1.5
        }
      ]
    };
    try { rdRenderDeckGL(geoBlock, t, m); } catch (e) { geoBlock.el.textContent = "deckgl error: " + e.message; }
  });
}

function drawDeck() {
  return loadScript("deckgl", SC.cdn.deckgl).then(function () {
    renderEmb();
    return drawGeo();
  });
}

// ── in-browser SQL: duckdb-wasm ──────────────────────────────────────────────
// The DATA→TRANSFORM half of the story: an analytical SQL engine (DuckDB compiled
// to WebAssembly) runs entirely in the browser — no server, no key. The SAME result
// rows can drive any block (chart shown here; a graph or map is the same shape).
//
// A seeded fact table stands in for "complex extracted data": per-service, per-region
// request counts + latency. Registered as JSON so the query reads it with read_json.
var SQL_ROWS = (function () {
  var services = ["Auth", "Search", "Billing", "Media", "Graph", "Cache"];
  var regions = ["REGION-01", "REGION-02", "REGION-03"];
  var base = { Auth: 160, Search: 150, Billing: 120, Media: 95, Graph: 88, Cache: 72 };
  var p95 = { Auth: 38, Search: 61, Billing: 44, Media: 120, Graph: 83, Cache: 12 };
  var rows = [];
  services.forEach(function (s, si) {
    regions.forEach(function (r, ri) {
      // Deterministic spread (no RNG): region and service index shape the numbers.
      rows.push({
        service: s, region: r,
        requests: base[s] + ri * 24 + si * 3,
        p95_ms: p95[s] + ri * 7 - si
      });
    });
  });
  return rows;
})();

var DEFAULT_SQL = [
  "SELECT service,",
  "       SUM(requests)        AS total_requests,",
  "       ROUND(AVG(p95_ms),1) AS avg_p95_ms",
  "FROM requests",
  "GROUP BY service",
  "ORDER BY total_requests DESC;"
].join("\n");

var duck = { ready: null, conn: null };

// Instantiate once. The cross-origin worker gotcha: a CDN worker URL cannot be given
// to `new Worker` directly, so it is wrapped in a same-origin Blob that importScripts
// it. selectBundle picks the mvp/eh bundle (no SharedArrayBuffer), so no COOP/COEP.
function initDuckDB() {
  if (duck.ready) return duck.ready;
  duck.ready = import(SC.cdn.duckdb).then(function (duckdb) {
    var bundles = duckdb.getJsDelivrBundles();
    return duckdb.selectBundle(bundles).then(function (bundle) {
      var workerUrl = URL.createObjectURL(new Blob(
        ['importScripts("' + bundle.mainWorker + '");'], { type: "text/javascript" }
      ));
      var worker = new Worker(workerUrl);
      var db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(), worker);
      return db.instantiate(bundle.mainModule, bundle.pthreadWorker).then(function () {
        URL.revokeObjectURL(workerUrl);
        return db.registerFileText("requests.json", JSON.stringify(SQL_ROWS));
      }).then(function () {
        return db.connect();
      }).then(function (conn) {
        // A view over the registered JSON, so the query reads a plain table name.
        return conn.query(
          "CREATE OR REPLACE VIEW requests AS SELECT * FROM read_json_auto('requests.json')"
        ).then(function () { duck.conn = conn; });
      });
    });
  });
  return duck.ready;
}

// Arrow → plain rows. 64-bit aggregates arrive as BigInt; coerce so Plotly + the
// table treat them as numbers rather than throwing on JSON/`toFixed`.
function arrowToRows(table) {
  var cols = table.schema.fields.map(function (f) { return f.name; });
  var rows = table.toArray().map(function (r) {
    var o = r.toJSON(), out = {};
    cols.forEach(function (c) {
      var v = o[c];
      out[c] = typeof v === "bigint" ? Number(v) : v;
    });
    return out;
  });
  return { cols: cols, rows: rows };
}

function renderSqlTable(cols, rows) {
  var head = "<tr>" + cols.map(function (c) { return "<th>" + escapeHtml(c) + "</th>"; }).join("") + "</tr>";
  var body = rows.map(function (row) {
    return "<tr>" + cols.map(function (c) {
      var v = row[c];
      var mono = typeof v === "number" ? ' class="mono"' : "";
      return "<td" + mono + ">" + escapeHtml(v === null || v === undefined ? "" : v) + "</td>";
    }).join("") + "</tr>";
  }).join("");
  document.getElementById("sc-sql-table").innerHTML =
    "<table><thead>" + head + "</thead><tbody>" + body + "</tbody></table>";
}

function renderSqlChart(cols, rows) {
  var host = document.getElementById("sc-sql-chart");
  if (typeof Plotly === "undefined" || !rows.length) { return; }
  var t = brand().tokens, m = mode();
  // x = first non-numeric column (a label); y = first numeric column after it.
  var xCol = cols.find(function (c) { return typeof rows[0][c] !== "number"; }) || cols[0];
  var yCol = cols.find(function (c) { return c !== xCol && typeof rows[0][c] === "number"; }) || cols[1];
  if (!yCol) { host.innerHTML = ""; return; }
  var plot = t.canvas.plotly[m];
  Plotly.react(host, [{
    type: "bar",
    x: rows.map(function (r) { return r[xCol]; }),
    y: rows.map(function (r) { return r[yCol]; }),
    marker: { color: plot.series, line: { width: 2, color: plot.plot } }
  }], Object.assign(plotlyBase(t, m), { title: { text: yCol + " by " + xCol } }),
    { displayModeBar: false, responsive: true });
}

function runSql() {
  var status = document.getElementById("sc-sql-status");
  var sql = document.getElementById("sc-sql-input").value;
  status.textContent = duck.conn ? "Running…" : "Loading DuckDB (several MB, first run only)…";
  return loadScript("plotly", SC.cdn.plotly)
    .then(initDuckDB)
    .then(function () { return duck.conn.query(sql); })
    .then(function (table) {
      var r = arrowToRows(table);
      renderSqlChart(r.cols, r.rows);
      renderSqlTable(r.cols, r.rows);
      status.textContent = r.rows.length + " row" + (r.rows.length === 1 ? "" : "s")
        + " · DuckDB " + "WASM, in-browser";
    })
    .catch(function (e) {
      status.textContent = "SQL error: " + (e && e.message ? e.message : e);
    });
}

// ── architecture (stencil SVG, drawio-editable) ────────────────────────────
function mountArchitectures() {
  document.getElementById("sc-archs").innerHTML = SC.architectures.map(function (a, i) {
    return '<div class="sc-archwrap" style="margin-top:2rem">'
      + "<h3>" + a.title + "</h3>"
      + '<p style="font-size:.9rem;margin:.2rem 0 .8rem">' + a.caption + "</p>"
      + '<div class="sc-panel">' + a.svg + "</div>"
      + '<div class="sc-actions">'
      + '<button class="sc-mini" data-arch="' + i + '" data-kind="svg">Download editable SVG</button>'
      + '<button class="sc-mini" data-arch="' + i + '" data-kind="drawio">Download .drawio</button>'
      + '<span class="hint">Opens in diagrams.net as real AWS & GCP shapes.</span>'
      + "</div></div>";
  }).join("");

  document.querySelectorAll("[data-arch]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var a = SC.architectures[Number(btn.dataset.arch)];
      var wrap = document.createElement("div");
      wrap.innerHTML = a.svg;
      var svg = wrap.querySelector("svg");
      var name = a.title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      var blob, file;
      if (btn.dataset.kind === "drawio") {
        // The mxfile source rides in the SVG's `content` attribute — pull it back out.
        blob = new Blob([svg.getAttribute("content")], { type: "application/xml" });
        file = name + ".drawio";
      } else {
        blob = new Blob([svg.outerHTML], { type: "image/svg+xml" });
        file = name + ".svg";
      }
      var url = URL.createObjectURL(blob);
      var a2 = document.createElement("a");
      a2.href = url; a2.download = file; a2.click();
      URL.revokeObjectURL(url);
    });
  });
}

// ── boot / re-render ───────────────────────────────────────────────────────
function labelFor(t, key) {
  var v = (t.fonts[key] || "").split(",")[0].replace(/['"]/g, "");
  return key.toUpperCase() + " · " + (v || "—");
}

function render() {
  var b = brand(), t = b.tokens;
  document.getElementById("sc-hero").textContent = b.name;
  document.getElementById("sc-title").textContent =
    SC_SINGLE ? b.name + " — theme showcase" : "Theme showcase";
  document.getElementById("sc-footer").textContent =
    b.name + " · " + (t.fonts.display || t.fonts.body).split(",")[0].replace(/['"]/g, "")
    + " + " + t.fonts.body.split(",")[0].replace(/['"]/g, "")
    + " · build " + SC.buildId;

  var disp = labelFor(t, "display");
  document.getElementById("sc-lbl-display").textContent = disp + " · 40px";
  document.getElementById("sc-lbl-display-sm").textContent = disp + " · 24px";
  document.getElementById("sc-lbl-body").textContent = labelFor(t, "body");
  document.getElementById("sc-lbl-mono").textContent = labelFor(t, "mono");

  paintSwatches();
  paintDiverging();
  paintStatus();
  drawCharts();
  drawGraph();
  drawMermaid();
  drawDeck();
}

function setBrand(name) {
  document.documentElement.setAttribute("data-brand", name);
  document.querySelectorAll("#sc-brands button").forEach(function (x) {
    x.setAttribute("aria-pressed", String(x.dataset.brand === name));
  });
  // A brand may be light-native or dark-native; honour its own default.
  var b = BRANDS.find(function (x) { return x.name === name; });
  var def = b && b.tokens.defaultTheme;
  if (def === "light" || def === "dark") setMode(def, true);
  render();
}

function setMode(m, quiet) {
  document.documentElement.setAttribute("data-theme", m);
  document.querySelectorAll("#sc-modes button").forEach(function (x) {
    x.setAttribute("aria-pressed", String(x.dataset.mode === m));
  });
  if (!quiet) render();
}

// brand switcher only exists in a gallery — a single-brand artifact has no other brand
var bar = document.getElementById("sc-brands");
if (SC_SINGLE) {
  bar.remove();
} else {
  bar.innerHTML = BRANDS.map(function (b) {
    return '<button data-brand="' + b.name + '">' + b.name + "</button>";
  }).join("");
  bar.querySelectorAll("button").forEach(function (btn) {
    btn.addEventListener("click", function () { setBrand(btn.dataset.brand); });
  });
}
document.querySelectorAll("#sc-modes button").forEach(function (btn) {
  btn.addEventListener("click", function () { setMode(btn.dataset.mode); });
});

// Embedding colour toggle: recolour the SAME points by topic or by EVoC cluster.
// Only the point cloud re-renders — no need to rebuild every chart on the page.
document.querySelectorAll("[data-emb-colour]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    embState.colour = btn.dataset.embColour;
    renderEmb();
  });
});

// In-browser SQL: seed the editor, run on click. DuckDB loads lazily on first run.
var sqlInput = document.getElementById("sc-sql-input");
if (sqlInput) {
  sqlInput.value = DEFAULT_SQL;
  document.getElementById("sc-sql-run").addEventListener("click", runSql);
}

mountArchitectures();
setBrand(BRANDS[0].name);

