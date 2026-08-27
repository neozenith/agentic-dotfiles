# Mermaid.JS Diagram Reference for Discovery Documents

Quick reference for writing and validating the Mermaid lens diagrams embedded in discovery
markdown files. Distilled from the full `/mermaidjs-diagrams` skill.

## Rendering and Verification

mmdc exits non-zero if any mermaid fence fails to render. Use this as a validation gate.

```bash
INPUT="path/to/document.md"
INPUT_PATH="path/to/"
OUTPUT_BASE=".mmdc_cache"

# Variant 1: dark + transparent + PNG (default)
OUTPUT_FORMAT="png"
THEME=dark
BGCOLOR=transparent
VARIANT="${THEME}_${BGCOLOR}_${OUTPUT_FORMAT}"
OUTPUT_TARGET="${OUTPUT_BASE}/${VARIANT}/${INPUT_PATH}/"
OUTPUT="${OUTPUT_BASE}/${VARIANT}/${INPUT}"
npx -p @mermaid-js/mermaid-cli mmdc \
  -i "${INPUT}" \
  -a "${OUTPUT_TARGET}" \
  -o "${OUTPUT}" \
  --scale 4 -e "${OUTPUT_FORMAT}" -t "${THEME}" -b "${BGCOLOR}"

# Variant 2: default + white + PNG (for README, light-mode docs)
OUTPUT_FORMAT="png"
THEME=default
BGCOLOR=white
VARIANT="${THEME}_${BGCOLOR}_${OUTPUT_FORMAT}"
OUTPUT_TARGET="${OUTPUT_BASE}/${VARIANT}/${INPUT_PATH}/"
OUTPUT="${OUTPUT_BASE}/${VARIANT}/${INPUT}"
npx -p @mermaid-js/mermaid-cli mmdc \
  -i "${INPUT}" \
  -a "${OUTPUT_TARGET}" \
  -o "${OUTPUT}" \
  --scale 4 -e "${OUTPUT_FORMAT}" -t "${THEME}" -b "${BGCOLOR}"
```

**Exit code 0** = all diagrams valid. **Non-zero** = error on stderr with the offending fence.

## Choosing a Diagram Type

| Type | Best for | Notes |
|------|----------|-------|
| `flowchart LR` | Architecture, data flow, dependency graphs | Handles fan-out well, supports subgraphs |
| `flowchart TD` | Hierarchical/layered views | Top-down layout |
| `sequenceDiagram` | Interaction flows, API calls | Time-ordered message passing |
| `stateDiagram-v2` | State machines, workflows | Transitions and conditions |
| `architecture-beta` | Brand-logo diagrams, simple linear chains | Strict layout rules (see pitfalls) |

**Default choice: `flowchart LR`** — it's the most versatile and handles the complex topology
typical of current-vs-desired state comparisons.

## Common Pitfalls

### Multiline text in node labels

**`\n` does NOT work** — renders as garbled characters. Use `<br/>` instead:

```mermaid
flowchart LR
    A["Line one<br/>Line two"]
```

For Mermaid v10.7+, markdown strings with real newlines also work:
```mermaid
flowchart LR
    A["`**Phase 1**
    Creates output tables`"]
```

`<br/>` does NOT work in subgraph labels or erDiagram — use short single-line titles.

### Unicode in node labels

Characters like U+21B3 (↳), U+2192 (→), U+00B7 (·) cause rendering failures in mmdc
even when they display correctly in browser previews. **Stick to ASCII-only text** in
node labels.

### architecture-beta edge rules

These are critical — violations produce silent failures (exit code 0, but error-bomb PNG):

1. **Edges MUST have labels.** `A:R -[label]-> L:B` works. `A:R --> L:B` silently fails.
2. **Direction goes BEFORE the rhs node id.** `A:R -[label]-> L:B` ✓ `A:R -[label]-> B:L` ✗
3. **One outgoing `R` edge per node.** Fan-out (one node → multiple `R` targets) causes
   collapsed/overlapping layout. Design as strict linear chains.
4. **`--iconPacks` required for CLI rendering.** Icons are not bundled. Pass
   `--iconPacks @iconify-json/logos @iconify-json/mdi` to mmdc.
5. **Only real npm packages work with `--iconPacks`.** The mechanism fetches from unpkg.com
   inside Puppeteer. Non-existent packages fail silently (empty icon boxes, exit code 0).

### Flowchart with Font Awesome icons

Flowchart diagrams using `fa:fa-icon` syntax need no `--iconPacks` flag:

```mermaid
flowchart LR
    A["fa:fa-server Current System"]
    B["fa:fa-cloud Desired System"]
    A -->|migrate| B
```

## Variant Quick Reference

