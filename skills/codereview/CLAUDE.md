# codereview — Maintainer Decision Lens

Read the ADR log below before changing anything. Each ADR carries a **Lens** —
apply it to the next decision instead of re-deriving the trade-off.

## Development contract

Docs-only skill (no `scripts/`, so no Makefile `fix`/`ci` loop). Gates before
handoff, run from repo root:

```sh
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_contrast.ts   .claude/skills/codereview/README.md
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts .claude/skills/codereview/README.md
uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 .claude/skills/codereview/README.md
```

All files ≤ 500 lines (`.claude/rules/claude_skills/index.md`).

## File map

| File | Role |
|------|------|
| `SKILL.md` | Agent operating manual: phases, rubric, denylist, output format |
| `README.md` | Human explainer: purpose, quickstart, architecture diagram |
| `EVIDENCE.md` | Research citations behind each rule |
| `CLAUDE.md` | This file — rationale and decision log |

## Architecture principles

- Precision is the binding constraint; every rule exists to protect it.
- Generation is aggressive, validation owns precision (never the reverse).
- Severity is informational, never blocking; the human decides.

## ADR log

### ADR-1: generate-then-verify with a hard ≥80 confidence threshold

- **Status:** Accepted
- **Context:** Deployed LLM reviewers without a validation stage achieve
  ~7-10% comment acceptance (RevMate); with verification stages, ~75%
  precision (BitsAI-CR). Anthropic's own plugin uses an anchored 0-100 rubric
  with an 80 cutoff.
- **Decision:** Separate adversarial validation phase; anchored rubric;
  silent drop below 80.
- **Consequences:** Fewer findings reported than generated — by design;
  borderline-real issues are sacrificed to protect trust.
- **Lens:** Never trade threshold for coverage; if a category keeps producing
  sub-80 findings, exclude the category rather than lowering the bar.

### ADR-2: aggressive perspective passes, conservative reporting

- **Status:** Accepted
- **Context:** Cursor's Bugbot finding: agentic reviewers with a downstream
  validator perform better with aggressive generation prompts; perspective-
  based reading yields more unique defects than ad-hoc reading.
- **Decision:** Four parallel single-lens passes told to over-generate;
  the validator, not the generators, owns precision.
- **Consequences:** Higher token cost per review; better recall without
  precision loss.
- **Lens:** Tune recall in the passes, precision in the validator — never
  make a pass "more careful" to reduce noise; that's the validator's job.

### ADR-3: mandatory "Not checked" section

- **Status:** Accepted
- **Context:** Controlled experiment (arXiv:2411.11401): reviewers anchor on
  what the AI flagged and overlook everything else — silence reads as
  clearance.
- **Decision:** Every review output, including clean ones, ends with an
  explicit list of what was not covered.
- **Consequences:** Slightly longer output; calibrated human trust.
- **Lens:** Output-format changes must preserve an explicit blind-spot
  disclosure; "looks clean" without scope disclosure is a regression.

### ADR-4: evidence lives in EVIDENCE.md at skill root

- **Status:** Accepted
- **Context:** Citations justify rules but aren't operational; this skill
  predates the sibling skills' `resources/` convention and links to
  EVIDENCE.md are already in place.
- **Decision:** Keep EVIDENCE.md at the root; new lazy-loaded material would
  go in `resources/`.
- **Consequences:** Minor layout inconsistency with sibling skills, no
  functional difference.
- **Lens:** Don't churn file layout for symmetry alone; move EVIDENCE.md only
  when a real change touches it anyway.

### ADR-5: round-2 red-team amendments — evidence gates, no silent drops, class-conditional bars

- **Status:** Accepted (2026-06; amends ADR-1's mechanics, keeps its goal)
- **Context:** A dedicated disconfirmation research pass (see EVIDENCE.md
  "Counter-evidence") showed: LLM self-rated confidence is uncalibrated;
  silent drops are unauditable; the nit cap was capping review's main
  measured product (evolvability); the security denylist matched human
  reviewers' worst blind spots; "senior engineer test" referents disagree 10×.
- **Decision:** Reporting gates on evidence artifacts (citation + stated
  trigger + surviving disproof), class-conditional bars (≥50 for
  correctness/security/data-loss/concurrency, ≥75 for style), a collapsed
  below-threshold appendix instead of silent drops, an uncapped Evolvability
  section, data-flow-gated security scope, error-path/regression-test
  carve-outs, and convergence scoped to untouched lines.
- **Consequences:** Slightly noisier reviews on security-touching diffs — by
  design; the precision-first stance now bends where the FN cost is unbounded.
- **Lens:** Precision rules are class-conditional: tune strictness by the
  cost of a missed finding in that class, never globally. And any filter must
  leave an audit trail of what it removed.

## Extension checklist

- [ ] New finding categories come with a denylist review — does the category
      have a structurally high FP rate? If so, exclude it (ADR-1).
- [ ] Prompt changes route per ADR-2: recall → passes, precision → validator.
- [ ] Output changes keep severity-informational semantics and Not-checked
      (ADR-3).
- [ ] Both mermaid gates + mdtoc re-run if README touched; all files ≤ 500 lines.

## Known gotchas

- The 400-LOC size check must exclude lockfiles/generated content or every
  dependency bump triggers the reduced-confidence warning.
- Convention findings require quoting the exact rule text — a paraphrased
  rule fails validation and gets dropped, which surprises authors of new
  rules files.
- On re-review, previously-reported-but-unfixed Important findings are
  re-confirmed, not re-discovered — don't double-report them as new.
