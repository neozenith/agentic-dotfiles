"use strict";
// Deck.GL block renderer — `rdRenderDeckGL(block, tokens, theme)`.
//
// Inlined BEFORE viewer.js so its functions are hoisted (same contract as
// viewer-cytoscape.js). Placeholder-free by ADR-008: this is real, lintable JS.
//
// Two views, one renderer:
//
//   view: "orbit"  — a 3D scatter in a colour space. The block may hand us bare
//                    hex colours; we PROJECT them to positions ourselves.
//   view: "map"    — geographic. Positions are [lng, lat]. By default the brand
//                    canvas IS the basemap (no vendor token). A demo can opt into
//                    real tiles: `basemap` = raster (deck TileLayer), or
//                    `basemapStyle` = a vector GL style (MapLibre owns the map,
//                    deck rides as a MapboxOverlay). Both are free + keyless.
//
// The whole design rests on one idea borrowed from colour-space visualisers: a
// space is *just a projection function* rgb -> [x, y, z], plus a frame that
// describes its shape. Swap the projection and every mark in the scene moves;
// the data never changes. That is why the same block type serves a gamut study
// and a map — "where does this datum live" is the only question a layer asks.

// ── Colour maths (OKLab / OKLCH) ───────────────────────────────────────────
// OKLab is a perceptual space: L is lightness (0 black, 1 white) and the a/b
// plane carries hue+colourfulness. OKLCH is the same space in cylindrical form:
// C (chroma) is the distance from the grey axis, H (hue) the angle around it.
// Design in OKLCH because a categorical palette wants CONSTANT L (equal contrast
// against the canvas) and VARYING H — which is a horizontal ring in this space.

function rdSrgbToLinear(c) {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function rdLinearToSrgb(c) {
  return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}

function rdHexToRgb(hex) {
  var h = String(hex).trim().replace("#", "");
  if (h.length === 3) { h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2]; }
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255
  ];
}

function rdRgbToOklab(rgb) {
  var r = rdSrgbToLinear(rgb[0]), g = rdSrgbToLinear(rgb[1]), b = rdSrgbToLinear(rgb[2]);
  var l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b;
  var m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b;
  var s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b;
  var l_ = Math.cbrt(l), m_ = Math.cbrt(m), s_ = Math.cbrt(s);
  return [
    0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
    1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
    0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
  ];
}

// Inverse: an (L, C, H) triple back to sRGB. `inGamut` is the whole point —
// most of the OKLCH cylinder is NOT representable in sRGB, and a palette that
// asks for an unrepresentable chroma gets silently clipped by the browser.
function rdOklchToRgb(L, C, H) {
  var h = (H * Math.PI) / 180;
  var a = C * Math.cos(h), b = C * Math.sin(h);
  var l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  var m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  var s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  var l = l_ * l_ * l_, m = m_ * m_ * m_, s = s_ * s_ * s_;
  var lr = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
  var lg = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
  var lb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;
  var rgb = [rdLinearToSrgb(lr), rdLinearToSrgb(lg), rdLinearToSrgb(lb)];
  var eps = 0.0001;
  var inGamut = rgb.every(function (v) { return v >= -eps && v <= 1 + eps; });
  return { rgb: rgb.map(function (v) { return Math.min(1, Math.max(0, v)); }), inGamut: inGamut };
}

function rdRgbToOklch(rgb) {
  var lab = rdRgbToOklab(rgb);
  var C = Math.hypot(lab[1], lab[2]);
  var H = (Math.atan2(lab[2], lab[1]) * 180) / Math.PI;
  return { L: lab[0], C: C, H: H < 0 ? H + 360 : H };
}

// The sRGB gamut ceiling at a given (L, H): the largest chroma that still lands
// inside the cube. Binary search — cheap, and exact enough at 24 iterations.
// This is the function that explains a clipped palette: ask for C beyond this
// and you do not get it, you get this.
function rdMaxChroma(L, H) {
  var lo = 0, hi = 0.4;
  for (var i = 0; i < 24; i++) {
    var mid = (lo + hi) / 2;
    if (rdOklchToRgb(L, mid, H).inGamut) { lo = mid; } else { hi = mid; }
  }
  return lo;
}

