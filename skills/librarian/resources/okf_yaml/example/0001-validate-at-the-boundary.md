---
type: Architecture Decision
title: Validate external payloads at the boundary, not at the point of use
description: Data crossing a trust boundary is validated once, where it enters
tags: [correctness, boundaries]
status: accepted
accepted_on: 2026-08-28
provenance: Two incidents traced to a response field that changed shape upstream and was read as valid at three call sites
enforced_in:
  - the request handler layer
  - the queue consumer
  - the config loader
generated: { by: human:maintainer, at: 2026-08-28T00:00:00Z }
---

<!-- GENERATED from REC-0001 by okf_render.py. Do not edit; edit the .yml and regenerate. -->

> **Lens**: A value from outside the process is untyped until something checks it.
> Check it where it enters, once, or every later reader re-checks it differently.

## Relates to

- Depended on by [REC-0002](0002-one-error-taxonomy.md) (the error taxonomy assumes payloads are already shaped)

## Problem

### Symptom

A malformed upstream payload reaches business logic and fails as a type error three frames deep, naming a field the caller never mentioned.

### Pain point

The stack trace points at the consumer rather than the boundary, so every incident costs a bisect to find where the bad value entered.

## Decision

### The lens

- **Given**: every value crossing a trust boundary is unknown until something checks it
- **We prefer**: parsing each payload into a typed value at the boundary it enters, over defensive checks at each point of use
- **Because**: one check produces one error naming the real source, while scattered checks disagree about what valid means
- **Unless**: the boundary is provably internal and the producer is in the same deployable

### In practice

- Every handler parses its request body before business logic sees it.
- A parse failure returns the boundary's own error, never a downstream type error.

## Consequences

### Pros

- A malformed payload fails once, at the edge, naming the offending field.
- Downstream code can treat its inputs as typed without re-checking.

### Cons

- Schemas must be maintained alongside the types they mirror, and the two can drift.
