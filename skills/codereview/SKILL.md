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

Then score confidence on this anchored rubric and **silently drop everything below 80**:

| Score | Meaning |
|-------|---------|
| 0 | False positive, pre-existing, or style preference |
| 25 | Plausible but unverified; depends on context you didn't confirm |
| 50 | Real but a nitpick a senior engineer wouldn't block on |
| 75 | Verified real; will be hit in practice |
| 100 | Evidence directly confirms the defect (traced the failing path) |

If you are not certain an issue is real, do not flag it. False positives erode trust
and waste more time than they save.

## What NOT to Flag (denylist)

Never report:
- **Pre-existing issues** as if this change introduced them (genuinely severe ones go
  in the separate Pre-existing section, max 2).
- **Anything a linter, formatter, or typechecker will catch.** Don't run them to
  verify; don't compete with deterministic tooling.
- **Pedantic nitpicks a senior engineer would not flag** — the senior-engineer test.
- **Speculative problems** with no realistic trigger path ("could be slow if...",
  generic "add input validation", hypothetical DoS/rate-limiting concerns).
- **Symbols "missing" outside the hunk** — code defined elsewhere in the codebase, or
  apparent incompleteness at diff-hunk boundaries.
- **Code that looks wrong but is correct** — verify before flagging, not after.
- **Issues explicitly silenced** in code (suppression comments) or already adjudicated
  in prior review threads.
- **Generic test-coverage or security commentary** not tied to a specific defect in
  the changed code.

## Output

Lead with a verdict line, then findings grouped by severity. Severity is informational,
never blocking — the human decides.

```
## Review: <one-line change summary> (<N> findings: <i> important, <n> nits)

### 🔴 Important — fix before merge
- `path/file.ts:42` — <claim>. <trigger scenario>. <concrete suggested fix>.

### 🟡 Nit (non-blocking)        ← max 5; fold the rest into "plus N similar"
- `path/file.ts:88` — Nit: <claim>.

### 🟣 Pre-existing (not this change's fault)   ← max 2, only if genuinely severe

### Not checked
<one line listing what this review did NOT cover — e.g. runtime behavior,
cross-service contracts, performance under load — so silence isn't read as clearance.>
```

Formatting rules:
- Every finding: `file:line`, the claim, the fix. For convention violations, quote the
  exact rule text.
- Label maintainability findings as such — expect ~75% of legitimate findings to be
  maintainability, not functional defects; don't inflate them to Important to seem
  thorough.
- The **Not checked** section is mandatory. Readers anchor on what the review flags
  and stop looking elsewhere; state your blind spots explicitly.
- If nothing survives validation, say "No issues found above the confidence threshold"
  and still include Not checked. A clean short review is a successful review.

## Re-review Behavior

On a second pass over the same change (after fixes):
- Verify previously reported Important findings are resolved; say which are.
- Report only **new Important** findings. No new nits after round one — reviews must
  converge, not discover fresh style opinions on every push.
