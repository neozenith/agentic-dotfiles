# concise-decisions — ADR log

The decision record for this skill, one file per decision (`NNNN-short-name.md`, four digits so lexical sort is
chronological). Parent: [CLAUDE.md](../../CLAUDE.md), which owns the dev contract, file map, principles, extension
checklist, and gotchas.

**None of this is loaded at runtime.** `SKILL.md` and `resources/` are the only runtime authority (ADR-0018). These
files govern the people and agents *editing* those surfaces. When a runtime surface and an ADR disagree, the surface
is wrong — fix the surface, never edit the record.

**Read the lens first.** Each ADR's lens is a forward-looking rule that answers the next question of its kind without
re-deriving the trade-off. The list below is all twenty; open a file only when you need its argument.

## Index

- **[0001](0001-two-surfaces-briefing-then-answer-channel.md) — A question is two surfaces: a briefing, then one
  answer channel**
  *Reasoning material stays in the body; only the choice moves into the answer surface.*
- **[0002](0002-no-cheap-question-form.md) — There is no cheap question form**
  *A variant that removes a section is a defect. Shrink content, never structure.*
- **[0003](0003-tbd-route-family-defer-is-partial-decision.md) — The escape hatch is a route family, and `defer` is a
  partial decision**
  *A new "I can't answer yet" joins the route table with a what-happens-next and a decision status — never as a
  fourth ordinary option.*
- **[0004](0004-shapes-and-harnesses-are-separate-lazy-files.md) — Shapes and harnesses are separate lazy files**
  *Every-shape rules live in `SKILL.md` or the template; one-harness rules live in its adapter. Delete restatements.*
- **[0005](0005-no-multi-select-composing-options-become-permutations.md) — Multi-select is never used; composing
  options become permutations**
  *When a surface cannot carry per-option reasoning, change the question shape, not the requirement.*
- **[0006](0006-text-feed-is-a-first-class-adapter.md) — The text feed is a first-class adapter**
  *Environment degradation changes where the answer is typed; requirement degradation is never an adapter's call.*
- **[0007](0007-five-question-check-is-the-acceptance-rubric.md) — The five-question check is the acceptance rubric**
  *Grade a question cold from the answer surface, not against how it reads with full context in mind.*
- **[0008](0008-check-decision-records-before-asking.md) — Decision records are searched before any question is
  ranked**
  *The first cost of a question is a search, not a sentence. No `Checked:` line means you are not ready to ask.*
- **[0009](0009-defer-logs-the-whole-question-as-a-ticket.md) — `defer`/`handoff` logs the entire question as a
  backlog ticket**
  *A TBD route leaves behind everything needed to take its next step without the agent present — content, never a
  pointer.*
- **[0010](0010-headings-index-the-hierarchy-of-information.md) — Headings index the hierarchy of information in an
  ADR**
  *Every part a reader returns to needs a name. Prefer a heading over a bold run-in when the part is read out of
  order.*
- **[0011](0011-lens-grammar-given-prefer-because-unless.md) — A lens is written `Given` / `We prefer` / `Because` /
  `Unless`**
  *A lens without an `Unless` is an assertion, not a decision, and cannot be safely reused when the context moves.*
- **[0012](0012-one-decision-per-turn.md) — One decision per turn; a wizard cannot cascade**
  *Batching questions destroys information: the first answer can no longer change the second question.*
- **[0013](0013-free-text-on-the-chosen-option-is-the-contract.md) — Free text on the chosen option is the contract,
  not a courtesy**
  *A surface that captures the choice but not the why is not an answer surface.*
- **[0014](0014-previews-are-complete-outcomes-on-real-data.md) — Previews are complete outcomes on real data; the
  pane holds a card**
  *An illustration of the outcome is not a smaller preview; it is a different and useless thing.*
- **[0015](0015-the-briefing-is-scanned-not-read.md) — The briefing is scanned, not read**
  *Assume the reader lands mid-document. Labels and self-describing titles are how they find their place; prose is
  not.*
- **[0016](0016-the-cascade-carries-the-lens-not-only-the-choice.md) — The cascade carries the lens, not only the
  choice**
  *An answer resolves its own question; the reasoning resolves questions nobody has asked yet.*
- **[0017](0017-reply-grammar-is-two-prose-lines.md) — The reply grammar is two prose lines, and a bare route name is
  valid**
  *A reply grammar is instructions to a person, not a parser spec. Write the sentence, then accept what they type.*
- **[0018](0018-runtime-authority-is-skill-md-and-resources.md) — Runtime authority is `SKILL.md` and `resources/`;
  everything else is dev-time**
  *A document not loaded during a run cannot constrain the run — only the people editing what is loaded.*
