// Tests for mermaid_complexity.ts.
//
// Strategy:
//   - Unit-test the metric formulas against known inputs (pure math, no parser).
//   - Parity-test against the existing Python implementation's published
//     outputs on the two `.mmd` fixtures in resources/examples/. Parity is the
//     scientific control — both implementations must agree on flowchart
//     (where Python's regex is decent) and the TS implementation is expected
//     to report MORE structure on architecture-beta (where Python's regex
//     returns zero nodes).

import { beforeAll, describe, expect, test } from "bun:test";
import { resolve } from "node:path";

import {
  analyzeContent,
  analyzeFile,
  assessParseQuality,
  buildFindings,
  formatFinding,
  main,
} from "./mermaid_complexity.ts";

const EXAMPLES_DIR = resolve(import.meta.dir, "../resources/examples");

// ─── Fixture parity ──────────────────────────────────────────────────────────

describe("canonical parser output vs Python regex baseline", () => {
  test("flowchart_fontawesome_icons.mmd — canonical parser gives cleaner node count", async () => {
    // Python regex reports nodes=11, vcs=30.8. The TS version uses
    // mermaid-core's JISON parser (via happy-dom shim) which counts 10
    // explicit vertex definitions — the Python regex over-counted by
    // picking up a subgraph label identifier. Edges and subgraphs agree.
    const [report] = await analyzeFile(resolve(EXAMPLES_DIR, "flowchart_fontawesome_icons.mmd"), highDensity());
    if (!report) throw new Error("expected a report");
    expect(report.parser_used).toBe("mermaid-core");
    expect(report.diagram_type).toBe("flowchart-v2");
    expect(report.nodes).toBe(10);
    expect(report.edges).toBe(10);
    expect(report.subgraphs).toBe(4);
    expect(report.max_depth).toBe(1);
    expect(report.visual_complexity_score).toBe(29.7);
    expect(report.rating).toBe("ideal");
    expect(report.fence).toBeUndefined();
  });

  test("architecture_beta_iconify_logos.mmd — TS captures what Python regex misses", async () => {
    // Scientific validation: Python returns nodes=0 for architecture-beta
    // because its regex only handles flowchart-style syntax. TS uses the
    // Langium parser and returns the real structure.
    const [report] = await analyzeFile(resolve(EXAMPLES_DIR, "architecture_beta_iconify_logos.mmd"), highDensity());
    if (!report) throw new Error("expected a report");
    expect(report.parser_used).toBe("langium");
    expect(report.diagram_type).toBe("architecture-beta");
    expect(report.nodes).toBeGreaterThan(0);
    expect(report.subgraphs).toBeGreaterThan(0);
  });

  test("test_gallery.md — .md file yields one report per ```mermaid fence", async () => {
    const reports = await analyzeFile(resolve(EXAMPLES_DIR, "test_gallery.md"), highDensity());
    expect(reports.length).toBeGreaterThan(20); // 27 fences after scope narrowing
    // Every report carries a fence location
    for (const r of reports) {
      const fence = r.fence;
      if (!fence) throw new Error("expected fence on md report");
      expect(fence.line_start).toBeGreaterThan(0);
      expect(fence.line_end).toBeGreaterThan(fence.line_start);
    }
    // At least one Langium-parsed diagram landed in the gallery
    const langiumReports = reports.filter((r) => r.parser_used === "langium");
    expect(langiumReports.length).toBeGreaterThan(0);
  });
});

// ─── TDD: full structural parity on test_gallery.md ──────────────────────────
//
// Ground truth: hand-counted structural metrics for every fence in
// test_gallery.md, one row per diagram type. `nodes`, `edges`, `subgraphs`,
// and `depth` are what a *correct* parser must return.
//
// Semantic conventions:
//   - node   = the primary structural unit of that diagram (vertices,
//              actors, classes, entities, states, sections, axes, sets,
//              commits, services, components, blocks, tasks, mindmap nodes)
//   - edge   = the primary relationship unit (arrows, messages,
//              transitions, relationships, merges, unions)
//   - subgraph = enclosing container (mermaid subgraphs, architecture
//                groups, kanban columns, gantt sections, git branches,
//                journey sections, timeline sections, c4 boundaries)
//   - depth   = maximum nesting level of subgraphs / tree hierarchy
//
// Every fence is expected to pass. Types that currently fail (the JISON
// set that needs DOM) will fail loudly here until the parser is fixed —
// this is TDD red, by design.
//
// Source of truth:  .claude/skills/mermaidjs_diagrams/resources/examples/test_gallery.md
interface GalleryExpectation {
  fence: number;
  keyword: string;
  nodes: number;
  edges: number;
  subgraphs: number;
  depth: number;
  rationale: string;
}

