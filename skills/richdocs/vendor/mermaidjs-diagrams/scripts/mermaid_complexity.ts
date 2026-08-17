#!/usr/bin/env bun
// Mermaid Diagram Complexity Analyzer — TypeScript port.
//
// Deterministically scores Mermaid diagrams using cognitive load research
// and recommends subdivision when diagrams exceed visual clarity thresholds.
//
// Research basis:
// - Huang et al. (2020) "Scalability of Network Visualisation from a
//   Cognitive Load Perspective" https://arxiv.org/abs/2008.07944
// - 50 nodes is difficulty threshold, 100 is hard limit.
// - Cyclomatic complexity: E - N + 2P.
//
// Upgrade vs. the Python original (`mermaid_complexity.py`): uses mermaid's
// canonical parsers via the @mermaid-js/parser (Langium) grammars and the
// bundled JISON parsers reached through a happy-dom shim. The Python version
// extracts structure via regex; this version extracts it via the real AST,
// which is strictly more accurate.
//
// Usage:
//   bun run mermaid_complexity.ts path/to/diagram.mmd
//   bun run mermaid_complexity.ts docs/diagrams/
//   bun run mermaid_complexity.ts docs/diagrams/ --preset low --json
//
// Config precedence: CLI args > env vars (MERMAID_COMPLEXITY_*) > preset default.

// ─── Imports ─────────────────────────────────────────────────────────────────
// NOTE: mermaid is dynamic-imported AFTER the happy-dom shim because ES module
// imports are hoisted — a synchronous `import mermaid from "mermaid"` would
// load mermaid *before* any top-level statements run, including our shim.
// The static imports below are safe (they don't touch the DOM at load time).
import { Window } from "happy-dom";
import { parseArgs } from "node:util";
import { readdirSync, statSync } from "node:fs";
import { extname, join, relative, resolve } from "node:path";
import { parse as langiumParse } from "@mermaid-js/parser";

// ─── happy-dom shim (MUST run before the first mermaid import) ───────────────
// mermaid core registers DOMPurify hooks during JISON grammar actions. In
// headless Bun these fail because DOMPurify checks for a DOM before exporting
// `addHook`/`sanitize`. happy-dom is a lightweight DOM implementation; we
// install it on the global scope, then lazy-import mermaid.
function installDomShim(): void {
  const g = globalThis as Record<string, unknown>;
  if (g.window) return; // already installed
  const win = new Window();
  g.window = win;
  g.document = win.document;
  g.Element = win.Element;
  g.HTMLElement = win.HTMLElement;
  g.Node = win.Node;
  g.DocumentFragment = win.DocumentFragment;
  g.NodeFilter = win.NodeFilter;
  g.getComputedStyle = win.getComputedStyle.bind(win);
}

// Lazy singleton for mermaid core — imported on first use, after the shim runs.
let _mermaid: typeof import("mermaid").default | null = null;
async function getMermaid(): Promise<typeof import("mermaid").default> {
  if (_mermaid) return _mermaid;
  installDomShim();
  _mermaid = (await import("mermaid")).default;
  return _mermaid;
}

// ─── Configuration ───────────────────────────────────────────────────────────

interface Preset {
  node_ideal: number;
  node_acceptable: number;
  node_complex: number;
  node_hard_limit: number;
  vcs_ideal: number;
  vcs_acceptable: number;
  vcs_complex: number;
  vcs_critical: number;
  node_target: number;
  vcs_target: number;
}

const PRESETS: Record<string, Preset> = {
  "low-density": {
    node_ideal: 8,
    node_acceptable: 12,
    node_complex: 20,
    node_hard_limit: 35,
    vcs_ideal: 15,
    vcs_acceptable: 25,
    vcs_complex: 40,
    vcs_critical: 60,
    node_target: 10,
    vcs_target: 20,
  },
  "medium-density": {
    node_ideal: 12,
    node_acceptable: 20,
    node_complex: 35,
    node_hard_limit: 60,
    vcs_ideal: 25,
    vcs_acceptable: 40,
    vcs_complex: 70,
    vcs_critical: 100,
    node_target: 15,
    vcs_target: 30,
  },
  "high-density": {
    node_ideal: 20,
    node_acceptable: 35,
    node_complex: 50,
    node_hard_limit: 100,
    vcs_ideal: 35,
    vcs_acceptable: 60,
    vcs_complex: 100,
    vcs_critical: 150,
    node_target: 25,
    vcs_target: 40,
  },
};

const PRESET_ALIASES: Record<string, string> = {
  low: "low-density",
  l: "low-density",
  strict: "low-density",
  med: "medium-density",
  medium: "medium-density",
  m: "medium-density",
  balanced: "medium-density",
  high: "high-density",
  h: "high-density",
  permissive: "high-density",
  default: "high-density",
};

const VCS_WEIGHTS = { edge: 0.5, subgraph: 3.0, depth: 0.1 } as const;

interface ThresholdConfig extends Preset {
  edge_weight: number;
  subgraph_weight: number;
  depth_weight: number;
  preset_name: string;
}

function canonicalPreset(name: string): string {
  const lower = name.toLowerCase();
  return PRESET_ALIASES[lower] ?? (lower in PRESETS ? lower : lower);
}

function configFromPreset(name: string): ThresholdConfig {
  const canonical = canonicalPreset(name);
  const preset = PRESETS[canonical];
  if (!preset) {
    throw new Error(`Unknown preset '${name}'. Valid: low-density, medium-density, high-density`);
  }
  return {
    ...preset,
    edge_weight: VCS_WEIGHTS.edge,
    subgraph_weight: VCS_WEIGHTS.subgraph,
    depth_weight: VCS_WEIGHTS.depth,
    preset_name: canonical,
  };
}

function applyEnvOverrides(config: ThresholdConfig): ThresholdConfig {
  const out = { ...config };
  let customized = false;
  const envPreset = Bun.env.MERMAID_COMPLEXITY_PRESET;
  if (envPreset) {
    Object.assign(out, configFromPreset(envPreset));
  }
  const numericKeys: (keyof ThresholdConfig)[] = [
    "node_ideal",
    "node_acceptable",
    "node_complex",
    "node_hard_limit",
    "vcs_ideal",
    "vcs_acceptable",
    "vcs_complex",
    "vcs_critical",
    "node_target",
    "vcs_target",
    "edge_weight",
    "subgraph_weight",
    "depth_weight",
  ];
  for (const key of numericKeys) {
    const envKey = `MERMAID_COMPLEXITY_${key.toUpperCase()}`;
    const raw = Bun.env[envKey];
    if (raw !== undefined) {
      const parsed = Number(raw);
      if (Number.isFinite(parsed)) {
        (out[key] as number) = parsed;
        customized = true;
      }
    }
  }
  if (customized) out.preset_name = "custom";
  return out;
}

// ─── Types ───────────────────────────────────────────────────────────────────

interface MermaidStats {
  nodes: number;
  edges: number;
  subgraphs: number;
  max_subgraph_depth: number;
  node_ids: string[];
  subgraph_names: string[];
  parser_used: "langium" | "mermaid-core" | "custom";
  diagram_type: string;
}

interface ComplexityMetrics {
  visual_complexity_score: number;
  edge_density: number;
  cyclomatic_complexity: number;
  vcs_formula: string;
  vcs_breakdown: {
    nodes_contribution: number;
    edges_contribution: number;
    subgraphs_contribution: number;
    base_vcs: number;
    depth_multiplier: number;
    final_vcs: number;
  };
}

