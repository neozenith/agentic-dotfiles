---
paths:
  - "scripts/**/*.py"
  - "**/scripts/*.py"
---

# Manifest Pattern for Permutation Pipelines

Reusable CLI pattern for scripts that generate output artifacts from a matrix of
input parameters (e.g., datasets x models, configs x environments). Provides
introspection, filtering, and self-command generation.

> Extends `python/helper_scripts/RULES.md` for scripts with permutation matrices.

## When to Apply

Use this pattern when a script:
- Generates multiple output files from a cross-product of parameters
- Has long-running builds where you want to track progress
- Needs to generate commands for CI/CD or parallel execution

## Core Data Structure

Each permutation is a dict with these required fields:

```python
{
    "permutation_id": "dataset1_modelA",    # Unique slug (valid filename stem)
    "done": True,                           # Whether output artifact exists
    "sort_key": (100, 384, "dataset1"),     # Tuple for cost-ascending sort
    "label": "Dataset1 + ModelA (384d)",    # Human-readable description
}
```

Additional fields are domain-specific (e.g., `output_path`, `db_size`).

## CLI Structure: Subcommands (not flags)

Manifest functionality is exposed as an argparse **subcommand**, not a `--manifest`
flag. This cleanly separates info modes from build modes at the CLI level:

```python
subparsers = parser.add_subparsers(dest="command")

# Info subcommands (no heavy imports needed)
manifest_p = subparsers.add_parser("manifest", help="Show permutation status")
manifest_p.add_argument("--missing", action="store_true")
manifest_p.add_argument("--done", action="store_true")
manifest_p.add_argument("--sort", choices=["size", "name"], default="size")
manifest_p.add_argument("--limit", type=int)
manifest_p.add_argument("--commands", action="store_true")
manifest_p.add_argument("--force", action="store_true")

subparsers.add_parser("list-inputs", help="List discovered input sources")
subparsers.add_parser("list-params", help="List available parameter values")

# Build subcommand (heavy imports deferred to handler)
build_p = subparsers.add_parser("build", help="Build artifact(s)")
build_p.add_argument("--output-folder", type=str, required=True)
build_p.add_argument("--input-id", type=str)
build_p.add_argument("--param-name", type=str)
build_p.add_argument("--force", action="store_true")
```

### Manifest Subcommand Flags

| Flag | Description |
|------|-------------|
| `--missing` | Filter to incomplete permutations |
| `--done` | Filter to completed permutations |
| `--sort {size,name}` | Sort order (default: `size` = cheapest first) |
| `--limit N` | Limit to first N entries after filtering/sorting |
| `--commands` | Print runnable self-commands instead of a table |
| `--force` | With `--commands`: append `--force` to each generated command |

## Implementation Structure

### 1. Manifest Builder

Returns the full cross-product of permutations with status:

```python
def permutation_manifest(output_dir: Path) -> list[dict]:
    """Build manifest of all permutations with build status."""
    inputs = discover_inputs()
    params = list(PARAM_REGISTRY.keys())

    entries = []
    for inp in inputs:
        cost_estimate = estimate_cost(inp)  # e.g., row count, file size
        for param in params:
            perm_id = f"{inp}_{param}"
            out_path = output_dir / f"{perm_id}.ext"
            done = out_path.exists()

            entries.append({
                "permutation_id": perm_id,
                "input_id": inp,
                "param_name": param,
                "done": done,
                "output_size": out_path.stat().st_size if done else None,
                "output_path": out_path,
                "sort_key": (cost_estimate, PARAM_REGISTRY[param]["cost"], inp),
                "label": f"{inp} + {param} ({cost_estimate} units)",
            })

    return entries
```

### 2. Manifest Printer

Handles filtering, sorting, limiting, and command generation:

```python
def print_manifest(
    entries: list[dict],
    output_dir: Path,
    *,
    missing: bool = False,
    done: bool = False,
    sort: str = "size",
    limit: int | None = None,
    commands: bool = False,
    force: bool = False,
) -> None:
    """Print manifest with filtering, sorting, and command generation."""
    # Filter
    if missing:
        entries = [e for e in entries if not e["done"]]
    if done:
        entries = [e for e in entries if e["done"]]

    # Sort
    if sort == "name":
        entries = sorted(entries, key=lambda e: e["permutation_id"])
    else:  # "size" -- cheapest/smallest first
        entries = sorted(entries, key=lambda e: e["sort_key"])

    # Limit
    if limit is not None:
        entries = entries[:limit]

    # Command generation mode
    if commands:
        force_suffix = " --force" if force else ""
        for e in entries:
            print(
                f"uv run -m my_package.builder build"
                f" --output-folder {output_dir}"
                f" --input-id {e['input_id']}"
                f" --param-name {e['param_name']}"
                f"{force_suffix}"
            )
        return

    # Table display mode
    total_done = sum(1 for e in entries if e["done"])
    print(f"\n=== Manifest ({total_done}/{len(entries)}) ===\n")
    for e in entries:
        marker = "DONE" if e["done"] else "MISS"
        print(f"  [{marker}] {e['permutation_id']:<30s} {e['label']}")
    print()
```

### 3. CLI Dispatch (deferred imports for build)

