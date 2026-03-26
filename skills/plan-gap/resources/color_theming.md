# Mermaid Color Theming Reference

Techniques for creating visually rich, information-dense Mermaid diagrams using
systematic color encoding. Covers HSL-based category systems, dual-theme safety,
visual hierarchy, subgraph coloring, and four complete palette recipes.

---

## 1. Core Syntax Recap

### classDef + class

```mermaid
flowchart LR
    A[Input]:::inputPrimary --> B[Process]:::process --> C[Output]:::outputPrimary

    classDef inputPrimary   fill:#2563eb,stroke:#1e40af,color:#fff,stroke-width:2px
    classDef process        fill:#7c3aed,stroke:#5b21b6,color:#fff,stroke-width:2px
    classDef outputPrimary  fill:#059669,stroke:#047857,color:#fff,stroke-width:2px
```

### Shorthand `:::` operator

Apply during node declaration: `A:::className`

### Direct `style` directive

```
style nodeId fill:#f9f,stroke:#333,stroke-width:4px
```

### Available style properties

| Property | Purpose | Example |
|----------|---------|---------|
| `fill` | Node background color | `fill:#2563eb` |
| `color` | Text/label color | `color:#fff` |
| `stroke` | Border color | `stroke:#1e40af` |
| `stroke-width` | Border thickness | `stroke-width:2px` |
| `stroke-dasharray` | Dashed borders | `stroke-dasharray:5 5` |
| `font-weight` | Text weight | `font-weight:bold` |
| `font-size` | Text size | `font-size:14px` |

**Format rule**: Mermaid only recognizes hex colors (`#rrggbb` or `#rrggbbaa`), not
named colors. Named colors (e.g., `red`, `blue`) work in some renderers but fail in
others. Always use hex.

---

## 2. HSL-Based Color Encoding System

### Theory: Three Visual Channels

Color has three perceptual dimensions that can encode different data types:

| Channel | Encodes | Perception |
|---------|---------|------------|
| **Hue** (H) | Category/type (nominal) | "What kind?" -- no inherent order |
| **Saturation** (S) | Importance/prominence (ordinal) | Higher = more important |
| **Lightness** (L) | Rank/depth within category (ordinal) | Darker = primary/deeper |

### Mapping to Diagram Roles

Assign each **category** (input, process, output, storage, external) a distinct
**hue family**. Within each family, vary saturation and lightness to encode
**prominence** (primary vs. secondary vs. background):

```
Category        Hue Family     Primary (high-S, low-L)    Secondary (mid-S, mid-L)    Background (low-S, high-L)
-------         ----------     -----------------------    ------------------------    --------------------------
Input/Source    Blue (210-220)  hsl(217, 91%, 60%)         hsl(217, 60%, 68%)          hsl(217, 30%, 85%)
Process/Logic   Violet (270)    hsl(271, 81%, 56%)         hsl(271, 55%, 68%)          hsl(271, 30%, 85%)
Output/Sink     Emerald (160)   hsl(160, 84%, 39%)         hsl(160, 55%, 55%)          hsl(160, 25%, 82%)
Storage/Data    Amber (38-45)   hsl(38, 92%, 50%)          hsl(38, 65%, 62%)           hsl(38, 30%, 85%)
Error/Danger    Red (0-4)       hsl(0, 84%, 60%)           hsl(0, 60%, 68%)            hsl(0, 30%, 85%)
External/API    Slate (215)     hsl(215, 14%, 34%)         hsl(215, 14%, 50%)          hsl(215, 14%, 75%)
```

### Converting to Hex for classDef

HSL values must be converted to hex for Mermaid. The Tailwind CSS palette provides
pre-converted values that follow this HSL progression naturally. Throughout this
document, all hex values are sourced from Tailwind v3 for consistency.

---

## 3. Light Mode + Dark Mode Safety

### The Core Problem

Mermaid's default `color` (text) changes with the active theme:
- **Light theme**: dark text on light backgrounds
- **Dark theme**: light text on dark backgrounds

When you set a custom `fill:` without setting `color:`, the theme's default text
color may clash with your chosen background. A dark fill + dark default text (light
mode) or a light fill + light default text (dark mode) becomes unreadable.

### The Rule: Always Pair `fill:` with `color:`

