# ADR-0006 — The text feed is a first-class adapter

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-23 |
| **Provenance** | `ADJ-12` — the Codex rehearsal series |
| **Relates to** | ADR-0017 makes the reply footer's grammar the canonical semantics |
| **Enforced in** | `SKILL.md` step 4.2 · `harnesses/session-feed.md` · `harnesses/codex.md` |

> **Lens** — Environment degradation changes *where the answer is typed*. Requirement degradation is never
> an adapter's call.

## Problem

### Symptom

Codex's structured question surface is tied to Plan mode, and the skill is used while refining planning
documents in Default mode. A text-only rendering was rehearsed instead, and signed off across all five shapes.

### Pain point

Calling that rendering a "fallback" invites it to be treated as a lesser form — compressed briefings, dropped sections,
"it is only text". That is requirement degradation dressed as environment sensing, and it is the failure mode the
whole skill exists to prevent.

## Decision

### The lens

- **Given** — a harness with no structured single-select surface carrying per-option free text
- **We prefer** — a complete text adapter with a reply footer, over a compressed "fallback" rendering
- **Because** — the requirement is set by the user, not by the harness; only the input mechanism changes
- **Unless** — never; this one is unconditional. "Fallback" language is forbidden even where the structured surface
  exists and is merely unavailable this session.

### In practice

- `session-feed.md` renders all nine sections; TBD routes render as a table, which *is* the route preview card there.
- `codex.md` routes to it in every Codex mode, and records what remains unverified about Plan mode.
- The reply grammar is the canonical semantics that structured pickers must also honour.
- Replies are parsed leniently: `B`, `b:`, `B —`, "B because …"; a bare route name is a TBD answer.
- The adapter is announced in one clause when it is not the structured one.

## Consequences

### Pros

- Text-only harnesses get the full anatomy, so the skill is portable without being weakened.
- The reply grammar became the shared semantics both adapter families implement.

### Cons

- Two adapters must be kept in agreement whenever the routes or footer change.