```python
args = parser.parse_args()

if args.command == "manifest":
    entries = permutation_manifest(output_dir)
    print_manifest(entries, output_dir, missing=args.missing, ...)
elif args.command == "build":
    # Deferred imports -- only loaded when building
    from my_package.builder.build import Builder
    from my_package.builder.models import ModelPool
    # ... build logic
elif args.command == "list-inputs":
    print_inputs()
```

## Sort Key Design

The `sort_key` tuple should order permutations by estimated build cost,
cheapest first. This enables `--missing --limit 3` to pick the fastest
tasks to run next.

**Convention:** Primary dimension = scaling factor (row count, file size),
secondary = parameter cost (model dimension, complexity), then tie-breakers.

```python
# Example: datasets vary in size, models vary in dimension
"sort_key": (num_rows, model_dim, dataset_name, model_name)
```

## Self-Command Generation

Generated commands must:
1. Be copy-pasteable and runnable from the project root
2. Pin each permutation to a single `(input, param)` pair via CLI flags
3. Include `--force` only when the user passes `--force` alongside `--commands`
4. Use relative paths from project root (fall back to absolute if outside)

## Common Compositions

```bash
# "What's left to build?"
uv run -m my_package.builder manifest --missing

# "Give me the 5 cheapest remaining tasks"
uv run -m my_package.builder manifest --missing --limit 5

# "Generate a shell script for CI"
uv run -m my_package.builder manifest --missing --commands > run_missing.sh

# "Rebuild everything"
uv run -m my_package.builder manifest --commands --force > rebuild_all.sh

# "What's done, sorted alphabetically?"
uv run -m my_package.builder manifest --done --sort name
```

## Staged Build with `_build/` Ephemeral Directory

Long-running builds should use a staging area to support resumability,
inspection of partial results, and atomic output:

### Directory Layout

```
output_folder/
├── _build/                          # Ephemeral staging area
│   └── dataset1_modelA/             # Per-permutation staging dir
│       ├── dataset1_modelA.db       # In-progress artifact
│       ├── dataset1_modelA.debug.log
│       ├── dataset1_modelA.info.log
│       └── dataset1_modelA.error.log
├── dataset1_modelA.db               # Final artifact (after atomic move)
└── dataset2_modelB.db
```

### Build Progress Table

Track completed phases inside the artifact itself for resumability
and manifest status display:

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS _build_progress (
        phase INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        completed_at TEXT NOT NULL
    )
""")
```

After each phase completes and commits:

```python
conn.execute(
    "INSERT INTO _build_progress (phase, name, completed_at) VALUES (?, ?, ?)",
    (phase_num, phase_name, datetime.now(UTC).isoformat()),
)
conn.commit()
```

### Lifecycle

1. **Setup**: Create `{output_dir}/_build/{perm_id}/` staging directory
2. **Build**: Create artifact in staging dir, recording each phase
3. **On success**: Drop `_build_progress` table, VACUUM, atomic move to final path, delete staging dir
4. **On failure**: Staging dir preserved with partial artifact + log files for inspection
5. **`--force`**: Cleans stale staging dirs before rebuilding

### Manifest Integration

The manifest builder checks staging dirs for in-progress builds:

```python
staging_db = output_dir / "_build" / perm_id / f"{perm_id}.db"
if not done and staging_db.exists():
    progress = read_build_progress(staging_db)
    if progress:
        status = f"BUILD [{phase_num}/{total_phases}] {phase_name}"
    else:
        status = "BUILD [0/N] starting"
```

## Hierarchical Logging Pattern

Long-running builds produce three log files per permutation in the
staging directory, enabling token-efficient debugging:

### Log File Levels

| File | Level | Purpose |
|------|-------|---------|
| `{perm_id}.debug.log` | DEBUG+ | Full trace -- everything |
| `{perm_id}.info.log` | INFO+ | Phase progress, counts, timing |
| `{perm_id}.error.log` | ERROR+ | Just errors -- share first for debugging |

### Format

```
%(asctime)s [%(levelname)s] %(message)s
```

With ISO 8601 timestamps (`%Y-%m-%dT%H:%M:%S`) enabling phase-windowed filtering.

### Implementation

```python
def _setup_logging(self) -> None:
    """Create three file handlers: debug, info, error."""
    self._log.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    for filename, level in [
        (f"{self.perm_id}.debug.log", logging.DEBUG),
        (f"{self.perm_id}.info.log", logging.INFO),
        (f"{self.perm_id}.error.log", logging.ERROR),
    ]:
        handler = logging.FileHandler(self.staging_dir / filename)
        handler.setLevel(level)
        handler.setFormatter(fmt)
        self._log.addHandler(handler)
        self._file_handlers.append(handler)

def _teardown_logging(self) -> None:
    """Close and remove all file handlers (called in finally)."""
    for handler in self._file_handlers:
        handler.close()
        self._log.removeHandler(handler)
    self._file_handlers.clear()
```

### Token-Efficient Debugging Workflow

1. Share `{perm_id}.error.log` (smallest) for initial diagnosis
2. If more context needed, share time-windowed slice from `{perm_id}.info.log`
3. `{perm_id}.debug.log` for deep investigation of a specific phase
4. On success: logs cleaned up with staging dir (not deliverables)
