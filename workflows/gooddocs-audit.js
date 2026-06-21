export const meta = {
  name: 'gooddocs-audit',
  description:
    'Keep docs true to code as a deterministic fan-out. Premise: CODE IS AUTHORITATIVE and ' +
    'docs (incl. in-code comments/docstrings) drift. Inventory + classify, one adversarial ' +
    'read-only verifier per doc that hunts three kinds of finding — drift (claim contradicts ' +
    'code), slop (AI-slop smells to prune), why-gap (a critical place missing THE WHY) — then ' +
    'dedup + severity-rank. mode=audit (default) reports only; mode=fix safely applies the ' +
    'mechanical, doc-confined fixes and FLAGS everything that needs human judgment. ' +
    'args: array of file paths, or {paths:[...], mode:"audit"|"fix"}; default audits all *.md. ' +
    'Built to run repeatedly (loop/schedule) against the files you are actively editing.',
  phases: [
    { title: 'Inventory', detail: 'glob/scope docs (md + in-code docs), classify rung+lens, git age' },
    { title: 'Verify', detail: 'one adversarial read-only agent per doc — drift + slop + why-gaps' },
    { title: 'Report', detail: 'dedup + severity-rank (claim-type x rung-traffic)' },
    { title: 'Fix', detail: 'fix-mode only: apply safe doc-confined fixes, flag the rest' },
  ],
}

// ── Doctrine lives in the skill; agents read it at runtime so there is ONE source of truth ──
const SKILL = '.claude/skills/gooddocs/SKILL.md'
const SLOP = '.claude/skills/gooddocs/resources/slop_smells.md'

// ── args → scope + mode ──────────────────────────────────────────────────────
const scoped = Array.isArray(args)
  ? args
  : args && Array.isArray(args.paths)
    ? args.paths
    : []
const mode = (args && !Array.isArray(args) && args.mode) || 'audit'

// ── Structured returns: the skill's prose "return format" as enforced schemas ──
const INVENTORY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    docs: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          path: { type: 'string' },
          kind: { type: 'string', enum: ['markdown', 'in-code'], description: 'standalone doc vs comments/docstrings inside a source file' },
          rung: { type: 'string', enum: ['quickstart', 'user-guide', 'reference', 'mixed', 'other'] },
          lens: { type: 'string', enum: ['tutorial', 'how-to', 'reference', 'explanation', 'mixed'] },
          doc_date: { type: 'string', description: 'git last-commit date of the doc/file (YYYY-MM-DD) or "unknown"' },
          code_date: { type: 'string', description: 'git last-commit date of the code it describes, or "unknown"' },
        },
        required: ['path', 'kind', 'rung', 'lens'],
      },
    },
  },
  required: ['docs'],
}

const DOC_AUDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    doc: { type: 'string' },
    claims_checked: { type: 'integer' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          location: { type: 'string', description: 'file:line of the doc/comment' },
          category: { type: 'string', enum: ['drift', 'slop', 'why-gap'] },
          claim: { type: 'string', description: 'the claim/comment text, the slop, or the place missing its WHY' },
          verdict: {
            type: 'string',
            enum: ['confirmed-by-execution', 'confirmed-by-reading', 'drifted', 'unverifiable'],
            description: 'drift only',
          },
          authority: {
            type: 'string',
            enum: ['code', 'doc', 'ambiguous'],
            description: 'drift only: which side is the source of truth. Default premise is code.',
          },
          evidence: { type: 'string', description: 'source file:line / read-only command output / why-it-is-slop / what-WHY-is-missing' },
          severity: { type: 'string', enum: ['red', 'yellow', 'purple', 'none'] },
          fix: { type: 'string', description: 'fix-or-flag remediation; never "delete" to resolve drift' },
        },
        required: ['location', 'category', 'claim', 'evidence', 'severity'],
      },
    },
  },
  required: ['doc', 'claims_checked', 'findings'],
}

const APPLY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    doc: { type: 'string' },
    applied: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: { location: { type: 'string' }, what: { type: 'string' } },
        required: ['location', 'what'],
      },
    },
    skipped: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: { location: { type: 'string' }, reason: { type: 'string' } },
        required: ['location', 'reason'],
      },
    },
  },
  required: ['doc', 'applied', 'skipped'],
}

