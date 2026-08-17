# Iconify `logos` Icon Reference

Quick-reference for `(logos:<slug>)` in Mermaid `architecture-beta` diagrams.
Equivalent to `diagrams.programming.language` + `diagrams.programming.framework`.

The `logos` set contains SVG brand logos for languages, frameworks, databases, and tools.
Install: `npm install @iconify-json/logos`

## Languages

```
logos:python
logos:javascript
logos:typescript
logos:go
logos:rust
logos:java
logos:kotlin
logos:swift
logos:ruby
logos:php
logos:c
logos:cplusplus
logos:csharp
logos:scala
logos:elixir
logos:erlang
logos:haskell
logos:dart
logos:r-lang
logos:bash
logos:lua
logos:zig
```

## Web Frameworks

```
logos:react
logos:vue
logos:angular
logos:svelte
logos:nextjs
logos:nuxt
logos:remix
logos:astro
logos:solidjs
logos:htmx
```

## Backend Frameworks

```
logos:django
logos:flask
logos:fastapi
logos:spring
logos:rails
logos:laravel
logos:express
logos:nestjs
logos:actix
logos:gin
logos:fiber
logos:phoenix
```

## Databases

```
logos:postgresql
logos:mysql
logos:mariadb
logos:mongodb
logos:redis
logos:sqlite
logos:elasticsearch
logos:cassandra
logos:neo4j
logos:cockroachdb
logos:couchdb
logos:influxdb
logos:supabase
```

## Runtimes & Package Managers

```
logos:nodejs
logos:deno
logos:bun
logos:npm
logos:yarn
logos:pnpm
logos:pip
logos:uv
```

## Containers & Orchestration

```
logos:docker
logos:kubernetes
logos:helm
logos:rancher
logos:podman
```

## Infrastructure as Code

```
logos:terraform
logos:ansible
logos:pulumi
logos:chef
logos:puppet
```

## CI/CD & Source Control

```
logos:git-icon
logos:github-icon
logos:gitlab
logos:bitbucket
logos:jenkins
logos:github-actions
logos:circleci
logos:travis-ci
logos:drone
logos:argocd
logos:flux
```

## Web Servers & Proxies

```
logos:nginx
logos:apache
logos:caddy
logos:traefik
logos:haproxy
```

## Message Brokers & Streaming

```
logos:kafka
logos:rabbitmq
logos:nats-io
logos:activemq
```

## Observability

```
logos:grafana
logos:prometheus
logos:datadog
logos:sentry
logos:opentelemetry
logos:jaeger
logos:loki
logos:elastic
logos:kibana
```

## Example: Full-Stack Service Diagram

```
architecture-beta
    group frontend(logos:react)[Frontend]
        service ui(logos:nextjs)[Web App] in frontend
        service cdn(logos:cloudflare)[CDN] in frontend

    group backend(logos:fastapi)[API Layer]
        service api(logos:python)[REST API] in backend
        service worker(logos:celery)[Task Worker] in backend

    group data(logos:postgresql)[Data Layer]
        service db(logos:postgresql)[Primary DB] in data
        service cache(logos:redis)[Cache] in data
        service search(logos:elasticsearch)[Search] in data

    ui:R --> L:cdn
    cdn:R --> L:api
    api:R --> L:db
    api:T --> B:cache
    api:B --> T:worker
    worker:R --> L:search
```

## Logos Quick Lookup Table

| Category | Slug | Notes |
|----------|------|-------|
| Python | `logos:python` | |
| JavaScript | `logos:javascript` | |
| TypeScript | `logos:typescript` | |
| Go | `logos:go` | |
| Rust | `logos:rust` | |
| React | `logos:react` | |
| Next.js | `logos:nextjs` | |
| Vue | `logos:vue` | |
| FastAPI | `logos:fastapi` | |
| Django | `logos:django` | |
| PostgreSQL | `logos:postgresql` | |
| MongoDB | `logos:mongodb` | |
| Redis | `logos:redis` | |
| Docker | `logos:docker` | |
| Kubernetes | `logos:kubernetes` | |
| Kafka | `logos:kafka` | |
| Terraform | `logos:terraform` | |
| GitHub | `logos:github-icon` | use `-icon` suffix |
| Git | `logos:git-icon` | use `-icon` suffix |
| Grafana | `logos:grafana` | |
| Prometheus | `logos:prometheus` | |
| Node.js | `logos:nodejs` | |
