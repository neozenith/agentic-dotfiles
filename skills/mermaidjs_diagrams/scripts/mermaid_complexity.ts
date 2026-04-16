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
import { extname, join, resolve } from "node:path";
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
    node_ideal: 8, node_acceptable: 12, node_complex: 20, node_hard_limit: 35,
    vcs_ideal: 15, vcs_acceptable: 25, vcs_complex: 40, vcs_critical: 60,
    node_target: 10, vcs_target: 20,
  },
  "medium-density": {
    node_ideal: 12, node_acceptable: 20, node_complex: 35, node_hard_limit: 60,
    vcs_ideal: 25, vcs_acceptable: 40, vcs_complex: 70, vcs_critical: 100,
    node_target: 15, vcs_target: 30,
  },
  "high-density": {
    node_ideal: 20, node_acceptable: 35, node_complex: 50, node_hard_limit: 100,
    vcs_ideal: 35, vcs_acceptable: 60, vcs_complex: 100, vcs_critical: 150,
    node_target: 25, vcs_target: 40,
  },
};

const PRESET_ALIASES: Record<string, string> = {
  low: "low-density", l: "low-density", strict: "low-density",
  med: "medium-density", medium: "medium-density", m: "medium-density", balanced: "medium-density",
  high: "high-density", h: "high-density", permissive: "high-density", default: "high-density",
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
    "node_ideal", "node_acceptable", "node_complex", "node_hard_limit",
    "vcs_ideal", "vcs_acceptable", "vcs_complex", "vcs_critical",
    "node_target", "vcs_target",
    "edge_weight", "subgraph_weight", "depth_weight",
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
  parser_used: "langium" | "mermaid-core" | "regex-fallback";
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
type ParseQuality = "ok" | "degraded" | "failed";
type Severity = "critical" | "complex" | "warning";

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
  // "ok" means metrics are trustworthy; "degraded" means regex fallback used;
  // "failed" means a multi-line diagram yielded 0 nodes (silent JISON/DOM fail).
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

interface Finding {
  id: string;
  file_path: string;
  location: string | null;
  diagram_type: string;
  severity: Severity;
  rating: Rating;
  parse_quality: ParseQuality;
  parser_used: MermaidStats["parser_used"];
  issues: string[];
  recommendation: string;
  boundaries: string[];
  metrics: {
    nodes: number;
    edges: number;
    subgraphs: number;
    max_depth: number;
    visual_complexity_score: number;
  };
}

interface DiagramSummary {
  id: string;
  file_path: string;
  location: string | null;
  diagram_type: string;
  parser_used: MermaidStats["parser_used"];
  rating: Rating;
  parse_quality: ParseQuality;
  metrics: {
    nodes: number;
    edges: number;
    subgraphs: number;
    max_depth: number;
    visual_complexity_score: number;
  };
}

interface JsonOutput {
  summary: {
    total: number;
    by_rating: Record<Rating, number>;
    pass: number;
    needs_attention: number;
    parse_warnings: number;
    preset: string;
    thresholds: {
      node_acceptable: number;
      node_complex: number;
      node_hard_limit: number;
      vcs_acceptable: number;
      vcs_complex: number;
      vcs_critical: number;
      node_target: number;
      vcs_target: number;
    };
  };
  findings: Finding[];
  diagrams?: DiagramSummary[];
}

// ─── Parser dispatch ─────────────────────────────────────────────────────────

const LANGIUM_TYPES: Record<string, "architecture" | "info" | "pie" | "gitGraph" | "packet" | "radar" | "treemap" | "treeView" | "wardley"> = {
  "architecture-beta": "architecture", "architecture": "architecture",
  "info": "info",
  "pie": "pie",
  "gitGraph": "gitGraph",
  "packet-beta": "packet", "packet": "packet",
  "radar-beta": "radar", "radar": "radar",
  "treemap-beta": "treemap", "treemap": "treemap",
  "treeView-beta": "treeView", "treeView": "treeView",
  "wardley-beta": "wardley", "wardley": "wardley",
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

  if (keyword in LANGIUM_TYPES) {
    try {
      return await extractLangiumStats(content, keyword);
    } catch {
      /* fall through */
    }
  }

  try {
    return await extractCoreStats(content, keyword);
  } catch {
    return extractRegexStats(content, keyword);
  }
}

// ── Langium extraction (@mermaid-js/parser) ─────────────────────────────────

async function langiumParseAny(type: string, content: string): Promise<unknown> {
  switch (type) {
    case "architecture": return langiumParse("architecture", content);
    case "info": return langiumParse("info", content);
    case "pie": return langiumParse("pie", content);
    case "gitGraph": return langiumParse("gitGraph", content);
    case "packet": return langiumParse("packet", content);
    case "radar": return langiumParse("radar", content);
    case "treemap": return langiumParse("treemap", content);
    case "treeView": return langiumParse("treeView", content);
    case "wardley": return langiumParse("wardley", content);
    default: throw new Error(`no langium parser for ${type}`);
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
    case "treemap":
    case "treeView": {
      const walk = (nodes: Array<Record<string, unknown>> | undefined, depth: number): void => {
        for (const n of nodes ?? []) {
          const label = (n.label as string | undefined) ?? (n.name as string | undefined) ?? `node_${nodeIds.length}`;
          nodeIds.push(label);
          if (depth > maxDepth) maxDepth = depth;
          const children = (n.children as Array<Record<string, unknown>> | undefined) ?? (n.nodes as Array<Record<string, unknown>> | undefined);
          if (children) {
            edges += children.length;
            walk(children, depth + 1);
          }
        }
      };
      walk((ast.root as Array<Record<string, unknown>> | undefined) ?? (ast.nodes as Array<Record<string, unknown>> | undefined), 1);
      break;
    }
    case "wardley": {
      const components = (ast.components as Array<{ name?: string }> | undefined) ?? [];
      const anchors = (ast.anchors as Array<{ name?: string }> | undefined) ?? [];
      const edgeArr = (ast.edges as Array<unknown> | undefined) ?? [];
      nodeIds.push(...components.map((c, i) => c.name ?? `comp_${i}`));
      nodeIds.push(...anchors.map((a, i) => a.name ?? `anchor_${i}`));
      edges = edgeArr.length;
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

// ── mermaid-core extraction via .db after parse ─────────────────────────────

async function extractCoreStats(content: string, keyword: string): Promise<MermaidStats> {
  const mermaid = await getMermaid();

  // mermaid.parse() lazily registers the matching diagram's JISON grammar.
  // It MUST run before getDiagramFromText, or the internal registry will
  // report "No diagram type detected".
  await mermaid.parse(content);

  const api = (mermaid as unknown as { mermaidAPI?: { getDiagramFromText?: (t: string) => Promise<{ db: Record<string, unknown>; type?: string }> } }).mermaidAPI;
  if (!api?.getDiagramFromText) throw new Error("mermaidAPI.getDiagramFromText not available");
  const diagram = await api.getDiagramFromText(content);
  const db = diagram.db as Record<string, (...args: unknown[]) => unknown>;
  const diagramType = diagram.type ?? keyword;

  // Generic extractors — mermaid's internal db exposes a common vocabulary for
  // most diagram types. We probe each known method and fall back to empty.
  const vertices = typeof db.getVertices === "function" ? (db.getVertices() as Map<string, { text?: string }> | Record<string, unknown>) : null;
  const edgesRaw = typeof db.getEdges === "function" ? (db.getEdges() as Array<unknown>) : null;
  const subGraphs = typeof db.getSubGraphs === "function" ? (db.getSubGraphs() as Array<{ id?: string; title?: string; nodes?: string[] }>) : null;

  // Diagram-type-specific fallbacks.
  const actors = typeof db.getActors === "function" ? (db.getActors() as Map<string, unknown> | Record<string, unknown>) : null;
  const messages = typeof db.getMessages === "function" ? (db.getMessages() as Array<unknown>) : null;
  const classes = typeof db.getClasses === "function" ? (db.getClasses() as Map<string, unknown> | Record<string, unknown>) : null;
  const relations = typeof db.getRelations === "function" ? (db.getRelations() as Array<unknown>) : null;
  const entities = typeof db.getEntities === "function" ? (db.getEntities() as Map<string, unknown> | Record<string, unknown>) : null;
  const erRelationships = typeof db.getRelationships === "function" ? (db.getRelationships() as Array<unknown>) : null;
  const states = typeof db.getRootDocV2 === "function" ? (db.getRootDocV2() as { doc?: Array<{ stmt?: string }> }) : null;
  const tasks = typeof db.getTasks === "function" ? (db.getTasks() as Array<unknown>) : null;

  let nodeIds: string[] = [];
  let edges = 0;
  const subgraphNames: string[] = [];
  let maxDepth = 0;

  if (vertices) {
    nodeIds = collectIds(vertices);
    edges = edgesRaw?.length ?? 0;
    if (subGraphs?.length) {
      subgraphNames.push(...subGraphs.map((s) => s.title ?? s.id ?? ""));
      maxDepth = subgraphNestingDepth(subGraphs);
    }
  } else if (actors) {
    nodeIds = collectIds(actors);
    edges = messages?.length ?? 0;
  } else if (classes) {
    nodeIds = collectIds(classes);
    edges = relations?.length ?? 0;
  } else if (entities) {
    nodeIds = collectIds(entities);
    edges = erRelationships?.length ?? 0;
  } else if (states?.doc) {
    nodeIds = states.doc.filter((s) => s.stmt === "state").map((_, i) => `state_${i}`);
    edges = states.doc.filter((s) => s.stmt === "relation").length;
  } else if (tasks) {
    nodeIds = tasks.map((_, i) => `task_${i}`);
  }

  return {
    nodes: nodeIds.length,
    edges,
    subgraphs: subgraphNames.length,
    max_subgraph_depth: maxDepth,
    node_ids: nodeIds.sort(),
    subgraph_names: subgraphNames,
    parser_used: "mermaid-core",
    diagram_type: diagramType,
  };
}

function collectIds(source: Map<string, unknown> | Record<string, unknown>): string[] {
  if (source instanceof Map) return [...source.keys()];
  return Object.keys(source);
}

function subgraphNestingDepth(subGraphs: Array<{ id?: string; nodes?: string[] }>): number {
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

// ── Regex fallback (direct port of the Python parser) ────────────────────────

function extractRegexStats(content: string, keyword: string): MermaidStats {
  const lines = content.split("\n");
  const nodes = new Set<string>();
  const subgraphStack: string[] = [];
  const subgraphNames: string[] = [];
  let edges = 0;
  let maxDepth = 0;

  const nodePatterns = [
    /^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\[/,
    /^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\(/,
    /^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\{/,
    /^[ \t]*([A-Za-z_][A-Za-z0-9_]*)>/,
    /^[ \t]*([A-Za-z_][A-Za-z0-9_]*)@\{/,
  ];
  const simpleEdgeRe = /([A-Za-z_][A-Za-z0-9_]*)\s*(?:-->|-\.->|==>|~~~|<-->|--[^-].*-->|-\.-.*-\.->|==.*==>)\s*([A-Za-z_][A-Za-z0-9_]*)/g;
  const arrowRe = /-->|-\.->|==>|~~~|<-->/g;
  const subgraphRe = /^[ \t]*subgraph\s+(?:"([^"]+)"|(\S+))?/i;
  const endRe = /^[ \t]*end\s*$/i;
  const commentRe = /^[ \t]*%%/;
  const directiveRe = /^[ \t]*(?:graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|journey)\s/i;
  const styleRe = /^[ \t]*(?:classDef|class|linkStyle|style)\s/i;
  const KEYWORDS = new Set(["graph","flowchart","subgraph","end","tb","td","bt","rl","lr","classdef","class","linkstyle","style","click","callback","direction","default","fill","stroke","color","width"]);

  for (const line of lines) {
    if (!line.trim() || commentRe.test(line) || directiveRe.test(line) || styleRe.test(line)) continue;

    const sg = subgraphRe.exec(line);
    if (sg) {
      const name = sg[1] ?? sg[2] ?? `subgraph_${subgraphNames.length}`;
      subgraphStack.push(name);
      subgraphNames.push(name);
      if (subgraphStack.length > maxDepth) maxDepth = subgraphStack.length;
      continue;
    }
    if (endRe.test(line)) { if (subgraphStack.length) subgraphStack.pop(); continue; }

    edges += (line.match(arrowRe) ?? []).length;

    let m: RegExpExecArray | null;
    simpleEdgeRe.lastIndex = 0;
    while ((m = simpleEdgeRe.exec(line)) !== null) {
      if (m[1]) nodes.add(m[1]);
      if (m[2]) nodes.add(m[2]);
    }
    for (const pat of nodePatterns) {
      const hit = pat.exec(line);
      if (hit?.[1]) nodes.add(hit[1]);
    }
    const potential = line.match(/\b([A-Za-z_][A-Za-z0-9_]*)\b/g) ?? [];
    for (const p of potential) {
      if (KEYWORDS.has(p.toLowerCase())) continue;
      const esc = p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      if (new RegExp(`\\b${esc}\\b\\s*(?:-->|-\\.->|==>|<--|<-\\.|-<)`).test(line)
          || new RegExp(`(?:-->|-\\.->|==>|<--|<-\\.|-<)\\s*\\b${esc}\\b`).test(line)) {
        nodes.add(p);
      }
    }
  }

  return {
    nodes: nodes.size,
    edges,
    subgraphs: subgraphNames.length,
    max_subgraph_depth: maxDepth,
    node_ids: [...nodes].sort(),
    subgraph_names: subgraphNames,
    parser_used: "regex-fallback",
    diagram_type: keyword,
  };
}

// ─── Metrics ─────────────────────────────────────────────────────────────────

function calculateComplexity(stats: MermaidStats, config: ThresholdConfig): ComplexityMetrics {
  const n = stats.nodes, e = stats.edges, s = stats.subgraphs, d = stats.max_subgraph_depth;
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
  vcs: number, nodes: number, edges: number, subgraphs: number, config: ThresholdConfig,
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
  if (nodesExceedsAcceptable) rationaleParts.push(`Node count (${nodes}) exceeds threshold (${config.node_acceptable})`);
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
    needs, count: finalCount, rationale,
    workingOut: {
      nodes, vcs, subgraphs,
      nodes_exceeds_acceptable: nodesExceedsAcceptable,
      nodes_exceeds_complex: nodesExceedsComplex,
      vcs_exceeds_acceptable: vcsExceedsAcceptable,
      node_based_splits: nodeSplits, node_based_formula: nodeFormula,
      vcs_based_splits: vcsSplits, vcs_based_formula: vcsFormula,
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
export async function analyzeFile(
  filePath: string,
  config: ThresholdConfig,
): Promise<ComplexityReport[]> {
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
  content: string, config: ThresholdConfig, filePath = "<stdin>",
): Promise<ComplexityReport> {
  const stats = await extractStats(content);
  const metrics = calculateComplexity(stats, config);
  const { rating, color } = rateComplexity(metrics.visual_complexity_score, stats.nodes, config);
  const { needs, count, rationale, workingOut } = recommendSubdivisions(
    metrics.visual_complexity_score, stats.nodes, stats.edges, stats.subgraphs, config,
  );
  const parseQuality = assessParseQuality(content, stats);

  return {
    file_path: filePath,
    nodes: stats.nodes, edges: stats.edges, subgraphs: stats.subgraphs, max_depth: stats.max_subgraph_depth,
    visual_complexity_score: metrics.visual_complexity_score,
    edge_density: metrics.edge_density,
    cyclomatic_complexity: metrics.cyclomatic_complexity,
    vcs_formula: metrics.vcs_formula,
    vcs_breakdown: metrics.vcs_breakdown,
    rating, color,
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

// Detects silent parser failures. Mermaid-core's JISON grammars silently fall
// through under headless DOM for several diagram types (block, c4, er, kanban,
// mindmap, quadrantChart, requirement, sankey, journey, venn, xychart, etc.),
// returning stats with 0 nodes/edges. Without this check, those get rated
// "ideal" because 0 ≤ every threshold, misleading LLM consumers.
export function assessParseQuality(content: string, stats: MermaidStats): ParseQuality {
  if (stats.parser_used === "regex-fallback") return "degraded";

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

// ─── LLM-friendly JSON builders ──────────────────────────────────────────────
// Transform verbose ComplexityReport[] into a concise { summary, findings,
// diagrams } shape. `findings` is the only slice most LLMs need — it carries
// concrete `issues[]`, a single-sentence `recommendation`, and split
// `boundaries[]` derived from existing subgraphs. `diagrams` is a compact
// per-diagram roll-up (no vcs_breakdown, no working_out, no formulas).

function reportId(r: ComplexityReport): string {
  const file = basename(r.file_path);
  return r.fence ? `${file}:L${r.fence.line_start}-L${r.fence.line_end}#${r.diagram_type}` : file;
}

function reportLocation(r: ComplexityReport): string | null {
  return r.fence ? `L${r.fence.line_start}-L${r.fence.line_end}` : null;
}

function hasFinding(r: ComplexityReport): boolean {
  return r.rating === "complex" || r.rating === "critical" || r.parse_quality !== "ok";
}

export function buildFinding(r: ComplexityReport, c: ThresholdConfig): Finding {
  const issues: string[] = [];
  const severity: Severity =
    r.rating === "critical" ? "critical" : r.rating === "complex" ? "complex" : "warning";

  if (r.parse_quality === "failed") {
    issues.push(
      `Parser returned 0 nodes for a multi-line ${r.diagram_type} diagram via ${r.parser_used}. ` +
        `This is a silent parse failure — the JISON grammar likely needs a real DOM to extract structure. Metrics are unreliable.`,
    );
  } else if (r.parse_quality === "degraded") {
    issues.push(
      `Using regex-fallback parser for ${r.diagram_type} — both the Langium and mermaid-core paths failed. Metrics are approximate.`,
    );
  }

  if (r.rating === "critical") {
    if (r.nodes > c.node_complex) {
      issues.push(`Node count ${r.nodes} exceeds cognitive limit of ${c.node_complex} (Huang et al. 2020)`);
    }
    if (r.visual_complexity_score > c.vcs_complex) {
      issues.push(
        `Visual Complexity Score ${r.visual_complexity_score.toFixed(1)} exceeds critical threshold of ${c.vcs_complex}`,
      );
    }
    if (r.nodes > c.node_hard_limit) {
      issues.push(`Node count ${r.nodes} exceeds hard limit of ${c.node_hard_limit}`);
    }
  } else if (r.rating === "complex") {
    if (r.nodes > c.node_acceptable) {
      issues.push(`Node count ${r.nodes} exceeds acceptable threshold of ${c.node_acceptable}`);
    }
    if (r.visual_complexity_score > c.vcs_acceptable) {
      issues.push(
        `Visual Complexity Score ${r.visual_complexity_score.toFixed(1)} exceeds acceptable threshold of ${c.vcs_acceptable}`,
      );
    }
  }

  if (r.max_depth >= 3) {
    issues.push(`Subgraph nesting depth ${r.max_depth} (≥3) hinders readability`);
  }

  const boundaries = r.subgraph_names.slice();
  const recommendation = buildRecommendation(r, c, boundaries);

  return {
    id: reportId(r),
    file_path: r.file_path,
    location: reportLocation(r),
    diagram_type: r.diagram_type,
    severity,
    rating: r.rating,
    parse_quality: r.parse_quality,
    parser_used: r.parser_used,
    issues,
    recommendation,
    boundaries,
    metrics: {
      nodes: r.nodes,
      edges: r.edges,
      subgraphs: r.subgraphs,
      max_depth: r.max_depth,
      visual_complexity_score: r.visual_complexity_score,
    },
  };
}

function buildRecommendation(r: ComplexityReport, c: ThresholdConfig, boundaries: string[]): string {
  if (r.parse_quality === "failed") {
    return `Metrics for ${r.diagram_type} cannot be extracted reliably headlessly. Either review this diagram manually, skip complexity enforcement for this diagram type, or run analysis in an environment with a real DOM (jsdom/browser).`;
  }
  if (!r.needs_subdivision && r.parse_quality === "degraded") {
    return `Consider rewriting the diagram using syntax the canonical parser recognizes, or accept that metrics from regex fallback are approximate.`;
  }
  if (!r.needs_subdivision) return "No action required.";

  const splits = r.recommended_subdivisions;
  const target = `Target: ≤${c.node_target} nodes and ≤${c.vcs_target} VCS per sub-diagram.`;
  if (boundaries.length >= 2) {
    const shown = boundaries.slice(0, Math.max(splits, 4));
    const extra = boundaries.length > shown.length ? ` (+${boundaries.length - shown.length} more)` : "";
    return `Split into ${splits} sub-diagrams along existing subgraph boundaries: ${shown.join(", ")}${extra}. ${target}`;
  }
  return `Split into ${splits} sub-diagrams. No subgraph boundaries exist — introduce subgraphs to group related nodes before splitting. ${target}`;
}

function buildDiagramSummary(r: ComplexityReport): DiagramSummary {
  return {
    id: reportId(r),
    file_path: r.file_path,
    location: reportLocation(r),
    diagram_type: r.diagram_type,
    parser_used: r.parser_used,
    rating: r.rating,
    parse_quality: r.parse_quality,
    metrics: {
      nodes: r.nodes,
      edges: r.edges,
      subgraphs: r.subgraphs,
      max_depth: r.max_depth,
      visual_complexity_score: r.visual_complexity_score,
    },
  };
}

export function buildJsonOutput(
  reports: ComplexityReport[],
  config: ThresholdConfig,
  includeDiagrams = true,
): JsonOutput {
  const byRating: Record<Rating, number> = { ideal: 0, acceptable: 0, complex: 0, critical: 0 };
  let parseWarnings = 0;
  for (const r of reports) {
    byRating[r.rating]++;
    if (r.parse_quality !== "ok") parseWarnings++;
  }
  const findings = reports.filter(hasFinding).map((r) => buildFinding(r, config));
  const out: JsonOutput = {
    summary: {
      total: reports.length,
      by_rating: byRating,
      pass: byRating.ideal + byRating.acceptable,
      needs_attention: byRating.complex + byRating.critical,
      parse_warnings: parseWarnings,
      preset: config.preset_name,
      thresholds: {
        node_acceptable: config.node_acceptable,
        node_complex: config.node_complex,
        node_hard_limit: config.node_hard_limit,
        vcs_acceptable: config.vcs_acceptable,
        vcs_complex: config.vcs_complex,
        vcs_critical: config.vcs_critical,
        node_target: config.node_target,
        vcs_target: config.vcs_target,
      },
    },
    findings,
  };
  if (includeDiagrams) out.diagrams = reports.map(buildDiagramSummary);
  return out;
}

// ─── Formatting ──────────────────────────────────────────────────────────────

const COLORS = {
  green: "\x1b[92m", yellow: "\x1b[93m", orange: "\x1b[38;5;208m", red: "\x1b[91m",
  reset: "\x1b[0m", dim: "\x1b[2m", bold: "\x1b[1m",
} as const;
const EMOJI: Record<Rating, string> = { ideal: "✅", acceptable: "🟡", complex: "🟠", critical: "🔴" };

function formatReport(r: ComplexityReport, showWorking: boolean): string {
  const c = COLORS[r.color];
  const rs = COLORS.reset, dim = COLORS.dim, bold = COLORS.bold;
  const bd = r.vcs_breakdown;
  const out: string[] = [
    "",
    "=".repeat(70),
    `📊 ${bold}${basename(r.file_path)}${rs}${r.fence ? ` ${dim}[fence ${r.fence.index} L${r.fence.line_start}-L${r.fence.line_end}]${rs}` : ""}  ${dim}(${r.diagram_type} via ${r.parser_used})${rs}`,
    "=".repeat(70),
    "",
    "📈 Raw Metrics:",
    `   Nodes:     ${pad(r.nodes, 4)}  ${dim}(acceptable ≤${r.thresholds_used.node_acceptable})${rs}`,
    `   Edges:     ${pad(r.edges, 4)}`,
    `   Subgraphs: ${pad(r.subgraphs, 4)}  (depth: ${r.max_depth})`,
    "",
    "📐 Visual Complexity Score (VCS):",
    `   Formula:  ${dim}${r.vcs_formula}${rs}`,
    `   Result:   ${c}${bold}${r.visual_complexity_score.toFixed(1).padStart(6)}${rs}  ${dim}(acceptable ≤${r.thresholds_used.vcs_acceptable})${rs}`,
    "",
    `   ${dim}Breakdown:${rs}`,
    `     Nodes:     ${bd.nodes_contribution.toFixed(1).padStart(6)}`,
    `     Edges:   + ${bd.edges_contribution.toFixed(1).padStart(6)}  ${dim}(${r.edges} × edge_weight)${rs}`,
    `     Subgraphs:+ ${bd.subgraphs_contribution.toFixed(1).padStart(6)}  ${dim}(${r.subgraphs} × subgraph_weight)${rs}`,
    `     Base VCS:  ${bd.base_vcs.toFixed(1).padStart(6)}`,
    `     × Depth:   ${bd.depth_multiplier.toFixed(2).padStart(6)}  ${dim}(1 + ${r.max_depth} × depth_weight)${rs}`,
    "     ─────────────────",
    `     Final:     ${bd.final_vcs.toFixed(1).padStart(6)}`,
    "",
    `   Edge Density:          ${r.edge_density.toFixed(4).padStart(6)}`,
    `   Cyclomatic Complexity: ${pad(r.cyclomatic_complexity, 6)}`,
    "",
    `🎯 Rating: ${EMOJI[r.rating]} ${c}${bold}${r.rating.toUpperCase()}${rs}`,
  ];

  if (r.needs_subdivision) {
    out.push("", `⚠️  ${bold}SUBDIVISION RECOMMENDED${rs}`);
    out.push(`   Recommended splits: ${bold}${r.recommended_subdivisions}${rs}`);
    out.push(`   Rationale: ${r.subdivision_rationale}`);
    if (r.subgraph_names.length) {
      const head = r.subgraph_names.slice(0, 5).join(", ");
      const tail = r.subgraph_names.length > 5 ? ` (+${r.subgraph_names.length - 5} more)` : "";
      out.push(`   Potential boundaries: ${head}${tail}`);
    }
    if (showWorking && r.working_out) {
      const wo = r.working_out;
      out.push(
        "",
        `📝 ${bold}Calculation Working Out:${rs}`,
        "",
        "   Step 1: Check thresholds",
        `     Nodes (${wo.nodes}) > acceptable (${r.thresholds_used.node_acceptable})? ${wo.nodes_exceeds_acceptable ? "YES ❌" : "NO ✓"}`,
        `     VCS (${wo.vcs.toFixed(1)}) > acceptable (${r.thresholds_used.vcs_acceptable})? ${wo.vcs_exceeds_acceptable ? "YES ❌" : "NO ✓"}`,
        "",
        "   Step 2: Calculate node-based splits",
        `     ${wo.node_based_formula}`,
        `     → ${wo.node_based_splits} split(s) needed`,
        "",
        "   Step 3: Calculate VCS-based splits",
        `     ${wo.vcs_based_formula}`,
        `     → ${wo.vcs_based_splits} split(s) needed`,
        "",
        "   Step 4: Take maximum",
        `     max(${wo.node_based_splits}, ${wo.vcs_based_splits}) = ${Math.max(wo.node_based_splits, wo.vcs_based_splits)}`,
      );
      if (wo.subgraph_adjusted_splits !== Math.max(wo.node_based_splits, wo.vcs_based_splits)) {
        out.push("", "   Step 5: Subgraph adjustment", `     ${wo.subgraph_adjustment_reason}`);
      }
      out.push("", `   ${bold}Final recommendation: ${wo.final_splits} split(s)${rs}`);

      if (wo.estimated_per_split.length) {
        out.push("", `🔄 ${bold}Estimated Per-Split Complexity:${rs}`);
        let anyFurther = false;
        for (const split of wo.estimated_per_split) {
          const splitColor = COLORS[{ ideal: "green", acceptable: "yellow", complex: "orange", critical: "red" }[split.estimated_rating] as Color];
          const status = split.estimated_rating === "ideal" || split.estimated_rating === "acceptable" ? "✓" : "⚠️";
          out.push(`   Split ${split.split_number}: ~${split.estimated_nodes} nodes, ~${split.estimated_vcs.toFixed(0)} VCS → ${splitColor}${split.estimated_rating}${rs} ${status}`);
          if (split.would_need_further_subdivision) {
            anyFurther = true;
            if (split.recursive_recommendation) out.push(`      └─ ${dim}${split.recursive_recommendation}${rs}`);
          }
        }
        if (anyFurther) out.push("", `   ⚠️  ${bold}Warning:${rs} Some splits would still exceed thresholds.`, "      Consider increasing splits or reducing detail level.");
      }
    }
  } else {
    out.push("", "✅ No subdivision needed - diagram is within visual clarity thresholds");
  }

  return out.join("\n");
}

function formatSummary(reports: ComplexityReport[]): string {
  const byRating: Record<Rating, ComplexityReport[]> = { ideal: [], acceptable: [], complex: [], critical: [] };
  for (const r of reports) byRating[r.rating].push(r);
  const needsWork = [...byRating.complex, ...byRating.critical];
  const lines = [
    "",
    "=".repeat(70),
    `📊 SUMMARY: ${reports.length} diagram(s) analyzed`,
    "=".repeat(70),
    "",
    `  ✅ Ideal:      ${pad(byRating.ideal.length, 3)}`,
    `  🟡 Acceptable: ${pad(byRating.acceptable.length, 3)}`,
    `  🟠 Complex:    ${pad(byRating.complex.length, 3)}`,
    `  🔴 Critical:   ${pad(byRating.critical.length, 3)}`,
  ];
  if (needsWork.length) {
    lines.push("", "📋 Diagrams needing attention:");
    for (const r of needsWork.sort((a, b) => b.visual_complexity_score - a.visual_complexity_score)) {
      lines.push(`   • ${basename(r.file_path)}: VCS=${r.visual_complexity_score.toFixed(1)}, nodes=${r.nodes}, recommend ${r.recommended_subdivisions} split(s)`);
    }
  }
  return lines.join("\n");
}

// ─── CLI ─────────────────────────────────────────────────────────────────────

function printHelp(): void {
  console.log(`Usage: mermaid_complexity.ts <path...> [options]

Analyze Mermaid diagram complexity via canonical parsers.

Arguments:
  path...                      One or more .mmd files or directories

Options:
  --preset, -p <name>          Density preset: low | medium | high (default: high)
                               Aliases: l/low/strict, m/medium/med/balanced, h/high/permissive
  --json                       Emit { summary, findings, diagrams } JSON.
                               - summary: totals, preset, thresholds
                               - findings: only diagrams with issues/warnings, each
                                 with concrete issues[], a recommendation, and
                                 boundaries[] derived from subgraphs (LLM-friendly)
                               - diagrams: compact per-diagram roll-up
  --findings-only              With --json, drop the diagrams[] array so only
                               summary + findings are emitted. Maximum concision
                               for LLM consumers.
  --summary-only               Emit only the summary block (text mode)
  --show-working, -w           Show subdivision calculation details
  --quiet, -q                  Minimal output
  -h, --help                   Show this help

Threshold overrides (all numeric):
  --node-ideal N        --node-acceptable N    --node-complex N
  --vcs-ideal N         --vcs-acceptable N     --vcs-complex N
  --node-target N       --vcs-target N
  --edge-weight F       --subgraph-weight F    --depth-weight F

Environment variables (same precedence as CLI overrides):
  MERMAID_COMPLEXITY_PRESET, MERMAID_COMPLEXITY_NODE_ACCEPTABLE, etc.

Exit codes: 0 if all diagrams ideal/acceptable, 1 if any complex/critical.`);
}

export async function main(argv: string[] = Bun.argv.slice(2)): Promise<number> {
  const { values, positionals } = parseArgs({
    args: argv,
    options: {
      preset: { type: "string", short: "p" },
      json: { type: "boolean", default: false },
      "findings-only": { type: "boolean", default: false },
      "summary-only": { type: "boolean", default: false },
      "show-working": { type: "boolean", short: "w", default: false },
      quiet: { type: "boolean", short: "q", default: false },
      help: { type: "boolean", short: "h", default: false },
      "node-ideal": { type: "string" }, "node-acceptable": { type: "string" }, "node-complex": { type: "string" },
      "vcs-ideal": { type: "string" }, "vcs-acceptable": { type: "string" }, "vcs-complex": { type: "string" },
      "node-target": { type: "string" }, "vcs-target": { type: "string" },
      "edge-weight": { type: "string" }, "subgraph-weight": { type: "string" }, "depth-weight": { type: "string" },
    },
    allowPositionals: true,
    strict: true,
  });

  if (values.help) { printHelp(); return 0; }
  if (positionals.length === 0) { printHelp(); return 2; }

  // Config: CLI preset > env preset > default
  let config = configFromPreset(values.preset ?? "high-density");
  config = applyEnvOverrides(config);
  const cliOverrides: Array<[string, keyof ThresholdConfig]> = [
    ["node-ideal","node_ideal"], ["node-acceptable","node_acceptable"], ["node-complex","node_complex"],
    ["vcs-ideal","vcs_ideal"], ["vcs-acceptable","vcs_acceptable"], ["vcs-complex","vcs_complex"],
    ["node-target","node_target"], ["vcs-target","vcs_target"],
    ["edge-weight","edge_weight"], ["subgraph-weight","subgraph_weight"], ["depth-weight","depth_weight"],
  ];
  let customized = false;
  for (const [flag, field] of cliOverrides) {
    const raw = values[flag as keyof typeof values];
    if (typeof raw === "string") {
      const n = Number(raw);
      if (Number.isFinite(n)) { (config[field] as number) = n; customized = true; }
    }
  }
  if (customized) config.preset_name = "custom";

  if (!values.quiet && !values.json) {
    console.log(`\n🔧 Using preset: ${config.preset_name}`);
    console.log(`   Thresholds: nodes ≤${config.node_acceptable}/${config.node_complex}, VCS ≤${config.vcs_acceptable}/${config.vcs_complex}, targets: ${config.node_target}/${config.vcs_target}`);
  }

  const files = collectFiles(positionals);
  if (files.length === 0) {
    console.error("❌ No files found");
    return 1;
  }

  const reports: ComplexityReport[] = [];
  for (const f of files.sort()) {
    reports.push(...(await analyzeFile(f, config)));
  }

  if (values.json) {
    const output = buildJsonOutput(reports, config, !values["findings-only"]);
    console.log(JSON.stringify(output, null, 2));
  } else if (values["summary-only"]) {
    console.log(formatSummary(reports));
  } else {
    for (const r of reports) {
      if (!values.quiet) console.log(formatReport(r, values["show-working"] ?? false));
    }
    if (reports.length > 1) console.log(formatSummary(reports));
  }

  const hasIssues = reports.some((r) => r.rating === "complex" || r.rating === "critical");
  return hasIssues ? 1 : 0;
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

function round1(x: number): number { return Math.round(x * 10) / 10; }
function round2(x: number): number { return Math.round(x * 100) / 100; }
function round4(x: number): number { return Math.round(x * 10000) / 10000; }
function pad(n: number, w: number): string { return n.toString().padStart(w); }
function basename(p: string): string { return p.split("/").pop() ?? p; }

// ─── Entry ───────────────────────────────────────────────────────────────────

if (import.meta.main) {
  main()
    .then((code) => process.exit(code))
    .catch((err: unknown) => {
      console.error(`error: ${err instanceof Error ? err.message : String(err)}`);
      process.exit(1);
    });
}