- **[0019](0019-ranking-is-shown-not-only-performed.md) — The ranking is shown, not only performed**
  *Claiming a question is the most important one is not evidence. Name what it outranks.*
- **[0020](0020-the-adr-log-is-the-only-knowledge-store.md) — The ADR log is the only knowledge store; there is no
  adjudications ledger**
  *One store, or none. Write the ruling where the rule lives, or do not write it.*

All twenty are **Accepted**. ADR-0020 supersedes one clause each of ADR-0018 and ADR-0008, per the partial-supersession
mechanism in *Adding an ADR* below; no ADR has been superseded whole, and no ADR's argument has been rewritten. Dates
and provenance live in each file's metadata table.

## Compliance map

There is no per-ADR Compliance section — the audit anchor is each file's `Enforced in` row, collected here. To check
whether the skill still honours its own decisions, walk this table: for each ADR, open the named surfaces and confirm
they say what that ADR's `In practice` clauses require.

| # | Enforced in |
|---|---|
| 0001 | `SKILL.md` §§ Requirement, Never · steps 4, 4.3, 4.5 · `question-template.md` · `harnesses/*.md` |
| 0002 | `SKILL.md` §§ Rules/Never/Pragmatic default · `question-template.md` · `shapes/low-stakes.md` |
| 0003 | `SKILL.md` step 4.3 row 8 · check 5 · § After the answer 5 · § Never · `tbd-routes.md` · `harnesses/*.md` |
| 0004 | `SKILL.md` steps 4.1, 4.2 · § Resources · `shapes/*.md` · `harnesses/*.md` |
| 0005 | `SKILL.md` step 4.1 · § Never · `shapes/subset-as-permutations.md` · `harnesses/claude-code.md` |
| 0006 | `SKILL.md` step 4.2 · `harnesses/session-feed.md` · `harnesses/codex.md` |
| 0007 | `SKILL.md` steps 4.4, 4.5 |
| 0008 | `SKILL.md` step 2 · §§ Decision records, Never · step 4.3 row 3 · check 3 · `question-template.md` |
| 0009 | `tbd-routes.md` §§ Routes/Where the ticket goes · `SKILL.md` § After the answer 5 · `question-template.md` |
| 0010 | none — dev-time only |
| 0011 | `SKILL.md` § After the answer 3 · `question-template.md` § Filling rules |
| 0012 | `SKILL.md` steps 4, 4.5, 6 · § Never · `harnesses/claude-code.md` · `harnesses/session-feed.md` |
| 0013 | `SKILL.md` § The requirement · step 4.3 row 9 · check 4 · § Never · `harnesses/*.md` |
| 0014 | `SKILL.md` §§ Rules, Never · `question-template.md` § Filling rules · `harnesses/claude-code.md` |
| 0015 | `SKILL.md` § Rules that do not bend · `question-template.md` § Filling rules · `harnesses/session-feed.md` |
| 0016 | `SKILL.md` step 5 · § After the answer 2–4 · § Never · `harnesses/*.md` |
| 0017 | `question-template.md` footer · `tbd-routes.md` § Presenting the routes · `harnesses/*.md` |
| 0018 | `SKILL.md` § Resources |
| 0019 | `SKILL.md` step 4.3 row 2 · check 2 · `question-template.md` § Why decide this now |
| 0020 | `SKILL.md` § Resources · § Decision records row 3 |

## Adding an ADR

1. Copy [TEMPLATE.md](TEMPLATE.md). Its filling rules are the contract — one rule per ADR, `Unless` never blank,
   `Enforced in` names surfaces and not conditions.
2. Name it `NNNN-short-name.md` with the next number. Add an entry to the index **and** a row to the compliance map.
3. If it supersedes an earlier ADR **whole**, set that one's Status to `Superseded by ADR-NNNN` and link both ways.
   If it supersedes only **one clause** of an earlier ADR, the same mechanism applies at clause scope: append the
   supersession to that ADR's Status row naming the clause, add the pair to both `Relates to` rows, and mark the
   affected `In practice` bullet with a parenthetical note pointing forward. The superseded ADR's argument, lens, and
   remaining clauses are left exactly as written: a Status row and a forward marker are metadata, not a change of
   mind, and both sides must describe the relation with the same word.
4. Write the ruling that forced it — the user's own words — into `Problem`, and name the session in `Provenance` as
   prose. There is no ledger to promote from and none to leave evidence in (ADR-0020).
5. Change the runtime surfaces named in `Enforced in` in the same commit. An ADR whose surfaces were not updated is
   the drift this log exists to prevent.
