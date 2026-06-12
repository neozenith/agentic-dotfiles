# Evidence Base for the refactor Skill

Why each rule in [../SKILL.md](../SKILL.md) exists.

## Hotspots beat smell checklists

- **Individual code smells do NOT predict maintenance effort** once file size
  and churn are controlled: Sjøberg et al., TSE 2012 — six professional
  developers, 3-4 weeks of real maintenance; none of 12 smells remained
  significant. ([PDF](https://www.mn.uio.no/ifi/personer/vit/dagsj/sjoberg_etal_code-smells.pdf))
- **But antipattern participation does** predict change- and fault-proneness
  beyond size (god-class-style hubs): Khomh, Di Penta, Guéhéneuc & Antoniol,
  EMSE 2012, 54 releases of ArgoUML/Eclipse/Mylyn/Rhino.
  ([Springer](https://link.springer.com/article/10.1007/s10664-011-9171-y))
- **Low-quality code in hot paths is economically large**: Tornhill & Borg,
  "Code Red" (TechDebt 2022, 39 codebases): 15x more defects, 124% longer
  resolution times. ([arXiv:2203.04374](https://arxiv.org/abs/2203.04374))
  Hotspot = churn × complexity is the CodeScene method
  ([docs](https://docs.enterprise.codescene.io/versions/4.5.0/usage/index.html)).

## Macro refactoring pays; cycles are the expensive debt

- **The Microsoft field study**: dedicated refactoring of Windows 7 modules
  produced significant reductions in inter-module dependencies and
  post-release defects; 77% of surveyed engineers perceived regression risk.
  Kim, Zimmermann & Nagappan, FSE 2012.
  ([MSR page](https://www.microsoft.com/en-us/research/publication/a-field-study-of-refactoring-challenges-and-benefits/))
- **Architectural debt concentrates defects**: most error-prone files are
  architecturally connected (Xiao/Cai et al., ICSE 2016,
  [ACM](https://dl.acm.org/doi/abs/10.1145/2884781.2884822)); in Chromium 68%
  of vulnerability-associated files are cyclically coupled vs 43% baseline;
  practitioners rank cycles first by refactoring cost
  ([arXiv:2203.08702](https://arxiv.org/pdf/2203.08702)).
- **Deep modules** as the macro target; complexity = dependencies + obscurity:
  Ousterhout, *A Philosophy of Software Design*.

## Discipline: two hats, small steps, safety nets

- **Two hats / structure-vs-behavior separation**: Fowler
  ([Workflows of Refactoring](https://martinfowler.com/articles/workflowsOfRefactoring/fallback.html));
  Kent Beck, *Tidy First?* — separate commits/PRs because reviewers cannot
  verify behavior preservation when interleaved; tidying as buying an option.
- **Seams + characterization tests**: Feathers, *Working Effectively with
  Legacy Code* — pin current behavior (including bugs) before structural change.
- **Refactoring introduces bugs at known rates**: inheritance-hierarchy
  refactorings induced bugs in ~40% of cases; Move Field/Method induce fixes
  in the target class (69%/60%); renames are near-safe. Bavota et al.,
  SCAM 2012 ([PDF](https://people.lu.usi.ch/bavotg/papers/scam2012.pdf));
  replication [arXiv:2009.11685](https://arxiv.org/pdf/2009.11685);
  refactoring-heavy phases precede bug spikes (Weißgerber & Diehl, MSR 2006,
  [PDF](https://www.st.uni-trier.de/diehl/pubs/msr06.pdf)).
- **Incremental beats big-bang**: Fowler,
  [Strangler Fig](https://martinfowler.com/bliki/StranglerFigApplication.html) ·
  [Branch By Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html).

## ADRs as the lens of values

- Nygard's original framing: without recorded rationale a newcomer can only
  "blindly accept or blindly change" a past decision —
  [adr.github.io](https://adr.github.io/). Refactoring against an Accepted ADR
  is an architecture change requiring a superseding ADR.
- **Fitness functions** turn decisions into executable CI constraints —
  Ford/Parsons/Kua, *Building Evolutionary Architectures*
  ([ch. 4](https://www.oreilly.com/library/view/building-evolutionary-architectures/9781492097532/ch04.html)).

## LLM-agent-specific evidence

- LLMs produce unsafe refactorings at measurable rates: ChatGPT 7.4%,
  Gemini 6.6% (behavior changes / syntax errors) —
  [arXiv:2411.04444](https://arxiv.org/abs/2411.04444); raw extract-method
  suggestions up to 76% incorrect before IDE validation
  ([arXiv:2510.03914](https://arxiv.org/html/2510.03914v1)). Mitigation:
  deterministic tooling for mechanical transforms + tests after every step.
- **Agents default to micro-edits**: across 15,451 agent refactorings, the top
  operations were variable-type changes and renames; high-level design changes
  were rare — [arXiv:2511.04824](https://arxiv.org/pdf/2511.04824). The skill's
  Phase 1 ranking exists to force the macro framing.
