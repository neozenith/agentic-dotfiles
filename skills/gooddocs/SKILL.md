---
name: gooddocs
description: "Documentation quality skill with three modes: (1) AUDIT — fan out parallel subagents to corroborate that docs still reflect the reality of the code (commands run, paths exist, signatures match, claims hold) and produce a drift report; (2) WRITE/IMPROVE — author or rewrite docs using the researched lens taxonomy (Diátaxis + distilled style principles from great OSS docs), optionally in the maintainer's personal voice; (3) RESTRUCTURE — reorganize an existing doc, spec, or plan file for structural readability (heading hierarchy, list/table discipline, whitespace rhythm, BLUF) without changing its claims. Use when the user asks to check/audit docs, fix stale docs, write or improve documentation, restructure a doc/spec/plan for readability, or says 'gooddocs'. Add 'voice' to the invocation to write in the maintainer's voice; default is the neutral researched style."
argument-hint: "[audit | write <target> | restructure <target>] [voice] [paths] (default: audit all docs)"
user-invocable: true
---

# Good Docs

Three jobs: keep docs **true** (audit), make docs **great** (write), make
docs **navigable** (restructure). Drift detection comes first, style second.

**Premise: code is authoritative; documentation drifts.** Docs are a
lossy projection of the code, and the projection rots as the code moves — so
when a doc and the code disagree, the default is the *doc* is stale (the rare
exception: the doc is a spec/contract the code violates — then flag, don't
"fix"). **Documentation includes in-code documentation** — docstrings and
explanatory comments are docs and drift the same way. This skill is built to
run **repeatedly** (under a loop or a schedule, against the files you are
actively editing) to keep drift low continuously, not just as a one-shot pass.
Every page is classified on two axes: its **ladder rung** (Quickstart / User
guide / Reference — i.e., Beginner / Intermediate / Expert depth) and its
**lens** (tutorial, how-to, reference, explanation). The ladder is the
top-level structure; lenses are the within-rung discipline. Default to one
lens per page, but deliberate fusion with one consistent voice is valid —
purity is a heuristic, not a law (its own author says so).

Resources (read on first use):
- [resources/lenses.md](resources/lenses.md) — lens taxonomy + 15 distilled
  style principles from the OSS docs survey.
- [resources/structure.md](resources/structure.md) — markdown structure rules:
  heading hierarchy, list/table discipline, whitespace rhythm, structure
  smells, spec/plan skeletons.
- [resources/voice.md](resources/voice.md) — the maintainer's voice
  fingerprint. Load ONLY when the user asked for `voice`; otherwise the
  neutral researched style applies.
- [resources/slop_smells.md](resources/slop_smells.md) — the curated AI-slop
  smell catalog (grown by the maintainer over time) + how to capture THE WHY.
  Load during audit and write/restructure.

## Mode selection

- `audit` (default when docs exist and no write target given): corroborate
  docs against reality, report drift.
- `write <target>`: create or rewrite a doc. Always run a mini-audit of any
  claims the doc will carry forward.
- `restructure <target>`: reorganize an existing doc/spec/plan for structural
  readability — claims unchanged.
- `voice` flag: additionally load and apply `resources/voice.md`.

## Audit mode — corroborate docs vs reality

### 1. Inventory & classify

Glob `**/*.md` (skip vendored/generated/node_modules). For each substantial
doc, record: path, apparent rung + lens, age vs the code it describes
(`git log -1 --format=%cs -- <doc>` vs the same for the code dirs it references).
**In-code documentation is in scope too**: module/function docstrings and
explanatory comments are docs — mark each unit as `markdown` or `in-code`. When
invoked on an explicit path set (the loop/schedule case), audit exactly those
files instead of globbing.

### 2. Fan out verification subagents (parallel)

Launch parallel `Explore`/`general-purpose` subagents, one per doc (or per doc
cluster). **Frame each agent adversarially**: its brief is "find evidence this
claim is FALSE" — never "verify this claim" (LLMs sycophantically confirm
plausible claims; a real `file:line` citation can still fail to entail the
claim). Prefer executable checks (run, grep, glob) over reading; claims only
an LLM's judgment can assess get an explicit lower evidence tier:

| Claim type | Check |
|------------|-------|
| Commands / snippets | Do the flags, targets, scripts exist? Run read-only ones (`--help`, `make -n`) where safe; never run mutating commands. |
| File paths & repo layout | Paths exist? Layout diagrams match `ls` reality? |
| API signatures / config keys | Match current source? (grep the symbol) |
| Env vars | Referenced vars actually read in code? Code-read vars documented? |
| Versions / counts / numbers | Match lockfiles, configs, actual counts? |
| Links | Internal links resolve? (External: spot-check only.) |
| Behavioral claims | A `file:line` in current source supports the claim? |

Each agent returns: claim → verdict (`confirmed-by-execution` /
`confirmed-by-reading` (LLM judgment, not proof) / `drifted` / `unverifiable`)
→ evidence (`file:line` or command output) → suggested fix. For `drifted`, also
record **authority** (`code` = doc is stale [default] / `doc` = doc is the
contract the code violates / `ambiguous`) — it gates what is safe to auto-fix.

Beyond drift, each agent also emits two other finding categories:
- **slop** — an AI-slop smell from [resources/slop_smells.md](resources/slop_smells.md)
  (e.g. self-addressed tracking notes, deletable filler, hard-coded value lists
  that duplicate code). Pruning identified slop is the one sanctioned deletion.
- **why-gap** — a critical place where THE WHY (the reasoning/value behind a
  decision) is missing and a future reader would need it. **Flag only, never
  auto-fix**: rationale cannot be invented, only the author knows it. See
  slop_smells.md §"Capture THE WHY".

### 3. Drift report

```
## Docs audit: <N> docs, <C> claims checked, <D> drifted, <U> unverifiable

| Doc | Claim | Reality | Severity | Fix |
|-----|-------|---------|----------|-----|
| README.md:42 | `make dev` boots both servers | target renamed to `make up` | 🔴 broken quickstart | update command |
```

Severity is **claim-type × rung-traffic**, not a fixed ordering: a wrong
command in a Quickstart (high traffic, blind trust) outranks the same error in
a deep reference page; a stale screenshot ranks below a missing prerequisite.
🔴 a reader following the doc fails; 🟡 misleading but survivable;
🟣 unverifiable claim (flag for the author).
Order by severity. Offer: (a) apply fixes, (b) fix 🔴 only, (c) report only.
The default remediation is **fix or flag — never delete**: deleting drifted
content converts low-severity drift into guaranteed knowledge loss (the docs
equivalent of graceful degradation). When applying fixes, fix the *doc* unless
the doc is the contract and the code drifted — if ambiguous, ask which is
authoritative.

## Write mode — lens-guided authoring

1. **Pick the rung, then the lens, and say both.** The rung sets register:
   Quickstart = zero decisions and minutes-to-success; User guide = coherent
   prose legal, trade-offs introduced; Reference = uniform schema, dense and
   dry. Scannability/BLUF rules apply at full force on lookup pages (how-to,
   reference) and relaxed on learning pages (tutorial narration, explanation)
   where connected causal prose wins. The lenses:
   - *Tutorial* — a lesson; learner mindset; guaranteed-success path; no
     options, no explanation (link out instead).
   - *How-to* — a goal; competent-user mindset; action and only action, as a
     sequence; practical beats complete.
   - *Reference* — lookup; austere, factual, structure mirrors the product;
     describe and only describe. Use a rigid repeated page template.
   - *Explanation* — understanding; why it is so — decisions, constraints,
     alternatives weighed; opinion is legitimate here.
   ADRs, runbooks, changelogs map onto these (see lenses.md §"Extended lenses").
2. Apply the 15 style principles in lenses.md — most load-bearing: runnable
   verified examples (run every command before writing it, include expected
   output), document the negative space (what it does NOT do, when NOT to use
   it), fixed templates for reference pages, problem-before-solution for
   explanation, candor about limitations.
3. Apply the structure rules in structure.md: BLUF at every level, headings
   as frontloaded statements passing the TOC test, ≤H3 depth, bullets only
   for parallel items (reasoning stays in prose), repeated bullet patterns
   promoted to tables, blank line between blocks, no prose wall longer than
   ~4 paragraphs without a visual interrupt. New specs/plans start from the
   skeletons in structure.md.
