# V2 AI — Brand & Design Reference (`DESIGN.md`)

Distilled from the **V2 AI Design System**. Source of truth for how V2 AI looks and sounds. Use this to steer the brandvoice agent skill.

**Theme:** light-mode-native (white/black/yellow), with a full dark mode · **v2** · Colour engineering ported from the OsakaNights core (OKLCH bands, golden-angle chart hues, CVD validation) and re-derived against V2's own hues. Every number in this document was computed, not estimated. Palettes are validated with `dataviz/scripts/validate_palette.js`.

---

## 1. Who V2 AI is

AI-native enterprise consultancy (originally V2 Digital), operating across APAC. Deep partner alliances (AWS, Google Cloud, Databricks, NVIDIA, OpenAI, Snowflake). Positioned around enterprise AI, data platforms, agentic systems, and responsible scaling.

- **Positioning lines:** "We turn disruption into unstoppable growth." · "Harness the power of AI in the Enterprise."
- **Four service pillars:** **ALIGN → ENABLE → SCALE → SECURE** (always in this order).

---

## 2. Voice & tone — the core of the brandvoice skill

**Persona: a senior enterprise consultant, not a startup.** Confident, consultative, grave-but-plain-spoken.

### Rules
- **Voice:** third-person collective by default — "V2 is…", "We turn…", "Our deep alliances…". Use "you" only to address the enterprise buyer directly, and rarely.
- **Sell the verb, not the technology.** Frame everything as an outcome: "Transforming AI ambition into accountable strategy," "Securing AI and data from design to runtime."
- **Length:** headlines one line (max two). Body copy 2–3 short, declarative sentences. No walls of text.
- **No exclamation marks. No emoji. No unicode dingbats. No sass.** Affect comes from typography, colour, and photography — never pictograms in running text.
- **Australian spelling** — "Modernisation," "alliances." Respect it.
- **Numbers as digits + symbol** — "$30m," "Series A."

### Casing (strict)
- **Title Case** — page section headings: "Some of our Customers," "Our Services," "Why V2 AI."
- **UPPERCASE** — nav labels, pillar names (ALIGN / ENABLE / SCALE / SECURE), CTA buttons (CONTACT, SIGN UP), eyebrow tags ("Case Study").
- **Sentence case** — paragraph body and card copy.

### Punctuation signatures
- "READ MORE" is **always** followed by a chevron `›` (U+203A) — never →, », or an emoji arrow. This `›` is the *only* non-typographic glyph the brand allows in text.
- CTA buttons carry a small filled triangle **arrow "bump"** to the right (a graphic element, not a text character).

### Reference copy (verbatim)
- Hero: "Harness the power of AI in the Enterprise."
- Sub-hero: "V2 is a leading AI-native consultancy that helps enterprises solve complex challenges, accelerate transformation, and unlock new opportunities."
- ALIGN card: "Transforming AI ambition into accountable strategy, measurable value, and responsible, continuous governance."
- Industrial AI: "Beyond the brochureware with highly developed, enterprise AI & Agentic factories, aligned with responsibility and risk."

---

## 3. Colour

**Anchor palette is 3 values** — every surface starts on one of these:

| Token | Hex |
|---|---|
| Yellow (primary brand / CTA) | `#FFC000` |
| Black | `#000000` |
| White | `#FFFFFF` |

**Service accent system — 4 colours, one per pillar.** Use *only* on pillar icons, card borders, case-study eyebrows, and deep-tint column backgrounds.

| Pillar | Accent | Deep-tint bg |
|---|---|---|
| ALIGN | `#F1325F` (pink) | `#2D0F13` |
| ENABLE | `#2BBF4A` (green) | — |
| SCALE | `#36BAF4` (cyan) | `#072533` |
| SECURE | `#FF8C00` (orange) | `#342804` |

**Neutrals:** near-black ink `#1A1818`, body mute `#666666`, dark-bg mute `#BFBFBF`, texture bed `#EBEBEB`.

### Colour rules
- **Never mix accents inside one block.** An ALIGN block is pink only. The full services grid shows all four in pillar order.
- **No gradients for general backgrounds.** The only permitted gradients: subtle transparent→black protection gradients on photo heroes, and the soft two-stop gradients baked into the pillar-icon SVGs.
- No bluish-purple, no duotone photo filters.