Never rely on the theme's default text color. Every `classDef` should explicitly
declare both `fill` and `color`:

```
%% WRONG -- text color depends on theme, may become invisible
classDef bad fill:#1e40af

%% CORRECT -- explicit text color, safe in any theme
classDef good fill:#1e40af,color:#fff,stroke:#1e3a8a
```

### Safe Background + Text Pairings

**Dark backgrounds with white text** (works in both themes):

| Fill | Stroke | Color | Notes |
|------|--------|-------|-------|
| `#1e40af` (blue-800) | `#1e3a8a` (blue-900) | `#fff` | Deep blue, high contrast |
| `#2563eb` (blue-600) | `#1e40af` (blue-800) | `#fff` | Medium blue, vivid |
| `#047857` (emerald-700) | `#065f46` | `#fff` | Forest green |
| `#b91c1c` (red-700) | `#991b1b` | `#fff` | Deep red |
| `#7c3aed` (violet-600) | `#6d28d9` (violet-700) | `#fff` | Purple |
| `#334155` (slate-700) | `#1e293b` (slate-800) | `#fff` | Neutral dark |

**Light backgrounds with dark text** (works in both themes):

| Fill | Stroke | Color | Notes |
|------|--------|-------|-------|
| `#dbeafe` (blue-100) | `#3b82f6` (blue-500) | `#1e293b` | Pale blue |
| `#d1fae5` (emerald-100) | `#10b981` (emerald-500) | `#1e293b` | Pale green |
| `#fef3c7` (amber-100) | `#f59e0b` (amber-500) | `#1e293b` | Pale amber |
| `#fecaca` (red-100) | `#ef4444` (red-500) | `#1e293b` | Pale red |
| `#f1f5f9` (slate-100) | `#94a3b8` (slate-400) | `#1e293b` | Neutral light |

**The "safe middle ground" range**: Fill colors in the 400-600 Tailwind shade range
with `color:#fff` maintain readable contrast in both light and dark themes. Shades
lighter than 300 need `color:#1e293b` (dark text). Shades darker than 700 always
work with `color:#fff`.

### WCAG Contrast Minimums

- **Normal text on fill**: 4.5:1 contrast ratio minimum (WCAG AA)
- **Large text (18px+ or 14px bold)**: 3:1 minimum
- **Non-text elements** (borders, icons): 3:1 against adjacent colors

White (`#fff`) on `#2563eb` (blue-600) = ~4.6:1 -- passes AA.
White (`#fff`) on `#3b82f6` (blue-500) = ~3.1:1 -- fails AA for normal text.
Dark (`#1e293b`) on `#93c5fd` (blue-300) = ~5.2:1 -- passes AA.

**Rule of thumb**: For white text, use Tailwind shade 600+ fills. For dark text,
use Tailwind shade 300 or lighter fills.

---

## 4. Visual Hierarchy Techniques

### Prominent vs. Background Elements

The key to information-dense diagrams is making primary flow elements "pop" while
supporting elements recede:

```mermaid
flowchart LR
    A[Primary Source]:::primary --> B[Core Process]:::primary --> C[Primary Output]:::primary
    D[Config]:::secondary -.-> B
    E[Logs]:::tertiary -.-> F[Archive]:::tertiary

    classDef primary   fill:#2563eb,stroke:#1e40af,color:#fff,stroke-width:2px
    classDef secondary fill:#93c5fd,stroke:#3b82f6,color:#1e293b,stroke-width:1px
    classDef tertiary  fill:#dbeafe,stroke:#93c5fd,color:#475569,stroke-width:1px,stroke-dasharray:5 5
```

### Emphasis Channels Beyond Color

| Technique | Effect | classDef syntax |
|-----------|--------|-----------------|
| Thick border | Draws eye to node | `stroke-width:3px` |
| Thin border | Node recedes | `stroke-width:1px` |
| Dashed border | "Optional" or "async" | `stroke-dasharray:5 5` |
| Bold text | Emphasizes label | `font-weight:bold` |
| Larger text | Heading nodes | `font-size:16px` |

### Three-Tier Hierarchy Pattern

Every category should have three tiers:

