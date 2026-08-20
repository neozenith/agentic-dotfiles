# Contrast Tooling Surface

The full CLI surface of the two contrast tools — flags, output fields, and the
exit-code contract. The *mandate* to run them lives in `SKILL.md` ("Required
for every diagram"); this file is the reference you open when the recipe there
isn't enough. The conceptual palette rules live in `color_theming.md`.

## Two complementary tools

| Script | Scope | Use when |
|--------|-------|---------|
| `scripts/mermaid_contrast.ts` | Audits every `classDef`/`style` directive inside `.mmd`/`.md` files — scores `fill × color` (text on fill) at AA ≥ 4.5:1 and `fill × stroke` (border on fill) at AA ≥ 3:1 | Catching low-contrast custom color palettes before they land in docs |
| `scripts/color_contrast.ts` | Generic WCAG + APCA calculator for any two CSS colors (hex, rgb, oklch, named, etc.) | Ad-hoc pair checks — e.g. sampling colors from a screenshot or comparing theme tokens |

## Invocations

```bash
# Audit every diagram in a directory tree (auto-detects mkdocs vs github)
bun run .claude/skills/mermaidjs-diagrams/scripts/mermaid_contrast.ts docs/
bun run .claude/skills/mermaidjs-diagrams/scripts/mermaid_contrast.ts docs/ --summary
bun run .claude/skills/mermaidjs-diagrams/scripts/mermaid_contrast.ts docs/ --json

# Force a render context (see SKILL.md "Required for every diagram")
bun run .claude/skills/mermaidjs-diagrams/scripts/mermaid_contrast.ts docs/ --profile mkdocs-material
bun run .claude/skills/mermaidjs-diagrams/scripts/mermaid_contrast.ts docs/ --profile github

# Ad-hoc pair
bun run .claude/skills/mermaidjs-diagrams/scripts/color_contrast.ts "#ffffff" "#2563eb"
bun run .claude/skills/mermaidjs-diagrams/scripts/color_contrast.ts "rgb(55 65 81)" "oklch(0.98 0 0)" --json

# Translucent fill: --over composites it onto the page bg first (resolve the box)
bun run .claude/skills/mermaidjs-diagrams/scripts/color_contrast.ts "#36464e" "#1d4ed836" --over "#ffffff"

# Batch pairs via stdin
echo '[["#fff","#777"],["red","blue"]]' | bun run .claude/skills/mermaidjs-diagrams/scripts/color_contrast.ts --stdin --json
```

## Exit semantics

Both scripts: `0` if every pair passes AA, `1` if any fail, `2` on usage error.
The non-zero exit makes both tools drop-in suitable for `make ci`-style gates.

Unlike the renderer, these tools need no browser, no package registry, and no
special execution class — they keep working in the restricted environments
described in `render_troubleshooting.md`. When a render is blocked, these gates
are still the proof that the diagram itself is sound.

## Output fields (per pair / per directive)

- `ratio` — WCAG 2.x contrast ratio, 1.0 – 21.0, rounded to 2dp
- `rating` — pass tier (`AAA`, `AA`, `AA Large`, or `fail`)
- `apca_lc` — signed APCA Lightness contrast (-108..+106), rounded to 1dp.
  APCA is the next-gen algorithm driving WCAG 3.0 and handles dark-mode colors
  more accurately than the ratio metric.
