## Shell Tools

When you need to call tools from the shell, **use this rubric**:

- Find Files: `fd`
- Find Text: `rg` (ripgrep)
- Find Code Structure (PY/TS/TSX): `ast-grep`
  - **Default to Python:**  
    - `.py` → `ast-grep --lang py -p '<pattern>'`  
  - **For Typescript and React:**  
    - `.ts` → `ast-grep --lang ts -p '<pattern>'`  
    - `.tsx` (React) → `ast-grep --lang tsx -p '<pattern>'`
  - For other languages, set `--lang` appropriately (e.g., `--lang rust`).
- Select among matches: pipe to `fzf`
- JSON: `jq`
- YAML/XML: `yq`

If `ast-grep` is available avoid tools `rg` or `grep` unless a plain‑text search is explicitly requested.

On a mac I should run this prior to ensure the tools are available:
```sh
brew install fd ripgrep ast-grep fzf jq yq
```

## Running Python Scripts

NEVER run arbitrary `python` commands. Especially `python -c '...'`.

Create the python script first even if it is a temporary one. 

Each script should run independently using `uv` like:

```sh
uv run scripts/script_name_here.py
```

You should be able to extract full usage information with the `--help` flag.

```sh
uv run scripts/script_name_here.py --help
```