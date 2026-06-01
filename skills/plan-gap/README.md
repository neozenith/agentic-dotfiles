# Planning via Gap Analysis Specs `/plan-gap`

Structured planning spec designed for both human review and agent consumption. Your attention is precious.

With parallel AI research agents, verified citations (reduce hallucinated references), and structured decision records that minimize the questions you need to answer.

**USAGE**:

```text
/plan-gap docs/plans/

"Migrate our session-based auth middleware to OAuth2 + PKCE, replacing the custom token store with Redis-backed sessions."
```

## Research Workflow

```mermaid
flowchart LR
    USER(["User Brief"])

    subgraph P1b["Phase 1b: Broad Research"]
        TA["Track A - Current State<br/>Codebase Explorer"]
        TB["Track B - Future State<br/>SOTA + Prior Art"]
    end

    LV["Phase 1c: Link Verification<br/>(playwright-cli<br/>or WebFetch)"]
    SYN["Phase 1d: Identify<br/>Top-Level G&lt;N&gt; Gaps"]

    subgraph P1e["Phase 1e: Per-Gap Deep Dive"]
        G1A["G1<br/>Agent"]
        G2A["G2<br/>Agent"]
        GNA["G..N<br/>Agent"]
    end

    subgraph P1f["Phase 1f: Success Measures"]
        QA["Quality<br/>Standards<br/>Agent"]
        FM["Failure<br/>Modes<br/>Agent"]
    end

    subgraph P2["Phase 2: Refinement"]
        ADR["Scan Unresolved<br/>ADRs"]
        Q["Ask Most <b>Impactful</b><br/>Question"]
        HITL(["Human<br/>Answer"])
        INC["Integrate Answer<br/>Across All Relevant Questions<br/>and Resolve ADRs"]
    end

    subgraph P3["Phase 3: Validation"]
        MMD["Mermaid<br/>Rendering"]
        REQ["Requirement<br/>Integrity"]
        CON["Cross-<br/>Consistency"]
    end

    BTKT["Phase 4a: Per-Gap<br/>Behavior + TDD Ticket<br/>Decomposition<br/>(parallel per G&lt;N&gt;)"]
    EXE["Phase 4b: Write<br/>Execution Plan +<br/>/loop runner prompt"]
    LP_CYC(["/loop iter:<br/>RED → GREEN<br/>→ REFACTOR<br/>(per ticket)"])
    DONE([Spec Complete])

    USER --> TA & TB
    TA --> SYN
    TB --> LV --> SYN
    SYN --> G1A & G2A & GNA
    SYN --> QA & FM
    G1A & G2A & GNA --> ADR
    QA & FM --> ADR
    ADR --> Q --> HITL --> INC
    INC -->|unresolved ADRs remain| ADR
    INC -->|all resolved| MMD
    MMD --> REQ --> CON
    CON --> BTKT --> EXE --> LP_CYC
    LP_CYC --> DONE
    LP_CYC -.->|UNRESOLVED ADR| ADR

    classDef userNode fill:#f59e0b,stroke:#d97706,color:#1c1917,stroke-width:3px
    classDef exploreAgent fill:#2563eb,stroke:#1d4ed8,color:#eff6ff,stroke-width:2px
    classDef webAgent fill:#7c3aed,stroke:#6d28d9,color:#f5f3ff,stroke-width:2px
    classDef verifyNode fill:#dc2626,stroke:#b91c1c,color:#fef2f2,stroke-width:2px
    classDef synthNode fill:#0891b2,stroke:#0e7490,color:#ecfeff,stroke-width:2px
    classDef gapAgent fill:#059669,stroke:#047857,color:#ecfdf5,stroke-width:2px
    classDef qualAgent fill:#0d9488,stroke:#0f766e,color:#f0fdfa,stroke-width:2px
    classDef humanNode fill:#f59e0b,stroke:#d97706,color:#1c1917,stroke-width:3px
    classDef refinNode fill:#8b5cf6,stroke:#7c3aed,color:#f5f3ff,stroke-width:2px
    classDef validNode fill:#10b981,stroke:#059669,color:#ecfdf5,stroke-width:2px
    classDef tddAgent fill:#9d174d,stroke:#831843,color:#fdf2f8,stroke-width:2px
    classDef execNode fill:#9a3412,stroke:#7c2d12,color:#fff7ed,stroke-width:3px
    classDef terminalNode fill:#475569,stroke:#1e293b,color:#f8fafc,stroke-width:3px

    class USER,HITL userNode
    class TA exploreAgent
    class TB webAgent
    class LV verifyNode
    class SYN synthNode
    class G1A,G2A,GNA gapAgent
    class QA,FM qualAgent
    class ADR,Q,INC refinNode
    class MMD,REQ,CON validNode
    class BTKT,EXE tddAgent
    class LP_CYC execNode
    class DONE terminalNode

    style P1b fill:#1e3a8a22,stroke:#2563eb,color:#93c5fd
    style P1e fill:#065f4622,stroke:#059669,color:#34d399
    style P1f fill:#0f766e22,stroke:#0d9488,color:#2dd4bf
    style P2 fill:#5b21b622,stroke:#8b5cf6,color:#a78bfa
    style P3 fill:#04785722,stroke:#10b981,color:#6ee7b7
```

