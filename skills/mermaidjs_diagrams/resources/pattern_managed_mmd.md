# Pattern: Managed `.mmd` Files

Maintain a dedicated collection of standalone `.mmd` diagram source files with
Makefile-based batch rendering, complexity analysis, and dual-density management.

## B1. Setup Infrastructure (one-time)

Run the setup script to create the diagram directory with Makefile and supporting files:

```bash
uv run .claude/skills/mermaidjs_diagrams/scripts/setup_diagrams.py
```

This creates:
- `docs/diagrams/` directory
- `docs/diagrams/Makefile` (with proper tabs for batch `.mmd` to `.png` rendering)
- `docs/diagrams/.gitattributes`
- `docs/diagrams/README.md`

To target a different directory:
```bash
uv run .claude/skills/mermaidjs_diagrams/scripts/setup_diagrams.py --target-folder path/to/diagrams
```

## B2. Identify Diagram Lenses

Before creating diagrams, identify the key **lenses** (perspectives/views) needed:

| Lens | Purpose | Typical Content |
|------|---------|-----------------|
| `architecture` | System structure | Components, services, modules |
| `data-flow` | Information movement | Data paths, transformations |
| `deployment` | Infrastructure | Servers, containers, cloud services |
| `security` | Trust boundaries | Auth flows, encryption, access control |
| `sequence` | Interactions | API calls, user flows, processes |
| `state` | State machines | Statuses, transitions, workflows |

### File Organization Pattern

**Naming Convention**: `{lens}--[{subsystem}--]{scope}.mmd`
- `{lens}`: architecture, data-flow, deployment, security, sequence, state
- `{subsystem}`: Optional subsystem focus
- `{scope}`: overview (low-density), detail (high-density)
- `--`: separator (allows multiword lens/subsystem like `data-flow`)

```
docs/diagrams/
├── architecture--overview.mmd        # Low-density bird's eye view
├── architecture--detail.mmd          # High-density full system
├── architecture--api--detail.mmd     # High-density subsystem focus
├── data-flow--overview.mmd           # Low-density data paths
├── data-flow--detail.mmd             # High-density transformations
├── deployment--overview.mmd          # Low-density infrastructure
├── security--overview.mmd            # Low-density trust boundaries
└── sequence--auth--detail.mmd        # Specific interaction flow
```

## B3. Analyze Existing Diagram Complexity

**BEFORE updating any diagrams**, run the complexity analyzer:

```bash
# Default analysis (high-density preset)
uv run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/

# With detailed calculation breakdown
uv run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/ --show-working

# Analyze by density level
uv run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/*--overview.mmd --preset low
uv run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/*--detail.mmd --preset high
```

### Output Includes:

- Visual Complexity Score (VCS) for each diagram
- Node and edge counts with threshold comparisons
- Rating: ideal / acceptable / complex / critical
- Subdivision recommendations with step-by-step calculation (`--show-working`)

### Density Presets

| Preset | Nodes (acceptable/complex) | VCS (acceptable/complex) | Use Case |
|--------|---------------------------|-------------------------|----------|
| `low-density` (low/l) | <=12 / <=20 | <=25 / <=40 | Overview diagrams |
| `medium-density` (med/m) | <=20 / <=35 | <=40 / <=70 | README diagrams |
| `high-density` (high/h) | <=35 / <=50 | <=60 / <=100 | Detail diagrams (default) |

### Configuration Options

**CLI arguments** (highest precedence):
```bash
uv run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/ --preset med --node-target=18
```

**Environment variables** (prefix `MERMAID_COMPLEXITY_`):
```bash
MERMAID_COMPLEXITY_PRESET=low uv run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/
```

**.env file** (in project root):
```
MERMAID_COMPLEXITY_PRESET=medium-density
MERMAID_COMPLEXITY_NODE_TARGET=20
```

## B4. Handle Complex Diagrams (Subdivision)

For any diagram rated **complex** or **critical**, apply the hierarchical subdivision pattern.

### B4a. Review Working Out

```bash
uv run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/complex_diagram.mmd --show-working
```

