# 1. Ingest writes to the store synchronously

Status: Accepted (2026-01-15)

## Context

Early prototypes used a queue between ingest and the store; debugging the
async path cost more than the throughput it bought.

## Decision

`ingest.py` calls `store.save()` directly and synchronously. No queue, no
background workers.

## Consequences

Simpler failure modes; throughput capped by store latency.
