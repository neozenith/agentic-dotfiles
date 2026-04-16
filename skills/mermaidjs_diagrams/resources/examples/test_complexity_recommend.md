# Mermaid Complexity — Failures & Recommended Fixes

Companion to `test_complexity.md`. Each section pairs a **❌ failing diagram**
(triggering one specific `LintCode`) with the **recommended remediation** and
a **✅ fixed diagram** that passes under the default `high` preset. Every
example uses realistic system content so the failure mode is recognizable
from real projects, not abstract `n1, n2, n3` stand-ins.

Run with:

```bash
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts \
  .claude/skills/mermaidjs_diagrams/resources/examples/test_complexity_recommend.md
```

Only the ❌ fences should produce findings. Each ✅ fence should be silent —
if the tool flags a ✅ fence, the fix recipe has drifted and this file needs
updating.

## At-a-glance recipe card

| Finding | First-line fix |
|---------|----------------|
| `NodeCountExceedsAcceptable` | Group related nodes into a `subgraph` block, or collapse leaf clusters into one representative node. |
| `NodeCountExceedsCognitiveLimit` | Split into an **overview** (<=12 nodes) plus **per-subsystem detail** diagrams — see `resources/diagram_organization.md` dual-density pattern. |
| `NodeCountExceedsHardLimit` | Stop drawing. This is a dump, not a diagram. Redesign: pick a lens, pick a level of abstraction, start from scratch. |
| `VisualComplexityExceedsAcceptable` | Delete redundant edges. Introduce a mediating node (API gateway, event bus, service mesh). Enable `elk.mergeEdges: true`. |
| `VisualComplexityExceedsCritical` | Split by **lens** (architecture vs data-flow vs sequence), not just by component. Same nodes, different edge set per diagram. |
| `SubgraphNestingTooDeep` | Flatten to depth <=2. Replace the innermost subgraph with a separate diagram referenced by link, or compound labels on the parent level. |
| `ParserFailure` | Fix the syntax error. Cross-reference `test_complexity.md` §1–§2 and §11–§30 for the canonical syntax of each supported diagram kind. |
| `ParserDegraded` | Warn that the canonical parser fell back to regex and metrics are approximate. Same fixes as `ParserFailure`; rewrite in a canonical form the parser handles. |

> **Alternative fix pattern** for `NodeCountExceedsCognitiveLimit` and
> `NodeCountExceedsHardLimit` when you have multiple semi-independent
> subsystems: **hierarchical decomposition with compound "See Sub-Diagram
> X" pointers**. See [§8](#8-hierarchical-decomposition--see-sub-diagram-pointers)
> below.

## Pick the right diagram kind first

Half of the complexity findings below originate from using a `flowchart` for
content that *wasn't* actually a flow. Before drawing, ask what the diagram
is *for*:

| Intent | Right diagram kind |
|--------|-------------------|
| Static component structure, service boundaries, module layout | `flowchart` or `architecture-beta` |
| Temporal interaction between a small number of actors | `sequenceDiagram` |
| Data-model entities and their relationships | `erDiagram` |
| Finite states + transitions | `stateDiagram-v2` |
| Hierarchical concepts radiating from a root | `mindmap` (with `layout: tidy-tree`) |

Every diagram kind above parses cleanly under the canonical mermaid parser
in this skill's headless lint pipeline — see `test_complexity.md` §11–§30
for a working fixture of each. Picking the wrong kind (e.g. drawing an ERD
as a `flowchart` with 10 edges labelled "fk") produces a *complexity*
finding, not a *parser* finding — because flowcharts balloon in VCS when
they're asked to carry relational semantics.

---

## 1. NodeCountExceedsAcceptable — flat microservices catalogue

### ❌ Negative example

Every microservice drawn alongside its owned store. 18 services × (service +
store) = 36 nodes. The services are real; the flat layout is the problem —
the reader can't tell what's a platform primitive vs. a domain service vs.
a third-party integration.

```mermaid
flowchart LR
  auth[auth-service] --> auth_db[(users_auth)]
  sso[sso-gateway] --> sso_db[(sso_sessions)]
  billing[billing-service] --> billing_db[(billing_ledger)]
  invoicing[invoicing-service] --> invoice_db[(invoices)]
  subscriptions[subscriptions-service] --> subs_db[(subscriptions)]
  catalog[catalog-service] --> catalog_db[(products)]
  search[search-service] --> search_idx[(elasticsearch)]
  recommendations[recs-service] --> recs_cache[(redis_recs)]
  reviews[reviews-service] --> reviews_db[(reviews)]
  orders[orders-service] --> orders_db[(orders)]
  cart[cart-service] --> cart_cache[(redis_carts)]
  checkout[checkout-service] --> checkout_q[[sqs_checkouts]]
  inventory[inventory-service] --> inventory_db[(inventory)]
  warehouse[warehouse-service] --> warehouse_db[(fulfillment)]
  shipping[shipping-service] --> shipping_db[(shipments)]
  notifications[notifications-service] --> notif_q[[sns_notifications]]
  email[email-service] --> sendgrid[/Sendgrid API/]
  sms[sms-service] --> twilio[/Twilio API/]
```

