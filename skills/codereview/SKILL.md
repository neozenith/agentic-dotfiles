---
name: codereview
description: Principled, evidence-based code review of a diff, branch, or PR. Runs parallel perspective passes, validates every candidate finding before reporting, and filters aggressively for precision over volume. Use when the user asks to review code, a diff, a branch, or a pull request with this skill.
---

# Code Review

Review code the way the evidence says reviews actually create value: few findings,
high confidence, correctly labeled severity, delivered fast. Precision is the binding
constraint — unfiltered LLM review comments achieve ~7-10% acceptance in real
deployments; validated, filtered ones reach ~75%. Every rule below exists to protect
precision. Supporting research and citations: [EVIDENCE.md](EVIDENCE.md).

## Phase 0 — Scope & Preflight

1. Determine what to review, in order of precedence:
   - Explicit argument (PR number, ref range, file list).
   - Current branch vs the merge-base with the default branch, plus uncommitted changes.
2. Gather author intent: PR title/description or commit messages. Understanding the
   change is the central bottleneck of review — summarize the intent in 1-2 sentences
   before reading any code.
3. Locate applicable project rules: `CLAUDE.md`, `.claude/rules/**`, and any
   `REVIEW.md`, walking the path hierarchy for each touched file. Convention
   violations may only be flagged if you can quote the exact rule violated.
4. **Size check.** Count changed LOC (excluding lockfiles, generated code, vendored
   deps). If > 400 changed LOC, state this up front, note that defect-detection
   reliability degrades beyond this size (for humans and for you), recommend
   splitting, and proceed with explicitly reduced confidence rather than pretending
   one pass is reliable.
5. Bail out early (say so, do nothing else) if: the diff is empty, trivial
   (lockfile-only, generated-only), or the PR is closed/merged.

## Phase 1 — Perspective Passes (parallel)

Assigned perspectives find more unique defects than ad-hoc reading. Launch parallel
subagents (Explore or general-purpose, read-only), each with ONE narrow lens. For a
typical change, run these four; drop lenses that don't apply (e.g. no contract lens
for a docs-only change):

| Lens | Question it answers |
|------|---------------------|
| **Correctness** | Will this code compile/parse and produce right results? Trace data flow on the changed lines; check edge cases that the diff itself makes reachable. |
| **Contract & integration** | Do the changed call sites, APIs, schemas, and types stay consistent with their consumers elsewhere in the repo? This lens MAY read beyond the diff for context. |
| **Convention compliance** | Does the change violate a specific, quotable rule in CLAUDE.md / `.claude/rules/`? Includes requirement-erosion checks (silent fallbacks, skip-with-warning patterns — see the project's escalators-not-stairs rule). |
| **Maintainability** | Will the next reader misunderstand this? Naming that lies, dead code introduced, duplicated logic that already exists in the repo. |

Rules for every pass:
- Read the whole touched file (and neighbors when needed) for context, but **attribute
  findings only to introduced/changed code**. Pre-existing problems go in a separate
  bucket, never blamed on this change.
- Every candidate finding must include: `file:line`, a one-sentence claim, the
  **concrete trigger scenario** (the input or sequence under which it actually fires),
  and evidence (quoted code or quoted rule).
- Passes should be aggressive in generation — the validator, not the generator, is
  where precision lives.

## Phase 2 — Validation (adversarial)

For each candidate finding, attempt to **disprove** it before it may be reported:

1. Re-open the file at the cited lines. Confirm the code says what the finding claims.
2. Confirm the trigger scenario is reachable — a concrete caller, input, or state, not
   "could theoretically."
3. Check it isn't already handled: guards elsewhere, lint-suppression comments,
   prior review threads, intentional design noted in comments/docs.
4. If two independent passes flagged the same issue, that agreement raises confidence;
   a single-pass finding needs stronger direct evidence.

Then gate on **evidence, not self-rated confidence** (LLM verbalized confidence
is miscalibrated and top-clustered — the number is a forcing function, not a
probability). A finding is reportable when it has ALL of:

1. A `file:line` citation to the introduced code.
2. A stated trigger: the concrete input, state, or sequence under which it
   fires (a hypothesized race with a concrete interleaving counts; vague
   "could be a problem" does not).
3. Survival of the disproof attempt above.

The rubric below maps evidence to a score for severity calibration; the
**reporting bar is class-conditional**:

| Score | Evidence state |
|-------|---------------|
| 0 | Disproven, pre-existing, or style preference |
| 25 | Plausible; trigger not confirmed |
| 50 | Real but a nitpick (no blocking failure mode or maintenance cost) |
| 75 | Trigger confirmed; will be hit in practice |
| 100 | Failing path fully traced |

- Maintainability/style classes: report at ≥75 (false positives here cost
  trust cheaply spent).
- **Correctness, security, data-loss, concurrency classes: report at ≥50** —
  the cost asymmetry inverts; a missed defect here is unbounded, a weak
  finding costs seconds. Label sub-75 findings "possible — trigger
  unconfirmed".
- **Never silently drop.** Findings that miss the bar go in a one-line-each
  collapsed appendix ("Below threshold — unverified") so the filter's misses
  stay observable and auditable.

## What NOT to Flag (denylist)

Never report:
- **Pre-existing issues** as if this change introduced them. Genuinely severe
  ones within the diff's blast radius (code the change calls, is called by, or
  shares state with) go in the separate Pre-existing section — relevance-gated,
  not quota-capped.