### 3.1 The measured truth about the brand colours

Nothing below changes a brand hex. It states, with real WCAG maths, what each hex is legally allowed to *do*. All ratios computed against pure `#FFFFFF` and pure `#000000`.

| Colour | On white | On black | Verdict |
|---|---|---|---|
| Yellow `#FFC000` | **1.64:1** | **12.79:1** | Fails everything as text on white. Passes AAA as a *fill* under black text. |
| ALIGN `#F1325F` | 3.92:1 | 5.36:1 | Fails AA body text on white. Passes on black. |
| ENABLE `#2BBF4A` | 2.43:1 | 8.65:1 | Fails AA text on white by a wide margin. |
| SCALE `#36BAF4` | 2.21:1 | 9.49:1 | Fails AA text on white by a wide margin. |
| SECURE `#FF8C00` | 2.33:1 | 9.00:1 | Fails AA text on white by a wide margin. |
| Ink `#1A1818` | 17.68:1 | — | The light-mode reading voice. |
| Body mute `#666666` | 5.74:1 | — | AA for body, not AAA. |
| Dark mute `#BFBFBF` | — | 11.42:1 | AAA on black. |
| Texture bed `#EBEBEB` | — | 17.62:1 | Doubles as the dark-mode reading voice. |

**The yellow rule, stated plainly.** `#FFC000` on white is **1.64:1**. That is not a marginal failure — the AA floor for body text is 4.5:1 and for large text 3:1, so brand yellow misses the *easiest* threshold by roughly half. It is illegible as text on white and it will fail any audit.

> **Yellow is a surface, not an ink.** Use `#FFC000` as a CTA block, a hero band, a highlight bed, a bar fill. Put **black `#000000` (12.79:1)** or **ink `#1A1818` (10.77:1)** on top of it. **White on yellow is 1.64:1 and is banned.** Yellow is never body text, never a link, never a chart series, never a hairline on white.

**The pillar accents have the same shape of problem.** As raw hexes they are *fills and borders on black beds* — which is exactly how the brand already uses them (3px card borders, pillar icons, eyebrows on deep tints), so nothing existing breaks. But at 2.21–3.92:1 on white they cannot be accent *text* in light mode. Section 3.2 derives a text-safe tier for that job, at the same hues.

### 3.2 Accent tiers — OKLCH bands, not HSL

HSL lightness is arithmetic, not perception: at identical HSL lightness a cyan and an orange land at wildly different contrast, so an "even" HSL palette shouts in some hues and whispers in others. Every derived V2 tier is therefore pinned to a constant **OKLCH lightness**, which is perceptual by construction. Measured on V2's own four hues, the derived bands hold a **0.66-point** contrast spread in light mode and a **1.03-point** spread in dark — versus a **7.28-point** spread across the four raw brand accents on black (5.36:1 to 9.49:1).

The pillar hues, measured: ALIGN **13.9°** · SECURE **58.3°** · ENABLE **146.1°** · SCALE **232.5°** (brand yellow sits at 84.6°).

**UI accent tier — light mode: `oklch(0.50 0.11 h)`.** Text-safe on white.

| Pillar | Light-mode accent | On white |
|---|---|---|
| ALIGN | `#974550` | 6.40:1 |
| ENABLE | `#33733B` | 5.74:1 |
| SCALE | `#006C94` | 5.88:1 |
| SECURE | `#905114` | 6.23:1 |

**UI accent tier — dark mode: `oklch(0.74 0.13 h)`.** Text-safe on black.

| Pillar | Dark-mode accent | On black |
|---|---|---|
| ALIGN | `#F18692` | 8.57:1 |
| ENABLE | `#71C178` | 9.60:1 |
| SCALE | `#41B8EF` | 9.33:1 |
| SECURE | `#E79551` | 8.82:1 |

The raw brand hexes (`#F1325F`, `#2BBF4A`, `#36BAF4`, `#FF8C00`) remain the **fill/border/icon** tier and are unchanged. The derived tiers are the **text** tier. Both carry the same hue, so a pink border and pink accent text read as the same pillar.

**Tint surfaces** — `oklch(0.96 0.03 h)` light, `oklch(0.22 0.045 h)` dark. Callout beds and chips. The pairing of an accent with its own tint is pre-verified; never hand-pair a new one.

