---
name: prwalkthrough
description: "Walk a human through any PR or diff, regardless of size. Distills 100s-1000s of changed files into their deeper structure: 2-3 distinct mechanical change patterns (each verified for hidden deviants) plus the handful of genuinely novel changes, then narrates them intent-first and optionally runs a coach-style comprehension loop. Use when the user says 'walk me through this PR', 'explain this diff/PR', 'what actually changed here', or faces a huge PR they can't review file-by-file. Skip when the user wants a verdict on code quality — that's /codereview."
argument-hint: "[PR number | ref range | branch] (default: current branch vs merge-base)"
user-invocable: true
---

# PR Walkthrough

Convert a diff of any size into its **deeper structure**: the few distinct change
patterns that actually happened, not the surface list of files. A 500-file PR is
unreviewable file-by-file by construction (defect detection collapses past ~400
LOC per sitting); clustering converts it back under the human attention budget.
The cardinal sin is declaring a cluster "mechanical" without verifying every
member — the needle in the codemod is the whole risk.

## Phase 0 — Scope & intent

1. Resolve the diff: explicit PR number (`gh pr view/diff`), ref range, or
   current branch vs `git merge-base origin/<default> HEAD` plus uncommitted.
2. Mine intent BEFORE reading code: PR description, commit messages, linked
   issues. Understanding the *reason* for a change is the reviewer's top unmet
   need — open the walkthrough with one paragraph of intent.
3. Headline numbers: `git diff --shortstat`, `--dirstat=files,0`, file count.

## Phase 1 — Structural distillation (clustering)

Run the git-only clustering algorithm in
[resources/clustering.md](resources/clustering.md) — read it now. It yields
three sets:

| Set | Contents | Walkthrough treatment |
|-----|----------|----------------------|
| **Noise** | lockfiles, generated, vendored (verified via `linguist-generated` + path heuristics + sampled) | One bullet: "N generated/lock files; not hand-reviewed." |
| **Mechanical clusters** | groups of files sharing one normalized change shape, each with a template, count, exemplar hunk, and **deviant list** | One bullet per cluster + exemplar + deviants promoted out. |
| **Novel set** | residual files + all ejected deviants, ranked by churn × centrality | Full guided tour. |

Hard rules:
- **Verify cluster homogeneity mechanically, never by sampling.** Every member's
  hunks must reduce to instantiations of the cluster template
  (token-normalized comparison); anything left over is ejected to the novel set.
- Run diffs with `-M -C` so renames don't masquerade as churn; similarity <100%
  means "moved AND edited" — review only the edit.
- Commit boundaries seed clusters but are never trusted (11-40% of commits are
  tangled); content hashing decides.
- Label every cluster as **machine-verified** or **sampled** in the output — the
  human must know which guarantees they're getting.
- For large diffs, fan this work out to parallel Explore/general-purpose
  subagents (one per candidate cluster for verification; one for the novel set).

## Phase 2 — The narrative (pyramid order)

Present a one-screen map first, then progressively disclose. Order: intent →
architecture delta → novel changes → mechanical clusters → noise. Spend the
human's scarce attention on the novel core, not on file 412 of the rename sweep.

```
## Walkthrough: <intent, one sentence>

**Shape:** N files / +A −D · K mechanical patterns + M novel changes + noise

### The deeper structure
1. 🔁 <pattern template, human-phrased>            — 412 files [machine-verified]
2. 🔁 <pattern 2>                                  — 87 files  [machine-verified]
3. ✨ <novel change 1: what & why>                 — 3 files
4. ✨ <novel change 2>                             — 2 files
5. ⚠️ Deviants: <files that broke their cluster's pattern — review these>
6. 🗑 Noise: N lockfile/generated updates

**Next?** (a) tour the novel core · (b) inspect a pattern + its deviants ·
(c) quiz my understanding · (d) just the full narrative · (e) stop
```

Narrative rules:
- **Exemplar + count, never the full list.** Each mechanical cluster: template
  ("`getFoo(ctx)` → `getFoo(ctx, opts)`"), count, ONE rendered exemplar hunk,
  plus the *most dissimilar* in-cluster member if shapes varied.
- **Novel core as a guided tour**: ordered (file, line-range, narration) steps
  following the dependency/execution path — data model → core logic → call
  sites → tests. Reference locations as `file:line`.
- Cohorts ordered by dependency, never alphabetically.
- If a novel change alters a flow (API chain, event flow), render a small
  Mermaid sequence diagram (≤15 nodes, palette per the mermaidjs_diagrams skill).
- Always surface deviants prominently — they are the most review-worthy lines
  in the entire PR.

## Phase 3 — Interactive loop (coach-style)

If the user picks (a)/(b): present that section, then re-offer the menu.
If the user picks (c), run the comprehension loop (same contract as the `coach`
skill):

1. **One question per turn**, most diagnostic first — anchored on the novel
   core and deviants, never on mechanical trivia. Good shapes: "what happens to
   callers that passed `null` here?", "which cluster would break if X?",
   "why did this file need to deviate from pattern 1?"
2. Ask question type preference once: `(m) multiple choice · (o) open-ended ·
   (b) my pick`. MCQ distractors encode specific plausible misreadings of the
   diff.
3. Evaluate, then give adaptive feedback: wrong-and-confident gets the
   contrast-with-reality explanation and a pointer to the exact hunk; correct
   gets brief confirmation and the next question.
4. The user controls pace; "stop"/"done" exits to a two-line close that names
   anything still unexplored (sections not toured, clusters only sampled).

## Cross-cutting rules

- Never assert "these N files all got the same change" without the Phase 1
  verification — that sentence is a security claim.
- Optimize for *correct understanding*, not minimal reading time: the measured
  benefit of decomposition is fewer false conclusions, not speed.
- State what the walkthrough did NOT examine (noise set, unsampled context) so
  silence isn't read as clearance.
- Most turns ≤ one screen; depth on request.

Evidence and sources behind these rules: [resources/evidence.md](resources/evidence.md).
