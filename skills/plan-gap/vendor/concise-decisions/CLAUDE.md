# concise-decisions — Maintainer Decision Lens

Read the ADR log in [docs/adrs/](docs/adrs/README.md) before changing anything. Each ADR carries a **Lens** — apply it
to the next decision instead of re-deriving the trade-off, and check it before raising a question.

This file is **development-time only**. It is never loaded during a run, and no runtime surface may cite it as an
authority (ADR-0018).

## Development contract

Prose-only skill (no `scripts/`). Doc gates before handoff, run from repo root:

```sh
bun run skills/mermaidjs-diagrams/scripts/mermaid_contrast.ts   skills/concise-decisions/README.md
bun run skills/mermaidjs-diagrams/scripts/mermaid_complexity.ts skills/concise-decisions/README.md
uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 skills/concise-decisions/README.md
```

- All files ≤ 500 lines.
- **Prose folds at ≤120 characters.** Markdown table rows cannot fold; keep them under 140 by shortening cell values,
  and never put sentence-shaped content in a table cell.
- Examples are brand-agnostic (`mytool`, generic paths); project-specific rehearsal evidence lives in the originating
  project, never here.

## File map

| File | Role | Runtime? |
|------|------|----------|
| `SKILL.md` | Agent operating manual: the loop, step-4 composition with shape/harness routing, five-question check, never-table | **yes** |
| `resources/question-template.md` | The nine-section template, filling rules, variant summary | **yes**, composing |
| `resources/tbd-routes.md` | The non-decision answer family and what each route does next | **yes**, section 8 |
| `resources/shapes/exclusive-choice.md` | Baseline shape; worked generic example | **yes**, 1 per question |
| `resources/shapes/subset-as-permutations.md` | Composing options: atomic table first, combinations as options | **yes**, 1 per question |
| `resources/shapes/binary.md` | Two options; sub-choice in the reply footer | **yes**, 1 per question |
| `resources/shapes/low-stakes.md` | Shorter previews, full anatomy; the compressed-form failure | **yes**, 1 per question |
| `resources/shapes/resolved-by-cascade.md` | `Already settled` carries the ripple and the reopen path | **yes**, 1 per question |
| `resources/harnesses/claude-code.md` | Body + `AskUserQuestion` picker binding | **yes**, 1 per session |
| `resources/harnesses/session-feed.md` | Text-only binding with the reply footer (first-class) | **yes**, 1 per session |
| `resources/harnesses/codex.md` | Routes to session-feed; Codex-specific notes and unverified items | **yes**, 1 per session |
| `README.md` | Human explainer: purpose, value proposition, overview, loop diagram | no |
| `CLAUDE.md` | This file — the maintainer contract | no |
| `docs/adrs/README.md` | ADR index: Lens per decision, plus the **compliance map** | no |
| `docs/adrs/TEMPLATE.md` | The ADR file shape and its filling rules | no |
| `docs/adrs/NNNN-*.md` | One decision each | no |

## Architecture principles

- **Search before you ask.** Decision records are consulted, and the search is named in the question, before any
  question is ranked (ADR-0008).
- The **reasoning is the product**: every answer surface must capture option and why together; a surface that cannot
  is not an adapter (ADR-0013).
- **A lens states its context and its inversion** — `Given` / `We prefer` / `Because` / `Unless` (ADR-0011).
- **One decision per turn**, cascade the choice *and* the lens before the next (ADR-0012, ADR-0016).
- **Anatomy is fixed; only previews scale.** Nothing is "cheap" (ADR-0002).
- **Shape and harness are orthogonal** and each is loaded singly, on demand (ADR-0004).
- Adapters bind section 9 only (ADR-0001).
- **Only `SKILL.md` and `resources/` bind a run.** Everything else is written for whoever edits them (ADR-0018).
- **The ADR log is the only knowledge store.** No ledger, no learning file — a ruling becomes an ADR *and* a change
  to the surface it governs, or it is not recorded at all (ADR-0020).

## ADR log

