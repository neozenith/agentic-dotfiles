#!/bin/bash
# Render Mermaid.js diagrams embedded in markdown files via mermaid-cli (mmdc).
#
# Usage: ./render_mermaid.sh path/to/diagram.md [more files...]
#        ./render_mermaid.sh docs/**/*.md
#        ./render_mermaid.sh --doctor            # probe the host, render nothing
#        ./render_mermaid.sh --verify out/*.png  # is this a decodable PNG?
#        ./render_mermaid.sh --classify < stderr.txt
#
# Rendering drives a real Chromium, so it can fail for reasons unrelated to the
# diagram. This script senses the environment, classifies failures, applies the
# mechanical remedy for the classes that have one, and verifies that a real PNG
# was written. Full triage procedure: ../resources/render_troubleshooting.md

set -euo pipefail

OUTPUT_BASE=".mmdc_cache"
# Resolved from this script's own location so the pointer is a real, openable
# path whether the skill is used in place or vendored into another skill.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TROUBLESHOOTING="${SCRIPT_DIR%/scripts}/resources/render_troubleshooting.md"

# ── Environment sensing ────────────────────────────────────────────────────

# Keep temporary npm packages inside the task workspace. `npx` otherwise writes
# to the shared user npm cache, which can be owned by another process and fail
# with EPERM before Mermaid starts. This does not choose or download a browser.
MERMAID_RUNTIME_DIR="${MERMAID_RUNTIME_DIR:-$PWD/tmp/.mmdc_cache}"
export MERMAID_RUNTIME_DIR
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-$MERMAID_RUNTIME_DIR/npm}"

# Resolve a Chromium that is ALREADY installed. Puppeteer's own cache first
# (it needs no override), then browsers other tools installed, then the system.
# Returns empty when nothing is found — the caller must then leave Puppeteer's
# download path open rather than pinning it to a browser that does not exist.
resolve_browser() {
  local candidate

  if [ -n "${PUPPETEER_EXECUTABLE_PATH:-}" ] && [ -x "${PUPPETEER_EXECUTABLE_PATH}" ]; then
    printf '%s' "${PUPPETEER_EXECUTABLE_PATH}"
    return 0
  fi

  local -a roots=(
    "${PUPPETEER_CACHE_DIR:-$HOME/.cache/puppeteer}"
    "${PLAYWRIGHT_BROWSERS_PATH:-$HOME/Library/Caches/ms-playwright}"
    "$HOME/.cache/ms-playwright"
  )
  local -a names=(chrome-headless-shell chrome chromium "Google Chrome for Testing")

  local root name
  for root in "${roots[@]}"; do
    [ -d "$root" ] || continue
    for name in "${names[@]}"; do
      # -perm -111: an executable file, not the directory of the same name.
      candidate=$(find "$root" -maxdepth 4 -type f -perm -111 -name "$name" 2>/dev/null | sort | tail -n 1)
      if [ -n "$candidate" ]; then
        printf '%s' "$candidate"
        return 0
      fi
    done
  done

  local -a system=(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    "/Applications/Chromium.app/Contents/MacOS/Chromium"
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
  )
  for candidate in "${system[@]}"; do
    [ -x "$candidate" ] && { printf '%s' "$candidate"; return 0; }
  done
  for name in chromium chromium-browser google-chrome google-chrome-stable; do
    candidate=$(command -v "$name" 2>/dev/null || true)
    [ -n "$candidate" ] && { printf '%s' "$candidate"; return 0; }
  done

  return 0  # nothing found; empty output is the signal
}

# ── Failure classification ─────────────────────────────────────────────────

# Map raw stderr to a failure class. Order matters: the earliest-failing input
# wins, because a run that never unpacked mmdc cannot also have a browser bug.
classify_failure() {
  local text="$1"
  case "$text" in
    *EPERM*|*EACCES*|*_cacache*|*"operation not permitted, mkdir"*)
      printf 'NPM_CACHE_PERMISSION' ;;
    *ENOTFOUND*|*ETIMEDOUT*|*EAI_AGAIN*|*getaddrinfo*|*"network is unreachable"*)
      printf 'NETWORK_UNREACHABLE' ;;
    *"Could not find Chrome"*|*"Could not find browser"*|*"chrome-headless-shell"*|\
    *"Browser was not found"*|*"executablePath"*|*"Failed to launch the browser process"*)
      printf 'BROWSER_MISSING' ;;
    *MachPortRendezvous*|*bootstrap_check_in*|*"Permission denied (1100)"*|*"Operation not permitted"*)
      printf 'SANDBOX_DENIED' ;;
    *"Parse error"*|*"Syntax error in text"*|*UnknownDiagramError*|*"No diagram type detected"*)
      printf 'DIAGRAM_SYNTAX' ;;
    *)
      printf 'UNKNOWN' ;;
  esac
}

