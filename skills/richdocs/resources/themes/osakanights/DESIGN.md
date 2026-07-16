# OsakaNights — Style Reference

> Synthwave on the headphones. Walking home through Osaka at 3am after a night of karaoke with friends — and with people who were strangers when the night began.

**Theme:** dark-native, with a full daylight mode · **v2** · Brandpack: [`design-tokens.json`](design-tokens.json)

<!-- ── OsakaNights self-theming. Loads the real typefaces (design-tokens names
     them but cannot fetch them) and puts Fraunces on the headings. Night is the
     default via `defaultTheme` in design-tokens.json. Stripped by GitHub; the
     tables below carry every value, so this block is purely additive.
     NOTE: a <script> here would NOT run — richdocs renders markdown into
     innerHTML, and browsers never execute scripts inserted that way. -->
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=JetBrains+Mono:wght@400;700&display=swap');

h1,h2,h3,h4{font-family:'Fraunces',Georgia,serif !important;letter-spacing:-.01em}
h1{font-weight:700}
h2{color:var(--rd-accent)}

/* ── named swatches ── */
.on-row{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin:18px 0 26px}
.on-sw{border:1px solid var(--rd-border);border-radius:12px;overflow:hidden;background:var(--rd-surface)}
.on-sw .duo{display:flex;height:64px}
.on-sw .duo i{flex:1;display:block}
.on-sw .lab{padding:10px 12px}
.on-sw .nm{font-family:'Fraunces',serif;font-weight:700;font-size:15px;color:var(--rd-fg);line-height:1.25}
.on-sw .hx{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--rd-muted);margin-top:3px}
.on-sw .rl{font-family:'Fira Sans',sans-serif;font-size:11.5px;color:var(--rd-muted);margin-top:5px}

/* ── in-context demo panel ── */
.on-demo{border:1px solid var(--rd-border);border-radius:16px;overflow:hidden;margin:22px 0 30px}
.on-demo .head{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:.07em;
  text-transform:uppercase;color:var(--rd-muted);padding:10px 20px;
  border-bottom:1px solid var(--rd-border);background:var(--rd-surface)}