// ── Phase 1: inventory & classify ──────────────────────────────────────────
phase('Inventory')
const scopeLine = scoped.length
  ? `Classify exactly these paths (do not glob for others): ${scoped.join(', ')}. A path may be a markdown doc OR a source file whose comments/docstrings are the documentation under audit.`
  : 'Glob **/*.md from the repo root. Skip vendored/generated dirs (node_modules, .git, dist, build), tmp/, and the projects/ rsync mirror. Keep only substantial docs.'

const inv = await agent(
  [
    'You are the INVENTORY step of a documentation audit.',
    `Read the Audit-mode contract (section 1) in ${SKILL} and apply it.`,
    'DOCUMENTATION INCLUDES IN-CODE DOCUMENTATION: module/function docstrings and explanatory',
    'comments are docs too, and drift/slop in them counts. Mark each as kind=markdown or kind=in-code.',
    scopeLine,
    'For each doc record: path; kind; apparent rung; apparent lens;',
    'doc_date via "git log -1 --format=%cs -- <path>"; code_date via the same on the main code dir',
    'it describes (use "unknown" if not determinable).',
    'Do NOT verify claims yet and do NOT edit anything — classify and return the docs array only.',
  ].join('\n'),
  { label: 'inventory', phase: 'Inventory', schema: INVENTORY_SCHEMA, agentType: 'Explore' },
)

const docs = (inv && inv.docs) || []
if (!docs.length) {
  log('No docs found to audit.')
  return { mode, docs: 0, claims_checked: 0, findings: [] }
}
log(`Inventoried ${docs.length} doc(s); fanning out adversarial verifiers (mode=${mode}).`)

// ── Phase 2: adversarial per-doc verification (parallel, read-only) ──────────
phase('Verify')
const audited = await parallel(
  docs.map((d) => () =>
    agent(
      [
        'You are an ADVERSARIAL documentation auditor. The premise is CODE IS AUTHORITATIVE and the',
        `documentation drifts. Your brief is to find evidence that ${d.path} is wrong, sloppy, or`,
        'silent on the WHY — never to confirm it (LLMs sycophantically confirm plausible text).',
        `Read the claim-check table + verdict tiers in ${SKILL} (Audit mode, section 2), and the`,
        `AI-slop smell catalog in ${SLOP}. Apply both.`,
        '',
        `Target: ${d.path}  (kind: ${d.kind}, rung: ${d.rung || 'unknown'}, lens: ${d.lens || 'unknown'}).`,
        'If kind=in-code, audit the comments/docstrings, not the executable code.',
        '',
        'Emit findings in three categories:',
        '- category=drift: a claim/comment contradicts the code. Prefer EXECUTABLE checks (grep the',
        '  symbol, glob the path, run read-only "make -n"/"--help") over reading; NEVER run a mutating',
        '  or networked command. Set verdict (confirmed-by-execution | confirmed-by-reading | drifted |',
        '  unverifiable) and authority (code = code is right and the doc is stale [the default]; doc =',
        '  the doc is a spec/contract the code violates; ambiguous = unclear which is authoritative).',
        '  evidence = a source file:line or command output.',
        '- category=slop: an AI-slop smell from the catalog (e.g. task-tracking notes written to self',
        '  instead of to a future reader; text that could be deleted with no loss; hard-coded value',
        '  lists that duplicate code and raise refactor cost). evidence = which smell and why.',
        '- category=why-gap: a CRITICAL place where THE WHY (the reasoning/value behind a decision) is',
        '  absent and a future reader would need it. evidence = what reasoning is missing. Do NOT invent',
        '  the rationale — describe the gap.',
        '',
        'severity = claim-type x rung-traffic (a broken command/path in a high-traffic quickstart is',
        'red; misleading-but-survivable is yellow; an unverifiable claim to flag for the author is',
        'purple; fine is none). fix = a fix-or-flag suggestion; never propose deleting content to',
        'resolve drift (pruning identified slop is the one sanctioned deletion).',
        '',
        'You have read-only tools only: do NOT edit/write/create any file. Return doc, claims_checked',
        '(total claims/comments you assessed), and the findings array.',
      ].join('\n'),
      { label: `audit:${d.path}`, phase: 'Verify', schema: DOC_AUDIT_SCHEMA, agentType: 'Explore' },
    ),
  ),
)