| Pillar | Light tint | Accent on it | Dark tint | Accent on it |
|---|---|---|---|---|
| ALIGN | `#FFEDEE` | 5.67:1 | `#2C1114` | 7.15:1 |
| ENABLE | `#E6F8E6` | 5.18:1 | `#0B200D` | 7.83:1 |
| SCALE | `#E3F5FF` | 5.25:1 | `#001E2C` | 7.63:1 |
| SECURE | `#FFEEE2` | 5.51:1 | `#2A1504` | 7.30:1 |

The existing deep-tint backgrounds (`#2D0F13`, `#072533`, `#342804`) are retained for full-bleed case-study columns; the tints above are the systematic version for components.

**Derive, never eyedrop.** Any new hue plugged into these four expressions is contrast-safe and harmonised by construction:

```python
accent_light = f"oklch(0.50 0.11 {h})"   # text-safe on white
accent_dark  = f"oklch(0.74 0.13 {h})"   # text-safe on black
tint_light   = f"oklch(0.96 0.03 {h})"   # callout bed, light
tint_dark    = f"oklch(0.22 0.045 {h})"  # callout bed, dark
```

### 3.3 Status tier — RESERVED

Four states, on the same OKLCH bands as the accents. **A status colour is never assigned to a chart series.** If "critical" can also be "series 4", a red bar and a failed run become the same object and the palette stops carrying meaning.

| Role | Light | On white | Dark | On black | Light tint | Dark tint |
|---|---|---|---|---|---|---|
| good | `#33733B` | 5.74:1 | `#71C178` | 9.60:1 | `#E6F8E6` | `#0B200D` |
| warning | `#865900` | 6.10:1 | `#DA9E3F` | 8.94:1 | `#FEEFDC` | `#271701` |
| serious | `#954C28` | 6.28:1 | `#EE8F63` | 8.74:1 | `#FFEEE6` | `#2B1308` |
| critical | `#984646` | 6.36:1 | `#F28885` | 8.64:1 | `#FFEDEC` | `#2C1111` |

Status is a four-step ladder, not a traffic light: warning → serious → critical are distinguishable by hue *and* by the escalating word. Because the brand forbids emoji and dingbats, **the label carries the meaning** — every status chip is an UPPERCASE word (`WARNING`, `CRITICAL`) plus its tint bed. Colour is the second signal, never the first.

### 3.4 Muted grey ramp — the "grey everything, highlight one" tier

Grey is the default; colour is the exception. If every series is coloured, nothing is emphasised. Push every series to the muted ramp and let **one** keep its chart colour. The eye finds it pre-attentively, before conscious reading.

- **Light:** `#A4A4A4` `#B7B7B7` `#CACACA` `#DBDBDB` — 2.49 / 2.01 / 1.64 / 1.38:1 vs white
- **Dark:** `#717171` `#5D5D5D` `#4D4D4D` `#3D3D3D` — 4.30 / 3.19 / 2.48 / 1.93:1 vs black

One accent is a single takeaway — the executive-slide default. Two is a comparison, and that is the ceiling. Three or more and you have rebuilt a categorical palette and destroyed the emphasis.

The ramp is **deliberately below 3:1** so it recedes. That makes **direct labelling of the highlighted series mandatory**, not optional.

---

## 4. Typography

**Outfit everywhere.** (Montserrat appears in legacy pages and is being phased out — default to Outfit.)

- Weights in use: 100 Thin, 300 Light, 400 Regular, 500 Medium, 700 Bold.
- **Display sits at 100% line-height** — tight and assertive. Do not loosen it.
- Two optical signatures: (1) large **Light** weights (40–51px) create "airy authority" in feature paragraphs; (2) **ALL-CAPS Medium ~18px with +0.04em tracking** separates nav / buttons / pillar names from body.

| Role | Size | Weight |
|---|---|---|
| Section display ("Our Services") | 80px | Medium 500 |
| Hero headline | 65px | Bold 700 |
| Lead / feature paragraph | 30–51px | Light 300 |
| Body | 20px | Regular 400 |
| Nav / button / eyebrow (UPPERCASE) | 15.5–18px | Medium/Bold, +0.04em |