- **Parallel broad research** — codebase explorer + SOTA web researcher run simultaneously
- **Anti-hallucination** — every external URL verified via playwright-cli or WebFetch before citation
- **Per-gap deep dive** — N agents in parallel, each with fresh context focused on one gap
- **Quality + failure discovery** — agents scan your CI gates, agentic rules, and memory for codified standards and historical gotchas
- **ADR-driven questions** — unresolved decisions tracked per gap; the skill picks the single question that resolves the most ADRs across all gaps simultaneously
- **Human-in-the-loop** — you answer one focused question per iteration; the skill propagates your answer across all affected sections
- **Executable evidence — no stubs, no mocks of the deliverable** — every gap's Outputs include a *proof-of-execution* artifact produced by running the real code path on real input (the tracer bullet produces it); a ticket that can only ship a stub triggers a 5-Whys root-cause check (`resources/5ys.md`), and a `<!-- CHANGE-REQUEST -->` only if a genuine plan defect is confirmed — the `/loop` stops and returns to refinement

## Document Structure

A spec is a **folder** (`<plan>/`) of tiered files with `README.md` as the index, not one document. The index + the one gap + the one ticket an agent is on are its `/loop` working-set; Current/Desired State and background move to a review-only Discovery file (**context economy**).

```mermaid
flowchart TD
    subgraph IDX["Index — README.md (loop entry)"]
        EP["Execution Plan<br/>(folded: runner, progress, done)"]
        OV["Overview<br/>(linked gap list + deps diagram)"]
        GA["Gap Analysis<br/>(Gap Map + Dependencies + Gaps table)"]
        DEC["Decisions (ADRs)<br/>roll-up table"]
        SM["Success + Negative<br/>Measures"]
    end

    subgraph GAP["Gap — G&lt;n&gt;.md (per-gap)"]
        GC["Context"]
        GO["Outputs table"]
        GK["Key logic<br/>(snippet, optional)"]
        GADR["ADR&lt;n&gt;.&lt;m&gt;<br/>(bulleted decision)"]
        GT["Tickets table"]
    end

    subgraph TKT["Ticket — G&lt;n&gt;-T&lt;x.y&gt;.md (per-ticket)"]
        TD["[ ] Done checkbox"]
        TC["Contract sentence"]
        TT["Test / Implements /<br/>Depends-on table"]
    end

    subgraph DISC["Discovery — DISCOVERY.md (review only)"]
        DCUR["Current State<br/>(2-3 lens diagrams)"]
        DDES["Desired State<br/>(same lenses)"]
        DINC["Gap Increments<br/>(one per gap, stacked)"]
    end

    GA -->|"links each gap"| GAP
    GT -->|"links each ticket"| TKT
    OV -.background.-> DISC
    GAP -.arch link.-> DINC

    classDef idxStyle fill:#1e40af,color:#e0e7ff
    classDef gapStyle fill:#6d28d9,color:#f5f3ff
    classDef tktStyle fill:#0e7490,color:#cffafe
    classDef discStyle fill:#92400e,color:#fef3c7

    class EP,OV,GA,DEC,SM idxStyle
    class GC,GO,GK,GADR,GT gapStyle
    class TD,TC,TT tktStyle
    class DCUR,DDES,DINC discStyle

    style IDX fill:#172554,color:#dbeafe
    style GAP fill:#3b0764,color:#ede9fe
    style TKT fill:#083344,color:#ecfeff
    style DISC fill:#431407,color:#ffedd5
```

