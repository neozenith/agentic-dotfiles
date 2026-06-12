---
name: gooddocs
description: "Documentation quality skill with three modes: (1) AUDIT — fan out parallel subagents to corroborate that docs still reflect the reality of the code (commands run, paths exist, signatures match, claims hold) and produce a drift report; (2) WRITE/IMPROVE — author or rewrite docs using the researched lens taxonomy (Diátaxis + distilled style principles from great OSS docs), optionally in the maintainer's personal voice; (3) RESTRUCTURE — reorganize an existing doc, spec, or plan file for structural readability (heading hierarchy, list/table discipline, whitespace rhythm, BLUF) without changing its claims. Use when the user asks to check/audit docs, fix stale docs, write or improve documentation, restructure a doc/spec/plan for readability, or says 'gooddocs'. Add 'voice' to the invocation to write in the maintainer's voice; default is the neutral researched style."
argument-hint: "[audit | write <target> | restructure <target>] [voice] [paths] (default: audit all docs)"
user-invocable: true
---

# Good Docs

Two jobs: keep docs **true** (audit mode) and make docs **great** (write mode).
Incorrect documentation is worse than missing documentation — drift detection
comes first, style second. Every page gets exactly one lens (tutorial, how-to,
reference, explanation); mixing lenses on one page is the root failure mode of
bad docs.

Resources (read on first use):
- [resources/lenses.md](resources/lenses.md) — lens taxonomy + 15 distilled
  style principles from the OSS docs survey.
- [resources/structure.md](resources/structure.md) — markdown structure rules:
  heading hierarchy, list/table discipline, whitespace rhythm, structure
  smells, spec/plan skeletons.
- [resources/voice.md](resources/voice.md) — the maintainer's voice
  fingerprint. Load ONLY when the user asked for `voice`; otherwise the
  neutral researched style applies.

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
doc, record: path, apparent lens, age vs the code it describes
(`git log -1 --format=%cs -- <doc>` vs the same for the code dirs it references).

### 2. Fan out verification subagents (parallel)

Launch parallel `Explore`/`general-purpose` subagents, one per doc (or per doc
cluster). Each agent receives the doc text and must verify every **checkable
claim**, reading the actual code — never trusting the doc:

| Claim type | Check |
|------------|-------|
| Commands / snippets | Do the flags, targets, scripts exist? Run read-only ones (`--help`, `make -n`) where safe; never run mutating commands. |
| File paths & repo layout | Paths exist? Layout diagrams match `ls` reality? |
| API signatures / config keys | Match current source? (grep the symbol) |
| Env vars | Referenced vars actually read in code? Code-read vars documented? |
| Versions / counts / numbers | Match lockfiles, configs, actual counts? |
| Links | Internal links resolve? (External: spot-check only.) |
| Behavioral claims | A `file:line` in current source supports the claim? |

Each agent returns: claim → verdict (`confirmed` / `drifted` / `unverifiable`)
→ evidence (`file:line` or command output) → suggested fix.

### 3. Drift report

```
## Docs audit: <N> docs · <C> claims checked · <D> drifted · <U> unverifiable

| Doc | Claim | Reality | Severity | Fix |
|-----|-------|---------|----------|-----|
| README.md:42 | `make dev` boots both servers | target renamed to `make up` | 🔴 broken quickstart | update command |
```

Severity: 🔴 a reader following the doc fails (wrong command/path/signature) ·
🟡 misleading but survivable · 🟣 unverifiable claim (flag for the author).
Order by severity. Offer: (a) apply fixes · (b) fix 🔴 only · (c) report only.
When applying fixes, fix the *doc* unless the doc is the contract and the code
drifted — if ambiguous, ask which is authoritative.

## Write mode — lens-guided authoring

1. **Pick the lens first** (one per page) and say which:
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
- One lens per page. A reference page that starts teaching, or a tutorial that
  starts enumerating options, gets split, not blended.
- Keep doc sources near the code they describe; hub-and-spoke (thin root
  README routing to detailed docs next to their code).
- Diagram work is always delegated: launch a subagent that invokes the
  `mermaidjs_diagrams` skill (via the Skill tool) for curation, palette, and
  both gate scripts. gooddocs decides *where* a visual earns its place and at
  what density; mermaidjs_diagrams decides *how* it's drawn.
- Respect the repo's 500-line ceiling for skill/rule docs; suggest splits at
  natural seams rather than trimming substance.