### 4.1 The disambiguation gate

```
Illegal 1O0 · rn/m · vv/w · 5S8B
```

`l` vs `I` vs `1`, `O` vs `0`, `rn` vs `m` must resolve with **zero contextual deciphering**. Making a reader decode a glyph from context is a small tax, repeated hundreds of times per page.

**Outfit does not pass this gate.** It is a geometric sans: its lowercase `l` is an unadorned vertical stroke, indistinguishable from capital `I`; its `0` is unslashed and reads as `O` at UI sizes. Outfit is brand-fixed and stays — so the gate is enforced by **routing**, not by replacement:

> **Any string a reader must transcribe or verify wears the mono face, not Outfit.** Identifiers, hashes, ARNs, region names, hex values, API keys, version numbers, tabular figures, chart axis ticks, and code. The mono face is **JetBrains Mono** (slashed zero, tailed `l`, disambiguated `rn`), `--font-mono`, 13–15px, weight 400.

Outfit keeps display, headlines, body, nav, buttons, and pillar names — prose, where context does the disambiguating. This is not a compromise of the gate; it is the gate applied where it bites.

### 4.2 Full type scale

Extends the brand scale downwards for UI and documentation surfaces. Display line-height stays at 100%.

| Role | Size | Weight | Line height | Tracking | Face |
|---|---|---|---|---|---|
| Section display | 80px | 500 | 1.0 | — | Outfit |
| Hero headline | 65px | 700 | 1.0 | — | Outfit |
| Feature lead | 30–51px | 300 | 1.1 | — | Outfit |
| Subheading | 24px | 500 | 1.3 | — | Outfit |
| Body | 20px | 400 | 1.55 | — | Outfit |
| Body-sm | 16px | 400 | 1.55 | — | Outfit |
| Label / nav / CTA (UPPERCASE) | 15.5–18px | 500–700 | 1.2 | +0.04em | Outfit |
| Caption | 14px | 400 | 1.45 | — | Outfit |
| Mono / identifiers | 13–15px | 400 | 1.5 | — | JetBrains Mono |

Reading measure: 640–720px. Body never below 16px.

---

## 5. Layout & spacing

- **1196px fixed content column** inside a 1728px frame; ~266px gutters each side. Text always aligns to the column; hero beds (yellow band, full-bleed photos) escape it.
- **Section padding:** 80px top, 80–120px bottom. Sections on a shared dark bed abut with **no divider** (gap → 0).
- **Gap rhythm:** 20 (inside card) · 28 (between pillar rows) · 50 (between blocks) · 100 (section head → first content). Mobile ≈ halves these.

---

## 6. Shapes, cards & buttons

- **Corner radius:** service cards use **10px** — the *only* rounded value. Everything else is **square (0px)**.
- **Service cards:** black fill, **3px coloured border** matching the pillar, 10px radius, 30px padding. Pillar icon (79×79) top-left.
- **Case-study cards:** no border; solid deep-tint bg (wine/navy/umber) matching pillar; 10px radius; eyebrow in accent colour.
- **Buttons:** outlined rectangle, 2px border, 0px radius, UPPERCASE 15.5px Bold, with a filled-triangle arrow bump on the right edge. Two sizes (41px / 76px tall), two colours (black border on light, white border on dark). **The yellow block IS the primary CTA** on black beds — no separate pill.
- **No drop shadows, no inner shadows, no glassmorphism, no frosted blur** on flat UI. Depth comes only from photography + protection gradients.
- **Hover = opacity down to ~0.75** (never a colour swap). Active state does not shrink or move — the brand is stoic.
- **Focus is never removed.** A 2px focus ring in `#006C94` (light) / `#41B8EF` (dark), square, offset 2px. `outline: none` without a replacement is a defect.

---

## 7. Imagery & iconography

- Photography is **warm, slightly desaturated**, with heavy ink-to-black protection gradients on 2–3 edges. Human/founder photos are flat-lit, full-bleed on black (black shirts dissolve into the page).
- Signature illustration: 3D "diamond-cut" geometric portal/cloud shapes — supplied as PNGs; **don't redraw them.**
- Texture: low-contrast warm-grey cement/paper bed behind the Services grid.
- **No stock iconography on photos, no duotone, no vignette** beyond the protection gradient.
- **No icon font.** V2 has no native icon library. Iconography exists only for the 4 pillars (custom SVGs) and footer socials (LinkedIn, YouTube, Medium — mono white-on-black). If general UI icons are needed, substitute **Lucide, stroke 1.5, 24px** — and flag it as a substitution.