type Rating = "ideal" | "acceptable" | "complex" | "critical";
type Color = "green" | "yellow" | "orange" | "red";
type ParseQuality = "ok" | "failed";

interface SplitEstimate {
  split_number: number;
  estimated_nodes: number;
  estimated_edges: number;
  estimated_vcs: number;
  estimated_rating: Rating;
  would_need_further_subdivision: boolean;
  recursive_recommendation?: string;
}

interface SubdivisionWorkingOut {
  nodes: number;
  vcs: number;
  subgraphs: number;
  nodes_exceeds_acceptable: boolean;
  nodes_exceeds_complex: boolean;
  vcs_exceeds_acceptable: boolean;
  node_based_splits: number;
  node_based_formula: string;
  vcs_based_splits: number;
  vcs_based_formula: string;
  subgraph_adjusted_splits: number;
  subgraph_adjustment_reason: string;
  final_splits: number;
  needs_subdivision: boolean;
  estimated_per_split: SplitEstimate[];
}

interface ComplexityReport {
  file_path: string;
  nodes: number;
  edges: number;
  subgraphs: number;
  max_depth: number;
  visual_complexity_score: number;
  edge_density: number;
  cyclomatic_complexity: number;
  vcs_formula: string;
  vcs_breakdown: ComplexityMetrics["vcs_breakdown"];
  rating: Rating;
  color: Color;
  needs_subdivision: boolean;
  recommended_subdivisions: number;
  subdivision_rationale: string;
  working_out: SubdivisionWorkingOut | null;
  subgraph_names: string[];
  parser_used: MermaidStats["parser_used"];
  diagram_type: string;
  // "ok" means metrics are trustworthy; "failed" means a multi-line diagram
  // yielded 0 nodes (silent parser failure). No middle ground — a parser
  // either extracted structure we trust, or it did not.
  parse_quality: ParseQuality;
  thresholds_used: Record<string, number>;
  // Populated when the diagram was extracted from a fenced ```mermaid block
  // inside a markdown file. Absent for standalone .mmd files.
  fence?: {
    index: number;
    keyword: string;
    line_start: number;
    line_end: number;
  };
}

// Ruff-style lint output. Strong-typed, CamelCased error codes group failure
// classes; findings are emitted one-per-line `location: Code message`, and
// ParserFailure short-circuits any other checks on that diagram (no point
// threshold-checking a diagram the parser couldn't read).
export type LintCode =
  | "ParserFailure"
  | "NodeCountExceedsHardLimit"
  | "NodeCountExceedsCognitiveLimit"
  | "NodeCountExceedsAcceptable"
  | "VisualComplexityExceedsCritical"
  | "VisualComplexityExceedsAcceptable"
  | "SubgraphNestingTooDeep";

export type LintSeverity = "error" | "warning";

export interface LintFinding {
  code: LintCode;
  severity: LintSeverity;
  // Canonical terminal-clickable anchor: "path/to/file.md:100-108" for fenced
  // diagrams; "path/to/file.mmd" (no range) for standalone .mmd files.
  location: string;
  diagram_type: string;
  // One-line explanation with the concrete numbers that caused this finding.
  message: string;
  // Actionable next step. For ParserFailure, explains the root cause and
  // records that complexity checks were skipped. For threshold codes,
  // names the boundaries and target per-sub-diagram sizing.
  remediation: string;
  // Optional context fields populated only where they apply to the code.
  actual?: number;
  threshold?: number;
  parser?: MermaidStats["parser_used"];
  boundaries?: string[];
}

const ERROR_CODES: ReadonlySet<LintCode> = new Set<LintCode>([
  "ParserFailure",
  "NodeCountExceedsHardLimit",
  "NodeCountExceedsCognitiveLimit",
  "VisualComplexityExceedsCritical",
]);

// ─── Parser dispatch ─────────────────────────────────────────────────────────

const LANGIUM_TYPES: Record<
  string,
  "architecture" | "info" | "pie" | "gitGraph" | "packet" | "radar" | "treemap" | "treeView" | "wardley"
> = {
  "architecture-beta": "architecture",
  architecture: "architecture",
  info: "info",
  pie: "pie",
  gitGraph: "gitGraph",
  "packet-beta": "packet",
  packet: "packet",
  "radar-beta": "radar",
  radar: "radar",
  "treemap-beta": "treemap",
  treemap: "treemap",
  "treeView-beta": "treeView",
  treeView: "treeView",
  "wardley-beta": "wardley",
  wardley: "wardley",
};

function detectKeyword(content: string): string | null {
  for (const raw of content.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("%%")) continue;
    // Skip YAML frontmatter block ("---\n...\n---")
    if (line === "---") continue;
    const first = line.split(/\s+/)[0];
    return first ?? null;
  }
  return null;
}

async function extractStats(content: string): Promise<MermaidStats> {
  const keyword = detectKeyword(content) ?? "unknown";

  // 1. Langium grammar (@mermaid-js/parser) — typed AST, no DOM needed.
  if (keyword in LANGIUM_TYPES) {
    try {
      return await extractLangiumStats(content, keyword);
    } catch {
      /* fall through to mermaid-core */
    }
  }

  // 2. Mermaid-core JISON parser via happy-dom. The shim satisfies
  // DOMPurify; the parsers populate each type's DB (vertices, edges,
  // blocks, sections, etc.). A per-type adapter in extractCoreStats reads
  // the canonical DB shape.
  try {
    return await extractCoreStats(content, keyword);
  } catch {
    /* fall through */
  }

  // 3. Neither canonical parser produced stats. Return a tagged failure
  // so assessParseQuality flags ParserFailure.
  return {
    nodes: 0,
    edges: 0,
    subgraphs: 0,
    max_subgraph_depth: 0,
    node_ids: [],
    subgraph_names: [],
    parser_used: "mermaid-core",
    diagram_type: keyword,
  };
}

// ── Langium extraction (@mermaid-js/parser) ─────────────────────────────────

async function langiumParseAny(type: string, content: string): Promise<unknown> {
  switch (type) {
    case "architecture":
      return langiumParse("architecture", content);
    case "info":
      return langiumParse("info", content);
    case "pie":
      return langiumParse("pie", content);
    case "gitGraph":
      return langiumParse("gitGraph", content);
    case "packet":
      return langiumParse("packet", content);
    case "radar":
      return langiumParse("radar", content);
    case "treemap":
      return langiumParse("treemap", content);
    case "treeView":
      return langiumParse("treeView", content);
    case "wardley":
      return langiumParse("wardley", content);
    default:
      throw new Error(`no langium parser for ${type}`);
  }
}

