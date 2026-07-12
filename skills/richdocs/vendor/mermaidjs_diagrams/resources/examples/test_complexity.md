# Mermaid Complexity — Lint Test Fixtures

Each ```mermaid fence below is a named scenario designed to exercise one
specific `LintCode` produced by `scripts/mermaid_complexity.ts`. Run with the
**high-density preset** (the default) to see the expected findings:

```bash
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts \
  .claude/skills/mermaidjs_diagrams/resources/examples/test_complexity.md
```

## Expected lint output

Under the default (high-density) preset — `node_acceptable=35`,
`node_complex=50`, `node_hard_limit=100`, `vcs_acceptable=60`,
`vcs_complex=100`:

| Scenario                            | Expected code                          | Severity |
|-------------------------------------|----------------------------------------|----------|
| Clean flowchart                     | *(no finding)*                         | —        |
| Clean architecture-beta             | *(no finding)*                         | —        |
| Nodes just over acceptable (36)     | `NodeCountExceedsAcceptable`           | warning  |
| Nodes at cognitive limit (51)       | `NodeCountExceedsCognitiveLimit`       | error    |
| Nodes beyond hard limit (120)       | `NodeCountExceedsHardLimit`            | error    |
| VCS over acceptable (edge-heavy)    | `VisualComplexityExceedsAcceptable`    | warning  |
| VCS beyond critical (very dense)    | `VisualComplexityExceedsCritical`      | error    |
| Subgraph nested 3 deep              | `SubgraphNestingTooDeep`               | warning  |
| JISON diagram with no DOM (block)   | `ParserFailure`                        | error    |
| Subdivision with named boundaries   | `NodeCountExceedsCognitiveLimit` +     | error    |
|                                     | boundaries populated                   |          |

Short-circuit rule: when `ParserFailure` fires on a diagram, no other codes
are emitted for that diagram — the parser couldn't read it, so threshold
checks against garbage metrics would be misleading.

---

## Canonical diagram-kind support matrix

Every Mermaid diagram kind the canonical parser supports has a clean fixture
in the file:

- **§1–§2** and **§11–§30**: clean, below-threshold — the linter MUST emit
  **no findings** for these fences. If any of them start flagging, either
  the upstream parser regressed or our extraction adapter drifted.
- **§3–§10**: threshold-violation scenarios — each is designed to trigger
  one specific `LintCode`. Expected findings are enumerated in the "Expected
  lint output" table above.

| Fence | Diagram kind | Parser path | Extraction adapter |
|-------|--------------|-------------|--------------------|
| §1    | `flowchart`          | mermaid-core | `adaptFlowchart` |
| §2    | `architecture-beta`  | langium      | `extractLangiumStats` |
| §11   | `classDiagram`       | mermaid-core | `adaptClass` |
| §12   | `sequenceDiagram`    | mermaid-core | `adaptSequence` |
| §13   | `stateDiagram-v2`    | mermaid-core | `adaptState` |
| §14   | `erDiagram`          | mermaid-core | `adaptEr` |
| §15   | `journey`            | mermaid-core | `adaptJourney` |
| §16   | `mindmap`            | mermaid-core | `adaptMindmap` |
| §17   | `gantt`              | mermaid-core | `adaptGantt` |
| §18   | `pie`                | langium      | `extractLangiumStats` |
| §19   | `timeline`           | mermaid-core | `adaptTimeline` |
| §20   | `xychart-beta`       | mermaid-core | `adaptXychart` |
| §21   | `sankey-beta`        | mermaid-core | `adaptSankey` |
| §22   | `quadrantChart`      | mermaid-core | `adaptQuadrantChart` |
| §23   | `block-beta`         | mermaid-core | `adaptBlock` |
| §24   | `C4Context`          | mermaid-core | `adaptC4` |
| §25   | `kanban`             | mermaid-core | `adaptKanban` |
| §26   | `gitGraph`           | langium      | `extractLangiumStats` |
| §27   | `packet-beta`        | langium      | `extractLangiumStats` |
| §28   | `radar-beta`         | langium      | `extractLangiumStats` |
| §29   | `treemap-beta`       | langium      | `extractLangiumStats` |
| §30   | `requirementDiagram` | mermaid-core | `adaptRequirement` |

---

## 1. Clean flowchart (no findings)

A small, readable diagram well under every threshold. The linter should emit
no findings for this fence.

```mermaid
flowchart LR
  Client --> API
  API --> DB
  API --> Cache