// ── Projections: a colour space IS a function ──────────────────────────────
// Every space maps a colour into a cube of roughly [-0.5, 0.5] on each axis, so
// one camera framing works for all of them.
var RD_CHROMA_SCALE = 1.35;   // C ~0.37 (the sRGB max) -> 0.5 radius

var RD_SPACES = {
  // The raw cube. Perceptually lumpy — equal steps do not look equal.
  rgb: function (rgb) {
    return [rgb[0] - 0.5, rgb[1] - 0.5, rgb[2] - 0.5];
  },
  // Perceptual, but cartesian: hue is not an axis, so a hue ring is a circle
  // you have to infer.
  oklab: function (rgb) {
    var lab = rdRgbToOklab(rgb);
    return [lab[1] * RD_CHROMA_SCALE, lab[0] - 0.5, lab[2] * RD_CHROMA_SCALE];
  },
  // The designer's view. Height IS lightness, radius IS chroma, angle IS hue —
  // so a well-built categorical palette appears as a FLAT RING, and any swatch
  // that fell short of its chroma target is visibly closer to the centre pole.
  oklch: function (rgb) {
    var c = rdRgbToOklch(rgb);
    var h = (c.H * Math.PI) / 180;
    return [
      Math.cos(h) * c.C * RD_CHROMA_SCALE,
      c.L - 0.5,
      Math.sin(h) * c.C * RD_CHROMA_SCALE
    ];
  }
};

function rdProject(space, hex) {
  return (RD_SPACES[space] || RD_SPACES.oklch)(rdHexToRgb(hex));
}

function rdRgb255(hex, alpha) {
  var c = rdHexToRgb(hex);
  return [
    Math.round(c[0] * 255),
    Math.round(c[1] * 255),
    Math.round(c[2] * 255),
    alpha === undefined ? 255 : alpha
  ];
}

// ── Frame: the guides that make a space legible ────────────────────────────
// A scatter with no frame is a cloud of dots. The frame says "this axis is
// lightness, this ring is the edge of what sRGB can show".
function rdFrameLines(space, gamutLs, ink) {
  var lines = [];
  if (space === "rgb") { return lines; }

  // The achromatic pole: every grey, from black to white.
  lines.push({ source: [0, -0.5, 0], target: [0, 0.5, 0], color: ink });

  // One ring per requested lightness = the sRGB gamut boundary at that L.
  // A palette swatch sitting ON this ring got the chroma it asked for; one
  // sitting inside it did not.
  gamutLs.forEach(function (L) {
    var prev = null;
    for (var deg = 0; deg <= 360; deg += 4) {
      var maxC = space === "oklch" ? rdMaxChroma(L, deg) : rdMaxChroma(L, deg);
      var h = (deg * Math.PI) / 180;
      var pt = [Math.cos(h) * maxC * RD_CHROMA_SCALE, L - 0.5, Math.sin(h) * maxC * RD_CHROMA_SCALE];
      if (prev) { lines.push({ source: prev, target: pt, color: ink }); }
      prev = pt;
    }
  });
  return lines;
}

// `targetChroma` is the chroma the palette ASKED for — a design intent the
// renderer cannot infer, because a hex only records what was actually granted.
// Given it, we can draw the request as a TRUE CIRCLE at that chroma.
//
// The whole story is then one picture: a perfect circle (what you asked for)
// against a lumpy blob (what sRGB can give you). Wherever the circle escapes
// the blob, the request was impossible — and every swatch in that arc is pinned
// to the blob, short of its target.
function rdTargetRing(L, targetC, color) {
  var lines = [];
  var prev = null;
  for (var deg = 0; deg <= 360; deg += 4) {
    var h = (deg * Math.PI) / 180;
    var pt = [Math.cos(h) * targetC * RD_CHROMA_SCALE, L - 0.5, Math.sin(h) * targetC * RD_CHROMA_SCALE];
    if (prev) { lines.push({ source: prev, target: pt, color: color }); }
    prev = pt;
  }
  return lines;
}