remedy_for() {
  case "$1" in
    NPM_CACHE_PERMISSION)
      printf 'Package cache is unusable. Retrying with a clean task-local NPM_CONFIG_CACHE. Never sudo.' ;;
    BROWSER_MISSING)
      printf 'No usable Chromium was resolved. Retrying with Puppeteer allowed to download its own.' ;;
    SANDBOX_DENIED)
      printf 'The sandbox denied Chromium an OS facility it needs. Do NOT retry here — re-run ONLY the render in a browser-capable execution class. The complexity and contrast gates still run fine in this class.' ;;
    NETWORK_UNREACHABLE)
      printf 'No package registry. Use a preinstalled mmdc/browser, or ship the mermaid fences unrendered (GitHub/GitLab render them natively).' ;;
    DIAGRAM_SYNTAX)
      printf 'This one IS the diagram: stderr names the offending fence. Fix the Mermaid source and re-run.' ;;
    *)
      printf 'Unrecognised failure. Report the stderr above verbatim; do not guess at a diagram edit.' ;;
  esac
}

report_failure() {
  local class="$1" evidence="$2"
  {
    printf '\n[render-failure] class=%s\n' "$class"
    printf '  evidence: %s\n' "$evidence"
    printf '  remedy:   %s\n' "$(remedy_for "$class")"
    printf '  triage:   %s\n' "$TROUBLESHOOTING"
  } >&2
}

# First stderr line that carries a recognisable signature — the useful one to
# quote, which is rarely the last line of a Chromium stack dump.
evidence_line() {
  printf '%s\n' "$1" | grep -m1 -E \
    'EPERM|EACCES|ENOTFOUND|ETIMEDOUT|getaddrinfo|Could not find|chrome-headless-shell|Failed to launch|MachPortRendezvous|bootstrap_check_in|Permission denied|Parse error|Syntax error|UnknownDiagramError' \
    || printf '%s' "$(printf '%s\n' "$1" | tail -n 1)"
}

# ── Artifact verification ──────────────────────────────────────────────────

