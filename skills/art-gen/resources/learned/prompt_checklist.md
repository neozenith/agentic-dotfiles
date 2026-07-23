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

## Appending to this file

When a run comes back wrong, add an entry in the same shape — **Symptom / Case (dated) /
Why / Check** — in the same session, while the evidence is in front of you. Keep it under
500 lines; if it overflows, promote the stable rules into `SKILL.md` and delete the rest.