// The clipping tell: for each swatch, a spoke from where it LANDED out to where
// it was AIMED. Drawn only when the ceiling at that hue is below the target —
// i.e. only when the colour was actually denied. A swatch with chroma to spare
// gets no spoke: it is not clipped, it is simply not maximal.
function rdClipSpokes(data, targetC, warn) {
  var spokes = [];
  data.forEach(function (d) {
    if (!d.hex) { return; }
    var c = rdRgbToOklch(rdHexToRgb(d.hex));
    var maxC = rdMaxChroma(c.L, c.H);
    if (maxC >= targetC - 0.004) { return; }   // reachable — nothing was denied
    var h = (c.H * Math.PI) / 180;
    spokes.push({
      source: [Math.cos(h) * c.C * RD_CHROMA_SCALE, c.L - 0.5, Math.sin(h) * c.C * RD_CHROMA_SCALE],
      target: [Math.cos(h) * targetC * RD_CHROMA_SCALE, c.L - 0.5, Math.sin(h) * targetC * RD_CHROMA_SCALE],
      color: warn
    });
  });
  return spokes;
}

// ── Render ─────────────────────────────────────────────────────────────────
// Canvas renderers cannot read CSS custom properties (ADR-004), so the palette
// arrives as tokens. `canvas.deckgl.<mode>` is optional and falls back to the
// plotly sub-palette, which every brandpack already ships.
function rdDeckPalette(tokens, theme) {
  var canvas = tokens.canvas || {};
  var dg = (canvas.deckgl || {})[theme];
  var pl = (canvas.plotly || {})[theme] || {};
  var th = (tokens.themes || {})[theme] || {};
  var status = ((tokens.status || {})[theme] || {}).colours || {};
  return {
    background: (dg && dg.background) || pl.plot || "#101010",
    // The frame is a GUIDE, so it takes the muted-text token — not the plotly
    // `grid` colour, which is tuned to sit behind a 2D chart and vanishes
    // against a 3D scene's own background.
    ink: (dg && dg.ink) || th.muted || pl.grid || "#858585",
    text: (dg && dg.text) || pl.font || th.fg || "#dddddd",
    // Clipping is a warning, and the brand already owns a warning colour.
    warn: (dg && dg.warn) || status.warning || "#ebb25f",
    series: pl.series || []
  };
}

