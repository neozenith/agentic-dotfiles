"use strict";
// Cytoscape graph rendering for the richdocs viewer.
//
// Inlined into its own script element BEFORE viewer.js, so these functions are
// hoisted into global scope by the time viewer.js boots. Placeholder-free by
// contract (ADR-008) — every colour comes from TOKENS.canvas.cytoscape.
//
// (Deliberately no literal script tags in this comment: a test balances the
// opening/closing tag counts in the assembled page to catch payloads that could
// break out of their script element.)
//
// Token schema (all optional except the five legacy keys, which older brandpacks
// already ship). Missing values fall back to something sane derived from the
// theme, so an old pack keeps working:
//
//   canvas.cytoscape.<light|dark> = {
//     nodeFill, nodeLabel, edge, compoundBg, compoundBorder,   // legacy, required
//     nodeBorder?, nodeFillAlt?, edgeLabel?, edgeLabelBg?,     // refinements
//     selected?, shape?, roundness?
//   }

// Cytoscape cannot read CSS custom properties — it paints to a canvas. That is
// the whole reason design-tokens.json carries a second, JS-side palette (ADR-004).
function rdCyPalette(tokens, theme) {
  var c = tokens.canvas.cytoscape[theme] || {};
  var dark = theme === "dark";
  return {
    nodeFill: c.nodeFill,
    nodeBorder: c.nodeBorder || c.nodeFill,
    nodeLabel: c.nodeLabel,
    nodeFillAlt: c.nodeFillAlt || c.compoundBg,
    edge: c.edge,
    edgeLabel: c.edgeLabel || c.nodeLabel,
    edgeLabelBg: c.edgeLabelBg || (dark ? "#000000" : "#ffffff"),
    compoundBg: c.compoundBg,
    compoundBorder: c.compoundBorder,
    selected: c.selected || c.nodeBorder || c.nodeFill,
    shape: c.shape || "round-rectangle",
    roundness: typeof c.roundness === "number" ? c.roundness : 6,
    font: tokens.fonts.body
  };
}

// Blend two hex colours. Used to turn a saturated CATEGORY colour into a subtle
// theme-appropriate TINT for a compound's fill — so the compound reads as its
// category (hue + border) while its label stays the theme's contrast-safe text
// colour in BOTH light and dark. A raw category fill would fail label contrast in
// one theme or the other; a tint toward the canvas never does.
function rdMix(a, b, t) {
  function ch(h, i) { return parseInt(h.slice(1 + i * 2, 3 + i * 2), 16); }
  function h2(n) { return Math.round(n).toString(16).padStart(2, "0"); }
  return "#" + [0, 1, 2].map(function (i) {
    return h2(ch(a, i) * (1 - t) + ch(b, i) * t);
  }).join("");
}

