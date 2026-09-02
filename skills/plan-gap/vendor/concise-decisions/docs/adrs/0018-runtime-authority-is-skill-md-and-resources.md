# ADR-0018 — Runtime authority is `SKILL.md` and `resources/`; everything else is dev-time

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-24 · one clause superseded by [ADR-0020](0020-the-adr-log-is-the-only-knowledge-store.md) |
| **Provenance** | user ruling, 2026-08-24 — `README.md` and `CLAUDE.md` are development-time files |
| **Relates to** | why ADR-0010 gives every ADR an `Enforced in` row instead of a Compliance section |
| **Enforced in** | `SKILL.md` § Resources |

> **Lens** — A document that is not loaded during a run cannot constrain the run. It can only constrain the people and
> agents editing the files that *are* loaded. Write it for them, and make it point at what it governs.

## Problem

### Symptom

`README.md` and `CLAUDE.md` had grown into places where rules lived, and the ADR log recorded decisions without saying
where they took effect. A runtime surface could drift from a decision with nothing to catch it.

### Pain point

The user drew the line explicitly: `README.md` and `CLAUDE.md` are "supportive files during skill development", not
load-bearing at runtime — the README "is, and always will be the human facing documentation to describe the skill, its
value proposition, an overview of how it works". A rule that only exists in a dev-time document is a rule the agent
never sees. Worse, an ADR that names no enforcement point cannot be audited: nothing says which file was supposed to
change.

## Decision

### The lens

- **Given** — a skill whose runtime loads `SKILL.md` and, on demand, files under `resources/`
- **We prefer** — all binding rules in those surfaces, with dev-time documents pointing *at* them, over rules that
  live in `README.md`, `CLAUDE.md`, or the ADR log
- **Because** — only the loaded surfaces can change behaviour, so a rule recorded anywhere else is documentation of an
  intention rather than an instruction
- **Unless** — never; this one is unconditional. A rule that seems to belong in a dev-time document is either a
  maintainer convention, which is fine, or a missing runtime rule, which is a defect.

### In practice

- `SKILL.md` plus `resources/` are the only runtime authority. A runtime surface never cites `README.md` or
  `CLAUDE.md` as an authority.
- Every ADR carries an `Enforced in` row naming the runtime surfaces that must satisfy it — or `none — dev-time only`
  where the decision genuinely governs the log rather than the loop.
- **When a runtime surface and an ADR disagree, the surface is wrong.** Fix the surface; never edit the record.
- `README.md` stays the human explainer: purpose, value, an overview of how it works, and the loop diagram.
- `CLAUDE.md` stays the maintainer contract: dev gates, file map, principles, extension checklist, known gotchas.
- The skill's own adjudications remain a searchable record for step 2 — the one runtime use of a dev-time
  file. *(Superseded by [ADR-0020](0020-the-adr-log-is-the-only-knowledge-store.md): the carve-out was the
  loophole, the ledger is gone, and the rule now holds with no exception.)*

## Consequences

### Pros

- "Is the skill compliant with its own decisions?" is answerable by walking the `Enforced in` rows.
- Dev-time documents can be rewritten freely without changing behaviour.

### Cons

- A rule sometimes has to be stated twice — once as a decision, once in the surface that enforces it.
- `Enforced in` names surfaces without their conditions, so an audit reads both the ADR and the surface.
