# Programmatic, Deterministic Colour-System Generation — Research
Researched 2026-08-30. Every claim carries a source URL. Unverifiable claims flagged `[UNVERIFIED]`.

## 1. Material Design 3 / HCT — one seed, everything imputed
HCT = CAM16 hue + CAM16 chroma + **L\* from CIELAB** as "tone" (0=black, 100=white). Because tone *is* L\*, contrast becomes linear arithmetic:
> "A difference of 40 in HCT tone guarantees a contrast ratio >= 3.0, and a difference of 50 guarantees a contrast ratio >= 4.5." … "Unlike Y, L\* is linear to human perception, allowing trivial creation of accurate color tones." — <https://docs.materialkolor.com/material-color-utilities/com.materialkolor.hct/-hct/index.html>

**Seed → 6 palettes** by fixed chroma overrides + hue rotations ([dynamic_scheme.ts](https://github.com/material-foundation/material-color-utilities/blob/main/typescript/dynamiccolor/dynamic_scheme.ts)):

| Palette | `TONAL_SPOT` (Android default) | `FIDELITY`/`CONTENT` |
|---|---|---|
| primary | `hue, chroma 36` | `hue, chroma` (seed verbatim) |
| secondary | `hue, chroma 16` | `hue, max(chroma−32, chroma×0.5)` |
| tertiary | `hue+60, chroma 24` | rotated/derived |
| neutral | `hue, chroma 6` | `hue, chroma/12` |
| neutral-variant | `hue, chroma 8` | `hue, chroma/8 + 4` |
| error | fallback `fromHueAndChroma(25.0, 84.0)` — **fixed hue, not seed-derived** | same |

Other variants (same file): `VIBRANT` chroma 200, `RAINBOW` 48, `NEUTRAL` 12, `MONOCHROME` 0, `FRUIT_SALAD` hue−50/48, `EXPRESSIVE` hue+240/40. Each palette is sampled at 13 tones: 0,10,20,30,40,50,60,70,80,90,95,99,100 (<https://developer.android.com/develop/ui/views/theming/dynamic-colors>).

**Light/dark come from the *same* palettes** — a role is `(palette, tone(isDark), requiredRatioCurve, background)`. From [color_spec_2021.ts](https://github.com/material-foundation/material-color-utilities/blob/main/typescript/dynamiccolor/color_spec_2021.ts):

| Role | palette | light | dark | `ContrastCurve(−1, 0, .5, 1)` |
|---|---|---|---|---|
| primary | primary | 40 | 80 | `(3, 4.5, 7, 7)` |
| onPrimary | primary | 100 | 20 | `(4.5, 7, 11, 21)` |
| primaryContainer | primary | 90 | 30 | `(1, 1, 3, 4.5)` |
| onPrimaryContainer | primary | 30 | 90 | `(3, 4.5, 7, 11)` |
| surface | neutral | 98 | 6 | isBackground, no curve |
| onSurface | neutral | 10 | 90 | `(4.5, 7, 11, 21)` |
| onSurfaceVariant | neutral-var | 30 | 80 | `(3, 4.5, 7, 11)` |
| outline | neutral-var | 50 | 60 | `(1.5, 3, 4.5, 7)` |
| outlineVariant | neutral-var | 80 | 30 | `(1, 1, 3, 4.5)` |

Light/dark tones are near-mirrored (40↔80, 100↔20, 90↔30, 10↔90). **Dark mode is a different tone index into the same ramp, not a second palette.**

**Contrast is enforced, not assumed.** The declared tone is a starting point; `ContrastCurve` holds required ratios at contrast levels −1/0/0.5/1 and the resolver moves tone until met. Interpolation between the four anchors is piecewise-linear ([contrast_curve.ts](https://github.com/material-foundation/material-color-utilities/blob/main/typescript/dynamiccolor/contrast_curve.ts)). `contrastLevel`: 0.0 default, 0.5 medium, 1.0 high, −1.0 lowest (<https://api.flutter.dev/flutter/material/ColorScheme/ColorScheme.fromSeed.html>).

Solver primitives ([contrast.ts](https://github.com/material-foundation/material-color-utilities/blob/main/typescript/contrast/contrast.ts)): `ratioOfTones(a,b)`→1..21; `lighter(tone, ratio)`/`darker(...)` → **−1 if unachievable**; `lighterUnsafe`/`darkerUnsafe` clamp to 100/0 instead. `DynamicColor.foregroundTone(bgTone, ratio)` picks direction via `tonePrefersLightForeground(bgTone)`, with an explicit branch for when *neither* direction reaches the ratio ([dynamic_color.ts](https://github.com/material-foundation/material-color-utilities/blob/main/typescript/dynamiccolor/dynamic_color.ts)).

**Most reusable idea here:** model a role as `(palette, default tone, required-ratio curve, background ref)` and let a solver resolve tone. Contrast is a *constraint*, not a post-hoc lint.

## 2. Radix Colors — 12 steps defined by function, not lightness
Verbatim step semantics (<https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale>):

| Step | Reserved for | | Step | Reserved for |
|---|---|---|---|---|
| 1 | App background | | 7 | UI element border and focus rings |
| 2 | Subtle background | | 8 | Hovered UI element border |
| 3 | UI element background | | 9 | Solid backgrounds |
| 4 | Hovered UI element background | | 10 | Hovered solid backgrounds |
| 5 | Active / Selected UI element background | | 11 | Low-contrast text |
| 6 | Subtle borders and separators | | 12 | High-contrast text |

Why function-not-lightness: step **9 is the highest-chroma step** — "the purest step mixed with the least amount of white or black" — so 9→10 is not the monotonic lightness move that 1→8 is, and 9/10 flip foreground polarity per hue ("Sky, Mint, Lime, Yellow, and Amber are designed for dark foreground text and steps 9 and 10") (ibid.).

**Contrast guarantee is stated in APCA, not WCAG:** steps 11 and 12 are "guaranteed to Lc 60 and Lc 90 APCA contrast ratio on top of a step `2` background from the same scale" (ibid.).

**Dark scale:** the step *number* keeps its use case across modes — swap the scale, not the token; alias instead (`AppBg` → white in light, step 1/2 in dark) (<https://www.radix-ui.com/colors/docs/overview/aliasing>). The actual light→dark generation algorithm is **not published** `[UNVERIFIED]`.

**Custom palettes** (<https://www.radix-ui.com/colors/docs/overview/custom-palettes>): generated "based just on a couple reference colors"; `/colors/custom` emits steps 1–12 + alpha + P3 + Themes extras (surface/indicator/track) with sRGB fallbacks. **Dark is a separate generation pass** (toggle appearance, paste after light CSS). Stated caveat: *"As long as you use a reasonable background color, the contrast ratios will be similar to what Radix Colors provide"* — contrast is **inherited by construction, not solved for**. Themes ships 18 accents + 6 grays and auto-pairs a complementary gray to the accent (<https://www.radix-ui.com/themes/docs/theme/color>).

## 3. Adobe Leonardo — contrast ratio is the *input*
<https://leonardocolor.io/api.html> · <https://github.com/adobe/leonardo>
```js
new Color({ name, colorKeys: ['#2451FF'], colorspace: 'LCH', ratios: [3, 4.5], smooth: false })
new BackgroundColor({ ... })                        // exactly one required per Theme
new Theme({ colors, lightness: 100, contrast: 1, saturation: 100, output: 'HEX' })
```
Model: `colorKeys` interpolate **black → each key colour → white** into a lightness scale; `ratios` then *select* points on that scale by target contrast against the theme background, whose perceived lightness is `lightness` (0–100). **One theme, two modes:** re-render with `lightness: 100` (light) and `lightness: 10` (dark) — the same ratios hold. `contrast` is a global ratio multiplier (default 1); `saturation` desaturates 0–100.

Negative ratios give below-background steps: `[-1.4,-1.3,-1.2,1,2,3]` → `blue25, blue50, blue75, blue100, blue200, blue300`. Named-ratio form is the semantic-role hook: `ratios: { 'blue--largeText': 3, 'blue--normalText': 4.5 }` (api.html).

Constraints before adopting: colorspaces are **LCH, LAB, CAM02, HSL, HSLuv, HSV, RGB — no OKLCH/OKLAB**; **WCAG 2.x only**, no `formula` option for APCA/WCAG3 (grepped `packages/contrast-colors/README.md`: zero hits for oklch/oklab/apca/wcag3). Exact ratios are not always hit — "the tool takes an input (target ratio) but most often outputs a contrast ratio slightly higher… Since the WCAG requirement is defined as a minimum… it should be fine" (README). It overshoots rather than failing.

## 4. OKLCH / OKLAB and gamut mapping
**Why not HSL:** HSL's L is not perceived lightness, so equal L across hues looks unequal, `darken()` behaves differently per hue, and *changing only the hue* (accent → error red) silently shifts contrast into failure (<https://evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl>). CSS ranges: L 0–1, C 0–~0.37 in sRGB (higher in P3), H 0–360 (ibid.).

**The standard out-of-gamut technique is chroma reduction — not clipping, not lightness variation.** CSS Color 4 does a **binary search on chroma in OKLCh**, L and H fixed, with **MINDE**: each candidate is compared to its channel-clipped version via `deltaEOK`; below the JND (**0.02**) take the clipped version and stop. L ≤ 0 → black, L ≥ 1 → white (<https://colorjs.io/docs/gamut-mapping>). Pure clipping fails on yellows; pure chroma reduction over-desaturates — colorjs.io's P3-yellow example drops chroma 123 → 25 naively vs 103 with the CSS algorithm (ibid.). That gap is why MINDE exists.

Caveat for the decision: OKLCh is excellent for *interpolation* but its use as the gamut-mapping space is contested — it "can give odd results in specific cases despite doing a better job at preserving hue" (<https://github.com/w3c/csswg-drafts/issues/7071>; still-open <https://lists.w3.org/Archives/Public/public-css-archive/2026Jan/0619.html>).

| Library | Default out-of-gamut behaviour |
|---|---|
| colorjs.io | `toGamut({method:"css"})` — CSS Color 4 binary chroma search in Oklch, **default** |
| Culori | `toGamut(dest='rgb', mode='oklch', delta=differenceEuclidean('oklch'), jnd=0.02)`, v3.1.0+; `clampChroma` bisects chroma in **CIELCh by default** |
| chroma.js | **Clipping only** — `.clipped()` merely *reports* clipping; no gamut mapping |

Culori's own warning: `clampChroma` is "not guaranteed to return the optimal result" due to CIELCh discontinuities, falling back to `clampRgb` (<https://culorijs.org/api/>).

## 5. APCA vs WCAG 2.x — precise status
- APCA was **only ever "exploratory"** in WCAG 3 and was **formally pulled from the July 2023 working draft**. As of April 2026 the draft says: *"The contrast algorithm used in WCAG 3 is yet to be determined."* — <https://adrianroselli.com/2026/04/wcag3-contrast-as-of-april-2026.html>
- WCAG 3.0 is still a Working Draft (March 2026), not expected at Recommendation before ~2028–2030 — <https://www.accessibility.org.au/new-2026-update-for-the-wcag-3-0-working-draft/>
- Legal/procurement conformance today is **WCAG 2.x AA — 4.5:1 and 3:1** — <https://www.webability.io/blog/wcag-3-0-explained>
- **Shipped system documenting in APCA:** Radix Colors states step 11/12 as Lc 60 / Lc 90 (§2). That is a *documentation* choice, not a conformance claim.
- **Posture:** gate on WCAG 2.x, report APCA alongside. Do not swap the gate.

## 6. JS/TS pipeline — what you actually call

| Stage | Reach for | Call |
|---|---|---|
| Seed parse/serialize | Culori | `converter('oklch')`, `formatCss()` — <https://culorijs.org/api/> |
| Ramp generation | chroma.js | `chroma.scale([...]).mode('oklch').correctLightness().colors(n)` — <https://gka.github.io/chroma.js/> |
| Gamut mapping | colorjs.io | `.toGamut({method:'css', space:'srgb'})` — <https://colorjs.io/docs/gamut-mapping> |
| Contrast verification | colorjs.io | `Color.contrast(a, b, 'WCAG21' \| 'APCA')` — <https://colorjs.io/docs/contrast> |

- `correctLightness()` is a **bisection on CIELAB L\*** against the linear ideal, `max_iter = 20`, tol `1e-2` — <https://github.com/gka/chroma.js/blob/main/src/generator/scale.js>
- colorjs.io contrast algorithm strings (exact, case-insensitive): `WCAG21`, `APCA`, `Michelson`, `Weber`, `Lstar`, `DeltaPhi`. **APCA 0.0.98G shipped** (`normBG 0.56`, `normTXT 0.57`, `revTXT 0.62`, `revBG 0.65`, `blkThrs 0.022`, `blkClmp 1.414`) — <https://github.com/color-js/color.js/blob/main/src/contrast/APCA.js>
- **Culori has no APCA** — `wcagContrast`/`wcagLuminance` only (<https://culorijs.org/api/>). chroma.js: `chroma.contrast()` (WCAG), `chroma.deltaE()` (CIEDE2000 since v2.2.0); OKLab/OKLCh added v2.4.0, modern CSS syntax v3.0.0 — <https://github.com/gka/chroma.js/blob/main/CHANGELOG.md>
- Culori tree-shakes only via `culori/fn` + `useMode(modeOklch)` — <https://culorijs.org/guides/tree-shaking/>

## 7. Direct answers
**Minimum seed set.**
- **M3: one colour.** Secondary, tertiary and both neutrals are imputed by fixed chroma overrides and hue rotations off that one HCT; **error is hard-coded hue 25 / chroma 84**, not seed-derived ([dynamic_scheme.ts](https://github.com/material-foundation/material-color-utilities/blob/main/typescript/dynamiccolor/dynamic_scheme.ts)).
- **Radix: "a couple reference colors"** — an accent plus a background, gray auto-paired to the accent, dark a second pass (<https://www.radix-ui.com/colors/docs/overview/custom-palettes>).
- **Leonardo: key colour(s) + a background + a ratio list.** The background is mandatory — contrast is meaningless without it (<https://leonardocolor.io/api.html>).
- Practical floor for a new system: **1 brand colour + 1 background lightness**. A second seed buys a non-imputed neutral; a third buys a non-imputed error/semantic hue.

**Contrast vs brand — the published escape hatches.**
1. **M3 `FIDELITY`/`CONTENT`**: `primaryPalette = fromHueAndChroma(seed.hue, seed.chroma)` and `primaryContainer.tone = sourceColorHct.tone` — the seed appears **verbatim**; the *foreground* then moves via `DynamicColor.foregroundTone(container.tone, 4.5)` to restore contrast. Brand is pinned; contrast is bought from the other side of the pair (`color_spec_2021.ts`). This is the real escape hatch.
2. **M3 `contrastLevel` −1 → 1** as a system-wide waiver dial: every role carries a four-ratio `ContrastCurve`, so relaxing/tightening is one parameter, never a per-token override (`contrast_curve.ts`).
3. **Radix's refusal**: *"Radix Colors are not intended to be customised… Any customisation would likely break these features"*; the sanctioned move is to **add a custom brand scale alongside** the accessible ones (<https://www.radix-ui.com/colors/docs/palette-composition/composing-a-palette>). That *is* the waiver: brand lives in a separate, non-guaranteed scale.
- **Leonardo has no waiver** — a brand colour is only a `colorKey` (an interpolation anchor) and is not guaranteed to appear in the output at all. Output is whatever hits the ratio.

**Hue walk at constant L+C, out-of-gamut hues.** Standard technique: **reduce chroma, hold L and H** — CSS Color 4 binary chroma search + MINDE (<https://colorjs.io/docs/gamut-mapping>). Do **not** vary lightness — that destroys the contrast guarantee the ramp exists for. Do **not** plain-clip — it wrecks hue on yellows (ibid.). Defaults: colorjs.io `css`; Culori `toGamut` CSS-like at `jnd 0.02`; chroma.js clips silently. **Consequence:** for a fixed-L+C hue walk your effective chroma is the **min over hues** — yellows/greens cap far lower than blues, so either accept per-hue chroma variance or pick C = the sRGB-safe minimum at that L.

**Golden-angle (137.5°) prior art.** Yes, and it is old and shallow.
- Canonical: Martin Ankerl, *How to Generate Random Colors Programmatically* (2009) — increment hue by the golden-ratio conjugate **0.618033988749895** in HSV — <https://martin.ankerl.com/2009/12/09/how-to-create-random-colors-programmatically/>
- Implementations: <https://github.com/Alex7Kom/golden-colors> · <https://topher.io/writing/secrets-of-the-golden-angle>
- **No serious design system uses it as the primary mechanism**, and the reason is gamut shape, not maths. iWantHue instead runs **k-means / force-vector repulsion in CIELab** and states the limit outright: *"selecting high chromas digs a big hole in the color space, but because its shape is not even, only certain hues remain"* — several blue-purples, few greens, no yellow; its "Fancy" preset caps near 10 colours because "chroma and lightness have a narrow range" — <https://medialab.github.io/iwanthue/theory/> · <https://github.com/medialab/iwanthue>
- **Verdict:** golden-angle spacing is a good *deterministic tie-breaker* for unbounded category counts (never repeats, no clustering, stateless from an index). It is a poor *distinctness* guarantee above ~8–10 categories, because equal hue steps are not equal perceptual steps and the sRGB solid is not a cylinder. Above that, cluster in Lab/OKLab under explicit L/C constraints, or fall back to a curated qualitative palette.

## 8. Flagged gaps
- Radix's light→dark generation algorithm is not published `[UNVERIFIED]`.
- The `40 tone → 3:1 / 50 tone → 4.5:1` rule is documented in MaterialKolor's port of the `Hct` class doc comment, not on m3.material.io; upstream `ColorUtils.java` does not carry it.
- Leonardo's internal solver (binary search vs sampled scan along the interpolated scale) is undocumented `[UNVERIFIED]`.
