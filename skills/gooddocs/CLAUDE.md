# gooddocs — Maintainer Decision Lens

Read the ADR log below before changing anything. Each ADR carries a **Lens** —
apply it to the next decision instead of re-deriving the trade-off.

## Development contract

Prose skill + eval suite. Doc gates before handoff, run from repo root:

```sh
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_contrast.ts   .claude/skills/gooddocs/README.md
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts .claude/skills/gooddocs/README.md
uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 .claude/skills/gooddocs/README.md
```

All files ≤ 500 lines (`.claude/rules/claude_skills/index.md`).

## File map

| File | Role |
|------|------|
| `SKILL.md` | Agent operating manual: modes, claim-check table, report format |
| `README.md` | Human explainer: purpose, quickstart, architecture diagram |
| `resources/lenses.md` | Lens taxonomy + style principles + OSS survey (lazy) |
| `resources/structure.md` | Markdown structure rules, smells, spec/plan skeletons (lazy) |
| `resources/voice.md` | Maintainer voice fingerprint — loaded only on `voice` |
| `resources/slop_smells.md` | Curated AI-slop smell catalog + capture-THE-WHY guidance (lazy; maintainer-grown) |
| `scripts/evals/` | Base eval: drifted-README fixture, golden, runner (via `_evalkit`) |
| `CLAUDE.md` | This file — rationale and decision log |
| `../../workflows/gooddocs-audit.js` | Reusable named **dynamic workflow** wrapping AUDIT (+ safe-fix) for loop/schedule use; reads this skill's doctrine at runtime |

Eval suite (`.claude/rules/claude_skills/evals.md`): `make -C
.claude/skills/gooddocs/scripts ci` (free), `… evals` (paid golden runs).

## Architecture principles

- Truth before style: drift detection outranks prose polish.
- One lens per page; voice is a register layered on lenses, never a substitute.
- Audit is read-only; no mutating command is ever executed to "verify" a doc.

## ADR log

### ADR-1: audit is the default mode

- **Status:** Accepted
- **Context:** "Incorrect documentation is worse than missing documentation"
  (Write the Docs "Current" principle); stale docs actively mislead, and the
  user's primary ask was corroborating docs against code reality.
- **Decision:** Bare `/gooddocs` audits; writing requires an explicit target.
- **Consequences:** The skill never silently rewrites; every write is preceded
  by at least a mini-audit of carried-forward claims.
- **Lens:** Any new feature must answer "does this help docs be *true*?"
  before "does this help docs be *pretty*?" — truth features win ties.

### ADR-2: voice is opt-in and layered, not a fork

- **Status:** Accepted
- **Context:** The maintainer wants docs optionally in his personal voice, but
  the researched lens discipline must hold either way; duplicating the style
  principles into a "voice edition" would drift.
- **Decision:** `resources/voice.md` is loaded only on the `voice` flag and
  changes register/signature moves only; `lenses.md` always applies.
- **Consequences:** One source of truth for structure; voice file stays small
  and personal; default output is brand-agnostic researched style.
- **Lens:** New style guidance goes in `lenses.md` if it's about *what good
  docs do*, in `voice.md` only if it's about *how this maintainer sounds*.

### ADR-3: claims are verified by subagents reading code, never by trusting docs

- **Status:** Accepted
- **Context:** Documentation drift research (just-in-time inconsistency
  detection, Swimm auto-sync) shows doc claims must be checked against the
  artifact, not against other prose; LLMs readily "confirm" plausible text.
- **Decision:** The audit fan-out gives each subagent the doc plus repo
  access; verdicts require `file:line` or command-output evidence; read-only
  commands only.
- **Consequences:** Audits cost subagent tokens; `unverifiable` is an honest
  verdict category rather than a guess.
- **Lens:** A claim without evidence is `unverifiable`, never `confirmed` —
  if adding a new claim type to the check table, define its evidence form
  first.

### ADR-4: survey-derived principles live in one lazy resource

- **Status:** Accepted
- **Context:** The 23-project survey and lens taxonomy are reference material;
  inlining them in SKILL.md would bloat the always-loaded surface past the
  point an agent reads it.
- **Decision:** SKILL.md keeps operations; `lenses.md` keeps the taxonomy,
  principles, and survey, loaded on first use.
- **Consequences:** SKILL.md stays under two screens; principles are citable
  by number ("principle 3: negative space").
- **Lens:** SKILL.md carries *how to operate*; anything an agent consults
  rather than executes goes to `resources/`.

### ADR-5: restructure is a distinct mode that never touches claims

- **Status:** Accepted
- **Context:** The maintainer wants the skill to improve the *structural*
  readability of existing docs and spec/plan files. Folding this into write
  mode would invite silent rewording of technical content during what should
  be a shape-only operation; structure has its own evidence base (layer-cake
  scanning, ~20-28% of words read, 4±1 chunking) and its own rulebook.