```

## 2. Clean architecture-beta (no findings)

Langium-parsed, small. Proves the architecture-beta path is quiet when the
diagram is within limits.

```mermaid
architecture-beta
  group svc(cloud)[Services]
  service web(server)[Web] in svc
  service api(server)[API] in svc
  web:R -- L:api
```

## 3. NodeCountExceedsAcceptable — 36 nodes, loosely connected

Just above the `node_acceptable=35` threshold. Expected: one
`NodeCountExceedsAcceptable` (warning). No VCS finding because edges are
sparse enough to keep VCS under `vcs_acceptable=60`.

```mermaid
flowchart LR
  N1[n1] --> N2[n2]
  N3[n3]
  N4[n4]
  N5[n5]
  N6[n6]
  N7[n7]
  N8[n8]
  N9[n9]
  N10[n10]
  N11[n11]
  N12[n12]
  N13[n13]
  N14[n14]
  N15[n15]
  N16[n16]
  N17[n17]
  N18[n18]
  N19[n19]
  N20[n20]
  N21[n21]
  N22[n22]
  N23[n23]
  N24[n24]
  N25[n25]
  N26[n26]
  N27[n27]
  N28[n28]
  N29[n29]
  N30[n30]
  N31[n31]
  N32[n32]
  N33[n33]
  N34[n34]
  N35[n35]
  N36[n36]
```

## 4. NodeCountExceedsCognitiveLimit — 51 nodes

Just above the 50-node Huang 2020 cognitive limit. Expected: one
`NodeCountExceedsCognitiveLimit` (error). Note the waterfall rule —
`NodeCountExceedsAcceptable` is NOT also emitted.

```mermaid
flowchart LR
  N1[n1]
  N2[n2]
  N3[n3]
  N4[n4]
  N5[n5]
  N6[n6]
  N7[n7]
  N8[n8]
  N9[n9]
  N10[n10]
  N11[n11]
  N12[n12]
  N13[n13]
  N14[n14]
  N15[n15]
  N16[n16]
  N17[n17]
  N18[n18]
  N19[n19]
  N20[n20]
  N21[n21]
  N22[n22]
  N23[n23]
  N24[n24]
  N25[n25]
  N26[n26]
  N27[n27]
  N28[n28]
  N29[n29]
  N30[n30]
  N31[n31]
  N32[n32]
  N33[n33]
  N34[n34]
  N35[n35]
  N36[n36]
  N37[n37]
  N38[n38]
  N39[n39]
  N40[n40]
  N41[n41]
  N42[n42]
  N43[n43]
  N44[n44]
  N45[n45]
  N46[n46]
  N47[n47]
  N48[n48]
  N49[n49]
  N50[n50]
  N51[n51]
```

## 5. NodeCountExceedsHardLimit — 120 nodes

Beyond any comprehensible diagram size. Expected:
`NodeCountExceedsHardLimit` (error) with remediation "split immediately".
Also fires `VisualComplexityExceedsCritical` because VCS = 120 > 100.

```mermaid
flowchart TD
  N1[n1]
  N2[n2]
  N3[n3]
  N4[n4]
  N5[n5]
  N6[n6]
  N7[n7]
  N8[n8]
  N9[n9]
  N10[n10]
  N11[n11]
  N12[n12]
  N13[n13]
  N14[n14]
  N15[n15]
  N16[n16]
  N17[n17]
  N18[n18]
  N19[n19]
  N20[n20]
  N21[n21]
  N22[n22]
  N23[n23]
  N24[n24]
  N25[n25]
  N26[n26]
  N27[n27]
  N28[n28]
  N29[n29]
  N30[n30]
  N31[n31]
  N32[n32]
  N33[n33]
  N34[n34]
  N35[n35]
  N36[n36]
  N37[n37]
  N38[n38]
  N39[n39]
  N40[n40]
  N41[n41]
  N42[n42]
  N43[n43]
  N44[n44]
  N45[n45]
  N46[n46]
  N47[n47]
  N48[n48]
  N49[n49]
  N50[n50]
  N51[n51]
  N52[n52]
  N53[n53]
  N54[n54]
  N55[n55]
  N56[n56]
  N57[n57]
  N58[n58]
  N59[n59]
  N60[n60]
  N61[n61]
  N62[n62]
  N63[n63]
  N64[n64]
  N65[n65]
  N66[n66]
  N67[n67]
  N68[n68]
  N69[n69]
  N70[n70]
  N71[n71]
  N72[n72]
  N73[n73]
  N74[n74]
  N75[n75]
  N76[n76]
  N77[n77]
  N78[n78]
  N79[n79]
  N80[n80]
  N81[n81]
  N82[n82]
  N83[n83]
  N84[n84]
  N85[n85]
  N86[n86]
  N87[n87]
  N88[n88]
  N89[n89]
  N90[n90]
  N91[n91]
  N92[n92]
  N93[n93]
  N94[n94]
  N95[n95]
  N96[n96]
  N97[n97]
  N98[n98]
  N99[n99]
  N100[n100]
  N101[n101]
  N102[n102]
  N103[n103]
  N104[n104]
  N105[n105]
  N106[n106]
  N107[n107]
  N108[n108]
  N109[n109]
  N110[n110]
  N111[n111]
  N112[n112]
  N113[n113]
  N114[n114]
  N115[n115]
  N116[n116]
  N117[n117]
  N118[n118]
  N119[n119]
  N120[n120]
