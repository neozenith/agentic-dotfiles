---
description: "Update Mermaid.JS diagrams"
---

# Context

Setup and maintain automatic project diagrams using Mermaid.JS.
This is a **generalizable command** that works for ANY project by analyzing YOUR codebase.

# Workflow

## Step 1: Setup Infrastructure

Run the setup script to ensure docs/diagrams/ exists with proper Makefile:

```bash
uv run .claude/scripts/setup_diagrams.py
```

This creates:
- `docs/diagrams/` directory
- `docs/diagrams/Makefile` (with proper tabs)
- `docs/diagrams/.gitattributes`
- `docs/diagrams/README.md`

## Step 2: Update Each Diagram (Parallel Execution)

For EACH `.mmd` file in `docs/diagrams/`, launch a Task subagent to update it.

**Use the Task tool with these parameters:**
- `subagent_type`: "general-purpose"
- `description`: "Update [diagram-name] diagram"
- `prompt`: Detailed instructions for that specific diagram

**Important:** Launch ALL agents in PARALLEL (single message with multiple Task tool calls).

### Example Agent Prompts (Adapt to Actual Diagrams):

For a diagram like `data-pipeline-architecture.mmd`:
```
Update the diagram at docs/diagrams/data-pipeline-architecture.mmd to reflect the current data processing pipeline.

1. Read the existing diagram to understand its structure and purpose
2. Analyze the codebase:
   - Find all Python scripts in scripts/ directory
   - Parse the Makefile to understand which scripts are actively used
   - Identify data processing layers and dependencies
3. Update the .mmd file:
   - Remove references to scripts that no longer exist
   - Add new scripts if major additions were made
   - Update script descriptions if their purpose changed
   - Preserve the existing Mermaid flowchart structure and styling
4. Report what you changed

Only update this diagram, don't modify other files.
```

For a diagram like `makefile-dependencies.mmd`:
```
Update the diagram at docs/diagrams/makefile-dependencies.mmd to reflect current Makefile targets.

1. Read the existing diagram
2. Parse the Makefile to extract:
   - All .PHONY targets
   - Target dependencies
   - Main workflow targets
3. Update the .mmd file to show the current dependency graph
4. Report what changed

Only update this diagram.
```

## Step 3: Generate PNG Images

After all agents complete, regenerate PNGs:

```bash
make -C docs/diagrams diagrams
```

## Step 4: Sync README

If the project README.md has an "Architecture Diagrams" or similar section:
- Ensure all diagrams are listed
- Each diagram should show:
  ```markdown
  ![Diagram Name](docs/diagrams/diagram-name.png)
  [Source](docs/diagrams/diagram-name.mmd)
  ```

If no such section exists, consider whether to add one based on the project context.