### Expected finding

```text
test_complexity_recommend.md:N-M: NodeCountExceedsAcceptable 36 nodes > 35 acceptable threshold
```

### Recommendation

An 18-pair service→store catalogue is a *catalogue*, not an architecture
diagram. The reader can't see structure at this density. Two canonical
fixes:

1. **Group by responsibility domain.** Most services fall into 3–5 business
   domains (Identity, Commerce, Content, Fulfillment, Communications). Wrap
   each in a `subgraph`.
2. **Drop the per-service store when it's implied.** "Every service owns
   its own DB" is the microservices convention; showing 18 copies of it
   communicates nothing. Reserve store nodes for data that's *shared*
   across services, or when a store type (queue vs. cache vs. RDBMS) is
   itself a design point worth calling out.

### ✅ Positive example

```mermaid
flowchart LR
  subgraph Identity
    auth[auth-service]
    sso[sso-gateway]
  end
  subgraph Commerce
    billing[billing-service]
    subscriptions[subscriptions-service]
    cart[cart-service]
    checkout[checkout-service]
    orders[orders-service]
  end
  subgraph Content
    catalog[catalog-service]
    search[search-service]
    recs[recs-service]
    reviews[reviews-service]
  end
  subgraph Fulfillment
    inventory[inventory-service]
    warehouse[warehouse-service]
    shipping[shipping-service]
  end
  subgraph Communications
    notifications[notifications-service]
    email[email-service]
    sms[sms-service]
  end
  ops_store[(shared operational store)]
  Commerce --> ops_store
  Fulfillment --> ops_store
  Identity --> ops_store
```

---

## 2. NodeCountExceedsCognitiveLimit — per-source pipeline stages

### ❌ Negative example

A realistic ELT pipeline that forgot to abstract: every SaaS source gets
its own landing table, its own normalizer, its own enricher, and its own
publish destination. 10 sources × 5 stages + 1 orchestrator = 51 nodes.

```mermaid
flowchart LR
  %% Sources (10)
  stripe[Stripe] --> raw_stripe[(raw.stripe)]
  segment[Segment] --> raw_segment[(raw.segment)]
  hubspot[HubSpot] --> raw_hubspot[(raw.hubspot)]
  salesforce[Salesforce] --> raw_salesforce[(raw.salesforce)]
  mixpanel[Mixpanel] --> raw_mixpanel[(raw.mixpanel)]
  amplitude[Amplitude] --> raw_amplitude[(raw.amplitude)]
  intercom[Intercom] --> raw_intercom[(raw.intercom)]
  zendesk[Zendesk] --> raw_zendesk[(raw.zendesk)]
  pagerduty[PagerDuty] --> raw_pagerduty[(raw.pagerduty)]
  github[GitHub] --> raw_github[(raw.github)]
  %% Normalize per-source (10)
  raw_stripe --> norm_stripe[norm_stripe]
  raw_segment --> norm_segment[norm_segment]
  raw_hubspot --> norm_hubspot[norm_hubspot]
  raw_salesforce --> norm_salesforce[norm_salesforce]
  raw_mixpanel --> norm_mixpanel[norm_mixpanel]
  raw_amplitude --> norm_amplitude[norm_amplitude]
  raw_intercom --> norm_intercom[norm_intercom]
  raw_zendesk --> norm_zendesk[norm_zendesk]
  raw_pagerduty --> norm_pagerduty[norm_pagerduty]
  raw_github --> norm_github[norm_github]
  %% Enrich per-source (10)
  norm_stripe --> enrich_revenue[enrich_revenue]
  norm_segment --> enrich_events[enrich_events]
  norm_hubspot --> enrich_company[enrich_company]
  norm_salesforce --> enrich_deals[enrich_deals]
  norm_mixpanel --> enrich_sessions[enrich_sessions]
  norm_amplitude --> enrich_funnels[enrich_funnels]
  norm_intercom --> enrich_conversations[enrich_convos]
  norm_zendesk --> enrich_tickets[enrich_tickets]
  norm_pagerduty --> enrich_incidents[enrich_incidents]
  norm_github --> enrich_commits[enrich_commits]
  %% Publish per-destination (10)
  enrich_revenue --> snowflake[(Snowflake)]
  enrich_events --> bigquery[(BigQuery)]
  enrich_company --> dbt_marts[(dbt marts)]
  enrich_deals --> looker[Looker]
  enrich_sessions --> tableau[Tableau]
  enrich_funnels --> hex[Hex]
  enrich_conversations --> retool[Retool]
  enrich_tickets --> sigma[Sigma]
  enrich_incidents --> metabase[Metabase]
  enrich_commits --> grafana[Grafana]
  %% Orchestrator (1)
  airflow[Airflow DAG]
```

