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

## Document Structure

```mermaid
flowchart LR
    subgraph DOC["Gap Analysis Spec Document"]
        subgraph OV["Overview"]
            OV1["Scope + Purpose"]
            OV2["Gap Index<br/>(navigable bullet list)"]
            OV3["Dependencies Diagram"]
        end

        subgraph CS["Current State"]
            CS1["Architecture Description"]
            CS2["Mermaid Diagram"]
            CS3["Known Limitations"]
        end

        subgraph DS["Desired State"]
            DS1["Target Architecture"]
            DS2["Mermaid Diagram"]
            DS3["Design Decisions<br/>+ Literature"]
        end

        subgraph GA["Gap Analysis"]
            GM["Gap Map Diagram<br/>(Current --> Gap --> Desired)"]
            DEP["Dependencies Diagram<br/>(implementation order)"]
            subgraph GN["G&lt;N&gt;: Per-Gap Detail"]
                GN1["Current / Gap / Output(s)"]
                GN2["References<br/>(code snippets, SQL, pseudocode)"]
                GN3["ADRs<br/>(resolved + unresolved decisions)"]
            end
        end

        subgraph SM["Success Measures"]
            SM1["Project Quality Bar<br/>(CI gates table)"]
            SM2["Domain-Specific<br/>Measures"]
        end

        subgraph NM["Negative Measures"]
            NM1["Quality Bar Violations"]
            NM2["Domain-Specific<br/>Failures"]
        end
    end

    OV --> CS --> DS --> GA --> SM --> NM

    classDef ovStyle fill:#1e40af,stroke:#1e3a8a,color:#e0e7ff,stroke-width:2px
    classDef csStyle fill:#b45309,stroke:#92400e,color:#fef3c7,stroke-width:2px
    classDef dsStyle fill:#047857,stroke:#065f46,color:#d1fae5,stroke-width:2px
    classDef gaStyle fill:#6d28d9,stroke:#5b21b6,color:#ede9fe,stroke-width:2px
    classDef gnStyle fill:#7c3aed,stroke:#6d28d9,color:#f5f3ff,stroke-width:1px
    classDef smStyle fill:#0e7490,stroke:#155e75,color:#cffafe,stroke-width:2px
    classDef nmStyle fill:#b91c1c,stroke:#991b1b,color:#fee2e2,stroke-width:2px

    class OV1,OV2,OV3 ovStyle
    class CS1,CS2,CS3 csStyle
    class DS1,DS2,DS3 dsStyle
    class GM,DEP gaStyle
    class GN1,GN2,GN3 gnStyle
    class SM1,SM2 smStyle
    class NM1,NM2 nmStyle

    style OV fill:#1e3a8a22,stroke:#1e40af,color:#93c5fd
    style CS fill:#92400e22,stroke:#b45309,color:#fbbf24
    style DS fill:#065f4622,stroke:#047857,color:#34d399
    style GA fill:#5b21b622,stroke:#6d28d9,color:#a78bfa
    style GN fill:#6d28d922,stroke:#7c3aed,color:#c4b5fd
    style SM fill:#155e7522,stroke:#0e7490,color:#22d3ee
    style NM fill:#991b1b22,stroke:#b91c1c,color:#f87171
```

- **Overview** — one-screen orientation: what this is, which gaps exist, and what order to tackle them
- **Current State** — grounded in codebase exploration with file:line citations and architecture diagrams
- **Desired State** — informed by SOTA research with verified external citations (no hallucinated URLs)
- **Gap Analysis** — each gap has concrete deliverables (Output(s)), code-level References for agentic execution, and ADRs tracking every design decision
- **Success Measures** — anchored to your project's actual CI gates (not vague aspirations), plus domain-specific measures per gap
- **Negative Measures** — Type 2 failures where it *looks* done but silently isn't — discovered by scanning your project's own rules and historical gotchas



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