| Variant | Flags | Best For |
|---------|-------|----------|
| `dark_transparent_png` | `-e png -t dark -b transparent` | Dark UIs, slides (default) |
| `default_white_png` | `-e png -t default -b white` | README, light docs, print |
| `dark_transparent_svg` | `-e svg -t dark -b transparent` | Scalable dark docs |
| `default_white_svg` | `-e svg -t default -b white` | Scalable light docs |

## Lens Menu

Current State and Desired State each pick **2–3 lenses** from this menu — only the ones that
genuinely illuminate the initiative (do not force a lens that adds no signal). Use the **same**
lenses for Current and Desired so each pair reads as a before/after.

| Lens | Shows | Recommended type | Pick when |
|------|-------|------------------|-----------|
| **Component** | Modules/services and their boundaries | `flowchart TD` | The change reshapes structure or ownership |
| **Data-flow** | How data moves through the system | `flowchart LR` | The change is about a pipeline or transform |
| **Sequence** | Time-ordered interaction between actors | `sequenceDiagram` | The change alters a call/handshake order |
| **Deployment** | Runtime/process/host topology | `flowchart TD` | The change moves where things run |
| **State** | Lifecycle states and transitions | `stateDiagram-v2` | The change adds/reorders states or modes |
| **Entity** | Schema / data model relationships | `erDiagram` | The change touches tables, columns, or keys |

**Reuse node IDs between each Current/Desired pair** so the reader can visually diff what
changed, what was added, and what was removed.

## Color Theming

### Critical Rules

1. **Always pair `fill:` with explicit `color:`** — Mermaid's default text color changes
   between light and dark themes. Without explicit `color:`, white text on a dark fill
   becomes invisible in light mode (or vice versa).

2. **Use hex colors only** — `#rrggbb` or `#rrggbbaa`. Named colors (`red`, `blue`)
   fail silently in some renderers (mmdc, GitHub).

3. **WCAG contrast** — white text (`#fff`) needs fill at Tailwind shade 600+ for AA
   compliance (4.5:1 ratio). Example: `#3b82f6` (blue-500) only achieves 3.1:1 — use
   `#2563eb` (blue-600, 4.6:1) or darker.

### HSL Encoding Channels

| Channel | Encodes | Example |
|---------|---------|---------|
| **Hue** | Category (nominal) | Blue=input, green=output, purple=process |
| **Saturation** | Importance (ordinal) | High=primary element, low=background |
| **Lightness** | Rank within category (ordinal) | Dark=primary, light=secondary |

### Discovery Palette

Recommended `classDef` declarations for discovery documents. Current and Desired each get a
distinct hue; role fills mark what a node *means* inside a state. Primary nodes use shade 600+
fills with white/near-white text; subgraph backgrounds use 8-digit hex with low alpha
(`22` = ~13% opacity).

```
%% State hues — one per discovery section
classDef csStyle   fill:#b45309,stroke:#92400e,color:#fef3c7,stroke-width:2px  %% Current State: amber
classDef dsStyle   fill:#047857,stroke:#065f46,color:#d1fae5,stroke-width:2px  %% Desired State: emerald

%% Role fills — what a node means within a state
classDef baseline  fill:#334155,stroke:#1e293b,color:#e2e8f0,stroke-width:1px  %% unchanged node: slate
classDef danger    fill:#b91c1c,stroke:#991b1b,color:#fee2e2,stroke-width:2px  %% problem area (Current): red
classDef process   fill:#6d28d9,stroke:#5b21b6,color:#ede9fe,stroke-width:2px  %% changed node (Desired): violet
classDef good      fill:#166534,stroke:#14532d,color:#dcfce7,stroke-width:2px  %% new node (Desired): green

%% Subgraph backgrounds — low alpha so nodes remain readable
style CS fill:#92400e22,stroke:#b45309,color:#fbbf24
style DS fill:#065f4622,stroke:#047857,color:#34d399
```

### Three-Tier Hierarchy Per Category

Within a single hue family, vary fill darkness and stroke to encode importance:

| Tier | Fill | Text | Stroke | Use |
|------|------|------|--------|-----|
| **Primary** | Shade 600-800 | `#fff` | 2px solid, shade 800-900 | Key nodes, decisions |
| **Secondary** | Shade 300-400 | `#1e293b` | 1px solid, shade 500 | Supporting detail |
| **Background** | Shade 50-100 or `#xxxxxx22` | Shade 400-500 | 1px dashed, shade 200 | Subgraphs, grouping |

### Gotchas

- `stroke-dasharray` uses **spaces** not commas: `stroke-dasharray:5 5` (commas are
  `classDef` property delimiters)
- GitHub dark mode: default Mermaid theme arrows can vanish; custom `linkStyle` with
  explicit color helps
- Subgraph label color comes from the `color:` in the `style` directive, not from
  `classDef` — set it explicitly for each subgraph
