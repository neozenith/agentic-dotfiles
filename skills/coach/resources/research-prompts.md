# Research Prompt Templates

Templates for the parallel research subagents launched in Phase 1 of `SKILL.md`. Substitute `<TOPIC>` with the learner's topic before invoking.

All agents have two hard rules:

1. **Every non-obvious claim must be accompanied by a citation** (URL + one-line source description). Uncited claims are discarded.
2. **Prefer primary sources** (specifications, papers, official docs, canonical implementations) over blog posts, listicles, or SEO content.

Launch agents **in a single message, multiple `Agent` tool calls** so they run concurrently.

---

## Default fan-out (always launched)

### Agent 1 — Web & official documentation

```
subagent_type: general-purpose
description: "Ground <TOPIC> via official sources"
```

> Research the topic **<TOPIC>** using WebSearch and WebFetch. Return a concise report (≤400 words) with these sections:
>
> 1. **One-paragraph precise definition** from the most authoritative source you can find (standard body, vendor doc, canonical textbook). Cite the URL.
> 2. **3–5 foundational sub-concepts** that a learner must understand before they can use the topic. For each: a one-line definition + citation.
> 3. **Common misconceptions** — specific wrong mental models that learners hold. For each: what the misconception is + why it's wrong + citation if available.
> 4. **When does it apply vs not apply** — boundary conditions. Cite.
>
> Prefer: W3C/IETF RFCs, official language/framework docs, vendor reference documentation, standards bodies, seminal textbooks. Avoid: content farms, AI-generated summaries, low-effort blog aggregations.

### Agent 2 — Academic / arxiv

```
subagent_type: general-purpose
description: "Find peer-reviewed foundations for <TOPIC>"
```

> Research the topic **<TOPIC>** by searching arxiv.org, Google Scholar, ACM DL, and similar academic sources. Return a concise report (≤400 words):
>
> 1. **Seminal paper** — the paper most commonly cited as the origin or canonical reference. Title, authors, year, URL, one-sentence contribution.
> 2. **2–4 key follow-ups** that refined, challenged, or extended the seminal work. Same fields as above.
> 3. **Current state (last 2 years)** — what the open problems and recent advances are. One sentence per paper, 2–3 papers.
> 4. **Terminology drift** — has the name of this concept changed across the literature? Are there synonyms a learner might encounter?
>
> For each paper, include arxiv URL or DOI. Do not include a paper you have not verified exists.

### Agent 3 — GitHub / reference implementations

```
subagent_type: general-purpose
description: "Find canonical <TOPIC> implementations on GitHub"
```

> Research the topic **<TOPIC>** by searching GitHub for reference implementations, canonical libraries, and high-quality examples. Return a concise report (≤300 words):
>
> 1. **Canonical implementation** — the repo most commonly used or referenced as "how this is done in practice." Repo URL, star count, one-sentence description of what makes it canonical.
> 2. **2–3 alternative implementations** showing different approaches, with the trade-off each makes vs the canonical one.
> 3. **A minimal, readable code snippet** (≤30 lines) from one of the repos that demonstrates the core concept in isolation. Link to the file and line range.
> 4. **Common implementation pitfalls** visible in the issues trackers of these repos (if any).
>
> Prefer: high-star, actively maintained repos with clear docs. Avoid: abandoned forks, tutorial repos, AI-code-dump repos.

---

## Conditional fan-out (only if user supplied sources)

### Agent 4 — Local codebase

Only launch if the user supplied file or directory paths.

```
subagent_type: Explore
description: "Map <TOPIC> usage in supplied codebase paths"
thoroughness: medium
```

> Analyse the supplied paths `<PATHS>` for code and documentation related to the topic **<TOPIC>**. Return:
>
> 1. **Where the topic is implemented or referenced** — file paths and line numbers.
> 2. **The project's specific vocabulary for the topic** (names, abbreviations, conventions).
> 3. **Any divergence from the canonical form** of the topic (as known from public sources) — e.g. the project uses a simplified or extended variant.
> 4. **Learning hooks** — 2–3 concrete places in the code where reading the file would teach the topic well.

### Agent 5 — Confluence / Google Drive (MCP)

Only launch if the user supplied `confluence:…` or `gdrive:…` hints.

```
subagent_type: general-purpose
description: "Gather internal docs on <TOPIC> from MCP sources"
```

> Use the available `mcp__claude_ai_Atlassian_Rovo__*` / `mcp__claude_ai_Google_Drive__*` tools to search the internal documentation spaces specified by `<HINTS>` for pages related to **<TOPIC>**. Return:
>
> 1. **Internal canonical page** for the topic (if one exists) — title, URL, last-modified date.
> 2. **Internal-specific terminology** that differs from public usage.
> 3. **Internal constraints or policies** that a learner must know to use the topic correctly inside this organisation.
> 4. **A list of 3–5 internal pages worth reading next**, ordered by information density.
>
> Do not quote long passages verbatim — summarise and link.

---

## Synthesis after agents return

When all agents return, synthesise by producing the ≤5-bullet summary in Phase 2 of `SKILL.md`. Rules during synthesis:

- **Union, then prune.** Take the claims from all agents. Discard any that are not cited. Discard any that conflict with a higher-authority source.
- **Order by foundational dependency.** Bullet 1 is the one every other bullet presumes.
- **Prefer the learner's context when agents disagree.** If the internal (Agent 5) docs say something different from public (Agent 1) docs, the internal version is what the learner will encounter — note both and favour internal.
- **Kill a bullet rather than pad one.** If you cannot state it precisely in one line, it belongs in Phase 3 expansion, not the summary.