// A layer spec is `{ type, data, ...props }` and `type` is looked up on deck's
// global. That keeps the block OPEN — any deck.gl layer works without a code
// change here — while the projection sugar below stays specific to colour work.
function rdBuildLayers(spec, pal) {
  var space = spec.space || "oklch";
  var isOrbit = spec.view !== "map";
  var layers = [];

  // A map view draws NO basemap by default — the brand canvas IS the basemap, so no
  // vendor tiles or key are needed. But a demo can opt into real tiles with
  // `basemap: true` (OSM) or `basemap: "<url template>"`; it goes UNDER everything.
  if (!isOrbit && spec.basemap) {
    var tileUrl = spec.basemap === true
      ? "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      : spec.basemap;
    layers.push(new deck.TileLayer({
      id: "rd-basemap",
      data: tileUrl,
      minZoom: 0,
      maxZoom: 19,
      tileSize: 256,
      renderSubLayers: function (props) {
        var bb = props.tile.boundingBox;  // [[west, south], [east, north]]
        return new deck.BitmapLayer(props, {
          data: null,
          image: props.data,
          bounds: [bb[0][0], bb[0][1], bb[1][0], bb[1][1]]
        });
      }
    }));
  }

  if (isOrbit && spec.gamut && spec.gamut.length) {
    var frame = rdFrameLines(space, spec.gamut, rdRgb255(pal.ink, 200));
    // The requested chroma, drawn as the circle it actually is. Where it sits
    // outside the gamut ring, the design asked for a colour that does not exist.
    if (spec.targetChroma) {
      spec.gamut.forEach(function (L) {
        frame = frame.concat(rdTargetRing(L, spec.targetChroma, rdRgb255(pal.warn, 130)));
      });
    }
    layers.push(new deck.LineLayer({
      id: "rd-frame",
      data: frame,
      getSourcePosition: function (d) { return d.source; },
      getTargetPosition: function (d) { return d.target; },
      getColor: function (d) { return d.color; },
      getWidth: 1.5
    }));
  }

  (spec.layers || []).forEach(function (raw, i) {
    var props = Object.assign({}, raw);
    var type = props.type;
    delete props.type;
    if (!deck[type]) { throw new Error("unknown deck.gl layer type: " + type); }
    if (props.id === undefined) { props.id = "rd-layer-" + i; }

    // Lighting OFF by default. deck.gl's lit layers (PointCloudLayer, ColumnLayer,
    // …) shade every mark as a 3D solid under an ambient+directional light, which
    // DARKENS the fill — so a swatch renders muddier than its own hex. In a
    // colour-space visualiser the mark IS a colour claim; a lit mark makes that
    // claim false (the dot no longer matches the flat swatch). Flat/unlit is the
    // only colour-correct default. An author who genuinely wants shaded geometry
    // opts back in by putting `material` on the layer spec.
    if (props.material === undefined) { props.material = false; }

    // Pickable by default so hover tooltips (getTooltip) actually fire — a deck.gl
    // layer is NOT pickable unless asked, and a silent non-pickable layer looks
    // identical until you try to hover it. The basemap tile layer opts out below.
    if (props.pickable === undefined) { props.pickable = true; }

    // Sugar: a datum carrying `hex` needs neither a position nor a colour. We
    // derive BOTH from the colour itself — the datum IS its own coordinate.
    // This is what lets a palette be authored as a plain list of hex strings.
    var data = props.data || [];
    if (isOrbit && Array.isArray(data) && data.length && data[0] && data[0].hex) {
      if (props.getPosition === undefined) {
        props.getPosition = function (d) { return rdProject(space, d.hex); };
      }
      if (props.getColor === undefined && props.getFillColor === undefined) {
        props.getColor = function (d) { return rdRgb255(d.hex); };
        props.getFillColor = function (d) { return rdRgb255(d.hex); };
      }
      if (spec.targetChroma) {
        layers.push(new deck.LineLayer({
          id: props.id + "-clip",
          data: rdClipSpokes(data, spec.targetChroma, rdRgb255(pal.warn, 235)),
          getSourcePosition: function (d) { return d.source; },
          getTargetPosition: function (d) { return d.target; },
          getColor: function (d) { return d.color; },
          getWidth: 3
        }));
      }
    } else if (Array.isArray(data) && data.length && data[0] && data[0].position) {
      // A point cloud that is NOT a colour space (e.g. a reduced text embedding):
      // each datum carries its own `position` and `color`. PointCloudLayer's default
      // getColor is a CONSTANT black, so a `color` field would otherwise never show —
      // wire the accessors here so the topic colours actually render.
      if (props.getPosition === undefined) {
        props.getPosition = function (d) { return d.position; };
      }
      if (data[0].color && props.getColor === undefined && props.getFillColor === undefined) {
        props.getColor = function (d) { return d.color; };
        props.getFillColor = function (d) { return d.color; };
      }
    }
    layers.push(new deck[type](props));
  });

  return layers;
}

// The tooltip closure is shared by the plain-Deck path and the MapLibre-overlay
// path, so a datum reads the same whether the scene rides a WebGL canvas or a
// vector basemap. Factored out of rdRenderDeckGL for exactly that reuse.
function rdTooltip(spec, pal, tokens) {
  return function (info) {
    if (!info.object) { return null; }
    var o = info.object;
    // A point cloud of text (an embedding) shows the ACTUAL chunk, wrapped, with
    // its topic as a header — that is the whole point of a RAG-debugging view.
    if (o.text) {
      return {
        text: (o.topic ? o.topic.toUpperCase() + "\n" : "") + o.text,
        style: {
          background: pal.background, color: pal.text, fontFamily: tokens.fonts.body,
          fontSize: "12px", border: "1px solid " + pal.ink, borderRadius: "6px",
          padding: "8px 10px", maxWidth: "320px", whiteSpace: "normal", lineHeight: "1.4"
        }
      };
    }
    var label = o.label || o.name || o.hex;
    if (!label) { return null; }
    var body = label;
    if (o.hex) {
      var c = rdRgbToOklch(rdHexToRgb(o.hex));
      var maxC = rdMaxChroma(c.L, c.H);
      var target = spec.targetChroma;
      body += "\nL " + c.L.toFixed(3) + "  C " + c.C.toFixed(3) + "  H " + c.H.toFixed(1) + "°";
      body += "\nsRGB ceiling here: " + maxC.toFixed(3);
      // Two different facts, never conflated: sitting AT the ceiling is a
      // property of the hue; being CLIPPED needs a request to fall short of.
      if (c.C >= maxC - 0.004) { body += "\nat the sRGB ceiling"; }
      if (target && maxC < target - 0.004) {
        body += "\nCLIPPED: asked " + target.toFixed(3)
          + ", denied " + (target - maxC).toFixed(3);
      }
    }
    return {
      text: body,
      style: {
        background: pal.background, color: pal.text, fontFamily: tokens.fonts.mono,
        fontSize: "11px", border: "1px solid " + pal.ink, borderRadius: "6px",
        padding: "6px 8px", whiteSpace: "pre"
      }
    };
  };
}

