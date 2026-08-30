---
type: Architecture Decision
title: One error taxonomy, owned by the boundary that raises it
description: Every failure names its boundary and its cause, in one vocabulary
tags: [correctness, errors]
status: accepted
accepted_on: 2026-08-29
provenance: A support rotation where three subsystems reported the same upstream outage in three unrelated vocabularies
enforced_in:
  - the shared error type
  - every boundary that constructs one
generated: { by: human:maintainer, at: 2026-08-29T00:00:00Z }
---

> **Lens**: An error is a message to whoever must act on it.
> Name the responsible boundary in the error itself, or the reader guesses.

## Relates to

- Depends on [REC-0001](0001-validate-at-the-boundary.md) (the taxonomy assumes payloads are already shaped)

## Problem

### Symptom

The same upstream failure surfaces as a timeout, a null dereference, and a generic 500, depending on which subsystem noticed it first.

### Pain point

Triage starts by reconciling three vocabularies before anyone can ask what actually broke, which is the expensive part of every incident.

## Decision

### The lens

- **Given**: a failure is only actionable when the reader can tell which boundary owns it
- **We prefer**: one error type carrying the boundary and the cause, over each subsystem raising its own vocabulary
- **Because**: a shared vocabulary makes failures comparable across subsystems, which is what triage needs first
- **Unless**: a boundary is genuinely outside the taxonomy's domain, in which case it wraps rather than translates

### In practice

- Every boundary constructs the shared error type and names itself.
- Wrapping preserves the original cause rather than flattening it to a string.

## Consequences

### Pros

- Triage reads one vocabulary regardless of which subsystem reported first.
- The responsible boundary is in the error, not inferred from a stack trace.

### Cons

- A shared type couples subsystems that would otherwise be independent, so changing it is a coordinated change.
