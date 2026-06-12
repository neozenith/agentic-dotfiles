# Skill Runtime Environments & Tiered Scripts

This is the **environments** child of the skill/rule family rooted at
[`index.md`](index.md). Siblings: [`scripts.md`](scripts.md) (code contract),
[`evals.md`](evals.md) (which simulates these tiers),
[`statefulness.md`](statefulness.md) (what persists per environment).

Skills run in environments with wildly different capabilities. Helper scripts
are designed in **tiers** so the skill stays useful everywhere — degrading on
*environment*, never on *requirements* (escalators-not-stairs: if the user's
request inherently needs Tier A, Tier B is not a fallback, it's a loud
failure).

## The capability spectrum (researched 2026-06)

| Environment | Scripts | Pkg install | Network | Skills support |
|-------------|---------|-------------|---------|----------------|
| Claude Code CLI (local) | full bash (opt. sandboxed) | yes | user-controlled; sandbox = domain allowlist | full |
| Claude Code on the web | yes (cloud VM, root) | yes (npm/PyPI/crates on Trusted allowlist) | leveled: None/Trusted/Full/Custom | repo `.claude/*` yes; user `~/.claude` no |
| Claude Desktop Cowork | yes (Linux VM, VirtioFS-mounted folders) | yes (registries on default allowlist) | MITM-proxy allowlist, set at session start | yes |
| Claude Desktop (chat) | not on host (server-side sandbox only; MCP for host actions) | server-side, tiered | tiered | claude.ai skills (server-side) |
| claude.ai web / API code-exec | yes (gVisor container, Python 3.11) | claude.ai: tiered; API tool: **none** | API tool: none | zip-upload skills |
| Codex CLI (local) | yes (sandboxed) | needs approval — **network off by default in sandbox** | off in sandbox unless enabled | AGENTS.md; Codex skills |
| Codex cloud | yes (container) | setup phase: yes; agent phase: off by default | proxied allowlist | AGENTS.md |

Key asymmetries: package registries are the only near-universally allowlisted
domains; Docker exists almost nowhere; "network: yes" is per-domain (probe
the registry you need, not example.com).

## Script tiers

- **Tier A — package access.** May assume `uv`/`uvx`, `bunx`, registry
  network. Prefer self-contained launchers (`uv run --with pkg`, PEP-723
  deps, `bunx pkg`) over installs; pin versions.
- **Tier B — stdlib only.** May assume `python3` (+ usually `bash`; probe
  `node` before relying on it). Single-file scripts, stdlib imports only.
  Same **artifact contract** (output paths, JSON schema) as the Tier A
  variant so SKILL.md instructions don't fork. Preinstalled extras (pandas
  in Anthropic's container) are discovered via `importlib.util.find_spec`
  and selected explicitly — never as silent fallback for a required feature.
- **Tier C — no execution.** SKILL.md itself carries the procedural
  fallback: exact steps, copy-paste commands for the *user*, expected
  outputs. Token-expensive by design; Tiers A/B exist to avoid it.

Naming: `scripts/run.py` (Tier A, deps at top, crashes loudly when missing)
and `scripts/run_stdlib.py` (Tier B, zero non-stdlib imports). State tier
requirements in the SKILL.md `description` (the only universally-loaded
surface) — e.g. "requires network access to pypi.org".

## Environment sensing (cheapest first)

Ship `scripts/preflight.sh` as step 0: prints `TIER=A|B|C` + failed probes,
exits non-zero if the skill's minimum tier isn't met, and **reports its
decision loudly** ("Tier B: pypi.org unreachable, using stdlib path").

```bash
# 1. Env vars (free)
[ "$CLAUDE_CODE_REMOTE" = "true" ]            # Claude Code on the web
[ -n "$CLAUDECODE" ]                          # any Claude Code harness
[ -n "$CODEX_PROXY_CERT" ] || env | grep -q '^CODEX_ENV_'   # Codex cloud
[ -n "$CODEX_SANDBOX" ]                       # Codex CLI sandboxed
[ "$CODEX_SANDBOX_NETWORK_DISABLED" = "1" ]   # Codex sandbox, net off
# 2. Filesystem/OS markers (fast)
[ -d "$HOME/.claude" ]                        # real user machine
command -v check-tools >/dev/null             # Claude Code web only
[ "$(hostname)" = "runsc" ]                   # gVisor ⇒ claude.ai sandbox (UNVERIFIED marker)
# 3. Capability probes (slow — short timeouts, run last)
command -v uv bunx python3 node
timeout 5 python3 -c "import urllib.request as u;u.urlopen('https://pypi.org',timeout=4)"
```

Caveats: identity ≠ capability — `CLAUDECODE=1` doesn't mean network; sense
net/write/tools separately. Cowork has no documented env marker (heuristics
only). Claude Code's sandbox redirects `$TMPDIR` per session.

## Fallback ladder

1. Sense identity (env vars) → set expectations.
2. Probe Tier A (tool present AND registry reachable, ≤5s timeout) → full
   helper.
3. Probe Tier B (`python3` works, workspace writable) → stdlib variant.
4. Tier C → emit the markdown procedure.

The ladder runs **before** work starts. Environment degradation is announced;
requirement degradation is forbidden — a request that needs Tier A in a
Tier B world fails loudly with the reason.