Lives in [docs/adrs/](docs/adrs/README.md), one file per decision, shaped by
[TEMPLATE.md](docs/adrs/TEMPLATE.md): metadata table, Lens blockquote, `Problem` (Symptom / Pain point), `Decision`
(The lens / In practice), `Consequences` (Pros / Cons). The index carries every Lens *and* a compliance map of every
`Enforced in` row, so read it first and self-answer; open a file only for its argument.

Accepted ADRs are immutable in substance — supersede with a new file and a cross-link, never an edit. Supersession may
be partial: a later ADR can retire one clause and leave the rest standing, recorded in the earlier ADR's Status and
`Relates to` rows plus a forward marker on the affected bullet, never by rewriting the clause. Reformatting to a new
template shape is not a change of mind.

Every lens is listed once, in the [index](docs/adrs/README.md#index), and only there. A second copy here would have to
be hand-edited on every new decision, which is how the two fall out of step.

## Extension checklist

- [ ] New shape → `resources/shapes/<name>.md` with recognise / anatomy deltas / generic worked example / shape
      checks; routing row in `SKILL.md` step 4.1; no base rules restated.
- [ ] New harness → `resources/harnesses/<name>.md` binding section 9 only; sensing row in `SKILL.md` step 4.2; if it
      lacks per-option reasoning, it routes to `session-feed.md`.
- [ ] New TBD route → `resources/tbd-routes.md` with what-happens-next and decision status; adapters updated to
      present it; the canonical route line updated everywhere it appears.
- [ ] User override during a run → straight to `docs/adrs/NNNN-*.md` from
      [TEMPLATE.md](docs/adrs/TEMPLATE.md), in the same turn, carrying the user's own words in `Problem`; a row in
      **both** index tables; the session named in `Provenance`; **and the runtime surfaces named in `Enforced in`
      changed in the same commit.** An ADR whose surfaces were not updated is the drift the log exists to prevent.
      There is no intermediate ledger to stage it in — see ADR-0020.
- [ ] Evals → rubric is the five checks plus the never-table; place under `evals/` per the repo's eval harness.
- [ ] Doc gates green; every file ≤ 500 lines; prose ≤120 columns; examples brand-agnostic.

## Known gotchas

- **Picker renders before the body** (Claude Code, seen once): the user sees only the picker. Symptom: "zero context,
  what is this asking?". Mitigation: the `question` text restates decision + stakes; labels self-describing.
- **`T` as the TBD label** reads as a fourth option in a text feed. Use `TBD`.
- **Fragment decision sentences** ("Decision: choose the X syntax") fail check 1 even when the rest is complete.
- **Preview pane truncation**: anything beyond a few lines is cut; the body holds the artifact, the pane holds a card.
- **A declined tool call** is the user exiting, not an answer — stop and wait.
- **A worked example that drops a section** (seen: the low-stakes example shipped without `Already settled`) teaches
  the defect ADR-0002 forbids. Check examples against the template, not against each other.
- **Route table and reply footer drifting apart** (seen twice: `task` absent from every reply surface; then `handoff`
  and `task` missing from the picker's `question` text while present in its preview). Symptom: a route the user cannot
  type. The footer's route line in `tbd-routes.md` is the single source; grep for `explain` and reconcile every hit.
- **A `show` artifact in the session scratchpad is not "somewhere the user can open it"** (seen 2026-08-24). Symptom:
  "you did not actually create the artifacts". `show` means real files at a real path in the repo, given as
  repo-relative links.
- **A markdown table row cannot fold.** A cell holding a quotation or a full condition measured 248 characters in a
  candidate ADR layout. Tables are for short values; sentence-shaped content goes in bullets.
- **The installed copy under `~/.claude/skills/` or a project's `.claude/skills/` can be stale.** Seen 2026-08-24: a
  `/concise-decisions` invocation loaded a pre-rewrite `SKILL.md` with no `docs/` and no shapes. Symptom: the skill
  behaves like an older version of itself. Check the loaded copy before trusting a run as evidence.