---

## 8. Motion

- Fades and opacity only. **No bounces, no spring, no parallax.**
- Default any added motion to **240ms `cubic-bezier(0.2, 0.8, 0.2, 1)`** fades. Lean into stillness — this is an enterprise voice.
- `prefers-reduced-motion: reduce` collapses every transition to 0ms.

---

## 9. Do / Don't quick list

**Do**
- Start on black, yellow, or white.
- Title Case sections, UPPERCASE labels, sentence-case body.
- End "READ MORE" with `›`.
- Keep display at 100% line-height; use Light weights for large feature copy.
- Australian spelling; digits for numbers.
- Put black or ink on yellow. Treat yellow as a bed.
- Derive new colours from the OKLCH expressions in §3.2.
- Grey every chart series except the one or two carrying the message.

**Don't**
- Exclamation marks, emoji, unicode dingbats.
- Mixing service accents in one block.
- Gradient backgrounds, drop shadows, glass/frost.
- Rounded corners anywhere except 10px service cards.
- Redrawing the 3D portal illustrations.
- **White text on yellow (1.64:1), or yellow text on white (1.64:1).**
- **Green↔red diverging scales** (§10.4).
- Reusing a status colour as a chart series.
- Letting colour carry meaning with no label, sign, or word beside it.

---

## 10. Data visualisation

**The chart palette is not the UI palette.** Chart fills need chroma and depth that chrome does not: the categorical band sits at **`oklch(0.58 0.16 h)`** in light mode and **`oklch(0.64 0.17 h)`** in dark, versus the UI band's L 0.50 / L 0.74 at C 0.11–0.13.

### 10.1 The categorical series — golden-angle order

Eight slots. The hue order is a **golden-angle walk (137.5°)** anchored on ALIGN, so **any prefix of the sequence stays well separated** — three series, five, or eight, always spread. Warm/cool alternation is a consequence of the big jumps, not the goal.

```
13.9° → 232.5° → 99.0° → 321.5° → 184.0° → 58.3° → 269.0° → 146.1°
```

Adjacent steps: 141.4 · 132.2 · 138.9 · 133.3 · 141.7 · 137.5 · 137.5 (mean 137.5°). All four pillar hues land in the walk: ALIGN at slot 1, SCALE at slot 2, SECURE at slot 6, ENABLE at slot 8.

| Slot | Hue | Light `oklch(0.58 0.16 h)` | vs white | Dark `oklch(0.64 0.17 h)` | vs black |
|---|---|---|---|---|---|
| 1 | 13.9° *(ALIGN)* | `#C6495D` | 4.65:1 | `#DF576C` | 5.72:1 |
| 2 | 232.5° *(SCALE)* | `#0085B5` | 4.18:1 | `#0098CE` | 6.38:1 |
| 3 | 99.0° | `#8C7A00` | 4.29:1 | `#A18C00` | 6.27:1 |
| 4 | 321.5° | `#A455B2` | 4.65:1 | `#BA64C9` | 5.75:1 |
| 5 | 184.0° | `#008E81` | 4.05:1 | `#00A294` | 6.60:1 |
| 6 | 58.3° *(SECURE)* | `#B56200` | 4.46:1 | `#CE7000` | 5.94:1 |
| 7 | 269.0° | `#5471D8` | 4.44:1 | `#6383F2` | 6.06:1 |
| 8 | 146.1° *(ENABLE)* | `#249239` | 4.00:1 | `#32A646` | 6.68:1 |

**Validated** with `validate_palette.js` (Machado-2009 CVD, CIE76 ΔE), target adjacent ΔE ≥ 12:

- **Light, surface `#FFFFFF`** — lightness band PASS · chroma floor PASS · **worst adjacent CVD ΔE 27.8** (`#008E81` ↔ `#A455B2`, deuteranopia) · contrast vs surface PASS. All checks pass.
- **Dark, surface `#000000`** — lightness band PASS · chroma floor PASS · **worst adjacent CVD ΔE 29.1** (`#00A294` ↔ `#BA64C9`, deuteranopia) · contrast vs surface PASS. All checks pass.

