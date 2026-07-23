# Learned: collaboration workflows for targeted edits

Distilled from real editing sessions. These are **alignment rituals**: cheap intermediate
artifacts that get the human and the agent pointing at the same thing *before* an expensive
or hard-to-reverse edit. Read this when a task involves "put X on the right spot" or "make
this face/logo/region correct" — produce the agreement artifact first, then edit.

> Self-curated learning file (see `.claude/rules/claude_skills/statefulness.md`, Pathway 2).
> Entries are already-decided; refine them as the workflow improves, don't re-litigate.

## 1. Identity mapping before any face work

**Problem it solves:** an edit that targets "person N" silently swaps the wrong person.
A batch face-swap once mapped a teammate onto the driver because correspondence was guessed.

**Ritual:** before swapping/relabelling faces, emit a **colour-coded identity annotation**
per image — detect faces (YuNet or buffalo_l), draw the box + landmarks + a per-person
colour and name, and get the human to confirm. One colour per person, kept stable across
every frame, so the mapping reads at a glance (see the `tmp/*_named.png` / `05_annotated`
style: cyan/pink/green/yellow per person).

**How to assign names reliably (in priority order):**

1. **Stable physical features** — glasses, facial hair, hair colour/greying, skin tone.
   These are the strongest single cues (e.g. "only one teammate wears glasses").
2. **Fixed seating relative to a known anchor** — when two people look similar, role
   disambiguates: the person *at the wheel* is the driver; the one holding the pace-notes is
   the navigator; the rest are passengers by their seat. Encode the seating chart once and
   reuse it every frame.
3. **Recognition embeddings are a weak tiebreaker, not an authority** — cosine similarity
   between an AI-generated face and a real portrait runs low (~0.1–0.4), so a 1:1 embedding
   assignment can be confidently wrong. Use it to *propose*, always confirm visually.

**Then** swap with an explicit, confirmed name→source mapping — never an auto-match on the
low-confidence path.

## 2. The labelled grid: a shared coordinate vocabulary

**Problem it solves:** exchanging raw pixel coordinates is slow and error-prone, and a crop
that shows "only the rear door" wastes a round-trip.

**Ritual:** overlay a **labelled grid** (columns = letters A, B, C…; rows = numbers 1, 2,
3…) with `scripts/grid.py overlay <img> --cell 200`. The human then names a region as a
spreadsheet range — **"the doors are C5:F6"** — and `scripts/grid.py resolve C5:F6` returns
the pixel `box` **and** the TL/TR/BR/BL `quad`, which drops straight into an `art_pipe`
`perspective-overlay` `dst` or a `crop` `box`. Coordinates never get typed by hand.

```bash
uv run .claude/skills/art-edit/scripts/grid.py overlay frame.png -o frame_grid.png --cell 200
uv run .claude/skills/art-edit/scripts/grid.py resolve C5:F6 --cell 200
#   → {"box": [400,800,1200,1200], "quad": [[400,800],[1200,800],[1200,1200],[400,1200]]}
```

Pick the cell size for the image scale (200px suits a ~2.7K frame → ~14×8 cells). A finer
cell (100px) buys precision where a region needs it. The range is inclusive of the named
cells, and either corner order works (`F6:C5` == `C5:F6`).

