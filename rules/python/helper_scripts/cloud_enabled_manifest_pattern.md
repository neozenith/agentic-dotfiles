# Cloud-Enabled Manifest Pattern

A design pattern for Python CLI tools that manage large parameter sweeps: define N permutations of work, track which are complete, execute the missing ones, and optionally offload execution to cloud compute.

## When to Use

Apply this pattern when a project needs to:
- Run the same function/script across hundreds or thousands of parameter combinations
- Track which combinations have been completed across sessions
- Resume from where you left off after interruption
- Optionally distribute work across multiple machines or cloud workers

Common examples: benchmark suites, hyperparameter sweeps, experiment grids, data processing pipelines with many input variants.

## Five Composable Layers

The pattern is built from five layers. Each layer is independently useful — a project can adopt layers 1-3 for local-only execution and add layers 4-5 later for cloud dispatch.

```
Layer 1: Permutation Registry     — define the parameter space
Layer 2: Status Determination     — track what's done
Layer 3: Manifest CLI Interface   — filter, sort, emit commands
Layer 4: Execution Lifecycle      — run a single permutation
Layer 5: Cloud Dispatch           — offload to remote workers
```

---

## Layer 1: Permutation Registry

A function that returns a list of dicts, one per permutation. Each dict MUST include:

| Field | Type | Description |
|-------|------|-------------|
| `permutation_id` | `str` | Deterministic slug derived from parameters. Must be a valid path component (no slashes, no spaces). |
| `sort_key` | `tuple` | First element = primary scaling dimension. Enables cheapest-first execution order. |
| `label` | `str` | Human-readable description for status display. |
| `category` | `str or None` | Optional grouping. Enables `--category` filtering. |
| `done` | `bool` | Completion status. Populated by Layer 2. |

### Permutation ID Contract

The `permutation_id` is a **pure function** of the parameter axes. Given the same parameters, it always produces the same ID. It is used as: the result filename/directory key, the `--id` CLI argument, the SQS message body, and the unique identifier in status tracking.

```python
def permutation_id(dataset: str, *, model: str, n: int) -> str:
    """Deterministic slug from parameters. Valid as filename and CLI argument."""
    return f"{dataset}_{model}_n{n}"
```

### Registry Function

The registry enumerates all permutations by iterating the cross-product of parameter axes:

```python
MODELS = ["small", "medium", "large"]
DATASETS = ["dataset_a", "dataset_b"]
SIZES = [100, 500, 1000, 5000]

def all_permutations(results_dir: Path) -> list[dict]:
    """Generate all permutations with completion status."""
    perms = []
    for model in MODELS:
        for dataset in DATASETS:
            for n in SIZES:
                pid = permutation_id(dataset, model=model, n=n)
                perms.append({
                    "permutation_id": pid,
                    "sort_key": (n, model, dataset),  # cheapest first
                    "label": f"{model} / {dataset} / N={n}",
                    "category": None,
                    "done": check_status(results_dir, pid),
                })
    return perms
```

### Multi-Category Registries

For projects with distinct groups of permutations (different parameter shapes per group), use a category-dispatched registry:

```python
_GENERATORS = {
    "search": _search_permutations,
    "embedding": _embedding_permutations,
    "graph": _graph_permutations,
}

# Optional: exclude categories with known issues
_DEFAULT_EXCLUDES = {"experimental"}

def all_permutations(results_dir: Path) -> list[dict]:
    excluded = _get_excluded()  # from env var or default
    perms = []
    for cat, gen_fn in _GENERATORS.items():
        if cat not in excluded:
            perms.extend(gen_fn(results_dir))
    return perms
```

Category exclusion via environment variable (`SWEEP_EXCLUDE_CATEGORIES=cat1,cat2`) allows disabling problematic groups without code changes.

---

## Layer 2: Status Determination

Two approaches, chosen based on result format:

### File-Existence Check (simpler)

One result file per permutation. A permutation is done if its file exists.

```python
def check_status(results_dir: Path, permutation_id: str) -> bool:
    return (results_dir / f"{permutation_id}.json").exists()
```

Best when: each run produces exactly one result file, overwrites on re-run.

### Content Scan (for append-mode accumulation)

Multiple runs append to shared files. Scan file contents for the `permutation_id` field.

```python
def load_completed_ids(results_dir: Path) -> set[str]:
    completed = set()
    for filepath in sorted(results_dir.glob("*.jsonl")):
        for line in filepath.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                record = json.loads(line)
                pid = record.get("permutation_id")
                if pid:
                    completed.add(pid)
    return completed
```

