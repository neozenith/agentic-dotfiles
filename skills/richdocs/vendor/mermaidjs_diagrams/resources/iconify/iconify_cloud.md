# Iconify Cloud Provider Icon Reference

Quick-reference for cloud infrastructure icons in Mermaid `architecture-beta` diagrams.
Equivalent to `diagrams.aws.*`, `diagrams.gcp.*`, `diagrams.azure.*`.

Cloud icons come from multiple Iconify sets. Each provider has a dedicated set for
service-level icons, while the `logos` set covers generic provider branding.

---

## AWS Icons (`logos` set — `logos:aws-*`)

> **`@iconify-json/aws` does not exist on npm.** Do not use `--iconPacks @iconify-json/aws` —
> unpkg.com returns a 404 with no CORS header, which Puppeteer blocks silently.
>
> AWS service icons are in the `logos` set (`@iconify-json/logos`) under `logos:aws-*` slugs.
> Use `--iconPacks @iconify-json/logos` — no separate `aws` pack needed.

Install: `npm install @iconify-json/logos` (already needed for logos icons)

### Compute

```
logos:aws-ec2
logos:aws-ecs
logos:aws-eks
logos:aws-fargate
logos:aws-lambda
logos:aws-batch
logos:aws-lightsail
logos:aws-elastic-beanstalk
```

### Storage

```
logos:aws-s3
logos:aws-glacier
```

### Database

```
logos:aws-rds
logos:aws-aurora
logos:aws-dynamodb
logos:aws-elasticache
logos:aws-redshift
logos:aws-neptune
logos:aws-documentdb
logos:aws-keyspaces
logos:aws-timestream
```

### Networking

```
logos:aws-vpc
logos:aws-api-gateway
logos:aws-cloudfront
logos:aws-route53
logos:aws-elb
```

### Integration & Messaging

```
logos:aws-sqs
logos:aws-sns
logos:aws-eventbridge
logos:aws-step-functions
logos:aws-mq
logos:aws-msk
logos:aws-appsync
```

### Management & Observability

```
logos:aws-cloudwatch
logos:aws-cloudformation
logos:aws-cloudtrail
logos:aws-config
logos:aws-systems-manager
logos:aws-xray
logos:aws-quicksight
```

### Security & Identity

```
logos:aws-iam
logos:aws-kms
logos:aws-secrets-manager
logos:aws-cognito
logos:aws-shield
logos:aws-waf
logos:aws-certificate-manager
```

### Analytics

```
logos:aws-athena
logos:aws-glue
logos:aws-kinesis
logos:aws-lake-formation
logos:aws-open-search
```

---

## GCP Icons (`gcp-icons` set)

Install: `npm install @iconify-json/gcp-icons`

### Compute

```
gcp-icons:ComputeEngine
gcp-icons:KubernetesEngine
gcp-icons:CloudRun
gcp-icons:CloudFunctions
gcp-icons:AppEngine
gcp-icons:Batch
```

### Storage & Database

```
gcp-icons:CloudStorage
gcp-icons:CloudSQL
gcp-icons:Firestore
gcp-icons:Bigtable
gcp-icons:Spanner
gcp-icons:Memorystore
gcp-icons:AlloyDB
```

### Networking

```
gcp-icons:CloudLoadBalancing
gcp-icons:CloudDNS
gcp-icons:CloudCDN
gcp-icons:CloudArmor
gcp-icons:VirtualPrivateCloud
gcp-icons:CloudNAT
```

### Data & Analytics

```
gcp-icons:BigQuery
gcp-icons:Dataflow
gcp-icons:Pub/Sub
gcp-icons:Dataproc
gcp-icons:Looker
gcp-icons:DataFusion
```

### AI/ML

```
gcp-icons:VertexAI
gcp-icons:AutoML
gcp-icons:NaturalLanguageAPI
gcp-icons:VisionAPI
gcp-icons:SpeechToText
```

---

## Azure Icons (`azure` set)

Install: `npm install @iconify-json/azure-icons`

### Compute

```
azure:VirtualMachine
azure:KubernetesService
azure:ContainerApps
azure:Functions
azure:AppService
azure:ContainerRegistry
azure:BatchAccounts
```

### Storage & Database

```
azure:StorageAccounts
azure:CosmosDb
azure:SqlDatabase
azure:SqlServer
azure:RedisCache
azure:PostgreSqlFlexibleServer
azure:MySqlFlexibleServer
```

### Networking

```
azure:ApplicationGateway
azure:FrontDoor
azure:LoadBalancers
azure:VirtualNetworks
azure:DnsZones
azure:Firewall
azure:ExpressRouteCircuits
```

### Integration

```
azure:ServiceBus
azure:EventHubs
azure:EventGrid
azure:ApiManagementServices
azure:LogicApps
```

### Security

```
azure:KeyVaults
azure:ActiveDirectory
azure:ManagedIdentities
azure:SecurityCenter
azure:Sentinel
```

---

## Generic Cloud Logos (`logos` set)

When service-level detail is not needed, use these from the `logos` set:

```
logos:aws                  # AWS wordmark/logo
logos:google-cloud         # GCP logo
logos:azure                # Azure logo
logos:cloudflare           # Cloudflare
logos:vercel               # Vercel
logos:netlify              # Netlify
logos:digitalocean         # DigitalOcean
logos:linode               # Linode / Akamai Cloud
logos:hetzner              # Hetzner
```

---

## Multi-Cloud Example

```
architecture-beta
    group aws(logos:aws)[AWS]
        service compute(logos:aws-lambda)[Functions] in aws
        service store(logos:aws-s3)[Object Store] in aws
        service db(logos:aws-rds)[Relational DB] in aws

    group gcp(logos:google-cloud)[GCP]
        service bq(gcp-icons:BigQuery)[Analytics] in gcp
        service ml(gcp-icons:VertexAI)[ML Platform] in gcp

    service cdn(logos:cloudflare)[CDN Edge]

    cdn:R -[route]-> L:compute
    compute:R -[store]-> L:store
    compute:R -[query]-> L:db
    store:R -[export]-> L:bq
    bq:R -[train]-> L:ml
```

---

## Icon Set Selection Guide

| Use case | Recommended set | Example |
|----------|----------------|---------|
| High-level cloud provider | `logos` | `logos:aws` |
| Specific AWS service | `aws` | `aws:Lambda` |
| Specific GCP service | `gcp-icons` | `gcp-icons:BigQuery` |
| Specific Azure service | `azure` | `azure:Functions` |
| Generic server/DB shape | `mdi` | `mdi:server` |
| Tech brand (DB engine) | `logos` | `logos:postgresql` |

> **Slug verification:** AWS slugs match the official [AWS Architecture Icon Library](https://aws.amazon.com/architecture/icons/).
> GCP slugs match the [Google Cloud Icons](https://cloud.google.com/icons) library.
> Always cross-check against the [Iconify browser](https://icon-sets.iconify.design/) for exact casing.
