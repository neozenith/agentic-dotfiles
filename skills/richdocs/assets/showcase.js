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
// Every swatch names its colour twice: the sRGB hex it renders as, and its OKLCH
// coordinates, the space the token pipeline reasons in.
function oklchText(hex) {
  var c = rdRgbToOklch(rdHexToRgb(hex));
  return "oklch " + c.L.toFixed(3) + " " + c.C.toFixed(3) + " " + (c.C < 0.0005 ? 0 : c.H).toFixed(1);
}

function swatch(hex, label) {
  var dark = (function () {
    var r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 150;
  })();
  return '<div class="sc-sw" style="background:' + hex + ';color:' + (dark ? "#fff" : "#000") + '">'
    + (label ? "<b>" + label + "</b>" : "") + "<span>" + hex + "</span><span>" + oklchText(hex) + "</span></div>";
}

function paintSwatches() {
  var b = brand(), m = mode(), t = b.tokens;
  var th = t.themes[m];
  document.getElementById("sc-theme-ramp").innerHTML =
    ["bg", "surface", "border", "muted", "fg", "accent"].map(function (k) {
      return swatch(th[k], k);
    }).join("");

  var series = t.canvas.plotly[m].series || [];
  document.getElementById("sc-series-ramp").innerHTML =
    series.map(function (c, i) { return swatch(c, String(i + 1)); }).join("");

  var plot = t.canvas.plotly[m];
  var muted = plot.muted || [];
  document.getElementById("sc-muted-ramp").innerHTML =
    muted.map(function (c, i) { return swatch(c, "grey " + (i + 1)); }).join("");

  var seq = plot.sequential || [];
  document.getElementById("sc-seq-ramp").innerHTML =
    seq.map(function (c, i) {
      return swatch(c, i === 0 ? "low" : i === seq.length - 1 ? "high" : "");
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
          return swatch(c, lab);
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

// Three more diagram families, each semi-complex, on the token pipeline itself so the
// content is real: the profile store's entities, one live-tuning round trip, and the plan.
var MERMAID_ER = [
  "erDiagram",
  "  PROFILE ||--o| SEED : \"starts from\"",
  "  PROFILE ||--|| IR : \"curates\"",
  "  PROFILE ||--|{ DTCG_TOKEN : \"builds\"",
  "  SEED ||--|{ PARAMETER : \"states\"",
  "  IR ||--|{ ROLE : \"holds\"",
  "  PARAMETER }o--o{ ROLE : \"feeds\"",
  "  ROLE ||--o{ ROLE : \"derives\"",
  "  ROLE ||--|{ DTCG_TOKEN : \"serialises to\"",
  "  DTCG_TOKEN }|--|{ SURFACE : \"paints\"",
  "  PROFILE {",
  "    string name PK",
  "    string scope \"project or user\"",
  "    date curated_at",
  "  }",
  "  SEED {",
  "    string profile FK",
  "    float brand_hue",
  "    float brand_lightness",
  "  }",
  "  PARAMETER {",
  "    string key PK",
  "    string value",
  "    string provenance \"stated or default\"",
  "  }",
  "  ROLE {",
  "    string name PK",
  "    string light_hex",
  "    string dark_hex",
  "    string rule",
  "  }",
  "  DTCG_TOKEN {",
  "    string path PK",
  "    string colour_space",
  "    string mode",
  "  }",
  "  SURFACE {",
  "    string name PK",
  "    string renderer \"plotly, cytoscape, mermaid\"",
  "  }"
].join("\n");

var MERMAID_SEQUENCE = [
  "sequenceDiagram",
  "  autonumber",
  "  actor U as Maintainer",
  "  participant S as Showcase",
  "  participant P as Pyodide",
  "  participant G as generator.py",
  "  participant R as Renderers",
  "  U->>S: Drag L-light-bg to 0.97",
  "  S->>S: Debounce 250 ms",
  "  alt Python not loaded yet",
  "    S->>P: loadPyodide()",
  "    activate P",
  "    P-->>S: Runtime ready (about 5 s)",
  "    deactivate P",
  "  end",
  "  S->>P: generate(seed)",
  "  activate P",
  "  P->>G: Curator(seed).run()",
  "  activate G",
  "  loop Every role, both modes",
  "    G->>G: Solve lightness to contrast target",
  "  end",
  "  G-->>P: tokens, lineage, resolved",
  "  deactivate G",
  "  P-->>S: JSON",
  "  deactivate P",
  "  Note over S,R: A newer change supersedes this run",
  "  par Redraw",
  "    S->>R: Plotly and Sankey",
  "  and",
  "    S->>R: Cytoscape and Mermaid",
  "  and",
  "    S->>R: deck.gl scenes",
  "  end",
  "  S-->>U: Regenerated in 101 ms"
].join("\n");

var MERMAID_GANTT = [
  "gantt",
  "  title Design-token refactor",
  "  dateFormat YYYY-MM-DD",
  "  axisFormat %d %b",
  "  todayMarker off",
  "  section Requirements",
  "    Structure and location      :done, req1, 2026-09-01, 5d",
  "    Override boundary           :done, req2, after req1, 3d",
  "    Curation defaults           :active, req3, after req2, 12d",
  "  section Prototype",
  "    Seed to DTCG spike          :done, pro1, 2026-09-14, 2d",
  "    Lineage Sankeys             :done, pro2, 2026-09-23, 1d",
  "    Live seed tuning            :active, pro3, after pro2, 2d",
  "  section Decisions",
  "    DT-PROV-1 provenance        :crit, dec1, after pro3, 4d",
  "    Status and surfaces         :dec2, after dec1, 5d",
  "  section Migration",
  "    Rename richdocs tokens      :mig1, after dec2, 4d",
  "    Rename mermaid tokens       :mig2, after dec2, 4d",
  "    Retire legacy keys          :milestone, mig3, after mig1, 0d"
].join("\n");

// Blend two hex colours; t = weight of `a`. Mermaid needs literal colours, not color-mix().
function mixHex(a, b, t) {
  var x = hexRgb(a), y = hexRgb(b);
  return "#" + [0, 1, 2].map(function (i) {
    return Math.round(x[i] * t + y[i] * (1 - t)).toString(16).padStart(2, "0");
  }).join("");
}

function drawMermaid() {
  var b = brand(), m = mode(), t = b.tokens, th = t.themes[m];
  var on = th.onAccent || th.bg;
  var tint = mixHex(th.accent, th.bg, 0.22);          // text-safe: near the ground, fg on top
  var crit = (t.status && t.status[m] && t.status[m].colours.critical) || th.accent;
  window.mermaid.initialize({
    startOnLoad: false, theme: "base", securityLevel: "loose",
    gantt: { leftPadding: 120, barHeight: 22, barGap: 6, fontSize: 12, sectionFontSize: 12 },
    sequence: { mirrorActors: false, showSequenceNumbers: true },
    // Mermaid 11.4.1 paints a critical bar's label with taskTextColor (the on-fill colour)
    // even though the bar is a tint; on a dark ground that is dark-on-dark. Pin it to fg.
    themeCSS: ".critText0,.critText1,.critText2,.critText3{fill:" + th.fg + " !important}",
    themeVariables: {
      fontFamily: t.fonts.body, fontSize: "13px",
      background: th.bg, primaryColor: th.surface, primaryTextColor: th.fg,
      primaryBorderColor: th.accent, lineColor: th.muted, textColor: th.fg,
      mainBkg: th.surface, nodeBorder: th.accent,
      edgeLabelBackground: th.bg, tertiaryColor: th.surface,
      clusterBkg: th.surface, clusterBorder: th.border,
      // erDiagram: alternate attribute rows on the two grounds.
      attributeBackgroundColorOdd: th.surface, attributeBackgroundColorEven: th.bg,
      // sequenceDiagram: actors are surfaces; notes and activations are accent tints.
      actorBkg: th.surface, actorBorder: th.accent, actorTextColor: th.fg, actorLineColor: th.muted,
      signalColor: th.fg, signalTextColor: th.fg,
      labelBoxBkgColor: th.surface, labelBoxBorderColor: th.border, labelTextColor: th.fg,
      loopTextColor: th.fg, noteBkgColor: tint, noteBorderColor: th.accent, noteTextColor: th.fg,
      activationBkgColor: tint, activationBorderColor: th.accent, sequenceNumberColor: th.bg,
      // gantt: planned bars are the fill with on-fill text; active, done and critical bars
      // are tints carrying fg text, so every label clears contrast on its own bar.
      taskBkgColor: th.accent, taskBorderColor: th.accent, taskTextColor: on,
      taskTextOutsideColor: th.fg, taskTextLightColor: on, taskTextDarkColor: th.fg,
      activeTaskBkgColor: tint, activeTaskBorderColor: th.accent,
      doneTaskBkgColor: th.surface, doneTaskBorderColor: th.muted,
      critBkgColor: mixHex(crit, th.bg, 0.22), critBorderColor: crit,
      sectionBkgColor: th.surface, altSectionBkgColor: th.bg, sectionBkgColor2: th.surface,
      gridColor: th.border, titleColor: th.fg
    }
  });
  // Rendered mermaid SVG is not re-themable in place — always re-render every diagram.
  var jobs = [["sc-mermaid", MERMAID_OVERVIEW, "ov"], ["sc-mermaid-detail", MERMAID_DETAIL, "de"],
    ["sc-mermaid-er", MERMAID_ER, "er"], ["sc-mermaid-seq", MERMAID_SEQUENCE, "sq"],
    ["sc-mermaid-gantt", MERMAID_GANTT, "gt"]];
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

// ── deck.gl: the brand palette in OKLCH ──────────────────────────────────────
// Every categorical series colour plus the accent, each at its own OKLCH
// coordinates. The gamut rings sit at the palette's own lightnesses, and the
// target circle is the ACCENT's chroma: a spoke marks every series colour that
// falls short of the brand's intensity (ADR-014: clipping is ceiling < target,
// never inferable from the hex alone, so the target must be stated).
var oklchBlock = { el: null, payload: null };

function oklchPayload(t, m) {
  var th = t.themes[m];
  var plot = (t.canvas && t.canvas.plotly && t.canvas.plotly[m]) || {};
  var seen = {}, data = [];
  function add(hex, label) {
    if (!hex) return;
    var key = String(hex).toLowerCase();
    if (seen[key]) return;
    seen[key] = true;
    data.push({ hex: hex, label: label });
  }
  add(th.accent, "accent");
  (plot.series || []).forEach(function (h, i) { add(h, "series " + (i + 1)); });
  (plot.seriesAlt || []).forEach(function (h, i) { add(h, "series alt " + (i + 1)); });

  var accent = rdRgbToOklch(rdHexToRgb(th.accent));
  var series = data.slice(1).map(function (d) { return rdRgbToOklch(rdHexToRgb(d.hex)); });
  var ls = [accent.L].concat(series.map(function (c) { return c.L; }));
  var lo = Math.min.apply(null, ls), hi = Math.max.apply(null, ls);
  var rings = [lo, accent.L, hi]
    .map(function (x) { return Math.round(x * 100) / 100; })
    .filter(function (x, i, a) { return a.indexOf(x) === i; })
    .sort(function (a, b) { return a - b; });
  var target = Math.round(accent.C * 1000) / 1000;
  var short = series.filter(function (c) { return c.C < accent.C - 0.005; }).length;

  return {
    payload: {
      view: "orbit", space: "oklch", height: 480, gamut: rings, targetChroma: target,
      layers: [{ type: "PointCloudLayer", id: "oklch-palette", pointSize: 13, data: data }]
    },
    readout: series.length + " series colours · accent L " + accent.L.toFixed(2)
      + " C " + accent.C.toFixed(3) + " H " + accent.H.toFixed(0) + "° · "
      + short + " of " + series.length + " below the accent's chroma"
  };
}

function renderOklch() {
  if (typeof deck === "undefined") return;
  oklchBlock.el = document.getElementById("sc-oklch");
  if (!oklchBlock.el) return;
  var t = brand().tokens, m = mode();
  var built = oklchPayload(t, m);
  oklchBlock.payload = built.payload;
  try { rdRenderDeckGL(oklchBlock, t, m); } catch (e) { oklchBlock.el.textContent = "deckgl error: " + e.message; }
  var readout = document.getElementById("sc-oklch-readout");
  if (readout) readout.textContent = built.readout;
}

function drawDeck() {
  return loadScript("deckgl", SC.cdn.deckgl).then(function () {
    renderOklch();
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

// ── lineage (Sankey) ───────────────────────────────────────────────────────
// Optional per brand: a generated theme ships lineage.json, a hand-authored one does not
// (ADR-021). Nodes carry their own colour per mode; each link takes its source's colour,
// translucent, so a band reads as "this value flowed from there".
function hexA(hex, a) {
  var h = hex.replace("#", "");
  return "rgba(" + parseInt(h.slice(0, 2), 16) + "," + parseInt(h.slice(2, 4), 16) + ","
    + parseInt(h.slice(4, 6), 16) + "," + a + ")";
}

// WCAG relative luminance contrast, so a band whose source matches the ground (a surface
// role on its own surface) is drawn in the text colour instead of vanishing.
function lumOf(hex) {
  var c = [1, 3, 5].map(function (i) {
    var v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function contrastOf(a, b) {
  var x = lumOf(a), y = lumOf(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

function lineageHeight(s) {
  // Size to the busiest column, so labels never overprint. Columns are inferred the way
  // Plotly lays them out: a node's depth is the longest path that reaches it.
  var depth = {};
  s.nodes.forEach(function (n) { depth[n.id] = 0; });
  for (var pass = 0; pass < s.nodes.length; pass++) {
    var moved = false;
    s.links.forEach(function (l) {
      if (depth[l.target] < depth[l.source] + 1) { depth[l.target] = depth[l.source] + 1; moved = true; }
    });
    if (!moved) break;
  }
  var per = {};
  Object.keys(depth).forEach(function (k) { per[depth[k]] = (per[depth[k]] || 0) + 1; });
  var busiest = Math.max.apply(null, Object.keys(per).map(function (k) { return per[k]; }));
  return Math.max(360, busiest * 17 + 60);
}

function drawLineage() {
  var host = document.getElementById("sc-lineage");
  var none = document.getElementById("sc-lineage-none");
  var lin = brand().lineage;
  if (!lin || !lin.sankeys || !lin.sankeys.length) {
    host.innerHTML = ""; none.hidden = false;
    buildNav();
    return Promise.resolve();
  }
  none.hidden = true;
  host.innerHTML = lin.sankeys.map(function (s, i) {
    return '<h3 id="sc-lineage-' + i + '">' + escapeHtml(s.title) + "</h3>"
      + '<p class="sc-lineage-caption">' + escapeHtml(s.caption || "").replace(/`([^`]+)`/g, "<code>$1</code>") + "</p>"
      + '<div class="sc-panel"><div id="sc-sankey-' + i + '" style="height:' + lineageHeight(s) + 'px"></div></div>';
  }).join("");
  buildNav();   // the lineage headings are per brand, so the nav follows them
  return loadScript("plotly", SC.cdn.plotly).then(function () {
    var t = brand().tokens, m = mode(), p = t.canvas.plotly[m];
    lin.sankeys.forEach(function (s, i) {
      var idx = {};
      s.nodes.forEach(function (n, k) { idx[n.id] = k; });
      var colour = function (n) { return (n.colour && n.colour[m]) || p.font; };
      Plotly.react("sc-sankey-" + i, [{
        type: "sankey", arrangement: "snap",
        node: {
          label: s.nodes.map(function (n) { return n.label; }),
          customdata: s.nodes.map(function (n) { return n.group || ""; }),
          hovertemplate: "%{label}<br>%{customdata}<extra></extra>",
          color: s.nodes.map(colour),
          line: { color: p.grid, width: 0.5 },
          pad: 6, thickness: 14
        },
        link: {
          source: s.links.map(function (l) { return idx[l.source]; }),
          target: s.links.map(function (l) { return idx[l.target]; }),
          value: s.links.map(function (l) { return l.value || 1; }),
          color: s.links.map(function (l) {
            var c = colour(s.nodes[idx[l.source]]);
            return contrastOf(c, p.paper) < 1.6 ? hexA(p.font, 0.2) : hexA(c, 0.35);
          }),
          hovertemplate: "%{source.label} → %{target.label}<extra></extra>"
        }
      }], {
        paper_bgcolor: p.paper, plot_bgcolor: p.plot,
        font: { family: t.fonts.mono, color: p.font, size: 10.5 },
        margin: { l: 8, r: 8, t: 8, b: 8 }
      }, { displayModeBar: false, responsive: true });
    });
  });
}

// ── section navigation ─────────────────────────────────────────────────────
// Built from the page's own headings, so a new section appears here without a second
// list to maintain. Open/closed is a per-viewer convenience, remembered when storage
// is available and harmless when it is not.
var NAV_KEY = "richdocs-showcase-nav";
var navSpy = null;

function slug(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }

function buildNav() {
  var items = [];
  document.querySelectorAll(".wrap > section").forEach(function (sec, i) {
    var eyebrow = sec.querySelector(".sc-eyebrow");
    var label = eyebrow ? eyebrow.textContent.trim() : (sec.querySelector("h2") || {}).textContent || "Section " + (i + 1);
    if (!sec.id) sec.id = "sc-s-" + slug(label);
    var subs = [];
    sec.querySelectorAll("h3").forEach(function (h) {
      if (!h.id) h.id = sec.id + "-" + slug(h.textContent);
      subs.push('<li class="sc-nav-sub"><a href="#' + h.id + '">' + escapeHtml(h.textContent.trim()) + "</a></li>");
    });
    items.push('<li class="sc-nav-top"><a href="#' + sec.id + '">' + escapeHtml(label) + "</a>"
      + (subs.length ? "<ol>" + subs.join("") + "</ol>" : "") + "</li>");
  });
  document.getElementById("sc-nav").innerHTML = "<ol>" + items.join("") + "</ol>";
  spyNav();
}

function spyNav() {
  if (navSpy) navSpy.disconnect();
  if (!("IntersectionObserver" in window)) return;
  var links = {};
  document.querySelectorAll("#sc-nav a").forEach(function (a) { links[a.getAttribute("href").slice(1)] = a; });
  navSpy = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting || !links[e.target.id]) return;
      var sec = e.target.closest("section");
      Object.keys(links).forEach(function (k) { links[k].removeAttribute("aria-current"); });
      links[e.target.id].setAttribute("aria-current", "true");
      if (sec && links[sec.id]) links[sec.id].setAttribute("aria-current", "true");
    });
  }, { rootMargin: "-15% 0px -75% 0px" });
  document.querySelectorAll(".wrap > section, .wrap > section h3").forEach(function (el) {
    if (el.id) navSpy.observe(el);
  });
}

function setNav(open, remember) {
  document.documentElement.classList.toggle("sc-nav-open", open);
  document.getElementById("sc-nav-toggle").setAttribute("aria-expanded", String(open));
  if (remember) { try { localStorage.setItem(NAV_KEY, open ? "open" : "closed"); } catch (e) { /* storage blocked */ } }
}

function initNav() {
  var saved = null;
  try { saved = localStorage.getItem(NAV_KEY); } catch (e) { /* storage blocked */ }
  var narrow = window.matchMedia("(max-width: 1099px)");
  setNav(saved ? saved === "open" : !narrow.matches, false);
  document.getElementById("sc-nav-toggle").addEventListener("click", function () {
    setNav(!document.documentElement.classList.contains("sc-nav-open"), true);
  });
  // On a narrow screen the nav overlays the page, so following a link closes it.
  document.getElementById("sc-nav").addEventListener("click", function (e) {
    if (e.target.closest("a") && narrow.matches) setNav(false, false);
  });
  var bar = document.querySelector(".sc-bar");
  var sizeBar = function () {
    document.documentElement.style.setProperty("--sc-bar-h", bar.offsetHeight + "px");
  };
  sizeBar();
  window.addEventListener("resize", sizeBar);
  buildNav();
}

// ── live seed tuning (Pyodide) ─────────────────────────────────────────────
// A generated theme may ship its own producer (ADR-022): generator.json names the seed and
// a range per parameter, generator.py is the stdlib module that turns a seed into this
// brandpack. Changing a control runs THAT module in the browser, so the page and the CLI
// share one curation and nothing here re-implements it.
var py = { ready: null };
var tune = { timer: null, seq: 0 };

function initPy() {
  if (py.ready) return py.ready;
  py.ready = loadScript("pyodide", SC.cdn.pyodide).then(function () {
    return loadPyodide({ indexURL: SC.cdn.pyodide.replace(/[^/]*$/, "") });
  }).then(function (p) {
    p.runPython("import sys\nif '/home/pyodide' not in sys.path: sys.path.insert(0, '/home/pyodide')");
    py.p = p;
    return p;
  });
  py.ready.catch(function () { py.ready = null; });   // a failed load may be retried
  return py.ready;
}

function runGenerator(b) {
  var g = b.generator;
  return initPy().then(function (p) {
    var mod = "rd_gen_" + b.name.replace(/[^A-Za-z0-9_]/g, "_");
    if (!g.written) { p.FS.writeFile("/home/pyodide/" + mod + ".py", g.source); g.written = true; }
    p.globals.set("_rd_seed", JSON.stringify(b.seedLive));
    return JSON.parse(p.runPython("import json\nimport " + mod + " as _rd_m\n"
      + "json.dumps(_rd_m." + g.manifest.entry + "(json.loads(_rd_seed)))"));
  });
}

function tuneStatus(text, err) {
  var el = document.getElementById("sc-tune-status");
  el.textContent = text;
  el.classList.toggle("err", !!err);
}

function paramValue(b, prm) {
  return Object.prototype.hasOwnProperty.call(b.seedLive, prm.key) ? b.seedLive[prm.key] : prm.default;
}

function keywordLabel(k) { return k === null ? "auto" : String(k); }

// What a keyword (cusp, brand, auto) resolved to on the last run, as the generator reports it.
function resolvedOf(b, key) {
  var r = (b.resolved || {})[key];
  if (r === undefined || r === null) return null;
  return typeof r === "number" ? { light: r, dark: r } : r;
}
function resolvedText(b, key) {
  var r = resolvedOf(b, key);
  if (!r) return "";
  var f = function (x) { return Math.round(x * 1000) / 1000; };
  return "resolves to " + (r.light === r.dark ? f(r.light) : "light " + f(r.light) + " · dark " + f(r.dark));
}

// After a run, show keyword-mode rows at the value the keyword resolved to. Only the
// disabled inputs change, so a slider being dragged elsewhere keeps its focus.
function refreshResolved(b) {
  document.querySelectorAll(".sc-tune-row").forEach(function (row) {
    var key = row.dataset.key, r = resolvedOf(b, key);
    var out = row.querySelector(".sc-tune-resolved");
    if (out) out.textContent = resolvedText(b, key);
    if (!r) return;
    row.querySelectorAll('[data-role="range"]:disabled, [data-role="num"]:disabled').forEach(function (el) {
      el.value = r.light;
    });
  });
}

function setParam(b, prm, value) {
  // A value equal to the default is not stated: the seed stays minimal (brand.hue always stays).
  if (value === prm.default && prm.key !== "brand.hue") delete b.seedLive[prm.key];
  else b.seedLive[prm.key] = value;
  document.getElementById("sc-tune-seed").textContent = JSON.stringify(b.seedLive, null, 2);
  var row = document.querySelector('.sc-tune-row[data-key="' + prm.key + '"]');
  if (row) {
    var stated = Object.prototype.hasOwnProperty.call(b.seedLive, prm.key);
    row.classList.toggle("stated", stated);
    row.querySelector(".sc-tune-badge").textContent = stated ? "stated" : "default";
  }
  clearTimeout(tune.timer);
  tune.timer = setTimeout(function () { regenerate(b); }, 250);
}

function regenerate(b) {
  var seq = ++tune.seq, t0 = performance.now();
  tuneStatus(py.p ? "Curating…" : "Loading Python (once), then curating…");
  return runGenerator(b).then(function (out) {
    if (seq !== tune.seq) return;          // a newer change superseded this one
    b.tokens = out.tokens;
    b.lineage = out.lineage || null;
    b.resolved = out.resolved || {};
    refreshResolved(b);
    applyTokens(b);
    if (brand() === b) render();
    tuneStatus("Regenerated in " + Math.round(performance.now() - t0) + " ms. Stated values are marked.");
  }).catch(function (e) {
    if (seq !== tune.seq) return;
    var msg = String(e && e.message || e).trim().split("\n").filter(Boolean).pop();
    tuneStatus("Generator stopped: " + msg + ". The page still shows the last good theme.", true);
  });
}

function controlHtml(b, prm) {
  var v = paramValue(b, prm);
  var kws = prm.keywords || [];
  var numeric = typeof prm.min === "number";
  var isKw = kws.some(function (k) { return k === v; });
  var res = resolvedOf(b, prm.key);
  var num = typeof v === "number" ? v : res ? res.light : (numeric ? (prm.min + prm.max) / 2 : 0);
  var id = "sc-tp-" + prm.key.replace(/[^A-Za-z0-9]/g, "-");
  var html = '<div class="sc-tune-ctl">';
  if (kws.length) {
    html += '<select data-role="kw" aria-label="' + escapeHtml(prm.key) + ' mode">'
      + kws.map(function (k, i) {
          return '<option value="' + i + '"' + (isKw && k === v ? " selected" : "") + ">" + keywordLabel(k) + "</option>";
        }).join("")
      + (numeric ? '<option value="num"' + (isKw ? "" : " selected") + ">number</option>" : "")
      + "</select>";
  }
  if (numeric) {
    html += '<input type="range" data-role="range" id="' + id + '" min="' + prm.min + '" max="' + prm.max
      + '" step="' + prm.step + '" value="' + num + '"' + (isKw ? " disabled" : "") + ">"
      + '<input type="number" data-role="num" aria-label="' + escapeHtml(prm.key) + ' value" min="' + prm.min
      + '" max="' + prm.max + '" step="' + prm.step + '" value="' + num + '"' + (isKw ? " disabled" : "") + ">";
  }
  return html + "</div>";
}

// The groups a first look needs; the rest start collapsed.
var TUNE_OPEN = ["brand", "walk"];

function buildTune() {
  var b = brand();
  var host = document.getElementById("sc-tune-controls");
  if (!b.generator) { host.innerHTML = ""; return; }
  var groups = {};
  b.generator.manifest.params.forEach(function (prm) {
    var g = prm.key.split(/[.-]/)[0];
    (groups[g] = groups[g] || []).push(prm);
  });
  host.innerHTML = Object.keys(groups).map(function (g) {
    return "<details" + (TUNE_OPEN.indexOf(g) >= 0 ? " open" : "") + "><summary>" + escapeHtml(g)
      + "</summary>" + groups[g].map(function (prm) {
      var stated = Object.prototype.hasOwnProperty.call(b.seedLive, prm.key);
      var id = "sc-tp-" + prm.key.replace(/[^A-Za-z0-9]/g, "-");
      return '<div class="sc-tune-row' + (stated ? " stated" : "") + '" data-key="' + escapeHtml(prm.key) + '">'
        + '<label for="' + id + '"><span>' + escapeHtml(prm.key) + '</span><span class="sc-tune-badge">'
        + (stated ? "stated" : "default") + "</span></label>"
        + controlHtml(b, prm)
        + '<div class="sc-tune-src">default '
        + escapeHtml(prm.default === null && !prm.keywords ? "required" : keywordLabel(prm.default)) + " · "
        + escapeHtml(prm.source) + '</div><div class="sc-tune-src sc-tune-resolved">'
        + escapeHtml(resolvedText(b, prm.key)) + "</div></div>";
    }).join("") + "</details>";
  }).join("");
  document.getElementById("sc-tune-seed").textContent = JSON.stringify(b.seedLive, null, 2);

  host.querySelectorAll(".sc-tune-row").forEach(function (row) {
    var prm = b.generator.manifest.params.find(function (x) { return x.key === row.dataset.key; });
    var kw = row.querySelector('[data-role="kw"]');
    var range = row.querySelector('[data-role="range"]');
    var num = row.querySelector('[data-role="num"]');
    var fromNumber = function (raw) {
      var x = Number(raw);
      if (!isFinite(x)) return;
      if (range) range.value = x;
      if (num) num.value = x;
      setParam(b, prm, x);
    };
    if (kw) kw.addEventListener("change", function () {
      var isNum = kw.value === "num";
      if (range) { range.disabled = !isNum; num.disabled = !isNum; }
      if (isNum) fromNumber(range.value); else setParam(b, prm, prm.keywords[Number(kw.value)]);
    });
    if (range) range.addEventListener("input", function () { fromNumber(range.value); });
    if (num) num.addEventListener("change", function () { fromNumber(num.value); });
  });
}

function setTune(open) {
  document.documentElement.classList.toggle("sc-tune-open", open);
  document.getElementById("sc-tune-toggle").setAttribute("aria-expanded", String(open));
}

// Called on every brand switch: the panel only exists for a brand that ships a generator.
function syncTune() {
  var b = brand();
  var has = !!b.generator;
  document.getElementById("sc-tune-toggle").hidden = !has;
  if (!has) setTune(false);
  buildTune();
}

function initTune() {
  BRANDS.forEach(function (b) {
    if (!b.generator) return;
    b.seedLive = JSON.parse(JSON.stringify(b.generator.manifest.seed));
    b.resolved = b.generator.manifest.resolved || {};
    b.original = { tokens: b.tokens, lineage: b.lineage, resolved: b.resolved };
  });
  document.getElementById("sc-tune-toggle").addEventListener("click", function () {
    setTune(!document.documentElement.classList.contains("sc-tune-open"));
  });
  document.getElementById("sc-tune-close").addEventListener("click", function () { setTune(false); });
  document.getElementById("sc-tune-reset").addEventListener("click", function () {
    var b = brand();
    if (!b.generator) return;
    tune.seq++;                              // drop any curation still in flight
    b.seedLive = JSON.parse(JSON.stringify(b.generator.manifest.seed));
    b.tokens = b.original.tokens;
    b.lineage = b.original.lineage;
    b.resolved = b.original.resolved;
    applyTokens(b);
    buildTune();
    render();
    tuneStatus("Reset to the shipped seed.");
  });
  document.getElementById("sc-tune-copy").addEventListener("click", function () {
    var text = document.getElementById("sc-tune-seed").textContent;
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () { tuneStatus("seed.json copied."); });
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
  drawLineage();
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
  syncTune();
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
initNav();
initTune();
setBrand(BRANDS[0].name);

