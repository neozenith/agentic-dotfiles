# Render Failure Triage

`mmdc` renders by driving a real Chromium. That makes rendering the only part
of this skill that can fail for reasons that have **nothing to do with your
diagram**. This file is the triage procedure: classify first, remedy the class,
re-render, verify the artifact. Bailing out with "rendering isn't available
here" is a last resort with a named cause — never the first response to a
non-zero exit.

## The four independent inputs

A render needs four things to be true at once. They fail independently and each
has its own fix; fixing one never fixes another.

| Input | What it supplies | Fails as |
|-------|------------------|----------|
| **Package cache** | `npx` unpacking `@mermaid-js/mermaid-cli` | `EPERM` / `EACCES` before Mermaid ever starts |
| **Browser executable** | a Chromium binary Puppeteer can spawn | "Could not find Chrome" / missing `chrome-headless-shell` |
| **Execution class** | OS permission for that binary to launch | macOS `bootstrap_check_in ... Permission denied (1100)` |
| **Diagram source** | valid Mermaid | `Parse error` / `UnknownDiagramError` |

**Only the fourth sends you back to edit the diagram.** The first rule of
triage is refusing to "fix" a syntax-clean diagram because the browser could
not start. A diagram that passed `mermaid_complexity.ts` has already been
through Mermaid's canonical parser — if that gate is green, a render failure is
almost certainly environmental.

## Signature → class → remedy

Match the **first** recognisable line in stderr, not the last.

| stderr signature | Class | Remedy |
|------------------|-------|--------|
| `npm ERR! ... EPERM`, `EACCES`, `Cannot read ... /_cacache` | `NPM_CACHE_PERMISSION` | Point `NPM_CONFIG_CACHE` at a task-local dir and retry. Never `sudo`, never `--unsafe-perm`. |
| `Could not find Chrome`, `chrome-headless-shell` not found, `Browser was not found at the configured executablePath` | `BROWSER_MISSING` | Resolve an already-installed Chromium and pass it via `PUPPETEER_EXECUTABLE_PATH`. If no browser exists anywhere, **unset** `PUPPETEER_SKIP_DOWNLOAD` and let Puppeteer fetch one. |
| `MachPortRendezvous`, `bootstrap_check_in`, `Permission denied (1100)`, `Operation not permitted` at spawn | `SANDBOX_DENIED` | The sandbox denied the browser a required OS facility. **Stop retrying locally** — re-run the render (only the render) in a browser-capable execution class. |
| `ENOTFOUND`, `ETIMEDOUT`, `getaddrinfo`, `registry.npmjs.org` unreachable | `NETWORK_UNREACHABLE` | No registry. Use an already-installed `mmdc`/browser, or declare the render blocked and ship the fences unrendered (GitHub/GitLab render them natively). |
| `Parse error`, `Syntax error in text`, `UnknownDiagramError`, `No diagram type detected` | `DIAGRAM_SYNTAX` | The only class that means *edit the diagram*. stderr names the offending fence. |

Anything unmatched is `UNKNOWN`: preserve the full stderr, report it verbatim,
and do **not** guess at a diagram edit.

### Two traps worth naming

- **`PUPPETEER_SKIP_DOWNLOAD=true` with an empty cache cannot work.** That
  variable only says "don't fetch"; it does not conjure a browser. Set it
  *only* alongside a `PUPPETEER_EXECUTABLE_PATH` that exists.
- **Pointing Puppeteer at a fresh empty cache directory** to "fix" discovery
  makes `BROWSER_MISSING` permanent. The renderer needs a usable executable,
  not a particular cache layout.

## What the script does for you

`scripts/render_mermaid.sh` implements the top of this ladder itself:

1. **Sense** — resolve a Chromium from, in order: `PUPPETEER_EXECUTABLE_PATH`
   (if it exists), Puppeteer's own cache, Playwright's `chrome-headless-shell`,
   Playwright's full Chromium, system Chrome / Chromium / Edge. Found ⇒ export
   the path and `PUPPETEER_SKIP_DOWNLOAD=true`. Not found ⇒ leave the download
   path open rather than pinning a broken one.
2. **Isolate** — put the `npx` package cache under the task workspace so a
   poisoned shared `~/.npm` cannot break the run.
