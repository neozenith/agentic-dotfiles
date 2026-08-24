# Concise Decisions

Human attention is the scarcest resource. 
 
- Reduce cognitive fatigue and leverage the decisions we are already making. 
- Force the agent to leverage existing ADRs to self answer questions.
- Guide the agent extract your reasoning and apply it to all open questions before asking the next question.
- Use a checklist for the agent to **ask better questions** so you can make **informed decisions**.
- There is also a difference between **answering a question**, and **making a decision**.

----

## Asking Better Questions Framework

  1. Can I make an **informed decision** from what is presented?
  2. Do I understand why **this** question is being asked **now**? 
      - Why is it **the next most impactful question** worthy of my attention?
  3. Do I understand why prior decisions do **not** already answer it?
      - Have you checked existing decision records and knowledge bases?
  4. Can I attach my reasoning to whichever option I pick? 
      - Multichoice and Multi-select without space for freetext is a failure.
  5. Can I give a _**To Be Decided (TBD) answer**_ - an **answer** that is **not a decision**?
     - `explain` - Despite best efforts, I need part of the existing explanation expanded and revised before I can make an informed decision.
     - `show` - The question is visual or interactive in nature and needs real prototypes before an **informed decision** can be made. Create artifacts for each option and revise the question.
     - `spike` - We can not blindly trust performance metrics. We need to empirically collect data to make an **informed decision**. Run a timeboxed `spike` where the outcome is a `learning`. 
     - `defer` or `handoff` - The question is **valid** but it is **not important right now**. Log the entire question and recommendations as a ticket for a backlog. Mark this seam as a scope boundary for now.

----



