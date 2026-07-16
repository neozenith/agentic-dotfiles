---
marp: true
theme: {{DECK_NAME}}
paginate: true
footer: '{{DECK_NAME}}'
---

<!--
Tag each slide with its audience. ONE marker, nothing else: an HTML comment
wrapping `@tier NAME`, where NAME is a tier declared in tiers.toml. (This block
spells it out rather than showing a literal one, because a real marker here would
tag THIS slide: the parser reads markers anywhere in a slide body.)

The progress bar is DERIVED from those markers by scripts/tier_progress.py
(`make progress`), which writes the generated <style> block. Never hand-edit the
block or the fractions. Move a slide, re-run, commit.

Run `make template` for the layout reference: every class, helper and directive
this deck supports, each shown with its source.
-->

<!-- _class: lead -->
<!-- _paginate: false -->

# {{DECK_NAME}}

## The one-line promise

**The claim this deck exists to make.**

---

<!-- _class: divider -->
<!-- @tier exec -->

# The problem

### The one sentence that makes the audience lean in

---

<!-- @tier exec -->

## Why it matters

- **Lead with the point.** A skimmer reads the bold and stops, so put the claim first.
- **One idea per bullet.** If a bullet needs a comma splice, it is two bullets.
- **Name the cost.** State what the problem takes, in money, time or risk.

> A quote or claim worth setting apart from the argument.

---

<!-- @tier mgmt -->

## What we propose

<div class="columns">
<div class="box">

### The approach
What you will do, in one sentence.

</div>
<div class="box">

### The control
How it stays safe, in one sentence.

</div>
</div>

<span class="badge">The one line they must remember.</span>

---

<!-- @tier lead -->

## How it works

| Claim | Evidence |
|---|---|
| The first claim | What proves it |
| The second claim | What proves it |

---

<!-- @tier ic -->

## What is real today

<div class="columns">
<div class="box">

### Built
- The parts that exist and run

</div>
<div class="box">

### Not yet built
- The parts that do not

</div>
</div>

Say this plainly. An audience cannot tell an aspiration from a deployment, and a
diagram of an unbuilt system is a false claim.

---

<!-- _class: divider -->
<!-- @tier ic -->

# The ask

### The specific, decidable thing you want from the room