- **Index** (`<plan>/README.md`) — one-screen orientation: scope, the linked gap list, dependency order, a Decisions roll-up, and the CI-anchored Success/Negative Measures. The TOC and Execution Plan fold behind `<details>` so humans skim while the `/loop` agent still reads them.
- **Gap files** (`G<n>.md`) — one per gap: Context, an Outputs table (at least one row is a *proof-of-execution* artifact — the gap's evidence it really runs), an optional Key-logic snippet for agentic few-shot, gap-scoped bulleted ADRs, a Tickets table, and an `Architecture` nav link to its increment diagram — all cross-linked by ID.
- **Ticket files** (`G<n>-T<x.y>.md`) — one austere TDD slice each: a Done checkbox, a precise contract sentence, and a Test/Implements/Depends-on table. The `/loop` runner consumes one per iteration.
- **Discovery** (`DISCOVERY.md`) — Current State and Desired State as **2–3 lens diagrams each** (component, data-flow, sequence, deployment, …), plus a **Gap Increments** stack: one diagram per gap, each building on the Current baseline to show what that gap changes. Human review only — never loaded during the loop.



## GitHub Issues Backend

```mermaid
flowchart TD
    subgraph GH["GitHub"]
        PARENT["Parent Issue<br/>#42 Gap Analysis"]
        C1["Comment:<br/>Refinement Q1"]
        C2["Comment:<br/>Sync Changelog"]
        SUB1["Sub-Issue #43<br/>G1: Config Params"]
        SUB2["Sub-Issue #44<br/>G2: LLM Matching"]
        SUBN["Sub-Issue #4N<br/>G..N"]
    end

    subgraph LOCAL["Local Cache"]
        CACHE[".mmdc_cache/gh_issues/<br/>owner/repo/42/"]
        DARK["Dark Variant PNGs"]
        LIGHT["Light Variant PNGs"]
    end

    PARENT -->|"task list<br/>- [ ] #43"| SUB1
    PARENT -->|"task list<br/>- [ ] #44"| SUB2
    PARENT -->|"task list"| SUBN
    PARENT --- C1 & C2

    CACHE -->|"gh issue edit<br/>--body"| PARENT
    PARENT -->|"gh issue view<br/>--json body"| CACHE
    CACHE --> DARK & LIGHT

    classDef ghNode fill:#1f2937,stroke:#6b7280,color:#f9fafb,stroke-width:2px
    classDef parentNode fill:#2563eb,stroke:#1d4ed8,color:#eff6ff,stroke-width:3px
    classDef subNode fill:#7c3aed,stroke:#6d28d9,color:#f5f3ff,stroke-width:2px
    classDef commentNode fill:#4b5563,stroke:#6b7280,color:#e5e7eb,stroke-width:1px
    classDef localNode fill:#059669,stroke:#047857,color:#ecfdf5,stroke-width:2px
    classDef renderNode fill:#0d9488,stroke:#0f766e,color:#f0fdfa,stroke-width:1px

    class PARENT parentNode
    class SUB1,SUB2,SUBN subNode
    class C1,C2 commentNode
    class CACHE localNode
    class DARK,LIGHT renderNode

    style GH fill:#1f293722,stroke:#6b7280,color:#9ca3af
    style LOCAL fill:#065f4622,stroke:#059669,color:#34d399
```

- **Local-first editing** — iterate locally with Edit tool diffs and mmdc rendering, sync back via `gh issue edit --body`
- **Sub-issues for scale** — when the body exceeds ~50K chars or 8+ gaps, each G\<N\> becomes its own tracked sub-issue
- **Audit trail** — refinement Q&A posted as comments; sync changelogs reference GitHub's edit history API
- **Native Mermaid** — diagrams render directly in the GitHub issue view
