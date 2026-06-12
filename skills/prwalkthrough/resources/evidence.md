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

## Why a Socratic comprehension loop

- Socratic guided self-explanation outperforms free self-explanation for
  source-code comprehension specifically
  ([comparative study](https://www.researchgate.net/publication/349845034_A_Comparative_Study_of_Free_Self-Explanations_and_Socratic_Tutoring_Explanations_for_Source_Code_Comprehension);
  see also [arXiv:2310.03210](https://arxiv.org/pdf/2310.03210)). The loop
  contract (one question per turn, distractors as named misconceptions,
  learner controls pace) is shared with the local `coach` skill.
