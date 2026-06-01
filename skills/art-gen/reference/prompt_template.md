# <Subject> — <icon | illustration | scene> (generic prompt template)
# Lines that start with '#' or '<!--' are STRIPPED before the prompt is sent.
# Use them freely to document intent and iteration history — they cost no tokens.
#
# HOW TO USE
#   1. Replace the body below with your curated prompt.
#   2. Generate:  uv run .claude/skills/art-gen/scripts/art_gen.py generate --prompt-file this_file.md
#   3. To fan out variants, copy this file (e.g. _poseA.md, _poseB.md), change only the
#      POSE/variation paragraph in each, and pass every file with its own --prompt-file.
#
# CONCEPT
#   <one or two lines: what this image is and the idea behind it>
#
# STYLE NOTES (accumulate from iteration feedback)
#   - <trait to reinforce, e.g. "thick bold outlines; flat fills, minimal shading">
#   - <trait to avoid, e.g. "not photorealistic, not painterly, no gradients">
#
# ── Curated prompt below this line. Be specific and exhaustive; every word is signal. ──

Create an illustration of <SUBJECT> on a plain white background. No text, no words, no
letters of any kind. No borders, no rounded corners, no drop shadows, no app-icon
framing. Just the subject floating on white.

STYLE: <e.g. a friendly, bold cartoon illustration — mascot-grade quality with thick
outlines and flat fills. NOT photorealistic or painterly. Low-fidelity and characterful.>

SUBJECT / POSE: <describe the subject and, if relevant, the single dramatic "keyframe"
moment — the peak of an action — so the composition has energy and intent. State the
angle, what it is doing, and where attention should land.>

COLOR PALETTE (strict): <list each tone with an exact hex code and what it covers, e.g.
"darkest #1A1A1A — primary shapes/outlines; mid #6B7280 — secondary areas; accent
#3B82F6 — the single focal highlight (the only saturated colour)">. Use no colours
outside this list.

COMPOSITION: <aspect and framing, e.g. "square (1:1), subject centred and filling about
65–75% of the frame, with breathing room around it.">
