# GitHub Issues as Gap Analysis Documents

Reference for using GitHub issues as the storage backend for gap analysis documents.
Covers argument parsing, local cache for iteration and Mermaid rendering, the
sync-back protocol with changelog comments, and edit history lineage.

The **document body specification** (six sections, per-gap fields, skeleton template)
lives in `spec-body.md` — this file covers only the GitHub-specific mechanics.

## Argument Parsing

| Argument pattern | Target type | Action |
|------------------|-------------|--------|
| `owner/repo#N` | Existing issue | Read and continue refining |
| `https://github.com/owner/repo/issues/N` | Existing issue | Extract owner/repo/N, read and continue |
| `owner/repo` (no `#N`) | New issue on repo | Ask user for title, create issue |
| `path/to/file.md` | Local markdown file | Existing behavior |
| `path/to/directory/` | New local file | Existing behavior |

## Issue ↔ Document Mapping

The issue **title** serves as the `# [Title]` heading — do not duplicate it in the body.
The issue **body** contains the six sections defined in `spec-body.md`.

### What lives where

| Content | Location | Why |
|---------|----------|-----|
| Document title | Issue title | GitHub renders it as the H1 |
| Six sections (Overview through Negative Measures) | Issue body | Single editable document |
| Refinement Q&A (Phase 2 questions and answers) | Issue comments | Append-only audit trail |
| Sync changelog summaries | Issue comments | Traceability for each body edit |
| Verification markers (`PAYWALLED`, `LINK_NOT_VERIFIED`) | Issue body (HTML comments) | Hidden in rendered view, visible in raw |
| Labels (e.g., `enhancement`, `documentation`) | Issue labels | Optional — for repo-level triage |

## Local Cache

All iteration on a GitHub issue happens through a **local markdown file** that mirrors
the issue body. This gives the full benefits of local tooling: Edit tool diffs, mmdc
Mermaid rendering, and fast iteration without API round-trips per keystroke.

### Cache path

```
.mmdc_cache/gh_issues/{owner}/{repo}/{issue_number}/{normalised_title}.md
```

**Title normalisation:** lowercase, replace non-alphanumeric characters with `-`,
collapse runs of `-`, strip leading/trailing `-`.

Example: issue #42 titled "Gap Analysis: Migrate Auth to OAuth2" on `acme/backend`:

```
.mmdc_cache/gh_issues/acme/backend/42/gap-analysis-migrate-auth-to-oauth2.md
```

### Pull: GitHub → local cache

```bash
OWNER="acme"
REPO="backend"
ISSUE=42

# Read title and body
TITLE=$(gh issue view $ISSUE --repo $OWNER/$REPO --json title --jq '.title')
NORM_TITLE=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')

LOCAL_DIR=".mmdc_cache/gh_issues/${OWNER}/${REPO}/${ISSUE}"
LOCAL_FILE="${LOCAL_DIR}/${NORM_TITLE}.md"
mkdir -p "$LOCAL_DIR"

gh issue view $ISSUE --repo $OWNER/$REPO --json body --jq '.body' > "$LOCAL_FILE"
```

After pulling, use the Read and Edit tools on `$LOCAL_FILE` for all local iteration.

### Mermaid rendering

The mmdc INPUT uses the path relative to `.mmdc_cache/`, so the variant output
structure mirrors the issue's org/repo/number hierarchy:

```bash
INPUT="gh_issues/${OWNER}/${REPO}/${ISSUE}/${NORM_TITLE}.md"
INPUT_FILE=".mmdc_cache/${INPUT}"
INPUT_PATH="gh_issues/${OWNER}/${REPO}/${ISSUE}/"
OUTPUT_BASE=".mmdc_cache"

# Dark variant
VARIANT="dark_transparent_png"
OUTPUT_TARGET="${OUTPUT_BASE}/${VARIANT}/${INPUT_PATH}"
OUTPUT="${OUTPUT_BASE}/${VARIANT}/${INPUT}"
mkdir -p "$OUTPUT_TARGET"
npx -p @mermaid-js/mermaid-cli mmdc \
  -i "${INPUT_FILE}" -a "${OUTPUT_TARGET}" -o "${OUTPUT}" \
  --scale 4 -e png -t dark -b transparent

# Light variant
VARIANT="default_white_png"
OUTPUT_TARGET="${OUTPUT_BASE}/${VARIANT}/${INPUT_PATH}"
OUTPUT="${OUTPUT_BASE}/${VARIANT}/${INPUT}"
mkdir -p "$OUTPUT_TARGET"
npx -p @mermaid-js/mermaid-cli mmdc \
  -i "${INPUT_FILE}" -a "${OUTPUT_TARGET}" -o "${OUTPUT}" \
  --scale 4 -e png -t default -b white
```

**Resulting file tree:**

```
.mmdc_cache/
├── gh_issues/acme/backend/42/
│   └── gap-analysis-migrate-auth-to-oauth2.md          ← local working copy
├── dark_transparent_png/gh_issues/acme/backend/42/
│   ├── gap-analysis-migrate-auth-to-oauth2-1.png       ← diagram 1 (dark)
│   ├── gap-analysis-migrate-auth-to-oauth2-2.png       ← diagram 2 (dark)
│   └── ...
└── default_white_png/gh_issues/acme/backend/42/
    ├── gap-analysis-migrate-auth-to-oauth2-1.png       ← diagram 1 (light)
    ├── gap-analysis-migrate-auth-to-oauth2-2.png       ← diagram 2 (light)
    └── ...
```

## Push: Local Cache → GitHub (Sync Protocol)