async function extractLangiumStats(content: string, keyword: string): Promise<MermaidStats> {
  const mapped = LANGIUM_TYPES[keyword];
  if (!mapped) throw new Error(`not a langium keyword: ${keyword}`);
  const ast = (await langiumParseAny(mapped, content)) as Record<string, unknown>;

  const nodeIds: string[] = [];
  const subgraphNames: string[] = [];
  let edges = 0;
  let maxDepth = 0;

  switch (mapped) {
    case "architecture": {
      const services = (ast.services as Array<{ id?: string }> | undefined) ?? [];
      const groups = (ast.groups as Array<{ id?: string; title?: string; in?: string }> | undefined) ?? [];
      const edgeArr = (ast.edges as Array<unknown> | undefined) ?? [];
      nodeIds.push(...services.map((s) => s.id ?? ""));
      subgraphNames.push(...groups.map((g) => g.title ?? g.id ?? ""));
      maxDepth = architectureDepth(groups);
      edges = edgeArr.length;
      break;
    }
    case "pie": {
      const sections = (ast.sections as Array<{ label?: string }> | undefined) ?? [];
      nodeIds.push(...sections.map((s, i) => s.label ?? `slice_${i}`));
      break;
    }
    case "packet": {
      const blocks = (ast.blocks as Array<unknown> | undefined) ?? [];
      nodeIds.push(...blocks.map((_, i) => `block_${i}`));
      break;
    }
    case "gitGraph": {
      const statements = (ast.statements as Array<{ $type?: string; id?: string; name?: string }> | undefined) ?? [];
      for (const s of statements) {
        if (s.$type === "Commit") nodeIds.push(s.id ?? `commit_${nodeIds.length}`);
        else if (s.$type === "Branch") subgraphNames.push(s.name ?? `branch_${subgraphNames.length}`);
        else if (s.$type === "Merge") edges++;
      }
      break;
    }
    case "radar": {
      const axes = (ast.axes as Array<{ name?: string }> | undefined) ?? [];
      const curves = (ast.curves as Array<{ name?: string }> | undefined) ?? [];
      nodeIds.push(...axes.map((a, i) => a.name ?? `axis_${i}`));
      nodeIds.push(...curves.map((c, i) => c.name ?? `curve_${i}`));
      edges = axes.length * curves.length;
      break;
    }
    case "treeView": {
      // AST shape: flat ast.nodes[] with { name, indent }. Tree structure
      // derives from indent values; edges = nodes - roots.
      const nodes = (ast.nodes as Array<{ name?: string; indent?: number }> | undefined) ?? [];
      const stats = indentTreeStats(nodes.map((n, i) => ({ label: n.name ?? `node_${i}`, indent: n.indent ?? 0 })));
      nodeIds.push(...stats.labels);
      edges = stats.edges;
      maxDepth = stats.depth;
      break;
    }
    case "treemap": {
      // AST shape: ast.TreemapRows[] with .indent and .item.{Section|Leaf}.name.
      const rows = (ast.TreemapRows as Array<{ indent?: number; item?: { name?: string } }> | undefined) ?? [];
      const stats = indentTreeStats(rows.map((r, i) => ({ label: r.item?.name ?? `row_${i}`, indent: r.indent ?? 0 })));
      nodeIds.push(...stats.labels);
      edges = stats.edges;
      maxDepth = stats.depth;
      break;
    }
    case "wardley": {
      // AST shape: ast.anchors[], ast.components[], ast.links[] — NOT ast.edges.
      // The old code looked for `ast.edges` and returned 0.
      const components = (ast.components as Array<{ name?: string }> | undefined) ?? [];
      const anchors = (ast.anchors as Array<{ name?: string }> | undefined) ?? [];
      const links = (ast.links as Array<unknown> | undefined) ?? [];
      nodeIds.push(...anchors.map((a, i) => a.name ?? `anchor_${i}`));
      nodeIds.push(...components.map((c, i) => c.name ?? `comp_${i}`));
      edges = links.length;
      break;
    }
    case "info":
      break; // trivial diagram type, no structure
  }

  return {
    nodes: new Set(nodeIds.filter(Boolean)).size,
    edges,
    subgraphs: subgraphNames.length,
    max_subgraph_depth: maxDepth,
    node_ids: [...new Set(nodeIds.filter(Boolean))].sort(),
    subgraph_names: subgraphNames,
    parser_used: "langium",
    diagram_type: keyword,
  };
}

function architectureDepth(groups: Array<{ id?: string; in?: string }>): number {
  const parentOf = new Map<string, string | undefined>();
  for (const g of groups) parentOf.set(g.id ?? "", g.in);
  let max = 0;
  for (const g of groups) {
    let depth = 1;
    let cur = g.in;
    const seen = new Set<string>();
    while (cur && !seen.has(cur)) {
      seen.add(cur);
      depth++;
      cur = parentOf.get(cur);
    }
    if (depth > max) max = depth;
  }
  return max;
}

// Compute tree structure from a flat, indent-ordered node list.
// Used for treemap, treeView, mindmap, ishikawa, kanban — every diagram
// type where parent-child is encoded via indentation rather than explicit
// edges. `labels` preserves the node names for VCS bookkeeping; `edges` is
// the number of parent-child links (nodes - number_of_roots); `depth` is
// the maximum number of indent-steps past the root level.
export function indentTreeStats(items: Array<{ label: string; indent: number }>): {
  labels: string[];
  edges: number;
  depth: number;
} {
  if (items.length === 0) return { labels: [], edges: 0, depth: 0 };
  const labels = items.map((i) => i.label);
  const indents = items.map((i) => i.indent);
  const minIndent = Math.min(...indents);
  const uniqueIndents = [...new Set(indents)].sort((a, b) => a - b);
  const roots = items.filter((i) => i.indent === minIndent).length;
  const edges = Math.max(0, items.length - roots);
  const depth = Math.max(0, uniqueIndents.length - 1);
  return { labels, edges, depth };
}

// ── mermaid-core extraction via .db after parse ─────────────────────────────
//
// Every diagram type's canonical DB has a different shape. Some expose data
// via getter methods (flowchart's getVertices/getEdges, kanban's getSections,
// block's getBlocksFlat). Others expose it via direct properties (er.entities,
// state.nodes, requirement.requirements). We dispatch on diagram.type and
// each adapter reads ONLY that type's canonical surface — no text parsing,
// no regex. The parser did the work; we just read the result.

type AnyDb = Record<string, unknown>;
interface Structure {
  nodeIds: string[];
  edges: number;
  subgraphNames: string[];
  maxDepth: number;
}
type CoreAdapter = (db: AnyDb) => Structure;

async function extractCoreStats(content: string, keyword: string): Promise<MermaidStats> {
  const mermaid = await getMermaid();

  // mermaid.parse() lazily registers the matching diagram and populates its DB.
  await mermaid.parse(content);

  const api = (
    mermaid as unknown as {
      mermaidAPI?: { getDiagramFromText?: (t: string) => Promise<{ db: AnyDb; type?: string }> };
    }
  ).mermaidAPI;
  if (!api?.getDiagramFromText) throw new Error("mermaidAPI.getDiagramFromText not available");
  const diagram = await api.getDiagramFromText(content);
  const diagramType = diagram.type ?? keyword;

  const adapter = CORE_ADAPTERS[diagramType];
  if (!adapter) {
    throw new Error(`no core adapter for diagram.type="${diagramType}" (keyword="${keyword}")`);
  }
  const { nodeIds, edges, subgraphNames, maxDepth } = adapter(diagram.db);

  return {
    nodes: nodeIds.length,
    edges,
    subgraphs: subgraphNames.length,
    max_subgraph_depth: maxDepth,
    node_ids: [...nodeIds].sort(),
    subgraph_names: subgraphNames,
    parser_used: "mermaid-core",
    diagram_type: diagramType,
  };
}

// ─── Per-type DB adapters ──
// Each adapter reads ONLY canonical mermaid DB surface for that diagram type.
// Keys below match the `diagram.type` string mermaid assigns after parse
// (which may differ from the first-line keyword — e.g. "flowchart-v2" vs
// "flowchart", "er" vs "erDiagram", "stateDiagram" vs "stateDiagram-v2").

