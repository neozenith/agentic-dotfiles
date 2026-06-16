# Widget lookup cache — Discovery (Current, Desired & Increments)

> - **Index:** [README.md](./README.md)

Review/background context: the architecture that motivates the gap, not loaded during execution.

## Current State

### Current State — components

```mermaid
flowchart TD
    C[caller] --> L[lookup_widget] --> W[(WIDGETS dict)]
```

### Current State — data flow

```mermaid
flowchart LR
    Q[widget_id] --> L[lookup_widget] --> R[recomputed display view]
```

## Desired State

### Desired State — components

```mermaid
flowchart TD
    C[caller] --> L[lookup_widget] --> K[LRU cache] --> W[(WIDGETS dict)]
```

### Desired State — data flow

```mermaid
flowchart LR
    Q[widget_id] --> K[LRU cache hit?] -->|hit| R[cached view]
    K -->|miss| L[compute + store] --> R
```

## Gap Increments

### G1 increment

**G1 inserts the LRU cache between the caller and the recompute path** — extends Current State.

```mermaid
flowchart TD
    C[caller] --> L[lookup_widget] --> K[LRU cache] --> W[(WIDGETS dict)]
```