function rdRenderDeckGL(block, tokens, theme) {
  var spec = block.payload;
  var pal = rdDeckPalette(tokens, theme);
  var isOrbit = spec.view !== "map";

  block.el.style.height = (spec.height || 460) + "px";
  block.el.style.background = pal.background;
  block.el.style.position = "relative";

  // A re-render must not leak the old scene. The Deck path holds a WebGL context;
  // the MapLibre path holds its own map + canvas. Tear down whichever this block
  // built last, so a theme flip rebuilds cleanly either way.
  if (block.deck) { block.deck.finalize(); block.deck = null; }
  if (block.map) { block.map.remove(); block.map = null; block.overlay = null; }

  var getTooltip = rdTooltip(spec, pal, tokens);

  // Vector-basemap path: MapLibre owns the map + camera, deck.gl rides on top as a
  // MapboxOverlay. A real dark basemap needs no vendor key (CartoDB ships a free GL
  // style), and MapLibre's tile pipeline is far more robust than a hand-rolled
  // raster TileLayer — which is exactly why a raster basemap can silently blank on
  // a flaky network while this keeps its tiles. `basemap` (raster) stays supported
  // for docs that want no MapLibre dependency; `basemapStyle` (vector) opts into this.
  if (!isOrbit && spec.basemapStyle && typeof maplibregl !== "undefined" && deck.MapboxOverlay) {
    var v = spec.initialViewState || {};
    block.map = new maplibregl.Map({
      container: block.el,
      style: spec.basemapStyle,
      center: [v.longitude || 0, v.latitude || 0],
      zoom: v.zoom || 1.2,
      pitch: v.pitch || 0,
      bearing: v.bearing || 0,
      interactive: spec.controller !== false,
      attributionControl: { compact: true }
    });
    block.overlay = new deck.MapboxOverlay({
      interleaved: false,
      layers: rdBuildLayers(spec, pal),
      getTooltip: getTooltip
    });
    block.map.addControl(block.overlay);
    return;
  }

  var view = isOrbit
    ? new deck.OrbitView({ id: "orbit", orbitAxis: "Y", fovy: 50 })
    : new deck.MapView({ id: "map", repeat: true });

  // OrbitView `zoom` is log2(pixels per world unit) — NOT a map zoom. Every
  // space here is normalised to a ~1-unit extent, so the scene needs ~2^9 to
  // fill the canvas. Framing it like a map (zoom 1-5) renders a correct scene
  // the size of a postage stamp: the classic OrbitView trap.
  //
  // A gamut study is a horizontal SLAB at some lightness, not the whole solid,
  // so the camera centres on that slab (y = L - 0.5) and pulls in tighter.
  // Left at the origin, the subject drifts to the top of the frame.
  var gamut = (isOrbit && spec.gamut) || [];
  var meanL = gamut.length
    ? gamut.reduce(function (a, b) { return a + b; }, 0) / gamut.length
    : 0.5;
  var initialViewState = spec.initialViewState || (isOrbit
    ? {
      target: [0, meanL - 0.5, 0],
      zoom: gamut.length ? 9.5 : 8.6,
      rotationX: 30,
      rotationOrbit: -28,
      minZoom: 7,
      maxZoom: 12
    }
    : { longitude: 0, latitude: 20, zoom: 1.2 });

  block.deck = new deck.Deck({
    parent: block.el,
    views: view,
    initialViewState: initialViewState,
    controller: spec.controller !== false,
    useDevicePixels: true,
    parameters: { clearColor: rdRgb255(pal.background).map(function (v) { return v / 255; }) },
    layers: rdBuildLayers(spec, pal),
    getTooltip: getTooltip
  });
}
