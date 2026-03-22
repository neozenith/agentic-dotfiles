# Iconify Icon Setup Reference

Icons in Mermaid `architecture-beta` diagrams come from [Iconify](https://iconify.design/) icon packs.
Equivalent to `diagrams.custom.Custom` — this is how you bring any icon into a Mermaid diagram.

## Syntax

```
architecture-beta
    service <id>(<set>:<slug>)[Label]
    group   <id>(<set>:<slug>)[Label]
```

- **`<set>`**: Iconify icon set prefix (e.g. `logos`, `mdi`, `carbon`, `aws`)
- **`<slug>`**: Icon name within that set (e.g. `postgresql`, `server`, `s3`)
- Label and icon are both optional — `service mynode[Label]` works without an icon

## Icon Set Quick Reference

| Set prefix | npm package | Best for |
|------------|-------------|----------|
| `logos` | `@iconify-json/logos` | Tech brand logos (languages, frameworks, cloud) |
| `mdi` | `@iconify-json/mdi` | Generic UI/infrastructure concepts |
| `carbon` | `@iconify-json/carbon` | IBM-style enterprise/cloud shapes |
| `aws` | `@iconify-json/aws` | AWS service-specific icons |
| `gcp` | `@iconify-json/gcp-icons` | Google Cloud icons |
| `azure` | `@iconify-json/azure-icons` | Azure service icons |
| `devicons` | `@iconify-json/devicons` | Developer tool logos |
| `vscode-icons` | `@iconify-json/vscode-icons` | Editor/file type icons |

## Online vs Offline Loading

**Online (default):** Icons fetched from `https://api.iconify.design/{set}.json` at render time.
No setup required in the diagram source.

**Offline / self-hosted:** Register the pack in JavaScript before rendering:

```js
import { addCollection } from '@iconify/iconify';
import logosData from '@iconify-json/logos/icons.json';

addCollection(logosData);
```

Or via Mermaid's `iconPacks` config:

```js
mermaid.initialize({
  architecture: {
    iconPacks: ['logos', 'mdi', 'carbon'],
  },
});
```

## Registering a Custom Icon Pack

For icons not in any public set (internal brand logos, proprietary service icons):

```js
import { addCollection } from '@iconify/iconify';

// Minimal collection structure
addCollection({
  prefix: 'myorg',
  icons: {
    'data-lake': {
      body: '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>',
    },
    'ml-pipeline': {
      body: '<path d="..."/>',
    },
  },
  width: 24,
  height: 24,
});
```

Then reference as `myorg:data-lake` in the diagram.

## Browsing Available Icons

- **Search all sets:** https://icon-sets.iconify.design/
- **Logos set browser:** https://icon-sets.iconify.design/logos/
- **MDI browser:** https://icon-sets.iconify.design/mdi/
- **Copy the slug** shown under each icon — use it directly in `(<set>:<slug>)`

## Minimal Architecture Diagram Example

> **⚠ Mermaid 11.x bug — edges MUST have labels.** Unlabeled edges (`-->`) cause a
> Cytoscape.js rendering failure: the diagram parses silently but `mmdc` outputs an
> error-bomb PNG. Always use `-[label]-` in the arrow body.
> Correct: `id:Dir -[label]-> Dir:id` Wrong: `id:Dir --> Dir:id`

```
architecture-beta
    group cloud(logos:aws)[Cloud Region]

        service gateway(mdi:api)[API Gateway] in cloud
        service compute(mdi:server)[Compute] in cloud
        service store(logos:postgresql)[Database] in cloud
        service cache(logos:redis)[Cache] in cloud

    gateway:R -[route]-> L:compute
    compute:R -[query]-> L:store
    compute:T -[read]-> B:cache
```

## Using Icon Packs with `mmdc` CLI

When rendering diagrams via the command line, Iconify packs must be specified explicitly.
Icons are downloaded from `unpkg.com` on first use and cached locally.

### `--iconPacks` — npm packages

Pass one or more `@iconify-json/<set>` package names:

```bash
# Single pack
npx -p @mermaid-js/mermaid-cli mmdc \
  -i my_diagram.mmd \
  -o my_diagram.png \
  --scale 4 --iconPacks @iconify-json/logos

# Multiple packs (space-separated after the flag)
npx -p @mermaid-js/mermaid-cli mmdc \
  -i my_diagram.mmd \
  -o my_diagram.png \
  --scale 4 --iconPacks @iconify-json/logos @iconify-json/mdi @iconify-json/carbon

# Markdown input with icon packs
npx -p @mermaid-js/mermaid-cli mmdc \
  -i docs/plans/my_plan.md \
  -o docs/diagrams/mmdc/my_plan.md \
  -a docs/diagrams/mmdc/ \
  --scale 4 --iconPacks @iconify-json/logos @iconify-json/mdi
```

### `--iconPacksNamesAndUrls` — custom URL packs

For icon packs not on npm, or for pinned/custom versions. Format: `prefix#url`:

```bash
# Azure icons from a custom GitHub-hosted Iconify JSON
npx -p @mermaid-js/mermaid-cli mmdc \
  -i my_diagram.mmd \
  -o my_diagram.png \
  --scale 4 --iconPacksNamesAndUrls "azure#https://raw.githubusercontent.com/NakayamaKento/AzureIcons/refs/heads/main/icons.json"

# Multiple custom packs (space-separated)
npx -p @mermaid-js/mermaid-cli mmdc \
  -i my_diagram.mmd \
  -o my_diagram.png \
  --scale 4 --iconPacksNamesAndUrls \
    "azure#https://example.com/azure-icons.json" \
    "myorg#https://example.com/internal-icons.json"

# Mix npm packs + URL packs
npx -p @mermaid-js/mermaid-cli mmdc \
  -i my_diagram.mmd \
  -o my_diagram.png \
  --scale 4 --iconPacks @iconify-json/logos @iconify-json/mdi \
  --iconPacksNamesAndUrls "azure#https://raw.githubusercontent.com/NakayamaKento/AzureIcons/refs/heads/main/icons.json"
```

The `prefix` before `#` becomes the icon set name used in the diagram source
(e.g. `azure#...` means you write `(azure:StorageAccounts)` in the diagram).

### Makefile Integration

The `docs/diagrams/Makefile` generated by `setup_diagrams.py` supports an `ICON_PACKS` variable:

```bash
# Default (logos + mdi)
make -C docs/diagrams

# Override for a project using carbon icons too
make -C docs/diagrams ICON_PACKS="@iconify-json/logos @iconify-json/mdi @iconify-json/carbon"
```

## Key Rules

1. Icon set + slug are **case-sensitive** — use lowercase with hyphens as shown in icon browsers
2. Unknown icons render as an empty box — validate slugs against the Iconify browser
3. `group` nodes support icons the same as `service` nodes
4. `junction` nodes have **no** icon or label (they're routing points only)
5. Edge direction syntax: `A:R -[label]-> L:B` (right side of A → left side of B); sides are `L R T B`
   - **Direction goes BEFORE the rhs node id**: `A:R -[label]-> L:B` ✓  `A:R -[label]-> B:L` ✗ (error bomb)
   - **Labels are mandatory** — mermaid 11.x Cytoscape renderer silently fails on unlabeled edges, outputting an error-bomb PNG. The exit code is still 0 and the file is still written, so there is no way to detect the failure programmatically. Always include `-[label]-`.
6. CLI rendering **requires** `--iconPacks` — icons are not bundled in mmdc by default
7. **`--iconPacks` only works for real npm packages** — the mechanism is a `fetch(https://unpkg.com/${pack}/icons.json)` fired inside Puppeteer Chromium. If the package doesn't exist on npm, unpkg.com returns a 404 with no CORS header, which Puppeteer blocks silently. The diagram renders with empty icon boxes and exit code 0, giving no indication of the failure. Verified working packages: `@iconify-json/logos`, `@iconify-json/mdi`.
8. **Layout rule: one outgoing `R` edge per node** — Cytoscape's grid layout (used by architecture-beta) cannot resolve fan-out (one node → multiple `R` targets). Fan-out causes nodes to collapse onto each other or draw diagonal lines. Graphviz `dot` handles fan-out via rank assignment; architecture-beta does not. Design diagrams as strict linear chains for clean layouts.
