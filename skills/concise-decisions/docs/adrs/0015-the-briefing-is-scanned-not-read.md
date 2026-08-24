# ADR-0015 — The briefing is scanned, not read

| Field | Value |
|---|---|
| **Status** | Accepted · 2026-08-24 |
| **Provenance** | `ADJ-12` |
| **Relates to** | the runtime counterpart of ADR-0010, which applies the same principle to the ADR log |
| **Enforced in** | `SKILL.md` § Rules that do not bend · `question-template.md` § Filling rules · `harnesses/session-feed.md` |

> **Lens** — Assume the reader lands mid-document and never reads from the top. Labels, self-describing titles, and
> separated lines are how they find their place; a well-written paragraph is not.

## Problem

### Symptom

The Codex rehearsal took five iterations to converge, and every defect was a legibility one: pros and cons blended
into a paragraph, the recommendation buried after the previews, context written as prose instead of labelled lines,
and a decision sentence compressed into a fragment.

### Pain point

Separately, the picker was observed rendering **before** the body, so the user saw option labels with no briefing at
all and asked what the question even was. Both failures have the same cause: the briefing was written to be read in
order, and it is not read in order.

## Decision

### The lens

- **Given** — a briefing whose reader arrives cold, possibly at the answer surface first
- **We prefer** — labelled lines, self-describing titles, and one claim per line, over well-formed connected prose
- **Because** — the reader is scanning for their place, and a paragraph offers no entry point
- **Unless** — never; this one is unconditional. Conciseness never buys the right to a fragment: a decision sentence
  that reads as a fragment fails check 1 even when everything else is complete.

### In practice

- `Decision to make`, `Why decide this now`, `Already settled`, `Reversibility` stay as visible labels — in a feed
  these labels are the navigation.
- Option titles are self-describing and must make sense with the body off-screen: `B (Recommended): each --match opens
  a group` passes, `Confirm C` fails.
- The recommendation appears twice: in the option title and in the Recommendation line.
- `Pros:` and `Cons:` are separate lines under every preview, never a blended paragraph.
- The visible label for the non-decision option is the word `TBD`, never a bare letter — `T` was read as a fourth
  option.
- A structured picker's `question` text restates the decision and its stakes, so the user can orient from the picker
  alone.
- Rehearsal and grading instructions stay outside the question surface entirely.

## Consequences

### Pros

- The question survives being read out of order, or with only half of it on screen.
- Most of the rehearsal defects are now structurally impossible rather than discouraged.

### Cons

- The briefing reads as a form rather than as prose, which suits scanning and not reading.