const CORE_ADAPTERS: Record<string, CoreAdapter> = {
  "flowchart-v2": adaptFlowchart,
  flowchart: adaptFlowchart,
  graph: adaptFlowchart,
  classDiagram: adaptClass,
  "classDiagram-v2": adaptClass,
  class: adaptClass,
  sequence: adaptSequence,
  block: adaptBlock,
  c4: adaptC4,
  er: adaptEr,
  gantt: adaptGantt,
  ishikawa: adaptIshikawa,
  kanban: adaptKanban,
  mindmap: adaptMindmap,
  quadrantChart: adaptQuadrantChart,
  requirement: adaptRequirement,
  sankey: adaptSankey,
  stateDiagram: adaptState,
  "stateDiagram-v2": adaptState,
  timeline: adaptTimeline,
  journey: adaptJourney,
  venn: adaptVenn,
  xychart: adaptXychart,
};

function callGetter<T>(db: AnyDb, name: string): T | null {
  const fn = db[name];
  return typeof fn === "function" ? ((fn as () => T)() ?? null) : null;
}

function adaptFlowchart(db: AnyDb): Structure {
  // flowchartDb exposes data on direct properties: db.vertices (Map),
  // db.edges (Array), db.subGraphs (Array). No getters.
  const vertices = (db.vertices instanceof Map ? db.vertices : new Map()) as Map<string, unknown>;
  const edgesArr = (Array.isArray(db.edges) ? db.edges : []) as Array<unknown>;
  const subGraphs = (Array.isArray(db.subGraphs) ? db.subGraphs : []) as Array<{
    id?: string;
    title?: string;
    nodes?: string[];
  }>;
  return {
    nodeIds: [...vertices.keys()],
    edges: edgesArr.length,
    subgraphNames: subGraphs.map((s) => s.title ?? s.id ?? ""),
    maxDepth: subgraphNestingDepth(subGraphs),
  };
}

function adaptClass(db: AnyDb): Structure {
  // classDb exposes data on direct properties: db.classes (Map), db.relations (Array).
  const classes = (db.classes instanceof Map ? db.classes : new Map()) as Map<string, unknown>;
  const relations = (Array.isArray(db.relations) ? db.relations : []) as Array<unknown>;
  return { nodeIds: [...classes.keys()], edges: relations.length, subgraphNames: [], maxDepth: 0 };
}

interface SequenceState {
  records?: {
    actors?: Map<string, unknown>;
    messages?: Array<unknown>;
  };
}
function adaptSequence(db: AnyDb): Structure {
  // sequenceDb stores state under db.state.records.{actors,messages}.
  const state = (db.state as SequenceState | undefined)?.records;
  const actors = state?.actors instanceof Map ? state.actors : new Map<string, unknown>();
  const rawMessages = state?.messages;
  const messages = Array.isArray(rawMessages) ? rawMessages : [];
  return {
    nodeIds: [...actors.keys()],
    edges: messages.length,
    subgraphNames: [],
    maxDepth: 0,
  };
}

interface BlockItem {
  id?: string;
  type?: string;
  children?: BlockItem[];
}
function adaptBlock(db: AnyDb): Structure {
  // Block uses a recursive tree: container blocks have non-empty `children`,
  // leaf blocks don't. getBlocks() is the top-level list; walk recursively.
  const roots = callGetter<BlockItem[]>(db, "getBlocks") ?? [];
  const edges = (callGetter<Array<unknown>>(db, "getEdges") ?? []).length;
  const leaves: string[] = [];
  const containers: string[] = [];
  let maxDepth = 0;
  const walk = (items: BlockItem[], depth: number): void => {
    for (const item of items) {
      const id = item.id ?? "";
      const kids = item.children ?? [];
      // Mermaid wraps content in "space" / "composite" synthetic nodes —
      // count user-visible blocks only. Treat composite-with-children as
      // a container (subgraph), everything else as a leaf node.
      if (kids.length > 0) {
        containers.push(id);
        if (depth + 1 > maxDepth) maxDepth = depth + 1;
        walk(kids, depth + 1);
      } else if (item.type !== "space" && item.type !== "composite") {
        leaves.push(id);
      }
    }
  };
  walk(roots, 0);
  return { nodeIds: leaves, edges, subgraphNames: containers, maxDepth };
}

interface C4Boundary {
  alias?: string;
  label?: { text?: string };
}
function adaptC4(db: AnyDb): Structure {
  const shapes = callGetter<Array<{ alias?: string }>>(db, "getC4ShapeArray") ?? [];
  const rels = callGetter<Array<unknown>>(db, "getRels") ?? [];
  const boundaries = callGetter<C4Boundary[]>(db, "getBoundaries") ?? [];
  // Top-level "global" boundary is synthetic; exclude from user-visible count.
  const userBoundaries = boundaries.filter((b) => b.alias && b.alias !== "global");
  return {
    nodeIds: shapes.map((s) => s.alias ?? ""),
    edges: rels.length,
    subgraphNames: userBoundaries.map((b) => b.alias ?? ""),
    maxDepth: userBoundaries.length > 0 ? 1 : 0,
  };
}

function adaptEr(db: AnyDb): Structure {
  // ER db exposes data on direct properties. entities is a Map keyed on
  // entity name (CAR, NAMED-DRIVER); relationships is an Array.
  const entities = db.entities instanceof Map ? db.entities : new Map<string, unknown>();
  const relationships = (Array.isArray(db.relationships) ? db.relationships : []) as Array<unknown>;
  return {
    nodeIds: [...entities.keys()],
    edges: relationships.length,
    subgraphNames: [],
    maxDepth: 0,
  };
}

interface GanttTask {
  id?: string;
  task?: string;
}
interface GanttSection {
  name?: string;
}
function adaptGantt(db: AnyDb): Structure {
  const tasks = callGetter<GanttTask[]>(db, "getTasks") ?? [];
  const sections = callGetter<GanttSection[]>(db, "getSections") ?? [];
  return {
    nodeIds: tasks.map((t) => t.id ?? t.task ?? ""),
    edges: 0,
    subgraphNames: sections.map((s) => s.name ?? ""),
    maxDepth: sections.length > 0 ? 1 : 0,
  };
}

interface IshikawaNode {
  label?: string;
  name?: string;
  children?: IshikawaNode[];
}
function adaptIshikawa(db: AnyDb): Structure {
  const root = callGetter<IshikawaNode | null>(db, "getRoot");
  if (!root) return { nodeIds: [], edges: 0, subgraphNames: [], maxDepth: 0 };
  const labels: string[] = [];
  let maxDepth = 0;
  const walk = (node: IshikawaNode, depth: number): void => {
    labels.push(node.label ?? node.name ?? "");
    if (depth > maxDepth) maxDepth = depth;
    for (const c of node.children ?? []) walk(c, depth + 1);
  };
  walk(root, 0);
  return { nodeIds: labels, edges: Math.max(0, labels.length - 1), subgraphNames: [], maxDepth };
}

interface KanbanNode {
  id?: string;
  parentId?: string;
  isGroup?: boolean;
}
function adaptKanban(db: AnyDb): Structure {
  // getData() returns a flat node list; isGroup=true marks columns, tasks
  // point at their column via parentId.
  const data = callGetter<{ nodes?: KanbanNode[] } | null>(db, "getData");
  const nodes = data?.nodes ?? [];
  const columns = nodes.filter((n) => n.isGroup === true);
  const tasks = nodes.filter((n) => n.isGroup === false);
  return {
    nodeIds: tasks.map((t) => t.id ?? ""),
    edges: 0,
    subgraphNames: columns.map((c) => c.id ?? ""),
    maxDepth: columns.length > 0 ? 1 : 0,
  };
}

