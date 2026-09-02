# dadjoke — Maintainer Decision Lens

Read the ADR log below before changing anything. Each ADR carries a **Lens**; apply it to
the next decision instead of re-deriving the trade-off.

## Development contract

Prose skill with one paid eval cell and no scripts, so there is no `make fix`/`ci` loop.
The gates, run from the repository root, never `cd`:

```sh
# Free, deterministic. All three must exit 0 before handoff.
bun run skills/mermaidjs-diagrams/scripts/mermaid_contrast.ts   skills/dadjoke/README.md
bun run skills/mermaidjs-diagrams/scripts/mermaid_complexity.ts skills/dadjoke/README.md
uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 skills/dadjoke/README.md
```

All prose files stay at or under 500 lines (`rules/claude_skills/index.md`).

## File map

| File | Role |
|------|------|
| `SKILL.md` | Agent operating manual: theme resolution, brief, wave rules, Q&A form, quality bar, feedback loop |
| `README.md` | Human explainer: purpose, quickstart on both harnesses, architecture diagrams, troubleshooting |
| `CLAUDE.md` | This file: rationale and decision log |
| `agents/openai.yaml` | Codex UI metadata: display name, short description, default prompt mentioning `$dadjoke` |

## Architecture principles

- One body serves every harness. Anything harness-specific is resolved by a condition in
  the prose, never by a second copy of the skill.
- The theme is the one non-derivable input. Everything else has a default; the theme has a
  fallback ladder ending in a question.
- Feedback is evidence about this audience, not a comedy rule. The skill updates its brief
  from verdicts; it never defends a wave.
- The contract is prose. The eval grades the reply text, and the skill must leave the
  workspace untouched.

## ADR log

### ADR-1: the theme is the invocation argument, resolved by a fallback ladder

- **Status:** Accepted (2026-08-21)
- **Context:** The skill needed to take a theme as a parameter on Claude Code and Codex.
  Claude Code substitutes `$ARGUMENTS` on a real slash invocation; Codex substitutes
  nothing, so the placeholder reads literally and the theme is just the text after the
  `$dadjoke` mention. Headless `claude -p` with `--add-dir` also skips substitution.
- **Decision:** A bare `Theme argument: $ARGUMENTS` line followed by an ordered ladder:
  substituted argument, then text after the mention (when the line is blank or literal),
  then the theme of pasted jokes, then ask. Count and format are split out of the same
  argument.
- **Consequences:** One `SKILL.md` works on both harnesses and headless. The literal
  placeholder is visible to Codex models; the ladder tells them what it means.
- **Lens:** When a harness feature (substitution, a tool, a path) may be absent, write
  the body so its absence is a branch in the prose, not a broken step. Never ship a
  per-harness copy of the skill.

### ADR-2: keep `argument-hint` and `user-invocable` despite Codex's validator

- **Status:** Accepted (2026-08-21)
- **Context:** Codex's `skill-creator/scripts/quick_validate.py` whitelists frontmatter
  keys to `name, description, license, allowed-tools, metadata` and rejects these two.
  A live eval under a private `CODEX_HOME` (codex-cli 0.149.0, gpt-5.6-sol) showed the
  runtime lists the skill and reads its body with the keys present. This repository's
  other user-invocable skills carry both keys.
- **Decision:** Keep both keys. Treat the validator as an authoring lint for skills it
  generates, not as a load contract. Keep `<` and `>` out of `description`, which the
  validator also rejects and which costs nothing to honour.
- **Consequences:** The `/` menu shows the `<theme> [count] [Q&A]` hint in Claude Code.
  The validator run in the development contract is expected to fail on exactly these two
  keys; any third key it names is a regression.
- **Lens:** Distinguish a vendor's lint from its loader before stripping a feature.
  Prove the loader's behaviour with a real run, record which tool said what, and keep
  the feature if only the lint objects.


### ADR-4: sequences and checks are lists, not paragraphs