Shows: threshold checks, node-based splits, VCS-based splits, subgraph adjustment,
recursive analysis warnings.

### B4b. Dual-Density Versions

For each lens, maintain both density levels:

**Low-density overview** (`{lens}--overview.mmd`):
- Top-level components as single nodes, major relationships only
- Target: <=12 nodes, VCS <=25
- For: README, presentations, onboarding

**High-density detail** (`{lens}--detail.mmd`):
- All significant components, complete relationships
- Target: <=35 nodes, VCS <=60
- For: technical deep-dives, debugging

### B4c. Example Subdivision

Original: `backend_architecture.mmd` (50 nodes, VCS=159 - CRITICAL)

```
docs/diagrams/
├── architecture--overview.mmd          # 4 boxes (API, Agents, Storage, External)
├── architecture--detail.mmd            # Full system (~35 nodes)
├── architecture--api--detail.mmd       # Subsystem: API routes
├── architecture--agents--detail.mmd    # Subsystem: Agent system
└── architecture--storage--detail.mmd   # Subsystem: Database layer
```

### B4d. Subdivision Agent Prompt Template

For each subdivision, launch a Task agent with:

```
Create a focused diagram at docs/diagrams/{lens}--{scope}.mmd

Purpose: {describe the view this diagram provides}
Density: {low-density for overview, high-density for detail}
Source: Extract from {original_diagram} focusing on {subgraph_name}

1. Read the original diagram at docs/diagrams/{original}.mmd
2. Identify all nodes and edges within scope
3. Create a new focused diagram that:
   - Contains ONLY nodes appropriate for this density level
   - Shows external connections as simplified boundary nodes
   - Preserves the styling (classDef, linkStyle) from original
   - Uses consistent node IDs for cross-referencing
4. Verify complexity is within thresholds for the density preset

Report: node count, VCS, preset used, nodes extracted, boundary connections simplified.
```

## B5. Update Each Diagram (Parallel Execution)

For EACH `.mmd` file, launch a Task subagent. Launch ALL agents in PARALLEL.

**Agent prompt template (overview):**
```
Update docs/diagrams/architecture--overview.mmd to reflect current system architecture.

LOW-DENSITY overview: max 12 nodes, top-level components only, major relationships.
1. Read existing diagram  2. Analyze codebase  3. Update .mmd  4. Verify: --preset low
Only update this diagram, don't modify other files.
```

**Agent prompt template (detail):**
```
Update docs/diagrams/architecture--detail.mmd to reflect current system architecture.

HIGH-DENSITY detail: up to 35 nodes, all significant components, subgraphs for grouping.
1. Read existing diagram  2. Analyze codebase  3. Update .mmd  4. Verify: --preset high
Only update this diagram, don't modify other files.
```

## B6. Validate Complexity Post-Update

```bash
# Validate overview diagrams (low-density)
uv run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/*--overview.mmd --preset low

# Validate detail diagrams (high-density)
uv run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/*--detail.mmd --preset high

# Validate all
uv run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/
```

If any remain "complex" or "critical", repeat B4.

## B7. Generate PNG Images

```bash
# Batch render all .mmd files via Makefile
make -C docs/diagrams

# With Iconify icon packs
make -C docs/diagrams ICON_PACKS="@iconify-json/logos @iconify-json/mdi"
```

Or render a single diagram:
```bash
npx -p @mermaid-js/mermaid-cli mmdc \
  -i docs/diagrams/architecture--overview.mmd \
  -o docs/diagrams/architecture--overview.png \
  --scale 4 -t dark -b transparent
```

See `.claude/skills/mermaidjs_diagrams/resources/examples/` for sample `.mmd` files
and their rendered PNG output.

## B8. Sync README

```markdown
## Architecture Diagrams

### Quick Overview
![Architecture Overview](docs/diagrams/architecture--overview.png)
*High-level system components* | [Source](docs/diagrams/architecture--overview.mmd)
```

## Verification with Pattern: Render from Markdown

After updating `.mmd` files, use the render-from-markdown pattern as a verification
step on any markdown files that embed mermaid fences. See
`resources/pattern_render_markdown.md` for the variant system and full documentation.
