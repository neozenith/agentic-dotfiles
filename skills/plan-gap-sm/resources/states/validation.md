# State: validation — gate the converged spec before decomposition

This is a gate, not a polish pass: fix failures in place, or (for a defect that cannot be fixed by
an edit) raise an `<!-- UNRESOLVED -->` ADR in the affected gap file — the machine then routes back
to refinement automatically. Three checks this turn:

1. **Diagrams.**
   - `DISCOVERY.md`: ≥2 Current-State lenses, the same lenses for Desired State (consistent node
     IDs so before/after reads as a visual diff), and one `### G<n> increment` diagram per gap,
     each building on the previous.
   - `README.md`: Gap Map (`flowchart TD`) and Dependencies (`flowchart LR`) both present.
   - Render every diagram-bearing file (e.g. `mmdc`, or the project's mermaid validation tooling)
     and check contrast (every `fill:` paired with `color:`; WCAG-AA text) and complexity
     (≤ ~20 nodes; split anything denser).
2. **Requirement integrity.** Every Success Measure is mandatory and falsifiable; every gap names a
   concrete proof-of-execution Output (a committed artifact produced by running the real code path
   on real input); every Negative Measure is a concrete looks-done-but-isn't failure; no
   requirement has been silently downgraded to optional/fallback/skip-with-warning.
3. **Cross-consistency.** Every gap has ≥1 Success Measure; every cross-link resolves (gap
   Depends-on/Blocks/Prev/Next, `DISCOVERY.md#g<n>-increment` anchors, index→gap links); every
   settled ADR appears in both its gap file and the index Decisions roll-up.

**Receipt (required to exit).** When all three checks pass, write the evidence to
`.pgsm/receipts/validation.json`:

```json
{
  "checked_at": "<ISO-8601>",
  "render": {"command": "<exact command run>", "exit_code": 0, "files": ["README.md", "DISCOVERY.md"]},
  "requirement_integrity": "pass",
  "cross_consistency": "pass",
  "notes": "<anything a reviewer should know>"
}
```

This is the one place you write under `.pgsm/` — the receipt records a check you actually executed;
never write it without running the render. The exit gate is the receipt file plus marker and
diagram-count checks; a failing check means no receipt and the machine holds here.