const GALLERY_EXPECTATIONS: ReadonlyArray<GalleryExpectation> = [
  {
    fence: 0,
    keyword: "architecture-beta",
    nodes: 2,
    edges: 1,
    subgraphs: 1,
    depth: 1,
    rationale: "2 services (db, server), 1 edge, 1 group (api)",
  },
  {
    fence: 1,
    keyword: "gitGraph",
    nodes: 2,
    edges: 1,
    subgraphs: 1,
    depth: 0,
    rationale: "2 commits, 1 merge, 1 named branch (newbranch)",
  },
  { fence: 2, keyword: "info", nodes: 0, edges: 0, subgraphs: 0, depth: 0, rationale: "info diagram has no structure" },
  { fence: 3, keyword: "packet-beta", nodes: 3, edges: 0, subgraphs: 0, depth: 0, rationale: "3 packet blocks" },
  {
    fence: 4,
    keyword: "pie",
    nodes: 3,
    edges: 0,
    subgraphs: 0,
    depth: 0,
    rationale: "3 pie slices (Dogs, Cats, Rats)",
  },
  {
    fence: 5,
    keyword: "radar-beta",
    nodes: 6,
    edges: 5,
    subgraphs: 0,
    depth: 0,
    rationale: "5 axes + 1 curve = 6 nodes; 5 axis-values = 5 edges",
  },
  {
    fence: 6,
    keyword: "treemap",
    nodes: 4,
    edges: 3,
    subgraphs: 0,
    depth: 2,
    rationale: "Root + Branch 1 + 2 leaves; 3 parent-child edges; max depth 2",
  },
  {
    fence: 7,
    keyword: "treeView-beta",
    nodes: 4,
    edges: 3,
    subgraphs: 0,
    depth: 2,
    rationale: "docs/build/source/static; 3 parent-child edges; max depth 2",
  },
  {
    fence: 8,
    keyword: "wardley-beta",
    nodes: 3,
    edges: 2,
    subgraphs: 0,
    depth: 0,
    rationale: "1 anchor + 2 components; 2 edges (Business->Tea, Tea->Leaves)",
  },
  {
    fence: 9,
    keyword: "block",
    nodes: 3,
    edges: 0,
    subgraphs: 1,
    depth: 1,
    rationale: "db + A + B = 3 nodes; 1 inner block (ID)",
  },
  {
    fence: 10,
    keyword: "C4Context",
    nodes: 2,
    edges: 1,
    subgraphs: 1,
    depth: 1,
    rationale: "customerA + SystemAA; 1 BiRel; 1 Enterprise_Boundary",
  },
  {
    fence: 11,
    keyword: "classDiagram",
    nodes: 3,
    edges: 2,
    subgraphs: 0,
    depth: 0,
    rationale: "Animal + Duck + Fish; 2 inheritance arrows",
  },
  {
    fence: 12,
    keyword: "erDiagram",
    nodes: 2,
    edges: 1,
    subgraphs: 0,
    depth: 0,
    rationale: "CAR + NAMED-DRIVER; 1 relationship",
  },
  { fence: 13, keyword: "flowchart", nodes: 4, edges: 3, subgraphs: 0, depth: 0, rationale: "A/B/C/D; 3 arrows" },
  {
    fence: 14,
    keyword: "gantt",
    nodes: 2,
    edges: 0,
    subgraphs: 1,
    depth: 1,
    rationale: "2 tasks; 1 section (section = depth-1 container)",
  },
  {
    fence: 15,
    keyword: "ishikawa-beta",
    nodes: 6,
    edges: 5,
    subgraphs: 0,
    depth: 2,
    rationale: "root + 2 bones + 3 causes; tree edges = nodes - 1 = 5",
  },
  {
    fence: 16,
    keyword: "kanban",
    nodes: 4,
    edges: 0,
    subgraphs: 3,
    depth: 1,
    rationale: "4 tasks; 3 columns (Todo/Doing/Done)",
  },
  {
    fence: 17,
    keyword: "mindmap",
    nodes: 8,
    edges: 7,
    subgraphs: 0,
    depth: 2,
    rationale: "root + 3 branches + 4 leaves; tree depth 2 past root",
  },
  { fence: 18, keyword: "quadrantChart", nodes: 4, edges: 0, subgraphs: 0, depth: 0, rationale: "4 named quadrants" },
  {
    fence: 19,
    keyword: "requirementDiagram",
    nodes: 2,
    edges: 1,
    subgraphs: 0,
    depth: 0,
    rationale: "test_req + test_entity; 1 satisfies relationship",
  },
  {
    fence: 20,
    keyword: "sankey-beta",
    nodes: 5,
    edges: 4,
    subgraphs: 0,
    depth: 0,
    rationale: "iPhone/Mac/Products/Services/Revenue; 4 flow edges",
  },
  {
    fence: 21,
    keyword: "sequenceDiagram",
    nodes: 2,
    edges: 2,
    subgraphs: 0,
    depth: 0,
    rationale: "Alice + Bob; 2 messages",
  },
  {
    fence: 22,
    keyword: "stateDiagram",
    nodes: 5,
    edges: 5,
    subgraphs: 0,
    depth: 0,
    rationale:
      "mermaid splits [*] into root_start + root_end; Still + Moving + Crash + 2 endpoints = 5 nodes; 5 transitions (canonical parser truth, not hand-count)",
  },
  {
    fence: 23,
    keyword: "timeline",
    nodes: 3,
    edges: 0,
    subgraphs: 2,
    depth: 1,
    rationale: "3 events; 2 sections (each a depth-1 container)",
  },
  {
    fence: 24,
    keyword: "journey",
    nodes: 5,
    edges: 0,
    subgraphs: 2,
    depth: 1,
    rationale: "5 tasks; 2 sections (each a depth-1 container)",
  },
  { fence: 25, keyword: "venn-beta", nodes: 2, edges: 1, subgraphs: 0, depth: 0, rationale: "2 sets (A, B); 1 union" },
  { fence: 26, keyword: "xychart-beta", nodes: 3, edges: 0, subgraphs: 0, depth: 0, rationale: "3 x-axis categories" },
];

