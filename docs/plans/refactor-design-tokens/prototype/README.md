# Prototype: from a hue to a theme

A throwaway spike, not the curation tool. It walks the locked decisions end to end from seeds that state
**only a hue**, so the defaults can be seen propagating before the real tool is designed.

## Run

From the repo root:

```bash
uv run --no-project docs/plans/refactor-design-tokens/prototype/pipeline.py all
uv run --no-project .claude/skills/richdocs/scripts/md2html.py docs/plans/refactor-design-tokens/prototype/propagation.md --inline
uv run --no-project .claude/skills/richdocs/scripts/showcase.py
```

`all` runs `curate`, `build`, `install` and `doc`; each is also a subcommand, and `--profile NAME` limits
any of them to one profile. `init-seeds` rewrites the four seeds from the richdocs themes' light accents.

## Layout

```text
pipeline.py                     the whole pipeline, stdlib only
propagation.md                  generated: seed -> IR -> DTCG, per profile, with contrast checks
profiles/hue-<theme>/
  seed.json                     what is stated: {"brand.hue": ...}
  ir.json                       every role, both modes; rule and inputs under $extensions
  dtcg/light.tokens.json        DTCG 2025.10 colour objects
  dtcg/dark.tokens.json
  dtcg/profile.resolver.json    the mode modifier
  design-tokens.json            projection onto richdocs' current schema, for showcase.py
```

`install` copies each projection into `tmp/richdocs/theme/<name>/`, where richdocs' project override
lookup finds it. The showcase gallery then shows each hue-only theme beside its source theme.

## What to play with next

Every parameter and its default is in `DEFAULTS` at the top of `pipeline.py`, tagged with its source
decision or `prototype`. Add any of those keys to a `seed.json` and re-run `all` to see the override
propagate. The IR's top-level `$extensions` records each parameter as `stated` or `default`, which is the
starting point for working out how curation tells a stated value from an imputed one (DT-PROV-1).

## Known gaps

- `themecheck.py` only reads built-in themes, not `tmp/richdocs/theme/`, so it cannot check these.
  `propagation.md` carries its own text-on-background contrast tables instead.
- richdocs' legacy `status` has four levels and the locked vocabulary has three, so the projection maps
  both `serious` and `critical` to `color.text.danger`.
- richdocs' legacy `categoryColours` is one set for both modes; the projection uses the light-mode walk.
