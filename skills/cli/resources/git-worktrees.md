# Git worktrees — act on another branch/ref safely

Part of the **cli** skill ([SKILL.md](../SKILL.md)). When a command must build an
artifact *from a different git ref* — a baseline to diff against, the state of `main`,
a deferred comparison — without disturbing the working tree or doing a destructive
`git checkout`. Builds on [cli-foundations.md](cli-foundations.md).

## The pattern

Check the ref out into a **throwaway detached worktree**, operate inside it, and remove
it in a `finally`. Cache the result keyed on the **resolved commit sha**, so a moving
branch re-keys when it advances while a fixed tag/sha reuses the cache forever.

```python
import shutil
def run_git(args, *, cwd):
    p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if p.returncode: raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout

def resolve_sha(ref, *, cwd):                 # branch/tag/sha → full commit sha (the cache key)
    return run_git(["rev-parse", f"{ref}^{{commit}}"], cwd=cwd).strip()

def with_ref_worktree(ref, root, build):      # build(worktree_path, out_dir) -> artifact dir
    sha = resolve_sha(ref, cwd=root)
    out = root / "tmp" / "cache" / sha        # project-local tmp, keyed on sha (± target)
    if (out / "done").exists():
        return out                            # cache hit — fixed sha reuses; moving branch re-keyed
    wt = root / "tmp" / "_wt" / sha
    if wt.exists():
        run_git(["worktree", "remove", "--force", str(wt)], cwd=root)   # clear a stale one first
    wt.parent.mkdir(parents=True, exist_ok=True)
    run_git(["worktree", "add", "--detach", str(wt), sha], cwd=root)
    try:
        out.mkdir(parents=True, exist_ok=True)
        build(wt, out)                        # operate INSIDE the worktree
        (out / "done").write_text("")
        return out
    finally:
        try: run_git(["worktree", "remove", "--force", str(wt)], cwd=root)
        except RuntimeError:                  # git refused → manual cleanup
            shutil.rmtree(wt, ignore_errors=True); run_git(["worktree", "prune"], cwd=root)
```

## Why each piece

- **Key on the resolved sha, not the ref string.** `main` moves; keying on the ref would
  serve a stale artifact after it advances. Resolving to the commit makes the cache
  self-invalidating. If the build is parameterised (e.g. a target/profile that changes
  the output), key on `(sha, param)`.
- **The `try/finally` is load-bearing.** An orphaned worktree wedges the next
  `git worktree add` for the same path. Always remove in `finally`, with a
  `rmtree + worktree prune` fallback for when `git worktree remove` refuses.
- **Isolate dependencies inside the worktree.** If the operation needs the ref's *own*
  installed deps (lockfile/packages can differ per commit), install them **in the
  worktree** — never symlink the working tree's, or a wrong dependency graph silently
  distorts the result.
- **`tmp/` is project-local**, never the system `/tmp` — auditable and `git clean`-able.

## Driving from a CLI handler

The same mechanism underlies a `…-state` command that prints the resolved cache dir for
CI to consume (`STATE=$(tool build-state --ref main)`) and a `…-diff` command that builds
the baseline, then diffs the current tree against it. Both call `with_ref_worktree`; the
former prints `out` to **stdout only** (see [cli-foundations.md](cli-foundations.md)
§output-discipline), the latter renders a diff to stderr.

## Worktrees for *your own* cross-branch work

The same primitive is the safe way to do work on a second branch while another is checked
out (e.g. build/verify a change on a feature branch without stashing your current one):

```bash
git worktree add -b feat/x ../proj-feat-x main   # new branch in a sibling dir
# … work + commit + push from ../proj-feat-x …
git worktree remove --force ../proj-feat-x        # run from the PRIMARY worktree
git branch -D feat/x                              # if it was squash-merged
```

## Pitfalls

- **`git worktree remove` / `--delete-branch` run from the *primary* worktree.** Trying to
  delete a branch that is checked out in another worktree errors (`cannot delete branch
  … checked out at …`) — switch to the primary worktree first, or remove the worktree
  before the branch. (This also bites `gh pr merge --delete-branch` when the head branch
  lives in a worktree; the server-side merge still succeeds — clean up the worktree by
  hand.)
- **Orphan worktrees** from a crashed run block re-adds; `git worktree prune` clears the
  registry, then `rmtree` the dir.
- **A worktree shares the repo's object store** but has its own HEAD/index — cheap to
  create, but don't point two worktrees at the same branch (git refuses).
