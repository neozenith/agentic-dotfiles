# Phase 3 — Validation (full playbook)

The step-by-step detail for Phase 3, referenced from `SKILL.md` → Workflow → Phase 3. `SKILL.md` holds
the one-line summary; this file holds the mechanics. Paths are relative to `.claude/skills/plan-gap/`.

Phase 3 runs **after** the refinement loop converges and **before** Phase 4 decomposition. It is a
gate, not a polish pass: a failure here is fixed in place (or sends control back to Phase 2), it is not
waved through. Three checks — diagrams, requirement integrity, cross-consistency.

## Step 3a: Diagram validation

A spec carries diagrams in two files:

- **`DISCOVERY.md`** — the architecture lenses and the gap-increment stack:
  - `## Current State` — **at least two lenses** chosen from the menu
    (`resources/mermaidjs_diagrams.md` → Lens menu), each a labeled diagram.
  - `## Desired State` — the **same** lenses, with consistent node IDs so the before/after reads as a
    visual diff.
  - `## Gap Increments` — **one diagram per `G<n>`**, each starting from the Current-State baseline and
    highlighting (process/good fills) only the nodes that `G<n>` changes; `G<n+1>` builds on `G<n>`'s
    diagram. Each lives under a stable anchor (`### G<n> increment`) that its gap file links to.
- **`README.md`** (index) — the **Gap Map** (`flowchart TD`) and **Dependencies** (`flowchart LR`),
  both MANDATORY.

If any required diagram is missing, that is a validation failure — add it before proceeding. Then render
**every file that carries a diagram** with mmdc in both variants (dark + light) and verify exit code 0;
read `resources/mermaidjs_diagrams.md` for the commands, complexity thresholds, and pitfalls, and follow
the palette/gate rules in `resources/style.md` → Diagrams. Both gates are blockers:

- **Contrast** — WCAG AA on every `classDef` / `style` (`fill` + `color`, no same-hue `stroke`).
- **Complexity** — medium density by default (≤20 nodes, VCS ≤40). A Gap Map MAY run detail-density
  (its 3×N current→gap→desired mapping justifies it) — caption it as such.

## Step 3b: Requirement integrity

Read `resources/escalators-not-stairs.md` and apply it across **every gap** and (after Phase 4) **every
ticket**, not just the index:

- Every **Success Measure** is a mandatory, falsifiable requirement — not a "nice to have", not a vague
  aspiration, not something that degrades gracefully.
- Every gap names a concrete **proof-of-execution Output** — a committed artifact produced by running
  the production code path on real input. A gap whose only proof would be a stub, a mock of its own
  deliverable, or a parallel re-implementation **fails** this audit.
- Every **Negative Measure** describes a concrete Type 2 failure — the system gives a false signal of
  success while silently failing to deliver the value.
- No requirement from the Gap Analysis is silently downgraded in the Success Measures.

## Step 3c: Cross-consistency

Verify the set hangs together:

- Every gap has at least one corresponding Success Measure.
- Success Measures are falsifiable (objectively testable).
- Negative Measures are the complement of Success Measures (what "looks done but isn't").
- The Current State and Desired State lenses are visually distinguishable, and each gap's increment
  diagram is visually distinct from the baseline it extends.
- Every cross-link resolves: each gap file's Depends-on/Blocks/Prev/Next, its
  `Architecture: DISCOVERY.md#g<n>-increment` back-link, each ticket's Gap/Depends-on, and every
  index → gap → ticket link points at a file (and anchor) that exists (`resources/style.md` rule 13).
- Every settled ADR appears both in its gap file and as a row in the index Decisions roll-up.

For a **GitHub-issue spec**, diagrams render natively on GitHub (no mmdc render gate for correctness),
but local mmdc validation is still recommended to catch syntax errors before pushing; the cross-link
check applies to sub-issue task-list references instead of local files (`resources/gh-issues.md`).

When all three checks pass, proceed to Phase 4. If Step 3b surfaces a downgraded requirement that cannot
be fixed by an edit (the gap as written cannot produce real evidence), return control to Phase 2 to
rescope rather than passing the gate.