- **Decision:** A third mode with a hard contract: outline-first proposal,
  claims preserved verbatim, suspected-wrong claims flagged for audit rather
  than fixed inline. Rules live in `resources/structure.md`, which also feeds
  write mode (step 3). Whitespace guidance is justified by chunking/scanning
  evidence only — the widely-cited "Lin 2004 whitespace +20% comprehension"
  number is a debunked secondary-referencing error and must not be cited.
- **Consequences:** Restructure PRs are reviewable as pure moves; meaning
  changes can't hide inside reformatting (the same two-hats discipline the
  `refactor` skill applies to code).
- **Lens:** Shape changes and content changes never share a pass — if a
  restructure tempts you to fix a claim, that's a mode switch the user must
  see, not a drive-by edit.

### ADR-6: visuals are curated dual-density; authoring delegates to mermaidjs_diagrams

- **Status:** Accepted
- **Context:** The maintainer's practice: lots of diagrams to break up text
  walls and visually encode information, with simplified diagrams shown
  top-level and ultra-detailed variants hidden in `<details><summary>` blocks
  (opt-in cascading detail). The repo already has a dedicated
  `mermaidjs_diagrams` skill owning palette, WCAG contrast, and complexity
  gates; duplicating that knowledge here would drift.
- **Decision:** structure.md rules 16-17 encode the technique (diagram +
  one-sentence prose summary; dual-density pair with inviting `<summary>`
  labels). All diagram *authoring* is delegated to a subagent that invokes
  the `mermaidjs_diagrams` skill; gooddocs only decides where a visual earns
  its place and at what density.
- **Consequences:** gooddocs output inherits the gate guarantees without
  owning them; diagram-style changes happen in one skill and propagate.
- **Lens:** When gooddocs needs a capability another skill owns (diagrams,
  TOCs via mdtoc), it orchestrates that skill — it never reimplements it.
  New techniques enter as *placement rules* here, *rendering rules* there.

### ADR-7: the audience ladder is the top-level axis; Diátaxis is within-rung; purity softened

- **Status:** Accepted (2026-06; amends ADR-4's content and the original
  "non-negotiable" purity stance)
- **Context:** The maintainer clarified that "lenses" meant the three-stage
  learning ladder (Quickstart → User Guides → API Reference = Beginner →
  Intermediate → Expert). Red-team research confirmed: major docs sites put
  the ladder at top-level nav with Diátaxis types inside rungs; Diátaxis's
  own author disclaims per-page purity; whole genres don't fit the four
  types; scannability evidence is about lookup tasks, not learning.
- **Decision:** Two-axis classification (rung × lens). Scannability/BLUF at
  full force on lookup rungs, relaxed on learning rungs. Purity is a default
  with sanctioned escapes (deliberate fusion, small-project single README,
  overview/FAQ/gallery categories).
- **Consequences:** Audit severity became claim-type × rung-traffic; write
  mode picks rung before lens.
- **Lens:** When classifying a doc, ask "who is the reader and how much do
  they already know" (rung) before "what are they trying to do" (lens) —
  and never enforce a framework harder than its own author does.

### ADR-8: audits are adversarial and execution-first

- **Status:** Accepted (2026-06; hardens ADR-3)
- **Context:** Sycophancy research: LLMs confirm plausible claims at high
  rates and judges are swayed by detailed-but-wrong reasoning; a real
  file:line citation can fail to entail the claim it decorates.
- **Decision:** Subagent briefs say "find evidence this claim is FALSE";
  executable checks outrank reading; verdicts split `confirmed-by-execution`
  vs `confirmed-by-reading (LLM judgment, not proof)`; remediation is
  fix-or-flag, never delete.
- **Consequences:** Audits report honest confidence tiers; a "clean" audit is
  never presented as ground truth.
- **Lens:** A claim is only as confirmed as the strongest *non-LLM* mechanism
  that checked it; design every new check to maximize the executable share.

### ADR-9: code is authoritative; drift is continuous, so is the audit

- **Status:** Accepted (2026-06)
- **Context:** The reason gooddocs exists is that **code is the source of truth
  and docs go stale.** The maintainer wants to keep drift low by running the
  skill in another process — a `loop` or a schedule — *while working*, not as a
  rare one-shot sweep.