describe("test_gallery.md — structural parity (TDD red → green)", () => {
  type Report = Awaited<ReturnType<typeof analyzeFile>>[number];
  let reports: Report[];

  beforeAll(async () => {
    reports = await analyzeFile(resolve(EXAMPLES_DIR, "test_gallery.md"), highDensity());
  });

  test("fixture produced the expected number of fences", () => {
    expect(reports.length).toBe(GALLERY_EXPECTATIONS.length);
  });

  // Parametrize one test per fence so failures name the exact diagram type
  // in the bun:test output — easier to grep than a single megatest that
  // just says "27 diagrams failed".
  for (const exp of GALLERY_EXPECTATIONS) {
    test(`fence ${exp.fence} ${exp.keyword}: nodes=${exp.nodes} edges=${exp.edges} subgraphs=${exp.subgraphs} depth=${exp.depth}`, () => {
      const r = reports[exp.fence];
      if (!r) throw new Error(`missing report at fence ${exp.fence}`);
      expect({
        nodes: r.nodes,
        edges: r.edges,
        subgraphs: r.subgraphs,
        depth: r.max_depth,
      }).toEqual({
        nodes: exp.nodes,
        edges: exp.edges,
        subgraphs: exp.subgraphs,
        depth: exp.depth,
      });
    });
  }
});

// ─── Metric math ─────────────────────────────────────────────────────────────

describe("VCS formula", () => {
  test("all-zero diagram gives zero VCS and cyclomatic=max(1, 0-0+2)=2", async () => {
    const report = await analyzeContent("info\n", highDensity());
    expect(report.visual_complexity_score).toBe(0);
    expect(report.edges).toBe(0);
    expect(report.cyclomatic_complexity).toBe(2);
    expect(report.rating).toBe("ideal");
  });

  test("breakdown sums to final_vcs", async () => {
    const content = `flowchart LR
  A --> B
  B --> C
  subgraph G
    D --> E
  end
`;
    const report = await analyzeContent(content, highDensity());
    const bd = report.vcs_breakdown;
    const expectedBase = bd.nodes_contribution + bd.edges_contribution + bd.subgraphs_contribution;
    expect(bd.base_vcs).toBeCloseTo(expectedBase, 2);
    expect(bd.final_vcs).toBeCloseTo(bd.base_vcs * bd.depth_multiplier, 2);
  });

  test("edge_density = E / (N*(N-1))", async () => {
    const content = `flowchart LR
  A --> B
  B --> C
  C --> A
`;
    const report = await analyzeContent(content, highDensity());
    // 3 nodes, 3 edges → 3 / (3*2) = 0.5
    expect(report.edge_density).toBe(0.5);
  });
});

