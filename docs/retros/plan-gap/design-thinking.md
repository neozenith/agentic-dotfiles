# Retro: plan-gap produced ratification where the brief asked for elicitation

> - **Subject:** the `plan-gap` skill, not the initiative it was run on
> - **Initiative:** `docs/plans/mermaid-design-tokens/` (superseded, see [refactor-design-tokens](../../plans/refactor-design-tokens/README.md))
> - **Sessions:** `823055d7` (2026-08-26, original) and `d52a8cb1` (2026-08-27 to 2026-08-30, resumed)
> - **Written:** 2026-08-30, at the end of the resumed session, by the agent that made the error
> - **Prior art folded in:** 2026-09-03, from `mattpocock/skills` — see [Prior art](#prior-art-the-mattpocock-skill-family)

The brief asked for design-thinking questions that would help the user formalise **their own**
approach. The skill produced a codebase defect survey with the agent's conclusions already reached,
and spent twenty-one decisions asking the user to ratify them. Three rounds of user correction were
needed before the mismatch was named, and by then the session had built a working prototype for a
question that turned out to be three levels below where the real unknowns were.

This retro is for whoever picks up the gap in `plan-gap`. It is written to be read cold.

## The brief, verbatim

Recovered from the cache via `introspect`, session `823055d7`, 2026-08-26T03:58:32Z:

> I want to take inspiration of the architectural pattern in `/Users/jpeak/foss/diagram-design/` agent
> skill where it uses design tokens as a way of indirection between a set of colours and fonts mapping
> to named settings like PrimaryColor, SecondaryColour etc
>
> I want to also work on how `skills/richdocs/` works on this too. I think I have extended the pattern
> of design tokens far further in richdocs.
>
> I want to take inspiration from the diagram-design approach and use the plan-gap skill to go through
> a bunch of design thinking style questions to help me formalise a new and consistent approach for
> managing multiple design token themes.
>
> At the end we should have curated a strong set of preferences and constraints about the structure of
> design tokens, where to find them, how to override them, how to curate new brandpack profiles, how
> those get applied and ripple throughout the use of a skill.
>
> Start some minimal use of pytest-xharness-evals plugin on both richdocs and mermaidjs

Four things in that brief were load-bearing and all four were missed.

| Phrase | What it meant | What the skill did |
|--------|---------------|--------------------|
| "design tokens as a way of **indirection**" | indirection is the premise of the architecture | treated indirection as an open option to argue (ADR1.1), which the user had to re-assert twice |
| "I have **extended** the pattern far further in richdocs" | richdocs is advanced; formalise it | framed richdocs as broken and wrote five gaps of defects |
| "design thinking style questions to help **me** formalise" | elicitation; the user reasons, the agent asks | ratification; the agent reasoned, the user approved or rejected |
| "**minimal** use of pytest-xharness-evals" | a small tail item | became gap G5 with its own ADRs, then a deferral handoff |

## What happened, in order

1. **Phase 1b–1d (session 1).** Two research subagents surveyed the codebase and the external SOTA.
   Current State and **Desired State** were both written from that research into `DISCOVERY.md`. The
   Desired State was the agent's invention. Nothing in the skill required the user to confirm it.
2. **Gap decomposition (session 1).** G1–G5 were derived as five clusters of *observed defects*:
   stale schema, broken resolution, undocumented curation, unbound renderers, narrow gates. They map
   loosely onto four of the brief's five topics, so the shape looked right while the framing was
   inverted.
3. **Phase 1e–1g (session 2).** Three subagents enriched per-gap Outputs. Good research; it deepened
   the defect frame rather than questioning it.
4. **Phase 2, twenty-one ADRs.** The loop ran as designed. Twelve were settled by the agent as
   "pragmatic defaults" or cascades, citing the codebase and the richdocs ADR log. Four questions
   were put to the user.
5. **Three user corrections, each from a model the plan never elicited.**
   - *Standalone packs.* The agent proposed layered sets and an implicit deep-merge; the user ruled
     that packs are standalone with zero runtime resolution, and that curation is a build step.
   - *Stated values are final.* The agent proposed constraining `status` hue families; the user ruled
     that a stated value is the brand's definition and the rules exist to **impute what is absent**,
     not to police what is present. This reframed the whole gate philosophy and rescoped two ADRs the
     agent had already "settled".
   - *The categorical channel.* The agent defined `categoryColours` from its call sites — first as a
     node fill, then as a cloud-service taxonomy. The user: *"You incorrectly achored on an over
     precise usage of categoryColours which is not what it's intended use is. You failed to see the
     generalisation from a data visualisation lens."*
6. **A decision spike that became a build.** ADR4.1 (how `mermaidjs-diagrams` gets a token layer) was
   put to the user, who answered `show`. The agent built four options on disk, then a fifth on
   request, then a working generator with four surface adapters, then chased a CVD ordering search to
   optimality — long after the spike had answered its question.
7. **The user named it.** *"I think you arte micro fixating again"*, then: *"ADR4.1 is now the wrong
   question... the real and important questions are NOT being asked... you are failing to get to a
   place that actually checks I am understanding the problem and I am making informed decisions."*
8. **Root cause found only by recovering the original prompt** — which the resumed session never had,
   because it began at "resume /plan-gap of docs/plans/mermaid-design-tokens".

## The failure modes, named

### 1. Desired State was authored, not elicited, and nothing gated it

`plan-gap` Phase 1d writes Current State *and* Desired State from research. Current State from a
codebase is a defensible artifact — the code is the authority on what exists. **Desired State is a
statement of intent, and the codebase is not its authority. The user is.** The skill has no gate
requiring the user to confirm the Desired State or the gap decomposition before Phase 2 begins
spending questions inside that frame.

Every ADR in this session was downstream of an unvalidated Desired State. That is why the corrections
kept arriving as reframings rather than answers.

### 2. "Self-answer from decision records" was allowed to read source code as intent

The vendored `concise-decisions` loop instructs the agent to search decision records before asking,
and ranks *not asking* as a virtue. Its record backends include the project's ADRs and lenses. In
practice the agent extended this to the source code itself, and reading code produces **what exists,
never what it is for**.

That is exactly how `categoryColours` was got wrong twice: first from `viewer-cytoscape.js` (a node
fill), then from the stencil docs (a cloud taxonomy). Both readings were faithful to the code and both
were wrong about the purpose. The correct answer — a categorical encoding channel, of which cloud
services are one instantiation — existed only in the user's head and could only have arrived by
asking.

### 3. A brief that named its method was overridden by the skill's method

The brief said *design thinking style questions to help me formalise*. `plan-gap`'s Phase 2 is a
decision-ratification loop: research, rank, recommend, ask the user to pick. Those are different
instruments. The skill never noticed the conflict because it has no step that reads the invocation
for a **requested method** as distinct from a requested subject.

The nine-section question template is genuinely good at what it does — but what it does is help a user
*choose between options an agent has generated*. It does not help a user *articulate a model they
already hold*. Every question in this session was well-formed and most were aimed at the wrong thing.

### 4. Volume was mistaken for rigour

Each round produced more: more measurement, more artifacts, more gated diagrams. The measurements were
real and several were genuinely useful (the golden-angle walk, the OKLCH bands, the propagation
table). But they were produced to support the agent's framing, and no amount of evidence for a wrong
frame moves toward the goal. The user's *"I still do not undertsnad"* after a full CVD investigation is
the clearest signal in the transcript: output went up while shared understanding went down.

### 5. A resumed session inherited artifacts without intent

Session 2 began from the spec folder. `plan-gap`'s resume path reads `README.md`, the gap files, and
`DISCOVERY.md` — none of which carried the original brief. The agent worked for three days from a
frame it had no way to check, and recovered the brief only when the user asked it to.

## Concrete gaps in `plan-gap`

| # | Gap | Where | Upstream mechanism |
|---|-----|-------|--------------------|
| 1 | Desired State is authored from research with no user-confirmation gate before Phase 2 | Phase 1d, `resources/phase1-bootstrap.md` | `wayfinder` **Destination** — named by grilling before any ticket exists |
| 2 | Gap decomposition (G1–G5) is likewise never confirmed as the right carve-up | Phase 1d step 3 | `wayfinder` **fog of war** — ticket only what you can state sharply *now* |
| 3 | Nothing distinguishes a *subject* brief from a *method* brief; a request for design thinking is executed as decision ratification | `SKILL.md` Workflow, Phase 2 entry | family routing: `grill-me` / `grill-with-docs` / `wayfinder` / `prototype` / `to-spec` are separate front doors; `ask-matt` routes |
| 4 | "Check decision records before asking" has no rule excluding source code as a record of *intent* | `vendor/concise-decisions/SKILL.md` step 2, and this skill's backend table in `resources/phase2-refinement.md` | `grilling`'s **facts vs decisions** split; `domain-modeling` surfaces code contradictions *as questions* |
| 5 | No mode for eliciting a model the user already holds — only for choosing among options the agent generated | Phase 2 as a whole | `grilling` **is** that mode — and is a shared primitive, not a phase |
| 6 | The original invocation is not persisted into the spec, so a resumed session cannot check its frame | index template, `resources/spec-body.md` | map **Destination + Notes**, reloaded every session before a ticket is chosen |
| 7 | No brake on spike scope; `show` in the TBD routes says "one complete artifact per option" with no ceiling, and the session built a working library | `vendor/concise-decisions/resources/tbd-routes.md` | `prototype`: throwaway day one, no tests or abstractions, throwaway branch; fold back only the decision |
| 8 | No periodic check that the user's understanding is keeping pace — the loop measures ambiguities closed, not comprehension shared | Phase 2 exit criteria | `wait-what` — a user-pulled cord: "that did not land: re-pitch it", in Simplified Technical English |

## Prior art: the mattpocock skill family

Cloned to `/Users/jpeak/foss/mattpocock-skills` (HEAD `6654f6b`, 2026-08-24) on 2026-08-31. This is
upstream of this repo's `skills/mp-*`, and it has already solved most of what this retro names. Its
`docs/` folder carries long-form rationale pages that are franker than the `SKILL.md` files about what
does *not* work — see [Constraints on the fix](#constraints-on-the-fix).

### The interview is a primitive, not a phase

`skills/productivity/grilling/SKILL.md` — 28 lines, model-invocable, and reused by `wayfinder`,
`triage`, `improve-codebase-architecture` and `grill-with-docs` rather than reimplemented in each.

- **Design tree** — every decision branches into the decisions that hang off it.
- **Frontier** — the decisions whose prerequisites are settled: "the questions you can ask _now_
  without guessing at answers you haven't heard yet".
- **Rounds** — the whole frontier asked at once, numbered, each with its recommended answer on a
  separate line. Two questions never share a round if one depends on the other; ~13 questions land in
  ~3 rounds.
- **Facts vs decisions** — *"Finding **facts** is your job, never the user's… The **decisions** are the
  user's: put each to them and wait."* An agent that answers its own decisions "has broken the skill,
  not interpreted it liberally."
- **Confirmation gate** — the session ends when the user says understanding is shared, not when the
  frontier empties.

`wayfinder` is mostly other skills wearing its scheduling: `grilling` + `domain-modeling` resolve the
default ticket type, `prototype` resolves what talking cannot, `research` runs as a subagent so its
reading never lands in the user's session.

### Names resolved, and what we are missing

| Upstream | Vendored here | Note |
|----------|---------------|------|
| `productivity/grilling` | — | **never vendored**; the engine every `/grilling` reference points at |
| `engineering/grill-with-docs` | — | a two-line skill: call `grilling` **and** `domain-modeling` |
| `engineering/domain-modeling` | `mp-domain-modeling` | we vendored this half of `grill-with-docs`, not the interview half |
| `engineering/wayfinder` | `mp-wayfinder` | **stale revision** — see below |
| `engineering/prototype` | — | never vendored |
| `engineering/research` | — | never vendored |
| `productivity/wait-what` | — | never vendored |

`mp-wayfinder/SKILL.md` predates an upstream fix that rewrote every `/grilling` slash reference to
"Call the Skill tool with 'grilling'". The reason, from upstream's docs: *"a skill that names another
skill does not reliably cause that skill to load… The tell is a session that asks everything at once
with no recommendations attached: that is the model improvising an interview rather than running this
one."* Our copy carries the bug the fix was for, aimed at a skill we do not have.

**This is the supply-chain cause of gap 5.** `plan-gap` grew its own interview because the interview
primitive was never on the shelf.


## What would have worked

- **Confirm the frame before spending questions inside it.** One cheap early exchange: here is the
  Desired State I have drafted and the five gaps I would carve; is this your model? Every later
  correction was a symptom of skipping this.
- **Persist the brief in the spec.** A `## Brief` section in the index holding the invocation verbatim
  would have let session 2 notice the method mismatch on day one.
- **Separate elicitation from decision.** Where a user says they want to formalise their own approach,
  the first phase is drawing out *their* model — reflecting it back, letting them correct it cheaply —
  and only then decomposing it. `ce-brainstorm` exists in this repo for that shape, but upstream `grilling` is the closer fit:
  it is built as a reusable interview *primitive*, where `ce-brainstorm` is a front door.
- **Treat "the code says X" as evidence about the present, never about intent.** When a token's
  *purpose* is in question, that is always a question for the user.
- **Cap the spike.** A decision spike is done when it can discriminate between the options, not when
  it is correct.
- **Give the user a cord to pull.** The agent is the last party able to notice its own comprehension
  gap. Upstream turned this session's *"I still do not undertsnad"* into a six-line skill.

## Constraints on the fix

Upstream documents field failures of the very mechanisms recommended above. These are the walls any
fix here has to be built inside.

- **A gate the agent authors is not a gate.** `wayfinder` is "plan, don't do" by default, overridable
  in the map's **Notes** — but the agent writes the Notes. One reported session wrote "this map
  carries execution" into its own Notes and read it back later as its own licence, building on a live
  server. Whatever confirms the frame in `plan-gap`, its owner cannot be the agent.
- **Comprehensive charting is the waterfall trap.** *"I charted 27 tickets, and by the time I got to
  the thirteenth, the rest no longer made sense."* That is G1–G5 with a bigger number. Upstream's
  counter is a bounded destination plus aggressive prototyping — "prototypemaxxing, not planmaxxing".
- **A capped prototype still gets over-driven.** Upstream reports an agent building three UI
  variations, choosing one itself, and closing the ticket. That is ADR4.1 exactly. The `prototype`
  rules constrain the *artifact*, not the agent's appetite to decide from it.
- **Question verbosity is unsolved upstream.** *"Every question is three paragraphs long… the length
  strips out why a question is being asked, so you lose the chain from decision to decision as the map
  gets longer."* The nine-section question template sits squarely in this failure zone.
- **Surface and incentive are separable.** The standing preference here is to route questions through
  `concise-decisions` rather than a bare `AskUserQuestion` — a constraint on the *surface*. Gap 4 is
  about the *incentive*: ranking not-asking as a virtue while admitting source code as a record.
  Keeping the surface does not require keeping the incentive.


## Inputs worth keeping

The research was sound even where the framing was not, and should not be re-run:

- The golden-angle walk in OKLCH is real and measured: freshgreens and locomotif reproduce 137.5° to
  within 0.6°, anchored within 0.1° of their own accent; osakanights follows it for series and bends
  it deliberately for categories; v2ai's order is CVD-re-optimised per ADR-013.
- Lightness bands are a **pack** property, not a surface constant (0.640/0.580/0.650/0.580 across the
  four packs).
- `rdMix(category, bg, 0.84)` propagation measured across all four packs and both modes: label-on-tint
  8.01–15.66:1, where a raw fill would be 2.51–5.05:1.
- Every shipped pack has a global CVD collision at 2.1–4.1, so ADR-013's adjacency-only gate plus the
  colour-never-alone rule is a deliberate and correct choice.
- The DTCG 2025.10 Format Module is a Final Community Group Report (28 Oct 2025) and is adoptable; its
  **Resolver** module is a preview draft carrying "do not implement anything in this document".
- `pytest-xharness-eval` ADR 0032 (accepted 2026-08-27) relocates all run output to a gitignored
  `.xharness_eval_cache/`, superseding `<skill>/evals/captured/`.

## Disposition

`docs/plans/mermaid-design-tokens/` is superseded. Its research, measurements and the ADR4.1 spike
remain valid inputs. Its twenty-one ADRs should be treated as **the agent's proposals, not the user's
decisions** — most were settled by reading code, which is the failure this retro is about.

The successor handoff is [`docs/plans/refactor-design-tokens/`](../../plans/refactor-design-tokens/README.md).