- **Decision:** State the premise explicitly: when doc and code disagree the
  doc is stale by default; the only exception is a doc that is a spec/contract
  the code violates (flag, don't "fix"). Design for **repeated, scoped** runs
  against actively-edited files, and wrap the audit fan-out as a reusable named
  dynamic workflow (`.claude/workflows/gooddocs-audit.js`) for loop/schedule use.
- **Consequences:** Audit accepts an explicit path set (the loop case) instead
  of always globbing; "doc is stale" as the default is what makes
  non-interactive autofix tractable at all.
- **Lens:** When doc and code disagree, fix the doc unless it is a spec the code
  violates — and prefer a small scoped run you can repeat over a big one-shot.

### ADR-10: documentation includes in-code docs; the audit ports to a workflow

- **Status:** Accepted (2026-06)
- **Context:** Docstrings and explanatory comments are documentation and drift
  identically to `.md`; and the audit fan-out is orchestration-shaped, so it
  ports to a deterministic dynamic workflow that can run headless on a schedule.
- **Decision:** Audit scope includes in-code docs (each unit tagged
  `markdown` or `in-code`). The workflow encodes *orchestration* in JS while
  *doctrine* (claim table, smell catalog) stays in the skill and the workflow's
  agents **read it at runtime** — one source of truth. The audit's read-only
  invariant is enforced by giving verifier agents a read-only agent type, not by
  trusting a prompt.
- **Consequences:** Comments/docstrings get the same drift/slop/why scrutiny;
  the skill stays the doctrine and the workflow the orchestrator, never
  duplicating rules.
- **Lens:** When a skill's value is parallel fan-out, port *that* to a workflow
  and have it read the skill's doctrine — never copy the rules into the
  orchestrator, or they drift from each other.

### ADR-11: slop is a curated, maintainer-grown catalog; pruning it is the one sanctioned deletion

- **Status:** Accepted (2026-06)
- **Context:** AI-authored docs accrete recognizable **slop** — self-addressed
  task notes, deletable filler, hard-coded value lists that duplicate code and
  make refactors expensive. The maintainer will grow this list over time as new
  smells surface.
- **Decision:** `resources/slop_smells.md` is an append-only catalog with a
  fixed entry template; audit emits `category: slop` findings; **pruning
  identified slop is allowed**, whereas deleting *drifted* content is not (that
  stays fix-or-flag).
- **Consequences:** The skill sharpens as the catalog grows with zero code
  changes; deletion stays principled.
- **Lens:** Separate "content that should not exist" (slop → prune) from
  "content that is stale" (drift → fix-or-flag); only the former may be deleted.
  Every line must survive the delete test; value lists live in code, not prose.

### ADR-12: THE WHY is captured in-context as a decision lens; why-gaps are flag-only

- **Status:** Accepted (2026-06)
- **Context:** Code and docs capture *what* and *how* but rarely *why a thing
  exists*. The maintainer curates ADRs precisely to **accumulate the project's
  values**, which become the decision lens for future work — and the richest
  WHY is often the language used while prompting, which should be preserved
  "like a letter to a future reader."
- **Decision:** WHY is a first-class authoring obligation (a cross-cutting rule
  + a write-mode step): a short WHY beside the code in critical places, bigger
  reasons as ADRs. Audit emits `category: why-gap` for critical places missing
  it, but why-gaps are **flag-only** and safe-autofix **never fabricates
  rationale.**
- **Consequences:** The decision lens travels with the context; the skill can
  detect a missing WHY but will not invent one.
- **Lens:** When something is non-obvious, record *why* it is so (not just what)
  next to it, and treat the maintainer's prompting prose as primary source for
  that WHY. A machine may flag a missing WHY; only a human may supply it.

## Extension checklist

- [ ] New claim types added to the SKILL.md check table define their evidence
      form (ADR-3).
- [ ] Style additions routed per ADR-2 (lenses vs voice).
- [ ] Audit remains read-only — no new check may execute a mutating command.
- [ ] New slop smells follow the `slop_smells.md` entry template; pruning slop
      is the only sanctioned deletion (ADR-11).
- [ ] In-code docs (comments/docstrings) audited with the same rigor as `.md`
      (ADR-10); `why-gap` findings stay flag-only — autofix never invents a WHY
      (ADR-12).
- [ ] Audit-orchestration changes update `../../workflows/gooddocs-audit.js`;
      doctrine stays in the skill, not copied into the workflow (ADR-10).
- [ ] Both mermaid gates + mdtoc re-run if README touched; all files ≤ 500 lines.

## Known gotchas

- `git log -1 -- <doc>` vs code-dir dates is a heuristic: a doc younger than
  the code can still be wrong, and an old doc can be perfectly current — age
  only prioritizes, never verdicts.
- Link checkers rate-limit on external URLs; spot-check externals, fully check
  internals.
- Lens classification of legacy pages is often "mixed" — the verdict is a
  split proposal, not a forced single label.
- The voice file deliberately contains no project nouns (agnostic rule); if an
  excerpt would leak one, genericize it before adding.
- The workflow's read-only audit guarantee comes from the verifier **agent
  type** (no Edit/Write tool), not the prompt. Swap the agent type and you can
  silently break the read-only invariant (ADR-8/ADR-10) — the prompt won't save
  you.
- Safe-autofix (`mode=fix`) edits **documentation text only** (markdown prose or
  comment/docstring text) and requires drift `authority=code` before touching a
  claim; it must never change executable code. `why-gap` is never auto-applied.
