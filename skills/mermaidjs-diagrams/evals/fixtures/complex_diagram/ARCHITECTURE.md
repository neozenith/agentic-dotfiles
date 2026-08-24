# Storefront platform architecture

This document describes the production topology of the storefront platform: the
edge, the API layer, the domain services, the data stores, the third-party
integrations, the asynchronous pipeline, and the observability stack. The
diagram below was exported from the infrastructure inventory and has grown with
every service that was added; it is complete but no longer readable at a glance.

```mermaid
flowchart LR
    subgraph Edge
        DNS[Route 53 DNS]
        CDN[CloudFront CDN]
        WAF[Web application firewall]
    end
    subgraph Gateway
        GW[API gateway]
        AUTH[Auth service]
        RL[Rate limiter]
    end
    subgraph Web
        WEB[Next.js storefront]
        BFF[Backend for frontend]
        ADMIN[Admin console]
    end
    subgraph Services
        CAT[Catalog service]
        SEARCH[Search service]
        REC[Recommendations]
        CART[Cart service]
        PRICE[Pricing service]
        PROMO[Promotions]
        CHK[Checkout service]
        PAY[Payments service]
        ORD[Orders service]
        INV[Inventory service]
        SHIP[Shipping service]
        TAX[Tax service]
        USR[Users service]
        REV[Reviews service]
        NOTIF[Notifications]
    end
    subgraph Data
        PG1[(Catalog Postgres)]
        PG2[(Orders Postgres)]
        PG3[(Users Postgres)]
        REDIS[(Redis cache)]
        ES[(Elasticsearch)]
        S3[(S3 media bucket)]
        KAFKA[[Kafka]]
        DWH[(Snowflake warehouse)]
    end
    subgraph Integrations
        STRIPE[Stripe]
        PAYPAL[PayPal]
        TWILIO[Twilio SMS]
        SENDGRID[SendGrid email]
        CARRIER[Carrier APIs]
        AVALARA[Avalara tax]
    end
    subgraph Pipeline
        AIRFLOW[Airflow]
        DBT[dbt models]
        SPARK[Spark jobs]
    end
    subgraph Observability
        PROM[Prometheus]
        GRAF[Grafana]
        JAEGER[Jaeger tracing]
        LOKI[Loki logs]
        PAGER[PagerDuty]
    end

    DNS --> CDN --> WAF --> GW
    GW --> AUTH
    GW --> RL
    GW --> BFF
    GW --> ADMIN
    WEB --> BFF
    BFF --> CAT
    BFF --> SEARCH
    BFF --> REC
    BFF --> CART
    BFF --> CHK
    BFF --> USR
    BFF --> REV
    CAT --> PG1
    CAT --> S3
    SEARCH --> ES
    REC --> REDIS
    REC --> DWH
    CART --> REDIS
    CART --> PRICE
    PRICE --> PROMO
    CHK --> CART
    CHK --> PAY
    CHK --> TAX
    CHK --> SHIP
    CHK --> ORD
    PAY --> STRIPE
    PAY --> PAYPAL
    TAX --> AVALARA
    SHIP --> CARRIER
    ORD --> PG2
    ORD --> INV
    ORD --> KAFKA
    INV --> PG1
    USR --> PG3
    REV --> PG1
    KAFKA --> NOTIF
    KAFKA --> SPARK
    NOTIF --> TWILIO
    NOTIF --> SENDGRID
    AIRFLOW --> DBT
    AIRFLOW --> SPARK
    DBT --> DWH
    SPARK --> DWH
    CAT -.-> PROM
    CHK -.-> PROM
    ORD -.-> PROM
    PROM --> GRAF
    PROM --> PAGER
    BFF -.-> JAEGER
    BFF -.-> LOKI
```

The diagram is used in onboarding, in architecture reviews, and in incident
retrospectives. Each audience needs a different amount of it.
