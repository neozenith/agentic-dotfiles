#!/bin/bash
# Script to render Mermaid.js diagrams in markdown files using the mermaid-cli tool
# Usage: ./render_mermaid.sh path/to/diagram.md [more files...]
#        ./render_mermaid.sh docs/**/*.md

set -euo pipefail

if [ $# -eq 0 ]; then
  echo "Usage: $0 <file.md> [file2.md ...]" >&2
  exit 1
fi

OUTPUT_BASE=".mmdc_cache"

# Keep temporary npm packages inside the task workspace. `npx` otherwise writes
# to the shared user npm cache, which can be owned by another process and fail
# with EPERM before Mermaid starts. This does not choose or download a browser.
MERMAID_RUNTIME_DIR="${MERMAID_RUNTIME_DIR:-$PWD/tmp/.mmdc_cache}"
export MERMAID_RUNTIME_DIR
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-$MERMAID_RUNTIME_DIR/npm}"
mkdir -p "$NPM_CONFIG_CACHE"

render_variant() {
  local input="$1" theme="$2" bgcolor="$3" output_format="$4"
  local input_path input_filename variant output_target output

  input_path=$(dirname "$input")
  input_filename=$(basename "$input")
  variant="${theme}_${bgcolor}_${output_format}"
  output_target="${OUTPUT_BASE}/${variant}/${input_path}/"
  output="${OUTPUT_BASE}/${variant}/${input_path}/${input_filename}"

  npx -p @mermaid-js/mermaid-cli mmdc \
    -i "${input}" \
    -a "${output_target}" \
    -o "${output}" \
    --scale 4 -e "${output_format}" -t "${theme}" -b "${bgcolor}"
}

for INPUT in "$@"; do
  echo "Rendering: ${INPUT}"
  render_variant "$INPUT" dark transparent png
  render_variant "$INPUT" default white png
done