function rdCyStyle(tokens, theme) {
  var p = rdCyPalette(tokens, theme);
  var cats = tokens.categoryColours || {};
  var bg = (tokens.themes && tokens.themes[theme] && tokens.themes[theme].bg) || (theme === "dark" ? "#111111" : "#ffffff");
  function catTint(cat) { return cats[cat] ? rdMix(cats[cat], bg, 0.84) : p.compoundBg; }
  function catBorder(cat) { return cats[cat] || p.compoundBorder; }
  return [
    // Labels sit INSIDE the node. The old style floated them underneath, which
    // collided with edges and made dense graphs unreadable.
    {
      selector: "node",
      style: {
        "shape": p.shape,
        "background-color": p.nodeFill,
        "border-width": 1,
        "border-color": p.nodeBorder,
        "corner-radius": p.roundness,
        "label": "data(label)",
        "color": p.nodeLabel,
        "font-family": p.font,
        "font-size": "12px",
        "font-weight": 500,
        "text-valign": "center",
        "text-halign": "center",
        "text-wrap": "wrap",
        "text-max-width": "140px",
        "padding": "12px",
        "width": "label",
        "height": "label",
        "transition-property": "background-color, border-color, border-width",
        "transition-duration": "120ms"
      }
    },

    // A node may opt into the secondary fill: `{ data: { variant: "alt" } }`.
    {
      selector: 'node[variant="alt"]',
      style: { "background-color": p.nodeFillAlt, "color": p.nodeLabel }
    },

    // Compound (cluster) nodes: label at the top, dashed edge, no fill weight.
    {
      selector: ":parent",
      style: {
        "shape": "round-rectangle",
        "corner-radius": p.roundness + 2,
        "background-color": p.compoundBg,
        "background-opacity": 0.55,
        "border-width": 1,
        "border-style": "dashed",
        "border-color": p.compoundBorder,
        "label": "data(label)",
        "color": p.nodeLabel,
        "font-size": "11px",
        "font-weight": 600,
        "text-valign": "top",
        "text-halign": "center",
        "text-margin-y": -6,
        "padding": "18px"
      }
    },

    // A compound may carry `data(category)`: it is then tinted by that category's
    // hue with a saturated matching border, while its label keeps the theme's
    // contrast-safe text colour. Different categories → different hues, every label
    // readable in both themes.
    {
      selector: ":parent[category]",
      style: {
        "background-color": function (e) { return catTint(e.data("category")); },
        "background-opacity": 1,
        "border-width": 2,
        "border-style": "solid",
        "border-color": function (e) { return catBorder(e.data("category")); },
        "color": p.nodeLabel
      }
    },

    {
      selector: "edge",
      style: {
        "curve-style": "bezier",
        "line-color": p.edge,
        "width": 1.25,
        "opacity": 0.75,
        "target-arrow-color": p.edge,
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.85,
        // Edge labels get an opaque plate so they stay legible over the graph.
        "label": "data(label)",
        "color": p.edgeLabel,
        "font-family": p.font,
        "font-size": "10px",
        "text-background-color": p.edgeLabelBg,
        "text-background-opacity": 1,
        "text-background-padding": "3px",
        "text-background-shape": "roundrectangle",
        "text-rotation": "autorotate",
        "transition-property": "line-color, width, opacity",
        "transition-duration": "120ms"
      }
    },

    { selector: 'edge[style="dashed"]', style: { "line-style": "dashed" } },

    // Hover: light up the node and the edges it touches, dim nothing else —
    // dimming the rest is a lie when the graph is bigger than the viewport.
    {
      selector: "node:active, node.rd-hover",
      style: { "border-width": 2, "border-color": p.selected }
    },
    {
      selector: "edge.rd-hover",
      style: { "line-color": p.selected, "target-arrow-color": p.selected, "width": 2, "opacity": 1 }
    }
  ];
}

function rdCyLayout(payload) {
  var layout = Object.assign(
    { name: "dagre", rankDir: "LR", nodeSep: 28, rankSep: 56, edgeSep: 12, padding: 16 },
    payload.layout || {}
  );
  if (layout.name === "dagre" && !layout.rankDir) layout.rankDir = "LR";
  return layout;
}

function rdRenderCytoscape(block, tokens, theme) {
  var payload = block.payload;
  var el = block.el;
  el.style.height = (payload.height || 420) + "px";

  if (block.cy) block.cy.destroy();

  block.cy = window.cytoscape({
    container: el,
    elements: payload.elements,
    layout: rdCyLayout(payload),
    style: rdCyStyle(tokens, theme),
    // A doc is for reading, not for fighting a viewport. Zoom is available, but
    // the graph must never be *dragged away* by an accidental scroll.
    autoungrabify: false,
    userZoomingEnabled: false,
    boxSelectionEnabled: false
  });

  block.cy.on("mouseover", "node", function (e) {
    e.target.addClass("rd-hover");
    e.target.connectedEdges().addClass("rd-hover");
  });
  block.cy.on("mouseout", "node", function (e) {
    e.target.removeClass("rd-hover");
    e.target.connectedEdges().removeClass("rd-hover");
  });

  block.cy.fit(undefined, 20);
  return block.cy;
}