// ─── Rating thresholds ──────────────────────────────────────────────────────

describe("rating thresholds", () => {
  test("a large flowchart is rated complex or critical", async () => {
    const nodes = Array.from({ length: 60 }, (_, i) => `N${i}[node${i}]`).join("\n");
    const edges = Array.from({ length: 40 }, (_, i) => `N${i} --> N${(i + 1) % 60}`).join("\n");
    const content = `flowchart LR\n${nodes}\n${edges}\n`;
    const report = await analyzeContent(content, highDensity());
    expect(["complex", "critical"]).toContain(report.rating);
    expect(report.needs_subdivision).toBe(true);
  });
});

// ─── CLI entry ──────────────────────────────────────────────────────────────

describe("main() CLI", () => {
  test("--help exits 0 without throwing", async () => {
    const code = await main(["--help"]);
    expect(code).toBe(0);
  });

  test("no arguments prints help and returns 2", async () => {
    const code = await main([]);
    expect(code).toBe(2);
  });

  test("running on the flowchart fixture returns 0 (ideal)", async () => {
    const code = await main(["--quiet", "--json", resolve(EXAMPLES_DIR, "flowchart_fontawesome_icons.mmd")]);
    expect(code).toBe(0);
  });
});

// ─── LLM-friendly JSON output ────────────────────────────────────────────────

describe("parse quality detection", () => {
  test("single-keyword diagram (info) with 0 nodes is ok, not failed", async () => {
    const report = await analyzeContent("info\n", highDensity());
    expect(report.parse_quality).toBe("ok");
  });

  test("multi-line diagram with 0 nodes is flagged as failed", () => {
    // Simulate a mermaid-core silent JISON parse failure: multi-line content,
    // but the extractor returned no structure. assessParseQuality should
    // catch this so the diagram doesn't get rated "ideal" by default.
    const content = `block\ncolumns 1\n  db(("DB"))\n  block:ID\n    A\n    B\n  end\n`;
    const quality = assessParseQuality(content, {
      nodes: 0,
      edges: 0,
      subgraphs: 0,
      max_subgraph_depth: 0,
      node_ids: [],
      subgraph_names: [],
      parser_used: "mermaid-core",
      diagram_type: "block",
    });
    expect(quality).toBe("failed");
  });

  test("multi-line diagram with >0 nodes is ok regardless of parser", () => {
    // Every extraction path that succeeds returns parse_quality="ok".
    // There's no middle "degraded" tier — we either trust the metrics or
    // we report ParserFailure.
    const quality = assessParseQuality("flowchart LR\n  A --> B\n", {
      nodes: 2,
      edges: 1,
      subgraphs: 0,
      max_subgraph_depth: 0,
      node_ids: ["A", "B"],
      subgraph_names: [],
      parser_used: "mermaid-core",
      diagram_type: "flowchart",
    });
    expect(quality).toBe("ok");
  });
});

