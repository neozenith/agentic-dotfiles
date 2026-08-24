# ADR-0010 — Headings index the hierarchy of information in an ADR

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-24 |
| **Provenance** | `ADJ-21` — the ADR-LAYOUT decision, rev 3 |
| **Relates to** | ADR-0011 fills the `Decision` section this template defines |
| **Enforced in** | none — dev-time only (ADR-0018) |

> **Lens** — Every part of a document that a reader returns to needs a name. Prefer a heading over a bold
> run-in, and a named field over a paragraph, whenever the part will be read out of order.

## Problem

### Symptom

The first nine ADRs were a flat bullet list — `Status`, `Context`, `Decision`, `Consequences`, `Lens` as five bullets,
with a ten-line paragraph inside the `Context` bullet. The Lens, which is the only part reused on a later visit, sat
last.

### Pain point

The files were unreadable out of order and too wordy to skim. Four iterations of candidate layouts were needed before
the shape was right: removing a per-ADR `Compliance` section, moving metadata into a table, splitting Consequences into
Pros and Cons, and finally giving `Problem` and `Decision` their own sub-headings.

## Decision

### The lens

- **Given** — an ADR whose Lens and enforcement anchors are consulted far more often than its argument
- **We prefer** — sub-headings that index every part, over prose signposted with bold run-in labels
- **Because** — headings index the hierarchy of information, so a reader can enter at the part they need instead of
  reading from the top
- **Unless** — never; this one is unconditional for this log. A section too small to deserve a heading is a section
  that should be a field in the metadata table instead.

### In practice

- The file shape is fixed by [TEMPLATE.md](TEMPLATE.md): title, metadata table, Lens blockquote, `Problem` (`Symptom`,
  `Pain point`), `Decision` (`The lens`, `In practice`), `Consequences` (`Pros`, `Cons`).
- Metadata is a `| Field | Value |` table, not a bullet list or a front-matter block.
- The Lens is a blockquote directly under the metadata — above the argument that produced it.
- There is **no per-ADR `Compliance` section**. The audit anchor is the single `Enforced in` metadata row, and the
  index in [README.md](README.md) collects those rows into one compliance map.
- Prose folds at ≤120 characters; metadata table rows, which cannot fold, stay under 140.

## Consequences

### Pros

- An ADR can be entered at any section without reading the ones above it.
- Dropping the `Compliance` section cut roughly a third of every file, which was the wordiness that made the log
  unpleasant to read.
- The shape is uniform enough across the log to be parsed, not only read.

### Cons

- More heading levels for a short decision than a plain narrative would need.
- `Enforced in` names surfaces without their conditions, so an audit reads the ADR *and* the surface rather than the
  ADR alone.