```
classDef bluePrimary   fill:#2563eb,stroke:#1e40af,color:#fff,stroke-width:2px,font-weight:bold
classDef blueSecondary fill:#93c5fd,stroke:#3b82f6,color:#1e293b,stroke-width:1px
classDef blueTertiary  fill:#dbeafe,stroke:#93c5fd,color:#475569,stroke-width:1px,stroke-dasharray:5 5
```

| Tier | Fill shade | Stroke shade | Text | Border | Use for |
|------|-----------|-------------|------|--------|---------|
| Primary | 600 | 800 | `#fff` | 2px solid | Main flow nodes |
| Secondary | 300 | 500 | `#1e293b` | 1px solid | Supporting nodes |
| Tertiary | 100 | 300 | `#475569` | 1px dashed | Background/config nodes |

---

## 5. Subgraph Coloring

### Method 1: classDef + class (recommended)

```mermaid
flowchart LR
    subgraph ingress["Ingress Layer"]
        A[CDN] --> B[Load Balancer]
    end
    subgraph compute["Compute Layer"]
        C[Service A] --> D[Service B]
    end
    B --> C

    classDef sgBlue   fill:#dbeafe,stroke:#3b82f6,color:#1e293b
    classDef sgGreen  fill:#d1fae5,stroke:#10b981,color:#1e293b

    class ingress sgBlue
    class compute sgGreen
```

### Method 2: Direct `style` directive

```
style ingress fill:#dbeafe,stroke:#3b82f6,color:#1e293b
style compute fill:#d1fae5,stroke:#10b981,color:#1e293b
```

### Method 3: Transparent backgrounds via 8-digit hex

The last two hex digits control alpha/opacity. `00` = fully transparent, `ff` = fully
opaque. Intermediate values create semi-transparent overlays:

```
classDef sgTransparent fill:#3b82f620,stroke:#3b82f6,color:#1e293b
%%                              ^^ 20 = ~12% opacity -- very subtle tint
```

| Alpha suffix | Opacity | Use case |
|-------------|---------|----------|
| `00` | 0% | Invisible background (border only) |
| `10` | ~6% | Barely visible tint |
| `20` | ~12% | Subtle grouping hint |
| `33` | 20% | Light wash, good default |
| `66` | 40% | Visible but nodes still prominent |
| `99` | 60% | Strong tint, may overwhelm nodes |
| `ff` | 100% | Fully opaque (default) |

### Subgraph Best Practices

1. **Use pastel/light fills** -- shade 50-200 range or semi-transparent. Subgraph
   backgrounds should never compete with node fills for attention.

2. **Match stroke to the category hue** -- e.g., blue subgraph border with blue-500
   stroke while interior nodes use blue-600 fills.

3. **Subgraph label color** -- the `color` property in a subgraph classDef controls
   the subgraph title text. Use `#1e293b` (dark) for light subgraph fills or `#fff`
   for the rare dark subgraph fill.

4. **Invisible subgraph for pure grouping** (no visual border):
   ```
   classDef sgInvisible fill:#00000000,stroke-width:0
   class mySubgraph sgInvisible
   ```

---

## 6. Color Palette Recipes

All palettes below use Tailwind v3 hex values. Each includes primary (dark fill,
white text), secondary (light fill, dark text), and subgraph variants.

### Recipe A: Software Architecture (Cool Tones)

For layered architecture, microservices, deployment diagrams.

```
%% --- Architecture palette: blue/violet/teal/slate ---

%% Entrypoint / Ingress (Blue family)
classDef ingressPrimary    fill:#2563eb,stroke:#1e40af,color:#fff,stroke-width:2px
classDef ingressSecondary  fill:#93c5fd,stroke:#3b82f6,color:#1e293b,stroke-width:1px
classDef sgIngress         fill:#dbeafe,stroke:#3b82f6,color:#1e293b

%% Business Logic / Compute (Violet family)
classDef computePrimary    fill:#7c3aed,stroke:#6d28d9,color:#fff,stroke-width:2px
classDef computeSecondary  fill:#c4b5fd,stroke:#8b5cf6,color:#1e293b,stroke-width:1px
classDef sgCompute         fill:#ede9fe,stroke:#8b5cf6,color:#1e293b

%% Data / Storage (Teal family)
classDef dataPrimary       fill:#0d9488,stroke:#0f766e,color:#fff,stroke-width:2px
classDef dataSecondary     fill:#99f6e4,stroke:#14b8a6,color:#1e293b,stroke-width:1px
classDef sgData            fill:#ccfbf1,stroke:#14b8a6,color:#1e293b

%% External / Infrastructure (Slate family)
classDef infraPrimary      fill:#475569,stroke:#334155,color:#fff,stroke-width:2px
classDef infraSecondary    fill:#cbd5e1,stroke:#64748b,color:#1e293b,stroke-width:1px
classDef sgInfra           fill:#f1f5f9,stroke:#94a3b8,color:#334155

%% Accent: Danger / Alert
classDef danger            fill:#dc2626,stroke:#b91c1c,color:#fff,stroke-width:2px
%% Accent: Success / Healthy
classDef success           fill:#059669,stroke:#047857,color:#fff,stroke-width:2px
```