After local edits are complete and diagrams validate, sync the body back to the issue
with a changelog comment for traceability.

### Step 1: Push the body

```bash
UPDATED_BODY=$(cat "$LOCAL_FILE")
gh issue edit $ISSUE --repo $OWNER/$REPO --body "$UPDATED_BODY"
```

### Step 2: Query edit history for lineage

The GitHub GraphQL API exposes full edit history via `userContentEdits`:

```bash
EDIT_INFO=$(gh api graphql -f query="
{ repository(owner: \"$OWNER\", name: \"$REPO\") {
    issue(number: $ISSUE) {
      userContentEdits(first: 1) {
        nodes { id editedAt editor { login } }
      }
    }
  }
}" --jq '.data.repository.issue.userContentEdits.nodes[0]')

EDIT_AT=$(echo "$EDIT_INFO" | jq -r '.editedAt')
EDIT_ID=$(echo "$EDIT_INFO" | jq -r '.id')
```

**Note:** There is no direct URL to a specific edit in GitHub's UI. The edit history
is accessible by clicking the *edited* dropdown next to the issue timestamp. The
`edit_id` is stored in the comment as an HTML comment for programmatic tracing.

### Step 3: Post changelog comment

```bash
gh issue comment $ISSUE --repo $OWNER/$REPO --body "$(cat <<EOF
### Sync: Local → GitHub ($EDIT_AT)

**Changes:**
- **[Section name]** — [brief description of what changed]
- **[Section name]** — [brief description of what changed]

**Edit history:** click the *edited* dropdown on the issue body to view the full diff.

<!-- edit_id: $EDIT_ID -->
EOF
)"
```

The changelog comment serves two purposes:
1. **Human-readable summary** — dot-point list of what changed in this sync
2. **Machine-traceable lineage** — the `edit_id` HTML comment links this comment to
   the specific body revision in the GraphQL `userContentEdits` API

## Refinement Q&A via Comments

During Phase 2, questions and incorporation summaries are posted as issue comments.

### Question format

```markdown
### Refinement Question (N remaining)

**Question:** [The question text]

**Why this matters:** [Impact explanation]

**Sections affected:** [Which sections change based on the answer]
```

### Incorporation format

After incorporating an answer, update the body (via the sync protocol above) and post:

```markdown
### Incorporated

Updated **[section name(s)]** based on the above answer.
[Brief summary of what changed]
```

## GitHub-Specific Considerations

### Mermaid Diagrams

GitHub renders ` ```mermaid ` fences natively — diagrams are visible in the rendered
issue view without extra tooling. However, the skill SHOULD still validate with mmdc
locally when available, since GitHub's renderer silently shows an error block for
invalid syntax rather than failing explicitly.

### HTML Comments

`<!-- ... -->` comments are preserved in the body but hidden in the rendered view.
Use for: `<!-- ASSUMPTION: ... -->`, `<!-- PAYWALLED -->`, `<!-- LINK_NOT_VERIFIED -->`,
`<!-- UNVERIFIED: ... -->`, `<!-- WARNING: ... -->`.

### Body Size and Sub-Issues

GitHub issues support up to ~65,536 characters. When the body approaches this limit
— or when individual `G<N>` sections become large enough to impair readability —
split the document using **GitHub sub-issues** (task lists with tracked references).

#### When to split

- Body exceeds ~50,000 characters (leave headroom for edits)
- Any single `G<N>` section exceeds ~8,000 characters (Output(s) + References + ADRs)
- The gap count exceeds ~8 (navigating a single issue becomes unwieldy)

#### Split structure

The **parent issue** retains:
- Overview (with gap index and Dependencies diagram)
- Current State
- Desired State
- Gap Analysis header, Gap Map, and Dependencies diagrams
- A task list linking to child issues (one per gap)
- Success Measures (both subsections)
- Negative Measures (both subsections)

Each **child issue** contains the full `G<N>` subsection:
- Title: `G<N>: <Gap Title>` (e.g., `G2: LLM-Augmented Matching Stage`)
- Body: Current, Gap, Output(s), References, ADRs
- Label: same labels as parent (inherited for triage)

#### Creating sub-issues

```bash
# Create child issue for G<N>
CHILD=$(gh issue create --repo $OWNER/$REPO \
  --title "G$N: $GAP_TITLE" \
  --body "$GAP_BODY" \
  --label "gap-analysis" \
  | grep -o '[0-9]*$')

# Add as sub-issue to parent using task list syntax
# Read current body, append task list item, write back
CURRENT_BODY=$(gh issue view $PARENT --repo $OWNER/$REPO --json body --jq '.body')
UPDATED_BODY="${CURRENT_BODY}
- [ ] #${CHILD}"
gh issue edit $PARENT --repo $OWNER/$REPO --body "$UPDATED_BODY"
```

GitHub renders `- [ ] #N` as a tracked sub-issue with progress indicators in the
parent issue view. When the child is closed, the checkbox is automatically checked.

#### Sync protocol for split documents

- Phase 2 questions that affect a specific gap are posted as comments on the
  **child issue**, not the parent.
- Cross-gap questions are posted on the **parent issue** with references to affected
  children (`#N1`, `#N2`).
- The parent's Overview gap index links to child issues: `- [G1: Title](#N)`.
- When all child issues are closed, close the parent issue (Phase 3 complete)

### Issue State

| State | Meaning |
|-------|---------|
| Open | Document is in progress (any phase) |
| Closed | Document is complete and validated (Phase 3 passed) |

Close the issue after Phase 3 validation passes, with a final comment summarizing
the completed state.