interface MindmapNode {
  nodeId?: number;
  descr?: string;
  children?: MindmapNode[];
}
function adaptMindmap(db: AnyDb): Structure {
  const root = callGetter<MindmapNode | null>(db, "getMindmap");
  if (!root) return { nodeIds: [], edges: 0, subgraphNames: [], maxDepth: 0 };
  const labels: string[] = [];
  let maxDepth = 0;
  const walk = (node: MindmapNode, depth: number): void => {
    labels.push(node.descr ?? String(node.nodeId ?? ""));
    if (depth > maxDepth) maxDepth = depth;
    for (const c of node.children ?? []) walk(c, depth + 1);
  };
  walk(root, 0);
  return { nodeIds: labels, edges: Math.max(0, labels.length - 1), subgraphNames: [], maxDepth };
}

interface QuadrantData {
  quadrants?: Array<{ text?: { text?: string } | string }>;
}
function adaptQuadrantChart(db: AnyDb): Structure {
  const data = callGetter<QuadrantData | null>(db, "getQuadrantData");
  const quadrants = data?.quadrants ?? [];
  const labels = quadrants.map((q) => {
    const t = q.text;
    return typeof t === "string" ? t : (t?.text ?? "");
  });
  return { nodeIds: labels, edges: 0, subgraphNames: [], maxDepth: 0 };
}

function adaptRequirement(db: AnyDb): Structure {
  // requirements and elements are both Maps keyed on name. relations is an Array.
  const requirements = db.requirements instanceof Map ? db.requirements : new Map<string, unknown>();
  const elements = db.elements instanceof Map ? db.elements : new Map<string, unknown>();
  const relations = (Array.isArray(db.relations) ? db.relations : []) as Array<unknown>;
  return {
    nodeIds: [...requirements.keys(), ...elements.keys()],
    edges: relations.length,
    subgraphNames: [],
    maxDepth: 0,
  };
}

function adaptSankey(db: AnyDb): Structure {
  const nodes = callGetter<Array<{ id?: string }>>(db, "getNodes") ?? [];
  const links = callGetter<Array<unknown>>(db, "getLinks") ?? [];
  return {
    nodeIds: nodes.map((n) => n.id ?? ""),
    edges: links.length,
    subgraphNames: [],
    maxDepth: 0,
  };
}

interface StateNode {
  id?: string;
  type?: string;
}
interface StateEdge {
  id1?: string;
  id2?: string;
}
function adaptState(db: AnyDb): Structure {
  // stateDiagram db exposes data on direct properties.
  const nodes = (db.nodes as StateNode[] | undefined) ?? [];
  const edges = (db.edges as StateEdge[] | undefined) ?? [];
  return {
    nodeIds: nodes.map((n) => n.id ?? ""),
    edges: edges.length,
    subgraphNames: [],
    maxDepth: 0,
  };
}

interface TimelineTask {
  task?: string;
  section?: string;
}
interface TimelineSection {
  sectionName?: string;
  section?: string;
}
function adaptTimeline(db: AnyDb): Structure {
  const tasks = callGetter<TimelineTask[]>(db, "getTasks") ?? [];
  const sections = callGetter<TimelineSection[]>(db, "getSections") ?? [];
  return {
    nodeIds: tasks.map((t) => t.task ?? ""),
    edges: 0,
    subgraphNames: sections.map((s) => s.sectionName ?? s.section ?? ""),
    maxDepth: sections.length > 0 ? 1 : 0,
  };
}

interface JourneyTask {
  task?: string;
}
interface JourneySection {
  id?: string;
  name?: string;
}
function adaptJourney(db: AnyDb): Structure {
  const tasks = callGetter<JourneyTask[]>(db, "getTasks") ?? [];
  const sections = callGetter<JourneySection[]>(db, "getSections") ?? [];
  return {
    nodeIds: tasks.map((t) => t.task ?? ""),
    edges: 0,
    subgraphNames: sections.map((s) => s.name ?? s.id ?? ""),
    maxDepth: sections.length > 0 ? 1 : 0,
  };
}

interface VennSet {
  id?: string;
}
interface VennSubset {
  sets?: string[];
}
function adaptVenn(db: AnyDb): Structure {
  const sets = callGetter<VennSet[]>(db, "getCurrentSets") ?? [];
  const subsets = callGetter<VennSubset[]>(db, "getSubsetData") ?? [];
  // Subsets with multiple sets = unions/intersections = edges.
  const multiSetSubsets = subsets.filter((s) => (s.sets?.length ?? 0) >= 2);
  return {
    nodeIds: sets.map((s) => s.id ?? ""),
    edges: multiSetSubsets.length,
    subgraphNames: [],
    maxDepth: 0,
  };
}

interface XYChartData {
  xAxis?: { categories?: string[] };
}
function adaptXychart(db: AnyDb): Structure {
  const data = callGetter<XYChartData | null>(db, "getXYChartData");
  const categories = data?.xAxis?.categories ?? [];
  return { nodeIds: categories, edges: 0, subgraphNames: [], maxDepth: 0 };
}

function subgraphNestingDepth(subGraphs: Array<{ id?: string; nodes?: string[] }>): number {
  if (subGraphs.length === 0) return 0;
  const idToMembers = new Map<string, Set<string>>();
  for (const sg of subGraphs) {
    if (sg.id) idToMembers.set(sg.id, new Set(sg.nodes ?? []));
  }
  let max = 1;
  const depthOf = (id: string, seen: Set<string>): number => {
    if (seen.has(id)) return 1;
    seen.add(id);
    let d = 1;
    for (const [otherId, members] of idToMembers) {
      if (otherId !== id && members.has(id)) {
        d = Math.max(d, 1 + depthOf(otherId, seen));
      }
    }
    return d;
  };
  for (const id of idToMembers.keys()) max = Math.max(max, depthOf(id, new Set()));
  return max;
}

// ─── Metrics ─────────────────────────────────────────────────────────────────

function calculateComplexity(stats: MermaidStats, config: ThresholdConfig): ComplexityMetrics {
  const n = stats.nodes,
    e = stats.edges,
    s = stats.subgraphs,
    d = stats.max_subgraph_depth;
  const depthMultiplier = 1 + d * config.depth_weight;
  const baseVcs = n + e * config.edge_weight + s * config.subgraph_weight;
  const vcs = baseVcs * depthMultiplier;
  // Edge density = E / (N*(N-1)). Undefined for N≤1 — report 0 rather than
  // dividing by 1 as a fallback, which gave nonsensical densities like 5.0
  // when a parser returned 0 nodes but non-zero edges.
  const maxEdges = n > 1 ? n * (n - 1) : 0;
  const edgeDensity = maxEdges > 0 ? e / maxEdges : 0;
  const cyclomatic = Math.max(1, e - n + 2);

  const formula = `(${n} + ${e}×${config.edge_weight} + ${s}×${config.subgraph_weight}) × (1 + ${d}×${config.depth_weight})`;
  return {
    visual_complexity_score: round2(vcs),
    edge_density: round4(edgeDensity),
    cyclomatic_complexity: cyclomatic,
    vcs_formula: formula,
    vcs_breakdown: {
      nodes_contribution: n,
      edges_contribution: round2(e * config.edge_weight),
      subgraphs_contribution: round2(s * config.subgraph_weight),
      base_vcs: round2(baseVcs),
      depth_multiplier: round2(depthMultiplier),
      final_vcs: round2(vcs),
    },
  };
}