### Recipe B: Data Flow / ETL Pipeline (Warm Tones)

For data pipelines, ETL, stream processing, ML workflows.

```
%% --- Data Flow palette: amber/orange/emerald/indigo ---

%% Source / Input (Amber family)
classDef sourcePrimary     fill:#d97706,stroke:#b45309,color:#fff,stroke-width:2px
classDef sourceSecondary   fill:#fde68a,stroke:#f59e0b,color:#1e293b,stroke-width:1px
classDef sgSource          fill:#fef3c7,stroke:#f59e0b,color:#1e293b

%% Transform / Process (Orange family)
classDef transformPrimary  fill:#ea580c,stroke:#c2410c,color:#fff,stroke-width:2px
classDef transformSecondary fill:#fed7aa,stroke:#f97316,color:#1e293b,stroke-width:1px
classDef sgTransform       fill:#fff7ed,stroke:#f97316,color:#1e293b

%% Load / Output (Emerald family)
classDef loadPrimary       fill:#059669,stroke:#047857,color:#fff,stroke-width:2px
classDef loadSecondary     fill:#a7f3d0,stroke:#10b981,color:#1e293b,stroke-width:1px
classDef sgLoad            fill:#d1fae5,stroke:#10b981,color:#1e293b

%% Orchestration / Control (Indigo family)
classDef orchPrimary       fill:#4f46e5,stroke:#4338ca,color:#fff,stroke-width:2px
classDef orchSecondary     fill:#c7d2fe,stroke:#6366f1,color:#1e293b,stroke-width:1px
classDef sgOrch            fill:#e0e7ff,stroke:#6366f1,color:#1e293b

%% Accent: Failed / Error
classDef error             fill:#dc2626,stroke:#b91c1c,color:#fff,stroke-width:2px
%% Accent: Warning / Slow
classDef warning           fill:#f59e0b,stroke:#d97706,color:#1e293b,stroke-width:2px
```

### Recipe C: State / Workflow Diagram (Semantic Colors)

For state machines, CI/CD pipelines, approval workflows.

```
%% --- Workflow palette: semantic roles ---

%% Start / Entry state (Green family)
classDef stateStart        fill:#059669,stroke:#047857,color:#fff,stroke-width:2px
classDef stateStartLight   fill:#d1fae5,stroke:#10b981,color:#1e293b,stroke-width:1px

%% In-Progress / Active (Blue family)
classDef stateActive       fill:#2563eb,stroke:#1e40af,color:#fff,stroke-width:2px
classDef stateActiveLight  fill:#dbeafe,stroke:#3b82f6,color:#1e293b,stroke-width:1px

%% Review / Waiting (Amber family)
classDef stateWaiting      fill:#d97706,stroke:#b45309,color:#fff,stroke-width:2px
classDef stateWaitingLight fill:#fef3c7,stroke:#f59e0b,color:#1e293b,stroke-width:1px

%% End / Complete (Slate family)
classDef stateEnd          fill:#475569,stroke:#334155,color:#fff,stroke-width:2px
classDef stateEndLight     fill:#e2e8f0,stroke:#64748b,color:#1e293b,stroke-width:1px

%% Error / Rejected (Red family)
classDef stateError        fill:#dc2626,stroke:#b91c1c,color:#fff,stroke-width:2px
classDef stateErrorLight   fill:#fecaca,stroke:#ef4444,color:#1e293b,stroke-width:1px

%% Cancelled / Skipped (Zinc family -- true neutral)
classDef stateSkipped      fill:#3f3f46,stroke:#27272a,color:#fff,stroke-width:1px,stroke-dasharray:5 5
classDef stateSkippedLight fill:#e4e4e7,stroke:#a1a1aa,color:#52525b,stroke-width:1px,stroke-dasharray:5 5
```