**Assign in fixed order. Never cycle.** A ninth series folds into "Other" or the chart becomes small multiples. Slots are **numbered, never named** — a named series colour invites "the green one" instead of reading the legend.

Brand yellow `#FFC000` is **not** in the series and never will be. It is the CTA. A yellow bar and a yellow button in the same viewport is a broken signal.

### 10.2 Sequential ramp — one hue, magnitude only

SCALE cyan (232.5°), five steps, OKLCH lightness strictly monotone (ΔL 0.09–0.10, well above the 0.06 floor). **Never a rainbow for magnitude.**

- **Light:** `#61BDEB` `#42A0CD` `#1E85B0` `#006990` `#004E6C` — 2.10 / 2.94 / 4.17 / 6.13 / 9.11:1 vs white
- **Dark:** `#004E6C` `#006C94` `#278BB7` `#4DAAD7` `#6ECAF9` — 2.31 / 3.57 / 5.46 / 8.05 / 11.48:1 vs black

Both ramps pass the ordinal checks: monotone lightness, ΔL gaps above floor, single hue, and the pale end clears the 2:1 floor against its surface (2.10 light, 2.31 dark).

### 10.3 Two-level nesting

**Hue carries the family. Lightness carries the variant.** Vary OKLCH **lightness** (ΔL ≥ 0.12), never saturation — saturation-only variants hold lightness constant, so they collapse for colourblind readers and in greyscale print. Lightness survives both.

### 10.4 Diverging scales — green↔red is banned

All scales share a **grey midpoint**. A hue at zero makes zero look like a value.

| Scale | Worst CVD ΔE (poles) | Verdict | When |
|---|---|---|---|
| **SCALE cyan ↔ ALIGN pink** | **28.1** (protanopia) | Safe | **The default.** Brand-consistent and the most accessible. |
| **Teal ↔ ALIGN pink** | **12.9** (protanopia) | Usable | Only when green's semantics are load-bearing — profit/loss, new/old. Reads green-adjacent (cool vs hot) while actually surviving CVD. |
| **Green ↔ red** | **1.1** (deuteranopia) | **Banned** | Never. To a deuteranope the two poles are *the same colour*. The scale conveys nothing. |

V2 owns a green (ENABLE) and a pink-red (ALIGN), so the temptation is structural. Resist it: **1.1 ΔE is indistinguishable.**

**Default scale — cyan ↔ pink**

- Light: `#39B2E8` `#0085B5` `#005A7C` · mid `#8A8A8A` · `#8B2B3C` `#BA5663` `#EA808C`
- Dark: `#50C5FC` `#0898CD` `#00729C` · mid `#5A5A5A` · `#A64452` `#CE6874` `#FF939E`

**Green-semantics alternate — teal ↔ pink**

- Light: `#00BCBE` `#008C8D` `#005F60` · mid `#8A8A8A` · pink arm as above
- Dark: `#19D1D2` `#00A0A2` `#00787A` · mid `#5A5A5A` · pink arm as above

**Regardless of scale, the sign carries the meaning.** `+$1,240` / `−$380`, with the numeral in the mono face. Cover the colour with your hand: if the meaning dies, the encoding is broken.

### 10.5 Chart rules

- **One axis.** Never dual-axis. Two measures of different scale become two charts.
- **Colour follows the entity, never its rank.** Filtering must not repaint the survivors.
- **Text wears text tokens**, never the series colour.
- Square marks and square data-ends — the brand has one radius, and it is not here. 2px lines, a 2px surface gap between fills, recessive grid.
- A legend for two or more series; four or fewer are also direct-labelled. Identity is never colour-alone.
- Axis ticks, values, and identifiers wear the mono face (§4.1).

---

## 11. Accessibility contract

Machine-checked, not eyeballed. Every ratio here came from a script.