function rateComplexity(vcs: number, nodes: number, c: ThresholdConfig): { rating: Rating; color: Color } {
  if (nodes <= c.node_ideal && vcs <= c.vcs_ideal) return { rating: "ideal", color: "green" };
  if (nodes <= c.node_acceptable && vcs <= c.vcs_acceptable) return { rating: "acceptable", color: "yellow" };
  if (nodes <= c.node_complex && vcs <= c.vcs_complex) return { rating: "complex", color: "orange" };
  return { rating: "critical", color: "red" };
}

// ─── Subdivision recommendation ──────────────────────────────────────────────

function recommendSubdivisions(
  vcs: number,
  nodes: number,
  edges: number,
  subgraphs: number,
  config: ThresholdConfig,
): { needs: boolean; count: number; rationale: string; workingOut: SubdivisionWorkingOut } {
  const nodesExceedsAcceptable = nodes > config.node_acceptable;
  const nodesExceedsComplex = nodes > config.node_complex;
  const vcsExceedsAcceptable = vcs > config.vcs_acceptable;
  const needs = nodesExceedsAcceptable || vcsExceedsAcceptable;

  const nodeSplits = nodesExceedsAcceptable ? Math.ceil(nodes / config.node_target) : 1;
  const nodeFormula = nodesExceedsAcceptable
    ? `ceil(${nodes} / ${config.node_target}) = ${nodeSplits}`
    : `${nodes} ≤ ${config.node_acceptable}, no split needed`;

  const vcsSplits = vcsExceedsAcceptable ? Math.ceil(vcs / config.vcs_target) : 1;
  const vcsFormula = vcsExceedsAcceptable
    ? `ceil(${vcs.toFixed(1)} / ${config.vcs_target}) = ${vcsSplits}`
    : `${vcs.toFixed(1)} ≤ ${config.vcs_acceptable}, no split needed`;

  const count = Math.max(nodeSplits, vcsSplits);
  let subgraphAdjusted = count;
  let subgraphReason = "No adjustment needed";
  if (needs && subgraphs >= 2) {
    const suggested = Math.min(subgraphs, count + 1);
    if (suggested >= count) {
      subgraphAdjusted = suggested;
      subgraphReason = `Adjusted from ${count} to ${suggested} to align with ${subgraphs} existing subgraphs`;
    }
  }
  const finalCount = subgraphAdjusted;

  const rationaleParts: string[] = [];
  if (nodesExceedsAcceptable)
    rationaleParts.push(`Node count (${nodes}) exceeds threshold (${config.node_acceptable})`);
  if (vcsExceedsAcceptable) rationaleParts.push(`VCS (${vcs.toFixed(1)}) exceeds threshold (${config.vcs_acceptable})`);
  if (nodesExceedsComplex) rationaleParts.push(`⚠️ Nodes (${nodes}) exceed cognitive limit (${config.node_complex})`);
  if (subgraphAdjusted !== count) rationaleParts.push(`Using ${subgraphs} subgraphs as boundaries`);
  const rationale = rationaleParts.length ? rationaleParts.join("; ") : "Within limits";

  const estimatedPerSplit: SplitEstimate[] = [];
  if (needs && finalCount > 1) {
    const estNodes = Math.ceil(nodes / finalCount);
    const estEdges = Math.ceil(edges / finalCount);
    const estSubgraphs = Math.max(1, Math.floor(subgraphs / finalCount));
    for (let i = 0; i < finalCount; i++) {
      const estVcs = estNodes + estEdges * config.edge_weight + estSubgraphs * config.subgraph_weight;
      const { rating } = rateComplexity(estVcs, estNodes, config);
      const wouldNeedFurther = rating === "complex" || rating === "critical";
      const split: SplitEstimate = {
        split_number: i + 1,
        estimated_nodes: estNodes,
        estimated_edges: estEdges,
        estimated_vcs: round1(estVcs),
        estimated_rating: rating,
        would_need_further_subdivision: wouldNeedFurther,
      };
      if (wouldNeedFurther) {
        const additional = Math.ceil(estVcs / config.vcs_target);
        if (additional > 1) split.recursive_recommendation = `This split would need ${additional} further subdivisions`;
      }
      estimatedPerSplit.push(split);
    }
  }

  return {
    needs,
    count: finalCount,
    rationale,
    workingOut: {
      nodes,
      vcs,
      subgraphs,
      nodes_exceeds_acceptable: nodesExceedsAcceptable,
      nodes_exceeds_complex: nodesExceedsComplex,
      vcs_exceeds_acceptable: vcsExceedsAcceptable,
      node_based_splits: nodeSplits,
      node_based_formula: nodeFormula,
      vcs_based_splits: vcsSplits,
      vcs_based_formula: vcsFormula,
      subgraph_adjusted_splits: subgraphAdjusted,
      subgraph_adjustment_reason: subgraphReason,
      final_splits: finalCount,
      needs_subdivision: needs,
      estimated_per_split: estimatedPerSplit,
    },
  };
}

// ─── Analysis ────────────────────────────────────────────────────────────────

interface DiagramEntry {
  content: string;
  fence?: NonNullable<ComplexityReport["fence"]>;
}

const OPEN_MERMAID_FENCE = /^\s*```mermaid\s*$/;
const CLOSE_FENCE = /^\s*```\s*$/;

// Extract all fenced ```mermaid blocks from a markdown file.
// Mirrors find_mermaid_fences.ts with just the fields this script needs.
export function extractMarkdownFences(markdown: string): DiagramEntry[] {
  const lines = markdown.split("\n");
  const entries: DiagramEntry[] = [];
  let inFence = false;
  let fenceStart = 0;
  let buffer: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] ?? "";
    if (!inFence && OPEN_MERMAID_FENCE.test(line)) {
      inFence = true;
      fenceStart = i + 1;
      buffer = [];
    } else if (inFence && CLOSE_FENCE.test(line)) {
      const content = buffer.join("\n");
      entries.push({
        content,
        fence: {
          index: entries.length,
          keyword: detectKeyword(content) ?? "unknown",
          line_start: fenceStart,
          line_end: i + 1,
        },
      });
      inFence = false;
    } else if (inFence) {
      buffer.push(line);
    }
  }
  if (inFence) {
    throw new Error(`Unterminated \`\`\`mermaid fence opened at line ${fenceStart}`);
  }
  return entries;
}

function isMarkdownFile(filePath: string): boolean {
  const lower = filePath.toLowerCase();
  return lower.endsWith(".md") || lower.endsWith(".markdown");
}

async function readDiagrams(filePath: string): Promise<DiagramEntry[]> {
  const content = await Bun.file(filePath).text();
  if (isMarkdownFile(filePath)) {
    return extractMarkdownFences(content);
  }
  return [{ content }]; // .mmd or unknown: treat as a single diagram
}

// Analyze one file, returning one ComplexityReport per diagram found.
// - .mmd / other: a single-element array (the whole file is one diagram).
// - .md / .markdown: one entry per ```mermaid fenced block.
export async function analyzeFile(filePath: string, config: ThresholdConfig): Promise<ComplexityReport[]> {
  const diagrams = await readDiagrams(filePath);
  const reports: ComplexityReport[] = [];
  for (const entry of diagrams) {
    const report = await analyzeContent(entry.content, config, filePath);
    if (entry.fence) report.fence = entry.fence;
    reports.push(report);
  }
  return reports;
}

