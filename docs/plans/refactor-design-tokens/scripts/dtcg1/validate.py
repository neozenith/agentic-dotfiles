# /// script
# dependencies = ["jsonschema>=4.23", "referencing>=0.35"]
# ///
"""DT-DTCG-1 explain: build option A and option D from the real osakanights profile, validate each."""
import copy, json, urllib.request
from pathlib import Path
from jsonschema import Draft202012Validator, Draft7Validator
from referencing import Registry, Resource

SRC = Path("docs/plans/refactor-design-tokens/prototype/profiles/hue-osakanights/dtcg")
OUT = Path("docs/plans/refactor-design-tokens/scripts/dtcg1")
light = json.loads((SRC / "light.tokens.json").read_text())
dark = json.loads((SRC / "dark.tokens.json").read_text())

def get(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())

def refs(node, path=""):
    """Every {alias} and where it sits."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from refs(v, f"{path}.{k}" if path else k)
    elif isinstance(node, str) and node.startswith("{"):
        yield path, node

# Option A: modes as top-level groups; aliases must gain the mode prefix to resolve
def prefix(node, mode):
    if isinstance(node, dict):
        return {k: prefix(v, mode) for k, v in node.items()}
    if isinstance(node, str) and node.startswith("{") and node.endswith("}"):
        return "{" + mode + "." + node[1:]
    return node
A = {"$schema": "https://www.designtokens.org/schemas/2025.10/format.json",
     "light": prefix(light, "light"), "dark": prefix(dark, "dark")}
(OUT / "A.design-tokens.json").write_text(json.dumps(A, indent=1))

# Option D: one resolver document, both modes inline
D = {"$schema": "https://www.designtokens.org/schemas/2025.10/resolver.json",
     "version": "2025.10", "name": "osakanights",
     "modifiers": {"mode": {"contexts": {"light": [light], "dark": [dark]}, "default": "light"}},
     "resolutionOrder": [{"$ref": "#/modifiers/mode"}],
     "$extensions": {"dev.agentic-dotfiles.curation": {"profile": "osakanights"}}}
(OUT / "D.design-tokens.json").write_text(json.dumps(D, indent=1))

def check(name, doc, schema_url):
    schema = get(schema_url)
    # resolve any remote $refs the official schemas use
    registry = Registry(retrieve=lambda uri: Resource.from_contents(get(uri)))
    cls = Draft202012Validator if "2020-12" in schema.get("$schema", "") else Draft7Validator
    errs = list(cls(schema, registry=registry).iter_errors(doc))
    print(f"{name}: {'VALID' if not errs else f'{len(errs)} error(s)'} against {schema_url.rsplit('/',1)[-1]}"
          f"  ({len(json.dumps(doc))//1024} KB)")
    for e in errs[:3]:
        print("   ", list(e.absolute_path)[:6], e.message[:140])

print("aliases in the per-mode files:", list(refs(light))[:3])
check("A (groups light/dark)", A, "https://www.designtokens.org/schemas/2025.10/format.json")
check("D (resolver, modes inline)", D, "https://www.designtokens.org/schemas/2025.10/resolver.json")
print("A read :", A["light"]["color"]["text"]["default"]["$value"]["hex"])
print("D read :", D["modifiers"]["mode"]["contexts"]["light"][0]["color"]["text"]["default"]["$value"]["hex"])

D2 = copy.deepcopy(D)
ext = D2.pop("$extensions")
D2["modifiers"]["mode"]["$extensions"] = ext
(OUT / "D.design-tokens.json").write_text(json.dumps(D2, indent=1))
check("D (resolver, modes inline, $extensions on the modifier)", D2, "https://www.designtokens.org/schemas/2025.10/resolver.json")
