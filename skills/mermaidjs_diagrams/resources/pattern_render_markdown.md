# Pattern: Render Diagrams from Markdown

Render mermaid fences embedded in `.md` files using `mmdc`'s native markdown input mode.
No infrastructure setup is required.

## How It Works

`mmdc` reads a markdown file, extracts every ` ```mermaid ` fence, renders each as an
image artefact, and outputs a validated copy of the markdown with fences replaced by
`![diagram](image)` tags.

## Rendering Variants

Rendering is parameterised by three values that form a **variant tuple**:

| Parameter | Flag | Values | Default |
|-----------|------|--------|---------|
| Theme | `-t` / `--theme` | `default`, `dark` | `dark` |
| Background | `-b` / `--backgroundColor` | `white`, `black`, `transparent` | `transparent` |
| Output Format | (file extension) | `png`, `svg` | `png` |

The variant tuple determines the **output folder name**: `{theme}_{backgroundColor}_{format}`

Examples:
- `dark_transparent_png` (default)
- `default_white_png` (light theme for docs/README)
- `dark_black_svg` (dark with opaque background, vector)

## Rendering from a Markdown File

All examples use two variables:
- `BASE` -- output root directory (e.g. `.mmdc_cache` since I will often gitignore `.*_cache`)
- `VARIANT` -- the `{theme}_{backgroundColor}_{format}` tuple

The `-e` flag controls the artefact format (`png` or `svg`). Theme and background
flags apply to both formats.

### Render a single variant

```bash
INPUT="path/to/document.md"
BASE=".mmdc_cache"
VARIANT="dark_transparent_png"       # default variant

mkdir -p "${BASE}/${VARIANT}"
npx -p @mermaid-js/mermaid-cli mmdc \
  -i "${INPUT}" \
  -a "${BASE}/${VARIANT}/" \
  --scale 4 -e png -t dark -b transparent
```

### Render multiple variants

Generate both light and dark variants side by side:

```bash
INPUT="path/to/document.md"
BASE=".mmdc_cache"

# Variant 1: dark + transparent + PNG (default)
VARIANT="dark_transparent_png"
mkdir -p "${BASE}/${VARIANT}"
npx -p @mermaid-js/mermaid-cli mmdc \
  -i "${INPUT}" \
  -a "${BASE}/${VARIANT}/" \
  --scale 4 -e png -t dark -b transparent

# Variant 2: default + white + PNG (for README, light-mode docs)
VARIANT="default_white_png"
mkdir -p "${BASE}/${VARIANT}"
npx -p @mermaid-js/mermaid-cli mmdc \
  -i "${INPUT}" \
  -a "${BASE}/${VARIANT}/" \
  --scale 4 -e png -t default -b white
```

### SVG variant (scalable vector output)

```bash
INPUT="path/to/document.md"
BASE=".mmdc_cache"
VARIANT="dark_transparent_svg"

mkdir -p "${BASE}/${VARIANT}"
npx -p @mermaid-js/mermaid-cli mmdc \
  -i "${INPUT}" \
  -a "${BASE}/${VARIANT}/" \
  --scale 4 -e svg -t dark -b transparent
```

**Output structure** (for two PNG variants):
```
${BASE}/
├── dark_transparent_png/
│   ├── document.md           # Markdown with ![diagram] image tags
│   ├── document-1.png        # First mermaid fence rendered
│   ├── document-2.png        # Second mermaid fence rendered
│   └── ...
└── default_white_png/
    ├── document.md
    ├── document-1.png
    └── ...
```

## Rendering Standalone `.mmd` Files

For individual `.mmd` files (e.g. extracted from markdown or managed separately):

```bash
BASE="docs/diagrams"
VARIANT="dark_transparent_png"

mkdir -p "${BASE}/${VARIANT}"
npx -p @mermaid-js/mermaid-cli mmdc \
  -i "${BASE}/diagram.mmd" \
  -o "${BASE}/${VARIANT}/diagram.png" \
  --scale 4 -t dark -b transparent
```

## Using as Verification

This pattern can be used standalone or as a **verification step within the managed
`.mmd` workflow** (Pattern: Managed `.mmd` Files). After creating or updating diagrams,
render from the source markdown to verify all fences are valid:

```bash
INPUT="path/to/document.md"
BASE=".mmdc_cache"
VARIANT="dark_transparent_png"

mkdir -p "${BASE}/${VARIANT}"
npx -p @mermaid-js/mermaid-cli mmdc \
  -i "${INPUT}" \
  -a "${BASE}/${VARIANT}/" \
  --scale 4 -e png -t dark -b transparent
```

**Exit code 0** = all diagrams valid. **Non-zero** = error printed to stderr with
the offending diagram. Fix the fence and re-run.

## Icon Packs

When using `architecture-beta` diagrams with Iconify icons, add `--iconPacks`:

```bash
npx -p @mermaid-js/mermaid-cli mmdc \
  -i document.md \
  -a output_dir/ \
  --scale 4 -t dark -b transparent \
  --iconPacks @iconify-json/logos @iconify-json/mdi
```

For custom icon packs via URL:
```bash
  --iconPacksNamesAndUrls "vendor#https://example.com/icons.json"
```

Flowchart diagrams using Font Awesome (`fa:fa-icon`) need no `--iconPacks` flag.

## Per-Project Makefile Target

For projects that want `make diagrams` to render mermaid blocks from `README.md`:

```makefile
DIAGRAMS_DIR = diagrams
MMDC = npx -p @mermaid-js/mermaid-cli mmdc

diagrams:                ## Render README Mermaid diagrams (both variants)
	@mkdir -p $(DIAGRAMS_DIR)/dark_transparent_png
	@mkdir -p $(DIAGRAMS_DIR)/default_white_png
	$(MMDC) -i README.md -a $(DIAGRAMS_DIR)/dark_transparent_png/ \
		--scale 4 -e png -t dark -b transparent
	$(MMDC) -i README.md -a $(DIAGRAMS_DIR)/default_white_png/ \
		--scale 4 -e png -t default -b white

diagrams-clean:          ## Remove rendered diagram artefacts
	rm -rf $(DIAGRAMS_DIR)
```

## Variant Quick Reference

| Variant Tuple | Theme | Background | Format | Best For |
|---------------|-------|------------|--------|----------|
| `dark_transparent_png` | dark | transparent | PNG | Dark-mode UIs, slides, terminals |
| `dark_transparent_svg` | dark | transparent | SVG | Scalable dark-mode docs |
| `default_white_png` | default | white | PNG | README, light-mode docs, print |
| `default_white_svg` | default | white | SVG | Scalable light-mode docs |
| `dark_black_png` | dark | black | PNG | OLED screens, high contrast |
| `default_transparent_png` | default | transparent | PNG | Adaptive light-mode overlay |