### Expected findings

```text
test_complexity_recommend.md:N-M: NodeCountExceedsCognitiveLimit 51 nodes > 50 (Huang 2020 cognitive limit)
test_complexity_recommend.md:N-M: VisualComplexityExceedsAcceptable VCS 76.0 > 60 acceptable threshold
```

Two codes co-fire: VCS codes do **not** waterfall under node-count codes
because they measure different dimensions of cognitive load. A 51-node
pipeline with 50 edges fails both the node cap and the edge-weight cap.

### Recommendation

Huang et al. (2020) identified **50 nodes as the cognitive load threshold**
for comprehension of a node-link diagram. Past that, readers stop tracing
paths and start pattern-matching. The fix for pipeline diagrams specifically
is almost always the same: **collapse the fan-out**. If stage N does the
same thing to every source, draw stage N as one box — don't replicate it
per source.

Apply the dual-density pattern from
`resources/diagram_organization.md`:

1. Keep this 51-node pipeline as a `## Data Pipeline — Detail` section
   wrapped in a `<details>` collapsible for engineers doing a deep dive.
2. Author a new **overview** (<=12 nodes) for the README that collapses
   each per-source stage into one generalized stage. Place it *above* the
   `<details>` block.

### ✅ Positive example

```mermaid
flowchart LR
  sources[10 SaaS sources<br/>Stripe · Segment · HubSpot · ...] --> raw[raw landing<br/>raw.* schemas]
  raw --> normalize[normalize<br/>per-source cleaners]
  normalize --> enrich[enrich<br/>revenue · events · tickets]
  enrich --> warehouse[(Snowflake / BigQuery)]
  warehouse --> bi[BI surfaces<br/>Looker · Tableau · Hex · ...]
  airflow[Airflow DAG] -.->|orchestrates| sources
  airflow -.->|orchestrates| normalize
  airflow -.->|orchestrates| enrich
```

---

## 3. NodeCountExceedsHardLimit — full AWS footprint dump

### ❌ Negative example

An inventory-style dump of a mid-sized team's prod AWS account. Three tiers
× three availability zones × realistic resource mix = 101 nodes. Mermaid
will render it but the image is illegible at any screen size.

```mermaid
flowchart TD
  %% VPC / networking (10)
  vpc_prod[vpc-prod] --> sub_1a[subnet-1a] & sub_1b[subnet-1b] & sub_1c[subnet-1c] & sub_2a[subnet-2a] & sub_2b[subnet-2b] & sub_2c[subnet-2c]
  vpc_prod --> igw[igw-prod] & natgw[natgw-prod] & tgw[tgw-prod]
  %% ALBs (4)
  alb_web[alb-web] & alb_api[alb-api] & alb_admin[alb-admin] & nlb_tcp[nlb-tcp]
  %% EC2 web tier (20)
  web_001[ec2-web-001] & web_002[ec2-web-002] & web_003[ec2-web-003] & web_004[ec2-web-004] & web_005[ec2-web-005] & web_006[ec2-web-006] & web_007[ec2-web-007] & web_008[ec2-web-008] & web_009[ec2-web-009] & web_010[ec2-web-010]
  web_011[ec2-web-011] & web_012[ec2-web-012] & web_013[ec2-web-013] & web_014[ec2-web-014] & web_015[ec2-web-015] & web_016[ec2-web-016] & web_017[ec2-web-017] & web_018[ec2-web-018] & web_019[ec2-web-019] & web_020[ec2-web-020]
  %% EC2 app tier (25)
  app_001[ec2-app-001] & app_002[ec2-app-002] & app_003[ec2-app-003] & app_004[ec2-app-004] & app_005[ec2-app-005] & app_006[ec2-app-006] & app_007[ec2-app-007] & app_008[ec2-app-008] & app_009[ec2-app-009] & app_010[ec2-app-010]
  app_011[ec2-app-011] & app_012[ec2-app-012] & app_013[ec2-app-013] & app_014[ec2-app-014] & app_015[ec2-app-015] & app_016[ec2-app-016] & app_017[ec2-app-017] & app_018[ec2-app-018] & app_019[ec2-app-019] & app_020[ec2-app-020]
  app_021[ec2-app-021] & app_022[ec2-app-022] & app_023[ec2-app-023] & app_024[ec2-app-024] & app_025[ec2-app-025]
  %% EC2 worker tier (15)
  w_001[ec2-worker-001] & w_002[ec2-worker-002] & w_003[ec2-worker-003] & w_004[ec2-worker-004] & w_005[ec2-worker-005] & w_006[ec2-worker-006] & w_007[ec2-worker-007] & w_008[ec2-worker-008]
  w_009[ec2-worker-009] & w_010[ec2-worker-010] & w_011[ec2-worker-011] & w_012[ec2-worker-012] & w_013[ec2-worker-013] & w_014[ec2-worker-014] & w_015[ec2-worker-015]
  %% RDS (6)
  rds_prod[(rds-prod)] & rds_analytics[(rds-analytics)] & rds_audit[(rds-audit)] & rds_reports[(rds-reports)] & rds_legacy[(rds-legacy)] & rds_replica[(rds-replica)]
  %% ElastiCache (4)
  redis_sessions[(redis-sessions)] & redis_cache[(redis-cache)] & redis_ratelimit[(redis-ratelimit)] & redis_queue[(redis-queue)]
  %% Kinesis / SQS (5)
  kinesis_events[[kinesis-events]] & kinesis_audit[[kinesis-audit]] & sqs_jobs[[sqs-jobs]] & sqs_dlq[[sqs-dlq]] & eventbridge[[eventbridge-bus]]
  %% Lambdas (8)
  lambda_ingest[λ lambda-ingest] & lambda_etl[λ lambda-etl] & lambda_email[λ lambda-email] & lambda_webhook[λ lambda-webhook] & lambda_cron[λ lambda-cron] & lambda_resize[λ lambda-resize] & lambda_expire[λ lambda-expire] & lambda_fanout[λ lambda-fanout]
  %% S3 (4)
  s3_assets[(s3-assets)] & s3_backup[(s3-backup)] & s3_logs[(s3-logs)] & s3_data_lake[(s3-data-lake)]
```