<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [Concise Decisions](#concise-decisions)
  - [Asking Better Questions Framework](#asking-better-questions-framework)
  - [Quickstart](#quickstart)
  - [Architecture](#architecture)
  - [For maintainers](#for-maintainers)

<!--TOC-->
</details>

## Quickstart

In an agent session, when there are decisions blocking work:

```text
/concise-decisions
```

## Architecture

The loop, at a glance: one question per turn, and every answer is cascaded
before the next question is even ranked.

```mermaid
flowchart LR
    A["1. Inventory ambiguities"]:::stateStart
    B["2. Check decision records,<br/>then rank by impact"]:::stateActive
    C{"3. Pragmatic default<br/>obvious?"}:::stateWaiting
    D["State the default<br/>in passing"]:::stateShortcut
    E["4. Ask ONE question that<br/>passes the five checks"]:::stateActive
    U{"Answer is a<br/>decision?"}:::stateUser
    T["TBD route: explain, show,<br/>spike, defer / handoff"]:::stateUser
    F["5. Cascade the answer,<br/>record reasoning as a lens"]:::stateActive
    G{"6. Material ambiguity<br/>remains?"}:::stateWaiting
    H["Exit and proceed"]:::stateEnd

    A --> B --> C
    C -- Yes --> D --> F
    C -- No --> E --> U
    U -- Yes --> F
    U -- No --> T
    T -- revise, re-ask --> E
    F --> G
    G -- Yes, re-rank first --> A
    G -- No --> H

    classDef stateStart    fill:#d1fae5,stroke:#047857,color:#1e293b,stroke-width:2px
    classDef stateActive   fill:#dbeafe,stroke:#1d4ed8,color:#1e293b,stroke-width:2px
    classDef stateWaiting  fill:#fef3c7,stroke:#b45309,color:#1e293b,stroke-width:2px
    classDef stateUser     fill:#ede9fe,stroke:#7c3aed,color:#1e293b,stroke-width:2px
    classDef stateShortcut fill:#f1f5f9,stroke:#64748b,color:#1e293b,stroke-width:1px,stroke-dasharray:5 5
    classDef stateEnd      fill:#cbd5e1,stroke:#334155,color:#1e293b,stroke-width:2px
```


<details>
<summary>📋 Complete loop: decision records, composing the question, the TBD routes, and the cascade (25 nodes)</summary>

```mermaid
flowchart TB
    A["1. Inventory ambiguities,<br/>including silent assumptions"]:::stateStart
    B["2. Check decision records:<br/>ADRs, lenses, plan, memory, KBs"]:::stateActive
    B2{"Already decided<br/>by a record?"}:::stateWaiting
    B3["Apply it, cite it,<br/>drop it from the queue"]:::stateShortcut
    B4["Rank the rest by<br/>cross-cutting impact"]:::stateActive
    C{"3. All four pragmatic-default<br/>criteria hold?"}:::stateWaiting
    D["State the default in one line:<br/>a statement, not a question"]:::stateShortcut

    subgraph compose ["4. Compose ONE question"]
        direction TB
        E1["Pick ONE shape file: exclusive,<br/>permutations, binary, low-stakes,<br/>resolved-by-cascade"]:::stateActive
        E2["Sense the harness, load ONE adapter:<br/>claude-code, codex, session-feed"]:::stateActive
        E3["Fill the nine-section template:<br/>complete previews on real data"]:::stateActive
        E4{"Five-question check,<br/>read cold: all yes?"}:::stateWaiting
        E5["Fix the question"]:::stateActive
        E6["Send: briefing body, then<br/>ONE answer surface"]:::stateActive
        E1 --> E2 --> E3 --> E4
        E4 -- No --> E5 --> E3
        E4 -- Yes --> E6
    end

    U{"User answers:<br/>decision or TBD?"}:::stateUser

    subgraph tbd ["TBD routes: an answer that is not a decision"]
        direction TB
        T0{"Which route?"}:::stateUser
        T1["explain: revise that part,<br/>re-ask the same question"]:::stateUser
        T2["show: one complete artifact<br/>per option, then re-ask"]:::stateUser
        T3["spike: timeboxed experiment,<br/>the outcome is a learning"]:::stateUser
        T4["defer / handoff: whole question<br/>becomes a ticket; scope seam"]:::stateUser
        T5["other / task: render the new<br/>option or do the prep, re-ask"]:::stateUser
        T0 --> T1
        T0 --> T2
        T0 --> T3
        T0 --> T4
        T0 --> T5
    end

    subgraph after ["5. After the answer"]
        direction TB
        F1["Confirm the choice,<br/>quote the reasoning"]:::stateActive
        F2["Record decision + reasoning as a<br/>lens where decisions live"]:::stateActive
        F3["Cascade across every<br/>related ambiguity"]:::stateActive
        F1 --> F2 --> F3
    end

    G{"6. Material ambiguity<br/>remains?"}:::stateWaiting
    H["Exit and proceed"]:::stateEnd

    A --> B --> B2
    B2 -- Yes --> B3 --> B4
    B2 -- No --> B4
    B4 --> C
    C -- Yes --> D --> F3
    C -- No --> E1
    E6 --> U
    U -- Decision --> F1
    U -- TBD --> T0
    T1 --> E3
    T2 --> E3
    T3 --> E3
    T5 --> E3
    T4 --> F2
    F3 --> G
    G -- Yes, re-rank first --> A
    G -- No --> H

    classDef stateStart    fill:#d1fae5,stroke:#047857,color:#1e293b,stroke-width:2px
    classDef stateActive   fill:#dbeafe,stroke:#1d4ed8,color:#1e293b,stroke-width:2px
    classDef stateWaiting  fill:#fef3c7,stroke:#b45309,color:#1e293b,stroke-width:2px
    classDef stateUser     fill:#ede9fe,stroke:#7c3aed,color:#1e293b,stroke-width:2px
    classDef stateShortcut fill:#f1f5f9,stroke:#64748b,color:#1e293b,stroke-width:1px,stroke-dasharray:5 5
    classDef stateEnd      fill:#cbd5e1,stroke:#334155,color:#1e293b,stroke-width:2px
```

</details>

## For maintainers

Rationale and the extension checklist are in [CLAUDE.md](CLAUDE.md); the ADR
log with lenses is one file per decision in [docs/adrs/](docs/adrs/README.md).