export async function analyzeContent(
  content: string,
  config: ThresholdConfig,
  filePath = "<stdin>",
): Promise<ComplexityReport> {
  const stats = await extractStats(content);
  const metrics = calculateComplexity(stats, config);
  const { rating, color } = rateComplexity(metrics.visual_complexity_score, stats.nodes, config);
  const { needs, count, rationale, workingOut } = recommendSubdivisions(
    metrics.visual_complexity_score,
    stats.nodes,
    stats.edges,
    stats.subgraphs,
    config,
  );
  const parseQuality = assessParseQuality(content, stats);

  return {
    file_path: filePath,
    nodes: stats.nodes,
    edges: stats.edges,
    subgraphs: stats.subgraphs,
    max_depth: stats.max_subgraph_depth,
    visual_complexity_score: metrics.visual_complexity_score,
    edge_density: metrics.edge_density,
    cyclomatic_complexity: metrics.cyclomatic_complexity,
    vcs_formula: metrics.vcs_formula,
    vcs_breakdown: metrics.vcs_breakdown,
    rating,
    color,
    needs_subdivision: needs,
    recommended_subdivisions: count,
    subdivision_rationale: rationale,
    working_out: workingOut,
    subgraph_names: stats.subgraph_names,
    parser_used: stats.parser_used,
    diagram_type: stats.diagram_type,
    parse_quality: parseQuality,
    thresholds_used: {
      node_acceptable: config.node_acceptable,
      node_complex: config.node_complex,
      vcs_acceptable: config.vcs_acceptable,
      node_target: config.node_target,
      vcs_target: config.vcs_target,
    },
  };
}

// Detects silent parser failures. All three extraction paths (Langium,
// custom line-based extractors, mermaid-core) return stats; when a
// multi-line diagram yields 0 nodes that's a strong signal that extraction
// failed and the metrics are unreliable. We surface that as a ParserFailure
// rather than letting the diagram be rated "ideal" on the basis of
// 0 ≤ every threshold.
export function assessParseQuality(content: string, stats: MermaidStats): ParseQuality {
  const contentLines = content.split("\n").filter((l) => {
    const t = l.trim();
    return t && !t.startsWith("%%") && t !== "---";
  });
  // A diagram with only a keyword line (e.g., `info`) has no structure to extract.
  if (contentLines.length <= 1) return "ok";

  // Multi-line diagram but the parser returned no structure → likely a silent
  // JISON headless failure. Also catches partial extractions (edges without
  // nodes, e.g. the stateDiagram case).
  if (stats.nodes === 0) return "failed";
  return "ok";
}

// ─── Ruff-style findings ─────────────────────────────────────────────────────
// Emit one finding per issue, grouped into a strong-typed CamelCase enum.
// Priority rules:
//   1. ParserFailure short-circuits a diagram — complexity thresholds are not
//      evaluated against garbage metrics.
//   2. Within a diagram, the node-count family is a waterfall (hard > cog >
//      acceptable). Only the most severe node-count code fires. Same for VCS.

function formatLocation(r: ComplexityReport): string {
  const file = displayPath(r.file_path);
  return r.fence ? `${file}:${r.fence.line_start}-${r.fence.line_end}` : file;
}

function displayPath(abs: string): string {
  const rel = relative(process.cwd(), abs);
  // Outside CWD or identical → keep the absolute form.
  if (!rel || rel.startsWith("..") || rel.startsWith("/")) return abs;
  return rel;
}

function boundaryHint(boundaries: string[]): string {
  if (boundaries.length === 0) return "introduce subgraphs to group related nodes before splitting";
  const shown = boundaries.slice(0, 4);
  const extra = boundaries.length > shown.length ? ` (+${boundaries.length - shown.length} more)` : "";
  return `along existing subgraph boundaries: ${shown.join(", ")}${extra}`;
}

function splitTarget(c: ThresholdConfig): string {
  return `Target ≤${c.node_target} nodes and ≤${c.vcs_target} VCS per sub-diagram.`;
}

export function buildFindings(reports: ComplexityReport[], c: ThresholdConfig): LintFinding[] {
  const findings: LintFinding[] = [];

  for (const r of reports) {
    const location = formatLocation(r);
    const boundaries = r.subgraph_names.slice();

    // Rule 1: ParserFailure short-circuits. Emit only this code.
    if (r.parse_quality === "failed") {
      findings.push({
        code: "ParserFailure",
        severity: "error",
        location,
        diagram_type: r.diagram_type,
        message: `${r.diagram_type} yielded 0 nodes from multi-line source (parser: ${r.parser_used})`,
        remediation:
          `Parser could not extract structure headlessly. Verify the diagram renders in mermaid.js. ` +
          `If it does, this diagram type needs a DOM-enabled environment (jsdom/browser) to measure — ` +
          `either disable complexity checks for this diagram type or run analysis with a DOM polyfill. ` +
          `Complexity thresholds are skipped while parsing is broken.`,
        parser: r.parser_used,
      });
      continue;
    }

    // Node-count waterfall: pick the most severe band that applies.
    if (r.nodes > c.node_hard_limit) {
      findings.push({
        code: "NodeCountExceedsHardLimit",
        severity: "error",
        location,
        diagram_type: r.diagram_type,
        message: `${r.nodes} nodes > ${c.node_hard_limit} hard limit`,
        remediation:
          `Split immediately. This diagram is beyond any comprehensible size. ` +
          `${boundaryHint(boundaries).replace(/^along /, "Split along ")}. ${splitTarget(c)}`,
        actual: r.nodes,
        threshold: c.node_hard_limit,
        boundaries,
      });
    } else if (r.nodes > c.node_complex) {
      findings.push({
        code: "NodeCountExceedsCognitiveLimit",
        severity: "error",
        location,
        diagram_type: r.diagram_type,
        message: `${r.nodes} nodes > ${c.node_complex} (Huang 2020 cognitive limit)`,
        remediation: `Split into sub-diagrams ${boundaryHint(boundaries)}. ${splitTarget(c)}`,
        actual: r.nodes,
        threshold: c.node_complex,
        boundaries,
      });
    } else if (r.nodes > c.node_acceptable) {
      findings.push({
        code: "NodeCountExceedsAcceptable",
        severity: "warning",
        location,
        diagram_type: r.diagram_type,
        message: `${r.nodes} nodes > ${c.node_acceptable} acceptable threshold`,
        remediation: `Consider splitting ${boundaryHint(boundaries)}. ${splitTarget(c)}`,
        actual: r.nodes,
        threshold: c.node_acceptable,
        boundaries,
      });
    }

    // VCS waterfall: critical > acceptable, pick most severe.
    const vcs = r.visual_complexity_score;
    if (vcs > c.vcs_complex) {
      findings.push({
        code: "VisualComplexityExceedsCritical",
        severity: "error",
        location,
        diagram_type: r.diagram_type,
        message: `VCS ${vcs.toFixed(1)} > ${c.vcs_complex} critical threshold`,
        remediation:
          `Reduce diagram complexity. Split ${boundaryHint(boundaries)}, remove redundant edges, ` +
          `or collapse leaf nodes into labeled groups. ${splitTarget(c)}`,
        actual: Number(vcs.toFixed(1)),
        threshold: c.vcs_complex,
        boundaries,
      });
    } else if (vcs > c.vcs_acceptable) {
      findings.push({
        code: "VisualComplexityExceedsAcceptable",
        severity: "warning",
        location,
        diagram_type: r.diagram_type,
        message: `VCS ${vcs.toFixed(1)} > ${c.vcs_acceptable} acceptable threshold`,
        remediation:
          `Consider reducing complexity by splitting ${boundaryHint(boundaries)} ` +
          `or pruning edges. ${splitTarget(c)}`,
        actual: Number(vcs.toFixed(1)),
        threshold: c.vcs_acceptable,
        boundaries,
      });
    }

    if (r.max_depth >= 3) {
      findings.push({
        code: "SubgraphNestingTooDeep",
        severity: "warning",
        location,
        diagram_type: r.diagram_type,
        message: `subgraph nesting depth ${r.max_depth} (≥3) hinders readability`,
        remediation:
          `Flatten nesting by inlining inner subgraphs or promoting deeply-nested groups ` +
          `into their own top-level sub-diagrams.`,
        actual: r.max_depth,
        threshold: 3,
      });
    }
  }

  return findings;
}