### Recipe D: High-Density Knowledge Graph (Maximum Distinction)

For ER diagrams, knowledge graphs, ontologies with many entity types.

```
%% --- Knowledge Graph palette: 8 maximally distinct hues ---

classDef kgPerson          fill:#2563eb,stroke:#1e40af,color:#fff,stroke-width:2px
classDef kgOrganization    fill:#7c3aed,stroke:#6d28d9,color:#fff,stroke-width:2px
classDef kgLocation        fill:#059669,stroke:#047857,color:#fff,stroke-width:2px
classDef kgEvent           fill:#ea580c,stroke:#c2410c,color:#fff,stroke-width:2px
classDef kgDocument        fill:#0891b2,stroke:#0e7490,color:#fff,stroke-width:2px
classDef kgConcept         fill:#d97706,stroke:#b45309,color:#fff,stroke-width:2px
classDef kgProduct         fill:#e11d48,stroke:#be123c,color:#fff,stroke-width:2px
classDef kgTechnology      fill:#475569,stroke:#334155,color:#fff,stroke-width:2px

%% Lighter variants for secondary/mention nodes
classDef kgPersonLight     fill:#dbeafe,stroke:#3b82f6,color:#1e293b,stroke-width:1px
classDef kgOrgLight        fill:#ede9fe,stroke:#8b5cf6,color:#1e293b,stroke-width:1px
classDef kgLocationLight   fill:#d1fae5,stroke:#10b981,color:#1e293b,stroke-width:1px
classDef kgEventLight      fill:#fff7ed,stroke:#f97316,color:#1e293b,stroke-width:1px
classDef kgDocumentLight   fill:#cffafe,stroke:#06b6d4,color:#1e293b,stroke-width:1px
classDef kgConceptLight    fill:#fef3c7,stroke:#f59e0b,color:#1e293b,stroke-width:1px
classDef kgProductLight    fill:#ffe4e6,stroke:#f43f5e,color:#1e293b,stroke-width:1px
classDef kgTechLight       fill:#f1f5f9,stroke:#94a3b8,color:#334155,stroke-width:1px

%% Relation edge (use linkStyle for edges)
%% linkStyle default stroke:#64748b,stroke-width:1px
```

---

## 7. Complete Worked Example

A software architecture diagram using Recipe A:

```mermaid
flowchart LR
    subgraph ingress["Ingress"]
        cdn["CDN"]:::ingressPrimary
        lb["Load Balancer"]:::ingressSecondary
    end
    subgraph compute["Services"]
        api["API Gateway"]:::computePrimary
        worker["Worker"]:::computePrimary
        cache["Cache"]:::computeSecondary
    end
    subgraph data["Storage"]
        db[("Primary DB")]:::dataPrimary
        replica[("Read Replica")]:::dataSecondary
    end
    monitor["Monitoring"]:::infraSecondary

    cdn --> lb --> api
    api --> worker
    api --> cache --> db
    worker --> db
    db --> replica
    api -.-> monitor
    worker -.-> monitor

    classDef ingressPrimary    fill:#2563eb,stroke:#1e40af,color:#fff,stroke-width:2px
    classDef ingressSecondary  fill:#93c5fd,stroke:#3b82f6,color:#1e293b,stroke-width:1px
    classDef computePrimary    fill:#7c3aed,stroke:#6d28d9,color:#fff,stroke-width:2px
    classDef computeSecondary  fill:#c4b5fd,stroke:#8b5cf6,color:#1e293b,stroke-width:1px
    classDef dataPrimary       fill:#0d9488,stroke:#0f766e,color:#fff,stroke-width:2px
    classDef dataSecondary     fill:#99f6e4,stroke:#14b8a6,color:#1e293b,stroke-width:1px
    classDef infraSecondary    fill:#cbd5e1,stroke:#64748b,color:#1e293b,stroke-width:1px

    classDef sgBlue   fill:#dbeafe,stroke:#3b82f6,color:#1e293b
    classDef sgViolet fill:#ede9fe,stroke:#8b5cf6,color:#1e293b
    classDef sgTeal   fill:#ccfbf1,stroke:#14b8a6,color:#1e293b

    class ingress sgBlue
    class compute sgViolet
    class data sgTeal
```