- **Status:** Accepted (2026-08-21)
- **Context:** The theme ladder, the brief fields, and the wave rules were each one
  paragraph. Ordered steps and pass/fail checks were hard to follow when fused into
  prose, and the ladder had no explicit stop rule until it was listified.
- **Decision:** Numbered lists for ordered steps (resolution ladder, joke construction),
  bullets for checks and extraction lists, a labelled lead-in sentence per list. Each
  item keeps its own precondition beside it.
- **Consequences:** `SKILL.md` grew from 61 to 93 lines with no new rules. The
  restructure exposed the missing stop rule, which was added.
- **Lens:** When a block is a sequence or a checklist, write it as one. If listifying
  reveals a missing condition, add the condition, not more prose.

### ADR-5: waves of three with at least two engines; feedback replaces rules

- **Status:** Accepted (original design, recorded 2026-08-21)
- **Context:** One-shot joke requests tend to return three variants of one mechanism,
  which gives the user nothing to choose between and no signal to steer by.
- **Decision:** Default wave of three, varied across at least two named engines, jokes
  only while the user evaluates. Feedback is distilled into three to six portable
  observations before the next wave; a user correction replaces the rule it contradicts.
- **Consequences:** Early waves are exploratory by design. The skill can look like it
  "ignored" a house style until the user states it, at which point that statement wins.
- **Lens:** Optimise each wave for the information the user's verdict will carry, not
  for the single best joke. Treat a correction as data about this audience and rewrite
  the rule; never defend a wave.

### ADR-6: no scripts, by design

- **Status:** Accepted (2026-08-21)
- **Context:** The repository's script tiers (`rules/claude_skills/environments.md`)
  exist for skills that need execution. Nothing here does; the only mechanics are
  reading the argument and writing prose.
- **Decision:** No `scripts/`, no Makefile, no preflight. The development contract is the
  doc gates plus the paid eval cell.
- **Consequences:** The skill runs identically in the most restricted environments. There
  is no `make ci`; "done" is the gate list above exiting as documented.
- **Lens:** Add a script only when a run demonstrably needs one (a repeated helper
  several runs wrote themselves, or a deterministic check). A prose skill that gains a
  script must also gain the tiered fallback, so do not add one speculatively.

## Extension checklist

- [ ] `SKILL.md` still has the bare `Theme argument: $ARGUMENTS` line and the four-step ladder (ADR-1).
- [ ] Frontmatter still has exactly `name`, `description`, `argument-hint`, `user-invocable`; no `<`/`>` in `description` (ADR-2).
- [ ] `agents/openai.yaml` `default_prompt` still mentions `$dadjoke`; `short_description` is 25–64 characters.
- [ ] Both mermaid gates and `md_toc` exit 0 on `README.md`; the root `README.md` dadjoke entry still matches the argument shape.
- [ ] New rules are stated as conditions or list items, not added cases (ADR-4); a new mechanism gets an ADR with a Lens.
- [ ] Every prose file is at or under 500 lines.

## Known gotchas

- **Symptom:** Codex output contains the literal string `$ARGUMENTS`. **Cause:** Codex
  never substitutes; the ladder's step 2 is the intended path. Do not "fix" by removing
  the line, which breaks Claude Code substitution.
- **Symptom:** `claude -p` ignores the theme or asks for it. **Cause:** `--add-dir` grants
  file access but does not register a skill, so `/dadjoke x` is not a slash invocation
  there. Put the skill under the cwd's `.claude/skills/` and pass `--setting-sources project`.
- **Symptom:** Codex validator fails. **Cause:** two expected keys (ADR-2). A third key
  or an angle bracket in `description` is a real failure.
- **Symptom:** A weaker model tier prefixes the wave with a sentence of narration.
  **Cause:** Observed once on a small model; the "jokes only" rule is in `SKILL.md`. Do not
  add a shouting rule for one sample; re-check on the eval's default matrix first.
- **Symptom:** Eval cell fails on `files_written`. **Cause:** The model created a scratch
  file. That is a skill defect, not a harness one; the skill must leave the workspace alone.