3. **Render, capturing stderr** rather than letting it scroll away.
4. **Classify and self-rectify** — on `NPM_CACHE_PERMISSION` it rebuilds a
   clean task-local cache and retries once; on `BROWSER_MISSING` it retries
   once with download permitted. Each remedy is applied at most once, so a
   genuinely broken environment fails fast instead of looping.
5. **Verify the artifact** — see below.
6. **Report** — on unrecoverable failure it prints the class, the evidence line
   from stderr, and the remedy, then exits non-zero. It never reports success it
   did not verify.

Run it in probe-only mode to see what the current host offers before you
commit to a render:

```bash
bash .claude/skills/mermaidjs-diagrams/scripts/render_mermaid.sh --doctor
```

## Exit 0 is not proof of an image

A passing parser, complexity gate, or contrast gate proves nothing about
whether Chromium started. Even `mmdc` exiting 0 is weaker evidence than the
file itself. Verification is: the expected PNG exists, starts with the PNG
magic bytes, and its IHDR reports non-zero width and height. The script does
this automatically and fails the run when the check fails — but when you drive
`mmdc` by hand, do it yourself:

```bash
f=".mmdc_cache/dark_transparent_png/path/to/doc-1.png"
[ -s "$f" ] && file "$f"       # must say: PNG image data, W x H
```

When layout or legibility is the point of the render, go one step further and
actually look at the image with the `Read` tool. Dimensions prove a browser
ran; they do not prove the diagram is readable.

## Manual escalation, per class

```bash
# NPM_CACHE_PERMISSION — task-local cache, nothing shared
export NPM_CONFIG_CACHE="$PWD/tmp/.mmdc_cache/npm"
mkdir -p "$NPM_CONFIG_CACHE"

# BROWSER_MISSING — reuse a browser some other tool already installed
export PUPPETEER_EXECUTABLE_PATH="$(bash scripts/render_mermaid.sh --doctor | awk '/^browser:/{print $2}')"
export PUPPETEER_SKIP_DOWNLOAD=true
# ...or, if genuinely none exists and the registry is reachable:
unset PUPPETEER_SKIP_DOWNLOAD          # let Puppeteer fetch its own

# SANDBOX_DENIED — re-run ONLY the render in a browser-capable class.
# The gates below need no such permission; keep them in the restricted class.
bun run scripts/mermaid_complexity.ts doc.md
bun run scripts/mermaid_contrast.ts   doc.md
```

Any browser you resolve is a candidate, not a contract. Prove it with one real
Mermaid render before treating it as available — a binary that exists can still
be the wrong architecture or be denied at launch.

## When to stop

Stop and tell the user, naming the class and the evidence, when:

- the class is `SANDBOX_DENIED` and you cannot reach a browser-capable
  execution class — retrying the same launch only repeats the crash (on macOS
  it also spawns crash dialogs);
- the class is `NETWORK_UNREACHABLE` with no local `mmdc` or browser;
- a remedy has already been applied once and the same class recurs.

Say what is blocked and what is unaffected. Diagram *authoring* survives every
one of these failures: the complexity and contrast gates run without a browser,
and GitHub/GitLab render ` ```mermaid ` fences natively — PNGs are only needed
for PDFs, slides, and non-Mermaid viewers. Degrading the *artifact* to
unrendered fences with a named reason is honest; degrading the *diagram* to
dodge an environmental error is not.

## Field evidence (macOS, 2026-08)

Observed on a restricted macOS workspace, in this order — each fix exposed the
next failure, which is why they must be treated as separate inputs:

1. `npx` hit `EPERM` on the shared user npm cache before Mermaid started.
2. With a task-local cache, Puppeteer reported its `chrome-headless-shell`
   missing; `PUPPETEER_SKIP_DOWNLOAD=true` against an empty cache could not
   resolve it.
3. With a browser supplied, Chromium died on `MachPortRendezvous` /
   `bootstrap_check_in ... Permission denied (1100)` — the sandbox denying a
   macOS port registration. Only a different execution class fixed it.
4. Throughout, the document passed both the complexity and contrast gates. The
   diagram was never the problem.

The successful run reused Playwright's already-installed
`chrome-headless-shell` via `PUPPETEER_EXECUTABLE_PATH` and rendered both dark
and light variants to valid PNGs. That verifies the integration on that host,
on that day — it is not a promise about any other browser or host.
