# Vendored dependencies

Wholesale copies of capabilities `plan-gap` needs but does not author. Vendoring is
how this skill stays self-contained (`skills/CLAUDE.md` → "skills are fully
self-contained"): no runtime surface here may read, run, or be aware of a sibling
skill's files, so a needed capability is copied in and operated from this folder.

| Vendored | Operated by | Runtime authority |
|----------|-------------|-------------------|
| `concise-decisions/` | `resources/phase2-refinement.md` (Phase 2) | its `SKILL.md` + `resources/**` |
| `discovery/` | `resources/phase1-bootstrap.md` (Phase 1, step 1b) | its `SKILL.md` + `resources/**` |

## Rules for the copies

- **Read-only.** Never hand-edit a vendored file. A change you want is either a
  plan-gap overlay (write it in the phase file that operates the copy, per the
  table above) or an upstream change followed by a re-vendor.
- **Runtime authority is the vendored `SKILL.md` and the resources it names.**
  Each copy also carries its upstream `README.md`, `CLAUDE.md`, and `docs/adrs/` —
  development-time documents kept for provenance, addressed to whoever *edits* the
  upstream skill. They are **not** plan-gap's decision log (that is `../CLAUDE.md`),
  they are not decision records for a run, and they are never cited as authority
  while running.
- **A vendored copy accumulates nothing.** No session writes into this tree — not a
  learning file, not a cache, not a note. Everything a run produces belongs to the
  spec being refined; everything a *maintainer* learns belongs in `../CLAUDE.md`
  and the surface it governs. That is what keeps the refresh below a clean
  wholesale replace with nothing to preserve.

## Refresh procedure

Re-vendor wholesale, never cherry-pick individual files:

```sh
rsync -a --delete \
  --exclude node_modules --exclude '.*cache*' --exclude .DS_Store --exclude evals \
  <upstream-skill-dir>/ skills/plan-gap/vendor/<name>/
```

Then re-read the overlay that operates it and reconcile: if upstream renamed a
resource, changed a step number, or altered the question anatomy, the overlay's
citations must be updated in the same commit. Drift from upstream is accepted
between refreshes; a stale copy that still works is preferred to a live reference
that couples two skills.
