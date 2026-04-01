# Diagram Organization

Guidelines for organizing architectural diagrams across a project using lenses,
dual-density versions, and README integration.

## Lenses

A **lens** is a perspective or view of the system. Each lens answers a different
question about the architecture:

| Lens | Purpose | Typical Content |
|------|---------|-----------------|
| `architecture` | System structure | Components, services, modules |
| `data-flow` | Information movement | Data paths, transformations |
| `deployment` | Infrastructure | Servers, containers, cloud services |
| `security` | Trust boundaries | Auth flows, encryption, access control |
| `sequence` | Interactions | API calls, user flows, processes |
| `state` | State machines | Statuses, transitions, workflows |

Choose lenses based on what stakeholders need to understand. Not every project
needs all lenses — start with `architecture` and add others as complexity demands.

## File Naming Convention

```
{lens}--[{subsystem}--]{scope}.md
```

- **`{lens}`**: One of the lenses above (architecture, data-flow, deployment, etc.)
- **`{subsystem}`**: Optional subsystem focus (omit for whole-system views)
- **`{scope}`**: `overview` (simplified) or `detail` (comprehensive)
- **`--`**: Separator (allows multiword lens/subsystem like `data-flow`)

Each file contains a single mermaid code fence with the diagram.

### Example directory structure

```
docs/diagrams/
├── architecture--overview.md
├── architecture--detail.md
├── architecture--api--detail.md
├── data-flow--overview.md
├── data-flow--detail.md
├── deployment--overview.md
├── security--overview.md
└── sequence--auth--detail.md
```

## Dual-Density Approach

For each lens, maintain two density levels when a single diagram exceeds
complexity thresholds:

### Overview (simplified)

- Top-level components as single nodes, major relationships only
- Target: <=12 nodes, VCS <=25 (low-density preset)
- Audience: README, presentations, onboarding, non-technical stakeholders

### Detail (comprehensive)

- All significant components, complete relationships, subgraphs for grouping
- Target: <=35 nodes, VCS <=60 (high-density preset)
- Audience: Technical deep-dives, debugging, architecture reviews

### When to split

If a diagram is rated **complex** or **critical** by the complexity analyzer,
subdivide it:

1. Create an `overview` version that collapses subsystems into single nodes
2. Create `detail` versions for the full system or specific subsystems
3. Validate each version against the appropriate density preset

**Example:** An architecture diagram with 50 nodes (VCS=159, CRITICAL) becomes:

| File | Nodes | Preset |
|------|-------|--------|
| `architecture--overview.md` | ~4 | low |
| `architecture--detail.md` | ~35 | high |
| `architecture--api--detail.md` | ~15 | high |
| `architecture--agents--detail.md` | ~12 | high |
| `architecture--storage--detail.md` | ~10 | high |

## README Integration

Link rendered diagram images from the project README so they're visible without
navigating to source files:

```markdown
## Architecture

### Overview
![Architecture Overview](docs/diagrams/.mmdc_cache/dark_transparent_png/docs/diagrams/architecture--overview-1.png)
*High-level system components* | [Source](docs/diagrams/architecture--overview.md)

### Data Flow
![Data Flow Overview](docs/diagrams/.mmdc_cache/dark_transparent_png/docs/diagrams/data-flow--overview-1.png)
*How data moves through the system* | [Source](docs/diagrams/data-flow--overview.md)
```

Tips:
- Link overview diagrams in the README (not detail — they're too dense for a landing page)
- Include a "Source" link so readers can find the mermaid code fence
- Use the dark+transparent variant for dark-mode-friendly README rendering,
  or default+white for repos primarily viewed in light mode
