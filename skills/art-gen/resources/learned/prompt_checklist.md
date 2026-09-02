# Learned: pre-flight prompt checklist

Read this **before sending any generation request**, and append to it whenever a run comes
back wrong or a prompt has to be reworded. Each entry is a real failure that cost a paid
generation, written as a check you can apply in seconds.

> This is a self-curated learning file (see `.claude/rules/claude_skills/statefulness.md`,
> Pathway 2). Entries here are **already-decided** — don't re-litigate them. When an entry
> graduates into a permanent rule it moves into `SKILL.md` with an ADR noting the promotion;
> entries invalidated by a model change get deleted.

## The checklist

Run these against the prompt body (the text that survives comment-stripping) before spending.

### 1. Never name a string you don't want rendered

**Symptom:** the picture contains the exact words you forbade.
**Case (2026-07-24):** the constraint *"the words 'AI', 'language' and 'token' must not
appear anywhere in the picture"* produced a sky full of the words `AI`, `language`, `token`
and `subword`. An earlier version describing *"glowing AI language tokens"* and *"fragments
of subword text"* did the same.
**Why:** image models condition on the strings present. Negation is weak-to-absent over
rendered text, so a prohibition still supplies the token to draw.
**Check:** if a word must not appear in the image, it must not appear in the prompt **at
all** — not even inside a "do not render" clause. Describe the *shape* instead ("plain
angular shards with blank unmarked surfaces"). Put the semantic meaning in the storyboard
README where only humans read it.

**Corollary — the same lever works in reverse (2026-07-24):** when garbled/rendered text is
a *deliberate* style (a storm of jumbled AI glyphs and token fragments was wanted), *do*
describe it as text — "luminous garbled glyphs, jumbled half-words, code-like token
fragments" — and it appears. The rule is not "never mention text"; it is **"the prompt draws
what it names, so name text exactly when you want it and never when you don't."** When you do
want garble, still forbid *coherent* output: "deliberately garbled and meaningless, never
real sentences, never a real brand name or logo", or real captions creep in.

### 2. Describe subjects by feature, never by inferred identity

**Symptom:** the prompt asserts a real person's gender, age or role from a photograph.
**Case (2026-07-24):** reference-image descriptions were written as "a fair-skinned man in
his late thirties". Nothing in the source material established that, and these prompt files
are committed and reused.
**Why:** the cues that actually drive likeness are hair, stubble, eyewear, face shape and
build. Gender adds little and risks misgendering a real colleague in a file they will read.
**Check:** use neutral phrasing — "a fair-skinned person in their late thirties, short dark
brown hair, light stubble, rectangular dark-rimmed glasses". Reserve pronouns for people
whose pronouns you actually know; otherwise they/them.

### 3. State subject count as a hard number, and give each one a visible position

**Symptom:** N-1 people appear.
**Case (2026-07-24):** "four occupants" reliably produced three; the fourth was occluded or
simply omitted. Fixed by "there are EXACTLY FOUR people, no more and no fewer: two in the
front and two in the back, and all four faces are clearly visible and unobstructed", plus a
per-person seat assignment and a body style (five-door) that makes the rear seats visible.
**Check:** for any count > 2, state the number in words *and* assign each subject a distinct,
visible location. Then check the composition physically permits it — a two-door car cannot
show four faces.

### 4. Ask for "fictional and unbranded" up front

**Symptom:** a real manufacturer's badge, grille or logo appears.
**Case (2026-07-24):** rally-car frames came back wearing Škoda, Ford, VW and Lancia badges.
Real products are heavily represented in training data, so a generic object drifts toward a
specific brand.
**Check:** for any manufactured object, say it is fictional and unbranded and enumerate what
must be absent (badge, emblem, bonnet logo, branded grille shape, sponsor decals), then name
the *only* markings allowed. Expect partial compliance — verify the output, and if a badge
survives, heal it offline with `art-edit`'s `inpaint` rather than paying for a re-roll.

### 5. Prefer a positive restatement to a prohibition

**Symptom:** a "no X" instruction is ignored or inverted.
**Case (2026-07-24):** "no grey smoke" was less effective than "the storm is emissive light
that glows from within and lights the ground".
**Check:** for every "do not", ask whether the same intent can be stated as something to
draw. Keep prohibitions for a short final constraints block, and make each one concrete and
checkable rather than abstract.

### 6. Check the *actual* pixel dimensions against your cost assumption

**Symptom:** the bill is ~2× the estimate.
**Case (2026-07-24):** `--size 2K --aspect 16:9` renders 2752×1536. Pricing tiers on the
**longest edge**, so every frame billed at the 4K rate ($0.24, not $0.134).
**Check:** before a sweep, generate one frame and read `dimensions` + `estimated_cost_usd`
from its sidecar. `history` totals a directory.

### 7. Prompt-level fixes before pixel-level fixes

**Symptom:** paying for re-rolls to fix something deterministic.
**Case (2026-07-24):** livery colours that needed removing were better solved by asking for
plain black bodywork in the first place, and by keeping `art-edit` for anything left over.
**Check:** ask whether the defect is cheaper to fix in the prompt (free, before spending) or
offline in `art-edit` (free, after spending). Re-generating is the expensive third option.

### 8. Video (Veo): verify model id, region, and retrieval per backend BEFORE spending

**Symptom:** a paid request 404s, or renders successfully and then fails to download.
**Case (2026-07-24):** three separate failures on the first Veo clip, each costing a round
trip (and the third costing a *rendered but unretrieved* clip):

1. **Model ids are backend-specific.** Vertex/ADC serves GA ids `veo-3.1-*-generate-001`;
   the Gemini Developer API serves `veo-3.1-*-generate-preview`. The docs show `-preview`,
   so copying the docs onto a Vertex client 404s.
2. **Veo is region-restricted.** The Vertex `global` location has *no* Veo publisher model —
   `us-central1` does. A location default that works for images silently breaks video.
3. **Retrieval differs.** `client.files.download()` raises *"only supported in the Gemini
   Developer client"* on Vertex, where the bytes arrive inline on the video object. The
   render is already paid for by the time this fails.

**Check, in order, before the first paid video call:**
- List the publisher models for the project/region and confirm the exact id exists
  (`client.models.list()` filtered for the family) rather than trusting the docs' id.
- Pin an explicit region; never leave it at `global` for video.
- Handle both retrieval shapes (inline `video_bytes` first, `files.download` as the
  fallback) so a successful render is never lost to the download step.
- Run `--dry-run` to confirm the composed prompt and cost, then spend.

**Why it matters:** an image mistake costs cents; a video mistake costs dollars per attempt
and minutes of render time. Verify the *plumbing* with the cheapest model/duration first,
then re-run at quality.

### 9. Video: "continuous single take" + keyframe interpolation reads as SLOW MOTION

**Symptom:** an action clip looks like a gentle cruise; the subject appears to drift rather
than move with intent, even though the prompt described fast action.
**Case (2026-07-24):** a rally clip pinned between a drift keyframe and a jump keyframe was
asked for as *"continuous single take, handheld energy"*. The result read as slow driving.
**Why:** first-frame + `last_frame` interpolation already biases the model toward a smooth,
evenly-paced morph from A to B. Asking for a **single continuous take** on top of that
removes the only remaining device for compressing time, so the model spreads one gentle
movement across the whole duration. The two instructions compound.
**Check:**
- For action, ask for a **fast-cut montage** with an explicit shot count and per-shot
  duration ("five hard cuts in eight seconds, ~1.5s each, cutting on the action, no
  dissolves"). Cuts are how a short clip conveys distance and time passing.
- State **speed as its own requirement**, not as an adjective on the subject: "the car is
  absolutely flat out the entire time; speed is the single most important quality".
- Give **concrete velocity cues** the model can render — scenery strobing past, debris
  blasting off the tyres, heavy motion blur, engine at the limiter — rather than the bare
  word "fast".
- Reserve "continuous single take" for shots whose *point* is the unbroken move (a reveal,
  a oner); never combine it with keyframe interpolation on an action beat.
- Keep the **final shot** of the montage matching the end keyframe, so the clip still lands
  where the chain needs it.

### 10. "Overlap the middle of the letters" destroys the word when it wraps

**Symptom:** the poster's headline word is unreadable — the subject occludes letters the
reader needed.
**Case (2026-08-05):** a value poster asked for the subject to be drawn *"in front of the big
violet word, overlapping and hiding the middle of those letters so the word reads as if it is
behind him"*. On one of four frames the model set `ENGINEERING` on **two** lines and then
faithfully occluded the middle of **both**, yielding `ENG?NE / ER?NG`. The three frames that
kept the word on one line were fine.
**Why:** the occlusion instruction and the line-breaking decision are independent. The model
honours the overlap literally, so any wrap doubles the damage — and nothing in the prompt
pinned the line count.
**Check:** when a headline is meant to sit behind the subject, constrain **both** halves:
- pin the line count explicitly ("the word ENGINEERING is set on a single unbroken line").
- occlude a *named edge*, not "the middle" — "the subject overlaps only the lower third of
  the letters; every letter remains individually readable".
The source posters this style was distilled from do exactly that: one line, bottom edge only.

### 11. Reference-image POSE drives character likeness more than the prompt text

**Symptom:** a carefully described mascot comes back as a generic version of its species.
**Case (2026-08-05):** the same mascot prompt was run against two reference stills of the same
toy. The three-quarter, open-mouthed, one-arm-raised still produced a recognisable character;
the flatter arms-up, closed-mouth still produced a generic gremlin with human hands, pointy
ears and none of the toy's googly-eye stalks — even though the prompt named every one of those
features.
**Why:** with a `--ref`, the image dominates the text for *shape*; prose feature lists only
nudge it. A reference frame that hides the character's distinguishing silhouette gives the
model nothing to hold on to, and it falls back to the category prior.
**Check:** choose the reference frame that shows the **most distinguishing silhouette**
(expression open, limbs separated from the body, signature features unoccluded) rather than the
most neutral one. When unsure, run both poses — it is one extra frame, and it is the cheapest
A/B available.

### 12. A hard text inventory beats trusting the style reference not to bleed

**Symptom (avoided):** words from a style-reference image appear in the output.
**Case (2026-08-05):** a poster style-reference containing the rendered words `MISSION PILOT`
was passed as `--ref` alongside a subject reference. All four frames rendered *only* the three
intended strings, with no bleed.
**Why:** the prompt opened its typography block with *"there are exactly three pieces of text
in this poster and nothing else"*, numbered each one, and closed with *"apart from the three
pieces of text named above, every surface in the picture is blank and unmarked"* — a positive
restatement (rule 5) rather than a prohibition naming the unwanted strings (rule 1).
**Check:** when conditioning on a style reference that itself contains lettering, state a hard
**count** of text elements, enumerate them, and describe every other surface as blank. Do not
name the reference's words in order to forbid them.

### 13. Plan multi-image sets around a project RATE WINDOW, not around a per-run count

**Symptom:** `google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED` partway through a
fan-out, killing every remaining prompt file in that batch. `art_gen.py` does not catch it, so
the traceback aborts the run and the un-generated prompts are simply lost.
**Case (2026-08-05):** an eight-panel comic page. First attempt split the panels across two
concurrent four-prompt `generate` jobs; one 429'd after a single image. Serialising did **not**
fix it — a later single-process four-prompt top-up 429'd on its *first* call, with no
concurrency involved at all. Roughly five `gemini-3-pro-image` renders in a few minutes
exhausted the window on this project.
**Why:** the limit is a **project-level rate window**, not a per-process or per-invocation
budget. Concurrency makes you hit it sooner but is not the cause, so serialising alone does not
avoid it. Sequential fan-out inside one invocation has no inter-request delay either.
**Check, for any set of more than ~4 paid images:**
- Expect to generate in **waves with a cooling gap between them**, and plan the wall clock for
  that. A set of 8 is two or three sittings, not one command.
- Treat a 429 as a **scheduling** result, never a prompt failure — do not reword anything, and
  do not re-roll panels that already succeeded.
- Re-run only the prompts whose PNGs are missing. Derive that list from the **sidecars**
  (`prompt_file`), not from memory of what you launched.
- Make the composing step resolve order from the sidecar too, so a partial batch plus later
  top-ups still assemble in the right order and a re-roll keeps its slot despite a newer
  timestamp.
- Related failure in the same session: one call returned **no parts at all**, surfacing as
  `TypeError: 'NoneType' object is not iterable` rather than an API error. Same response —
  re-run that prompt, don't rewrite it.

### 14. Write constraints as imperatives to the artist, never as statements about the picture

**Symptom:** a sentence from the prompt's own constraints block appears *inside the image* as
rendered lettering.
**Case (2026-08-05):** a comic panel prompt ended with the constraint *"Apart from the one
caption box described above, every surface, screen, page, banner and garment in the picture is
blank and unmarked."* The panel came back with a caption box reading `IT COMPILES! SHIP IT!`
followed, in smaller type on the next line, by `All screens and garments are blank.`
**Why:** two things compounded. (a) The constraint was a **declarative sentence describing the
picture** — grammatically identical to the scene description, so it was treated as content to
depict rather than a rule to obey. (b) It sat immediately after the caption instruction, so it
read as a continuation of the caption. This is rule #1's failure mode wearing a different hat:
the prohibition supplied the very words it forbade.
**Check:**
- Phrase every constraint as an **imperative to the artist** — "Leave every surface free of
  lettering", not "every surface is blank". Imperatives cannot be mistaken for scene content.
- **Close the text inventory explicitly**: "The caption box contains these words and no others,
  and no further words appear inside it: X". An open-ended "the caption reads: X" invites
  continuation.
- Never place a constraints block adjacent to a lettering instruction. Put scene description
  between them, or the model reads them as one clause.
- This is cheap to catch: read the rendered lettering back word-for-word against the intended
  string before accepting a panel.

### 15. A self-contradicting prompt returns NO image, and it looks like a script crash

**Symptom:** `TypeError: 'NoneType' object is not iterable` from `art_gen.py`, with no API error
and no image. Re-running reproduces it exactly.
**Case (2026-08-05):** a comic panel's scene asked for a wall poster bearing *"one short bold
line at the top and three short bullet lines under it"*, while the same prompt's constraints
block said to *leave every surface free of lettering*. Two runs of that prompt both returned a
response with no image parts. Rewording the poster as **shapes** — "one short thick horizontal
black bar near its top and three short thin black bars beneath that, the way a headline and
three bullets look from across a room" — rendered first time.
**Why:** the two clauses could not both be satisfied. The model returned no image rather than
picking a side, and because `art_gen.py` iterates the response parts without checking for an
empty candidate, a *semantic* prompt failure surfaces as a Python traceback and reads like
infrastructure.
**Check:**
- Treat a reproducible `NoneType`/empty-parts failure as a **prompt contradiction**, not a
  transient API blip. Re-run once to confirm; if it repeats, read the prompt for a clause that
  fights another clause.
- Audit shared blocks against per-item scenes. A global constraint written once and injected
  into every prompt is exactly where this hides — it was fine for seven panels and fatal for the
  eighth.
- When a constraint forbids lettering but the scene needs something that *looks* like text,
  describe the **marks** (bars, blocks, squiggles) rather than the text. That satisfies both
  clauses instead of choosing between them.

## Appending to this file

When a run comes back wrong, add an entry in the same shape — **Symptom / Case (dated) /
Why / Check** — in the same session, while the evidence is in front of you. Keep it under
500 lines; if it overflows, promote the stable rules into `SKILL.md` and delete the rest.