| Guarantee | Rule | Measured |
|---|---|---|
| Body text | ≥ 7:1 on its surface | Ink `#1A1818` on white **17.68:1** · `#EBEBEB` on black **17.62:1** |
| Yellow is a surface | Black or ink text only; white on yellow banned | `#000` on `#FFC000` **12.79:1** · `#1A1818` **10.77:1** · `#FFF` **1.64:1** |
| Accent text | ≥ 5.7:1, guaranteed by the OKLCH band | Light band **5.74–6.40:1** · dark band **8.57–9.60:1** |
| Accent on its tint | Every pair pre-verified; never hand-pair | **5.18–5.67:1** light · **7.15–7.83:1** dark |
| Chart colours | adjacent CVD ΔE ≥ 12 · chroma ≥ 0.10 · ≥ 3:1 vs surface | **ΔE 27.8** light · **29.1** dark, all checks pass |
| Sequential ramp | monotone lightness, ΔL ≥ 0.06, pale end ≥ 2:1 | ΔL **0.09–0.10** · pale end **2.10:1** / **2.31:1** |
| Colour is never alone | Every status, series and callout carries a label, sign, or word. The brand forbids icons in text, so the **word** does the work. | — |
| Focus always visible | 2px ring, `#006C94` light / `#41B8EF` dark. `outline: none` alone is a defect. | 5.88:1 / 9.33:1 |
| Reduced motion | `prefers-reduced-motion` collapses the 240ms fades to 0ms | — |
| Glyphs are unambiguous | Identifiers, figures and code route to JetBrains Mono (§4.1) | — |

**Not guaranteed, must be mitigated:**

- Raw brand accents (`#F1325F` 3.92:1, `#2BBF4A` 2.43:1, `#36BAF4` 2.21:1, `#FF8C00` 2.33:1 on white) are **fills, borders and icons only** in light mode. Use the §3.2 tiers for text.
- Body mute `#666666` is 5.74:1 — AA, not AAA. Secondary copy only.
- The muted grey ramp is deliberately sub-3:1 and **requires direct labels**.

---

## 12. Decision log

| # | Decision | Evidence | Status |
|---|---|---|---|
| 1 | **Yellow is a surface, not an ink** | `#FFC000` on white **1.64:1** — misses the 4.5:1 AA floor by roughly half, and the 3:1 large-text floor too. On black it is **12.79:1**. | Accepted |
| 2 | White on yellow banned; black or ink only | 1.64:1 vs **12.79:1** / **10.77:1** | Accepted |
| 3 | **Raw pillar accents demoted to fill/border/icon in light mode** | 2.21–3.92:1 on white. No brand hex changed; a derived text tier was added instead. | Accepted |
| 4 | **OKLCH bands, not HSL** | Raw brand accents span **5.36–9.49:1** on black (7.28-point spread). The derived OKLCH bands span **0.66** (light) and **1.03** (dark) points. | Accepted |
| 5 | Dark mode keeps `#000000` canvas but reads on `#EBEBEB`, not `#FFFFFF` | Pure white on pure black is 21:1 and glares. `#EBEBEB` is 17.62:1 and is already a brand neutral — no new colour needed. | Accepted |
| 6 | Chart palette ≠ UI palette | The UI band's chroma (0.11–0.13) sits at or below the 0.10 chart floor after gamut clipping, and its lightness is outside the chart band in both modes. | Accepted |
| 7 | **Golden-angle hue order, anchored on ALIGN** | Mean adjacent step **137.5°**; all four pillars land in the walk. Worst adjacent CVD **ΔE 27.8 / 29.1** against a target of 12. | Accepted |
| 8 | Brand yellow excluded from the chart series | It is the CTA. A yellow bar next to a yellow button destroys the CTA signal. | Accepted |
| 9 | **Green↔red diverging banned** | Deuteranopia ΔE **1.1** — the poles are the same colour. Cyan↔pink **28.1**; teal↔pink **12.9**. | Accepted |
| 10 | Status tier reserved, never a chart series | A red bar and a failed run must not be the same object. | Accepted |
| 11 | **Outfit fails the disambiguation gate; it stays anyway** | Geometric sans: bare `l`, unslashed `0`. Brand is fixed. Resolved by routing every transcribable string to JetBrains Mono rather than by replacing Outfit. | Accepted |
| 12 | Status carries a word, not an icon | The brand forbids emoji and dingbats. The UPPERCASE label is the primary encoding; colour is secondary. | Accepted |
| 13 | Square data marks in charts | The system has exactly one radius (10px, service cards). Charts do not get a second. | Accepted |

