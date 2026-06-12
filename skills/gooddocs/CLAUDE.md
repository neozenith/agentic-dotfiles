# gooddocs — Maintainer Decision Lens

Read the ADR log below before changing anything. Each ADR carries a **Lens** —
apply it to the next decision instead of re-deriving the trade-off.

## Development contract

Docs-only skill (no `scripts/`, so no Makefile `fix`/`ci` loop). Gates before
handoff, run from repo root:

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
| `CLAUDE.md` | This file — rationale and decision log |

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

## Extension checklist

- [ ] New claim types added to the SKILL.md check table define their evidence
      form (ADR-3).
- [ ] Style additions routed per ADR-2 (lenses vs voice).
- [ ] Audit remains read-only — no new check may execute a mutating command.
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
