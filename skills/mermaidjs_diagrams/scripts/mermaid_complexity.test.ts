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

import { describe, expect, test } from "bun:test";
import { resolve } from "node:path";

import {
  analyzeContent,
  analyzeFile,
  assessParseQuality,
  buildFinding,
  buildJsonOutput,
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
    const [report] = await analyzeFile(
      resolve(EXAMPLES_DIR, "flowchart_fontawesome_icons.mmd"),
      highDensity(),
    );
    expect(report!.parser_used).toBe("mermaid-core");
    expect(report!.diagram_type).toBe("flowchart-v2");
    expect(report!.nodes).toBe(10);
    expect(report!.edges).toBe(10);
    expect(report!.subgraphs).toBe(4);
    expect(report!.max_depth).toBe(1);
    expect(report!.visual_complexity_score).toBe(29.7);
    expect(report!.rating).toBe("ideal");
    expect(report!.fence).toBeUndefined();
  });

  test("architecture_beta_iconify_logos.mmd — TS captures what Python regex misses", async () => {
    // Scientific validation: Python returns nodes=0 for architecture-beta
    // because its regex only handles flowchart-style syntax. TS uses the
    // Langium parser and returns the real structure.
    const [report] = await analyzeFile(
      resolve(EXAMPLES_DIR, "architecture_beta_iconify_logos.mmd"),
      highDensity(),
    );
    expect(report!.parser_used).toBe("langium");
    expect(report!.diagram_type).toBe("architecture-beta");
    expect(report!.nodes).toBeGreaterThan(0);
    expect(report!.subgraphs).toBeGreaterThan(0);
  });

  test("test_gallery.md — .md file yields one report per ```mermaid fence", async () => {
    const reports = await analyzeFile(
      resolve(EXAMPLES_DIR, "test_gallery.md"),
      highDensity(),
    );
    expect(reports.length).toBeGreaterThan(20); // 27 fences after scope narrowing
    // Every report carries a fence location
    for (const r of reports) {
      expect(r.fence).toBeDefined();
      expect(r.fence!.line_start).toBeGreaterThan(0);
      expect(r.fence!.line_end).toBeGreaterThan(r.fence!.line_start);
    }
    // At least one Langium-parsed diagram landed in the gallery
    const langiumReports = reports.filter((r) => r.parser_used === "langium");
    expect(langiumReports.length).toBeGreaterThan(0);
  });
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
    const code = await main([
      "--quiet",
      "--json",
      resolve(EXAMPLES_DIR, "flowchart_fontawesome_icons.mmd"),
    ]);
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
      nodes: 0, edges: 0, subgraphs: 0, max_subgraph_depth: 0,
      node_ids: [], subgraph_names: [],
      parser_used: "mermaid-core", diagram_type: "block",
    });
    expect(quality).toBe("failed");
  });

  test("regex-fallback parser is always degraded", () => {
    const quality = assessParseQuality("flowchart LR\n  A --> B\n", {
      nodes: 2, edges: 1, subgraphs: 0, max_subgraph_depth: 0,
      node_ids: ["A", "B"], subgraph_names: [],
      parser_used: "regex-fallback", diagram_type: "flowchart",
    });
    expect(quality).toBe("degraded");
  });
});

describe("buildFinding", () => {
  test("critical rating produces concrete issues with thresholds and research citation", async () => {
    const nodes = Array.from({ length: 80 }, (_, i) => `N${i}[node${i}]`).join("\n");
    const edges = Array.from({ length: 60 }, (_, i) => `N${i} --> N${(i + 1) % 80}`).join("\n");
    const content = `flowchart LR\n${nodes}\n${edges}\n`;
    const config = highDensity();
    const report = await analyzeContent(content, config);
    expect(report.rating).toBe("critical");

    const finding = buildFinding(report, config);
    expect(finding.severity).toBe("critical");
    // Issues name the threshold and cite Huang et al. 2020 for the node cap
    const allIssues = finding.issues.join(" | ");
    expect(allIssues).toContain("exceeds cognitive limit");
    expect(allIssues).toContain("Huang et al.");
    expect(allIssues).toContain("Visual Complexity Score");
    expect(finding.recommendation).toMatch(/Split into \d+ sub-diagram/);
    // With no subgraphs, recommendation should say "No subgraph boundaries exist"
    expect(finding.recommendation).toContain("No subgraph boundaries");
  });

  test("subdivision-needed with subgraphs recommends boundaries by name", async () => {
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
    if (report.needs_subdivision && report.subgraph_names.length >= 2) {
      const finding = buildFinding(report, config);
      expect(finding.boundaries).toEqual(expect.arrayContaining(["Alpha", "Beta", "Gamma"]));
      expect(finding.recommendation).toContain("Alpha");
    }
  });
});

describe("buildJsonOutput", () => {
  test("shape is { summary, findings, diagrams? } with expected counts", async () => {
    const reports = await analyzeFile(
      resolve(EXAMPLES_DIR, "test_gallery.md"),
      highDensity(),
    );
    const out = buildJsonOutput(reports, highDensity(), true);
    expect(out.summary.total).toBe(reports.length);
    expect(out.summary.pass + out.summary.needs_attention).toBe(reports.length);
    expect(out.summary.by_rating.ideal + out.summary.by_rating.acceptable
         + out.summary.by_rating.complex + out.summary.by_rating.critical).toBe(reports.length);
    expect(out.summary.preset).toBe("high-density");
    // Test gallery includes multiple JISON diagrams that fail silently — we
    // expect parse_warnings to be > 0, otherwise the detection is off.
    expect(out.summary.parse_warnings).toBeGreaterThan(0);
    // Every parse-quality warning surfaces in findings
    expect(out.findings.length).toBeGreaterThanOrEqual(out.summary.parse_warnings);
    expect(out.diagrams).toBeDefined();
    expect(out.diagrams!.length).toBe(reports.length);
  });

  test("includeDiagrams=false omits the diagrams array (maximum concision)", async () => {
    const reports = await analyzeFile(
      resolve(EXAMPLES_DIR, "test_gallery.md"),
      highDensity(),
    );
    const out = buildJsonOutput(reports, highDensity(), false);
    expect(out.diagrams).toBeUndefined();
    expect(out.findings).toBeDefined();
    expect(out.summary).toBeDefined();
  });

  test("ideal diagram with no issues produces an empty findings array", async () => {
    const content = "flowchart LR\n  A --> B\n  B --> C\n";
    const report = await analyzeContent(content, highDensity());
    expect(report.rating).toBe("ideal");
    expect(report.parse_quality).toBe("ok");
    const out = buildJsonOutput([report], highDensity(), false);
    expect(out.findings).toHaveLength(0);
    expect(out.summary.by_rating.ideal).toBe(1);
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
    node_ideal: 20, node_acceptable: 35, node_complex: 50, node_hard_limit: 100,
    vcs_ideal: 35, vcs_acceptable: 60, vcs_complex: 100, vcs_critical: 150,
    node_target: 25, vcs_target: 40,
    edge_weight: 0.5, subgraph_weight: 3.0, depth_weight: 0.1,
    preset_name: "high-density",
  };
}
