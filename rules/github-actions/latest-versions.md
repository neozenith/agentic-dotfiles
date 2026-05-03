---
paths:
  - ".github/workflows/*.yml"
  - ".github/workflows/*.yaml"
---

# GitHub Actions: Latest Stable Versions

Pin to the latest **major** version tag (e.g. `actions/checkout@v6`) unless a downstream constraint requires otherwise. Major-tag pinning lets the maintainer ship security patches without a workflow edit, while still gating on intentional breaking changes.

LLMs default to stale tags (`actions/checkout@v4`, `actions/setup-node@v4`, `actions/upload-artifact@v3`). All of those run on **Node 20**, which GitHub deprecated in early 2026. Workflows still using them will start emitting deprecation warnings and eventually fail. Use the table below as the source of truth.

## Quick-glance defaults

When you write a fresh workflow, these are the safe defaults:

```yaml
- uses: actions/checkout@v6
- uses: actions/setup-node@v6
- uses: actions/setup-python@v6
- uses: actions/cache@v5
- uses: actions/upload-artifact@v7
- uses: actions/download-artifact@v8
- uses: astral-sh/setup-uv@v8
- uses: oven-sh/setup-bun@v2
- uses: docker/setup-buildx-action@v4
- uses: docker/build-push-action@v7
- uses: aws-actions/configure-aws-credentials@v6
- uses: google-github-actions/auth@v3
```

## Pinning policy

| Use case | Pin to |
| --- | --- |
| Default (apps, internal CI) | Floating major: `actions/checkout@v6` |
| Compliance / supply-chain audited repos | Specific commit SHA with comment: `actions/checkout@<sha>  # v6.0.2` |
| Reproducible release pipelines | Specific patch: `actions/checkout@v6.0.2` |
| Pre-1.0 actions (`v0.x.y`) | Always pin a specific patch — floating `v0` can break |

Never pin to `@main`, `@master`, or `@latest`. Those resolve to whatever HEAD looks like at runtime and defeat both reproducibility and security review.

## Deprecated / Avoid

| Action | Reason | Use instead |
| --- | --- | --- |
| `actions/checkout@v4` and earlier | Node 20 runtime — deprecated by GitHub Actions runner in early 2026. | `actions/checkout@v6` |
| `actions/setup-node@v4` and earlier | Node 20 runtime — deprecated. | `actions/setup-node@v6` |
| `actions/setup-python@v5` and earlier | Node 20 runtime — deprecated. | `actions/setup-python@v6` |
| `actions/cache@v4` and earlier | Node 20; v3 cache backend is shut down (artifacts return 410 Gone). | `actions/cache@v5` |
| `actions/upload-artifact@v3` | Backend retired — uploads fail outright. v4+ artifacts are immutable. | `actions/upload-artifact@v7` |
| `actions/download-artifact@v3` | Same backend retirement as upload v3. | `actions/download-artifact@v8` (must match upload v4+) |
| `actions/github-script@v6` and earlier | Node 16/20; ships old `@actions/github`. | `actions/github-script@v9` |
| `github/codeql-action@v3` and earlier | Node 20 runtime — deprecated. | `github/codeql-action@v4` |
| `tj-actions/changed-files` (any version) | **Compromised in the March 2025 supply-chain attack (CVE-2025-30066).** Even though the maintainer rotated tags and now publishes new releases (v47+), the trust model is broken: an attacker pushed malicious code retroactively to all existing tags, exfiltrating CI secrets from thousands of repos. Several large orgs have a hard ban on this action. | `dorny/paths-filter@v4` for path-change detection, or `git diff` with explicit `fetch-depth: 0` checkout. If you must use it, pin to a specific commit SHA reviewed after 2025-03-15 and audit secrets exposure. |
| `tibdex/github-app-token` | Archived; no longer maintained. | `actions/create-github-app-token@v3` |
| Any action pinned to `@main` / `@master` / `@latest` | Resolves to mutable HEAD at runtime — breaks reproducibility and bypasses security review of upstream changes. | Pin to a major tag or commit SHA. |
| Any action whose `action.yml` declares `using: node16` or `using: node20` | Both runtimes are deprecated on GitHub Actions. Workflows will warn now and fail later. | Upgrade to a major release that declares `using: node24`. |

## How to refresh this file

```bash
# Latest release for one action
gh api repos/<owner>/<repo>/releases/latest --jq '{tag_name, published_at, name}'

# Runtime declared in action.yml at a specific tag
gh api 'repos/<owner>/<repo>/contents/action.yml?ref=<tag>' --jq '.content' \
  | base64 -d | grep -A1 'using:'
```

For composite actions or actions whose entrypoint lives at a sub-path (e.g. `github/codeql-action/init`), check the sub-path's own `action.yml`.

Re-run the refresh quarterly, or when GitHub announces a runner Node bump. Update the "Last refreshed" date at the top.
