# Attention Is Scarce (AIS)

> Every question to the user is a tax on their attention. Spend it like
> the scarcest resource in the loop — because it is.

When ≥ 2 open decisions are blocking work, run this loop instead of asking a
chain of questions: pick the **single highest-leverage** question, ship it
with a recommended default, then cascade the answer across the rest.

```mermaid
flowchart TD
    A[1. Inventory ambiguities]:::stateStart
    B[2. Rank by cross-cutting impact]:::stateActive
    C{3. Pragmatic default<br/>obvious?}:::stateWaiting
    D[Pick default,<br/>note assumption]:::stateShortcut
    E[4. Ask ONE multiple-choice<br/>question with recommendation]:::stateActive
    F[5. Cascade answer across<br/>related ambiguities]:::stateActive
    G{6. Material ambiguity<br/>remains?}:::stateWaiting
    H[Exit and proceed]:::stateEnd

    A --> B
    B --> C
    C -- Yes --> D
    C -- No --> E
    E --> F
    D --> F
    F --> G
    G -- Yes, re-rank first --> A
    G -- No --> H

    classDef stateStart    fill:#d1fae5,stroke:#047857,color:#1e293b,stroke-width:2px
    classDef stateActive   fill:#dbeafe,stroke:#1d4ed8,color:#1e293b,stroke-width:2px
    classDef stateWaiting  fill:#fef3c7,stroke:#b45309,color:#1e293b,stroke-width:2px
    classDef stateShortcut fill:#f1f5f9,stroke:#64748b,color:#1e293b,stroke-width:1px,stroke-dasharray:5 5
    classDef stateEnd      fill:#cbd5e1,stroke:#334155,color:#1e293b,stroke-width:2px
```

See `SKILL.md` for invocation triggers, pragmatic-default criteria, framing
rules, output template, and anti-patterns.
