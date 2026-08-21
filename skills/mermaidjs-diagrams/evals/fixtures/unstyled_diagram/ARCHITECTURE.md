# Ingest pipeline

The ingest service pulls events from the queue, validates them, and writes
them to the store. Failures land on a dead-letter queue.

```mermaid
flowchart LR
    Q[Event queue] --> V[Validator]
    V --> S[Store]
    V --> D[Dead letter queue]
```