.on-demo .body{padding:28px 24px;background:#101010}
:root[data-theme=light] .on-demo .body{background:#faf8f9}
.on-demo h4{font-family:'Fraunces',serif !important;font-weight:700;font-size:30px;
  color:#c3b0fd;margin:0 0 10px;line-height:1.15}
:root[data-theme=light] .on-demo h4{color:#5c4295}
.on-demo p{font-family:'Fira Sans',sans-serif;font-size:15.5px;line-height:1.65;
  color:#adadad;max-width:560px;margin:0 0 8px}
:root[data-theme=light] .on-demo p{color:#57525e}
.on-demo a{color:#6bcbf7;text-decoration:none;border-bottom:1px solid currentColor}
:root[data-theme=light] .on-demo a{color:#005e7d}
.on-demo .tagrow{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}
.on-demo .tag{font-family:'Fira Sans',sans-serif;font-size:12.5px;font-weight:500;
  border-radius:999px;padding:4px 12px}
.on-demo .btns{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px;align-items:center}
.on-demo .encore{font-family:'Fira Sans',sans-serif;font-weight:700;font-size:14.5px;
  background:#cc66ff;color:#101010;border:0;border-radius:999px;padding:12px 26px;
  box-shadow:0 0 26px rgba(204,102,255,.30);cursor:pointer}
:root[data-theme=light] .on-demo .encore{background:#6515c1;color:#fff;box-shadow:0 2px 14px rgba(101,21,193,.22)}
.on-demo .ghost{font-family:'Fira Sans',sans-serif;font-weight:500;font-size:14.5px;
  background:transparent;color:#dddddd;border:2px solid #323232;border-radius:999px;padding:10px 24px;cursor:pointer}
:root[data-theme=light] .on-demo .ghost{color:#1c1a20;border-color:#e5dee2}
.on-demo .call{border-radius:12px;padding:14px 18px;border:1px solid;margin-bottom:8px;
  font-family:'Fira Sans',sans-serif;font-size:14.5px}
.on-demo .call b{display:block;margin-bottom:2px}
.on-demo .cap{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:#858585;margin-top:4px}
.on-note{font-family:'Fira Sans',sans-serif;font-size:13.5px;color:var(--rd-muted);
  font-style:italic;border-left:2px solid var(--rd-border);padding-left:12px;margin:-14px 0 26px}
</style>

---

## The origin story

An electric city in a digital future. Full of life, fun, and quirkiness — and underneath it, a cultural tone of **kindness, empathy, and hospitality**.

That last part is not decoration. It is the load-bearing idea, and it is why this system looks the way it does.

**Legibility is a form of kindness.** Every accessibility decision here — the disambiguation gate on the typeface, the perceptually-even colour bands, the refusal to let colour ever carry meaning alone, the low cognitive load — is not compliance. It is **hospitality made structural**. A reader is a welcomed guest. You do not make a guest work to understand you.

And within that, we can always be **tastefully playful**. The mixture of typefaces carries the character; the disambiguation gate keeps it honest. Warmth and clarity are not in tension here. Clarity *is* the warmth.

---

## Scope

**OsakaNights** is the design system. It is worn by three surfaces:

| Surface | Role |
|---------|------|
| **Josh's Karaoke Bar** | The narrative home. The fiction that gives the system its personality, and the setting for example architectures. |
| **jpeak.ai** | The personal site. Wears the system unmodified. |
| **`/richdocs` default** | Every generated doc inherits this palette and geometry. Defaults to Night. |

One system, one palette, one voice. A cost review and a cocktail menu look like they came from the same place — because they did.

---

## The two mechanisms

**1. Perceptual isoluminance.** Every accent sits at the same **OKLCH lightness**, so no colour out-shouts another. Hierarchy comes from size and space, not volume.

> HSL lightness is a maths convenience, not a perceptual measure. Blue-violet is intrinsically dark, so at HSL `L=70%` a violet scores 5.88:1 while a gold scores 13.63:1 — a 7.75-point spread masquerading as "isoluminant". In OKLCH the same six hues span **9.7–10.6:1**. A 0.88-point spread. That is what makes a violet primary viable at all.

**2. Playfulness comes from character, not curvature.** Roundness costs legibility and crispness. The quirkiness is carried by the *detail* in the typefaces, by generous space, by a distinctive voice, and by colour used as a reward — never by making things bubbly.

Exactly one saturated element appears per view: the **Encore**.

---

## Modes — Night and Day

Night is home. Day is the walk back to the hotel as the sky goes pale.

The isoluminant band is **re-derived per mode**, never mirrored. Daylight keeps the full hue vocabulary, because colour has to carry meaning in charts.

| | **Night** (default) | **Day** |
|---|---|---|
| Canvas | `#101010` Midnight Asphalt | `#faf8f9` First Light |
| Accent band | OKLCH **L 0.80 · C 0.11** | OKLCH **L 0.45 · C 0.13** |
| Chart band | OKLCH **L 0.65 · C 0.19** | OKLCH **L 0.62 · C 0.18** |
| Encore | `#cc66ff` + **black** text (6.26:1) | `#6515c1` + **white** text (8.64:1) |

**The Encore inverts.** Getting the text colour backwards fails AA in either mode.

---

## Tokens — Colour

### The names, in context

<div class="on-demo">
<div class="head">Night — every colour doing its actual job</div>
<div class="body">
  <h4>Everyone is your friend you haven't met yet.</h4>
  <p>This heading is <strong>Synth Violet</strong>. This paragraph is <strong>Steam</strong> — the voice you actually read in, off the ramen stall. A link like <a href="#">the songbook</a> is <strong>Konbini Cyan</strong>: the 24-hour store that's always open to you. The caption below is <strong>Drizzle</strong>.</p>
  <div class="cap">ROOM-07 · 6 SEATS · $45/HR — DRIZZLE, ON MIDNIGHT ASPHALT</div>

  <div class="tagrow">
    <span class="tag" style="background:#122413;color:#90d192">Wasabi · available</span>
    <span class="tag" style="background:#07232f;color:#6bcbf7">Konbini Cyan · J-Pop</span>
    <span class="tag" style="background:#2a1828;color:#e6a4e0">Ume Plum · members</span>
    <span class="tag" style="background:#251f07;color:#d4bd67">Lantern Gold · happy hour</span>
    <span class="tag" style="background:#301715;color:#fda19a">Sunrise Coral · late</span>
  </div>
  <div style="max-width:560px;margin-top:18px">
    <div class="call" style="background:#0e2513;color:#83d494;border-color:rgba(131,212,148,.32)">
      <b>✓ Open Sign — room confirmed</b>The Shibuya is yours, Friday 8pm til late.</div>
    <div class="call" style="background:#2c1c04;color:#ebb25f;border-color:rgba(235,178,95,.32)">
      <b>! Last Train — 40 minutes</b>Nothing's wrong. You just deserve to know now, not later.</div>
    <div class="call" style="background:#321615;color:#ffa09c;border-color:rgba(255,160,156,.32)">
      <b>✕ Shutters Down — booking failed</b>The card was declined. Nothing has been charged.</div>
  </div>

  <div class="btns">
    <button class="encore">Encore — book a room</button>
    <button class="ghost">Ghost — see the songbook</button>
  </div>
</div>
</div>

<div class="on-note">Toggle the theme (top right) to see every name re-derive for Day. The tags sit on <strong>Reflection</strong> surfaces; the buttons sit on <strong>Midnight Asphalt</strong>; the ghost button's border is <strong>Kerb</strong>.</div>

### The Street — neutral spine

<div class="on-row">
  <div class="on-sw"><div class="duo"><i style="background:#101010"></i><i style="background:#faf8f9"></i></div>
    <div class="lab"><div class="nm">Midnight Asphalt</div><div class="hx">#101010 · day: First Light</div><div class="rl">Page canvas</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#1a1a1c"></i><i style="background:#ffffff"></i></div>
    <div class="lab"><div class="nm">Shopfront</div><div class="hx">#1a1a1c / #ffffff</div><div class="rl">Cards, nav bars</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#26262a"></i><i style="background:#f2eef0"></i></div>
    <div class="lab"><div class="nm">Stairwell</div><div class="hx">#26262a / #f2eef0</div><div class="rl">Elevated panels, inputs</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#323232"></i><i style="background:#e5dee2"></i></div>
    <div class="lab"><div class="nm">Kerb</div><div class="hx">#323232 / #e5dee2</div><div class="rl">Borders, dividers</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#dddddd"></i><i style="background:#1c1a20"></i></div>
    <div class="lab"><div class="nm">Streetlight</div><div class="hx">#dddddd / #1c1a20</div><div class="rl">Headings · 14.0:1</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#adadad"></i><i style="background:#57525e"></i></div>
    <div class="lab"><div class="nm">Steam</div><div class="hx">#adadad / #57525e</div><div class="rl">Body copy · 8.5:1</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#858585"></i><i style="background:#847e8c"></i></div>
    <div class="lab"><div class="nm">Drizzle</div><div class="hx">#858585 / #847e8c</div><div class="rl">Captions, metadata only</div></div></div>
</div>

#### Reference

The city itself: wet asphalt, shopfronts, the steam off a ramen stall.

| Name | Night | Day | Role |
|------|-------|-----|------|
| **Midnight Asphalt** | `#101010` | `#faf8f9` *(First Light)* | Page canvas |
| **Shopfront** | `#1a1a1c` | `#ffffff` | Cards, nav bars |
| **Stairwell** | `#26262a` | `#f2eef0` | Elevated panels, inputs |
| **Kerb** | `#323232` | `#e5dee2` | Borders, dividers |
| **Streetlight** | `#dddddd` | `#1c1a20` | Headings, high-emphasis text |
| **Steam** | `#adadad` | `#57525e` | Body copy — the default reading voice |
| **Drizzle** | `#858585` | `#847e8c` | Captions, metadata only |

Never pure `#ffffff` on pure `#000000`. Both glare, and glare is not hospitable.

### Neon — the accents · OKLCH L 0.80 · C 0.11

The signs. Bright, but seen through humid air — never blinding.

<div class="on-row">
  <div class="on-sw"><div class="duo"><i style="background:#c3b0fd"></i><i style="background:#5c4295"></i></div>
    <div class="lab"><div class="nm">Synth Violet ★</div><div class="hx">#c3b0fd / #5c4295 · 9.92:1</div><div class="rl">PRIMARY — headings, brand</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#6bcbf7"></i><i style="background:#005e7d"></i></div>
    <div class="lab"><div class="nm">Konbini Cyan</div><div class="hx">#6bcbf7 / #005e7d · 10.43:1</div><div class="rl">Links, interactive, focus</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#d4bd67"></i><i style="background:#655401"></i></div>
    <div class="lab"><div class="nm">Lantern Gold</div><div class="hx">#d4bd67 / #655401 · 10.22:1</div><div class="rl">Highlights, warm emphasis</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#90d192"></i><i style="background:#146720"></i></div>
    <div class="lab"><div class="nm">Wasabi</div><div class="hx">#90d192 / #146720 · 10.62:1</div><div class="rl">Positive, availability</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#e6a4e0"></i><i style="background:#7b3577"></i></div>
    <div class="lab"><div class="nm">Ume Plum</div><div class="hx">#e6a4e0 / #7b3577 · 9.74:1</div><div class="rl">Tags, categories</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#fda19a"></i><i style="background:#90302e"></i></div>
    <div class="lab"><div class="nm">Sunrise Coral</div><div class="hx">#fda19a / #90302e · 9.73:1</div><div class="rl">Decorative accent</div></div></div>
</div>

<div class="on-note"><strong>Naming rules</strong> — so the next colour names itself:
<strong>(1)</strong> Names come from the walk, not from the colour. "Konbini Cyan", never "Bright Blue".
<strong>(2)</strong> The role should be guessable from the name — Konbini is always open, so it is the interactive colour; Last Train is a kind early warning, so it is the warning; Encore is asked for once, so it appears once per view.
<strong>(3)</strong> Tier suffixes are mechanical. Every Neon has a <em>Bloom</em> and a <em>Reflection</em>. Never invent a poetic name for a derived tier — you should never have to look up which glow belongs to which sign.
<strong>(4)</strong> Chart series are numbered, not named. Name them and people say "the green one" instead of reading the legend, which hands them the vocabulary to break the colour-never-carries-meaning-alone rule.
<strong>(5)</strong> Signals are nouns of <em>state</em>, not severity words. "Shutters Down", not "Critical" — panic is not hospitable, even in an error.</div>

#### Reference

| Name | Night | Day | Contrast | Role |
|------|-------|-----|----------|------|
| **Synth Violet** ★ | `#c3b0fd` | `#5c4295` | 9.92:1 | **Primary.** Headings, brand, active states. The soundtrack. |
| **Konbini Cyan** | `#6bcbf7` | `#005e7d` | 10.43:1 | Links, interactive text. The 24-hour store that's always open to you. |
| **Lantern Gold** | `#d4bd67` | `#655401` | 10.22:1 | Highlights, warm emphasis |
| **Wasabi** | `#90d192` | `#146720` | 10.62:1 | Positive, availability |
| **Ume Plum** | `#e6a4e0` | `#7b3577` | 9.74:1 | Tags, categories |
| **Sunrise Coral** | `#fda19a` | `#90302e` | 9.73:1 | Decorative — the sky going pale on the walk home |

**Derive, never eyedrop.** Any hue plugged into `oklch(0.80 0.11 h)` is contrast-safe and harmonised by construction.

### Bloom — OKLCH L 0.89

The halo around a neon tube in humid air. Hover states, glow, and text sitting *on* a Reflection surface.

`#ddd4fe` Violet Bloom · `#aee4fe` Cyan Bloom · `#e9dba6` Gold Bloom · `#bfe8bf` Wasabi Bloom · `#f6cbf1` Plum Bloom · `#fecdc8` Coral Bloom

### Reflection — OKLCH L 0.24 (night) / 0.95 (day)

Neon in wet asphalt. Tinted surfaces for callouts and chips. Neon-on-its-own-Reflection always clears AA (8.5–9.1:1).

Night: `#211b30` Violet · `#07232f` Cyan · `#251f07` Gold · `#122413` Wasabi · `#2a1828` Plum · `#301715` Coral

### Signals — **RESERVED**

The night has a shape, and it tells you where you are in it. **Kind warnings, given early.**

<div class="on-row">
  <div class="on-sw"><div class="duo"><i style="background:#83d494"></i><i style="background:#00672d"></i></div>
    <div class="lab"><div class="nm">Open Sign</div><div class="hx">#83d494 / #00672d</div><div class="rl">good — 営業中, still lit</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#ebb25f"></i><i style="background:#734c02"></i></div>
    <div class="lab"><div class="nm">Last Train</div><div class="hx">#ebb25f / #734c02</div><div class="rl">warning — the clock is real</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#fea47c"></i><i style="background:#8c3701"></i></div>
    <div class="lab"><div class="nm">Last Orders</div><div class="hx">#fea47c / #8c3701</div><div class="rl">serious — act now</div></div></div>
  <div class="on-sw"><div class="duo"><i style="background:#ffa09c"></i><i style="background:#932a30"></i></div>
    <div class="lab"><div class="nm">Shutters Down</div><div class="hx">#ffa09c / #932a30</div><div class="rl">critical — it's over</div></div></div>
</div>

#### Reference

| Role | Name | Night | Day | Reflection |
|------|------|-------|-----|------------|
| good | **Open Sign** | `#83d494` | `#00672d` | `#0e2513` |
| warning | **Last Train** | `#ebb25f` | `#734c02` | `#2c1c04` |
| serious | **Last Orders** | `#fea47c` | `#8c3701` | `#31180c` |
| critical | **Shutters Down** | `#ffa09c` | `#932a30` | `#321615` |

**Signals are never assigned to a chart series.** If Shutters Down can also be "series 4", a red bar and a red error state become indistinguishable and the palette stops carrying meaning.

### Encore — the one saturated colour

`#cc66ff` (night, black text) / `#6515c1` (day, white text).

**One per view.** Primary CTA fill only — never text, never borders, never decoration, never a chart series. It carries a soft glow: the only shadow in the entire system. It is the thing you ask for at the end of the night, and you only get to ask once.

---

## Tokens — Typography

**A mixture of faces, deliberately.** Character comes from the *combination*; legibility is non-negotiable in each.

### Fraunces — Display
`--font-display` · Weights 600, 700 · 32–72px · line-height 1.05–1.15 · tracking -0.01em

A soft serif that earns its personality through **detail** — its `SOFT` and `WONK` variable axes — rather than roundness. This is the quirk. Display only, never below 28px.

### Fira Sans — Body & UI
`--font-body` · Weights 400–700 · 13–24px · line-height 1.5–1.65

Everything below 28px: body, nav, buttons, captions, inputs, chart labels. Humanist, characterful, and — critically — it gives lowercase `l` a **tail**.

### JetBrains Mono — Technical
`--font-mono` · Weight 400 · 13–14px

Code, IDs, prices, tabular figures, metadata.

### Bebas Neue — Signage only
Reserved **exclusively** for literal neon-sign motifs. A condensed grunge face; it fights everything above.

### The disambiguation gate 🔒

**A typeface that fails this is out, regardless of how beautiful it is.**

```
Illegal 1O0 · rn/m · vv/w · 5S8B
```

`l` vs `I` vs `1`, `O` vs `0`, `rn` vs `m` must resolve with **zero contextual deciphering**.

This is the hospitality principle made concrete. Making a reader squint and decode a glyph from context is a small unkindness, repeated hundreds of times per page. It is a pass/fail gate, not a score — which is why Fira Sans (tailed `l`) and Fraunces (serifed `l`) win, and why otherwise-lovely geometric faces lose.

> **Held in reserve:** Atkinson Hyperlegible Next — built by the Braille Institute specifically for glyph disambiguation. The right choice if dense tabular or technical content ever needs its own face.

### Type scale

| Role | Size | Weight | Line height | Tracking |
|------|------|--------|-------------|----------|
| caption | 13px | 400 | 1.5 | — |
| body-sm | 14px | 400 | 1.6 | — |
| body | 16px | 400 | 1.6 | — |
| body-lg | 18px | 400 | 1.65 | — |
| subheading | 24px | 600 | 1.4 | — |
| heading-sm | 32px | 600 | 1.15 | -0.01em |
| heading | 48px | 700 | 1.1 | -0.01em |
| display | 72px | 700 | 1.05 | -0.01em |

---

## Tokens — Spacing & Shapes

**Base unit:** 4px · **Density:** spacious

`4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96 · 128`

| Element | Radius |
|---------|--------|
| buttons, pills, tags | 9999px |
| cards | 16px |
| large cards | 24px |
| inputs | 12px |
| badges | 8px |

**Layout:** page max-width 1200px · section gap 96–128px · card padding 24–32px · reading measure 640px.

Elevation comes from **surface steps and 1px Kerb hairlines**, never drop shadows. The Encore's glow is the sole exception.

---

## Data Visualisation

**The default categorical series is `Ghibli Pastel`** — the soft accent band itself, doing double duty as the chart series. Named for Studio Ghibli's hand-painted watercolours. `Dotonbori` (deeper, richer) is kept as the alternate `seriesAlt` for when a denser look is wanted.

### Ghibli Pastel — the default categorical series · OKLCH L 0.80 / C 0.11

A defining OsakaNights identity, **used identically in Day and Night**. Eight hues on a golden-angle walk (137.5°) from Synth Violet (295°): `295° → 73° → 210° → 348° → 125° → 263° → 40° → 178°`.

`#c3affd #e9b26a #58d1e5 #f2a0cb #adca7b #9bbeff #fba587 #63d5bd`

**This palette takes priority over the chart-mark contrast gate.** On the light plot its marks sit at ~1.7:1 — an accepted, deliberate trade, because every series is legended (colour never alone) and adjacent hues still clear CVD (worst ΔE 9.3). It is recorded as an explicit `waivers.seriesContrast` in the brandpack; the gate honours it with a visible note rather than a silent skip. Do not darken the palette or the chart bed to satisfy the gate.

### Dotonbori — the deep alternate (`seriesAlt`) · OKLCH L 0.65 / C 0.19

The deeper, more saturated band, selectable as `seriesAlt`. Named for the neon canal: a run of signs, each distinct, none competing.

The order is not arbitrary. Consecutive hues step **113–158° apart, mean 133.6°** — approximately the **golden angle (137.5°)**.

```
275° → 32° → 166° → 303° → 56° → 214° → 5° → 130°
```

A golden-angle walk means **any prefix of the sequence is well separated.** Three series, five, eight — always spread. (Warm/cool alternation is a *consequence* of the big jumps, not the cause.)

**Assign in fixed order. Never cycle.** A 9th series folds into "Other", or becomes small multiples.

<div class="on-row" style="grid-template-columns:repeat(auto-fill,minmax(110px,1fr))">
  <div class="on-sw"><div class="duo" style="height:52px"><i style="background:#7180fe"></i></div>
    <div class="lab"><div class="nm" style="font-size:13px">Dotonbori 1</div><div class="hx">275° · violet</div></div></div>
  <div class="on-sw"><div class="duo" style="height:52px"><i style="background:#ec563d"></i></div>
    <div class="lab"><div class="nm" style="font-size:13px">Dotonbori 2</div><div class="hx">32°</div></div></div>
  <div class="on-sw"><div class="duo" style="height:52px"><i style="background:#06a87c"></i></div>
    <div class="lab"><div class="nm" style="font-size:13px">Dotonbori 3</div><div class="hx">166°</div></div></div>
  <div class="on-sw"><div class="duo" style="height:52px"><i style="background:#a86bec"></i></div>
    <div class="lab"><div class="nm" style="font-size:13px">Dotonbori 4</div><div class="hx">303°</div></div></div>
  <div class="on-sw"><div class="duo" style="height:52px"><i style="background:#d57004"></i></div>
    <div class="lab"><div class="nm" style="font-size:13px">Dotonbori 5</div><div class="hx">56°</div></div></div>
  <div class="on-sw"><div class="duo" style="height:52px"><i style="background:#02a0b9"></i></div>
    <div class="lab"><div class="nm" style="font-size:13px">Dotonbori 6</div><div class="hx">214°</div></div></div>
  <div class="on-sw"><div class="duo" style="height:52px"><i style="background:#e85080"></i></div>
    <div class="lab"><div class="nm" style="font-size:13px">Dotonbori 7</div><div class="hx">5°</div></div></div>
  <div class="on-sw"><div class="duo" style="height:52px"><i style="background:#6ba304"></i></div>
    <div class="lab"><div class="nm" style="font-size:13px">Dotonbori 8</div><div class="hx">130°</div></div></div>
</div>

<div class="on-note">Numbered, never named. If a series colour has a name, people say "the green one" instead of reading the legend — and the palette has handed them the vocabulary to break the colour-never-carries-meaning-alone rule.</div>

#### Reference

| Slot | Hue | Night | Day |
|------|-----|-------|-----|
| 1 | 275° | `#7180fe` | `#6977f0` |
| 2 | 32° | `#ec563d` | `#dd5139` |
| 3 | 166° | `#06a87c` | `#049e74` |
| 4 | 303° | `#a86bec` | `#9d65dd` |
| 5 | 56° | `#d57004` | `#c96900` |
| 6 | 214° | `#02a0b9` | `#0796ae` |
| 7 | 5° | `#e85080` | `#d94b78` |
| 8 | 130° | `#6ba304` | `#649803` |

Validated: worst adjacent CVD **ΔE 18.2** (target 12), all checks pass in both modes.

### Concrete — the muted greys

Grey is the default; colour is the exception. If everything is coloured, nothing is emphasised. **Push every series to Concrete and let one keep its neon.** The eye finds it preattentively, before conscious reading.

Night: `#7a7a7a` `#636363` `#505050` `#404040` · Day: `#868686` `#9e9e9e` `#b1b1b1` `#c4c4c4`

- **One accent** — a single takeaway. The executive-slide default.
- **Two accents** — a comparison. This is the ceiling.
- **Three or more** — you have rebuilt a categorical palette and destroyed the emphasis.

Concrete falls below 3:1 by design (it must recede), so **direct-label the accented series**. That is mandatory relief, not a nicety.

### Bundle of Fibres — two-level nesting

**Hue carries the family. Lightness carries the variant.** A reader sees "all the green ones are engine X" at a glance, then discriminates within it.

Steps vary **OKLCH lightness** (ΔL 0.12, well above the 0.06 floor) — *not* saturation. Varying saturation alone holds lightness roughly constant, so sub-variants collapse for colourblind readers and in greyscale print. Lightness survives both.

| Family | Light | Mid | Deep |
|--------|-------|-----|------|
| violet (275°) | `#abb9fe` | `#7d8df9` | `#5a66c7` |
| green (145°) | `#90d192` | `#4db155` | `#278733` |
| coral (32°) | `#fca391` | `#ea6d56` | `#b94834` |
| teal (195°) | `#57d4d4` | `#00aeae` | `#008282` |
| blue (240°) | `#78c7fd` | `#00a2ee` | `#0079b3` |

### Sequential — one hue, light → dark

Magnitude. Synth Violet, five steps, lightness strictly monotone. **Never a rainbow.**
Night: `#ddd4fe` `#c3b0fd` `#a48bf2` `#8266d9` `#5f45ad`

### Diverging — three scales, one rule

All share the same red pole and a **grey** midpoint — never a hue at zero, or zero starts to look like a value.

| Scale | ΔE under deuteranopia | Verdict | When |
|-------|----------------------|---------|------|
| **Violet ↔ Red** | **22.3** | ✅ Safe | **The default.** Brand-consistent and the most accessible. |
| **Teal ↔ Red** | **11.6** | 🟡 Usable | **When green's semantics matter** — good/bad, new/old, profit/loss. Reads as green-adjacent (cool vs hot) while actually surviving CVD. |
| **Green ↔ Red** | **1.0** | ❌ **Banned** | Never. The poles are *the same colour* to a deuteranope — it conveys nothing. |

Night violet arm: `#8f6edb` `#a890e9` `#c1b3f1` · midpoint `#3a3a3a` · red arm `#f1a8a1` `#e68078` `#d55753`
Night teal arm: `#009a9a` `#0ab8b9` `#74d0cf`

**Regardless of scale, the sign and arrow carry the meaning.** `▲ +$1,240` / `▼ −$380`. Cover the colour with your hand — if the meaning dies, the encoding is broken.

### Chart rules

- **One axis.** Never dual-axis. Two measures of different scale become two charts.
- **Colour follows the entity, never its rank.** Filtering must not repaint the survivors.
- **Text wears text tokens**, never the series colour.
- Thin marks, 2px lines, 4px rounded data-ends, a 2px surface gap between fills, recessive grid.
- A legend for ≥2 series; ≤4 series also direct-labelled. Identity is never colour-alone.

---

## Hospitality Contract

*(Elsewhere this would be called an accessibility contract. Here it is the point of the whole thing.)*

Machine-checked, not eyeballed.

| Guarantee | Rule |
|-----------|------|
| Body text | ≥ 7:1 on its surface |
| All Neon accents | ≥ 9.7:1 night, ≥ 6.6:1 day — guaranteed by the OKLCH band |
| Neon-on-Reflection | Every twin pair pre-verified. Never hand-pair a new combination. |
| Chart colours | CVD ΔE ≥ 12 adjacent · chroma ≥ 0.10 · ≥ 3:1 vs surface |
| Colour is never alone | Every signal, series and callout carries an icon, sign, or label |
| Focus always visible | 2px Konbini Cyan ring. Never `outline: none` without a replacement. |
| Reduced motion | `prefers-reduced-motion` collapses all transitions and the neon pulse |
| Glyphs are unambiguous | The disambiguation gate. No exceptions for beauty. |

**Not guaranteed, must be mitigated:** Drizzle `#858585` (5.16:1) clears AA but not AAA — metadata only. Concrete greys are deliberately sub-3:1 and require direct labels.

---

## Motion

| Element | Motion | Duration |
|---------|--------|----------|
| Hover | 1px lift, border shift | 150ms ease-out |
| Theme flip | Cross-fade | 350ms ease |
| Section entry | Fade + 8px rise, once | 400ms ease-out |
| Neon signage | Slow glow pulse, 4s loop | Signage only |
| Everything else | None | — |

**Nothing bounces, nothing springs.** Bounce is the cheap route to "playful" and it undermines the calm the palette works for. No scroll-jacking, no parallax, no autoplay carousels. `prefers-reduced-motion: reduce` disables all of it — including the pulse.

---

## Iconography

2px strokes, rounded caps and joins, no fills. Single colour from the Neon tier. 24px on a 24px grid, never below 16px. Icons **accompany** labels; they never replace them.

**There is no mascot, and that is deliberate.** The warmth here comes from the voice, the whitespace, and the character in the typefaces — not from a cartoon looking back at you. A mascot would be the design apologising for itself.

---

## Voice & Tone

The palette is calm so the *words* can be warm. **The reader is a welcomed guest.**

**Voice:** the person who's genuinely pleased you showed up. Warm, direct, a little dry. Never a hype-man, never corporate.

| Do | Don't |
|----|-------|
| "Book a room and sing badly with people who won't mind." | "Unleash your inner rockstar!!" |
| "Eight private rooms. Forty thousand songs. One tambourine of questionable quality." | "State-of-the-art entertainment solutions." |
| "Melbourne's Japanese karaoke bar." | "The best karaoke in Australia." |

- **Specificity over superlatives.** "Forty thousand songs" beats "an extensive library".
- **Self-deprecation is allowed; false modesty is not.**
- **One exclamation mark per page, maximum.** Probably zero.
- **Tastefully playful, never at the reader's expense.** The joke is never "you don't get it".
- The tagline is load-bearing: *"Everyone is your friend you haven't met yet."*

Applies to `/richdocs` output too. A cost review can be plain without being lifeless.

---

## Do's and Don'ts

### Do
- Derive every new colour from `oklch(0.80 0.11 h)` — contrast safety comes free.
- Use the Encore exactly once per view, always with the mode's correct text colour.
- Keep body at 16–18px / 1.6 / 640px measure. Readability is the product.
- Grey every chart series to Concrete except the one or two carrying the message.
- Use violet↔red for diverging by default; teal↔red only when green's semantics are needed.
- Leave 96–128px between sections. One idea per screen.

### Don't
- **Don't use green↔red diverging.** ΔE 1.0 — it conveys nothing to a deuteranope.
- Don't reuse a Signal colour as a chart series.
- Don't let colour carry meaning alone. Ever.
- Don't use the display face below 28px, or Bebas Neue outside signage.
- Don't add drop shadows. The Encore's glow is the only one.
- Don't ship a typeface that fails the disambiguation gate, however handsome.
- Don't chase "friendly" with roundness. Character, space, and voice do that job.

---

## Decision Log

| # | Decision | Evidence | Status |
|---|----------|----------|--------|
| 1 | `#E91E63` retired | 4.38:1 canvas / 4.35:1 white text / 4.38:1 black text — fails AA in every direction | ✅ |
| 2 | One system, three surfaces | The bar *is* the personal brand | ✅ |
| 3 | **Synth Violet primary** | Replaces neon pink | ✅ |
| 4 | **OKLCH, not HSL** | HSL band spread 5.88–13.63:1 (fake isoluminance). OKLCH: 9.7–10.6:1 | ✅ |
| 5 | Day keeps the full rainbow | Charts need hue vocabulary in both modes | ✅ |
| 6 | Chart palette ≠ UI palette | UI band fails CVD (ΔE 3.0) and the chroma floor | ✅ |
| 7 | Golden-angle hue order | Any prefix stays separated. ΔE 18.2 | ✅ |
| 8 | **Fraunces + Fira Sans** | Both clear the disambiguation gate; character via detail | ✅ |
| 9 | Roundness rejected | Fredoka/Nunito/Rubik lose legibility and crispness | ✅ |
| 10 | Signals reserved | Never a chart series | ✅ |
| 11 | **Violet↔red default, teal↔red for green semantics, green↔red banned** | Deuteranopia ΔE 22.3 / 11.6 / **1.0** | ✅ |
| 12 | Bebas Neue → signage only | Condensed grunge face; fights the system | ✅ |
| 13 | **No mascot** | Justified by "friendly = round" — a theory this system rejects. Warmth comes from voice, space and typeface character. | ✅ |
| 14 | **Named OsakaNights** | The accessibility work is hospitality made structural, not compliance. The name carries that. | ✅ |

---

## Similar Brands

- **Linear** — one chromatic accent in an otherwise monochrome dark system.
- **ElevenLabs** — editorial restraint; accents confined to artwork, not chrome.
- **Vercel** — hairline borders instead of shadows; typography carries the brand.
- **Stripe** — generous whitespace and a data-viz palette that is genuinely designed.

---

## Quick Start

```css
:root {
  /* The Street — neutral spine */
  --midnight-asphalt:#101010; --shopfront:#1a1a1c; --stairwell:#26262a;
  --kerb:#323232; --streetlight:#dddddd; --steam:#adadad; --drizzle:#858585;

  /* Neon — oklch(0.80 0.11 h) */
  --synth-violet:#c3b0fd; --konbini-cyan:#6bcbf7; --lantern-gold:#d4bd67;
  --wasabi:#90d192; --ume-plum:#e6a4e0; --sunrise-coral:#fda19a;

  /* Bloom — oklch(0.89 0.07 h) */
  --violet-bloom:#ddd4fe; --cyan-bloom:#aee4fe; --gold-bloom:#e9dba6;
  --wasabi-bloom:#bfe8bf; --plum-bloom:#f6cbf1; --coral-bloom:#fecdc8;

  /* Reflection — oklch(0.24 0.04 h) */
  --violet-reflection:#211b30; --cyan-reflection:#07232f; --gold-reflection:#251f07;
  --wasabi-reflection:#122413; --plum-reflection:#2a1828; --coral-reflection:#301715;

  /* Signals — RESERVED, never a chart series */
  --open-sign:#83d494;      /* good    */
  --last-train:#ebb25f;     /* warning */
  --last-orders:#fea47c;    /* serious */
  --shutters-down:#ffa09c;  /* critical*/

  /* Encore — the one saturated colour */
  --encore:#cc66ff; --encore-text:#101010;
  --encore-glow: 0 0 26px rgba(204,102,255,.30);

  /* Dotonbori — chart series, golden-angle order, oklch(0.65 0.19 h) */
  --dot-1:#7180fe; --dot-2:#ec563d; --dot-3:#06a87c; --dot-4:#a86bec;
  --dot-5:#d57004; --dot-6:#02a0b9; --dot-7:#e85080; --dot-8:#6ba304;

  /* Concrete — muted greys, the "everything else" */
  --concrete-1:#7a7a7a; --concrete-2:#636363; --concrete-3:#505050; --concrete-4:#404040;

  /* Sequential (Synth Violet) + diverging (violet↔red default) */
  --seq-1:#ddd4fe; --seq-2:#c3b0fd; --seq-3:#a48bf2; --seq-4:#8266d9; --seq-5:#5f45ad;
  --dv-good-1:#8f6edb; --dv-good-2:#a890e9; --dv-good-3:#c1b3f1;
  --dv-zero:#3a3a3a;
  --dv-bad-3:#f1a8a1; --dv-bad-2:#e68078; --dv-bad-1:#d55753;
  --dv-teal-1:#009a9a; --dv-teal-2:#0ab8b9; --dv-teal-3:#74d0cf;  /* green-semantics alt */

  /* Type */
  --font-display:'Fraunces', Georgia, serif;
  --font-body:'Fira Sans', system-ui, sans-serif;
  --font-mono:'JetBrains Mono', ui-monospace, monospace;

  /* Shape */
  --radius-card:16px; --radius-card-lg:24px;
  --radius-input:12px; --radius-badge:8px; --radius-pill:9999px;
  --page-max:1200px; --section-gap:112px; --measure:640px;
}

[data-mode="day"] {
  --midnight-asphalt:#faf8f9;  /* First Light */
  --shopfront:#ffffff; --stairwell:#f2eef0; --kerb:#e5dee2;
  --streetlight:#1c1a20; --steam:#57525e; --drizzle:#847e8c;

  --synth-violet:#5c4295; --konbini-cyan:#005e7d; --lantern-gold:#655401;
  --wasabi:#146720; --ume-plum:#7b3577; --sunrise-coral:#90302e;

  --open-sign:#00672d; --last-train:#734c02;
  --last-orders:#8c3701; --shutters-down:#932a30;

  --encore:#6515c1; --encore-text:#ffffff;

  --dot-1:#6977f0; --dot-2:#dd5139; --dot-3:#049e74; --dot-4:#9d65dd;
  --dot-5:#c96900; --dot-6:#0796ae; --dot-7:#d94b78; --dot-8:#649803;
  --concrete-1:#868686; --concrete-2:#9e9e9e; --concrete-3:#b1b1b1; --concrete-4:#c4c4c4;

  --dv-good-1:#6b4cae; --dv-good-2:#8973c3; --dv-good-3:#a89bd3;
  --dv-zero:#e8e4e6;
  --dv-bad-3:#d4918b; --dv-bad-2:#c1645e; --dv-bad-1:#a83634;
  --dv-teal-1:#067272; --dv-teal-2:#019696; --dv-teal-3:#60b5b5;
}
```

### Deriving a new colour

```python
# Any hue. Contrast-safe and harmonised by construction.
neon       = f"oklch(0.80 0.11 {h})"   # UI accent
bloom      = f"oklch(0.89 0.07 {h})"   # hover / glow
reflection = f"oklch(0.24 0.04 {h})"   # tinted surface
dotonbori  = f"oklch(0.65 0.19 {h})"   # chart fill
```