- **Anything a linter, formatter, or typechecker will catch.** Don't run them to
  verify; don't compete with deterministic tooling.
- **Findings with no statable failure mode or maintenance cost.** (This replaces
  the "senior engineer test" — senior reviewers disagree up to 10× on what to
  flag, so the test is the finding's content, not an imagined reviewer: if you
  can't state what goes wrong or what it costs the next maintainer, drop it.)
- **Findings without a stated triggering condition.** A named trigger ("if two
  requests hit this before the lock…") is a hypothesis and in scope; trigger-free
  hand-waving ("could be slow", "add validation") is not. Note: race conditions
  and error-path failures are *inherently* hypothesis-shaped — judge the
  concreteness of the trigger, not the category.
- **Symbols "missing" outside the hunk** — code defined elsewhere in the codebase, or
  apparent incompleteness at diff-hunk boundaries.
- **Code that looks wrong but is correct** — verify before flagging, not after.
- **Issues explicitly silenced** in code (suppression comments) or already adjudicated
  in prior review threads.
- **Security commentary with no identified data flow.** But security findings
  WITH a traced flow are always in scope — even "generic"-sounding classes like
  input validation and access control, because those are precisely where human
  review misses most (~88% escape rates in case-control studies).
- **Generic "add more tests" commentary.** Two specific carve-outs are in
  scope, line-anchored: (a) a changed/added error-handling path with no test —
  the class behind most catastrophic production failures; (b) a bug-fix PR
  with no regression test for the fixed bug.

## Output

Lead with a verdict line, then findings grouped by severity. Severity is informational,
never blocking — the human decides.

```
## Review: <one-line change summary> (<N> findings: <i> important, <n> nits)

### 🔴 Important — fix before merge
- `path/file.ts:42` — <claim>. <trigger scenario>. <concrete suggested fix>.

### 🔧 Evolvability — uncapped; ~75% of review's measured value lives here
- `path/file.ts:60` — misleading name / structure resisting change / missing rationale.

### 🟡 Nit (style/trivia only)   ← max 5; fold the rest into "plus N similar"
- `path/file.ts:88` — Nit: <claim>.

### 🟣 Pre-existing (in this change's blast radius — relevance-gated, no quota)

### Not checked
<specific to THIS diff: name the single highest-risk dimension not analyzed
("concurrency behavior of the new cache") plus standing exclusions. Vary it
per review — fixed boilerplate trains readers to skip it.>

<details><summary>Below threshold — unverified (N)</summary>
one line each; kept so the filter's misses stay auditable</details>
```

Formatting rules:
- Every finding: `file:line`, the claim, the fix. For convention violations, quote the
  exact rule text.
- Label each finding per-finding, blind to any expected distribution. (Across
  many reviews ~75% of legitimate findings being evolvability is a *post-hoc
  sanity check* — never a per-review quota; quotas pressure misclassification
  exactly on the security-heavy diffs where the mix legitimately differs.)
- The **Not checked** section is mandatory for auditability — but don't expect
  a disclaimer to cure reader over-reliance (instructions don't fix automation
  bias); making it diff-specific and actionable is what gives it value.
- If nothing survives validation, say "No issues found above the confidence threshold"
  and still include Not checked. A clean short review is a successful review.

## Re-review Behavior

On a second pass over the same change (after fixes):
- Verify previously reported Important findings are resolved; say which are.
- **Lines changed since the last round are fresh code**: findings there are
  admissible at any severity — revision N+1 contains code that didn't exist at
  revision N, and review-applied patches themselves induce defects.
- On **untouched** lines: new Important/correctness findings are always
  admissible; new nits are suppressed. Convergence is a social contract about
  style opinions, not a license to stop finding bugs.