```

## 6. VisualComplexityExceedsAcceptable — edge-heavy, node-light

Node count (10) is fine, but 40 interconnecting edges push VCS past 60.
Expected: one `VisualComplexityExceedsAcceptable` (warning). No node-count
finding.

```mermaid
flowchart LR
  A[A] --> B[B]
  A --> C[C]
  A --> D[D]
  A --> E[E]
  A --> F[F]
  B --> C
  B --> D
  B --> E
  B --> F
  B --> G[G]
  C --> D
  C --> E
  C --> F
  C --> G
  C --> H[H]
  D --> E
  D --> F
  D --> G
  D --> H
  D --> I[I]
  E --> F
  E --> G
  E --> H
  E --> I
  E --> J[J]
  F --> G
  F --> H
  F --> I
  F --> J
  G --> H
  G --> I
  G --> J
  H --> I
  H --> J
  I --> J
  J --> A
  J --> B
  J --> C
  J --> D
  J --> E
```

## 7. VisualComplexityExceedsCritical — very dense graph

Many nodes plus many edges. Expected: `VisualComplexityExceedsCritical`
(error), probably alongside `NodeCountExceedsCognitiveLimit` and
`NodeCountExceedsHardLimit` depending on size.

```mermaid
flowchart LR
  A1 --> A2 --> A3 --> A4 --> A5 --> A6 --> A7 --> A8 --> A9 --> A10
  A1 --> B1 --> B2 --> B3 --> B4 --> B5 --> B6 --> B7 --> B8 --> B9 --> B10
  A2 --> C1 --> C2 --> C3 --> C4 --> C5 --> C6 --> C7 --> C8 --> C9 --> C10
  A3 --> D1 --> D2 --> D3 --> D4 --> D5 --> D6 --> D7 --> D8 --> D9 --> D10
  A4 --> E1 --> E2 --> E3 --> E4 --> E5 --> E6 --> E7 --> E8 --> E9 --> E10
  A5 --> F1 --> F2 --> F3 --> F4 --> F5 --> F6 --> F7 --> F8 --> F9 --> F10
  B1 --> C1
  B2 --> C2
  B3 --> C3
  B4 --> C4
  B5 --> C5
  C1 --> D1
  C2 --> D2
  C3 --> D3
  C4 --> D4
  C5 --> D5
  D1 --> E1
  D2 --> E2
  D3 --> E3
  D4 --> E4
  D5 --> E5
  E1 --> F1
  E2 --> F2
  E3 --> F3
  E4 --> F4
  E5 --> F5
  F10 --> A1
```

## 8. SubgraphNestingTooDeep — 3 levels deep

Structure is small (node count under any threshold) but subgraphs are
nested 3 deep. Expected: one `SubgraphNestingTooDeep` (warning).

```mermaid
flowchart TB
  subgraph Outer
    subgraph Middle
      subgraph Inner
        X1[leaf] --> X2[leaf]
      end
    end
  end
