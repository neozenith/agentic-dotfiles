# Iconify `mdi` Icon Reference

Quick-reference for `(mdi:<slug>)` in Mermaid `architecture-beta` diagrams.
Equivalent to `diagrams.programming.flowchart` — generic shapes for any concept
not covered by brand logos or cloud-specific sets.

[Material Design Icons](https://pictogrammers.com/library/mdi/) has 7,000+ icons.
Install: `npm install @iconify-json/mdi`

---

## Infrastructure

```
mdi:server                  # Generic compute / server
mdi:server-network          # Server cluster / farm
mdi:server-outline          # Hollow server (lighter weight)
mdi:laptop                  # Client machine / workstation
mdi:desktop-classic         # Desktop client
mdi:cellphone               # Mobile client
mdi:tablet                  # Tablet client
mdi:router-network          # Network router
mdi:router-wireless         # WiFi router
mdi:switch                  # Network switch
mdi:firewall                # Firewall appliance
mdi:cpu-64-bit              # Processing / compute
mdi:memory                  # RAM / memory
mdi:harddisk                # Block storage / disk
mdi:nas                     # Network attached storage
mdi:tape-drive              # Tape / cold storage
mdi:gpu                     # GPU / accelerated compute
```

## Data & Databases

```
mdi:database                # Generic relational DB
mdi:database-outline        # DB (hollow variant)
mdi:database-multiple       # Sharded / replicated DB
mdi:database-search         # Search index
mdi:database-clock          # Time-series / temporal DB
mdi:database-lock           # Encrypted / secured DB
mdi:table                   # Structured data / table
mdi:table-multiple          # Multiple tables
mdi:chart-scatter-plot      # Analytics store
mdi:cube                    # Data cube / OLAP
mdi:vector-square           # Vector store / embeddings
mdi:graph                   # Graph database
mdi:graph-outline           # Graph DB (hollow)
```

## Networking & Connectivity

```
mdi:web                     # Internet / public web
mdi:earth                   # Global / worldwide
mdi:lan                     # LAN segment
mdi:wan                     # WAN link
mdi:access-point            # WiFi AP / edge node
mdi:dns                     # DNS / name resolution
mdi:ip-network              # IP network / subnet
mdi:vpn                     # VPN tunnel
mdi:tunnel                  # Network tunnel
mdi:connection              # Generic connection
mdi:arrow-right             # Directed flow
mdi:arrow-left-right        # Bidirectional link
mdi:repeat                  # Round-trip / two-way
mdi:transfer                # Data transfer
```

## APIs & Integration

```
mdi:api                     # API endpoint
mdi:webhook                 # Webhook / callback
mdi:code-json               # JSON / REST payload
mdi:xml                     # XML payload
mdi:graphql                 # GraphQL (generic, prefer logos:graphql)
mdi:swap-horizontal         # Data exchange / sync
mdi:sync                    # Sync / replication
mdi:cloud-sync              # Cloud sync
mdi:broadcast               # Broadcast / pub channel
mdi:publish                 # Publish / emit event
mdi:subscribe               # Subscribe / consume
mdi:message-text            # Message / event
mdi:message-processing      # Message processing
mdi:email-fast              # Email / notification
```

## Security & Identity

```
mdi:shield                  # Security / protection
mdi:shield-check            # Verified / compliant
mdi:shield-lock             # Secured / hardened
mdi:shield-alert            # Security warning
mdi:lock                    # Locked / encrypted
mdi:lock-open               # Unlocked / public
mdi:key                     # API key / credential
mdi:key-chain               # Key management
mdi:certificate             # TLS cert / PKI
mdi:fingerprint             # Biometric / unique identity
mdi:account-circle          # User / identity
mdi:account-group           # Group / team
mdi:account-key             # User with credential
mdi:domain                  # Organization / tenant
mdi:badge-account           # Service account / role
mdi:incognito               # Anonymous / guest
mdi:two-factor-authentication # MFA
```

## Observability & Operations

```
mdi:chart-line              # Metrics / time-series chart
mdi:chart-bar               # Histogram / bar chart
mdi:chart-pie               # Pie / proportion chart
mdi:gauge                   # Gauge / SLO indicator
mdi:speedometer             # Throughput / performance
mdi:bell                    # Alert / notification
mdi:bell-alert              # Active alert
mdi:monitor-eye             # Monitoring / observability
mdi:eye                     # Watch / observe
mdi:bug                     # Error / bug
mdi:bug-check               # Traced error
mdi:timeline-text           # Log stream / trace
mdi:text-box-search         # Log search
mdi:file-search             # Log file search
mdi:pulse                   # Health check / heartbeat
mdi:heart-pulse             # Health / liveness probe
mdi:timer                   # Timer / scheduled task
mdi:timer-cog               # Cron / scheduled job
```

## Storage & Files

```
mdi:folder                  # Directory / folder
mdi:folder-multiple         # Multiple directories
mdi:folder-open             # Open / accessible directory
mdi:file                    # Generic file
mdi:file-document           # Document / report
mdi:file-code               # Source code file
mdi:file-multiple           # Batch of files
mdi:archive                 # Archive / compressed
mdi:zip-box                 # ZIP archive
mdi:cloud-upload            # Upload to cloud
mdi:cloud-download          # Download from cloud
mdi:upload                  # Upload
mdi:download                # Download
mdi:content-copy            # Replicate / copy
mdi:backup-restore          # Backup and restore
```

## Compute & Processing

```
mdi:cog                     # Service / configuration
mdi:cog-outline             # Background service
mdi:cogs                    # System / multi-service
mdi:application-cog         # App with config
mdi:function                # Serverless function
mdi:function-variant        # Lambda / FaaS
mdi:robot                   # Automation / bot
mdi:robot-outline           # Agent / AI worker
mdi:chip                    # Embedded / IoT chip
mdi:raspberry-pi            # Edge device / IoT gateway
mdi:container               # Container
mdi:docker                  # Container runtime (prefer logos:docker)
mdi:kubernetes              # Orchestration (prefer logos:kubernetes)
mdi:pipeline                # CI/CD pipeline / data pipeline
mdi:pipe                    # Data pipe / stream
```

## Status & Workflow

```
mdi:check-circle            # Success / healthy
mdi:close-circle            # Failure / unhealthy
mdi:alert-circle            # Warning / degraded
mdi:pause-circle            # Paused
mdi:play-circle             # Running / active
mdi:stop-circle             # Stopped
mdi:refresh                 # Retry / reload
mdi:autorenew               # Auto-refresh / loop
mdi:arrow-decision          # Conditional branch (diamond)
mdi:source-merge            # Merge / join
mdi:source-branch           # Branch / fork
mdi:call-split              # Scatter / fan-out
mdi:call-merge              # Gather / fan-in
```

---

## Shape → MDI Equivalent

| Flowchart shape | MDI icon | Usage |
|----------------|----------|-------|
| Rectangle (process) | `mdi:cog` | Service / process step |
| Cylinder (database) | `mdi:database` | Any data store |
| Diamond (decision) | `mdi:arrow-decision` | Conditional routing |
| Parallelogram (I/O) | `mdi:transfer` | Data in/out |
| Stadium (start/end) | `mdi:circle-double` | Entry/exit point |
| Rounded rect (display) | `mdi:monitor` | UI / display layer |
| Document | `mdi:file-document` | Report / artifact |
| Hexagon (prep) | `mdi:cog-outline` | Setup / initialization |
| Circle (inspection) | `mdi:eye` | Review / check point |

---

## Example: Generic Pipeline Diagram

```
architecture-beta
    service ingest(mdi:upload)[Ingest]
    service validate(mdi:shield-check)[Validate]
    service transform(mdi:cogs)[Transform]
    service store(mdi:database)[Store]
    service notify(mdi:bell)[Notify]
    service monitor(mdi:chart-line)[Monitor]

    ingest:R --> L:validate
    validate:R --> L:transform
    transform:R --> L:store
    store:T --> B:notify
    store:B --> T:monitor
```