---

## 8. Gotchas and Renderer Differences

### GitHub Markdown Rendering

- GitHub synchronizes Mermaid light/dark theme with the user's GitHub appearance
  setting. Custom `fill:` colors are static and do not adapt.
- **All Mermaid themes have contrast issues on GitHub**. The safest approach is to
  always set explicit `color:` on every `classDef` rather than relying on the theme.
- GitHub renders Mermaid inside iframes. External CSS cannot reach the diagram.
- Arrow colors default to dark gray in the "default" theme, which vanishes against
  GitHub's dark background. Avoid relying on edge visibility without `linkStyle`.

### VS Code Preview

- The `markdown-mermaid` extension allows separate theme configuration for VS Code
  light and dark modes (unlike GitHub, which auto-detects).
- Colors render identically to the Mermaid Live Editor in most cases.
- `htmlLabels: true` may be needed in some VS Code setups for `classDef` `color:`
  to apply correctly (especially in Quarto documents).

### mmdc (CLI)

- `mmdc` uses Puppeteer for headless rendering. Output closely matches browser
  rendering but is a static snapshot.
- Use `-t dark -b transparent` for dark-theme PNGs, `-t default -b white` for
  light-theme PNGs. Render both variants to verify colors.
- Long labels and wide diagrams are more likely to clip or wrap incorrectly in
  mmdc than in browser-based previews.

### Obsidian

- Obsidian uses its own Mermaid integration. `classDef` `color:` (text color)
  has historically had issues with dark mode. Always verify if text remains
  readable after theme changes.

### General Cross-Renderer Rules

1. **Only use hex colors** (`#rrggbb` or `#rrggbbaa`). Named colors (`red`, `blue`)
   may work in some renderers but silently fail in others.
2. **Always pair `fill:` with `color:`**. Never rely on theme-default text color.
3. **Test in both light and dark themes** before committing. Render with
   `mmdc -t default -b white` AND `mmdc -t dark -b transparent`.
4. **`stroke-dasharray` uses spaces, not commas** -- commas are property delimiters
   in classDef. Use `stroke-dasharray:5 5` not `stroke-dasharray:5,5`.
5. **8-digit hex opacity** (`#rrggbbaa`) works in modern Mermaid for transparent
   subgraph fills but may not render correctly in older integrations.
6. **Subgraph classDef** was fixed in Mermaid PR #1245 (Feb 2020) and PR #1730
   (Oct 2020). Older Mermaid versions (pre-8.9) may not support it. Use the `style`
   directive as a fallback for ancient renderers.

---

## 9. Tailwind v3 Hex Reference (Subset for Diagrams)

Quick lookup for the hex values used throughout this document.