Best when: results accumulate across multiple runs, one JSONL file per category.

### S3-Aware Status (Cloud Layer)

Both approaches extend to remote state via an S3 mirror that unions local and remote listings:

```python
def load_completed_ids(results_dir: Path, mirror) -> set[str]:
    completed = set()
    for filepath in mirror.list_union(results_dir, "*.jsonl"):
        if not mirror.ensure_local(filepath):
            continue
        # ... same JSONL scan as above
    return completed
```

The S3 mirror provides three operations:
- `ensure_local(path)` — download from S3 if missing locally; return True if available
- `sync_to_s3(path)` — upload to S3 if not already there (by size comparison)
- `list_union(dir, pattern)` — sorted union of local glob and S3 listing (no download)

---

## Layer 3: Manifest CLI Interface

The manifest subcommand is the primary interface for inspecting the parameter space. It MUST support these five flags:

```python
manifest_parser.add_argument("--missing", action="store_true",
    help="Show only incomplete permutations")
manifest_parser.add_argument("--done", action="store_true",
    help="Show only completed permutations")
manifest_parser.add_argument("--commands", action="store_true",
    help="Emit one runnable shell command per permutation")
manifest_parser.add_argument("--sort", choices=["size", "name"], default="size",
    help="Sort order: 'size' (cheapest first) or 'name' (alphabetical)")
manifest_parser.add_argument("--limit", type=int, default=None,
    help="Limit output to first N entries after filtering and sorting")
```

Optional: `--category` for multi-category registries, `--force` to append `--force` to emitted commands.

### Command Emission

The `--commands` flag emits self-contained runnable commands:

```
uv run -m mypackage run --id dataset_a_small_n100
uv run -m mypackage run --id dataset_a_small_n500
uv run -m mypackage run --id dataset_a_medium_n100
```

Each line is a complete command that can be: executed locally, piped to `xargs -P4` for local parallelism, or enqueued to an SQS queue for cloud dispatch.

### Status Display

Non-command mode shows a human-readable table grouped by category:

```
=== Manifest (342/500 done) ===

SEARCH (120/150):
  [DONE] dataset_a_small_n100          Search: small / dataset_a / N=100
  [MISS] dataset_a_small_n5000         Search: small / dataset_a / N=5000
  ...
```

### `manifest --commands --missing --limit 1`

This specific invocation is the **cloud dispatch primitive**: it returns the single cheapest missing permutation as a runnable command. A worker executes this to self-select its work.

---

## Layer 4: Execution Lifecycle

A single permutation is executed via a `run` subcommand:

```bash
uv run -m mypackage run --id dataset_a_small_n100
```

### Result Writing

After execution, write the result atomically and upload to S3 if configured:

```python
def save_result(results_dir: Path, permutation_id: str, record: dict, mirror=None):
    path = results_dir / f"{permutation_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    if mirror:
        mirror.sync_to_s3(path)
```

For JSONL append mode:

```python
def append_result(path: Path, record: dict, mirror=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    if mirror:
        mirror.sync_to_s3(path)
```

### Force Flag

The `--force` flag allows re-running a completed permutation. Without it, the run command should exit early if the result already exists.

### Prep Dependencies

Input data and model dependencies should be managed by an explicit `prep` subcommand, not lazy-loaded during `run`. This matters for cloud execution where prep should happen during image priming, not on every worker boot.

```python
# Explicit prep with status visibility
prep_parser.add_argument("--status", action="store_true",
    help="Show prep artifact status without downloading")
```

---

## Layer 5: Cloud Dispatch

Optional layer that distributes execution across remote workers. Builds on layers 1-4 without modifying them.

### Adoption Tiers

| Tier | What it adds | Complexity | When to adopt |
|------|-------------|-----------|---------------|
| **Local only** | Layers 1-4 | None | Default starting point |
| **S3 mirror** | Remote result store, cross-machine status | Low | Multiple machines, shared results |
| **Single worker** | Launch one EC2 instance, run `manifest --missing --limit 1`, monitor heartbeat | Medium | Offload expensive runs |
| **SQS fan-out** | Enqueue IDs, ASG scales workers from AMI | High | Many permutations in parallel |

### S3 Heartbeat

Workers write a JSON file to S3 every 15 seconds for liveness monitoring:

```json
{"timestamp": "2026-03-27T07:15:30Z", "phase": "running", "permutation_id": "dataset_a_small_n5000"}
```

The client polls this file. If stale for >60 seconds, the worker may be hung. If stale for >180 seconds, auto-terminate.

### Worker Self-Selection Pattern

Workers determine their own work by querying the manifest or polling SQS:

**Manifest-based** (simpler, for single workers):
```bash
BENCH_CMD=$(uv run -m mypackage manifest --commands --missing --limit 1)
eval "$BENCH_CMD"
```

**SQS-based** (for parallel workers via ASG):
```bash
MSG=$(aws sqs receive-message --queue-url "$QUEUE_URL" --wait-time-seconds 20)
PERM_ID=$(echo "$MSG" | jq -r '.Messages[0].Body // empty')
RECEIPT=$(echo "$MSG" | jq -r '.Messages[0].ReceiptHandle // empty')

if [ -z "$PERM_ID" ]; then
    echo "Queue empty."
    shutdown -h now
fi

uv run -m mypackage run --id "$PERM_ID" --force
aws sqs delete-message --queue-url "$QUEUE_URL" --receipt-handle "$RECEIPT"
```

### Spot Instance Resilience

With SQS dispatch, spot instance interruption is handled naturally:
1. Worker pulls message from SQS (message becomes invisible for the visibility timeout)
2. Worker starts executing the permutation
3. If interrupted (SIGKILL), the message visibility timeout expires
4. Message reappears in the queue
5. Another worker picks it up

No special retry logic needed — the SQS visibility timeout IS the retry mechanism.

### AMI Priming

For fast worker startup, prime an AMI with slow-to-create artifacts:

**Bake into AMI** (slow to create, rarely changes):
- OS packages, build tools, compiler caches
- Git repo clone with submodules
- Compiled binaries and static libraries
- Python virtual environment with all dependencies

**Inject at boot** (changes per run):
- Git branch name, SQS queue URL, S3 bucket name
- Injected via a systemd service that downloads a worker script from S3

Do NOT use cloud-init user-data for boot execution on AMI-launched instances — cloud-init only runs user-data on first boot. Use a systemd oneshot service that runs after `network-online.target`.

### Scaling Policy

When using ASG + SQS, the scaling metric must consider both visible AND in-flight messages. A naive alarm on visible messages alone will scale in while workers are actively processing (pulled messages become invisible).

```
scale_metric = ApproximateNumberOfMessagesVisible + ApproximateNumberOfMessagesNotVisible
```

Require 10 consecutive zero-metric periods before scaling in. This prevents premature termination of active workers.

---

## Anti-Patterns

| Anti-Pattern | Why it fails | Correct approach |
|-------------|-------------|-----------------|
| Lazy prep inside `run` | Workers OOM or timeout during first-run prep | Explicit `prep` subcommand; bake into AMI |
| Cloud-init user-data for AMI workers | Cloud-init skips user-data on non-first boot | Systemd service downloads script from S3 |
| Scale-in on visible messages only | Workers terminated mid-execution | Use `visible + inflight` metric |
| `#cloud-boothook` for S3 downloads | Runs before networking is available | Systemd service with `After=network-online.target` |
| Phase logs uploaded only in EXIT trap | Spot SIGKILL doesn't fire trap handlers | Upload results per-permutation, not at shutdown |
| Fixed-index assignment (Batch array style) | Interrupted index requires reassignment logic | Worker self-selection via manifest or SQS |
| Syncing compiled artifacts to S3 | Platform-specific, fragile, wastes bandwidth | AMI is the cache; EBS persists on stop |

## Monitoring Dashboard Pattern

A Plotly Dash app that auto-refreshes every 15 seconds, backed by CloudWatch metrics (not ephemeral client-side state). Survives page refresh.

Key panels:
- **Metric cards**: queue visible, in-flight, dead letter, worker count
- **Time-series chart**: CloudWatch `ApproximateNumberOfMessages*` + ASG `GroupInServiceInstances` with selectable time range (1h/3h/12h/1d/3d/7d)
- **Worker table**: per-instance state, heartbeat age, current phase (from S3 heartbeat)
- **Scaling events table**: ASG activities classified as SCALE OUT / SCALE IN / SPOT RECLAIM / UNHEALTHY

All colors must pass WCAG AA contrast ratios (4.5:1 minimum for text). Use Tailwind shade 400+ for accent text on dark backgrounds.
