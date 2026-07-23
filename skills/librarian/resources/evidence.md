# Evidence — research base for the librarian's doctrine

**Research date: 2026-07-23.** Three parallel research passes: OSS docs
organisation, human+agent docs conventions, and docs-layout manifest
precedents. Re-check the fastest-rotting claims (harness support matrix,
AGENTS.md adoption counts) before they become load-bearing for a new decision.

## Canonical files and locations

- GitHub resolves community health files with precedence **`.github/` > root
  > `docs/`**, first match wins; recognised set includes README, CONTRIBUTING,
  CODE_OF_CONDUCT, SECURITY, SUPPORT, GOVERNANCE.
  <https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file>
- LICENSE detection requires root; CITATION.cff root; FUNDING.yml and
  issue/PR templates are `.github/`-only.
- CHANGELOG format standard: Keep a Changelog. <https://keepachangelog.com/>
- UPPERCASE root meta-file convention history:
  <https://robertmelton.com/posts/the_case_of_the_uppercase_filename/>

## docs/ organisation

- Diátaxis (tutorials / how-to / reference / explanation) is the dominant
  taxonomy. <https://diataxis.fr/> — canonical implementation: Django
  (`intro/ topics/ howto/ ref/` + `internals/` for contributor docs)
  <https://docs.djangoproject.com/en/5.1/internals/contributing/writing-documentation/>
- Kubernetes splits user docs / contributor docs / proposals into three repos
  — the reference architecture for audience separation.
  <https://github.com/kubernetes/website/>
- Misplacement signals: overgrown README (<https://www.makeareadme.com/>),
  decisions in wikis
  (<https://www.martinfowler.com/bliki/ArchitectureDecisionRecord.html>),
  quadrant bleed (<https://diataxis.fr/>), docs outside the repo
  (<https://dev.to/nicoespeon/where-should-you-put-the-documentation-18gg>).

## ADRs and proposals

- Nygard ADRs: file-per-decision, immutable, supersede with cross-links.
  <https://www.martinfowler.com/bliki/ArchitectureDecisionRecord.html>
- adr-tools layout `doc/adr/NNNN-title.md` + the `.adr-dir` pointer file
  (searched upward, honoured by independent reimplementations) — the cleanest
  existing "declare your dialect" microformat.
  <https://github.com/npryce/adr-tools>
- MADR prescribes `docs/decisions/NNNN-title-with-dashes.md`.
  <https://adr.github.io/madr/> — tooling catalog <https://adr.github.io/adr-tooling/>;
  log4brains (`.log4brains.yml` = folder + template in one config)
  <https://github.com/thomvaill/log4brains>
- RFC precedents: rust-lang/rfcs (`text/0000-*.md`, number = PR number)
  <https://github.com/rust-lang/rfcs>; Kubernetes KEPs
  (directory-per-proposal + metadata sidecar)
  <https://github.com/kubernetes/enhancements/tree/master/keps>.
- RFC = pre-decision (mutable in review); ADR = post-decision (immutable).

## Agent files

- AGENTS.md: open format, 60k+ repos, Linux Foundation stewardship since
  Dec 2025. <https://agents.md/> — nesting = closest-file-wins; harness
  matrix as of mid-2026:
  <https://www.iuriio.com/blog/posts/2026/05/agents-md-field-guide-2026>
- **Claude Code does not read AGENTS.md natively** (as of v2.1.x, 2026-07) —
  bridge via symlink or a CLAUDE.md whose first line is `@AGENTS.md`.
  <https://github.com/anthropics/claude-code/issues/34235>
- Size/pointer discipline: ~200-line target; Vercel eval — an always-on docs
  *index* beat both no-docs and skills-only, and stayed at 100% pass after
  5× compression; effective files enumerate concrete commands and explicit
  boundaries. <https://www.morphllm.com/agents-md-guide>,
  <https://www.augmentcode.com/blog/how-to-write-good-agents-dot-md-files>
- "Each fact lives in exactly one document"; L0 dispatcher → L1 reference →
  L2 specs → L3 code hierarchy.
  <https://blog.sigplan.org/2026/04/21/repositories-are-human-agent-knowledge-factories/>
- ADRs as agent context: agents self-answer "why" instead of re-litigating;
  agent file carries the operative constraint, ADR carries the rationale.
  <https://mnemehq.com/insights/how-ai-coding-agents-use-adrs/>

## Docs-conventions manifests

- **No standard docs-conventions file exists.** The role is filled piecemeal:
  `docs/README.md` indexes (unstandardised), GitLab's meta-documentation
  directory (docs-about-docs, CI-linted)
  <https://docs.gitlab.com/development/documentation/styleguide/>,
  site-generator navs as implicit machine manifests
  (<https://www.mkdocs.org/user-guide/writing-your-docs/>,
  <https://docusaurus.io/docs/sidebar>), Backstage's `techdocs-ref`
  annotation <https://backstage.io/docs/features/software-catalog/well-known-annotations/>.
- Presence linting precedents: GitHub community profile
  <https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories>,
  repolinter rulesets (archived)
  <https://github.com/todogroup/repolinter/blob/main/docs/rules.md>,
  OpenSSF Scorecard <https://github.com/ossf/scorecard/blob/main/docs/checks.md>,
  ls-lint naming contracts <https://ls-lint.org/>.
- Synthesis adopted by this skill: `docs/CONVENTIONS.md` = human-readable
  dialect declaration + layout map + greppable pointers, referenced from the
  root agent file ([conventions_template.md](conventions_template.md)).

## Counter-evidence and bounded claims

- **`docs/CONVENTIONS.md` is a convention this skill defines, not an adopted
  ecosystem standard.** No filename has won in the wild; the strongest claim
  is "composes three proven precedents", not "industry practice".
- **llms.txt is weak for repos**: website-scoped, no major provider commits
  to reading it, no measured citation benefit
  (<https://seeklab.io/blog/what-is-llmstxt-the-honest-2026-guide/>). The
  skill deliberately does not require it.
- **repolinter is archived** — presence-linting demand is real but tooling is
  under-maintained; the librarian's audit fills that role as prompts, not as
  a dependency on dead tooling.
- **Diátaxis purity is disclaimed by its own author** — folder taxonomy is a
  default, not a law; small projects legitimately stay single-README. The
  baseline encodes both escapes.
- Harness support claims (which tool reads which file) rotted fastest in this
  research and will again; verify before citing.
