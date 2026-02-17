# Custom Node Reference

Use `Custom` to add any icon (company logos, product icons, etc.) not built into the diagrams library.

## Import

```python
from diagrams.custom import Custom
```

## Constructor

```python
Custom(label: str, icon_path: str)
```

- **`label`**: Display text below the icon
- **`icon_path`**: Path to a **local** PNG file (no direct URL support)

## Using Local Images

Place PNG icons relative to your script, then reference by path:

```
project/
  diagram.py
  icons/
    company_logo.png
    partner_logo.png
```

```python
from diagrams import Diagram, Cluster
from diagrams.custom import Custom
from diagrams.aws.compute import Lambda

with Diagram("Integration", show=False, direction="LR"):
    company = Custom("Acme Corp", "./icons/company_logo.png")
    partner = Custom("Partner API", "./icons/partner_logo.png")
    worker = Lambda("Worker")

    company >> worker >> partner
```

## Using Remote Images (URLs)

Download first with `urlretrieve`, then pass local path:

```python
from diagrams import Diagram
from diagrams.custom import Custom
from urllib.request import urlretrieve

# Download icons before diagram context
urls = {
    "hl_cloud": "https://example.com/hl-cloud-logo.png",
    "trac": "https://example.com/trac-logo.png",
}
icons = {}
for name, url in urls.items():
    local = f"{name}.png"
    urlretrieve(url, local)
    icons[name] = local

with Diagram("External Systems", show=False, direction="LR"):
    hl = Custom("H&L Cloud", icons["hl_cloud"])
    trac = Custom("Trac", icons["trac"])
    hl >> trac
```

## Helper Pattern: Icon Folder Scanner

When the user provides a folder of images, scan and create a lookup:

```python
from pathlib import Path
from diagrams.custom import Custom

def load_icons(icon_dir: str) -> dict[str, str]:
    """Scan directory for PNG files, return {stem: path} mapping."""
    return {p.stem: str(p) for p in Path(icon_dir).glob("*.png")}

# Usage
icons = load_icons("./icons")
# icons = {"company_logo": "./icons/company_logo.png", ...}
node = Custom("My Company", icons["company_logo"])
```

## Key Rules

1. Only accepts **local file paths** — always download remote images first
2. PNG format works best (SVG not supported)
3. Recommended icon size: 256x256 px (larger images are auto-scaled)
4. `Custom` nodes support all edge operators (`>>`, `<<`, `-`) and `Cluster` grouping
5. Clean up downloaded files after diagram generation if desired
