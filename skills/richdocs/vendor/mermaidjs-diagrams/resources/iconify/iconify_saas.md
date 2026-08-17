# Iconify SaaS & DevTool Icon Reference

Quick-reference for SaaS product and developer tool icons in Mermaid `architecture-beta` diagrams.
Equivalent to `diagrams.saas.*`.

All icons below come from the `logos` set unless noted. Install: `npm install @iconify-json/logos`

---

## Identity & Auth

```
logos:auth0
logos:okta
logos:keycloak
logos:firebase
logos:supabase
```

## Communication & Chat

```
logos:slack
logos:discord
logos:mattermost
logos:telegram
logos:rocketchat
```

## Alerting & Incident Management

```
logos:pagerduty
logos:opsgenie
logos:grafana               # Grafana OnCall
logos:victorops
```

## Monitoring & Observability

```
logos:datadog
logos:grafana
logos:prometheus
logos:sentry
logos:elastic               # Elastic/ELK stack
logos:kibana
logos:newrelic
logos:dynatrace
logos:opentelemetry
logos:jaeger
logos:zipkin
logos:honeycomb
```

## CDN & Edge

```
logos:cloudflare
logos:fastly
logos:akamai
logos:vercel
logos:netlify
```

## Analytics & Data Warehouse

```
logos:snowflake
logos:databricks
logos:dbt
logos:fivetran
logos:airbyte
logos:stitch
logos:looker
logos:tableau
logos:redash
logos:metabase
```

## Payment & Commerce

```
logos:stripe
logos:paypal
logos:adyen
logos:braintree
```

## CRM & Support

```
logos:salesforce
logos:zendesk
logos:intercom
logos:hubspot
logos:freshdesk
```

## Feature Flags & Experimentation

```
logos:launchdarkly
logos:split
logos:unleash
```

## Security

```
logos:snyk
logos:sonarqube
logos:vault                 # HashiCorp Vault
logos:aqua-security
logos:falco
```

## Infrastructure Platforms

```
logos:hashicorp
logos:terraform
logos:nomad
logos:consul
logos:vault
logos:packer
logos:vagrant
```

## Source Control & CI/CD

```
logos:github-icon
logos:gitlab
logos:bitbucket
logos:jenkins
logos:circleci
logos:travis-ci
logos:github-actions
logos:drone
logos:bamboo
logos:teamcity
logos:concourse
logos:argocd
logos:flux
logos:tekton
logos:spinnaker
```

## Container Registries

```
logos:docker
logos:quay
logos:harbor
```

## API Management

```
logos:kong
logos:apigee
logos:postman
logos:swagger
```

## Workflow & Automation

```
logos:zapier
logos:n8n
logos:airflow
logos:prefect
logos:temporal
logos:celery
```

## Messaging & Event Streaming

```
logos:kafka
logos:rabbitmq
logos:nats-io
logos:redis               # Redis Streams
logos:pulsar
logos:activemq
```

## Search

```
logos:elasticsearch
logos:algolia
logos:meilisearch
logos:typesense
```

## File Storage & Collaboration

```
logos:aws                  # S3-compatible (use with label)
logos:cloudflare           # R2
logos:dropbox
logos:box
```

---

## Example: DevOps Platform Diagram

```
architecture-beta
    group source(logos:github-icon)[Source]
        service repo(logos:git-icon)[Repository] in source
        service ci(logos:github-actions)[CI] in source

    group registry(logos:docker)[Artifacts]
        service images(logos:docker)[Container Registry] in registry
        service charts(logos:helm)[Helm Charts] in registry

    group platform(logos:kubernetes)[Platform]
        service cluster(logos:kubernetes)[K8s Cluster] in platform
        service gitops(logos:argocd)[GitOps] in platform
        service secrets(logos:vault)[Secrets] in platform

    group observe(logos:grafana)[Observability]
        service metrics(logos:prometheus)[Metrics] in observe
        service logs(logos:elastic)[Logs] in observe
        service traces(logos:opentelemetry)[Traces] in observe
        service alerts(logos:pagerduty)[Alerting] in observe

    repo:R --> L:ci
    ci:R --> L:images
    images:R --> L:gitops
    gitops:R --> L:cluster
    cluster:B --> T:metrics
    cluster:B --> T:logs
    cluster:B --> T:traces
    metrics:R --> L:alerts
```

---

## SaaS Quick Lookup

| Category | Product | Slug |
|----------|---------|------|
| Identity | Auth0 | `logos:auth0` |
| Identity | Okta | `logos:okta` |
| Chat | Slack | `logos:slack` |
| Chat | Discord | `logos:discord` |
| Alerting | PagerDuty | `logos:pagerduty` |
| Monitoring | Datadog | `logos:datadog` |
| Monitoring | Grafana | `logos:grafana` |
| Monitoring | Sentry | `logos:sentry` |
| CDN | Cloudflare | `logos:cloudflare` |
| CDN | Vercel | `logos:vercel` |
| Analytics | Snowflake | `logos:snowflake` |
| Analytics | Databricks | `logos:databricks` |
| Payment | Stripe | `logos:stripe` |
| Payment | PayPal | `logos:paypal` |
| Secrets | Vault | `logos:vault` |
| Secrets | Snyk | `logos:snyk` |
| Streaming | Kafka | `logos:kafka` |
| Streaming | RabbitMQ | `logos:rabbitmq` |
| Search | Elasticsearch | `logos:elasticsearch` |
| Search | Algolia | `logos:algolia` |
| CRM | Salesforce | `logos:salesforce` |
| Support | Zendesk | `logos:zendesk` |
| Feature flags | LaunchDarkly | `logos:launchdarkly` |

> **Tip:** If a SaaS product doesn't have a `logos` entry, check `simple-icons` set —
> it has 3,000+ brand icons: `simple-icons:<brand-name-lowercase>`.
> Install: `npm install @iconify-json/simple-icons`