```

## 9. ParserFailure — JISON block diagram without DOM

`block` is a JISON-parsed diagram type that needs a real DOM to extract
structure. Headless Bun + happy-dom can't parse it → 0 nodes → ParserFailure.
Expected: one `ParserFailure` (error) and **no other codes** for this fence
(short-circuit rule).

```mermaid
block
columns 3
  a["Alpha"]
  b["Beta"]
  c["Gamma"]
  d["Delta"]
  e["Epsilon"]
  f["Zeta"]
  a --> d
  b --> e
  c --> f
```

## 10. Subdivision with named boundaries — NodeCountExceedsCognitiveLimit + boundaries[]

Large flowchart with 4 named subgraphs. Expected:
`NodeCountExceedsCognitiveLimit` (error) where `boundaries` contains
["Ingress", "Web", "App", "Data"] so an LLM receiving the JSON can pick
split anchors by name, not by guesswork.

```mermaid
flowchart LR
  subgraph Ingress
    I1[i1] --> I2[i2] --> I3[i3] --> I4[i4]
    I4 --> I5[i5] --> I6[i6] --> I7[i7]
    I7 --> I8[i8] --> I9[i9] --> I10[i10]
    I10 --> I11[i11] --> I12[i12] --> I13[i13]
  end
  subgraph Web
    W1[w1] --> W2[w2] --> W3[w3] --> W4[w4]
    W4 --> W5[w5] --> W6[w6] --> W7[w7]
    W7 --> W8[w8] --> W9[w9] --> W10[w10]
    W10 --> W11[w11] --> W12[w12] --> W13[w13]
  end
  subgraph App
    P1[p1] --> P2[p2] --> P3[p3] --> P4[p4]
    P4 --> P5[p5] --> P6[p6] --> P7[p7]
    P7 --> P8[p8] --> P9[p9] --> P10[p10]
    P10 --> P11[p11] --> P12[p12] --> P13[p13]
  end
  subgraph Data
    D1[d1] --> D2[d2] --> D3[d3] --> D4[d4]
    D4 --> D5[d5] --> D6[d6] --> D7[d7]
    D7 --> D8[d8] --> D9[d9] --> D10[d10]
    D10 --> D11[d11] --> D12[d12] --> D13[d13]
  end
  I13 --> W1
  W13 --> P1
  P13 --> D1
```

---

## 11. Clean classDiagram (no findings)

`adaptClass` reads `db.classes` (Map) and `db.relations` (Array).

```mermaid
classDiagram
  class Animal {
    +String name
    +eat()
    +sleep()
  }
  class Dog {
    +String breed
    +bark()
  }
  class Cat {
    +purr()
  }
  Animal <|-- Dog
  Animal <|-- Cat
```

## 12. Clean sequenceDiagram (no findings)

`adaptSequence` reads `db.state.records.actors` (Map) and `db.state.records.messages` (Array).

```mermaid
sequenceDiagram
  actor User
  participant Gateway
  participant Service
  participant DB

  User->>Gateway: request
  Gateway->>Service: forward
  Service->>DB: query
  DB-->>Service: rows
  Service-->>Gateway: response
  Gateway-->>User: 200 OK
```

## 13. Clean stateDiagram-v2 (no findings)

`adaptState` reads the stateDiagram DB's nodes and links.

```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Loading : fetch()
  Loading --> Ready : success
  Loading --> Error : failure
  Ready --> Idle : reset()
  Error --> Idle : retry()
  Ready --> [*]
```

## 14. Clean erDiagram (no findings)

`adaptEr` reads `db.entities` (Map) and `db.relationships` (Array). ERDs parse
cleanly under headless Bun + happy-dom — the adapter extracts the entities
directly from the populated DB.

```mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
  ORDER ||--|{ ORDER_LINE : contains
  ORDER_LINE }o--|| PRODUCT : "refers to"
  CUSTOMER ||--o{ ADDRESS : has
  ORDER }o--|| ADDRESS : "ships to"
  PRODUCT }o--|| CATEGORY : "belongs to"
```

## 15. Clean journey diagram (no findings)

```mermaid
journey
  title Morning routine
  section Wake up
    Open eyes: 3: Me
    Stretch:   4: Me
  section Kitchen
    Make coffee: 5: Me
    Check email: 2: Me
```

## 16. Clean mindmap (no findings)

```mermaid
mindmap
  root((System))
    Ingress
      CDN
      Load Balancer
    Compute
      API
      Worker
    Data
      Cache
      Primary DB
