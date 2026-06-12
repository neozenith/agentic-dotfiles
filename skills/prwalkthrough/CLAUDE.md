# prwalkthrough — Maintainer Decision Lens

Read the ADR log below before changing anything. Each ADR carries a **Lens** —
apply it to the next decision instead of re-deriving the trade-off.

## Development contract

Docs-only skill (no `scripts/` directory, so no Makefile `fix`/`ci` loop).
Gates before handoff, run from repo root:

```sh
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_contrast.ts   .claude/skills/prwalkthrough/README.md
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts .claude/skills/prwalkthrough/README.md
uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 .claude/skills/prwalkthrough/README.md
```

All files ≤ 500 lines (`.claude/rules/claude_skills/index.md`).

## File map

| File | Role |
|------|------|
| `SKILL.md` | Agent operating manual: phases, output contract, loop rules |
| `README.md` | Human explainer: purpose, quickstart, architecture diagrams |
| `resources/clustering.md` | The git-only clustering algorithm (lazy-loaded) |
| `resources/evidence.md` | Research citations behind each rule (lazy-loaded) |
| `CLAUDE.md` | This file — rationale and decision log |

## Architecture principles

- Clustering claims are **verification claims**: a cluster is never declared
  mechanical from file lists or sampling — only from per-member content checks.
- The narrative spends human attention proportional to novelty, not file count.
- The interactive loop shares its contract with the sibling `coach` skill
  (one question per turn, learner-controlled pace).

## ADR log

### ADR-1: git-only clustering, no external tooling

- **Status:** Accepted
- **Context:** Refactoring-detection tools (RefactoringMiner, RefDiff) and AST
  differs are more precise but introduce per-language dependencies the skill
  can't assume in arbitrary repos.
- **Decision:** Build clustering on `git patch-id` (strict tier) plus
  token-normalized hashing via `sed`/`shasum` (loose tier).
- **Consequences:** Works in any git repo with zero setup; loose tier can
  over-merge, mitigated by the two-tier rule.
- **Lens:** When choosing between a sharper language-specific tool and a
  universal git primitive, take the git primitive and compensate with a
  verification pass — the skill must work on *anyone's* PR.

### ADR-2: deviant detection is exhaustive, never sampled

- **Status:** Accepted
- **Context:** The whole value claim is "412 files = 1 pattern". A hidden
  hand-edit inside the sweep (the needle in the codemod) is both the main
  correctness risk and a known malicious-change vector.
- **Decision:** Every cluster member gets a token-set/hunk-count check; output
  labels each cluster `machine-verified` or `sampled`.
- **Consequences:** Slower on huge PRs (fan out to subagents); the label keeps
  the human's trust calibrated.
- **Lens:** Any statement of the form "these N files all got the same change"
  is a security claim — never make it from a sample, and always disclose the
  verification level.

### ADR-3: narrative is pyramid-ordered, map-first

- **Status:** Accepted
- **Context:** Review research says understanding/rationale is the bottleneck
  and attention collapses past ~400 LOC; dumping sections linearly buries the
  novel core.
- **Decision:** One-screen map (patterns + novel + deviants + noise), then
  progressive disclosure via a menu; intent paragraph always first.
- **Consequences:** Most turns fit one screen; the human chooses depth.
- **Lens:** When adding a new output section, it must earn a line on the map —
  if it can't be summarized in one map line, it belongs behind the menu.

### ADR-4: comprehension loop reuses the coach contract

- **Status:** Accepted
- **Context:** A second bespoke quiz protocol would drift from `coach` and
  double maintenance.
- **Decision:** Same per-turn rules (one diagnostic question, type choice,
  misconception-encoding distractors, learner stops anytime), anchored only on
  novel changes and deviants.
- **Consequences:** Familiar UX across skills; no quiz state file (PR
  understanding is session-scoped, unlike topic mastery).
- **Lens:** Interactive teaching loops in this repo follow the coach contract;
  diverge only with a recorded reason here.

## Extension checklist

- [ ] New clustering heuristics go in `resources/clustering.md` with the exact
      command, and a matching pitfall/mitigation if they can mislead.
- [ ] New narrative sections earn a map line (ADR-3).
- [ ] Verification level labels preserved in any output format change (ADR-2).
- [ ] Both mermaid gates + mdtoc re-run if README touched; all files ≤ 500 lines.

## Known gotchas

- `git patch-id` without `--stable` produces different hashes across diff
  orderings — always pass `--stable`.
- `uniq -c -f1` field counting is whitespace-sensitive; the quickstart pipe
  assumes `path hash` order (path first).
- `git check-attr` on a huge file list needs `xargs`; direct expansion can
  blow the arg limit on 1000+-file PRs.
- A formatting sweep over a file that ALSO got a logic edit only reveals
  itself via the `git diff -w` non-empty check — easy to forget.