# A zero exit from mmdc is not proof that Chromium started. Require the PNG
# magic bytes and a non-zero width/height in the IHDR chunk (bytes 16..23).
verify_png() {
  local f="$1" header dims w h
  [ -s "$f" ] || return 1
  header=$(od -An -tx1 -N8 "$f" | tr -d ' \n')
  [ "$header" = "89504e470d0a1a0a" ] || return 1
  # IHDR width/height are big-endian; compose them byte-by-byte rather than
  # trusting `od -tu4`, which decodes in host byte order.
  dims=$(od -An -tu1 -j16 -N8 "$f")
  # shellcheck disable=SC2086
  set -- $dims
  [ $# -eq 8 ] || return 1
  w=$(( ($1 << 24) | ($2 << 16) | ($3 << 8) | $4 ))
  h=$(( ($5 << 24) | ($6 << 16) | ($7 << 8) | $8 ))
  [ "$w" -gt 0 ] && [ "$h" -gt 0 ]
}

verify_output_dir() {
  local dir="$1" stem="$2" found=0 bad=0 f
  for f in "$dir/$stem"-*.png; do
    [ -e "$f" ] || continue
    found=$((found + 1))
    if verify_png "$f"; then
      echo "  verified: $f"
    else
      echo "  CORRUPT:  $f (not a decodable PNG with non-zero dimensions)" >&2
      bad=$((bad + 1))
    fi
  done
  if [ "$found" -eq 0 ]; then
    echo "  NO ARTIFACT: mmdc exited 0 but wrote no PNG under $dir" >&2
    return 1
  fi
  [ "$bad" -eq 0 ]
}

# ── Rendering ──────────────────────────────────────────────────────────────

run_mmdc() {
  local input="$1" output_target="$2" output="$3" theme="$4" bgcolor="$5" fmt="$6"
  npx -p @mermaid-js/mermaid-cli mmdc \
    -i "${input}" \
    -a "${output_target}" \
    -o "${output}" \
    --scale 4 -e "${fmt}" -t "${theme}" -b "${bgcolor}"
}

# Render one variant, self-rectifying once per remediable failure class.
render_variant() {
  local input="$1" theme="$2" bgcolor="$3" fmt="$4"
  local input_path input_filename stem variant output_target output
  local attempt=0 err="" status=0 class="" applied=""

  input_path=$(dirname "$input")
  input_filename=$(basename "$input")
  stem="${input_filename%.*}"
  variant="${theme}_${bgcolor}_${fmt}"
  output_target="${OUTPUT_BASE}/${variant}/${input_path}/"
  output="${OUTPUT_BASE}/${variant}/${input_path}/${input_filename}"
  mkdir -p "$output_target"

  while [ "$attempt" -lt 3 ]; do
    attempt=$((attempt + 1))
    status=0
    err=$(run_mmdc "$input" "$output_target" "$output" "$theme" "$bgcolor" "$fmt" 2>&1 >/dev/null) || status=$?

    if [ "$status" -eq 0 ]; then
      verify_output_dir "$output_target" "$stem" && return 0
      report_failure UNKNOWN "mmdc exited 0 but the artifact check failed"
      return 1
    fi

    class=$(classify_failure "$err")
    printf '%s\n' "$err" >&2

    # Each remedy is applied at most once: a broken host fails fast, it doesn't loop.
    case "$class" in
      NPM_CACHE_PERMISSION)
        case "$applied" in *NPM*) break ;; esac
        applied="${applied}NPM "
        echo "[self-rectify] $(remedy_for "$class")" >&2
        NPM_CONFIG_CACHE="$MERMAID_RUNTIME_DIR/npm-retry"
        export NPM_CONFIG_CACHE
        rm -rf "$NPM_CONFIG_CACHE" && mkdir -p "$NPM_CONFIG_CACHE"
        ;;
      BROWSER_MISSING)
        case "$applied" in *BROWSER*) break ;; esac
        applied="${applied}BROWSER "
        echo "[self-rectify] $(remedy_for "$class")" >&2
        unset PUPPETEER_EXECUTABLE_PATH PUPPETEER_SKIP_DOWNLOAD || true
        ;;
      *)
        break ;;
    esac
  done

  report_failure "$class" "$(evidence_line "$err")"
  return 1
}

# ── CLI ────────────────────────────────────────────────────────────────────

doctor() {
  local exe
  exe=$(resolve_browser)
  echo "npm_cache: $NPM_CONFIG_CACHE"
  if [ -n "$exe" ]; then
    echo "browser: $exe"
    echo "tier: A (render available — prove it with one real render before trusting it)"
  else
    echo "browser: <none resolved>"
    echo "tier: B (no local Chromium; mmdc must download one, which needs registry access)"
  fi
  command -v npx >/dev/null && echo "npx: $(command -v npx)" || echo "npx: <missing> — rendering is unavailable"
  echo "triage: $TROUBLESHOOTING"
}

verify_cmd() {
  local status=0 f
  for f in "$@"; do
    if verify_png "$f"; then
      echo "ok: $f"
    else
      echo "BAD: $f (not a decodable PNG with non-zero dimensions)" >&2
      status=1
    fi
  done
  return "$status"
}

case "${1:-}" in
  --doctor) doctor; exit 0 ;;
  --classify) classify_failure "$(cat)"; echo; exit 0 ;;
  --verify) shift; verify_cmd "$@"; exit $? ;;
  "" ) echo "Usage: $0 [--doctor|--classify|--verify FILE...] <file.md> [file2.md ...]" >&2; exit 1 ;;
esac

mkdir -p "$NPM_CONFIG_CACHE"

# Adopt the resolved browser in THIS shell (a command substitution would export
# into a subshell only). Skip the download solely when we actually have one:
# PUPPETEER_SKIP_DOWNLOAD against an empty cache makes BROWSER_MISSING permanent.
BROWSER=$(resolve_browser)
if [ -n "$BROWSER" ]; then
  export PUPPETEER_EXECUTABLE_PATH="$BROWSER"
  export PUPPETEER_SKIP_DOWNLOAD=true
  echo "Browser: $BROWSER"
else
  unset PUPPETEER_EXECUTABLE_PATH PUPPETEER_SKIP_DOWNLOAD
  echo "Browser: none preinstalled — letting Puppeteer fetch its own (needs registry access)"
fi

FAILED=0
for INPUT in "$@"; do
  echo "Rendering: ${INPUT}"
  render_variant "$INPUT" dark transparent png || FAILED=1
  render_variant "$INPUT" default white png || FAILED=1
done
exit "$FAILED"