### Expected findings

```text
test_complexity_recommend.md:N-M: NodeCountExceedsHardLimit 101 nodes > 100 hard limit
test_complexity_recommend.md:N-M: VisualComplexityExceedsCritical VCS ~105 > 100 critical threshold
```

### Recommendation

Beyond the hard limit, there is **no fix that preserves the diagram**. This
is a signal that the *scope* is wrong: you've attempted to show an entire
account's resource inventory at a single level of abstraction. That isn't
architecture — it's `aws-cli describe-everything`.

1. **Pick a lens.** Is this about request flow? Deployment topology? Cost
   attribution? Blast radius? The lens narrows what to draw.
2. **Pick a level.** Overview (<=12 nodes representing actors / tiers /
   systems) or single-subsystem detail (<=35 nodes inside one boundary).
   Don't mix.
3. **Start over from an empty canvas** at the chosen lens × level. Do not
   try to trim a 101-node inventory to 35 — you'll preserve the wrong
   things.

For the inventory itself, the right tool is a table or a resource-tagging
report, not a diagram.

### ✅ Positive example

The deployment lens at overview level — what actually *flows* through the
stack, ignoring individual instances:

```mermaid
flowchart LR
  user([user]) --> cdn[CloudFront / CDN]
  cdn --> alb[ALB]
  alb --> web[web tier<br/>20× ec2]
  web --> app[app tier<br/>25× ec2]
  app --> data[data tier<br/>RDS + Redis]
  app --> events[[event bus<br/>Kinesis + SQS]]
  events --> workers[worker tier<br/>15× ec2 + λ fleet]
  workers --> data
```

---

## 4. VisualComplexityExceedsAcceptable — no-gateway microservice mesh

### ❌ Negative example

15 real microservices, each calling every other directly — the "polyglot
microservices without a service mesh" anti-pattern. ~105 edges. Nodes stay
under the acceptable cap, but edge density makes the diagram unreadable.

```mermaid
flowchart LR
  auth --> users & billing & orders & inventory & shipping & email & sms & support & audit & analytics & recs & reviews & catalog & notifications
  users --> billing & orders & inventory & shipping & email & sms & support & audit & analytics & recs & reviews & catalog & notifications
  billing --> orders & inventory & shipping & email & sms & support & audit & analytics & recs & reviews & catalog & notifications
  orders --> inventory & shipping & email & sms & support & audit & analytics & recs & reviews & catalog & notifications
  inventory --> shipping & email & sms & support & audit & analytics & recs & reviews & catalog & notifications
  shipping --> email & sms & support & audit & analytics & recs & reviews & catalog & notifications
  email --> sms & support & audit & analytics & recs & reviews & catalog & notifications
  sms --> support & audit & analytics & recs & reviews & catalog & notifications
  support --> audit & analytics & recs & reviews & catalog & notifications
  audit --> analytics & recs & reviews & catalog & notifications
  analytics --> recs & reviews & catalog & notifications
  recs --> reviews & catalog & notifications
  reviews --> catalog & notifications
  catalog --> notifications
```