| Tailwind class | Hex | Typical role |
|---------------|-----|-------------|
| blue-100 | `#dbeafe` | Subgraph fill, tertiary node |
| blue-300 | `#93c5fd` | Secondary node fill |
| blue-500 | `#3b82f6` | Stroke, accent |
| blue-600 | `#2563eb` | Primary node fill |
| blue-800 | `#1e40af` | Primary stroke |
| blue-900 | `#1e3a8a` | Deep stroke |
| violet-100 | `#ede9fe` | Subgraph fill |
| violet-300 | `#c4b5fd` | Secondary fill |
| violet-500 | `#8b5cf6` | Stroke |
| violet-600 | `#7c3aed` | Primary fill |
| violet-700 | `#6d28d9` | Primary stroke |
| emerald-100 | `#d1fae5` | Subgraph fill |
| emerald-300 | `#6ee7b7` | Secondary fill |
| emerald-500 | `#10b981` | Stroke |
| emerald-600 | `#059669` | Primary fill |
| emerald-700 | `#047857` | Primary stroke |
| teal-100 | `#ccfbf1` | Subgraph fill |
| teal-300 | `#5eead4` | Secondary fill |
| teal-500 | `#14b8a6` | Stroke |
| teal-600 | `#0d9488` | Primary fill |
| amber-100 | `#fef3c7` | Subgraph fill |
| amber-300 | `#fcd34d` | Secondary fill |
| amber-500 | `#f59e0b` | Stroke, warning accent |
| amber-600 | `#d97706` | Primary fill |
| orange-100 | `#fff7ed` | Subgraph fill |
| orange-300 | `#fdba74` | Secondary fill |
| orange-500 | `#f97316` | Stroke |
| orange-600 | `#ea580c` | Primary fill |
| red-100 | `#fee2e2` | Error subgraph fill |
| red-200 | `#fecaca` | Error secondary fill |
| red-500 | `#ef4444` | Error stroke |
| red-600 | `#dc2626` | Error primary fill |
| red-700 | `#b91c1c` | Error stroke |
| indigo-100 | `#e0e7ff` | Subgraph fill |
| indigo-500 | `#6366f1` | Stroke |
| indigo-600 | `#4f46e5` | Primary fill |
| cyan-100 | `#cffafe` | Subgraph fill |
| cyan-500 | `#06b6d4` | Stroke |
| cyan-600 | `#0891b2` | Primary fill |
| rose-500 | `#f43f5e` | Stroke |
| rose-600 | `#e11d48` | Primary fill |
| slate-100 | `#f1f5f9` | Neutral subgraph fill |
| slate-200 | `#e2e8f0` | Neutral secondary fill |
| slate-300 | `#cbd5e1` | Neutral secondary fill |
| slate-400 | `#94a3b8` | Neutral stroke, muted text |
| slate-500 | `#64748b` | Neutral stroke |
| slate-600 | `#475569` | Neutral primary fill |
| slate-700 | `#334155` | Neutral primary stroke |
| slate-800 | `#1e293b` | Dark text color, deep fill |
| slate-900 | `#0f172a` | Deepest neutral |
| zinc-100 | `#f4f4f5` | True-neutral light fill |
| zinc-200 | `#e4e4e7` | True-neutral secondary |
| zinc-700 | `#3f3f46` | True-neutral dark fill |
| zinc-800 | `#27272a` | True-neutral deep fill |
| zinc-900 | `#18181b` | True-neutral darkest |

Standard text colors used in all palettes:
- White text: `#fff`
- Dark text: `#1e293b` (slate-800)
- Muted text: `#475569` (slate-600)

---

## 10. linkStyle for Edge Coloring

Edges (arrows/connections) can be styled by index or as defaults:

```
%% Style a single edge (0-indexed, in order of appearance)
linkStyle 0 stroke:#3b82f6,stroke-width:2px

%% Style multiple edges
linkStyle 1,2,5 stroke:#ef4444,stroke-width:2px

%% Style all edges (default)
linkStyle default stroke:#94a3b8,stroke-width:1px
```

For visual hierarchy, make primary-flow edges thicker and colored, while
secondary/monitoring edges are thinner and gray:

```
%% Primary data flow (thick, colored)
linkStyle 0,1,2 stroke:#2563eb,stroke-width:2px

%% Secondary/monitoring edges (thin, muted)
linkStyle 3,4 stroke:#94a3b8,stroke-width:1px
```

---

## Sources

Research compiled from:
- [Mermaid Theme Configuration](https://mermaid.js.org/config/theming.html)
- [Mermaid Flowchart Syntax](https://mermaid.ai/open-source/syntax/flowchart.html)
- [beautiful-mermaid library](https://github.com/lukilabs/beautiful-mermaid) -- CSS `color-mix()` derivation system
- [Mermaid GitHub dark mode discussion](https://github.com/orgs/community/discussions/35733)
- [Accessible Mermaid Charts in GitHub](https://pulibrary.github.io/2023-03-29-accessible-mermaid)
- [Tailwind CSS v3 Colors](https://v3.tailwindcss.com/docs/customizing-colors)
- [WCAG Contrast Requirements](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html)
- [Data Visualization Color Palettes Guide](https://www.datylon.com/blog/a-guide-to-data-visualization-color-palette)
- [Perceptually Uniform Color Spaces](https://programmingdesignsystems.com/color/perceptually-uniform-color-spaces/)
