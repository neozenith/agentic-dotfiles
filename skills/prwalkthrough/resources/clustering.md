# Git-Only Diff Clustering Algorithm

Collapses a huge diff into mechanical-change clusters vs novel changes using
nothing but git + standard shell. The core primitive is `git patch-id` — a hash
of a patch that ignores whitespace and line numbers, designed so "two patches
with the same patch ID are almost guaranteed to be the same thing."

Run all commands from the repo root. `$MERGE_BASE` below:

```sh
MERGE_BASE=$(git merge-base origin/<default-branch> HEAD)
```

## Phase 0 — Baseline

```sh
git diff --shortstat $MERGE_BASE..HEAD          # headline numbers
git diff --dirstat=files,0 $MERGE_BASE..HEAD    # which directories absorbed it
git diff -M -C --summary $MERGE_BASE..HEAD      # renames/copies (similarity %)
```

Pure renames (`similarity 100%`) collapse to one bullet. `-M90%` surfaces
"moved AND edited" files — only the edit needs review.

## Phase 1 — Triage noise

```sh
git diff --name-only $MERGE_BASE..HEAD | grep -E \
  '(\.lock$|lock\b|package-lock|bun\.lock|uv\.lock|Cargo\.lock|go\.sum|\.snap$|\.min\.|_pb2?\.|\.generated\.|/dist/|/vendor/|/node_modules/)'
# Honor the repo's own declaration:
git diff --name-only $MERGE_BASE..HEAD | xargs git check-attr linguist-generated -- | grep ': set'
```

Path heuristics can misclassify — confirm by sampling the diff of heuristic
matches before suppressing them. `check-attr` results need no sampling.

## Phase 2 — Distribution analysis (codemod shape detection)

```sh
git diff --numstat $MERGE_BASE..HEAD | sort -n
```

A mechanical sweep's signature: a large mass of files with small, near-constant
churn (300 files at +2/−2) vs a head of few files with large idiosyncratic
churn. Churn outliers within an otherwise-uniform mass are novel-change
candidates before any content analysis.

## Phase 3 — Normalized hunk fingerprinting (the core step)

**Strict tier — identical changes:**

```sh
for f in $(git diff --name-only $MERGE_BASE..HEAD); do
  printf '%s ' "$f"
  git diff $MERGE_BASE..HEAD -- "$f" | git patch-id --stable | cut -d' ' -f1
done | sort -k2
```

Identical patch-ids ⇒ byte-identical change (modulo whitespace/position) —
instant cluster (license headers, identical import swaps).

**Loose tier — similar-but-not-identical (template-instantiated) changes:**

```sh
git diff -U0 --ignore-all-space $MERGE_BASE..HEAD -- "$f" \
  | grep -E '^[+-]' | grep -vE '^(\+\+\+|---)' \
  | sed -E 's/[A-Za-z_][A-Za-z0-9_]*/ID/g; s/[0-9]+/N/g; s/"[^"]*"/S/g' \
  | shasum
```

This collapses `import { Foo } from "a"` → `import { Bar } from "b"` into one
shape class. Cluster on the loose hash; describe the cluster from the most
common +/− line pair (the template). Useful flags: `-U0` (hash only the edit,
not context), `--word-diff=porcelain` (a rename sweep's word-diff is literally
`-OldName +NewName` in every file).

**Two-tier rule against over-merging:** if a loose cluster contains >2 strict
sub-clusters, present sub-clusters separately or show one exemplar per
sub-cluster — aggressive normalization can merge semantically different edits
that share a token shape.

## Phase 4 — Secondary axes

- **Commits as seeds:** `git log --oneline --numstat $MERGE_BASE..HEAD` — a
  commit touching 400 files with uniform churn is self-labeled mechanical. But
  11-40% of commits are tangled: seeds only, content hashing decides.
- **Directory/extension grouping** catches "same migration applied per-language."

## Phase 5 — Deviant detection (the needle in the codemod)

For EVERY member of every cluster — never a sample:

1. **Ordered token-sequence check:** `git diff -U0 --word-diff=porcelain $MERGE_BASE..HEAD -- "$f"`
   — its changed-token *sequence* must match the cluster template position by
   position, with one consistent identifier mapping across the whole hunk
   (a bijection: template slot `ID1` always maps to the same concrete name).
   Never compare token *sets/bags* — a bag check is order-blind and passes
   argument swaps (`f(x, y)` → `f(y, x)`) and operand flips (`a - b` →
   `b - a`). Operators, punctuation, and keywords are compared verbatim
   (they are never normalized in Phase 3 either). Any mismatch or mapping
   violation ⇒ eject to novel set.
2. **Hunk-count check:** a file with 3 hunks in a 1-hunk-per-file cluster is
   suspect (codemod ran, plus someone hand-edited).
3. **Churn-outlier check** within the cluster.
4. **Whitespace-sweep mask:** in a "formatting" cluster, any file whose
   `git diff -w` is non-empty got a real edit too — deviant.
5. **Re-apply-and-diff oracle (strongest, when feasible):** regenerate the
   mechanical change on the base revision in a scratch worktree (run the
   formatter / apply the rename), then diff against the PR head. Any residue is
   exactly the non-mechanical content.

## Phase 6 — Output contract

Return: (a) k mechanical clusters — template, file count, total LOC waved
through, one exemplar hunk, the most dissimilar member, deviant list, and a
`shape-checked` / `sampled` label (shape-checked = ordered token-level
equivalence only; semantics, cross-hunk ordering, and cross-file interactions
are NOT verified — state this scope wherever the label appears); (b) the
novel set (residuals + ejected deviants) ranked by risk (security-sensitive
paths first), then churn × centrality; (c) the noise set with counts.

Known residual false-merge class even with the ordered check: a *consistent*
rename that changes semantics across the whole hunk (e.g. every `timeout_ms`
slot systematically swapped with every `retries` slot) maps bijectively and
passes. Cross-hunk and cross-file interactions are out of scope by
construction. This is why the label is `shape-checked`, not `verified`.
