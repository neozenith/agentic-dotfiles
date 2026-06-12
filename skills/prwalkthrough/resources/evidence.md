# Evidence Base for the prwalkthrough Skill

Why each rule in [../SKILL.md](../SKILL.md) exists.

## Why cluster at all

- **Review-size economics:** SmartBear/Cisco (2,500 reviews, 3.2M LOC): defect
  detection density is highest under ~200 changed LOC and collapses past ~400;
  >500 LOC/hour misses most defects. A 500-file PR is unreviewable
  file-by-file by construction.
  [Cisco case study](https://static1.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf)
- **Industrial validation:** Google reviews large-scale changes at the
  *pattern* level — Rosie shards LSCs, global approvers "use pattern-based
  tooling to review each of the changes," manually inspecting only anomalies.
  [SWE at Google ch. 22](https://abseil.io/resources/swe-book/html/ch22.html) ·
  [Chrome LSC process](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/process/lsc/large_scale_changes.md)
- **Systematic edits are template-instantiated**, which is why normalized
  hashing works: LASE learns a generalized edit script from ≥2 examples and
  locates targets with 99% precision
  ([Meng et al., ICSE 2013](https://web.cs.ucla.edu/~miryung/Publications/icse2013-lase-submitted.pdf));
  RefactoringMiner detects 60+ refactoring types at 99.6% precision from diffs
  alone ([Tsantalis et al.](https://users.encs.concordia.ca/home/n/nikolaos/publications/ICSE_2018.pdf));
  industrial codemod tooling (Refaster, ClangMR,
  [fastmod](https://github.com/facebookincubator/fastmod)) emits exactly this
  shape.

## Why intent-first narrative

- **Understanding is the bottleneck of review**, and the top unmet information
  need is the *rationale* for a change — Bacchelli & Bird, ICSE 2013
  ([PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/ICSE202013-codereview.pdf));
  Tao et al., FSE 2012: dominant questions are "what is the rationale?" and
  "is this change complete/consistent?"
  ([PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/07/howdosoftwareengineersunderstandcodechanges_fse2012.pdf))
- **Cohorts ordered by dependency** and collapsed file-group tables are the
  deployed pattern in CodeRabbit walkthroughs
  ([docs](https://docs.coderabbit.ai/pr-reviews/walkthroughs)); guided
  file-by-file tours are the CodeTour model
  ([microsoft/codetour](https://github.com/microsoft/codetour)).

## Why decomposition helps (and what it actually buys)

- **ClusterChanges** (Barnett et al., ICSE 2015): ~42% of 1,000 real changesets
  contained multiple independent non-trivial partitions; 16/20 developers
  judged the decomposition correct and helpful
  ([summary](https://blog.acolyer.org/2015/06/26/helping-developers-help-themselves-automatic-decomposition-of-code-review-changes/)).
- **Controlled experiment** (di Biase et al., PeerJ CS 2019): decomposed
  changes produced significantly **fewer false-positive review comments**
  (p=0.03) — not faster review. Hence: optimize for correct understanding,
  not reading speed. ([PeerJ](https://peerj.com/articles/cs-193/))
- **Tangled commits are common** (11-40% of commits; Herzig & Zeller
  [EMSE 2016](https://link.springer.com/article/10.1007/s10664-015-9376-6)) —
  why commit boundaries seed but never decide clusters.

## Why mechanical verification of every cluster member

- The deviant-hidden-in-a-cluster is both a correctness and a security risk:
  malicious changes hide in bulk diffs. Google's pattern tooling auto-approves
  only changes that "meet expectations"; anomalies get manual review (SWE at
  Google ch. 22). The re-apply-and-diff oracle mirrors Meta's
  codemod-with-oversight workflow.
- `git patch-id` is purpose-built for "same change?" comparison
  ([docs](https://git-scm.com/docs/git-patch-id)); `linguist-generated` is how
  GitHub itself collapses generated files
  ([docs](https://docs.github.com/en/repositories/working-with-files/managing-files/customizing-how-changed-files-appear-on-github)).

## Counter-evidence (red-team round, incorporated 2026-06)

These findings drove the round-2 amendments; they bound what the skill may claim.

- **The decomposition null result:** di Biase et al. (PeerJ CS 2019, n=28) —
  decomposition improved neither rationale-understanding nor defects found
  nor time; only fewer false-positive comments. No replication either way.
  Hence the honest value claim: fewer false conclusions, nothing more.
  ([PeerJ](https://peerj.com/articles/cs-193/))
- **Token-set verification is order-blind:** clone-detection literature shows
  identifier normalization is a precision killer; bag comparison passes
  argument swaps. Hence ordered-sequence + bijection mapping, and the
  `shape-checked` label with stated scope.
  ([SourcererCC](https://arxiv.org/pdf/1512.06448))
- **Automation labels cause omission errors:** overtrust in automated aids →
  complacency and unmonitored misses (Parasuraman & Riley 1997; Parasuraman
  & Manzey 2010). Hence "shape-checked" states what it cannot catch, every
  time. ([P&M 2010](https://journals.sagepub.com/doi/10.1177/0018720810376055))
- **Fluent narration inflates trust regardless of accuracy:** placebic
  explanations produce trust similar to real ones (Eiband et al., CHI 2019);
  the sense of understanding is an overconfidence artifact (Trout 2002);
  simple-story framings distort memory toward the story (Lombrozo 2007).
  Hence austere, file:line-cited narration and prominent uncertainty.
  ([CHI 2019](https://dl.acm.org/doi/fullHtml/10.1145/3290607.3312787))
- **Stated intent is unreliable:** ~44% of commit messages lack what/why
  (Tian et al., ICSE 2022); ~60% of refactoring commit messages are
  inconsistent with the actual change. Hence intent as a claim diffed
  against code, never the frame.
  ([arXiv:2202.02974](https://arxiv.org/abs/2202.02974))
- **Presentation order causally redirects detection:** defects in
  later-positioned files are found less (Fregnan et al., EMSE 2022,
  n=106 experiment + 219k PRs). The tour reallocates a fixed attention
  budget — hence the mandatory "Not shown" disclosure and waved-through LOC
  totals. ([arXiv:2208.04259](https://arxiv.org/abs/2208.04259))
- **Folded content is missed:** NN/g accordion guidance (qualitative) —
  hence deviants and security-sensitive paths are expansion-exempt.
  ([NN/g](https://www.nngroup.com/articles/accordions-on-desktop/))