---

## 13. Quick start

```css
:root {
  /* Anchors */
  --v2-yellow:#FFC000; --v2-yellow-ink:#000000;   /* NEVER white on yellow */
  --v2-black:#000000;  --v2-white:#FFFFFF;

  /* Neutrals */
  --v2-ink:#1A1818; --v2-mute:#666666; --v2-texture:#EBEBEB; --v2-dark-mute:#BFBFBF;

  /* Pillar accents — RAW: fills, 3px borders, icons */
  --align:#F1325F; --enable:#2BBF4A; --scale:#36BAF4; --secure:#FF8C00;

  /* Pillar accents — TEXT tier, light: oklch(0.50 0.11 h) */
  --align-text:#974550; --enable-text:#33733B; --scale-text:#006C94; --secure-text:#905114;

  /* Tints — oklch(0.96 0.03 h) */
  --align-tint:#FFEDEE; --enable-tint:#E6F8E6; --scale-tint:#E3F5FF; --secure-tint:#FFEEE2;

  /* Status — RESERVED, never a chart series */
  --status-good:#33733B; --status-warning:#865900;
  --status-serious:#954C28; --status-critical:#984646;

  /* Chart series — golden-angle order, oklch(0.58 0.16 h) */
  --ser-1:#C6495D; --ser-2:#0085B5; --ser-3:#8C7A00; --ser-4:#A455B2;
  --ser-5:#008E81; --ser-6:#B56200; --ser-7:#5471D8; --ser-8:#249239;

  /* Muted ramp — grey everything, highlight one */
  --muted-1:#A4A4A4; --muted-2:#B7B7B7; --muted-3:#CACACA; --muted-4:#DBDBDB;

  /* Sequential (SCALE cyan) + diverging (cyan↔pink default) */
  --seq-1:#61BDEB; --seq-2:#42A0CD; --seq-3:#1E85B0; --seq-4:#006990; --seq-5:#004E6C;
  --dv-pos-3:#39B2E8; --dv-pos-2:#0085B5; --dv-pos-1:#005A7C;
  --dv-zero:#8A8A8A;
  --dv-neg-1:#8B2B3C; --dv-neg-2:#BA5663; --dv-neg-3:#EA808C;
  --dv-teal-1:#005F60; --dv-teal-2:#008C8D; --dv-teal-3:#00BCBE;  /* green-semantics alt */

  /* Focus */
  --focus:#006C94;

  /* Type */
  --font-body:'Outfit', system-ui, sans-serif;
  --font-mono:'JetBrains Mono', ui-monospace, monospace;  /* identifiers, figures, code */

  /* Shape */
  --radius-card:10px; --radius-everything-else:0;
  --content-col:1196px; --measure:680px;

  /* Motion */
  --fade:240ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

[data-theme="dark"] {
  --v2-ink:#EBEBEB; --v2-mute:#BFBFBF;

  --align-text:#F18692; --enable-text:#71C178; --scale-text:#41B8EF; --secure-text:#E79551;
  --align-tint:#2C1114; --enable-tint:#0B200D; --scale-tint:#001E2C; --secure-tint:#2A1504;

  --status-good:#71C178; --status-warning:#DA9E3F;
  --status-serious:#EE8F63; --status-critical:#F28885;

  --ser-1:#DF576C; --ser-2:#0098CE; --ser-3:#A18C00; --ser-4:#BA64C9;
  --ser-5:#00A294; --ser-6:#CE7000; --ser-7:#6383F2; --ser-8:#32A646;

  --muted-1:#717171; --muted-2:#5D5D5D; --muted-3:#4D4D4D; --muted-4:#3D3D3D;

  --seq-1:#6ECAF9; --seq-2:#4DAAD7; --seq-3:#278BB7; --seq-4:#006C94; --seq-5:#004E6C;
  --dv-pos-3:#50C5FC; --dv-pos-2:#0898CD; --dv-pos-1:#00729C;
  --dv-zero:#5A5A5A;
  --dv-neg-1:#A64452; --dv-neg-2:#CE6874; --dv-neg-3:#FF939E;
  --dv-teal-1:#00787A; --dv-teal-2:#00A0A2; --dv-teal-3:#19D1D2;

  --focus:#41B8EF;
}
```