### Expected finding

```text
test_complexity_recommend.md:N-M: VisualComplexityExceedsAcceptable VCS ~67.5 > 60 acceptable threshold
```

### Recommendation

A diagram where every service touches every other service is an adjacency
matrix with arrows — the wrong tool for the shape. The fix mirrors the
real architectural fix:

1. **Introduce a mediating node.** Reality: services shouldn't call each
   other directly either. Drawing an **API gateway** or **service mesh**
   (istio / linkerd / consul-connect) turns an N² mesh into two N-shaped
   fans — same semantics, 1/7th the visual complexity.
2. **Enable `elk.mergeEdges: true`.** If true peer-to-peer is the actual
   topology, ELK will at least bundle parallel edges into single strokes.
   See `resources/layout_algorithms.md`.
3. **Replace with an event bus.** If the interactions are async, make that
   explicit: services publish to / subscribe from an event stream rather
   than call each other.

### ✅ Positive example

Introduce a mesh. Same 15 services, radically simpler diagram:

```mermaid
---
config:
  layout: elk
  elk: { mergeEdges: true }
---
flowchart LR
  client([client]) --> gateway[API gateway]
  gateway --> mesh{{service mesh<br/>istio}}
  mesh --> auth & users & billing & orders & inventory
  mesh --> shipping & email & sms & support & notifications
  mesh --> audit & analytics & recs & reviews & catalog
```

---

## 5. VisualComplexityExceedsCritical — full-mesh monolith-in-progress

### ❌ Negative example

20 services, fully mutually coupled — the "monolith-being-broken-apart"
state where every extraction still depends on every other. ~190 edges.
VCS soars past the critical threshold.

```mermaid
flowchart LR
  auth --> users & billing & orders & inventory & shipping & email & sms & support & audit & analytics & recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  users --> billing & orders & inventory & shipping & email & sms & support & audit & analytics & recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  billing --> orders & inventory & shipping & email & sms & support & audit & analytics & recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  orders --> inventory & shipping & email & sms & support & audit & analytics & recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  inventory --> shipping & email & sms & support & audit & analytics & recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  shipping --> email & sms & support & audit & analytics & recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  email --> sms & support & audit & analytics & recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  sms --> support & audit & analytics & recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  support --> audit & analytics & recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  audit --> analytics & recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  analytics --> recs & reviews & catalog & notifications & search & cart & checkout & payments & tax
  recs --> reviews & catalog & notifications & search & cart & checkout & payments & tax
  reviews --> catalog & notifications & search & cart & checkout & payments & tax
  catalog --> notifications & search & cart & checkout & payments & tax
  notifications --> search & cart & checkout & payments & tax
  search --> cart & checkout & payments & tax
  cart --> checkout & payments & tax
  checkout --> payments & tax
  payments --> tax
```

### Expected finding

```text
test_complexity_recommend.md:N-M: VisualComplexityExceedsCritical VCS ~115 > 100 critical threshold
```

### Recommendation

"Critical" means a reader would bail before finishing. The answer is
**split by lens**, not by component count. The same 20 services give you:

- **Architecture** lens: what the components *are*, hierarchically.
  Minimal edges (parent-child only).
- **Sequence** lens: how a specific interaction (e.g. checkout) traces
  through a subset of them, temporally.
- **Data flow** lens: how a specific entity (e.g. an order) moves between
  stores.

Readers pick the lens that answers their question; no single diagram tries
to show all three.

### ✅ Positive example — architecture lens

Six domains, 20 services hidden inside them. Tells the structural story:

```mermaid
flowchart LR
  subgraph Identity
    auth
    users
  end
  subgraph Commerce
    cart
    checkout
    orders
    billing
    payments
    tax
  end
  subgraph Content
    catalog
    search
    recs
    reviews
  end
  subgraph Fulfillment
    inventory
    shipping
  end
  subgraph Communications
    notifications
    email
    sms
  end
  subgraph Platform
    audit
    analytics
    support
  end
  Identity --> Commerce --> Fulfillment
  Commerce --> Communications
  Platform -.-> Identity & Commerce & Content & Fulfillment
```

### ✅ Positive example — sequence lens (companion diagram)

For the same 20-service system, the checkout interaction as a sequence
diagram. One specific workflow, temporal, reads top-to-bottom — far
clearer than trying to show all interactions on a single flowchart:

```mermaid
sequenceDiagram
  autonumber
  actor User
  participant Gateway as API gateway
  participant Cart as cart-service
  participant Checkout as checkout-service
  participant Inventory as inventory-service
  participant Payments as payments-service
  participant Orders as orders-service
  participant Notif as notifications-service

  User->>Gateway: POST /checkout
  Gateway->>Cart: GET cart
  Cart-->>Gateway: line items
  Gateway->>Checkout: submit(items)
  Checkout->>Inventory: reserve
  Inventory-->>Checkout: reservation_id
  Checkout->>Payments: charge
  Payments-->>Checkout: payment_id
  Checkout->>Orders: create(order)
  Orders-->>Checkout: order_id
  Checkout->>Notif: order_placed
  Checkout-->>Gateway: 201 order_id
  Gateway-->>User: confirmation page
```

---

## 6. SubgraphNestingTooDeep — AWS org / account / region nesting

### ❌ Negative example

A realistic multi-account cloud topology drawn with 3 levels of nesting:
AWS organization → account → region. Past 2 levels, Mermaid pads inner
boundaries until the diagram is mostly whitespace and readers lose track
of which container they're in.

```mermaid
flowchart TB
  subgraph aws_org[AWS Organization — acme.com]
    subgraph acct_prod[prod account — 111122223333]
      subgraph region_use1[us-east-1]
        prod_use1_web[ec2-web] --> prod_use1_rds[(rds-prod-use1)]
      end
    end
    subgraph acct_staging[staging account — 444455556666]
      subgraph region_use1_stg[us-east-1]
        stg_use1_web[ec2-web] --> stg_use1_rds[(rds-staging-use1)]
      end
    end
  end
```

### Expected finding

```text
test_complexity_recommend.md:N-M: SubgraphNestingTooDeep subgraph nesting depth 3 (≥3) hinders readability
```

### Recommendation

Past 2 levels of nesting, both dagre and elk over-pad inner boundaries and
the render becomes whitespace-heavy. Two fixes:

1. **Promote the inner label onto the middle level.** `prod / us-east-1`
   as a single label replaces a nested region subgraph with a labelled
   node. The hierarchy is still communicated, just without the extra box.
2. **Separate diagrams per leaf.** For genuinely important per-region
   detail (e.g. when regions diverge architecturally), make each region
   its own diagram, linked from a parent overview that shows just
   Organization → Account.

### ✅ Positive example — compound labels, depth 2

```mermaid
flowchart TB
  subgraph aws_org[AWS Organization — acme.com]
    prod_use1[prod / us-east-1]
    prod_usw2[prod / us-west-2]
    staging_use1[staging / us-east-1]
    dev_use1[dev / us-east-1]
  end
  prod_use1 --> ec2_prod_use1[ec2-web-asg] & rds_prod_use1[(rds-prod)]
  prod_usw2 --> ec2_prod_usw2[ec2-web-asg] & rds_prod_usw2[(rds-prod-dr)]
  staging_use1 --> ec2_stg[ec2-web] & rds_stg[(rds-staging)]
  dev_use1 --> ec2_dev[ec2-web] & rds_dev[(rds-dev)]
```

---

## 7. ParserFailure — genuinely unparseable fence

### ❌ Negative example — unknown diagram keyword

The canonical `@mermaid-js/parser` doesn't recognise the diagram kind and
the fence yields 0 nodes, firing `ParserFailure` (error).

```mermaid
not_a_known_diagram_type
  alpha
  beta
```

### Expected finding

```text
test_complexity_recommend.md:N-M: ParserFailure not_a_known_diagram_type yielded 0 nodes from multi-line source (parser: mermaid-core)
```

`ParserFailure` short-circuits every other check for the fence — when the
parser returns 0 nodes, node-count and VCS metrics would be meaningless, so
the linter suppresses all other codes for that block.

A sibling code, `ParserDegraded` (warning), fires when the canonical
parser extracted *something* via regex fallback but not a real AST. Treat
its numbers as approximate.

### Recommendation

Every mermaid diagram kind the skill supports parses cleanly via canonical
parsers — see `test_complexity.md` §1–§2 and §11–§30 for working fixtures
of each (`flowchart`, `architecture-beta`, `classDiagram`, `sequenceDiagram`,
`stateDiagram-v2`, `erDiagram`, `journey`, `mindmap`, `gantt`, `pie`,
`timeline`, `xychart-beta`, `sankey-beta`, `quadrantChart`, `block-beta`,
`C4Context`, `kanban`, `gitGraph`, `packet-beta`, `radar-beta`,
`treemap-beta`, `requirementDiagram`). If one of these trips
`ParserFailure` in your diagram but not in the fixture, the difference is
syntax-level — your fence has an author error, not a tooling limitation.

Common author-error causes:

| Cause | Fix |
|-------|-----|
| Typo in the diagram keyword (`flochart` → `flowchart`) | Spell it right |
| Unterminated `subgraph` / `end` blocks | Match them up |
| Grammar-level syntax error (e.g. hyphen in a `requirementDiagram` id like `REQ-001` — grammar allows alphanumerics + `_` only) | Use the canonical syntax — cross-reference with the `test_complexity.md` fixture for the diagram kind |
| Mermaid version mismatch — fence uses syntax newer than `@mermaid-js/parser` in `scripts/package.json` | Update the package, or revise the fence |

### ✅ Positive example — canonical flowchart

The same intent as the unknown-keyword fence, expressed as a valid
flowchart:

```mermaid
flowchart LR
  alpha --> beta
```

---

## 8. Hierarchical decomposition — "See Sub-Diagram" pointers

An alternative to the dual-density pattern (§2's "overview +
`<details>`-collapsed detail"). When a system has **multiple
semi-independent subsystems**, each deserving its own reference diagram,
the cleaner shape is an **overview full of dotted-border compound nodes**,
each of which links to its own dedicated sub-diagram section below.

Think UML package diagrams, but Mermaid-native and clickable in rendered
HTML.

### ❌ Negative example

Full e-commerce platform drawn as one diagram with every subsystem
exploded. 54 nodes, modest edge density, but no reader can hold all of
this in working memory — they'd give up before finishing the trace.

```mermaid
flowchart LR
  %% Actors (3)
  customer([customer]) & admin([admin]) & support_agent([support])
  %% Identity (5)
  auth[auth] & sso[sso] & users[users] & permissions[permissions] & audit[audit]
  %% Commerce (8)
  cart[cart] & checkout[checkout] & orders[orders] & billing[billing] & payments[payments] & tax[tax] & coupons[coupons] & refunds[refunds]
  %% Content (6)
  catalog[catalog] & search[search] & recs[recs] & reviews[reviews] & ratings[ratings] & cms[cms]
  %% Fulfillment (7)
  inventory[inventory] & warehouse[warehouse] & pickers[pickers] & packers[packers] & shipping[shipping] & tracking[tracking] & returns[returns]
  %% Communications (5)
  notifications[notifications] & email[email] & sms[sms] & push[push] & slack[slack]
  %% Analytics (4)
  events[events] & metrics[metrics] & reporting[reporting] & dashboards[dashboards]
  %% Support (4)
  tickets[tickets] & chat[chat] & knowledge[knowledge] & feedback[feedback]
  %% Platform (4)
  gateway[api gateway] & mesh[service mesh] & ops_db[(ops db)] & cache[(redis)]
  %% External (3)
  stripe[/Stripe/] & sendgrid[/Sendgrid/] & twilio[/Twilio/]
  %% Queue (2)
  queue[[sqs]] & search_idx[(elasticsearch)]
  %% Entry paths
  customer --> gateway --> auth --> users
  customer --> cart --> checkout --> payments --> stripe
  checkout --> orders --> inventory --> warehouse --> shipping --> tracking
  orders --> billing
  checkout --> tax & coupons
  orders --> notifications --> email --> sendgrid
  notifications --> sms --> twilio
  admin --> permissions
  support_agent --> tickets
  search --> search_idx
  events --> metrics --> dashboards
```

### Expected finding

```text
test_complexity_recommend.md:N-M: NodeCountExceedsCognitiveLimit 51 nodes > 50 (Huang 2020 cognitive limit)
test_complexity_recommend.md:N-M: VisualComplexityExceedsAcceptable VCS 63.5 > 60 acceptable threshold
```

### Recommendation

When the system decomposes into **≥4 subsystems, each meaningful on its
own**, don't collapse them into a `<details>` block together — break each
out into its own reference diagram and have the parent **point at them**.

Three Mermaid features make this work:

| Feature | Purpose | Snippet |
|---------|---------|---------|
| `classDef` with `stroke-dasharray` | Dotted-border visual cue that a node represents "something elaborated elsewhere" | `classDef compound stroke-dasharray:5 5,stroke-width:2px,fill:#f5f5f5` |
| Markdown node labels (Mermaid ≥ 10.7) | In-label italic "_See Sub-Diagram X_" signalling the pointer intent | `commerce["\`**Commerce**<br/>*See Sub-Diagram 2*\`"]` |
| `click` directive | Makes the compound node a hyperlink in GitHub/GitLab rendering, jumping to the sub-diagram's anchor | `click commerce "#sub-diagram-2-commerce" "Commerce detail"` |

Each sub-diagram lives in its own `### Sub-Diagram N — {name}` section and
has its own complexity budget (<=35 nodes, VCS <=60). Readers navigate
top-down: see the parent, click the compound node they care about, land on
a self-contained detail diagram.

### ✅ Overview — compound-node pointers

```mermaid
flowchart LR
  customer([customer])
  admin([admin])
  gateway[API gateway]

  customer --> gateway
  admin --> gateway

  gateway --> identity
  gateway --> commerce
  gateway --> content

  commerce --> fulfillment
  commerce --> communications
  commerce -.->|emits| analytics
  fulfillment -.->|emits| analytics

  identity["`**Identity**
  *See Sub-Diagram 1*`"]
  commerce["`**Commerce**
  *See Sub-Diagram 2*`"]
  content["`**Content**
  *See Sub-Diagram 3*`"]
  fulfillment["`**Fulfillment**
  *See Sub-Diagram 4*`"]
  communications["`**Communications**
  *(subsystem — TBD)*`"]
  analytics["`**Analytics**
  *(subsystem — TBD)*`"]

  classDef compound stroke-dasharray:5 5,stroke-width:2px,fill:#f5f5f5
  class identity,commerce,content,fulfillment,communications,analytics compound

  click identity "#sub-diagram-1--identity" "Identity subsystem detail"
  click commerce "#sub-diagram-2--commerce" "Commerce subsystem detail"
  click content "#sub-diagram-3--content" "Content subsystem detail"
  click fulfillment "#sub-diagram-4--fulfillment" "Fulfillment subsystem detail"
```

Nine nodes, well under every budget. Dotted-border compound nodes
visually distinguish "this box represents a separately-documented
subsystem" from concrete entities like the gateway or actor nodes. The
`click` directives turn the rendered diagram into a clickable table of
contents.

### Sub-Diagram 1 — Identity

```mermaid
flowchart LR
  user([user]) --> gateway[API gateway]
  gateway --> auth[auth-service]
  gateway --> sso[sso-gateway]
  auth --> users[users-service]
  sso --> users
  users --> permissions[permissions-service]
  permissions --> audit[audit-log]
  auth --> session_store[(redis-sessions)]
  users --> users_db[(users_auth)]
```

### Sub-Diagram 2 — Commerce

```mermaid
flowchart LR
  gateway[API gateway] --> cart[cart-service]
  cart --> checkout[checkout-service]
  checkout --> tax[tax-service]
  checkout --> coupons[coupons-service]
  checkout --> payments[payments-service]
  payments --> stripe[/Stripe/]
  checkout --> orders[orders-service]
  orders --> billing[billing-service]
  orders --> refunds[refunds-service]
  cart --> cart_cache[(redis-carts)]
  orders --> orders_db[(orders)]
  billing --> billing_db[(billing_ledger)]
```

### Sub-Diagram 3 — Content

```mermaid
flowchart LR
  user([user]) --> catalog[catalog-service]
  catalog --> catalog_db[(products)]
  user --> search[search-service]
  search --> search_idx[(elasticsearch)]
  user --> recs[recs-service]
  recs --> recs_cache[(redis-recs)]
  catalog --> reviews[reviews-service]
  reviews --> ratings[ratings-service]
  reviews --> reviews_db[(reviews)]
  catalog --> cms[cms-service]
```

### Sub-Diagram 4 — Fulfillment

```mermaid
flowchart LR
  orders[orders-service] --> inventory[inventory-service]
  inventory --> warehouse[warehouse-service]
  warehouse --> pickers[pickers-team]
  pickers --> packers[packers-team]
  packers --> shipping[shipping-service]
  shipping --> tracking[tracking-service]
  tracking --> returns[returns-service]
  inventory --> inventory_db[(inventory)]
  shipping --> shipping_db[(shipments)]
```

### Tradeoffs vs. dual-density

| Criterion | Dual-density (§2 fix) | Hierarchical decomposition (§8 fix) |
|-----------|----------------------|--------------------------------------|
| When to pick | One diagram has one natural overview ↔ detail axis | Several semi-independent subsystems, each worth its own focused diagram |
| Maintenance cost | Low — two fences in one section | Higher — N+1 sub-sections, each with its own budget, anchors to keep in sync |
| Readability | Reader sees the whole detail if they expand | Reader follows clickable breadcrumbs, never sees "all detail at once" |
| README suitability | Excellent — collapsed detail keeps the page short | Excellent for dedicated `docs/architecture.md`; heavy for README landing page |
| Complexity analyzer behaviour | Each fence scored independently; both budgeted | Each sub-diagram scored independently; overview stays tiny by design |
| Breaks when… | The "detail" exceeds 35 nodes even after collapsing | You add a new subsystem and forget to also author its Sub-Diagram section |

Use dual-density as the default. Reach for hierarchical decomposition
when the "detail" side of dual-density is itself past 35 nodes or covers
≥4 clearly-separable subsystems — that's the signal the diagram has
outgrown the single-section pattern.