// ── Phase 3: dedup + severity-rank ──────────────────────────────────────────
phase('Report')
const results = audited.filter(Boolean)
const allFindings = results.flatMap((a) => (a.findings || []).map((f) => ({ doc: a.doc, ...f })))

const seen = new Set()
const deduped = []
for (const f of allFindings) {
  const key = `${f.doc}|${f.location}|${f.category}|${f.claim}`
  if (seen.has(key)) continue
  seen.add(key)
  deduped.push(f)
}

const rank = { red: 0, yellow: 1, purple: 2, none: 3 }
deduped.sort((a, b) => (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9))
const claimsChecked = results.reduce((n, a) => n + (a.claims_checked || 0), 0)

// What is SAFE to auto-apply without human judgment:
//   - drift the CODE is authoritative for (doc is just stale), red/yellow → rewrite doc text to match
//   - slop, red/yellow → prune the offending comment/filler
// Never auto-applied (always flagged for a human):
//   - why-gap (cannot fabricate the rationale — only the author/maintainer knows it)
//   - drift where authority is doc/ambiguous (code may be the bug, not the doc)
//   - anything unverifiable / purple
const isSafe = (f) =>
  (f.severity === 'red' || f.severity === 'yellow') &&
  ((f.category === 'drift' && f.verdict === 'drifted' && f.authority === 'code') ||
    f.category === 'slop')

const drift = deduped.filter((f) => f.category === 'drift' && (f.verdict === 'drifted' || f.verdict === 'unverifiable'))
log(
  `${docs.length} doc(s) · ${claimsChecked} checked · ${drift.length} drifted/unverifiable · ` +
    `${deduped.filter((f) => f.category === 'slop').length} slop · ` +
    `${deduped.filter((f) => f.category === 'why-gap').length} why-gap`,
)

if (mode !== 'fix') {
  return { mode, docs: docs.length, claims_checked: claimsChecked, findings: deduped }
}

// ── Phase 4 (fix mode only): apply the safe fixes, flag the rest ─────────────
phase('Fix')
const actionable = deduped.filter(isSafe)
const flagged = deduped.filter((f) => !isSafe(f))

const byDoc = {}
for (const f of actionable) (byDoc[f.doc] ||= []).push(f)
const docsToFix = Object.keys(byDoc)

if (!docsToFix.length) {
  log(`No safe auto-fixes. ${flagged.length} finding(s) flagged for human review.`)
  return { mode, docs: docs.length, claims_checked: claimsChecked, findings: deduped, applied: [], flagged }
}

log(`Applying safe fixes across ${docsToFix.length} doc(s); ${flagged.length} flagged for human review.`)
const applied = await parallel(
  docsToFix.map((doc) => () =>
    agent(
      [
        'You are applying SAFE, mechanical documentation fixes. You may edit ONLY documentation text:',
        'markdown prose, or comment/docstring TEXT inside a source file. You must NEVER change',
        'executable code — no statements, signatures, imports, or logic. Behaviour stays identical.',
        '',
        `Target file: ${doc}`,
        'Apply exactly these pre-vetted findings and nothing else:',
        JSON.stringify(byDoc[doc], null, 2),
        '',
        'Rules:',
        '- drift (authority=code): rewrite the stale doc text so it matches the cited source. The code',
        '  is authoritative; the doc is wrong.',
        '- slop: prune the identified smell (delete the self-addressed tracking note / deletable filler,',
        '  or replace a hard-coded value list with a pointer to where the values live in code).',
        '- Do not delete substantive content to resolve drift; pruning the identified slop is the only',
        '  sanctioned deletion.',
        '- If applying a fix would require changing code, inventing a rationale, or any judgment call',
        '  about which side is authoritative, SKIP it with a reason instead of guessing.',
        'Return doc, applied[] (location + what changed), and skipped[] (location + reason).',
      ].join('\n'),
      { label: `fix:${doc}`, phase: 'Fix', schema: APPLY_SCHEMA },
    ),
  ),
)

const appliedResults = applied.filter(Boolean)
const appliedCount = appliedResults.reduce((n, r) => n + ((r.applied && r.applied.length) || 0), 0)
log(`Applied ${appliedCount} fix(es) across ${appliedResults.length} doc(s); ${flagged.length} flagged.`)

return {
  mode,
  docs: docs.length,
  claims_checked: claimsChecked,
  findings: deduped,
  applied: appliedResults,
  applied_count: appliedCount,
  flagged,
}
