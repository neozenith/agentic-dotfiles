---
name: prwalkthrough
description: "Walk a human through any PR or diff, regardless of size. Distills 100s-1000s of changed files into their deeper structure: a few distinct mechanical change patterns (each shape-checked for hidden deviants) plus the genuinely novel changes, then acts as an interactive guide revealing detail incrementally until the reviewer is satisfied. Use when the user says 'walk me through this PR', 'explain this diff/PR', 'what actually changed here', or faces a huge PR they can't review file-by-file. Skip when the user wants a verdict on code quality — that's /codereview."
argument-hint: "[PR number | ref range | branch] (default: current branch vs merge-base)"
user-invocable: true
---

# PR Walkthrough

Convert a diff of any size into its **deeper structure**: the few distinct
change patterns that actually happened, not the surface list of files. Honest
value claim: decomposition's measured benefit is **fewer false conclusions**
(not faster review or more defects found) — so every rule optimizes for
correct understanding and calibrated trust, never for reading speed.

## Phase 0 — Scope & stated intent

1. Resolve the diff: explicit PR number (`gh pr view/diff`), ref range, or
   current branch vs `git merge-base origin/<default> HEAD` plus uncommitted.
2. Collect the **stated intent** (PR description, commit messages, linked
   issues) — but treat it as a *claim to verify, never the frame*: ~44% of
   commit messages lack what/why, and for refactoring commits ~60% are
   inconsistent with the actual change. The narrative is built from the code;
   stated intent is diffed against it.
3. Headline numbers: `git diff --shortstat`, `--dirstat=files,0`, file count.

## Phase 1 — Structural distillation (clustering)

Run the git-only clustering algorithm in
[resources/clustering.md](resources/clustering.md) — read it now. It yields:

| Set | Contents | Treatment |
|-----|----------|-----------|
| **Noise** | lockfiles, generated, vendored (`linguist-generated` + sampled path heuristics) | One bullet with counts. |
| **Mechanical clusters** | files sharing one change shape — template, count, exemplar, deviant list | One bullet per cluster + exemplar; deviants promoted out. |
| **Novel set** | residual files + ejected deviants, ranked by risk (security-sensitive paths first), then churn × centrality | Guided reveal. |

Hard rules:
- **Verify every cluster member; compare ordered token sequences with a
  consistent identifier mapping — never token sets/bags.** Bag comparison is
  order-blind: an argument swap (`f(x, y)` → `f(y, x)`) passes a set check.
  Operators and literals are never normalized away.
- **The label is `shape-checked`, not "verified"** — and its scope is stated
  wherever it appears: *token-level only; does not check semantics, ordering
  across hunks, or cross-file interactions*. Overtrust in automation labels
  causes omission errors; the label must say what it cannot catch.
- Run diffs with `-M -C`; similarity <100% = "moved AND edited" — review the
  edit. Commit boundaries seed clusters but never decide them.
- For large diffs, fan verification out to parallel subagents.

## Phase 2 — The map (one screen, calibrated)

Lead with a code-grounded summary; flag intent discrepancies immediately.

```
## Walkthrough: <what the code actually does, one sentence>
**Stated intent says:** <match | "PR says X; the code also does Y / not Z">

**Shape:** N files / +A −D · K patterns + M novel changes + noise

1. ✨ <novel change 1: what & why>                 — 3 files   ← start here
2. ✨ <novel change 2>                             — 2 files
3. ⚠️ Deviants: <files that broke their pattern>   ← always shown, never folded
4. 🔁 <pattern template, human-phrased>            — 412 files [shape-checked*]
5. 🔁 <pattern 2>                                  — 87 files  [sampled only]
6. 🗑 Noise: N lockfile/generated updates

*shape-checked = token-level equivalence only; semantics not verified.
**Not shown / not checked:** <the waved-through LOC total, unsampled noise,
cross-file interactions — what accepting this map means trusting>

**Next?** (a) novel change 1 · (b) deviants · (c) pattern exemplars ·
(d) full narrative · (e) done
```

Map rules:
- Deviants and security-sensitive paths (auth, crypto, input handling,
  CI/release config) are **expansion-exempt**: surfaced eagerly, never behind
  a fold. Folded content is reliably missed.
- Per cluster, state the total LOC being waved through — the reviewer
  consciously accepts an N-thousand-LOC exemption rather than feeling
  "reviewed".
- Every behavioral claim in any narration carries a `file:line` citation and
  quotes diff lines for load-bearing claims. No color or backstory that
  doesn't change what the reviewer should check.

## Phase 3 — Guided cascade (interactive reveal)

You are a guide revealing cascading detail one section per turn. The reviewer
ends the walkthrough whenever they're satisfied — their attention is the
budget being protected.

1. On each pick, reveal ONE section at the next level of detail:
   novel change → its files in dependency order (data model → logic → call
   sites → tests) with narrated hunks; pattern → template + exemplar + most
   dissimilar member + deviant diffs; noise → the file list.
2. After each section, re-offer the menu with progress markers
   (`✓ seen · → suggested next · unvisited`) and keep the **Not shown** line
   current — the reviewer always sees their own coverage gap.
3. Suggest the next-highest-risk unvisited section, but the reviewer chooses.
   Never batch multiple sections; never push past "done".
4. On "done"/"stop": close with a two-line summary naming what was visited
   and **what was never opened** (sections, waved-through LOC) so ending
   early is an informed choice, not silent clearance.

## Cross-cutting rules

- Never assert "these N files got the same change" beyond what the Phase 1
  check actually proved — say `shape-checked` or `sampled`, with scope.
- When clustering quality is marginal (many small clusters, low strict-tier
  agreement), say so: "this diff may not have a clean core; the framing may
  be wrong." A fluent story raises trust whether or not it's right — narrate
  uncertainty with the same prominence as the story.
- State the skill's evidence limits if asked: reduced false conclusions is
  measured; better defect detection is not.
- Most turns ≤ one screen; depth on request.

Evidence and counter-evidence: [resources/evidence.md](resources/evidence.md).
