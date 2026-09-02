# ADR-0014 — Previews are complete outcomes on real data; the pane holds a card

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-24 |
| **Provenance** | user rehearsal, 2026-08-22, and the Codex series, 2026-08-23 |
| **Relates to** | ADR-0001 put the artifact in the body; this says what the body must contain |
| **Enforced in** | `SKILL.md` §§ Rules, Never · `question-template.md` § Filling rules · `harnesses/claude-code.md` |

> **Lens** — A preview is the outcome the user would get, rendered on their own data. An illustration of
> the outcome is not a smaller preview; it is a different and useless thing.

## Problem

### Symptom

Options were previewed with illustrative fragments and with artifacts rendered inside the picker's preview pane, which
truncates after a few lines. In the Codex rehearsal, fragments as option previews were among the four defects that
took five iterations to clear.

### Pain point

The user reported that the model "often attempts to render or describe something in a preview but it gets cut off",
and that the same content was "better laid out as previews in the session log". A truncated or invented preview cannot
be compared against another option, so check 1 fails and the whole briefing is wasted.

## Decision

### The lens

- **Given** — an option that must be compared against its alternatives before the user can choose
- **We prefer** — the complete outcome rendered on the user's real data, in the message body, over a fragment or a
  pane-rendered artifact
- **Because** — the pane truncates and the body does not, and an outcome on invented data does not answer what the
  user would actually get
- **Unless** — the decision is low-stakes, where the preview shrinks to the value itself — a path, a key name — which
  is still the complete outcome, not a fragment of one (ADR-0002).

### In practice

- Previews use the user's actual command, file, path, and output. If that data is not available, collect it before
  asking.
- Every option shows the *same* real scenario in its own terms, so the comparison is like with like.
- The body carries the artifact; the preview pane carries a card — an example line or two, `Solves:`,
  `Cost:`, and a pointer to the full block above.

## Consequences

### Pros

- Options are genuinely comparable rather than nominally so.
- Truncation stops being a failure mode, because nothing long is put where truncation happens.

### Cons

- A question cannot be asked until the real data has been gathered, which sometimes means doing work first.