**Extend it per task:** for a repeated placement (logos on every keyframe's doors), grid all
the frames once, collect one range per frame from the human, resolve each to a quad, and run
the batch. The grid is the interface; the resolver is the glue to the pipeline.

**Propose-then-correct, don't ask cold.** Do not hand the human a blank grid and ask "where
are the doors?". Make a **reasonable guess yourself, highlight the cells** you believe are
right (`grid.py overlay … --highlight "D5:H6=DOORS"`), and ask them only to *correct* the
ones that are off. Reviewing a proposal is far faster than specifying from scratch, and your
guess is usually close after one look. Colour-code multiple proposed regions distinctly
(amber for one logo zone, gold for another) so several proposals are corrected in one pass.
When you can see your own guess is wrong (the highlight catches the window line, misses the
front door), refine it before presenting — hand over your *best* guess, not your first.

**Label legibility is not optional.** Bright grid/label colours vanish on a bright sky or a
pale panel. Always draw axis and region labels with a contrasting outline (a black stroke
around the glyph reads on any background) rather than a single flat colour — otherwise the
reference letters you're asking the human to use are invisible exactly where the subject is
light. `grid.py` strokes every label for this reason.

## 3. Research current models when a technique hits its ceiling

**Problem it solves:** settling for a deterministic method that has a known quality wall,
when a purpose-built model would clear it.

**Ritual:** when an in-house technique underdelivers (the 2D landmark-affine face warp
imported the source portrait's lighting/expression and looked pasted-on), **research the
current model landscape** and surface the option to the user — what it does better, its cost,
and its caveats. In this project a quick search found *re-synthesising* face-swap models
(InsightFace `inswapper`) that regenerate the face to fit the target's pose/expression/light
— a clear, visible improvement the deterministic op could not reach.

Practical notes learned doing it:

- **Availability is a real gate.** `inswapper_128.onnx` was pulled from InsightFace's
  official releases (auto-download 404s); a HuggingFace community mirror had it. Probe the
  registry you actually need, and report honestly when a model is gated.
- **Keep heavy/dual-use models out of the deterministic skill.** Run them as a clearly-marked
  `tmp/` trial (own PEP-723 deps, own model cache) so the offline `art-edit` gate stays lean
  and the licensing/ethics of a face-swap model is an explicit, visible choice — not a
  silent dependency.
- **Present evidence, not just a claim.** Generate the comparison (native vs new model) and
  let the user judge; note where the new tool wins and where it doesn't (large forward faces:
  big win; small side-on faces: marginal).

## 4. Communicating fine placement: corner handles + a nudge vocabulary

**Problem it solves:** a grid range places a logo in the right *area*, but "the right area"
isn't "the right **angle/centre/skew**". On a foreshortened panel a flat axis-aligned decal
looks stuck-on. Humans find raw perspective coordinates hard to dictate.

**Ritual — preview with labelled handles, then take nudges.** Render the proposed placement
with its quad drawn on the frame and each corner labelled **TL / TR / BR / BL**, plus a
centre crosshair and the current rotation. Now the human has named things to move, and can
speak in a small, learnable **nudge vocabulary** the agent applies and re-previews:

| Intent | The human says | The agent does |
|--------|----------------|----------------|
| Rotate | "rotate −4°" / "tilt clockwise a bit" | rotate the quad about its centre |
| Scale | "shrink 10%" / "a bit bigger" | scale the quad about its centre |
| Move | "shift down 30px" / "left half a cell" | translate the quad |
| Skew / perspective | "pull the **TR** corner down" / "the right edge should lean back" | move the named corner(s) only |
| Re-anchor | "centre it on **F6**" | recompute the quad around a grid cell |

Per-corner control is what buys *perspective*: dragging just TR/BR down makes the decal
recede with the door. Keep the loop tight — one preview, a few nudges, re-render — and stop
when the human says it sits right. Persist the final quad in the pipeline spec so it is
reproducible and reusable as the starting point on the next frame.

**Match the placement to the panel's plane.** Cars/surfaces at a 3/4 angle need the logo's
far edge shorter (foreshortened); a purely rectangular quad reads as a sticker. Start from
the door's own four corners (read off the grid) rather than an axis-aligned box when the
surface visibly recedes.

## The menu — patterns to offer a user up front

When a task needs the human to point at *where / who / how-aligned*, proactively offer these
so they can pick the cheapest channel for what they mean:

- **Labelled grid + cell range** ("doors are E4:H5") — for *where* (region). §2
- **Colour-coded named annotation** — for *who* (identity), confirmed before edits. §1
- **Propose-then-correct highlights** — agent guesses, human only fixes the misses. §2
- **Corner handles + nudge vocabulary** — for *how-aligned* (angle/centre/skew). §4
- **Side-by-side comparison** — for *which is better* (native vs a model). §3

Announce the menu when a placement/identity task starts; let the human choose the channel.

## The through-line

Each ritual front-loads a cheap, legible artifact — a colour-coded map, a labelled grid, a
handled preview, a side-by-side — so agreement happens *before* the costly step. When a task
is "target the right thing", build the agreement artifact first, and offer the human the
lightest vocabulary that expresses what they need to convey.