export function formatFinding(f: LintFinding): string {
  return `${f.location}: ${f.code} ${f.message}`;
}

// Verify at compile-time that ERROR_CODES matches the inline severity assignments above.
void ERROR_CODES;

// ─── CLI ─────────────────────────────────────────────────────────────────────

function printHelp(): void {
  console.log(`Usage: mermaid_complexity.ts <path...> [options]

Lint Mermaid diagrams for visual-complexity thresholds and parser failures.
Ruff-style output: one finding per line, silent on clean runs.

Arguments:
  path...                      One or more .mmd/.md files or directories

Options:
  --preset, -p <name>          Density preset: low | medium | high (default: high)
                               Aliases: l/low/strict, m/medium/med/balanced, h/high/permissive
  --json                       Emit findings as a top-level JSON array.
  --quiet, -q                  (reserved; default output is already minimal)
  -h, --help                   Show this help

Threshold overrides (all numeric):
  --node-ideal N        --node-acceptable N    --node-complex N
  --vcs-ideal N         --vcs-acceptable N     --vcs-complex N
  --node-target N       --vcs-target N
  --edge-weight F       --subgraph-weight F    --depth-weight F

Environment variables (same precedence as CLI overrides):
  MERMAID_COMPLEXITY_PRESET, MERMAID_COMPLEXITY_NODE_ACCEPTABLE, etc.

Output format (text, default):
  path/to/file.md:100-108: <CamelCaseCode> <terse message with numbers>

Codes (CamelCase enum):
  ParserFailure                      (error)  multi-line diagram yielded 0 nodes
  NodeCountExceedsHardLimit          (error)  nodes above absolute cap
  NodeCountExceedsCognitiveLimit     (error)  nodes > 50 (Huang 2020)
  NodeCountExceedsAcceptable         (warn)   nodes above readability threshold
  VisualComplexityExceedsCritical    (error)  VCS above critical threshold
  VisualComplexityExceedsAcceptable  (warn)   VCS above readability threshold
  SubgraphNestingTooDeep             (warn)   subgraph depth >= 3

Short-circuit: ParserFailure suppresses all other codes for that diagram —
  complexity thresholds are not evaluated against unparseable input.

Exit codes: 0 if no findings; 1 if any finding (error OR warning); 2 for usage errors.`);
}

export async function main(argv: string[] = Bun.argv.slice(2)): Promise<number> {
  const { values, positionals } = parseArgs({
    args: argv,
    options: {
      preset: { type: "string", short: "p" },
      json: { type: "boolean", default: false },
      quiet: { type: "boolean", short: "q", default: false },
      help: { type: "boolean", short: "h", default: false },
      "node-ideal": { type: "string" },
      "node-acceptable": { type: "string" },
      "node-complex": { type: "string" },
      "vcs-ideal": { type: "string" },
      "vcs-acceptable": { type: "string" },
      "vcs-complex": { type: "string" },
      "node-target": { type: "string" },
      "vcs-target": { type: "string" },
      "edge-weight": { type: "string" },
      "subgraph-weight": { type: "string" },
      "depth-weight": { type: "string" },
    },
    allowPositionals: true,
    strict: true,
  });

  if (values.help) {
    printHelp();
    return 0;
  }
  if (positionals.length === 0) {
    printHelp();
    return 2;
  }

  // Config: CLI preset > env preset > default
  let config = configFromPreset(values.preset ?? "high-density");
  config = applyEnvOverrides(config);
  const cliOverrides: Array<[string, keyof ThresholdConfig]> = [
    ["node-ideal", "node_ideal"],
    ["node-acceptable", "node_acceptable"],
    ["node-complex", "node_complex"],
    ["vcs-ideal", "vcs_ideal"],
    ["vcs-acceptable", "vcs_acceptable"],
    ["vcs-complex", "vcs_complex"],
    ["node-target", "node_target"],
    ["vcs-target", "vcs_target"],
    ["edge-weight", "edge_weight"],
    ["subgraph-weight", "subgraph_weight"],
    ["depth-weight", "depth_weight"],
  ];
  let customized = false;
  for (const [flag, field] of cliOverrides) {
    const raw = values[flag as keyof typeof values];
    if (typeof raw === "string") {
      const n = Number(raw);
      if (Number.isFinite(n)) {
        (config[field] as number) = n;
        customized = true;
      }
    }
  }
  if (customized) config.preset_name = "custom";

  const files = collectFiles(positionals);
  if (files.length === 0) {
    console.error("No files found");
    return 2;
  }

  const reports: ComplexityReport[] = [];
  for (const f of files.sort()) {
    reports.push(...(await analyzeFile(f, config)));
  }

  // Sort findings by severity (errors first), then by location. Emission order
  // controls LLM attention; errors should not be buried behind warnings.
  const findings = buildFindings(reports, config).sort((a, b) => {
    if (a.severity !== b.severity) return a.severity === "error" ? -1 : 1;
    return a.location.localeCompare(b.location);
  });

  if (values.json) {
    console.log(JSON.stringify(findings, null, 2));
  } else {
    for (const f of findings) console.log(formatFinding(f));
  }

  // Ruff semantics: any finding (error or warning) produces a non-zero exit.
  // Zero findings = clean run = exit 0 = no output.
  return findings.length > 0 ? 1 : 0;
}

const DIRECTORY_FILE_EXTS = new Set([".mmd", ".md", ".markdown"]);

function collectFiles(paths: string[]): string[] {
  const out: string[] = [];
  for (const p of paths) {
    const abs = resolve(p);
    try {
      const st = statSync(abs);
      if (st.isDirectory()) {
        for (const name of readdirSync(abs)) {
          if (DIRECTORY_FILE_EXTS.has(extname(name).toLowerCase())) {
            out.push(join(abs, name));
          }
        }
      } else if (st.isFile()) {
        out.push(abs);
      }
    } catch {
      /* missing path — ignore */
    }
  }
  return out;
}

// ─── Small helpers ───────────────────────────────────────────────────────────

function round1(x: number): number {
  return Math.round(x * 10) / 10;
}
function round2(x: number): number {
  return Math.round(x * 100) / 100;
}
function round4(x: number): number {
  return Math.round(x * 10000) / 10000;
}

// ─── Entry ───────────────────────────────────────────────────────────────────

if (import.meta.main) {
  main()
    .then((code) => process.exit(code))
    .catch((err: unknown) => {
      console.error(`error: ${err instanceof Error ? err.message : String(err)}`);
      process.exit(1);
    });
}
