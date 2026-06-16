# Evidence Base for the codereview Skill

## Counter-evidence (red-team round, incorporated 2026-06)

A dedicated disconfirmation pass found these; each drove an amendment:

- **LLM verbalized confidence is near-meaningless**: overconfident,
  top-clustered, AUROC ~0.52-0.61 for separating right from wrong
  ([Xiong et al., ICLR 2024](https://arxiv.org/abs/2306.13063)). → The gate
  is evidence artifacts (citation + stated trigger + surviving disproof);
  the score is a forcing function, not a probability.
- **Silent dropping is unauditable and the FN cost asymmetry inverts for
  security** (industry SAST practitioners: "the false negative will kill
  you", [arXiv:2307.16325](https://arxiv.org/html/2307.16325v3)). → Collapsed
  below-threshold appendix; class-conditional reporting bar (≥50 for
  correctness/security/data-loss/concurrency).
- **The maintainability class IS review's measured product** — ~75% of
  findings, twice replicated ([Mäntylä & Lassenius TSE 2009](https://dl.acm.org/doi/10.1109/TSE.2008.71);
  [Beller et al. MSR 2014](http://sback.it/publications/msr2014.pdf)). →
  Uncapped Evolvability section; nit cap applies to style/trivia only.
- **"What a senior would flag" is unfalsifiable**: 10× reviewer variability
  ([Hatton](https://www.leshatton.org/Documents/checklists_in_inspections.pdf));
  in Chromium, reviewer experience correlated with HIGHER security-miss rates
  ([arXiv:2102.06909](https://ar5iv.labs.arxiv.org/html/2102.06909)). →
  Replaced with "statable failure mode or maintenance cost".
- **The denylisted security categories are where humans miss most**: ~88%
  of improper-input-validation and access-control defects escaped review in
  the same Chromium study. → Denylist narrowed to "no identified data flow".
- **Untested error handling causes most catastrophic failures**: 92% of
  catastrophic failures from bad non-fatal-error handling; 58% trivially
  exposable by simple tests ([Yuan et al., OSDI 2014](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-yuan.pdf)).
  → Error-path-test and regression-test carve-outs.
- **Disclaimers don't cure automation bias** ([Parasuraman & Manzey 2010](https://journals.sagepub.com/doi/10.1177/0018720810376055):
  not preventable "by training or instructions"). → Not-checked kept for
  auditability, made diff-specific; the bias-counter claim retired.
- **Re-review suppression has no supporting evidence**, and revision N+1
  contains new code by construction. → Convergence scoped to untouched
  lines, style nits only.

Why each rule in [SKILL.md](SKILL.md) exists. Two source streams: empirical software
engineering research (human code review, 2006-2018) and deployed LLM-reviewer
studies (2022-2026).

## Review size, speed, and the 400 LOC rule

- **Defect-detection ability collapses beyond ~400 changed LOC.** SmartBear/Cisco
  study (Cohen et al., 2006; 2,500 reviews, 3.2M LOC): defect density found is
  highest under ~200 LOC and falls sharply past 400. Review speed above ~450 LOC/hour
  found below-average defect density in 87% of cases. Detection effectiveness also
  drops after ~60 minutes of sustained inspection.
  [Cisco case study](https://static0.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf) ·
  [11 Best Practices](https://static1.smartbear.co/support/media/resources/cc/11_best_practices_for_peer_code_review_redirected.pdf)
- **Small changes are the norm at scale.** Google: "100 lines is usually a reasonable
  size for a CL, and 1000 lines is usually too large."
  [Google eng-practices, Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- → SKILL.md Phase 0 size check: flag >400 LOC diffs, recommend splitting, state
  reduced confidence rather than pretending one pass is reliable.

## What reviews actually find (severity calibration)

- **~75% of legitimate review findings are maintainability/evolvability, not
  functional defects.** Mäntylä & Lassenius, IEEE TSE 35(3), 2009 (759 defects
  classified). [DOI](https://dl.acm.org/doi/10.1109/TSE.2008.71)
- **Only ~15% of reviewer comments flag a possible defect at all.** Czerwonka,
  Greiler & Tilford, "Code Reviews Do Not Find Bugs," Microsoft, ICSE 2015.
  [PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2015/05/PID3556473.pdf)
- **Realized top benefits are knowledge transfer and shared understanding;
  understanding the change is the central bottleneck.** Bacchelli & Bird, ICSE 2013.
  [ACM](https://dl.acm.org/doi/10.5555/2486788.2486882)
- → SKILL.md labels maintainability findings honestly instead of inflating them, and
  Phase 0 summarizes author intent before reading code.

## Coverage, participation, reviewer count

- **Low review coverage/participation → up to 2 and 5 additional post-release defects
  respectively; reviewer expertise correlates with quality.** McIntosh, Kamei, Adams
  & Hassan, MSR 2014 / EMSE 21(5), 2016 (Qt, VTK, ITK).
  [PDF](https://posl.ait.kyushu-u.ac.jp/~kamei/publications/McIntosh_MSR2014.pdf)
- **Two reviewers is the convergent industry sweet spot; more adds cost, not yield.**
  Rigby & Bird, ESEC/FSE 2013 (Microsoft, Google, AMD, major OSS independently
  converged on ~2 reviewers + small changes + fast iteration).
  [PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/rigby2013convergent.pdf)
- **Latency dominates satisfaction.** Sadowski et al., ICSE-SEIP 2018 (9M changes at
  Google): median review latency < 4h; 70% of changes commit within 24h.
  [PDF](https://sback.it/publications/icse2018seip.pdf)
- → An AI first-pass is most valuable as immediate feedback that frees the (≤2)
  human reviewers for design and domain correctness.

## Reading techniques (why perspective passes)

- **Assigned perspectives find more unique defects than ad-hoc or checklist reading**
  by reducing overlap between readers. Laitenberger & El Emam (60 professional
  developers, Bosch Telecom); Basili et al. PBR lineage. Checklist-vs-ad-hoc
  replications are mixed — the robust effect is role/scenario assignment.
  [arxiv 0909.4260](https://arxiv.org/pdf/0909.4260)
- → SKILL.md Phase 1 runs parallel single-lens passes (correctness, contract,
  convention, maintainability) and dedupes — the one place an AI can do what human
  teams can't afford.

## LLM reviewers: deployed results (why validation + filtering)

- **Unfiltered LLM review comments achieve ~7-10% acceptance.** RevMate at
  Mozilla + Ubisoft (587 reviews, 1.6k comments): 7-8% accepted — though accepted
  ones induced revisions as often as human comments.
  [arxiv 2411.07091](https://arxiv.org/abs/2411.07091)
- **A verification stage before posting is the difference.** ByteDance BitsAI-CR:
  RuleChecker generates → ReviewFilter validates → 75% comment precision at 12k+
  weekly users. [arxiv 2501.15134](https://arxiv.org/abs/2501.15134). Meta gates
  generation behind an actionability classifier (P 0.81 / R 0.92).
  [arxiv 2507.13499](https://arxiv.org/html/2507.13499v1)
- **Aggressive generation + strict validation beats conservative generation.**
  Cursor Bugbot: agentic reviewers perform better with aggressive investigation
  prompts when a downstream validator owns precision; majority voting across
  shuffled passes was a top quality lever.
  [Building Bugbot](https://cursor.com/blog/building-bugbot)
- **AI review can harm via anchoring.** Controlled experiment (29 professionals,
  50+ hours): AI-assisted reviewers found the same median 50% of injected issues,
  saved zero time, and overlooked code the AI didn't highlight.
  [arxiv 2411.11401](https://arxiv.org/abs/2411.11401). An industrial Qodo study
  (4,335 PRs) found 73.8% of bot comments addressed but *longer* PR closure times,
  with irrelevant comments and automation bias cited.
  [arxiv 2412.18531](https://arxiv.org/abs/2412.18531)
- **LLMs misjudge correctness ~1/3 of the time even with the problem description**
  (GPT-4o/Gemini 2.0 Flash: 64-68% accuracy).
  [arxiv 2505.20206](https://arxiv.org/abs/2505.20206)
- → SKILL.md's adversarial Phase 2, the ≥80 confidence threshold, the denylist, and
  the mandatory **Not checked** section (anchoring countermeasure) all derive from
  these results.

## Practitioner patterns adopted

- **Anchored 0-100 confidence rubric, report ≥80 only; explicit do-not-flag list;
  diff-scoped blame with whole-file context; separate Pre-existing severity;
  generate-then-verify subagents** — Anthropic's code-review plugin and hosted
  Code Review.
  [code-review.md](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md) ·
  [docs](https://code.claude.com/docs/en/code-review)
- **Trigger-scenario requirement; never flag symbols defined outside the hunk.**
  Qodo PR-Agent reviewer prompts.
  [prompts.toml](https://github.com/qodo-ai/pr-agent/blob/main/pr_agent/settings/pr_reviewer_prompts.toml)
- **Severity prefixes ("Nit:") and non-blocking decorations.**
  [Google eng-practices](https://google.github.io/eng-practices/review/reviewer/comments.html) ·
  [conventionalcomments.org](https://conventionalcomments.org/)
- **Category-level exclusion of structurally-high-FP classes** (generic DoS,
  rate-limiting, input-validation commentary).
  [claude-code-security-review](https://github.com/anthropics/claude-code-security-review)
- **Noise reduction is ultimately a feedback-learning problem.** Greptile: prompt
  engineering alone failed; embedding-similarity blocking of previously-downvoted
  comments took addressed-rate from 19% → 55%+. Cursor's north-star is resolution
  rate (~80%). For a local skill the analog is honoring suppressions and prior
  review threads as already-adjudicated.
  [Greptile case study](https://www.zenml.io/llmops-database/improving-ai-code-review-bot-comment-quality-through-vector-embeddings)