```

## 17. Clean gantt (no findings)

```mermaid
gantt
  title Release schedule
  dateFormat YYYY-MM-DD
  section Backend
    Design       :a1, 2026-01-01, 5d
    Implement    :a2, after a1, 10d
  section Frontend
    Wireframes   :b1, 2026-01-01, 4d
    Build        :b2, after b1, 12d
```

## 18. Clean pie (no findings)

Langium-parsed.

```mermaid
pie title Traffic by source
  "Organic search" : 45
  "Direct" : 25
  "Referral" : 15
  "Social" : 15
```

## 19. Clean timeline (no findings)

```mermaid
timeline
  title Project milestones
  2024 : Kickoff
       : Discovery
  2025 : Alpha release
       : Beta release
  2026 : GA
```

## 20. Clean xychart-beta (no findings)

```mermaid
xychart-beta
  title "Revenue by quarter"
  x-axis [Q1, Q2, Q3, Q4]
  y-axis "Revenue (USD)" 0 --> 1000000
  bar [250000, 420000, 680000, 910000]
```

## 21. Clean sankey-beta (no findings)

```mermaid
sankey-beta

source,target,value
Revenue,Salaries,400
Revenue,Infrastructure,150
Revenue,Marketing,120
Revenue,Reserves,80
```

## 22. Clean quadrantChart (no findings)

```mermaid
quadrantChart
  title Effort vs impact
  x-axis Low effort --> High effort
  y-axis Low impact --> High impact
  quadrant-1 Do now
  quadrant-2 Plan
  quadrant-3 Defer
  quadrant-4 Reconsider
  "Feature A": [0.7, 0.8]
  "Feature B": [0.3, 0.6]
  "Feature C": [0.2, 0.2]
  "Feature D": [0.8, 0.3]
```

## 23. Clean block-beta (no findings)

`adaptBlock` walks the block tree recursively; synthetic `space`/`composite`
wrappers are excluded from the user-visible node count.

```mermaid
block-beta
  columns 3
  a["Alpha"]
  b["Beta"]
  c["Gamma"]
  d["Delta"]
  e["Epsilon"]
  f["Zeta"]
  a --> d
  b --> e
  c --> f
```

## 24. Clean C4Context (no findings)

`adaptC4` excludes the synthetic top-level `global` boundary.

```mermaid
C4Context
  title System context — Acme Platform
  Person(customer, "Customer", "Uses the web and mobile apps")
  System(platform, "Acme Platform", "Core offering")
  System_Ext(payments, "Stripe", "Payment processor")
  Rel(customer, platform, "Browses & purchases")
  Rel(platform, payments, "Charges via API", "HTTPS/JSON")
```

## 25. Clean kanban (no findings)

```mermaid
kanban
  Todo
    task1[Task 1]
    task2[Task 2]
  Doing
    task3[Task 3]
  Done
    task4[Task 4]
    task5[Task 5]
```

## 26. Clean gitGraph (no findings)

Langium-parsed.

```mermaid
gitGraph
  commit id: "initial"
  commit id: "add tests"
  branch feature
  commit id: "draft impl"
  commit id: "polish"
  checkout main
  merge feature
  commit id: "release"
```

## 27. Clean packet-beta (no findings)

Langium-parsed.

```mermaid
packet-beta
  title TCP segment header (simplified)
  0-15: "Source port"
  16-31: "Destination port"
  32-63: "Sequence number"
  64-95: "Acknowledgement number"
```

## 28. Clean radar-beta (no findings)

Langium-parsed.

```mermaid
radar-beta
  axis Speed, Reliability, Cost, Security, UX
  curve baseline["v1 baseline"]{3, 4, 2, 3, 3}
  curve target["v2 target"]{4, 5, 3, 4, 4}
```

## 29. Clean treemap-beta (no findings)

Langium-parsed.

```mermaid
treemap-beta
  title Budget allocation
  "Engineering": 40
  "Product": 20
  "Design": 15
  "Operations": 15
  "Marketing": 10
```

## 30. Clean requirementDiagram (no findings)

`adaptRequirement` reads `db.requirements` + `db.elements` (both Maps) and
`db.relations` (Array).

```mermaid
requirementDiagram

requirement auth_req {
id: REQ_001
text: Users must authenticate before accessing protected resources
risk: high
verifymethod: test
}

element login_service {
type: service
}

login_service - satisfies -> auth_req
```