4. **Curate visuals where information is flow/structure/sequence-shaped**
   (structure.md rules 16-17): diagrams break prose walls and encode the
   information more densely than the paragraphs they replace. Use
   **dual-density cascading detail** — simplified diagram inline, the
   ultra-detailed variant in a `<details><summary>` block beneath it, each
   with a one-sentence prose summary. Delegate the diagram authoring to a
   subagent instructed to invoke the `mermaidjs_diagrams` skill — it owns
   palette, contrast, and complexity gates; never hand-roll mermaid here.
5. If `voice` was requested, layer the voice fingerprint on top — it changes
   register and signature moves, never the lens discipline.
6. **Verify before done**: every command in the new doc executed (or `make -n`
   dry-run), every path globbed, every internal link resolved, TOC regenerated
   via the `mdtoc` skill for docs >100 lines, and any added diagrams passing
   the mermaidjs_diagrams gate scripts.

## Restructure mode — shape without changing claims

For improving the structural readability of an existing doc, spec, or plan
(read [resources/structure.md](resources/structure.md) first):

1. **Diagnose**: extract the heading outline and run the TOC test; scan for
   the structure smells table (prose walls, bullet walls, deep nests, vague
   labels, buried ledes, disguised tables, alert spam, zombie metadata).
2. **Propose the new outline first** — the before/after heading tree plus the
   smell list found, one line each. Get agreement before rewriting (the
   outline IS the restructure; prose moves are mechanical after that).
3. **Rewrite preserving every claim verbatim where possible**: this mode
   reorganizes — it does not re-research, re-verify, or reword technical
   content beyond frontloading topic sentences. If a claim looks wrong,
   flag it for an audit; don't silently fix it. Prose walls whose content is
   flow/structure-shaped may become diagrams (the information, unchanged, in
   visual form) — dual-density per structure.md rule 17, authored via a
   `mermaidjs_diagrams` subagent.
4. For specs/plans, converge toward the canonical skeletons (status block,
   BLUF summary, numbered requirement IDs, Open Questions, phases with
   observable acceptance criteria) — preserving existing IDs/anchors that
   other docs may reference.
5. **Verify before done**: heading levels never skip, every fence keeps its
   language tag, internal anchors still resolve (renamed headings break
   inbound links — grep for them), TOC regenerated via `mdtoc`.

## Cross-cutting rules

- Never write a claim you didn't verify; if unverifiable, mark it or cut it.
- **Capture THE WHY.** Code and docs record *what* and *how*; the reasoning
  behind a decision is the most valuable and most perishable layer. In critical
  places put a short WHY in the comment/docstring next to the code so the
  decision lens travels with the context; curate project-shaping reasons as
  ADRs (they accumulate the values that become the lens for future work). The
  richest WHY is often in the maintainer's prompting language — preserve it with
  reverence, like a letter to a future reader, rather than letting it evaporate.
- **Prune slop, don't add it.** Apply [resources/slop_smells.md](resources/slop_smells.md):
  every line must survive the delete test, and no value/identifier list is
  copied into prose where it would drift from code. Fewest touch points wins —
  write so the cost of a future refactor stays lean.
- One lens per page by default. A reference page that starts teaching, or a
  tutorial that starts enumerating options, gets split — unless the doc set
  deliberately fuses lenses with one consistent voice, in which case enforce
  the fusion's consistency instead. Small projects (< ~10 pages) get one good
  sectioned README, not four near-empty buckets.
- Keep doc sources near the code they describe; hub-and-spoke (thin root
  README routing to detailed docs next to their code).
- Diagram work is always delegated: launch a subagent that invokes the
  `mermaidjs_diagrams` skill (via the Skill tool) for curation, palette, and
  both gate scripts. gooddocs decides *where* a visual earns its place and at
  what density; mermaidjs_diagrams decides *how* it's drawn.
- Respect the repo's 500-line ceiling for skill/rule docs; suggest splits at
  natural seams rather than trimming substance.
