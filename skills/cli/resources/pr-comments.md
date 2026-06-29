# PR comment automation + embedding CI-run artifacts

Part of the **cli** skill ([SKILL.md](../SKILL.md)). Two related patterns: **upsert a
sticky PR comment** (idempotent — edit in place, don't pile up duplicates), and **embed
an image rendered during a CI run** inline in that comment without committing it to the
repo. Builds on [cli-foundations.md](cli-foundations.md).

## Sticky comment upsert via a hidden marker

The trick is a **unique hidden HTML comment** as an anchor. To update, find the existing
comment whose body contains the marker and `PATCH` it; otherwise `POST` a new one. One
marker per logical target (per PR, per stack, per check) so updates don't collide.

```python
MARK = f"<!-- tool:{key} -->"          # unique per logical target
def upsert_pr_comment(repo, pr, body, token):
    full = f"{MARK}\n{body}"
    ids = _gh("api", f"repos/{repo}/issues/{pr}/comments", "--paginate",
              "--jq", f'.[] | select(.body | contains("{MARK}")) | .id', token=token).split()
    if ids:
        _gh("api", "-X", "PATCH", f"repos/{repo}/issues/comments/{ids[0]}",
            "-f", f"body={full}", token=token)
    else:
        _gh("api", f"repos/{repo}/issues/{pr}/comments", "-f", f"body={full}", token=token)
```

- **Resolve the PR number fail-loud** from an explicit env var, else parse `GITHUB_REF`
  (`refs/pull/<n>/merge`); never guess.
- **Keep the `gh`/network calls at a thin seam** and unit-test the pure parts (marker
  build, body render, PR-number parse) separately — mark the IO seam `# pragma: no cover`.
- **The same marker-upsert works for a committed file region**, not just a PR comment:
  `<!-- tool:start -->` … `<!-- tool:end -->` around an auto-generated block in a README,
  replaced in place on regen. (The diagram drift gate in
  [svg-diagrams.md](svg-diagrams.md) reuses this.)
- Auth is keyless in CI: a `GITHUB_TOKEN` with `pull-requests: write`. For multiple
  sticky comments (e.g. a changed-set matrix + an all-set matrix), use a distinct marker
  per comment and delete retired markers.

## Embed a CI-rendered image in the comment (no `ci-images` branch)

To show a diagram/chart that was rendered *during* the workflow, you don't commit it.
Let GitHub's own `actions/upload-artifact` store it, then resolve a directly-embeddable
URL and reference it as `![alt](url)` in the sticky comment — GitHub's image proxy
fetches and caches the bytes.

The chain:

1. **Upload the image un-archived** in the workflow: `actions/upload-artifact` with
   **`archive: false`** (so the stored blob is the raw image, not a zip), and capture its
   `artifact-id` output.
2. **Resolve the blob URL headers-only.** The artifacts `…/zip` endpoint 302-redirects to
   a short-lived signed blob URL. Read the `Location:` header **without** downloading the
   body. Because the upload was un-archived, that URL serves the raw image inline.

```python
def resolve_artifact_url(repo, artifact_id, token):
    hdrs = subprocess.run(
        ["curl", "-sS", "-D", "-", "-o", "/dev/null",
         "-H", f"Authorization: Bearer {token}",
         f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip"],
        capture_output=True, text=True, check=True).stdout
    for line in hdrs.splitlines():
        if line.lower().startswith("location:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("no redirect Location — was the artifact uploaded with archive:false?")
```

3. **Embed the resolved URL** in the comment body and upsert it:

```python
url  = resolve_artifact_url(repo, artifact_id, token)
body = f"### Architecture\n\n![diagram]({url})\n\n_Signed URL expires; re-run the workflow to refresh._"
upsert_pr_comment(repo, pr, body, token)
```

## Split the render and the comment steps

Make "render the image" and "post the comment" **separate subcommands**. The render step
needs the heavy deps (cloud creds, the rasterizer); the comment step needs only
`GITHUB_TOKEN` + the `artifact-id`. Splitting them means the comment job stays tiny and
the workflow can upload between the two:

```
job: render   →  tool diagram        →  actions/upload-artifact (archive:false) → artifact-id
job: comment  →  tool diagram-comment --artifact-id <id>   (only gh token needed)
```

## Pitfalls

- **`archive: false` is mandatory** — without it the redirect points at a `.zip`, not a
  renderable image; the resolver raises if no `Location` is found.
- **Read the redirect, don't follow it.** `curl -D - -o /dev/null` reads headers only; a
  full download wastes bandwidth and you don't need the bytes.
- **The signed URL is short-lived.** Put a "re-run to refresh" note in the comment so a
  stale image later isn't a mystery.
- **Marker must be unique per target** — a shared marker makes two checks fight over one
  comment, each overwriting the other.
- **Token scopes:** `pull-requests: write` to comment, `actions: read` to resolve the
  artifact URL.
- **Fail loud on a missing PR number / token** — a "skip if not on a PR" path silently
  hides a broken CI wiring; raise with a clear message instead.