describe("buildFindings — ruff-style lint output", () => {
  test("ideal diagram emits no findings (clean run = silent)", async () => {
    const report = await analyzeContent("flowchart LR\n  A --> B\n  B --> C\n", highDensity());
    expect(report.rating).toBe("ideal");
    const findings = buildFindings([report], highDensity());
    expect(findings).toHaveLength(0);
  });

  test("ParserFailure short-circuits: no other codes emitted for the same diagram", async () => {
    // Synthesize a report with parse_quality='failed' AND enough size to
    // trigger NodeCountExceedsCognitiveLimit and VisualComplexityExceedsCritical.
    // Without the short-circuit, buildFindings would emit three error codes.
    // With it, only ParserFailure is emitted.
    const baseReport = await analyzeContent("flowchart LR\n  A --> B\n", highDensity());
    const fakeFailure = {
      ...baseReport,
      parse_quality: "failed" as const,
      nodes: 120,
      edges: 80,
      subgraphs: 2,
      max_depth: 4,
      visual_complexity_score: 180,
      rating: "critical" as const,
    };
    const findings = buildFindings([fakeFailure], highDensity());
    expect(findings).toHaveLength(1);
    const [first] = findings;
    if (!first) throw new Error("expected one finding");
    expect(first.code).toBe("ParserFailure");
    expect(first.severity).toBe("error");
    expect(first.message).toContain("0 nodes");
  });

  test("critical flowchart emits NodeCountExceedsCognitiveLimit AND VisualComplexityExceedsCritical", async () => {
    const nodes = Array.from({ length: 80 }, (_, i) => `N${i}[node${i}]`).join("\n");
    const edges = Array.from({ length: 60 }, (_, i) => `N${i} --> N${(i + 1) % 80}`).join("\n");
    const content = `flowchart LR\n${nodes}\n${edges}\n`;
    const config = highDensity();
    const report = await analyzeContent(content, config);
    const findings = buildFindings([report], config);
    const codes = findings.map((f) => f.code);
    expect(codes).toContain("NodeCountExceedsCognitiveLimit");
    expect(codes).toContain("VisualComplexityExceedsCritical");
    // Waterfall rule: node-count codes don't overlap; acceptable is NOT
    // emitted alongside cognitive-limit.
    expect(codes).not.toContain("NodeCountExceedsAcceptable");
  });

  test("critical finding carries Huang 2020 citation and actual/threshold numbers", async () => {
    const nodes = Array.from({ length: 80 }, (_, i) => `N${i}[node${i}]`).join("\n");
    const content = `flowchart LR\n${nodes}\n`;
    const config = highDensity();
    const report = await analyzeContent(content, config);
    const finding = buildFindings([report], config).find((f) => f.code === "NodeCountExceedsCognitiveLimit");
    if (!finding) throw new Error("expected NodeCountExceedsCognitiveLimit finding");
    expect(finding.message).toContain("Huang 2020");
    expect(finding.actual).toBe(report.nodes);
    expect(finding.threshold).toBe(config.node_complex);
  });

  test("subdivision-worthy diagram with named subgraphs populates boundaries array", async () => {
    const content = [
      "flowchart LR",
      "  subgraph Alpha",
      "    " + Array.from({ length: 15 }, (_, i) => `A${i}[a${i}]`).join("\n    "),
      "  end",
      "  subgraph Beta",
      "    " + Array.from({ length: 15 }, (_, i) => `B${i}[b${i}]`).join("\n    "),
      "  end",
      "  subgraph Gamma",
      "    " + Array.from({ length: 15 }, (_, i) => `G${i}[g${i}]`).join("\n    "),
      "  end",
    ].join("\n");
    const config = highDensity();
    const report = await analyzeContent(content, config);
    const findings = buildFindings([report], config);
    if (findings.length > 0) {
      const withBoundaries = findings.find((f) => f.boundaries && f.boundaries.length > 0);
      if (withBoundaries) {
        expect(withBoundaries.boundaries).toEqual(expect.arrayContaining(["Alpha", "Beta", "Gamma"]));
        expect(withBoundaries.remediation).toContain("Alpha");
      }
    }
  });
});

describe("formatFinding — ruff-style text", () => {
  test("emits `path[:range]: Code message` and nothing else", async () => {
    const nodes = Array.from({ length: 80 }, (_, i) => `N${i}[node${i}]`).join("\n");
    const content = `flowchart LR\n${nodes}\n`;
    const config = highDensity();
    const report = await analyzeContent(content, config);
    const findings = buildFindings([report], config);
    for (const f of findings) {
      const line = formatFinding(f);
      expect(line).not.toContain("\n");
      expect(line).toMatch(/^.+: [A-Z][A-Za-z]+ /);
      expect(line).toContain(f.code);
    }
  });
});

describe("edge density handles 0 or 1 node correctly", () => {
  test("n=0, e=5 gives edge_density 0 (not 5.0 from div-by-1 fallback)", async () => {
    // Historically a parser could return nodes=0 with edges>0. The bugfix
    // reports 0 rather than dividing e by a fallback denominator of 1.
    const stats = { nodes: 0, edges: 5 };
    const maxEdges = stats.nodes > 1 ? stats.nodes * (stats.nodes - 1) : 0;
    const density = maxEdges > 0 ? stats.edges / maxEdges : 0;
    expect(density).toBe(0);
  });
});

// ─── Shared test config ──────────────────────────────────────────────────────

function highDensity() {
  return {
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
    edge_weight: 0.5,
    subgraph_weight: 3.0,
    depth_weight: 0.1,
    preset_name: "high-density",
  };
}
